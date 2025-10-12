"""Pytest configuration and fixtures for PazPaz backend tests."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from pazpaz.core.redis import get_redis
from pazpaz.db.base import Base, get_db
from pazpaz.main import app
from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace

# Test database URL - use separate test database
TEST_DATABASE_URL = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz_test"
# Use database 1 for tests - password will be added from environment
TEST_REDIS_URL = "redis://localhost:6379/1"


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the entire test session.

    This fixture ensures that async tests have a consistent event loop
    throughout the test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """
    Create a test database engine.

    Uses NullPool to avoid connection pooling issues in tests.
    Each test gets a fresh connection.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Create all tables and install pgcrypto extension
    async with engine.begin() as conn:
        # Install pgcrypto extension for encryption tests
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        # Create encryption functions (used in performance tests)
        await conn.execute(
            text("""
                CREATE OR REPLACE FUNCTION encrypt_phi_pgcrypto(
                    plaintext TEXT,
                    encryption_key TEXT,
                    key_version TEXT DEFAULT 'v1'
                )
                RETURNS TEXT AS $$
                DECLARE
                    encrypted_bytes BYTEA;
                    encoded_result TEXT;
                BEGIN
                    IF plaintext IS NULL THEN RETURN NULL; END IF;
                    IF encryption_key IS NULL OR OCTET_LENGTH(encryption_key) < 32 THEN
                        RAISE EXCEPTION 'Encryption key must be at least 32 bytes';
                    END IF;
                    encrypted_bytes := encrypt(
                        convert_to(plaintext, 'UTF8'),
                        convert_to(encryption_key, 'UTF8'),
                        'aes'
                    );
                    encoded_result := encode(encrypted_bytes, 'base64');
                    RETURN key_version || ':' || encoded_result;
                END;
                $$ LANGUAGE plpgsql IMMUTABLE STRICT;
            """)
        )

        await conn.execute(
            text("""
                CREATE OR REPLACE FUNCTION decrypt_phi_pgcrypto(
                    ciphertext TEXT,
                    encryption_key TEXT
                )
                RETURNS TEXT AS $$
                DECLARE
                    key_version TEXT;
                    encoded_data TEXT;
                    encrypted_bytes BYTEA;
                    decrypted_bytes BYTEA;
                BEGIN
                    IF ciphertext IS NULL THEN RETURN NULL; END IF;
                    IF encryption_key IS NULL OR OCTET_LENGTH(encryption_key) < 32 THEN
                        RAISE EXCEPTION 'Encryption key must be at least 32 bytes';
                    END IF;
                    IF position(':' IN ciphertext) > 0 THEN
                        key_version := split_part(ciphertext, ':', 1);
                        encoded_data := split_part(ciphertext, ':', 2);
                    ELSE
                        key_version := 'v1';
                        encoded_data := ciphertext;
                    END IF;
                    encrypted_bytes := decode(encoded_data, 'base64');
                    decrypted_bytes := decrypt(
                        encrypted_bytes,
                        convert_to(encryption_key, 'UTF8'),
                        'aes'
                    );
                    RETURN convert_from(decrypted_bytes, 'UTF8');
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE EXCEPTION 'Decryption failed (invalid key or corrupted data)';
                END;
                $$ LANGUAGE plpgsql IMMUTABLE STRICT;
            """)
        )

        # Create tables
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(test_db_engine) -> AsyncGenerator[AsyncSession]:
    """
    Alias for db_session - provides database session for testing.

    This fixture name matches the parameter name used in service functions,
    making it easier to test service layer code directly.
    """
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession]:
    """
    Create a database session for testing.

    Each test gets a fresh session that is rolled back after the test,
    ensuring test isolation.
    """
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[redis.Redis]:
    """
    Create a Redis client for testing.

    Uses a separate Redis database (database 1) to avoid conflicts with dev data.
    Flushes the test database before and after each test.
    """
    from pazpaz.core.config import settings

    # Use settings.redis_password which loads from .env file
    # Replace database 0 with database 1 for testing
    redis_url = f"redis://:{settings.redis_password}@localhost:6379/1"

    client = redis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
    )

    # Clear test database before test
    await client.flushdb()

    yield client

    # Clear test database after test
    await client.flushdb()
    await (
        client.aclose()
    )  # Use aclose() instead of close() to avoid deprecation warning


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession, redis_client: redis.Redis
) -> AsyncGenerator[AsyncClient]:
    """
    Create a test HTTP client.

    Overrides the get_db and get_redis dependencies to use test instances.
    """
    from starlette.middleware.base import BaseHTTPMiddleware

    # Middleware to inject db_session into request.state for audit middleware
    class DBSessionInjectorMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, db_session):
            super().__init__(app)
            self.db_session = db_session

        async def dispatch(self, request, call_next):
            request.state.db_session = self.db_session
            response = await call_next(request)
            return response

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Add test middleware to inject db_session
    app.add_middleware(DBSessionInjectorMiddleware, db_session=db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Remove test middleware and clear overrides
    app.user_middleware = [
        m
        for m in app.user_middleware
        if not isinstance(m.cls, type)
        or m.cls.__name__ != "DBSessionInjectorMiddleware"
    ]
    app.middleware_stack = None  # Force rebuild
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client_with_csrf(
    db_session: AsyncSession,
    redis_client: redis.Redis,
    workspace_1: Workspace,
    test_user_ws1: User,
) -> AsyncGenerator[AsyncClient]:
    """
    Create a test HTTP client pre-configured with CSRF token for workspace_1.

    This fixture is a convenience wrapper that automatically adds CSRF token
    to the client, making it suitable for tests that make POST/PUT/DELETE
    requests without needing to manually add CSRF headers to each request.

    Usage:
        async def test_create_something(client_with_csrf, ...):
            # CSRF already configured
            headers = get_auth_headers(workspace_1.id)
            response = await client_with_csrf.post(..., headers=headers)
    """

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Add CSRF token to client
        await add_csrf_to_client(ac, workspace_1.id, test_user_ws1.id, redis_client)
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def workspace_1(db_session: AsyncSession) -> Workspace:
    """
    Create a test workspace (workspace 1).

    This represents a therapist's workspace for testing.
    """
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test Workspace 1",
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture(scope="function")
async def test_user_ws1(db_session: AsyncSession, workspace_1: Workspace) -> User:
    """
    Create a test user in workspace 1.

    This user is used for CSRF token generation in tests.
    Uses a consistent UUID for easy reference in tests.
    """
    user = User(
        id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        workspace_id=workspace_1.id,
        email="test-user-ws1@example.com",
        full_name="Test User Workspace 1",
        role=UserRole.OWNER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def workspace_2(db_session: AsyncSession) -> Workspace:
    """
    Create a second test workspace (workspace 2).

    Used to test workspace isolation - data should not leak between workspaces.
    """
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        name="Test Workspace 2",
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture(scope="function")
async def test_user_ws2(db_session: AsyncSession, workspace_2: Workspace) -> User:
    """
    Create a test user in workspace 2.

    This user is used for CSRF token generation in tests for workspace 2.
    Uses a consistent UUID for easy reference in tests.
    """
    user = User(
        id=uuid.UUID("10000000-0000-0000-0000-000000000002"),
        workspace_id=workspace_2.id,
        email="test-user-ws2@example.com",
        full_name="Test User Workspace 2",
        role=UserRole.OWNER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def sample_client_ws1(db_session: AsyncSession, workspace_1: Workspace) -> Client:
    """
    Create a sample client in workspace 1.

    Standard test client with complete data.
    """
    client = Client(
        workspace_id=workspace_1.id,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        consent_status=True,
        notes="Sample client notes",
        tags=["vip", "massage"],
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture(scope="function")
async def sample_client_ws2(db_session: AsyncSession, workspace_2: Workspace) -> Client:
    """
    Create a sample client in workspace 2.

    Used to test workspace isolation.
    """
    client = Client(
        workspace_id=workspace_2.id,
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        phone="+9876543210",
        consent_status=True,
        notes="Another workspace client",
        tags=["physiotherapy"],
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture(scope="function")
async def sample_appointment_ws1(
    db_session: AsyncSession, workspace_1: Workspace, sample_client_ws1: Client
) -> Appointment:
    """
    Create a sample appointment in workspace 1.

    Scheduled for tomorrow at 10:00 AM.
    """
    tomorrow = datetime.now(UTC).replace(
        hour=10, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=tomorrow,
        scheduled_end=tomorrow + timedelta(hours=1),
        location_type=LocationType.CLINIC,
        location_details="Room 101",
        status=AppointmentStatus.SCHEDULED,
        notes="Initial consultation",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture(scope="function")
async def sample_appointment_ws2(
    db_session: AsyncSession, workspace_2: Workspace, sample_client_ws2: Client
) -> Appointment:
    """
    Create a sample appointment in workspace 2.

    Used to test workspace isolation for appointments.
    """
    tomorrow = datetime.now(UTC).replace(
        hour=14, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    appointment = Appointment(
        workspace_id=workspace_2.id,
        client_id=sample_client_ws2.id,
        scheduled_start=tomorrow,
        scheduled_end=tomorrow + timedelta(hours=1),
        location_type=LocationType.HOME,
        location_details="123 Main St",
        status=AppointmentStatus.SCHEDULED,
        notes="Home visit",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture(scope="function")
async def cancelled_appointment_ws1(
    db_session: AsyncSession, workspace_1: Workspace, sample_client_ws1: Client
) -> Appointment:
    """
    Create a cancelled appointment in workspace 1.

    Used to test that cancelled appointments don't cause conflicts.
    """
    tomorrow = datetime.now(UTC).replace(
        hour=15, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=tomorrow,
        scheduled_end=tomorrow + timedelta(hours=1),
        location_type=LocationType.ONLINE,
        location_details="Zoom link",
        status=AppointmentStatus.CANCELLED,
        notes="Client cancelled",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture(scope="function")
async def test_session(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
) -> Session:
    """
    Create a test session in workspace 1.

    Standard SOAP note with all fields populated.
    """
    from pazpaz.models.session import Session

    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC) - timedelta(days=1),
        subjective="Patient reports lower back pain",
        objective="Limited range of motion observed",
        assessment="Acute lumbar strain",
        plan="Ice therapy, rest for 48 hours",
        duration_minutes=60,
        is_draft=True,
        version=1,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest_asyncio.fixture(scope="function")
async def test_session2(
    db_session: AsyncSession,
    workspace_2: Workspace,
    sample_client_ws2: Client,
    test_user_ws2: User,
) -> Session:
    """
    Create a test session in workspace 2.

    Used to test workspace isolation.
    """
    from pazpaz.models.session import Session

    session = Session(
        workspace_id=workspace_2.id,
        client_id=sample_client_ws2.id,
        created_by_user_id=test_user_ws2.id,
        session_date=datetime.now(UTC) - timedelta(days=2),
        subjective="Different workspace session",
        objective="Different workspace observations",
        assessment="Different workspace assessment",
        plan="Different workspace plan",
        duration_minutes=45,
        is_draft=False,
        finalized_at=datetime.now(UTC) - timedelta(days=2),
        version=1,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


# Convenience aliases for consistent test fixture naming
@pytest_asyncio.fixture(scope="function")
async def test_workspace(workspace_1: Workspace) -> Workspace:
    """Alias for workspace_1 (convenience)."""
    return workspace_1


@pytest_asyncio.fixture(scope="function")
async def test_workspace2(workspace_2: Workspace) -> Workspace:
    """Alias for workspace_2 (convenience)."""
    return workspace_2


@pytest_asyncio.fixture(scope="function")
async def test_user(test_user_ws1: User) -> User:
    """Alias for test_user_ws1 (convenience)."""
    return test_user_ws1


@pytest_asyncio.fixture(scope="function")
async def test_user2(test_user_ws2: User) -> User:
    """Alias for test_user_ws2 (convenience)."""
    return test_user_ws2


@pytest_asyncio.fixture(scope="function")
async def test_client(sample_client_ws1: Client) -> Client:
    """Alias for sample_client_ws1 (convenience)."""
    return sample_client_ws1


@pytest_asyncio.fixture(scope="function")
async def test_client2(sample_client_ws2: Client) -> Client:
    """Alias for sample_client_ws2 (convenience)."""
    return sample_client_ws2


@pytest_asyncio.fixture(scope="function")
async def auth_headers(workspace_1: Workspace, test_user_ws1: User) -> dict[str, str]:
    """Provide pre-configured auth headers for workspace 1."""
    return get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)


# Helper functions for tests


def get_auth_headers(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    csrf_cookie: str | None = None,
) -> dict[str, str]:
    """
    DEPRECATED: Use get_auth_cookies() instead for JWT authentication.

    This function now generates a JWT token and sets it as a cookie.
    The X-Workspace-ID header is ignored by endpoints (workspace_id comes from JWT).

    Args:
        workspace_id: UUID of the workspace
        user_id: UUID of the user (defaults to predefined test user)
        email: Email of the user
        csrf_cookie: Optional CSRF cookie value to merge with JWT cookie

    Returns:
        Dictionary with cookies containing JWT token (and CSRF if provided)
    """
    from pazpaz.core.security import create_access_token

    # Use predefined test user IDs based on workspace
    if user_id is None:
        if str(workspace_id) == "00000000-0000-0000-0000-000000000001":
            user_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
            email = "test-user-ws1@example.com"
        elif str(workspace_id) == "00000000-0000-0000-0000-000000000002":
            user_id = uuid.UUID("10000000-0000-0000-0000-000000000002")
            email = "test-user-ws2@example.com"
        else:
            user_id = uuid.UUID("10000000-0000-0000-0000-000000000001")

    # Generate JWT token
    jwt_token = create_access_token(
        user_id=user_id,
        workspace_id=workspace_id,
        email=email,
    )

    # Build cookie header (merge JWT and CSRF if provided)
    cookie_parts = [f"access_token={jwt_token}"]
    if csrf_cookie:
        cookie_parts.append(f"csrf_token={csrf_cookie}")

    # Return cookie header format that httpx understands
    return {"Cookie": "; ".join(cookie_parts)}


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(
    db_session: AsyncSession,
    redis_client: redis.Redis,
    workspace_1: Workspace,
    test_user_ws1: User,
) -> AsyncGenerator[AsyncClient]:
    """
    Create an authenticated test HTTP client with JWT cookie.

    This fixture provides a client that simulates a logged-in user with:
    - JWT access token in HttpOnly cookie
    - CSRF token in cookie and header
    - Configured for workspace_1

    Usage:
        async def test_something(authenticated_client):
            response = authenticated_client.get("/api/v1/clients")
            assert response.status_code == 200
    """
    from starlette.middleware.base import BaseHTTPMiddleware

    from pazpaz.core.security import create_access_token
    from pazpaz.middleware.csrf import generate_csrf_token

    # Middleware to inject db_session into request.state for audit middleware
    class DBSessionInjectorMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, db_session):
            super().__init__(app)
            self.db_session = db_session

        async def dispatch(self, request, call_next):
            request.state.db_session = self.db_session
            response = await call_next(request)
            return response

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Add test middleware to inject db_session
    app.add_middleware(DBSessionInjectorMiddleware, db_session=db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Generate JWT token
        jwt_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
        )

        # Generate CSRF token
        csrf_token = await generate_csrf_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        # Set cookies on client
        ac.cookies.set("access_token", jwt_token)
        ac.cookies.set("csrf_token", csrf_token)

        # Add default headers including CSRF
        ac.headers.update(
            {
                "X-CSRF-Token": csrf_token,
                "X-Workspace-ID": str(workspace_1.id),
            }
        )

        yield ac

    # Remove test middleware and clear overrides
    app.user_middleware = [
        m
        for m in app.user_middleware
        if not isinstance(m.cls, type)
        or m.cls.__name__ != "DBSessionInjectorMiddleware"
    ]
    app.middleware_stack = None  # Force rebuild
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def workspace_id(workspace_1: Workspace) -> uuid.UUID:
    """Provide workspace_id for tests."""
    return workspace_1.id


@pytest_asyncio.fixture(scope="function")
async def user_id(test_user_ws1: User) -> uuid.UUID:
    """Provide user_id for tests."""
    return test_user_ws1.id


@pytest_asyncio.fixture(scope="function")
async def client_id(sample_client_ws1: Client) -> uuid.UUID:
    """Provide client_id for tests."""
    return sample_client_ws1.id


async def add_csrf_to_client(
    client: AsyncClient,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    redis_client: redis.Redis,
) -> str:
    """
    Add CSRF token to test client for state-changing requests.

    This helper generates a CSRF token and stores it in Redis.
    Returns the CSRF token value to be used with get_auth_headers().

    Args:
        client: Test client (unused, kept for compatibility)
        workspace_id: Workspace ID for token scoping
        user_id: User ID for token scoping
        redis_client: Redis client for token storage

    Returns:
        CSRF token string

    Example:
        csrf_token = await add_csrf_to_client(
            client, workspace.id, user.id, redis_client
        )
        headers = get_auth_headers(workspace.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        response = await client.post("/api/v1/clients", headers=headers, json=data)
    """
    from pazpaz.middleware.csrf import generate_csrf_token

    # Generate CSRF token
    csrf_token = await generate_csrf_token(
        user_id=user_id,
        workspace_id=workspace_id,
        redis_client=redis_client,
    )

    return csrf_token
