"""Shared pytest fixtures for all Vaani tests."""
from __future__ import annotations

import os

# Override settings before app is imported so tests use predictable credentials
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SARVAM_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.storage.database import get_db
from app.storage.models import Base


# ── Database ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session, tables created fresh per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client(db_session: AsyncSession):
    """FastAPI async test client with DB dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_revoked_tokens():
    """Clear the in-memory token revocation set between tests."""
    from app.api.auth import _revoked_tokens
    _revoked_tokens.clear()
    yield
    _revoked_tokens.clear()


@pytest_asyncio.fixture
async def auth_headers(test_client: AsyncClient):
    """Get a valid JWT bearer token."""
    resp = await test_client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── External API mocks ────────────────────────────────────────────────────────

@pytest.fixture
def mock_sarvam_stt(monkeypatch):
    """Mock AsyncSarvamAI STT to avoid real API calls (STT uses async client)."""
    from unittest.mock import AsyncMock
    fake_response = MagicMock()
    fake_response.transcript = "यह एक टेस्ट ट्रांसक्रिप्ट है"
    fake_response.language_code = "hi-IN"
    fake_response.time_taken = 0.1

    mock_client = MagicMock()
    mock_client.speech_to_text.transcribe = AsyncMock(return_value=fake_response)

    monkeypatch.setattr("sarvamai.AsyncSarvamAI", lambda **kwargs: mock_client)
    return mock_client


@pytest.fixture
def mock_groq(monkeypatch):
    """Mock Groq streaming completions."""

    async def fake_stream(*args, **kwargs):
        class FakeChunk:
            choices = [type("c", (), {"delta": type("d", (), {"content": "Mock agent response."})()})()]

        class FakeStream:
            async def __aiter__(self):
                yield FakeChunk()

        return FakeStream()

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=fake_stream)
    # Patch at source package — AsyncGroq is imported lazily inside __init__
    monkeypatch.setattr("groq.AsyncGroq", lambda **kwargs: mock_client)
    return mock_client


@pytest.fixture
def mock_sarvam_tts(monkeypatch):
    """Mock SarvamAI TTS."""
    import base64

    fake_response = MagicMock()
    fake_response.audios = [base64.b64encode(b"\x00" * 100).decode()]

    mock_async_client = MagicMock()
    mock_async_client.text_to_speech.convert = AsyncMock(return_value=fake_response)

    mock_sync_client = MagicMock()
    mock_sync_client.text_to_speech.convert.return_value = fake_response

    # Patch at source package — both are imported lazily inside __init__
    monkeypatch.setattr("sarvamai.SarvamAI", lambda **kwargs: mock_sync_client)
    monkeypatch.setattr("sarvamai.AsyncSarvamAI", lambda **kwargs: mock_async_client)
    return mock_async_client
