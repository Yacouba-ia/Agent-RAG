import logging
import re

import requests
from sqlalchemy.orm import Session

from config import settings
from tablebase import DocumentChunks

logger = logging.getLogger(__name__)

HF_MODEL_ID = "Qwen/Qwen3-32B"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"
MAX_CONTEXT_CHARS = 12000


def get_user_collection_name(user_id: int) -> str:
    return f"user_{user_id}"


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
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
    filename = metadata.get("filename") or "document inconnu"
    page = metadata.get("page")

    if page is None:
        return filename

    return f"{filename}, page {int(page) + 1}"


def format_retrieved_documents(docs) -> str:
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
    return {
        token
        for token in re.findall(r"\w+", query.lower())
        if len(token) >= 3
    }


def retrieve_documents(db: Session, query: str, user_id: int, limit: int = 5) -> list[dict]:
    query_tokens = _tokenize_query(query)
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


def call_huggingface(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {settings.HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.2,
            "return_full_text": False,
        },
    }

    response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, list) and data:
        generated_text = data[0].get("generated_text")
        if generated_text:
            return generated_text.strip()

    if isinstance(data, dict):
        generated_text = data.get("generated_text")
        if generated_text:
            return generated_text.strip()

    logger.warning("Unexpected Hugging Face response format: %s", data)
    return "Je ne sais pas."


def run_rag(db: Session, query: str, user_id: int) -> str:
    docs = retrieve_documents(db=db, query=query, user_id=user_id)
    if not docs:
        return (
            "Je ne sais pas. Aucun document pertinent n'a ete trouve "
            "dans votre base documentaire."
        )

    context = format_retrieved_documents(docs)[:MAX_CONTEXT_CHARS]
    prompt = build_prompt(query=query, context=context)
    return call_huggingface(prompt)
