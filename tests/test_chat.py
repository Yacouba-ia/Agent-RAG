from fastapi.testclient import TestClient

from routers import chat_router


def test_chat_ask_streams_mocked_rag_response(client: TestClient, monkeypatch):
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
    token = login_response.json()["access_token"]

    monkeypatch.setattr(chat_router, "run_rag", lambda db, query, user_id: "Reponse RAG de test")

    response = client.post(
        "/chat_ask/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "thread_id": 1,
            "query": "Quelle est la reponse ?",
        },
    )

    assert response.status_code == 200
    assert response.text == "Reponse RAG de test"
