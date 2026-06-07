from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette import status

from database import db_dependency
from tablebase import RateLimitEvent


class DatabaseRateLimiter:
    """Rate limiter persistant en base pour proteger l'API portfolio.

    Ce choix reste simple, compatible SQLite/PostgreSQL et plus credible
    qu'un compteur uniquement en memoire pour un projet destine a Railway.
    """

    def __init__(self, max_requests: int, window_seconds: int, scope: str):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope

    def check(self, db: Session, key: str) -> None:
        """Enregistre une requete et refuse si la limite est atteinte."""
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=self.window_seconds)

        db.query(RateLimitEvent).filter(
            RateLimitEvent.scope == self.scope,
            RateLimitEvent.client_key == key,
            RateLimitEvent.created_at < window_start,
        ).delete(synchronize_session=False)

        current_count = (
            db.query(func.count(RateLimitEvent.id))
            .filter(RateLimitEvent.scope == self.scope)
            .filter(RateLimitEvent.client_key == key)
            .filter(RateLimitEvent.created_at >= window_start)
            .scalar()
        )

        if current_count is not None and current_count >= self.max_requests:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de requetes. Reessayez plus tard.",
            )

        db.add(
            RateLimitEvent(
                scope=self.scope,
                client_key=key,
                created_at=now,
            )
        )
        db.commit()


# Les limites sont separees: auth est plus strict que le chat.
auth_limiter = DatabaseRateLimiter(max_requests=10, window_seconds=60, scope="auth")
chat_limiter = DatabaseRateLimiter(max_requests=20, window_seconds=60, scope="chat")
upload_limiter = DatabaseRateLimiter(max_requests=5, window_seconds=60, scope="upload")


def _client_key(request: Request) -> str:
    """Utilise l'adresse IP cliente comme cle de rate limit."""
    if request.client:
        return request.client.host

    return "unknown"


def auth_rate_limit(db: db_dependency, request: Request) -> None:
    """Dependance FastAPI pour les endpoints d'authentification."""
    auth_limiter.check(db, _client_key(request))


def chat_rate_limit(db: db_dependency, request: Request) -> None:
    """Dependance FastAPI pour l'endpoint de chat."""
    chat_limiter.check(db, _client_key(request))


def upload_rate_limit(db: db_dependency, request: Request) -> None:
    """Dependance FastAPI pour l'upload PDF."""
    upload_limiter.check(db, _client_key(request))
