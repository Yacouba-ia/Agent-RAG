from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth_router, chat_router, upload_router, user_router

app = FastAPI()

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(user_router.router)
app.include_router(upload_router.router)
