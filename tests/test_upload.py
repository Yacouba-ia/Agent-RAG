from fastapi.testclient import TestClient


def test_upload_rejects_non_pdf_file(client: TestClient):
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

    response = client.post(
        "/upload/upload_document",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "pdfs": (
                "notes.txt",
                b"not a pdf",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Seuls les fichiers PDF sont acceptes"


def test_upload_rejects_path_traversal_filename(client: TestClient):
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

    response = client.post(
        "/upload/upload_document",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "pdfs": (
                "../notes.pdf",
                b"%PDF-1.4 fake content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Le nom du fichier est invalide"
