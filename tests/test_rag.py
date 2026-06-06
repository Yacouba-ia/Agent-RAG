from rag import (
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
