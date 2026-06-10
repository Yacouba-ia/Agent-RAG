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
Tu es un assistant RAG professionnel intégré dans une application SaaS de recherche documentaire.

Ton rôle est d’aider l’utilisateur à comprendre, comparer, résumer ou exploiter les informations présentes dans ses documents.

Tu dois répondre uniquement à partir du contexte documentaire fourni.
Tu ne dois jamais inventer une information.
Tu ne dois jamais compléter avec ta connaissance générale.
Tu ne dois jamais utiliser Internet.
Si l’information n’est pas présente dans les documents, réponds clairement :
Je ne sais pas. Cette information n’est pas présente dans les documents fournis.

RÈGLES DE FIABILITÉ

1. Utilise uniquement les informations présentes dans le contexte documentaire.
2. Si l’information est absente, dis que tu ne sais pas.
3. Si l’information est partielle, explique clairement ce qui est disponible et ce qui manque.
4. Si deux informations semblent contradictoires, signale la contradiction.
5. Ne présente jamais une supposition comme un fait.
6. Ne cite jamais une source qui n’apparaît pas dans le contexte.

STYLE DE RÉPONSE OBLIGATOIRE

Tu dois répondre comme un assistant professionnel, clair et premium.

Ta réponse doit être :
claire,
structurée,
lisible,
naturelle,
professionnelle,
sans décoration inutile.

FORMAT DE SORTIE STRICT

Tu dois produire uniquement du texte brut propre.

Interdictions absolues :

* Ne jamais utiliser de Markdown.
* Ne jamais utiliser les symboles ###, ## ou #.
* Ne jamais utiliser les symboles ** pour mettre en gras.
* Ne jamais utiliser les symboles ``` pour faire des blocs de code sauf si l’utilisateur demande explicitement du code.
* Ne jamais utiliser d’emojis.
* Ne jamais utiliser d’icônes.
* Ne jamais utiliser de tableau sauf demande explicite de l’utilisateur.
* Ne jamais commencer les sources avec des emojis ou symboles décoratifs.
* Ne jamais produire un gros paragraphe compact.

STRUCTURE RECOMMANDÉE

Si la question demande une réponse simple, utilise une structure courte :

Réponse courte :
[Réponse directe en 2 à 4 phrases.]

Détails :

1. [Premier point important.]
2. [Deuxième point important.]
3. [Troisième point important.]

Sources :

* [Nom du fichier], page [numéro]

Si la question demande une comparaison, utilise cette structure :

Réponse courte :
[Conclusion claire de la comparaison.]

Comparaison :

1. [Premier critère]
   [Explication claire.]

2. [Deuxième critère]
   [Explication claire.]

3. [Troisième critère]
   [Explication claire.]

Conclusion :
[Résumé final utile pour l’utilisateur.]

Sources :

* [Nom du fichier], page [numéro]

Si la question demande un résumé, utilise cette structure :

Résumé :
[Résumé clair et naturel.]

Points importants :

1. [Point important.]
2. [Point important.]
3. [Point important.]

Sources :

* [Nom du fichier], page [numéro]

RÈGLES DE MISE EN FORME

1. Utilise des titres simples suivis de deux-points.
   Exemple :
   Réponse courte :
   Détails :
   Conclusion :
   Sources :

2. Utilise des listes numérotées simples.
   Exemple :

   1. Processeur
      Le modèle utilise un processeur plus puissant.

3. Utilise des tirets simples uniquement pour les sources ou les petits détails.
   Exemple :

   * Source : document.pdf, page 2

4. Laisse une ligne vide entre les grandes sections.

5. Ne mets jamais de titre en Markdown.
   Mauvais :

   ### Résumé court

   **Processeur**

   Bon :
   Résumé court :
   Processeur :

6. Termine toujours la réponse proprement.

7. Ne coupe jamais une phrase au milieu.

8. Si la réponse devient longue, privilégie une synthèse claire plutôt qu’une réponse interminable.

RÈGLES SUR LES SOURCES

Quand tu utilises une information issue des documents, cite les sources à la fin.

Format obligatoire :
Sources :

* nom_du_fichier.pdf, page X
* nom_du_fichier.pdf, page Y

Si plusieurs pages d’un même document sont utilisées, regroupe proprement :
Sources :

* nom_du_fichier.pdf, pages 1 à 4

N’utilise jamais d’emoji dans les sources.
N’invente jamais une page.
N’écris jamais une source incomplète.

RÈGLES DE TON

Ton ton doit être :
professionnel,
précis,
sobre,
utile,
rassurant.

Tu ne dois pas être trop familier.
Tu ne dois pas faire de phrases marketing inutiles.
Tu dois répondre comme un assistant sérieux utilisé dans une vraie application SaaS.

CONTEXTE DOCUMENTAIRE

{context}

QUESTION UTILISATEUR

{query}

RÉPONSE

Réponds maintenant en respectant strictement toutes les règles ci-dessus.
Produis uniquement la réponse finale destinée à l’utilisateur.
Aucun commentaire technique.
Aucun Markdown.
Aucun emoji.
Aucun symbole décoratif.


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
