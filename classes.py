from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserValidation(BaseModel):
    username: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)

class SessionValidation(BaseModel):
    thread_id: int
    user_id: int
    title: str

class MessageValidation(BaseModel):
    session_id: int
    role: str
    content: str

class TokenValidation(BaseModel):
    access_token: str
    token_type: str

class PasswordValidation(BaseModel):
    old_password: str
    new_password: str

class ChatRequest(BaseModel):

    thread_id: int
    query: str

class Conversation(BaseModel):
    id: int
    thread_id: int
    title: str
    project_type: str
    model_used: str
    created_at: datetime
    update_at: datetime
