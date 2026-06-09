from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CORS_ORIGINS = (
    "https://ai-knowledge-assistant-frontend-ashen.vercel.app",
)


class Settings(BaseSettings):
    """Configuration chargee depuis les variables d'environnement ou .env."""

    DATABASE_URL: str
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL")

    # LangSmith utilise les variables LANGCHAIN_* pour configurer le tracing.
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "rag-fastapi-openai-api"

    jwt_secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algo: str = Field(validation_alias="JWT_ALGO")
    allowed_origins: str = Field(default="", validation_alias="ALLOWED_ORIGINS")
    trust_proxy_headers: bool = Field(default=False, validation_alias="TRUST_PROXY_HEADERS")

    @property
    def cors_origins(self) -> list[str]:
        """Convertit ALLOWED_ORIGINS en liste d'origines CORS propres."""
        configured_origins = [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]

        # L'origine Vercel publique est autorisee par defaut pour eviter un
        # deploiement Railway sans header CORS quand ALLOWED_ORIGINS est absent.
        return list(dict.fromkeys([*configured_origins, *DEFAULT_CORS_ORIGINS]))

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


# Ce singleton donne la meme configuration validee a tous les modules.
settings = Settings()
