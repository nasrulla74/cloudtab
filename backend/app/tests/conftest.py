"""
Shared fixtures for CloudTab test suite.

Uses an in-memory SQLite database via aiosqlite for fast, isolated tests.
Each test function gets its own database session that is rolled back after the test.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.models.base import Base

# ---------------------------------------------------------------------------
# Async event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database engine & session  (SQLite in-memory, per-session)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture()
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test database session. Rolls back after each test for isolation."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session
        # Rollback any uncommitted changes after the test
        await session.rollback()


# ---------------------------------------------------------------------------
# Seed user helper
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def test_user(db: AsyncSession):
    """Create and return a test user."""
    from app.models.user import User

    user = User(
        email="test@cloudtab.local",
        hashed_password=hash_password("testpass123"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture()
def auth_token(test_user) -> str:
    """Return a valid JWT access token for the test user."""
    return create_access_token(str(test_user.id))


# ---------------------------------------------------------------------------
# Test server + instance helpers
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def test_server(db: AsyncSession, test_user):
    """Create and return a test server."""
    from app.core.encryption import encrypt_value
    from app.models.server import Server

    server = Server(
        owner_id=test_user.id,
        name="Test Server",
        host="192.168.1.100",
        port=22,
        ssh_user="root",
        ssh_key_encrypted=encrypt_value("fake-ssh-key"),
    )
    db.add(server)
    await db.flush()
    return server


@pytest_asyncio.fixture()
async def test_instance(db: AsyncSession, test_server):
    """Create and return a test Odoo instance."""
    from app.models.odoo_instance import OdooInstance

    instance = OdooInstance(
        server_id=test_server.id,
        name="Test Instance",
        odoo_version="17.0",
        edition="community",
        container_name="odoo-test-s1",
        host_port=8069,
        pg_container_name="odoo-test-s1-db",
        pg_port=9069,
        pg_password="odoo",
        addons_path="/opt/cloudtab/odoo-test-s1/addons",
    )
    db.add(instance)
    await db.flush()
    return instance


# ---------------------------------------------------------------------------
# HTTPX AsyncClient (integration tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def client(db: AsyncSession, test_user) -> AsyncGenerator[AsyncClient, None]:
    """
    An AsyncClient that talks to the real FastAPI app, but with the DB
    dependency overridden to use the test session.
    """
    from app.core.database import get_db
    from app.main import app

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def auth_client(client: AsyncClient, auth_token: str) -> AsyncClient:
    """AsyncClient pre-configured with an auth header."""
    client.headers["Authorization"] = f"Bearer {auth_token}"
    return client
