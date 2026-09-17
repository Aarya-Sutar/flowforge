"""Shared pytest fixtures.

Tests run against an in-memory SQLite database rather than Postgres. This
keeps Phase 1 tests fast and dependency-free (no Docker required to run
`pytest`). It's a deliberate simplification: SQLite does not enforce every
constraint Postgres does. Phase 7 (Testing Architecture) revisits this with
a real Postgres test database for full parity with production.
"""
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User, UserRole

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    # Route handlers enqueue Celery tasks via `.delay(...)`, which otherwise tries
    # to open a real connection to Redis. No broker runs in the test environment,
    # so we replace `.delay` with a no-op — the worker pipeline itself is tested
    # directly in test_processing_service.py, independent of Celery/HTTP entirely.
    monkeypatch.setattr("app.workers.tasks.process_request.delay", lambda *args, **kwargs: None)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_user(db_session: Session, *, email: str, role: UserRole) -> User:
    user = User(name=email.split("@")[0], email=email, password_hash=hash_password("password123"), role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_a(db_session: Session) -> User:
    return _create_user(db_session, email="user-a@example.com", role=UserRole.USER)


@pytest.fixture()
def user_b(db_session: Session) -> User:
    return _create_user(db_session, email="user-b@example.com", role=UserRole.USER)


@pytest.fixture()
def operator_user(db_session: Session) -> User:
    return _create_user(db_session, email="operator@example.com", role=UserRole.OPERATOR)


@pytest.fixture()
def admin_user(db_session: Session) -> User:
    return _create_user(db_session, email="admin@example.com", role=UserRole.ADMIN)


@pytest.fixture()
def user_a_headers(user_a: User) -> dict[str, str]:
    return _auth_headers(user_a)


@pytest.fixture()
def user_b_headers(user_b: User) -> dict[str, str]:
    return _auth_headers(user_b)


@pytest.fixture()
def operator_headers(operator_user: User) -> dict[str, str]:
    return _auth_headers(operator_user)


@pytest.fixture()
def admin_headers(admin_user: User) -> dict[str, str]:
    return _auth_headers(admin_user)
