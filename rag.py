import logging
import re

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
Tu es un assistant RAG intelligent.

Tu reponds uniquement a partir des informations retrouvees dans la base documentaire.
Si l'information n'existe pas dans les documents, dis simplement que tu ne sais pas.
Reponds dans la langue utilisee par l'utilisateur.
Quand une reponse utilise des documents, cite les sources disponibles avec le nom du fichier
et la page.
Pas de markdown.
Pas de tableaux.

Documents:
{context}

Question:
{query}

Reponse:
""".strip()


def _extract_openai_text(response) -> str | None:
    """Extrait le texte genere depuis la reponse OpenAI Responses API."""
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    return None


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
            max_output_tokens=700,
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


@traceable(name="run_rag")
def run_rag(db: Session, query: str, user_id: int) -> str:
    """Pipeline RAG complet: recherche, prompt, generation de reponse."""
    docs = retrieve_documents(db=db, query=query, user_id=user_id)
    if not docs:
        return NO_RELEVANT_DOCUMENT_MESSAGE

    context = format_retrieved_documents(docs)[:MAX_CONTEXT_CHARS]
    prompt = build_prompt(query=query, context=context)
    return call_openai(prompt)
