"""Integration tests for server API endpoints."""

import pytest
from httpx import AsyncClient


class TestListServers:
    @pytest.mark.asyncio
    async def test_list_servers_empty(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/servers")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_servers_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/servers")
        assert resp.status_code == 401


class TestCreateServer:
    @pytest.mark.asyncio
    async def test_create_server_success(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/api/v1/servers",
            json={
                "name": "API Test Server",
                "host": "10.0.0.5",
                "port": 22,
                "ssh_user": "root",
                "ssh_key": "my-fake-key",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test Server"
        assert data["host"] == "10.0.0.5"
        assert data["status"] == "unknown"
        assert "ssh_key_encrypted" not in data  # Should not leak encrypted key
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_server_missing_fields(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/api/v1/servers",
            json={"name": "Incomplete"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_server_invalid_port(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/api/v1/servers",
            json={
                "name": "Bad Port",
                "host": "10.0.0.1",
                "port": 99999,
                "ssh_user": "root",
                "ssh_key": "key",
            },
        )
        assert resp.status_code == 422


class TestGetServer:
    @pytest.mark.asyncio
    async def test_get_server(self, auth_client: AsyncClient, test_server):
        resp = await auth_client.get(f"/api/v1/servers/{test_server.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Server"

    @pytest.mark.asyncio
    async def test_get_server_not_found(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/servers/99999")
        assert resp.status_code == 404


class TestUpdateServer:
    @pytest.mark.asyncio
    async def test_update_server(self, auth_client: AsyncClient, test_server):
        resp = await auth_client.patch(
            f"/api/v1/servers/{test_server.id}",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"


class TestDeleteServer:
    @pytest.mark.asyncio
    async def test_delete_server(self, auth_client: AsyncClient, test_server):
        resp = await auth_client.delete(f"/api/v1/servers/{test_server.id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = await auth_client.get(f"/api/v1/servers/{test_server.id}")
        assert resp2.status_code == 404
