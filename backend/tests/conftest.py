"""Pytest fixtures for SAT-TRIAGE backend tests."""

from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import user  # noqa: F401, E402
from app.models.user import User  # noqa: E402


def make_test_auth_headers(db: Session, username: str = "test_admin", role: str = "ADMIN") -> dict[str, str]:
    """Ensure a test user exists in the given session and return a valid Bearer JWT header."""
    from sqlalchemy import select

    existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if existing is None:
        existing = User(
            username=username,
            email=f"{username}@devcore.space",
            password_hash=hash_password("TestSuitePass!2026"),
            role=role,
            is_active=True,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

    settings = get_settings()
    token = create_access_token(
        subject=existing.username,
        role=role,
        secret_key=settings.jwt_secret_key,
        user_id=existing.id,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(sqlite_session: Session) -> dict[str, str]:
    """Return Bearer JWT headers for an ADMIN user in sqlite_session."""
    return make_test_auth_headers(sqlite_session, username="test_admin", role="ADMIN")


@pytest.fixture()
def sqlite_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Provide an isolated SQLite database session with schema initialized."""
    db_file = tmp_path / "test_sat_triage.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture()
def client(sqlite_session: Session) -> Generator[TestClient, None, None]:
    """Return a TestClient wired to the isolated test DB session."""

    def override_get_db() -> Generator[Session, None, None]:
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
