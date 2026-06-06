import logging

from fastapi import APIRouter, Body, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from classes import Conversation, PasswordValidation
from database import db_dependency
from routers.auth_router import bcrypt_context, user_dependency
from tablebase import ChatMessages, ChatSessions, Users

router = APIRouter(
    prefix="/user",
    tags=["user"]
)

logger = logging.getLogger(__name__)


@router.put("/update_password", status_code=status.HTTP_202_ACCEPTED)
async def update_password(
        user: user_dependency,
        db: db_dependency,
        form_data: PasswordValidation = Body()
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non authentifie"
        )

    user_update = db.query(Users).filter(Users.id == user.get("id")).first()

    if not user_update:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non authentifie"
        )

    if not bcrypt_context.verify(form_data.old_password, user_update.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ancien mot de passe incorrect"
        )

    try:
        user_update.hashed_password = bcrypt_context.hash(form_data.new_password)
        db.add(user_update)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to update user password")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise a jour du mot de passe",
        ) from exc

    return {"message": "Mot de passe mis a jour avec succes"}


@router.get(
    "/conversation",
    status_code=status.HTTP_200_OK,
    response_model=list[Conversation]
)
async def get_conversation(
        db: db_dependency,
        user: user_dependency,
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=10, ge=1, le=100)
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated"
        )

    result = (
        db.query(ChatSessions)
        .filter(ChatSessions.user_id == user.get("id"))
        .offset(skip)
        .limit(limit)
        .all()
    )

    return result


@router.get("/messages/{session_id}", status_code=status.HTTP_200_OK)
async def get_messages(
        db: db_dependency,
        user: user_dependency,
        session_id: int = Path(),
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=10, ge=1, le=100)
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated"
        )

    session = (
        db.query(ChatSessions)
        .filter(ChatSessions.id == session_id)
        .filter(ChatSessions.user_id == user.get("id"))
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    result = (
        db.query(ChatMessages)
        .filter(ChatMessages.session_id == session_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return result


@router.delete("/messages/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_messages(
        db: db_dependency,
        user: user_dependency,
        session_id: int = Path(...)
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated"
        )

    session = (
        db.query(ChatSessions)
        .filter(ChatSessions.id == session_id)
        .filter(ChatSessions.user_id == user.get("id"))
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    (
        db.query(ChatMessages)
        .filter(ChatMessages.session_id == session_id)
        .delete()
    )

    try:
        db.delete(session)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to delete chat session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression de la conversation",
        ) from exc
