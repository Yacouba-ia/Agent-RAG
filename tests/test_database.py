from database import normalize_database_url


def test_normalize_database_url_uses_psycopg_for_plain_postgresql_url():
    url = "postgresql://user:password@host:5432/database"

    assert (
        normalize_database_url(url)
        == "postgresql+psycopg://user:password@host:5432/database"
    )


def test_normalize_database_url_keeps_explicit_driver_url():
    url = "postgresql+psycopg://user:password@host:5432/database"

    assert normalize_database_url(url) == url


def test_normalize_database_url_keeps_sqlite_url():
    url = "sqlite:///./test.db"

    assert normalize_database_url(url) == url
