import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from config import settings
from database import db_dependency
from routers import auth_router, chat_router, upload_router, user_router

app = FastAPI()
logger = logging.getLogger(__name__)

# CORS est active seulement si ALLOWED_ORIGINS est configure.
# Cela garde l'API fermee par defaut en usage local ou backend seul.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if settings.trust_proxy_headers:
    # Quand le projet est derriere un proxy, on recupere la vraie IP cliente.
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    """Journalise chaque requete HTTP avec sa route, son statut et sa duree."""
    start_time = perf_counter()
    response = None

    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (perf_counter() - start_time) * 1000
        status_code = response.status_code if response else 500
        logger.info(
            "HTTP %s %s -> %s en %.2f ms",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )


@app.get("/health")
async def health_check():
    """Endpoint de sante utilise par Docker, Railway et les checks externes."""
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check(db: db_dependency):
    """Verifie que l'API et PostgreSQL sont pret a servir du trafic."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception:
        logger.exception("Readiness check failed")
        return Response(
            content='{"status":"not ready","database":"error"}',
            media_type="application/json",
            status_code=503,
        )


# Les routers sont separes par domaine pour garder main.py simple.
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(user_router.router)
app.include_router(upload_router.router)
