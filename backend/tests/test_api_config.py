"""Tests for GET /config and PUT /config/llm_provider."""
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_config_returns_current_provider(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.get("/config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_provider" in data
    assert data["llm_provider"] in ("auto", "groq", "gemini")


@pytest.mark.asyncio
async def test_set_llm_provider_groq(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.put(
        "/config/llm_provider",
        json={"provider": "groq"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["llm_provider"] == "groq"


@pytest.mark.asyncio
async def test_set_llm_provider_gemini(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.put(
        "/config/llm_provider",
        json={"provider": "gemini"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["llm_provider"] == "gemini"


@pytest.mark.asyncio
async def test_set_llm_provider_auto(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.put(
        "/config/llm_provider",
        json={"provider": "auto"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["llm_provider"] == "auto"


@pytest.mark.asyncio
async def test_set_llm_provider_invalid_rejected(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.put(
        "/config/llm_provider",
        json={"provider": "openai"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_llm_provider_requires_auth(test_client: AsyncClient):
    resp = await test_client.put(
        "/config/llm_provider",
        json={"provider": "groq"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_config_reflects_set_provider(test_client: AsyncClient, auth_headers: dict):
    await test_client.put(
        "/config/llm_provider",
        json={"provider": "gemini"},
        headers=auth_headers,
    )
    resp = await test_client.get("/config", headers=auth_headers)
    assert resp.json()["llm_provider"] == "gemini"


@pytest.mark.asyncio
async def test_set_llm_provider_requires_write_scope(test_client: AsyncClient, auth_headers: dict):
    """Admin token has write scope — should succeed."""
    resp = await test_client.put(
        "/config/llm_provider",
        json={"provider": "auto"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
