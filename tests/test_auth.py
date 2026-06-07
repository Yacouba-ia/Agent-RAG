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


def test_auth_rate_limit_blocks_after_limit(client: TestClient):
    # On envoie 11 inscriptions pour verifier le blocage au niveau de la 11e requete.
    for index in range(10):
        response = client.post(
            "/auth/register",
            json={
                "username": f"yacouba{index}",
                "email": f"yacouba{index}@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 201

    response = client.post(
        "/auth/register",
        json={
            "username": "yacouba10",
            "email": "yacouba10@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Trop de requetes. Reessayez plus tard."
