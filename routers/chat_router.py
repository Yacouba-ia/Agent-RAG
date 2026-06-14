import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from classes import ChatRequest
from database import db_dependency
from rag import (
    NO_RELEVANT_DOCUMENT_MESSAGE,
    OPENAI_UNAVAILABLE_MESSAGE,
    build_rag_prompt,
    clean_assistant_answer,
    clean_stream_chunk,
    stream_openai_answer,
)
from rate_limit import chat_rate_limit
from routers.auth_router import user_dependency
from tablebase import ChatMessages, ChatSessions

router = APIRouter(
    prefix="/chat_ask",
    tags=["chat_ask"]
)

logger = logging.getLogger(__name__)


def save_assistant_message(db, session_id: int, answer: str) -> None:
    """Sauvegarde la reponse complete apres la fin du streaming."""
    if not answer.strip():
        return

    rag_chat = ChatMessages(
        session_id=session_id,
        role="assistant",
        content=answer.strip(),
    )
    try:
        db.add(rag_chat)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to save streamed assistant chat message")


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(chat_rate_limit)],
)
async def chat_ask(
        db: db_dependency,
        user: user_dependency,
        data: ChatRequest
):
    """Enregistre la question, lance le RAG, sauvegarde la reponse et la renvoie en streaming."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non authentifie"
        )

    thread_id = data.thread_id
    query = data.query
    user_id = user.get("id")

    session = (
        db.query(ChatSessions)
        .filter(ChatSessions.thread_id == thread_id)
        .filter(ChatSessions.user_id == user_id)
        .first()
    )

    if not session:
        # La premiere question d'un fil cree la ligne de conversation.
        session = ChatSessions(
            thread_id=thread_id,
            user_id=user_id,
            title=query[:30] + "...."
        )
        try:
            db.add(session)
            db.commit()
            db.refresh(session)
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to create chat session")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la creation de la conversation",
            ) from exc

    user_chat = ChatMessages(
        session_id=session.id,
        role="user",
        content=query
    )
    try:
        # On enregistre le message utilisateur avant la generation pour garder l'historique complet.
        db.add(user_chat)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to save user chat message")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement du message",
        ) from exc

    try:
        prompt = build_rag_prompt(db=db, query=query, user_id=user_id)
    except Exception as exc:
        logger.exception("RAG prompt preparation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service RAG indisponible",
        ) from exc

    session_id = session.id

    def generate():
        chunks = []

        try:
            if prompt is None:
                clean_message = clean_assistant_answer(NO_RELEVANT_DOCUMENT_MESSAGE)
                chunks.append(clean_message)
                yield clean_message
                return

            for chunk in stream_openai_answer(prompt):
                clean_chunk = clean_stream_chunk(chunk)

                if clean_chunk:
                    chunks.append(clean_chunk)
                    yield clean_chunk

        except Exception:
            logger.exception("Unexpected RAG streaming failure")
            clean_error = clean_assistant_answer(OPENAI_UNAVAILABLE_MESSAGE)
            chunks.append(clean_error)
            yield clean_error

        finally:
            final_answer = clean_assistant_answer("".join(chunks))

            save_assistant_message(
                db=db,
                session_id=session_id,
                answer=final_answer,
            )

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")