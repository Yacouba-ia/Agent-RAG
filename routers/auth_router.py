import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette import status

from classes import TokenValidation, UserValidation
from config import settings
from database import db_dependency
from rate_limit import auth_rate_limit
from tablebase import Users

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/login")

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_user_by_username(username: str, db: Session):
    return db.query(Users).filter(Users.username == username).first()


def authenticate_user(username: str, password: str, db: Session):
    user_authenticated = get_user_by_username(username, db)
    if not user_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides"
        )
    if not bcrypt_context.verify(password, user_authenticated.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )

    return user_authenticated


def create_token(username: str, user_id: int, expires_date: timedelta):
    encoded_data = {"username": username, "id": user_id}
    expiration = datetime.now(UTC) + expires_date
    encoded_data.update({"exp": expiration})
    return jwt.encode(encoded_data, settings.jwt_secret_key, algorithm=settings.jwt_algo)


def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algo])
        username: str = payload.get("username")
        user_id: int = payload.get("id")

        if user_id is None or username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
                headers={"WWW-Authenticate": "Bearer"}
            )

    except JWTError as exc:
        logger.warning("Invalid JWT token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erreur d'authentification",
            headers={"WWW-Authenticate": "Bearer"}
        ) from exc

    return {"id": user_id, "username": username}

user_dependency = Annotated[dict, Depends(get_current_user)]

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
)
async def register(db:db_dependency,  user_body: UserValidation = Body()):
    existing_email = db.query(Users).filter(Users.email == user_body.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email deja utilise"
        )

    existing_username = get_user_by_username(user_body.username, db)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom d'utilisateur deja utilise"
        )

    new_user = Users(
        username=user_body.username,
        email=user_body.email,
        hashed_password=bcrypt_context.hash(user_body.password),
        is_active=True
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("User registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la creation de l'utilisateur",
        ) from exc

    return {"message": "Utilisateur cree avec succes"}


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=TokenValidation,
    dependencies=[Depends(auth_rate_limit)],
)
async def login(db:db_dependency, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    authenticated_user = authenticate_user(form_data.username, form_data.password, db)
    if not authenticated_user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_token(authenticated_user.username, authenticated_user.id, timedelta(minutes=30))
    return {"access_token": token, "token_type": "bearer"}
