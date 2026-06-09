from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rag import NO_RELEVANT_DOCUMENT_MESSAGE
from routers import chat_router
from tablebase import ChatMessages


def _login_test_user(client: TestClient) -> str:
    client.post(
        "/auth/register",
        json={
            "username": "yacouba",
            "email": "yacouba@example.com",
            "password": "password123",
        },
    )
    login_response = client.post(
        "/auth/login",
        data={
            "username": "yacouba",
            "password": "password123",
        },
    )
    return login_response.json()["access_token"]


def test_chat_ask_streams_and_saves_full_assistant_response(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    token = _login_test_user(client)

    monkeypatch.setattr(
        chat_router,
        "build_rag_prompt",
        lambda db, query, user_id: "Prompt RAG de test",
    )
    monkeypatch.setattr(
        chat_router,
        "stream_openai_answer",
        lambda prompt: iter(["Reponse ", "RAG ", "streamee"]),
    )

    response = client.post(
        "/chat_ask/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "thread_id": 1,
            "query": "Quelle est la reponse ?",
        },
    )

    assistant_message = (
        db_session.query(ChatMessages)
        .filter(ChatMessages.role == "assistant")
        .one()
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "Reponse RAG streamee"
    assert assistant_message.content == "Reponse RAG streamee"


def test_chat_ask_streams_and_saves_no_relevant_document_message(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    token = _login_test_user(client)

    monkeypatch.setattr(
        chat_router,
        "build_rag_prompt",
        lambda db, query, user_id: None,
    )

    response = client.post(
        "/chat_ask/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "thread_id": 1,
            "query": "Quelle est la reponse ?",
        },
    )

    assistant_message = (
        db_session.query(ChatMessages)
        .filter(ChatMessages.role == "assistant")
        .one()
    )

    assert response.status_code == 200
    assert response.text == NO_RELEVANT_DOCUMENT_MESSAGE
    assert assistant_message.content == NO_RELEVANT_DOCUMENT_MESSAGE
