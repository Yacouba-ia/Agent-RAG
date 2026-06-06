from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    HF_TOKEN: str

    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "rag-fastapi-huggingface-api"

    jwt_secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algo: str = Field(validation_alias="JWT_ALGO")
    allowed_origins: str = Field(default="", validation_alias="ALLOWED_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        if not self.allowed_origins:
            return []

        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
