import requests

import rag
from rag import (
    call_huggingface,
    format_document_source,
    format_retrieved_documents,
    get_user_collection_name,
    split_text,
)


def test_get_user_collection_name():
    assert get_user_collection_name(42) == "user_42"


def test_format_document_source_with_page():
    source = format_document_source({"filename": "contrat.pdf", "page": 0})

    assert source == "contrat.pdf, page 1"


def test_format_retrieved_documents_includes_sources():
    docs = [
        {
            "content": "Le contrat commence le 1er janvier.",
            "metadata": {"filename": "contrat.pdf", "page": 1},
        }
    ]

    result = format_retrieved_documents(docs)

    assert "Source: contrat.pdf, page 2" in result
    assert "Le contrat commence le 1er janvier." in result


def test_split_text_keeps_overlap():
    chunks = split_text("a" * 1200, chunk_size=1000, chunk_overlap=200)

    assert len(chunks) == 2
    assert chunks[0] == "a" * 1000
    assert chunks[1] == "a" * 400


def test_call_huggingface_retries_then_returns_text(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(503, {"error": "Model is loading"})
        return FakeResponse(200, [{"generated_text": "Reponse de test"}])

    monkeypatch.setattr(rag.requests, "post", fake_post)
    monkeypatch.setattr(rag, "sleep", lambda *_: None)

    result = call_huggingface("Question de test")

    assert result == "Reponse de test"
    assert calls["count"] == 2


def test_call_huggingface_returns_clear_unavailable_message(monkeypatch):
    class FakeResponse:
        def __init__(self):
            self.status_code = 503

        def json(self):
            return {"error": "Model is loading"}

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

    monkeypatch.setattr(rag.requests, "post", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(rag, "sleep", lambda *_: None)

    result = call_huggingface("Question de test")

    assert result == (
        "Je ne peux pas generer de reponse pour le moment. "
        "Le modele Hugging Face est temporairement indisponible."
    )
