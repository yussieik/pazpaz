"""Pytest configuration and fixtures for PazPaz backend tests."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
import redis.asyncio as redis
import structlog
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
from pazpaz.models.session import Session
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace

# Ensure .env file is loaded for tests (if not already set via environment)
# This allows tests to run with: pytest tests/ (without explicit env vars)
if not os.getenv("ENCRYPTION_MASTER_KEY"):
    from dotenv import load_dotenv

    # Load .env from backend directory
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(dotenv_path=env_path)

# Test database URL - use separate test database
# In CI, use DATABASE_URL from environment (already configured correctly)
# Locally, build URL with local credentials
TEST_DATABASE_URL = os.getenv("DATABASE_URL")
if not TEST_DATABASE_URL:
    # Get password from environment (should match running Docker container)
    TEST_DB_PASSWORD = os.getenv(
        "POSTGRES_PASSWORD", "7ZkNSVfvKEbFi2D0uNFoPJzv8sXAYiGaSnXGbRWEoY"
    )
    TEST_DATABASE_URL = (
        f"postgresql+asyncpg://pazpaz:{TEST_DB_PASSWORD}@localhost:5432/pazpaz_test"
    )

# Redis URL - use environment variable if set (for CI), otherwise use local default
TEST_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")


# ============================================================================
# Docker Service Management (Auto-start MinIO and ClamAV for integration tests)
# ============================================================================


def is_service_running(service_name: str) -> bool:
    """
    Check if a docker-compose service is running.

    Args:
        service_name: Name of the service in docker-compose.yml

    Returns:
        True if service is running, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "-q", service_name],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def wait_for_service_health(
    service_name: str, max_wait: int = 120, check_interval: int = 2
) -> bool:
    """
    Wait for a Docker service to become healthy.

    Args:
        service_name: Name of the service in docker-compose.yml
        max_wait: Maximum time to wait in seconds
        check_interval: Interval between health checks in seconds

    Returns:
        True if service is healthy, False if timeout
    """
    start_time = time.time()
    compose_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    while time.time() - start_time < max_wait:
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json", service_name],
                cwd=compose_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                import json

                service_info = json.loads(result.stdout.strip())
                if isinstance(service_info, list) and service_info:
                    service_info = service_info[0]

                health = service_info.get("Health", "")
                state = service_info.get("State", "")

                # Service is healthy if either:
                # 1. Health status is "healthy"
                # 2. State is "running" and no health check defined
                if health == "healthy" or (state == "running" and not health):
                    return True

        except Exception:
            pass

        time.sleep(check_interval)

    return False


def start_docker_service(service_name: str) -> bool:
    """
    Start a docker-compose service and wait for it to be healthy.

    Args:
        service_name: Name of the service in docker-compose.yml

    Returns:
        True if service started successfully, False otherwise
    """
    compose_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    try:
        # Start the service
        result = subprocess.run(
            ["docker", "compose", "up", "-d", service_name],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(f"Failed to start {service_name}: {result.stderr}")
            return False

        # Wait for service to be healthy
        return wait_for_service_health(service_name)

    except Exception as e:
        print(f"Error starting {service_name}: {e}")
        return False


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_services():
    """
    Ensure MinIO and ClamAV services are running before integration tests.

    This fixture automatically:
    1. Checks if services are running
    2. Starts them if not running (using docker-compose up)
    3. Waits for health checks to pass
    4. Provides clear error messages if services can't start

    Note: ClamAV is optional - if it fails to start (e.g., on ARM64 Macs),
    a warning is printed but tests continue. Tests requiring ClamAV will be
    skipped or fail gracefully.

    This runs once per test session and doesn't stop services after tests
    (allows reuse across test runs for faster iteration).

    In CI environments, this fixture skips Docker service management since
    services should be pre-configured (e.g., via GitHub Actions services).
    """
    # Skip Docker service management in CI - services are pre-configured
    if os.getenv("CI") == "true":
        print("ℹ Running in CI environment - skipping Docker service management")
        yield
        return

    required_services = {
        "minio": ("MinIO (S3 storage)", True),  # (description, required)
        "clamav": ("ClamAV (virus scanning)", False),  # Optional on ARM64
    }

    services_started = []

    for service_name, (service_desc, is_required) in required_services.items():
        if is_service_running(service_name):
            print(f"✓ {service_desc} is already running")
            continue

        print(f"⚠ {service_desc} not running, starting it now...")

        if start_docker_service(service_name):
            print(f"✓ {service_desc} started successfully")
            services_started.append(service_name)
        else:
            if is_required:
                pytest.exit(
                    f"Failed to start {service_desc}. "
                    f"Please ensure Docker is running and try:\n"
                    f"  docker-compose up -d {service_name}",
                    returncode=1,
                )
            else:
                print(
                    f"⚠ Warning: {service_desc} failed to start (this is expected "
                    f"on ARM64 Macs). Tests requiring this service may be skipped."
                )

    yield

    # Note: We don't stop services here to allow reuse across test runs
    # Services will be stopped when user runs `docker-compose down`


@pytest.fixture(scope="function", autouse=True)
def configure_structlog_for_tests(caplog):
    """
    Configure structlog to work with pytest's caplog fixture.

    By default, structlog bypasses Python's logging system and writes directly
    to stdout, which prevents caplog from capturing log records. This fixture
    reconfigures structlog for each test to use ProcessorFormatter, which
    integrates properly with Python's logging system and allows caplog to
    capture structured log events.

    The event name (first positional argument to logger.info/warning/etc)
    will be available in record.msg for assertions in tests.
    """
    # Configure structlog to use ProcessorFormatter for test compatibility
    # This makes logs go through Python's logging system so caplog can capture them
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure Python's logging to use ProcessorFormatter
    # This formats the structlog events before caplog captures them
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=structlog.get_config()["processors"],
        processor=structlog.dev.ConsoleRenderer(colors=False),
    )

    # Get the root logger and configure it
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    # Set caplog to capture DEBUG level and above
    caplog.set_level(logging.DEBUG)

    yield

    # Cleanup: remove the handler we added
    root_logger.removeHandler(handler)


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the entire test session.

    This fixture ensures that async tests have a consistent event loop
    throughout the test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Ensure all pending tasks are completed before closing
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass  # Ignore cleanup errors
    finally:
        loop.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_db_engine():
    """
    Create a test database engine once per session.

    PERFORMANCE OPTIMIZATION: Creates tables, extensions, and functions only once
    instead of 304 times. This saves ~10 seconds per test.

    Uses NullPool to avoid connection pooling issues in tests.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # ONE-TIME SETUP: Create all tables and install required extensions
    async with engine.begin() as conn:
        # Install pgcrypto extension for encryption tests
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        # Install citext extension for case-insensitive email comparisons
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext;"))

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
                        RAISE EXCEPTION
                            'Decryption failed (invalid key or corrupted data)';
                END;
                $$ LANGUAGE plpgsql IMMUTABLE STRICT;
            """)
        )

        # Create tables
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # CLEANUP: Drop all tables after entire session with CASCADE
    async with engine.begin() as conn:
        # Get all table names
        result = await conn.execute(
            text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
        )
        tables = [row[0] for row in result.fetchall()]

        # Drop all tables if any exist
        if tables:
            tables_str = ", ".join(tables)
            await conn.execute(text(f"DROP TABLE IF EXISTS {tables_str} CASCADE"))

    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def create_sentinel_workspace(test_db_engine):
    """
    Create sentinel workspace for unauthenticated audit events.

    This workspace (UUID 00000000-0000-0000-0000-000000000000) is used by
    the audit logging system for unauthenticated events like failed login attempts.
    It's created once per session and persists across all tests.
    """
    from pazpaz.services.audit_service import UNAUTHENTICATED_WORKSPACE_ID

    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create sentinel workspace using raw SQL with ON CONFLICT to handle duplicates
    async with test_db_engine.connect() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO workspaces (id, name, is_active, status, created_at, updated_at, storage_used_bytes, storage_quota_bytes)
                VALUES (
                    '{UNAUTHENTICATED_WORKSPACE_ID}',
                    '[Sentinel] Unauthenticated Events',
                    true,
                    'ACTIVE',
                    NOW(),
                    NOW(),
                    0,
                    10737418240
                )
                ON CONFLICT (id) DO NOTHING
            """)
        )
        await conn.commit()

    yield

    # Clean up after session
    async with test_db_engine.connect() as conn:
        await conn.execute(
            text(f"DELETE FROM workspaces WHERE id = '{UNAUTHENTICATED_WORKSPACE_ID}'")
        )
        await conn.commit()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def truncate_tables(test_db_engine, create_sentinel_workspace):
    """
    Truncate all tables before each test for clean state.

    PERFORMANCE OPTIMIZATION: TRUNCATE is ~100x faster than DROP/CREATE tables.
    Using autouse=True ensures this runs before every test automatically.

    Note: Depends on create_sentinel_workspace to ensure sentinel workspace exists.
    """
    yield  # Let the test run first

    # Truncate all tables after test, EXCEPT the sentinel workspace
    async with test_db_engine.connect() as conn:
        from pazpaz.services.audit_service import UNAUTHENTICATED_WORKSPACE_ID

        # Get all table names dynamically
        result = await conn.execute(
            text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
        )
        tables = [row[0] for row in result.fetchall()]

        if tables:
            # Truncate all tables with CASCADE and RESTART IDENTITY
            # But preserve the sentinel workspace
            tables_str = ", ".join(tables)
            await conn.execute(
                text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE")
            )

            # Re-insert sentinel workspace after truncation
            await conn.execute(
                text(f"""
                    INSERT INTO workspaces (id, name, is_active, status, created_at, updated_at, storage_used_bytes, storage_quota_bytes)
                    VALUES (
                        '{UNAUTHENTICATED_WORKSPACE_ID}',
                        '[Sentinel] Unauthenticated Events',
                        true,
                        'ACTIVE',
                        NOW(),
                        NOW(),
                        0,
                        10737418240
                    )
                    ON CONFLICT (id) DO NOTHING
                """)
            )
            await conn.commit()


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


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession]:
    """
    Create a database session for testing.

    Each test gets a fresh session. Tables are truncated by the truncate_tables
    fixture after each test to ensure isolation.
    """
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[redis.Redis]:
    """
    Create a Redis client for testing.

    Uses a separate Redis database (database 1) to avoid conflicts with dev data.
    Flushes the test database before and after each test.

    IMPORTANT: Creates a fresh connection pool for each test to avoid event loop
    binding issues when tests run sequentially in the same session.
    """
    # Use TEST_REDIS_URL from environment (configured at module level, line 59)
    # In CI: redis://localhost:6379/0 (no password)
    # Locally: redis://:<password>@localhost:6379/1
    redis_url = TEST_REDIS_URL

    # Create a NEW connection pool for each test
    # This ensures the connection is bound to the current event loop
    client = redis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        # Disable connection pooling to avoid event loop binding issues
        single_connection_client=True,
    )

    # Clear test database before test
    try:
        await client.flushdb()
    except Exception:
        # If flushdb fails on setup, close client and re-raise
        await client.aclose()
        raise

    yield client

    # Clear test database after test - wrap in try-except to handle event loop closure
    try:
        await client.flushdb()
    except Exception:
        pass  # Ignore flush errors during teardown
    finally:
        # Always close the client
        try:
            await client.aclose()
        except Exception:
            pass  # Ignore close errors during teardown


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

    # Set global Redis client to our test client to ensure middleware uses it
    import pazpaz.core.redis

    pazpaz.core.redis._redis_client = redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Clear middleware stack before adding new middleware
    # This allows us to modify middleware even after app startup
    app.middleware_stack = None
    app.user_middleware = [
        m
        for m in app.user_middleware
        if not isinstance(m.cls, type)
        or m.cls.__name__ != "DBSessionInjectorMiddleware"
    ]

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

    # Set global Redis client to our test client to ensure middleware uses it
    import pazpaz.core.redis

    pazpaz.core.redis._redis_client = redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Add CSRF token to client
        csrf_token = await add_csrf_to_client(
            ac, workspace_1.id, test_user_ws1.id, redis_client
        )
        # Set CSRF cookie and default header on client
        ac.cookies.set("csrf_token", csrf_token)
        ac.headers["X-CSRF-Token"] = csrf_token
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def workspace_1(db_session: AsyncSession) -> Workspace:
    """
    Create a test workspace (workspace 1).

    This represents a therapist's workspace for testing.
    Uses merge() to handle case where workspace already exists from previous test.
    """
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test Workspace 1",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,  # 10 GB (explicit default)
        storage_used_bytes=0,  # Explicitly set to 0
        timezone="UTC",  # Default timezone for tests
    )
    workspace = await db_session.merge(workspace)
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
    user = await db_session.merge(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture(scope="function")
async def workspace_2(db_session: AsyncSession) -> Workspace:
    """
    Create a second test workspace (workspace 2).

    Used to test workspace isolation - data should not leak between workspaces.
    Uses merge() to handle case where workspace already exists from previous test.
    """
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        name="Test Workspace 2",
    )
    workspace = await db_session.merge(workspace)
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
    user = await db_session.merge(user)
    await db_session.commit()
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

    # Set global Redis client to our test client to ensure middleware uses it
    import pazpaz.core.redis

    pazpaz.core.redis._redis_client = redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Clear middleware stack before adding new middleware
    # This allows us to modify middleware even after app startup
    app.middleware_stack = None
    app.user_middleware = [
        m
        for m in app.user_middleware
        if not isinstance(m.cls, type)
        or m.cls.__name__ != "DBSessionInjectorMiddleware"
    ]

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
