import logging
import re
from collections.abc import Iterator

from langsmith import traceable
from openai import OpenAI, OpenAIError
from sqlalchemy.orm import Session

from config import settings
from tablebase import DocumentChunks

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 12000
OPENAI_TIMEOUT_SECONDS = 60
OPENAI_UNAVAILABLE_MESSAGE = (
    "Je ne peux pas générer de réponse pour le moment. "
    "Le service IA est temporairement indisponible."
)
NO_RELEVANT_DOCUMENT_MESSAGE = (
    "Je ne sais pas. Aucun document pertinent n'a été trouvé "
    "dans votre base documentaire."
)
OPENAI_SYSTEM_INSTRUCTIONS = (
    "Tu es un assistant RAG. Réponds uniquement à partir du contexte documentaire "
    "fourni dans le prompt utilisateur. Si le contexte ne contient pas l'information, "
    "dis que tu ne sais pas. Ne révèle jamais d'erreur technique, de clé API ou "
    "d'information sensible."
)


def get_user_collection_name(user_id: int) -> str:
    """Helper de nommage garde pour les tests et la coherence historique."""
    return f"user_{user_id}"


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """Decoupe le texte extrait d'un PDF en chunks avec chevauchement."""
    cleaned_text = " ".join(text.split())
    if not cleaned_text:
        return []

    chunks = []
    start = 0

    while start < len(cleaned_text):
        end = start + chunk_size
        chunks.append(cleaned_text[start:end])

        if end >= len(cleaned_text):
            break

        start = max(end - chunk_overlap, start + 1)

    return chunks


def format_document_source(metadata: dict) -> str:
    """Construit une source lisible a partir des metadata du chunk."""
    filename = metadata.get("filename") or "document inconnu"
    page = metadata.get("page")

    if page is None:
        return filename

    return f"{filename}, page {int(page) + 1}"


def format_retrieved_documents(docs) -> str:
    """Formate les chunks retrouves en contexte avec sources explicites."""
    if not docs:
        return "Aucun document pertinent trouve dans la base documentaire."

    formatted_docs = []
    for index, doc in enumerate(docs, start=1):
        source = format_document_source(doc["metadata"])
        formatted_docs.append(
            f"Extrait {index}\n"
            f"Source: {source}\n"
            f"Contenu: {doc['content']}"
        )

    return "\n\n".join(formatted_docs)


def _tokenize_query(query: str) -> set[str]:
    """Extrait des mots simples depuis la question utilisateur."""
    return {
        token
        for token in re.findall(r"\w+", query.lower())
        if len(token) >= 3
    }


@traceable(name="retrieve_documents")
def retrieve_documents(db: Session, query: str, user_id: int, limit: int = 5) -> list[dict]:
    """Retrouve les chunks les plus pertinents avec un scoring leger par mots."""
    query_tokens = _tokenize_query(query)
    # On limite les candidats aux chunks recents pour garder la recherche previsible
    # sans installer de base vectorielle pour ce deploiement portfolio.
    chunks = (
        db.query(DocumentChunks)
        .filter(DocumentChunks.user_id == user_id)
        .order_by(DocumentChunks.created_at.desc())
        .limit(200)
        .all()
    )

    scored_chunks = []
    for chunk in chunks:
        content_lower = chunk.content.lower()
        score = sum(1 for token in query_tokens if token in content_lower)

        if score > 0:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)

    return [
        {
            "content": chunk.content,
            "metadata": {
                "filename": chunk.filename,
                "page": chunk.page,
                "user_id": chunk.user_id,
            },
        }
        for _, chunk in scored_chunks[:limit]
    ]


def build_prompt(query: str, context: str) -> str:
    """Cree l'instruction finale envoyee au modele de generation."""
    return f"""
Tu es un assistant RAG professionnel de niveau startup, spécialisé dans l’analyse de documents, la recherche d’information dans une base documentaire privée et la génération de réponses fiables, claires et utiles.

Ta mission est de répondre à l’utilisateur uniquement à partir des informations présentes dans les documents fournis dans le contexte.

RÈGLES PRINCIPALES

1. Fidélité aux documents

* Utilise uniquement les informations présentes dans le contexte documentaire.
* N’invente jamais une information absente des documents.
* Ne complète pas avec ta connaissance générale, même si tu connais la réponse.
* Si l’information demandée n’est pas présente dans les documents, réponds clairement :
  "Je ne sais pas. Cette information n’est pas présente dans les documents fournis."

2. Gestion de l’incertitude

* Si les documents contiennent une information partielle, explique ce qui est disponible et ce qui manque.
* Si plusieurs documents semblent se contredire, signale la contradiction et cite les sources concernées.
* Ne donne jamais une réponse catégorique quand les documents ne permettent pas de l’affirmer.

3. Qualité de réponse attendue

* Réponds dans la même langue que l’utilisateur.
* Structure la réponse comme un assistant professionnel moderne.
* Évite les gros paragraphes compacts.
* Utilise des titres courts et clairs quand cela aide la lecture.
* Utilise des listes numérotées pour les étapes, comparaisons, classements ou suites logiques.
* Utilise des puces pour les caractéristiques, détails, avantages, limites ou points importants.
* Ajoute des sauts de ligne entre les sections.
* Sois clair, précis, direct et utile.
* Adapte le niveau de détail à la question de l’utilisateur.

4. Format recommandé
   Quand la question demande une explication, utilise si utile cette structure :

Résumé court

Réponse détaillée

Points importants

Limites ou informations manquantes

Sources utilisées

Tu n’es pas obligé d’utiliser toutes ces sections à chaque fois. Choisis la structure la plus naturelle selon la question.

5. Citations et sources

* Quand tu utilises une information issue des documents, cite toujours la source disponible.
* Utilise le nom du fichier et la page si disponibles.
* Format recommandé :
  Source : nom_du_fichier, page X
* Si plusieurs sources sont utilisées, liste-les à la fin dans une section "Sources utilisées".
* Ne cite jamais une source qui n’existe pas dans le contexte.
* Ne termine jamais une citation de manière incomplète.

6. Réponses longues

* Si la réponse est longue, organise-la en sections.
* Termine toujours proprement la réponse.
* Ne coupe pas une phrase en plein milieu.
* Ajoute une courte conclusion quand cela aide la compréhension.

7. Tableaux

* N’utilise pas de tableau par défaut.
* Utilise un tableau uniquement si cela rend la comparaison beaucoup plus claire.
* Si le support d’affichage ne gère pas bien les tableaux, préfère des listes structurées.

8. Questions hors documents
   Si l’utilisateur pose une question qui ne peut pas être répondue avec les documents :

* Ne fais pas de recherche externe.
* Ne réponds pas avec ta connaissance générale.
* Dis simplement que l’information n’est pas présente dans les documents.
* Propose à l’utilisateur d’uploader un document contenant cette information si nécessaire.

9. Style

* Ton ton doit être professionnel, naturel et rassurant.
* Tu dois être utile sans être verbeux inutilement.
* Tu dois ressembler à un assistant IA premium intégré dans une application SaaS moderne.
* Tu dois produire une réponse prête à être lue par un utilisateur final.

CONTEXTE DOCUMENTAIRE

{context}

QUESTION UTILISATEUR

{query}

RÉPONSE ATTENDUE

Réponds maintenant à la question de l’utilisateur en respectant strictement toutes les règles ci-dessus.

""".strip()


def _extract_openai_text(response) -> str | None:
    """Extrait le texte genere depuis la reponse OpenAI Responses API."""
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    return None


def build_rag_prompt(db: Session, query: str, user_id: int) -> str | None:
    """Prepare le prompt RAG sans lancer la generation."""
    docs = retrieve_documents(db=db, query=query, user_id=user_id)
    if not docs:
        return None

    context = format_retrieved_documents(docs)[:MAX_CONTEXT_CHARS]
    return build_prompt(query=query, context=context)


@traceable(name="call_openai")
def call_openai(prompt: str) -> str:
    """Appelle OpenAI pour generer la reponse finale du pipeline RAG."""
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not configured")
        return OPENAI_UNAVAILABLE_MESSAGE

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=OPENAI_TIMEOUT_SECONDS,
    )

    try:
        response = client.responses.create(
            model=settings.openai_model,
            instructions=OPENAI_SYSTEM_INSTRUCTIONS,
            input=prompt,
            max_output_tokens=settings.openai_max_output_tokens,
            temperature=0.2,
            store=False,
        )
    except OpenAIError:
        logger.exception("OpenAI generation failed")
        return OPENAI_UNAVAILABLE_MESSAGE
    except Exception:
        logger.exception("Unexpected OpenAI generation failure")
        return OPENAI_UNAVAILABLE_MESSAGE

    generated_text = _extract_openai_text(response)
    if generated_text:
        return generated_text

    logger.warning("Unexpected OpenAI response format: %s", response)
    return "Je ne sais pas."


@traceable(name="stream_openai_answer")
def stream_openai_answer(prompt: str) -> Iterator[str]:
    """Streame la reponse OpenAI token par token pour FastAPI."""
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not configured")
        yield OPENAI_UNAVAILABLE_MESSAGE
        return

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=OPENAI_TIMEOUT_SECONDS,
    )

    stream = None
    try:
        stream = client.responses.create(
            model=settings.openai_model,
            instructions=OPENAI_SYSTEM_INSTRUCTIONS,
            input=prompt,
            max_output_tokens=settings.openai_max_output_tokens,
            temperature=0.2,
            store=False,
            stream=True,
        )

        for event in stream:
            event_type = getattr(event, "type", "")

            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    yield delta
                continue

            if event_type == "error":
                logger.error(
                    "OpenAI streaming error: code=%s message=%s",
                    getattr(event, "code", None),
                    getattr(event, "message", None),
                )
                yield OPENAI_UNAVAILABLE_MESSAGE
                return
    except OpenAIError:
        logger.exception("OpenAI streaming failed")
        yield OPENAI_UNAVAILABLE_MESSAGE
    except Exception:
        logger.exception("Unexpected OpenAI streaming failure")
        yield OPENAI_UNAVAILABLE_MESSAGE
    finally:
        close_stream = getattr(stream, "close", None)
        if callable(close_stream):
            close_stream()


@traceable(name="run_rag")
def run_rag(db: Session, query: str, user_id: int) -> str:
    """Pipeline RAG complet: recherche, prompt, generation de reponse."""
    prompt = build_rag_prompt(db=db, query=query, user_id=user_id)
    if prompt is None:
        return NO_RELEVANT_DOCUMENT_MESSAGE

    return call_openai(prompt)
