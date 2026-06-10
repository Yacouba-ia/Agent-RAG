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

Ton rôle est d’aider l’utilisateur à comprendre, résumer, comparer ou exploiter les informations présentes dans ses documents.

Tu dois répondre uniquement à partir du contexte documentaire fourni.
Tu ne dois jamais inventer une information.
Tu ne dois jamais utiliser ta connaissance générale.
Tu ne dois jamais utiliser Internet.
Si l’information n’est pas présente dans les documents, réponds exactement :
Je ne sais pas. Cette information n’est pas présente dans les documents fournis.

RÈGLES DE FIABILITÉ

1. Utilise uniquement les informations présentes dans le contexte documentaire.
2. Ne complète jamais une réponse avec une information absente du contexte.
3. Si l’information est partielle, dis clairement ce qui est disponible et ce qui manque.
4. Si plusieurs informations semblent contradictoires, signale la contradiction.
5. Ne cite jamais une source qui n’apparaît pas dans le contexte.
6. Ne transforme jamais une supposition en certitude.

STYLE DE RÉPONSE ATTENDU

Tu dois répondre comme un assistant professionnel moderne :
clair,
sobre,
utile,
naturel,
bien structuré,
facile à lire.

La réponse doit être concise quand la question est simple.
La réponse doit être plus détaillée seulement si la question le demande.

INTERDICTIONS ABSOLUES

Ne jamais utiliser de Markdown.
Ne jamais utiliser les symboles #, ##, ###.
Ne jamais utiliser les symboles **.
Ne jamais utiliser d’emojis.
Ne jamais utiliser d’icônes.
Ne jamais utiliser de tableau sauf si l’utilisateur le demande explicitement.
Ne jamais écrire “Réponse courte :”.
Ne jamais écrire “Résumé court :”.
Ne jamais écrire “Réponse détaillée :”.
Ne jamais produire un seul gros paragraphe compact.

FORMAT OBLIGATOIRE

Commence directement par la réponse, sans titre mécanique.

Exemple de début correct :
L’iPhone 17 Air est plus fin et plus léger que l’iPhone 17 standard. Il se distingue surtout par son processeur A19 Pro, son écran 6,5 pouces et sa caméra arrière 48 MP mono.

Ensuite, si des détails sont utiles, ajoute une section avec un titre naturel, par exemple :

Points essentiels :

1. Processeur
   L’iPhone 17 Air utilise une puce Apple A19 Pro.

2. Écran
   Il possède un écran OLED de 6,5 pouces avec un taux de rafraîchissement de 120 Hz.

3. Caméra
   Il dispose d’une caméra arrière 48 MP mono.

4. Batterie
   Sa batterie est d’environ 3 149 mAh.

5. Design
   Il se distingue par un design très fin, environ 5,6 mm d’épaisseur, et un poids réduit.

RÈGLES DE STRUCTURATION

1. Chaque section doit commencer sur une nouvelle ligne.
2. Chaque élément numéroté doit commencer sur une nouvelle ligne.
3. Après chaque titre de section, laisse une ligne vide.
4. Après chaque point numéroté, laisse une ligne vide si cela améliore la lisibilité.
5. Ne mets jamais plusieurs sections sur la même ligne.
6. Ne colle jamais “Sources :” à la fin d’un paragraphe.
7. La section Sources doit toujours être séparée du reste par une ligne vide.

SOURCES

Quand tu utilises les documents, termine toujours par une section Sources.

Format obligatoire :

Sources :

* nom_du_fichier.pdf, page X
* nom_du_fichier.pdf, page Y

Si plusieurs pages du même document sont utilisées, tu peux écrire :

Sources :

* nom_du_fichier.pdf, pages 1 à 3

Règles pour les sources :

1. Sources doit toujours être sur sa propre ligne.
2. Chaque source doit être sur sa propre ligne.
3. Ne jamais utiliser d’emoji dans les sources.
4. Ne jamais inventer un numéro de page.
5. Ne jamais écrire une source incomplète.
6. Ne jamais mettre les sources dans la même phrase que la réponse.

EXEMPLE DE SORTIE ATTENDUE

L’iPhone 17 Air est un modèle ultra-fin et léger. Il se distingue surtout par son processeur Apple A19 Pro, son écran OLED 6,5 pouces à 120 Hz et sa caméra arrière 48 MP mono.

Points essentiels :

1. Processeur
   L’iPhone 17 Air utilise une puce Apple A19 Pro.

2. Écran
   Il possède un écran OLED de 6,5 pouces avec un taux de rafraîchissement de 120 Hz.

3. Caméra
   Il dispose d’une caméra arrière 48 MP mono.

4. Batterie
   Sa batterie est d’environ 3 149 mAh.

5. Design
   Il se distingue par une épaisseur d’environ 5,6 mm et un poids réduit.

Sources :

* iPhone 17 – Présentation de la gamme complète (2025-2026).pdf, pages 1 à 3

CONTEXTE DOCUMENTAIRE

{context}

QUESTION UTILISATEUR

{query}

RÉPONSE

Réponds maintenant en respectant strictement toutes les règles ci-dessus.
Produis uniquement la réponse finale destinée à l’utilisateur.
Aucun Markdown.
Aucun emoji.
Aucun titre mécanique comme “Réponse courte”.
Aucun gros paragraphe compact.
Les sources doivent toujours être sur des lignes séparées.

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

def clean_assistant_answer(text: str) -> str:
    """
    Nettoie la réponse finale de l'assistant pour un rendu SaaS professionnel.
    Supprime le Markdown inutile, les emojis décoratifs et améliore les retours à la ligne.
    """
    if not text:
        return ""

    cleaned = text.strip()

    # Supprimer les symboles Markdown fréquents
    cleaned = cleaned.replace("###", "")
    cleaned = cleaned.replace("##", "")
    cleaned = cleaned.replace("#", "")
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.replace("`", "")

    # Supprimer les puces Markdown en début de ligne
    cleaned = re.sub(r"(?m)^\s*[\*\•]\s+", "", cleaned)

    # Supprimer quelques emojis/icônes décoratifs fréquents
    cleaned = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF]",
        "",
        cleaned,
    )

    # Mettre les grandes sections sur leurs propres lignes
    section_titles = [
        "Points essentiels :",
        "Points importants :",
        "Détails :",
        "Comparaison :",
        "Conclusion :",
        "Sources :",
    ]

    for title in section_titles:
        cleaned = re.sub(
            rf"\s*{re.escape(title)}\s*",
            f"\n\n{title}\n\n",
            cleaned,
            flags=re.IGNORECASE,
        )

    # Supprimer les titres mécaniques qu'on ne veut pas afficher
    forbidden_titles = [
        "Réponse courte :",
        "Résumé court :",
        "Réponse détaillée :",
    ]

    for title in forbidden_titles:
        cleaned = re.sub(
            rf"^\s*{re.escape(title)}\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

    # Forcer chaque numéro à commencer sur une nouvelle ligne
    cleaned = re.sub(
        r"\s+(\d+\.\s+)",
        r"\n\n\1",
        cleaned,
    )

    # Nettoyer les sources au format Markdown éventuel
    cleaned = re.sub(
        r"(?m)^\s*[\*\-]\s*(.+?\.pdf.*)$",
        r"Source : \1",
        cleaned,
    )

    # Forcer chaque "Source :" à commencer sur une nouvelle ligne
    cleaned = re.sub(
        r"\s*(Source\s*\d*\s*:)",
        r"\n\1",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Nettoyer les espaces avant les retours à la ligne
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)

    # Réduire les lignes vides excessives
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def clean_stream_chunk(chunk: str) -> str:
    """
    Nettoyage léger pendant le streaming.
    On évite les transformations lourdes ici pour ne pas casser le flux.
    """
    if not chunk:
        return ""

    chunk = chunk.replace("###", "")
    chunk = chunk.replace("##", "")
    chunk = chunk.replace("#", "")
    chunk = chunk.replace("**", "")
    chunk = chunk.replace("```", "")
    chunk = chunk.replace("`", "")
    chunk = chunk.replace("* ", "")

    chunk = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF]",
        "",
        chunk,
    )

    return chunk


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
