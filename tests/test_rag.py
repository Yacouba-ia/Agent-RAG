import rag
from rag import (
    OPENAI_UNAVAILABLE_MESSAGE,
    call_openai,
    format_document_source,
    format_retrieved_documents,
    get_user_collection_name,
    run_rag,
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


def test_call_openai_returns_generated_text(monkeypatch):
    calls = {}

    class FakeOpenAIResponse:
        output_text = " Reponse de test "

    class FakeResponses:
        def create(self, **kwargs):
            calls["create_kwargs"] = kwargs
            return FakeOpenAIResponse()

    class FakeOpenAIClient:
        def __init__(self, **kwargs):
            calls["client_kwargs"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr(rag.settings, "openai_api_key", "test-openai-key")
    monkeypatch.setattr(rag.settings, "openai_model", "gpt-4.1-mini")
    monkeypatch.setattr(rag, "OpenAI", FakeOpenAIClient)

    result = call_openai("Question de test")

    assert result == "Reponse de test"
    assert calls["client_kwargs"]["api_key"] == "test-openai-key"
    assert calls["create_kwargs"]["model"] == "gpt-4.1-mini"
    assert calls["create_kwargs"]["input"] == "Question de test"


def test_call_openai_returns_clear_unavailable_message_without_key(monkeypatch):
    monkeypatch.setattr(rag.settings, "openai_api_key", "")

    result = call_openai("Question de test")

    assert result == OPENAI_UNAVAILABLE_MESSAGE


def test_call_openai_returns_clear_unavailable_message_on_error(monkeypatch):
    class FakeResponses:
        def create(self, **kwargs):
            raise RuntimeError("OpenAI temporary error")

    class FakeOpenAIClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr(rag.settings, "openai_api_key", "test-openai-key")
    monkeypatch.setattr(rag, "OpenAI", FakeOpenAIClient)

    result = call_openai("Question de test")

    assert result == OPENAI_UNAVAILABLE_MESSAGE


def test_run_rag_keeps_no_relevant_document_message(monkeypatch):
    monkeypatch.setattr(rag, "retrieve_documents", lambda **kwargs: [])

    result = run_rag(db=None, query="Question", user_id=1)

    assert result == (
        "Je ne sais pas. Aucun document pertinent n'a été trouvé "
        "dans votre base documentaire."
    )
