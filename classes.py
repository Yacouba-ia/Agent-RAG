from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserValidation(BaseModel):
    """Payload attendu pour creer un utilisateur."""

    username: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)


class SessionValidation(BaseModel):
    """Structure interne d'une session de chat."""

    thread_id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)


class MessageValidation(BaseModel):
    """Structure interne d'un message sauvegarde."""

    session_id: int = Field(ge=1)
    role: str = Field(min_length=1, max_length=20)
    content: str = Field(min_length=1, max_length=4000)


class TokenValidation(BaseModel):
    """Reponse retournee apres une connexion reussie."""

    access_token: str
    token_type: str


class PasswordValidation(BaseModel):
    """Payload utilise pour changer le mot de passe."""

    old_password: str = Field(min_length=8, max_length=64)
    new_password: str = Field(min_length=8, max_length=64)


class ChatRequest(BaseModel):
    """Payload envoye a l'endpoint de chat RAG."""

    thread_id: int = Field(ge=1)
    query: str = Field(min_length=1, max_length=4000)


class Conversation(BaseModel):
    """Modele de reponse public pour lister les conversations."""

    id: int = Field(ge=1)
    thread_id: int = Field(ge=1)
    title: str = Field(min_length=1)
    project_type: str = Field(min_length=1)
    model_used: str = Field(min_length=1)
    created_at: datetime
    update_at: datetime
