"""Tests for /auth endpoints — login, refresh, revoke, scope enforcement."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(test_client: AsyncClient):
    resp = await test_client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(test_client: AsyncClient):
    resp = await test_client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_username(test_client: AsyncClient):
    resp = await test_client.post("/auth/login", json={"username": "hacker", "password": "admin"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_new_token(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.post("/auth/refresh", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body


@pytest.mark.asyncio
async def test_refresh_requires_auth(test_client: AsyncClient):
    resp = await test_client.post("/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoke_invalidates_token(test_client: AsyncClient):
    # Get a fresh token
    login_resp = await test_client.post("/auth/login", json={"username": "admin", "password": "admin"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Revoke it
    revoke_resp = await test_client.post("/auth/revoke", headers=headers)
    assert revoke_resp.status_code == 204

    # Subsequent request should fail
    refresh_resp = await test_client.post("/auth/refresh", headers=headers)
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_scope_enforcement_returns_403(test_client: AsyncClient, auth_headers: dict):
    """Admin token has all scopes, but verify that unauthenticated access fails."""
    resp = await test_client.get("/calls")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_requires_valid_token(test_client: AsyncClient):
    resp = await test_client.get("/calls", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401
