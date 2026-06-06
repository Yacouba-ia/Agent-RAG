from fastapi.testclient import TestClient


def test_register_creates_user(client: TestClient):
    response = client.post(
        "/auth/register",
        json={
            "username": "yacouba",
            "email": "yacouba@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    assert response.json() == {"message": "Utilisateur cree avec succes"}


def test_login_returns_access_token(client: TestClient):
    client.post(
        "/auth/register",
        json={
            "username": "yacouba",
            "email": "yacouba@example.com",
            "password": "password123",
        },
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "yacouba",
            "password": "password123",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
