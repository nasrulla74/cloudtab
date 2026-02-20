"""Unit tests for service layer — auth, server, odoo, domain, backup, git."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User

# ═══════════════════════════════════════════════════════════════════════════
# Auth Service
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthService:
    @pytest.mark.asyncio
    async def test_authenticate_valid_user(self, db: AsyncSession, test_user):
        from app.services.auth_service import authenticate_user

        user = await authenticate_user(db, "test@cloudtab.local", "testpass123")
        assert user is not None
        assert user.id == test_user.id
        assert user.email == "test@cloudtab.local"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, db: AsyncSession, test_user):
        from app.services.auth_service import authenticate_user

        user = await authenticate_user(db, "test@cloudtab.local", "wrongpass")
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_email(self, db: AsyncSession):
        from app.services.auth_service import authenticate_user

        user = await authenticate_user(db, "nobody@example.com", "whatever")
        assert user is None

    def test_create_tokens(self, test_user):
        from app.services.auth_service import create_tokens
        from app.core.security import decode_token

        tokens = create_tokens(test_user)
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"

        payload = decode_token(tokens["access_token"])
        assert payload["sub"] == str(test_user.id)
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_create_user(self, db: AsyncSession):
        from app.services.auth_service import create_user

        user = await create_user(db, "new@example.com", "newpass")
        assert user.id is not None
        assert user.email == "new@example.com"
        assert user.hashed_password != "newpass"


# ═══════════════════════════════════════════════════════════════════════════
# Server Service
# ═══════════════════════════════════════════════════════════════════════════

class TestServerService:
    @pytest.mark.asyncio
    async def test_create_server(self, db: AsyncSession, test_user):
        from app.schemas.server import ServerCreate
        from app.services.server_service import create_server

        data = ServerCreate(
            name="My Server",
            host="10.0.0.1",
            port=22,
            ssh_user="deploy",
            ssh_key="fake-key",
        )
        server = await create_server(db, data, test_user)
        assert server.id is not None
        assert server.name == "My Server"
        assert server.host == "10.0.0.1"
        assert server.owner_id == test_user.id
        assert server.ssh_key_encrypted != "fake-key"  # Encrypted

    @pytest.mark.asyncio
    async def test_list_servers_only_own(self, db: AsyncSession, test_user):
        from app.services.server_service import list_servers

        servers = await list_servers(db, test_user)
        # Each server created by test_user should appear
        for s in servers:
            assert s.owner_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_server_by_owner(self, db: AsyncSession, test_user, test_server):
        from app.services.server_service import get_server

        server = await get_server(db, test_server.id, test_user)
        assert server is not None
        assert server.id == test_server.id

    @pytest.mark.asyncio
    async def test_get_server_wrong_owner(self, db: AsyncSession, test_server):
        from app.services.server_service import get_server

        # Create a different user
        other_user = User(
            email="other@example.com",
            hashed_password=hash_password("pass"),
        )
        db.add(other_user)
        await db.flush()

        server = await get_server(db, test_server.id, other_user)
        assert server is None

    @pytest.mark.asyncio
    async def test_update_server(self, db: AsyncSession, test_server):
        from app.schemas.server import ServerUpdate
        from app.services.server_service import update_server

        data = ServerUpdate(name="Renamed Server")
        updated = await update_server(db, test_server, data)
        assert updated.name == "Renamed Server"

    @pytest.mark.asyncio
    async def test_delete_server(self, db: AsyncSession, test_user, test_server):
        from app.services.server_service import delete_server, get_server

        await delete_server(db, test_server)
        result = await get_server(db, test_server.id, test_user)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_task_log(self, db: AsyncSession, test_user):
        from app.services.server_service import create_task_log

        log = await create_task_log(
            db, "celery-123", test_user, "test_connection", 1, "server"
        )
        assert log.id is not None
        assert log.celery_task_id == "celery-123"
        assert log.user_id == test_user.id
        assert log.task_type == "test_connection"
        assert log.status == "pending"


# ═══════════════════════════════════════════════════════════════════════════
# Odoo Instance Service
# ═══════════════════════════════════════════════════════════════════════════

class TestOdooService:
    @pytest.mark.asyncio
    async def test_create_instance(self, db: AsyncSession, test_server):
        from app.schemas.odoo_instance import InstanceCreate
        from app.services.odoo_service import create_instance

        data = InstanceCreate(
            name="Production",
            odoo_version="17.0",
            edition="community",
            host_port=8069,
        )
        instance = await create_instance(db, test_server, data)
        assert instance.id is not None
        assert instance.name == "Production"
        assert instance.server_id == test_server.id
        assert instance.container_name.startswith("odoo-")
        assert instance.pg_container_name.endswith("-db")
        assert instance.pg_port == 8069 + 1000

    @pytest.mark.asyncio
    async def test_container_name_sanitization(self, db: AsyncSession, test_server):
        from app.services.odoo_service import _generate_container_name

        assert _generate_container_name("My App!", 5) == "odoo-my-app-s5"
        assert _generate_container_name("  spaces  ", 1) == "odoo-spaces-s1"
        assert _generate_container_name("UPPER", 2) == "odoo-upper-s2"

    @pytest.mark.asyncio
    async def test_list_instances(self, db: AsyncSession, test_server, test_instance):
        from app.services.odoo_service import list_instances

        instances = await list_instances(db, test_server.id)
        assert any(i.id == test_instance.id for i in instances)

    @pytest.mark.asyncio
    async def test_get_instance(self, db: AsyncSession, test_instance):
        from app.services.odoo_service import get_instance

        inst = await get_instance(db, test_instance.id)
        assert inst is not None
        assert inst.name == "Test Instance"

    @pytest.mark.asyncio
    async def test_get_nonexistent_instance(self, db: AsyncSession):
        from app.services.odoo_service import get_instance

        inst = await get_instance(db, 99999)
        assert inst is None

    @pytest.mark.asyncio
    async def test_update_instance(self, db: AsyncSession, test_instance):
        from app.schemas.odoo_instance import InstanceUpdate
        from app.services.odoo_service import update_instance

        data = InstanceUpdate(name="Renamed Instance")
        updated = await update_instance(db, test_instance, data)
        assert updated.name == "Renamed Instance"

    @pytest.mark.asyncio
    async def test_delete_instance(self, db: AsyncSession, test_instance):
        from app.services.odoo_service import delete_instance, get_instance

        await delete_instance(db, test_instance)
        result = await get_instance(db, test_instance.id)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Domain Service
# ═══════════════════════════════════════════════════════════════════════════

class TestDomainService:
    @pytest.mark.asyncio
    async def test_create_domain(self, db: AsyncSession, test_instance):
        from app.schemas.domain import DomainCreate
        from app.services.domain_service import create_domain

        data = DomainCreate(domain_name="odoo.example.com")
        domain = await create_domain(db, test_instance.id, data)
        assert domain.id is not None
        assert domain.domain_name == "odoo.example.com"
        assert domain.instance_id == test_instance.id
        assert domain.status == "pending"
        assert domain.ssl_status == "none"

    @pytest.mark.asyncio
    async def test_list_domains(self, db: AsyncSession, test_instance):
        from app.schemas.domain import DomainCreate
        from app.services.domain_service import create_domain, list_domains

        await create_domain(db, test_instance.id, DomainCreate(domain_name="a.example.com"))
        await create_domain(db, test_instance.id, DomainCreate(domain_name="b.example.com"))

        domains = await list_domains(db, test_instance.id)
        assert len(domains) >= 2

    @pytest.mark.asyncio
    async def test_get_domain(self, db: AsyncSession, test_instance):
        from app.schemas.domain import DomainCreate
        from app.services.domain_service import create_domain, get_domain

        domain = await create_domain(db, test_instance.id, DomainCreate(domain_name="get.example.com"))
        fetched = await get_domain(db, domain.id)
        assert fetched is not None
        assert fetched.domain_name == "get.example.com"

    @pytest.mark.asyncio
    async def test_delete_domain(self, db: AsyncSession, test_instance):
        from app.schemas.domain import DomainCreate
        from app.services.domain_service import create_domain, delete_domain, get_domain

        domain = await create_domain(db, test_instance.id, DomainCreate(domain_name="del.example.com"))
        await delete_domain(db, domain)
        result = await get_domain(db, domain.id)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Backup Service
# ═══════════════════════════════════════════════════════════════════════════

class TestBackupService:
    @pytest.mark.asyncio
    async def test_create_schedule(self, db: AsyncSession, test_instance):
        from app.schemas.backup import BackupScheduleCreate
        from app.services.backup_service import create_schedule

        data = BackupScheduleCreate(frequency="daily", retention_days=7)
        schedule = await create_schedule(db, test_instance.id, data)
        assert schedule.id is not None
        assert schedule.frequency == "daily"
        assert schedule.retention_days == 7
        assert schedule.is_active is True
        assert schedule.next_run_at is not None

    @pytest.mark.asyncio
    async def test_update_schedule(self, db: AsyncSession, test_instance):
        from app.schemas.backup import BackupScheduleCreate, BackupScheduleUpdate
        from app.services.backup_service import create_schedule, update_schedule

        schedule = await create_schedule(
            db, test_instance.id, BackupScheduleCreate(frequency="daily")
        )
        updated = await update_schedule(
            db, schedule, BackupScheduleUpdate(frequency="weekly", is_active=False)
        )
        assert updated.frequency == "weekly"
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_delete_schedule(self, db: AsyncSession, test_instance):
        from app.schemas.backup import BackupScheduleCreate
        from app.services.backup_service import create_schedule, delete_schedule, get_schedule

        schedule = await create_schedule(
            db, test_instance.id, BackupScheduleCreate(frequency="monthly")
        )
        sid = schedule.id
        await delete_schedule(db, schedule)
        result = await get_schedule(db, sid)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_schedules(self, db: AsyncSession, test_instance):
        from app.schemas.backup import BackupScheduleCreate
        from app.services.backup_service import create_schedule, list_schedules

        await create_schedule(db, test_instance.id, BackupScheduleCreate(frequency="daily"))
        schedules = await list_schedules(db, test_instance.id)
        assert len(schedules) >= 1

    @pytest.mark.asyncio
    async def test_calculate_next_run(self):
        from datetime import UTC, datetime
        from app.services.backup_service import _calculate_next_run

        now = datetime.now(UTC)
        daily = _calculate_next_run("daily")
        weekly = _calculate_next_run("weekly")
        monthly = _calculate_next_run("monthly")

        assert daily > now
        assert weekly > daily
        assert monthly > daily

    @pytest.mark.asyncio
    async def test_list_backup_records_empty(self, db: AsyncSession, test_instance):
        from app.services.backup_service import list_backup_records

        records = await list_backup_records(db, test_instance.id)
        assert records == []


# ═══════════════════════════════════════════════════════════════════════════
# Git Service
# ═══════════════════════════════════════════════════════════════════════════

class TestGitService:
    @pytest.mark.asyncio
    async def test_create_git_repo(self, db: AsyncSession, test_instance):
        from app.schemas.git_repo import GitRepoCreate
        from app.services.git_service import create_git_repo

        data = GitRepoCreate(
            repo_url="git@github.com:org/modules.git",
            branch="main",
            deploy_key="ssh-key-content",
        )
        repo = await create_git_repo(db, test_instance.id, data)
        assert repo.id is not None
        assert repo.repo_url == "git@github.com:org/modules.git"
        assert repo.branch == "main"
        assert repo.deploy_key_encrypted is not None
        assert repo.deploy_key_encrypted != "ssh-key-content"  # encrypted

    @pytest.mark.asyncio
    async def test_create_git_repo_no_deploy_key(self, db: AsyncSession, test_instance):
        from app.schemas.git_repo import GitRepoCreate
        from app.services.git_service import create_git_repo

        data = GitRepoCreate(
            repo_url="https://github.com/org/public.git",
            branch="develop",
        )
        repo = await create_git_repo(db, test_instance.id, data)
        assert repo.deploy_key_encrypted is None

    @pytest.mark.asyncio
    async def test_get_git_repo(self, db: AsyncSession, test_instance):
        from app.schemas.git_repo import GitRepoCreate
        from app.services.git_service import create_git_repo, get_git_repo

        created = await create_git_repo(
            db, test_instance.id,
            GitRepoCreate(repo_url="https://github.com/x/y.git", branch="main"),
        )
        fetched = await get_git_repo(db, created.id)
        assert fetched is not None
        assert fetched.repo_url == "https://github.com/x/y.git"

    @pytest.mark.asyncio
    async def test_update_git_repo(self, db: AsyncSession, test_instance):
        from app.schemas.git_repo import GitRepoCreate, GitRepoUpdate
        from app.services.git_service import create_git_repo, update_git_repo

        repo = await create_git_repo(
            db, test_instance.id,
            GitRepoCreate(repo_url="https://github.com/a/b.git", branch="main"),
        )
        updated = await update_git_repo(
            db, repo, GitRepoUpdate(branch="develop")
        )
        assert updated.branch == "develop"
        assert updated.repo_url == "https://github.com/a/b.git"  # unchanged

    @pytest.mark.asyncio
    async def test_delete_git_repo(self, db: AsyncSession, test_instance):
        from app.schemas.git_repo import GitRepoCreate
        from app.services.git_service import create_git_repo, delete_git_repo, get_git_repo

        repo = await create_git_repo(
            db, test_instance.id,
            GitRepoCreate(repo_url="https://github.com/d/e.git", branch="main"),
        )
        rid = repo.id
        await delete_git_repo(db, repo)
        result = await get_git_repo(db, rid)
        assert result is None
