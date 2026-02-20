"""Integration tests for auth API endpoints — login, refresh, /users/me."""

import pytest
from httpx import AsyncClient


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@cloudtab.local", "password": "testpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@cloudtab.local", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_invalid_email_format(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "pass"},
        )
        assert resp.status_code == 422  # Pydantic validation


class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_success(self, client: AsyncClient, test_user):
        # First login to get tokens
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@cloudtab.local", "password": "testpass123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Use refresh token to get new tokens
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, client: AsyncClient, test_user):
        # Login to get an access token
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@cloudtab.local", "password": "testpass123"},
        )
        access_token = login_resp.json()["access_token"]

        # Using access token as refresh should fail
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "garbage-token"},
        )
        assert resp.status_code == 401


class TestGetMe:
    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, auth_client: AsyncClient, test_user):
        resp = await auth_client.get("/api/v1/users/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@cloudtab.local"
        assert data["is_active"] is True
        assert data["id"] == test_user.id

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401
