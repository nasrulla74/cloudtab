"""Integration tests for instance, domain, backup, and git API endpoints.

Note: Celery task endpoints (deploy, start, stop, etc.) dispatch async tasks.
We mock the Celery .delay() calls to avoid needing a real broker.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


# ═══════════════════════════════════════════════════════════════════════════
# Instance endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestInstances:
    @pytest.mark.asyncio
    async def test_list_instances(self, auth_client: AsyncClient, test_server):
        resp = await auth_client.get(f"/api/v1/servers/{test_server.id}/instances")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    @patch("app.api.v1.instances.deploy_odoo_instance")
    async def test_create_instance(self, mock_deploy, auth_client: AsyncClient, test_server):
        mock_task = MagicMock()
        mock_task.id = "celery-fake-id"
        mock_deploy.delay.return_value = mock_task

        resp = await auth_client.post(
            f"/api/v1/servers/{test_server.id}/instances",
            json={
                "name": "New Odoo",
                "odoo_version": "17.0",
                "edition": "community",
                "host_port": 8070,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_id"] == "celery-fake-id"
        mock_deploy.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instance(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.get(f"/api/v1/instances/{test_instance.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Instance"

    @pytest.mark.asyncio
    async def test_update_instance(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.patch(
            f"/api/v1/instances/{test_instance.id}",
            json={"name": "Renamed Odoo"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Odoo"

    @pytest.mark.asyncio
    @patch("app.api.v1.instances.destroy_odoo_instance")
    async def test_delete_instance(self, mock_destroy, auth_client: AsyncClient, test_instance):
        mock_task = MagicMock()
        mock_task.id = "destroy-task-id"
        mock_destroy.delay.return_value = mock_task

        resp = await auth_client.delete(f"/api/v1/instances/{test_instance.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "destroy-task-id"
        mock_destroy.delay.assert_called_once_with(test_instance.id)

    @pytest.mark.asyncio
    async def test_get_instance_not_found(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/instances/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.api.v1.instances.start_odoo_instance")
    async def test_start_instance(self, mock_start, auth_client: AsyncClient, test_instance):
        mock_task = MagicMock()
        mock_task.id = "start-task-id"
        mock_start.delay.return_value = mock_task

        resp = await auth_client.post(f"/api/v1/instances/{test_instance.id}/start")
        assert resp.status_code == 200
        assert resp.json()["task_id"] == "start-task-id"

    @pytest.mark.asyncio
    @patch("app.api.v1.instances.stop_odoo_instance")
    async def test_stop_instance(self, mock_stop, auth_client: AsyncClient, test_instance):
        mock_task = MagicMock()
        mock_task.id = "stop-task-id"
        mock_stop.delay.return_value = mock_task

        resp = await auth_client.post(f"/api/v1/instances/{test_instance.id}/stop")
        assert resp.status_code == 200
        assert resp.json()["task_id"] == "stop-task-id"


# ═══════════════════════════════════════════════════════════════════════════
# Domain endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestDomains:
    @pytest.mark.asyncio
    async def test_list_domains_empty(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.get(f"/api/v1/instances/{test_instance.id}/domains")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    @patch("app.api.v1.domains.setup_nginx_proxy")
    async def test_create_domain(self, mock_nginx, auth_client: AsyncClient, test_instance):
        mock_task = MagicMock()
        mock_task.id = "nginx-task"
        mock_nginx.delay.return_value = mock_task

        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/domains",
            json={"domain_name": "test.example.com"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_id"] == "nginx-task"

    @pytest.mark.asyncio
    @patch("app.api.v1.domains.setup_nginx_proxy")
    async def test_create_and_delete_domain(
        self, mock_nginx, auth_client: AsyncClient, test_instance, db
    ):
        mock_task = MagicMock()
        mock_task.id = "nginx-task-2"
        mock_nginx.delay.return_value = mock_task

        # Create
        await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/domains",
            json={"domain_name": "del.example.com"},
        )

        # List to get the domain ID
        list_resp = await auth_client.get(
            f"/api/v1/instances/{test_instance.id}/domains"
        )
        domains = list_resp.json()
        domain_id = next(d["id"] for d in domains if d["domain_name"] == "del.example.com")

        # Delete
        resp = await auth_client.delete(f"/api/v1/domains/{domain_id}")
        assert resp.status_code == 204


# ═══════════════════════════════════════════════════════════════════════════
# Backup endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestBackups:
    @pytest.mark.asyncio
    async def test_list_schedules_empty(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.get(
            f"/api/v1/instances/{test_instance.id}/backup-schedules"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_schedule(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/backup-schedules",
            json={"frequency": "daily", "retention_days": 14},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["frequency"] == "daily"
        assert data["retention_days"] == 14
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_s3_schedule(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/backup-schedules",
            json={
                "frequency": "weekly",
                "retention_days": 60,
                "storage_type": "s3",
                "s3_bucket": "my-backups",
                "s3_prefix": "cloudtab/prod",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["storage_type"] == "s3"
        assert data["s3_bucket"] == "my-backups"
        assert data["s3_prefix"] == "cloudtab/prod"
        assert data["frequency"] == "weekly"
        assert data["retention_days"] == 60

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_frequency(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/backup-schedules",
            json={"frequency": "hourly"},  # Invalid
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_storage_type(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/backup-schedules",
            json={"frequency": "daily", "storage_type": "ftp"},  # Invalid
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    @patch("app.api.v1.backups.run_backup")
    async def test_trigger_backup(self, mock_backup, auth_client: AsyncClient, test_instance):
        mock_task = MagicMock()
        mock_task.id = "backup-task"
        mock_backup.delay.return_value = mock_task

        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/backup-now"
        )
        assert resp.status_code == 200
        assert resp.json()["task_id"] == "backup-task"

    @pytest.mark.asyncio
    async def test_list_backup_records_empty(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.get(
            f"/api/v1/instances/{test_instance.id}/backup-records"
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ═══════════════════════════════════════════════════════════════════════════
# Git repo endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestGitRepos:
    @pytest.mark.asyncio
    async def test_get_git_repo_none(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.get(
            f"/api/v1/instances/{test_instance.id}/git-repo"
        )
        assert resp.status_code == 200
        assert resp.json() is None

    @pytest.mark.asyncio
    async def test_link_git_repo(self, auth_client: AsyncClient, test_instance):
        resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/git-repo",
            json={
                "repo_url": "git@github.com:org/modules.git",
                "branch": "main",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["repo_url"] == "git@github.com:org/modules.git"
        assert data["branch"] == "main"

    @pytest.mark.asyncio
    async def test_link_and_get_git_repo(self, auth_client: AsyncClient, test_instance):
        # Link
        await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/git-repo",
            json={"repo_url": "https://github.com/x/y.git", "branch": "dev"},
        )

        # Get
        resp = await auth_client.get(
            f"/api/v1/instances/{test_instance.id}/git-repo"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["repo_url"] == "https://github.com/x/y.git"

    @pytest.mark.asyncio
    @patch("app.api.v1.git_repos.deploy_git_modules")
    async def test_deploy_modules(self, mock_deploy, auth_client: AsyncClient, test_instance):
        mock_task = MagicMock()
        mock_task.id = "deploy-modules-task"
        mock_deploy.delay.return_value = mock_task

        # First link a repo
        create_resp = await auth_client.post(
            f"/api/v1/instances/{test_instance.id}/git-repo",
            json={"repo_url": "https://github.com/a/b.git", "branch": "main"},
        )
        repo_id = create_resp.json()["id"]

        # Deploy
        resp = await auth_client.post(f"/api/v1/git-repos/{repo_id}/deploy")
        assert resp.status_code == 200
        assert resp.json()["task_id"] == "deploy-modules-task"


# ═══════════════════════════════════════════════════════════════════════════
# Task endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestTasks:
    @pytest.mark.asyncio
    async def test_get_task_not_found(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/tasks/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_after_creation(self, auth_client: AsyncClient, test_user, db):
        from app.services.server_service import create_task_log

        log = await create_task_log(
            db, "test-celery-id", test_user, "test_op", 1, "server"
        )

        resp = await auth_client.get(f"/api/v1/tasks/{log.celery_task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["celery_task_id"] == "test-celery-id"
        assert data["status"] == "pending"
        assert data["task_type"] == "test_op"
