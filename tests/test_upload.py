from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tablebase import DocumentChunks


def authenticate(client: TestClient) -> str:
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


def test_upload_rejects_non_pdf_file(client: TestClient):
    token = authenticate(client)

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
    token = authenticate(client)

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


def test_list_documents_groups_user_chunks(client: TestClient, db_session: Session):
    token = authenticate(client)
    db_session.add_all(
        [
            DocumentChunks(user_id=1, filename="handbook.pdf", page=0, content="Intro"),
            DocumentChunks(user_id=1, filename="handbook.pdf", page=1, content="Policy"),
            DocumentChunks(user_id=1, filename="strategy.pdf", page=0, content="Roadmap"),
        ]
    )
    db_session.commit()

    response = client.get(
        "/upload/documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert {document["name"] for document in body} == {"handbook.pdf", "strategy.pdf"}
    handbook = next(document for document in body if document["name"] == "handbook.pdf")
    assert handbook["chunk_count"] == 2
    assert handbook["status"] == "ready"


def test_delete_document_removes_only_current_user_chunks(
    client: TestClient,
    db_session: Session,
):
    token = authenticate(client)
    db_session.add_all(
        [
            DocumentChunks(user_id=1, filename="handbook.pdf", page=0, content="Intro"),
            DocumentChunks(user_id=1, filename="handbook.pdf", page=1, content="Policy"),
            DocumentChunks(user_id=2, filename="handbook.pdf", page=0, content="Other user"),
        ]
    )
    db_session.commit()

    response = client.delete(
        "/upload/documents/handbook.pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    remaining = db_session.query(DocumentChunks).all()
    assert len(remaining) == 1
    assert remaining[0].user_id == 2
