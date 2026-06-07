import logging
import re
from time import sleep

import requests
from langsmith import traceable
from sqlalchemy.orm import Session

from config import settings
from tablebase import DocumentChunks

logger = logging.getLogger(__name__)

# L'inference Hugging Face distante garde l'image Docker legere:
# pas de torch, transformers, sentence-transformers ou base vectorielle locale.
HF_MODEL_ID = "Qwen/Qwen3-32B"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"
MAX_CONTEXT_CHARS = 12000
HF_MAX_ATTEMPTS = 3
HF_RETRY_DELAY_SECONDS = 2
HF_TIMEOUT_SECONDS = 120
HF_UNAVAILABLE_MESSAGE = (
    "Je ne peux pas generer de reponse pour le moment. "
    "Le modele Hugging Face est temporairement indisponible."
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
    """Cree l'instruction finale envoyee a Hugging Face."""
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


def _extract_generated_text(data) -> str | None:
    """Extrait le texte genere a partir des formats de reponse Hugging Face connus."""
    if isinstance(data, list) and data:
        generated_text = data[0].get("generated_text")
        if generated_text:
            return generated_text.strip()

    if isinstance(data, dict):
        generated_text = data.get("generated_text")
        if generated_text:
            return generated_text.strip()

    return None


def _is_transient_hf_error(data) -> bool:
    """Repere les erreurs temporaires qui meritent un nouvel essai."""
    if not isinstance(data, dict):
        return False

    error_message = str(data.get("error", "")).lower()
    if not error_message:
        return False

    transient_markers = (
        "loading",
        "currently loading",
        "model is loading",
        "timeout",
        "temporarily unavailable",
        "busy",
    )
    return any(marker in error_message for marker in transient_markers)


@traceable(name="call_huggingface")
def call_huggingface(prompt: str) -> str:
    """Appelle l'API Hugging Face avec retries simples et normalisation de la reponse."""
    headers = {"Authorization": f"Bearer {settings.HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "options": {
            "wait_for_model": True,
        },
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.2,
            "return_full_text": False,
        },
    }

    for attempt in range(1, HF_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                HF_API_URL,
                headers=headers,
                json=payload,
                timeout=HF_TIMEOUT_SECONDS,
            )
            data = response.json()

            if response.status_code >= 500:
                raise requests.HTTPError(
                    f"Erreur temporaire Hugging Face: {response.status_code}",
                    response=response,
                )

            if response.status_code == 429 or _is_transient_hf_error(data):
                raise requests.HTTPError(
                    f"Hugging Face indisponible temporairement: {response.status_code}",
                    response=response,
                )

            response.raise_for_status()

            generated_text = _extract_generated_text(data)
            if generated_text:
                return generated_text

            logger.warning("Unexpected Hugging Face response format: %s", data)
            return "Je ne sais pas."
        except (requests.RequestException, ValueError) as exc:
            if attempt < HF_MAX_ATTEMPTS:
                logger.warning(
                    "Hugging Face attempt %s/%s failed, retrying: %s",
                    attempt,
                    HF_MAX_ATTEMPTS,
                    exc,
                )
                sleep(HF_RETRY_DELAY_SECONDS)
                continue

            logger.exception("Hugging Face request failed after retries")
            return HF_UNAVAILABLE_MESSAGE

    return HF_UNAVAILABLE_MESSAGE


@traceable(name="run_rag")
def run_rag(db: Session, query: str, user_id: int) -> str:
    """Pipeline RAG complet: recherche, prompt, generation de reponse."""
    docs = retrieve_documents(db=db, query=query, user_id=user_id)
    if not docs:
        return (
            "Je ne sais pas. Aucun document pertinent n'a ete trouve "
            "dans votre base documentaire."
        )

    context = format_retrieved_documents(docs)[:MAX_CONTEXT_CHARS]
    prompt = build_prompt(query=query, context=context)
    return call_huggingface(prompt)
