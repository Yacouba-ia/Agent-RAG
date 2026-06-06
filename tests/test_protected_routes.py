from fastapi.testclient import TestClient


def test_conversation_requires_authentication(client: TestClient):
    response = client.get("/user/conversation")

    assert response.status_code == 401
