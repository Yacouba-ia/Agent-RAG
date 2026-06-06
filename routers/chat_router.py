import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from classes import ChatRequest
from database import db_dependency
from rag import run_rag
from rate_limit import chat_rate_limit
from routers.auth_router import user_dependency
from tablebase import ChatMessages, ChatSessions

router = APIRouter(
    prefix="/chat_ask",
    tags=["chat_ask"]
)

logger = logging.getLogger(__name__)


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
        answer = run_rag(db=db, query=query, user_id=user_id)
    except Exception as exc:
        logger.exception("RAG generation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service RAG indisponible",
        ) from exc

    rag_chat = ChatMessages(
        session_id=session.id,
        role="assistant",
        content=answer.strip(),
    )
    try:
        db.add(rag_chat)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to save assistant chat message")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement de la reponse",
        ) from exc

    def generate():
        yield answer

    return StreamingResponse(generate(), media_type="text/plain")
