from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class Users(Base):
    """Utilisateurs inscrits dans l'application."""

    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class ChatSessions(Base):
    """Conversation appartenant a un utilisateur."""

    __tablename__ = "chat_sessions"
    # Un utilisateur ne doit pas avoir deux conversations avec le meme thread_id.
    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="uq_chat_sessions_user_thread"),
    )

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, nullable=False, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String, nullable=False, default="Nouvelle conversation")
    project_type = Column(String, nullable=False, default="Agent RAG")
    model_used = Column(String, nullable=False, default="Hugging Face")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    update_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChatMessages(Base):
    """Messages echanges dans une conversation."""

    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String, nullable=False, default="user")
    content = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class DocumentChunks(Base):
    """Morceaux de texte extraits des PDF pour la recherche documentaire."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = Column(String, nullable=False)
    page = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class RateLimitEvent(Base):
    """Evenements de rate limiting conserves en base pour une protection persistante."""

    __tablename__ = "rate_limit_events"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String, nullable=False, index=True)
    client_key = Column(String, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
