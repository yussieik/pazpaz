# PazPaz Backend Testing Guide

**Last Updated:** 2025-10-20
**Status:** Production Guidelines
**Test Suite:** 916 tests (100% passing)

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [pytest Configuration](#pytest-configuration)
4. [Test Fixtures](#test-fixtures)
5. [Common Test Patterns](#common-test-patterns)
6. [Running Tests](#running-tests)
7. [Authentication & CSRF](#authentication--csrf)
8. [Workspace Isolation Testing](#workspace-isolation-testing)
9. [Performance Testing](#performance-testing)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)

---

## Overview

The PazPaz backend test suite uses pytest with async support for comprehensive API and model testing. All tests run against a dedicated test database (`pazpaz_test`) with automatic table truncation between tests for isolation.

**Key Technologies:**
- **pytest** (8.4.2) - Test framework
- **pytest-asyncio** (1.2.0) - Async test support
- **pytest-xdist** (3.8.0) - Parallel test execution
- **httpx** - Async HTTP client for API tests
- **SQLAlchemy** - Database ORM with async support

**Test Database:**
- Database: `pazpaz_test`
- Connection: `postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz_test`
- Redis: `redis://localhost:6379/1` (database 1 for tests)

---

## Quick Start

### Prerequisites

1. PostgreSQL 16 running with `pazpaz_test` database created
2. Redis running locally
3. Backend dependencies installed: `uv sync`
4. `.env` file with encryption keys (auto-loaded by conftest.py)

### Running Tests

```bash
# Run all tests
cd /Users/yussieik/Desktop/projects/pazpaz/backend
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_api/test_sessions.py -v

# Run specific test
uv run pytest tests/test_api/test_sessions.py::test_create_session -v

# Run tests in parallel (4 workers)
uv run pytest tests/ -n 4

# Run with coverage report
uv run pytest tests/ --cov=pazpaz --cov-report=term-missing
```

---

## pytest Configuration

### pyproject.toml Settings

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
markers = [
    "performance: marks tests as performance tests (run with: pytest -m performance)",
]
```

**Key Settings:**
- **asyncio_mode = "auto":** Automatically detects async tests
- **asyncio_default_fixture_loop_scope = "function":** Fresh event loop per test
- **pythonpath = ["src"]:** Allows importing from `pazpaz.*`

### conftest.py Architecture

The test infrastructure uses **session-scoped database setup** with **function-scoped table truncation** for optimal performance:

**Session-Scoped (once per test run):**
- Database engine creation
- pgcrypto extension installation
- Table creation
- Encryption function setup

**Function-Scoped (per test):**
- Table truncation (TRUNCATE CASCADE)
- Database sessions
- Redis client (with flushdb)
- HTTP test client
- Entity fixtures (workspaces, users, clients)

---

## Test Fixtures

### Core Infrastructure Fixtures

#### test_db_engine (session scope)

Creates database engine once per test session with all tables and extensions:

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_db_engine():
    """
    Create test database engine once per session.

    Sets up:
    - PostgreSQL async connection (asyncpg)
    - pgcrypto extension
    - Encryption functions (encrypt_phi_pgcrypto, decrypt_phi_pgcrypto)
    - All SQLAlchemy tables
    """
    engine = create_async_engine(
        "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz_test",
        echo=False,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup after all tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

#### truncate_tables (function scope, autouse)

Automatically truncates all tables after each test for clean state:

```python
@pytest_asyncio.fixture(scope="function", autouse=True)
async def truncate_tables(test_db_engine):
    """
    Truncate all tables after each test.

    PERFORMANCE: TRUNCATE is ~100x faster than DROP/CREATE.
    Uses RESTART IDENTITY CASCADE for complete cleanup.
    """
    yield  # Run test first

    async with test_db_engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
        )
        tables = [row[0] for row in result.fetchall()]

        if tables:
            tables_str = ", ".join(tables)
            await conn.execute(
                text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE")
            )
            await conn.commit()
```

#### db_session (function scope)

Provides database session for each test:

```python
@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession]:
    """Create database session for testing."""
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
```

**Note:** Tables are truncated by `truncate_tables` fixture, so no manual cleanup needed.

#### redis_client (function scope)

Provides Redis client with automatic database flushing:

```python
@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[redis.Redis]:
    """
    Create Redis client for testing.

    Uses database 1 (separate from dev database 0).
    Flushes before and after each test.
    """
    redis_url = "redis://:{password}@localhost:6379/1"
    client = redis.from_url(redis_url, decode_responses=True)

    await client.flushdb()  # Clean before test
    yield client
    await client.flushdb()  # Clean after test
    await client.aclose()
```

#### client (function scope)

Provides HTTP test client with dependency overrides:

```python
@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession,
    redis_client: redis.Redis
) -> AsyncGenerator[AsyncClient]:
    """
    Create test HTTP client with overrides.

    Injects test database session and Redis client.
    Adds middleware for audit logging support.
    """
    # Override dependencies
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client

    # Add test middleware
    app.add_middleware(DBSessionInjectorMiddleware, db_session=db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup
    app.user_middleware = [
        m for m in app.user_middleware
        if m.cls.__name__ != 'DBSessionInjectorMiddleware'
    ]
    app.middleware_stack = None
    app.dependency_overrides.clear()
```

### Entity Fixtures

#### Workspaces

```python
@pytest_asyncio.fixture(scope="function")
async def workspace_1(db_session: AsyncSession) -> Workspace:
    """Test workspace with deterministic UUID."""
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test Workspace 1",
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace

@pytest_asyncio.fixture(scope="function")
async def workspace_2(db_session: AsyncSession) -> Workspace:
    """Second workspace for isolation testing."""
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        name="Test Workspace 2",
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace
```

**Design Decisions:**
- Deterministic UUIDs (`00000000-...-01`, `00000000-...-02`) for debugging
- Function scope for test isolation
- Explicit commit for use in tests (cleaned up by truncate_tables)

#### Users

```python
@pytest_asyncio.fixture(scope="function")
async def test_user_ws1(db_session: AsyncSession, workspace_1: Workspace) -> User:
    """Test user in workspace 1."""
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
```

**UUID Pattern:**
- Workspaces: `00000000-0000-0000-0000-00000000000X`
- Users: `10000000-0000-0000-0000-00000000000X`
- Easy to distinguish entity types by UUID prefix

#### Clients

```python
@pytest_asyncio.fixture(scope="function")
async def sample_client_ws1(
    db_session: AsyncSession,
    workspace_1: Workspace
) -> Client:
    """Sample client in workspace 1."""
    client = Client(
        workspace_id=workspace_1.id,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        consent_status=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client
```

---

## Common Test Patterns

### Pattern 1: Unauthenticated Request (Expect 401)

```python
async def test_cannot_list_clients_without_jwt(client):
    """Test that unauthenticated requests are rejected."""
    response = await client.get("/api/v1/clients")
    assert response.status_code == 401
    assert "detail" in response.json()
```

### Pattern 2: Authenticated GET Request

```python
async def test_list_clients(client, workspace_1, sample_client_ws1):
    """Test listing clients in workspace."""
    headers = get_auth_headers(workspace_1.id)
    response = await client.get("/api/v1/clients", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(sample_client_ws1.id)
```

### Pattern 3: Authenticated POST Request (with CSRF)

```python
async def test_create_client(
    client,
    workspace_1,
    test_user_ws1,
    redis_client
):
    """Test creating a new client."""
    # Generate CSRF token
    csrf_token = await add_csrf_to_client(
        client, workspace_1.id, test_user_ws1.id, redis_client
    )

    # Build headers with JWT and CSRF
    headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    # Make request
    client_data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
    }
    response = await client.post(
        "/api/v1/clients",
        headers=headers,
        json=client_data
    )

    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
```

### Pattern 4: Workspace Isolation Test

```python
async def test_cannot_access_other_workspace_client(
    client,
    workspace_1,
    workspace_2,
    sample_client_ws2,  # Client in workspace_2
):
    """Test that workspace_1 cannot access workspace_2 client."""
    headers = get_auth_headers(workspace_1.id)

    # Try to access workspace_2 client with workspace_1 auth
    response = await client.get(
        f"/api/v1/clients/{sample_client_ws2.id}",
        headers=headers
    )

    assert response.status_code == 404  # Not found (workspace isolation)
```

### Pattern 5: Database-Only Test (No HTTP)

```python
async def test_client_creation(db_session, workspace_1):
    """Test client model creation (no API)."""
    client = Client(
        workspace_id=workspace_1.id,
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    assert client.id is not None
    assert client.workspace_id == workspace_1.id
    assert client.created_at is not None
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_workspace_isolation.py

# Run specific test
uv run pytest tests/test_workspace_isolation.py::TestClientWorkspaceIsolation::test_cannot_access_client_from_different_workspace

# Run with verbose output
uv run pytest tests/ -v

# Run with short traceback
uv run pytest tests/ --tb=short

# Run quietly (minimal output)
uv run pytest tests/ -q

# Run performance tests only
uv run pytest tests/ -m performance

# Skip performance tests
uv run pytest tests/ -m "not performance"
```

### Coverage Commands

```bash
# Run with coverage report
uv run pytest tests/ --cov=pazpaz --cov-report=term-missing

# Generate HTML coverage report
uv run pytest tests/ --cov=pazpaz --cov-report=html

# Check coverage threshold (fail if <80%)
uv run pytest tests/ --cov=pazpaz --cov-fail-under=80
```

### Debugging Commands

```bash
# Stop on first failure
uv run pytest tests/ -x

# Drop into debugger on failure
uv run pytest tests/ --pdb

# Show print statements
uv run pytest tests/ -s

# Show local variables in traceback
uv run pytest tests/ -l

# Re-run failed tests
uv run pytest tests/ --lf

# Run failed tests first, then all
uv run pytest tests/ --ff
```

### Parallel Execution

```bash
# Run with 4 parallel workers (pytest-xdist)
uv run pytest tests/ -n 4

# Run with auto-detect CPU count
uv run pytest tests/ -n auto

# Distribute by test scope (better for database tests)
uv run pytest tests/ -n 4 --dist loadscope
```

**Performance:**
- Sequential: ~95 seconds for 916 tests
- Parallel (4 workers): ~40-50 seconds (60% faster)

---

## Authentication & CSRF

### Helper Functions

#### get_auth_headers()

Generates JWT authentication headers for tests:

```python
def get_auth_headers(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    csrf_cookie: str | None = None
) -> dict[str, str]:
    """
    Generate JWT authentication headers for tests.

    Returns Cookie header with access_token (and optional CSRF token).

    Usage:
        headers = get_auth_headers(workspace_1.id)
        response = await client.get("/api/v1/clients", headers=headers)
    """
    jwt_token = create_access_token(
        user_id=user_id or get_default_user_id(workspace_id),
        workspace_id=workspace_id,
        email=email,
    )

    cookie_parts = [f"access_token={jwt_token}"]
    if csrf_cookie:
        cookie_parts.append(f"csrf_token={csrf_cookie}")

    return {"Cookie": "; ".join(cookie_parts)}
```

#### add_csrf_to_client()

Generates CSRF token and returns it for use with headers:

```python
async def add_csrf_to_client(
    client: AsyncClient,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    redis_client: redis.Redis,
) -> str:
    """
    Generate CSRF token and store in Redis.

    Returns token string to be added to headers.

    Usage:
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        response = await client.post("/api/v1/clients", headers=headers, json=data)
    """
    from pazpaz.middleware.csrf import generate_csrf_token

    csrf_token = await generate_csrf_token(
        user_id=user_id,
        workspace_id=workspace_id,
        redis_client=redis_client,
    )
    return csrf_token
```

### CSRF Test Requirements

**Which Methods Need CSRF?**
- POST - needs CSRF
- PUT - needs CSRF
- PATCH - needs CSRF
- DELETE - needs CSRF
- GET - **no** CSRF needed
- HEAD - **no** CSRF needed
- OPTIONS - **no** CSRF needed

**Exempted Endpoints:**
- `/api/v1/auth/magic-link` - Entry point for authentication
- `/docs`, `/redoc`, `/openapi.json` - Documentation endpoints

### Complete CSRF Example

```python
async def test_create_with_csrf(
    client,
    workspace_1,
    test_user_ws1,
    redis_client
):
    """Complete example with CSRF protection."""
    # 1. Generate CSRF token
    csrf_token = await add_csrf_to_client(
        client,
        workspace_1.id,
        test_user_ws1.id,
        redis_client
    )

    # 2. Build headers with JWT and CSRF
    headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    # 3. Make request
    response = await client.post(
        "/api/v1/clients",
        headers=headers,
        json={"first_name": "John", "last_name": "Doe"}
    )

    assert response.status_code == 201
```

---

## Workspace Isolation Testing

All tests must verify workspace isolation for multi-tenant security.

### Testing Cross-Workspace Access (Must Return 404)

```python
async def test_cannot_access_other_workspace(
    client,
    workspace_1,
    workspace_2,
    sample_client_ws2
):
    """Workspace 1 user cannot access workspace 2 client."""
    headers = get_auth_headers(workspace_1.id)

    response = await client.get(
        f"/api/v1/clients/{sample_client_ws2.id}",
        headers=headers
    )

    assert response.status_code == 404
```

### Testing List Queries (Must Filter by Workspace)

```python
async def test_list_only_shows_own_workspace(
    client,
    workspace_1,
    workspace_2,
    sample_client_ws1,
    sample_client_ws2
):
    """List endpoint only shows workspace 1 clients."""
    headers = get_auth_headers(workspace_1.id)

    response = await client.get("/api/v1/clients", headers=headers)

    assert response.status_code == 200
    clients = response.json()

    # Should only see workspace_1 client
    assert len(clients) == 1
    assert clients[0]["id"] == str(sample_client_ws1.id)
```

### Testing Update/Delete Isolation

```python
async def test_cannot_update_other_workspace(
    client,
    workspace_1,
    workspace_2,
    sample_client_ws2,
    test_user_ws1,
    redis_client
):
    """Cannot update client in different workspace."""
    csrf_token = await add_csrf_to_client(
        client, workspace_1.id, test_user_ws1.id, redis_client
    )

    headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    response = await client.put(
        f"/api/v1/clients/{sample_client_ws2.id}",
        headers=headers,
        json={"first_name": "Hacked"}
    )

    assert response.status_code == 404
```

---

## Performance Testing

Performance tests are marked with `@pytest.mark.performance` and can be run separately.

### Running Performance Tests

```bash
# Run only performance tests
uv run pytest tests/ -m performance -v

# Skip performance tests
uv run pytest tests/ -m "not performance"
```

### Performance Test Example

```python
import pytest
import statistics
import time

@pytest.mark.performance
async def test_calendar_view_performance(client, workspace_1):
    """Calendar view endpoint must meet p95 <150ms target."""
    headers = get_auth_headers(workspace_1.id)

    response_times = []

    for _ in range(100):
        start = time.time()
        response = await client.get(
            "/api/v1/appointments",
            headers=headers,
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"}
        )
        response_times.append((time.time() - start) * 1000)
        assert response.status_code == 200

    p95 = statistics.quantiles(response_times, n=20)[18]  # 95th percentile

    assert p95 < 150, f"p95 response time {p95:.2f}ms exceeds 150ms target"
```

### Current Performance Benchmarks

| Endpoint | p95 Target | p95 Actual | Status |
|----------|-----------|-----------|--------|
| `GET /clients` | <150ms | 45ms | ✅ 3.3x faster |
| `GET /appointments` | <150ms | 50ms | ✅ 3x faster |
| `POST /clients` | <150ms | 55ms | ✅ 2.7x faster |
| `POST /sessions` | <150ms | 70ms | ✅ 2.1x faster |

---

## Troubleshooting

### Issue 1: Test Database Not Found

**Error:**
```
asyncpg.exceptions.InvalidCatalogNameError: database "pazpaz_test" does not exist
```

**Solution:**
```bash
# Create test database
docker-compose exec -T db psql -U pazpaz -c "CREATE DATABASE pazpaz_test;"

# Or connect to PostgreSQL and create manually:
psql -U pazpaz -h localhost
CREATE DATABASE pazpaz_test;
```

### Issue 2: Encryption Key Not Found

**Error:**
```
KeyNotFoundError: Encryption key not found
```

**Solution:**
The `.env` file should be auto-loaded by conftest.py, but verify:

1. Check `.env` file exists in `/backend/.env`
2. Verify `ENCRYPTION_MASTER_KEY` is set
3. Run tests from backend directory: `cd backend && uv run pytest tests/`

### Issue 3: Redis Connection Error

**Error:**
```
redis.exceptions.ConnectionError: Error 61 connecting to localhost:6379
```

**Solution:**
```bash
# Start Redis
redis-server

# Verify connection
redis-cli ping  # Should respond: PONG

# Check password in .env file
cat .env | grep REDIS_PASSWORD
```

### Issue 4: Tests Hanging or Slow

**Possible Causes:**
1. Database connection pool exhausted
2. Redis connections not closed
3. Async fixtures not properly cleaned up

**Solution:**
```bash
# Run with verbose logging to identify hanging test
uv run pytest tests/ -v -s

# Run specific test file to isolate issue
uv run pytest tests/test_sessions.py -v

# Check for leaked connections
docker-compose exec db psql -U pazpaz -c "SELECT count(*) FROM pg_stat_activity WHERE datname='pazpaz_test';"
```

### Issue 5: Middleware State Leakage

**Symptoms:**
- Test passes in isolation but fails when run with others
- "Wrong workspace" or "wrong user" errors
- db_session contains data from previous test

**Solution:**
Verify `client` fixture cleanup (already implemented in conftest.py):

```python
# Cleanup in client fixture teardown
app.user_middleware = [
    m for m in app.user_middleware
    if m.cls.__name__ != 'DBSessionInjectorMiddleware'
]
app.middleware_stack = None  # Force rebuild
app.dependency_overrides.clear()
```

---

## Best Practices

### ✅ DO

1. **Use Function-Scoped Fixtures for Database Tests**
   - Prevents test contamination
   - Ensures clean state per test

2. **Always Test Workspace Isolation**
   ```python
   async def test_workspace_isolation(client, workspace_1, resource_in_workspace_2):
       headers = get_auth_headers(workspace_1.id)
       response = await client.get(f"/api/v1/resource/{resource_in_workspace_2.id}", headers=headers)
       assert response.status_code == 404
   ```

3. **Use Deterministic UUIDs in Fixtures**
   ```python
   workspace = Workspace(
       id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
       name="Test Workspace 1"
   )
   ```

4. **Clean Up Middleware and Overrides**
   ```python
   # Already handled by conftest.py client fixture
   app.dependency_overrides.clear()
   ```

5. **Test Both Success and Error Cases**
   ```python
   async def test_create_success(...):
       # Test successful creation

   async def test_create_invalid_data(...):
       # Test validation errors

   async def test_create_unauthorized(...):
       # Test auth errors
   ```

### ❌ DON'T

1. **Don't Share Database State Between Tests**
   ```python
   # ❌ WRONG: Session scope leaks state
   @pytest_asyncio.fixture(scope="session")
   async def workspace():
       ...
   ```

2. **Don't Forget CSRF for State-Changing Requests**
   ```python
   # ❌ WRONG: Missing CSRF token
   async def test_create_client(client, workspace_1):
       headers = get_auth_headers(workspace_1.id)
       response = await client.post("/api/v1/clients", headers=headers, json=data)
       # Will fail with 403 Forbidden
   ```

3. **Don't Use Manual Cleanup Instead of Fixtures**
   ```python
   # ❌ WRONG: Manual DELETE instead of truncate_tables
   async def test_something(db_session):
       ...
       await db_session.execute(text("DELETE FROM clients"))
   ```

4. **Don't Mix Production and Test Databases**
   ```python
   # ❌ WRONG: Using production database URL
   TEST_DATABASE_URL = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz"

   # ✅ CORRECT: Use separate test database
   TEST_DATABASE_URL = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz_test"
   ```

5. **Don't Forget to Test Performance**
   ```python
   # ✅ CORRECT: Add performance tests for critical endpoints
   @pytest.mark.performance
   async def test_calendar_performance(...):
       # Verify p95 < 150ms target
   ```

---

## Test Suite Statistics

**Current Status (2025-10-20):**
- Total Tests: 916
- Passing: 916 (100%)
- Failed: 0
- Execution Time: ~95 seconds (sequential)
- Execution Time: ~40 seconds (parallel, 4 workers)

**Test Breakdown:**
- Session API: 78 tests
- Appointment API: 84 tests
- Client API: 35 tests
- Authentication: 13 tests
- Workspace Isolation: 16 tests
- CSRF Protection: 18 tests
- Encryption: 27 tests
- Audit Logging: 7 tests
- Performance: 17 tests
- Security: 50+ tests
- Other: 571 tests

**Coverage:**
- Overall: ~90% code coverage
- Critical paths: 100% coverage
- Performance benchmarks: All passing (<150ms p95)

---

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [CSRF Test Guide](./CSRF_TEST_GUIDE.md)
- [X-Forwarded-For Security Test Report](../../reports/qa/X_FORWARDED_FOR_SECURITY_TEST_REPORT.md)

---

**Last Updated:** 2025-10-20
**Maintained By:** Backend QA Specialist
**Version:** 2.0
**Status:** Production Guidelines
