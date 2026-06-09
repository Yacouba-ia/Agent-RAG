from fastapi.testclient import TestClient

from config import DEFAULT_CORS_ORIGINS, Settings

VERCEL_ORIGIN = "https://ai-knowledge-assistant-frontend-ashen.vercel.app"


def test_cors_origins_parse_env_and_strip_spaces():
    settings = Settings(
        DATABASE_URL="sqlite:///./test.db",
        OPENAI_API_KEY="test-openai-key",
        JWT_SECRET_KEY="test-secret-key",
        JWT_ALGO="HS256",
        ALLOWED_ORIGINS=" http://localhost:5173 , https://example.com ",
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://example.com",
        *DEFAULT_CORS_ORIGINS,
    ]


def test_cors_origins_include_vercel_origin_by_default():
    settings = Settings(
        DATABASE_URL="sqlite:///./test.db",
        OPENAI_API_KEY="test-openai-key",
        JWT_SECRET_KEY="test-secret-key",
        JWT_ALGO="HS256",
    )

    assert VERCEL_ORIGIN in settings.cors_origins


def test_preflight_allows_deployed_vercel_frontend(client: TestClient):
    response = client.options(
        "/auth/register",
        headers={
            "Origin": VERCEL_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == VERCEL_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
