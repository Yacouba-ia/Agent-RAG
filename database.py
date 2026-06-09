from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings


def normalize_database_url(database_url: str) -> str:
    """Force SQLAlchemy a utiliser psycopg3 avec les URLs PostgreSQL Railway."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


DATABASE_URL = normalize_database_url(settings.DATABASE_URL)

# pool_pre_ping evite les connexions mortes apres un redemarrage conteneur
# ou une connexion PostgreSQL restee inactive.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base est utilisee par les modeles SQLAlchemy et Alembic.
Base = declarative_base()


def get_db():
    """Dependance FastAPI qui ouvre une session DB par requete."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Alias reutilisable pour injecter la session DB dans les routes.
db_dependency = Annotated[Session, Depends(get_db)]
