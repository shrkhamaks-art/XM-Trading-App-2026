import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.rate_limit import enforce_rate_limit


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_rate_limit_allows_requests_within_limit(db_session):
    enforce_rate_limit(db_session, scope="test", identity="client", limit=2, window_seconds=60)
    enforce_rate_limit(db_session, scope="test", identity="client", limit=2, window_seconds=60)


def test_rate_limit_blocks_request_over_limit(db_session):
    enforce_rate_limit(db_session, scope="test", identity="client", limit=1, window_seconds=60)
    with pytest.raises(HTTPException) as error:
        enforce_rate_limit(db_session, scope="test", identity="client", limit=1, window_seconds=60)
    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "60"


def test_rate_limit_isolated_by_identity_and_scope(db_session):
    enforce_rate_limit(db_session, scope="login", identity="client-a", limit=1, window_seconds=60)
    enforce_rate_limit(db_session, scope="login", identity="client-b", limit=1, window_seconds=60)
    enforce_rate_limit(db_session, scope="register", identity="client-a", limit=1, window_seconds=60)
