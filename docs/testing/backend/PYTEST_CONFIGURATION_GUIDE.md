# pytest Configuration Guide for PazPaz

## Overview

This guide documents the pytest configuration for the PazPaz backend test suite, including fixture design, database isolation strategies, and troubleshooting guidance.

---

## Configuration Files

### pyproject.toml

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

- **testpaths:** All tests in `tests/` directory
- **pythonpath:** Add `src/` to Python path (import `pazpaz.*` modules)
- **asyncio_mode = "auto":** Automatically detect async tests
- **asyncio_default_fixture_loop_scope = "function":** New event loop per test

---

## Core Fixtures

### Database Engine Fixture

```python
@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """
    Create test database engine with fresh schema per test.

    Setup:
    - Creates async PostgreSQL engine (asyncpg driver)
    - Installs pgcrypto extension for encryption tests
    - Creates encrypt/decrypt functions
    - Creates all SQLAlchemy tables

    Teardown:
    - Drops all tables
    - Disposes engine and connections

    Isolation:
    - Function scope = fresh schema per test
    - NullPool = no connection pooling (test-only)
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        # Install pgcrypto (idempotent)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        # Create encryption functions (idempotent)
        await conn.execute(text("CREATE OR REPLACE FUNCTION encrypt_phi_pgcrypto(...)..."))
        await conn.execute(text("CREATE OR REPLACE FUNCTION decrypt_phi_pgcrypto(...)..."))

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

**Why Function Scope?**
- ✅ Test isolation: Each test gets clean database
- ✅ No shared state between tests
- ✅ Parallel-safe (pytest-xdist compatible)
- ✅ Prevents cascading failures

**Trade-off:**
- Slower execution (~95s vs ~60s with session scope)
- Acceptable for 202 test suite

### Database Session Fixture

```python
@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession]:
    """
    Create database session with automatic transaction rollback.

    Isolation Strategy:
    - Each test runs in isolated transaction
    - Changes rolled back after test
    - No manual cleanup needed
    - No foreign key violations (changes never committed)
    """
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()  # CRITICAL: Rollback all changes
```

**Key Benefits:**
1. **Automatic Cleanup:** `rollback()` discards all changes
2. **No Foreign Key Issues:** Cascade deletes not needed
3. **Fast:** Rollback faster than DELETE statements
4. **Safe:** No risk of orphaned records

**Common Pitfall:**
```python
# ❌ WRONG: Never commit in fixtures (breaks isolation)
async def workspace_1(db_session):
    workspace = Workspace(...)
    db_session.add(workspace)
    await db_session.commit()  # OK for fixtures
    return workspace

# ✅ CORRECT: Commit is fine in fixtures (rolled back at teardown)
# The rollback happens AFTER the test completes
```

### Redis Client Fixture

```python
@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[redis.Redis]:
    """
    Create Redis client for testing.

    Configuration:
    - Uses database 1 (not database 0 for dev)
    - Flushes database before/after each test
    - Loads password from settings
    """
    redis_url = f"redis://:{settings.redis_password}@localhost:6379/1"
    client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    await client.flushdb()  # Clear before test
    yield client
    await client.flushdb()  # Clear after test
    await client.aclose()
```

### HTTP Client Fixture

```python
@pytest_asyncio.fixture(scope="function")
async def client(db_session, redis_client) -> AsyncGenerator[AsyncClient]:
    """
    Create test HTTP client with dependency overrides.

    Setup:
    - Overrides get_db() to use test db_session
    - Overrides get_redis() to use test redis_client
    - Injects db_session into request.state (for audit middleware)

    Teardown:
    - CRITICAL: Removes middleware to prevent state leakage
    - Clears dependency overrides
    """
    class DBSessionInjectorMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, db_session):
            super().__init__(app)
            self.db_session = db_session

        async def dispatch(self, request, call_next):
            request.state.db_session = self.db_session
            return await call_next(request)

    # Override dependencies
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client

    # Add test middleware
    app.add_middleware(DBSessionInjectorMiddleware, db_session=db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # CRITICAL: Clean up middleware and overrides
    app.user_middleware = [
        m for m in app.user_middleware
        if m.cls.__name__ != 'DBSessionInjectorMiddleware'
    ]
    app.middleware_stack = None  # Force rebuild
    app.dependency_overrides.clear()
```

**Why Middleware Cleanup is Critical:**
- FastAPI caches middleware stack
- Without cleanup, next test uses old db_session
- Results in mysterious failures or state leakage

---

## Entity Fixtures

### Workspace Fixtures

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
- **Deterministic UUIDs:** Easier debugging and test readability
- **Function Scope:** Fresh workspace per test (no contamination)
- **Explicit Commit:** Needed to use workspace in test (will be rolled back)

### User Fixtures

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

---

## Authentication Helpers

### get_auth_headers()

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
    from pazpaz.core.security import create_access_token

    # Use predefined test user IDs
    if user_id is None:
        if str(workspace_id) == "00000000-0000-0000-0000-000000000001":
            user_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
        elif str(workspace_id) == "00000000-0000-0000-0000-000000000002":
            user_id = uuid.UUID("10000000-0000-0000-0000-000000000002")

    jwt_token = create_access_token(
        user_id=user_id,
        workspace_id=workspace_id,
        email=email,
    )

    cookie_parts = [f"access_token={jwt_token}"]
    if csrf_cookie:
        cookie_parts.append(f"csrf_token={csrf_cookie}")

    return {"Cookie": "; ".join(cookie_parts)}
```

### add_csrf_to_client()

```python
async def add_csrf_to_client(
    client: AsyncClient,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    redis_client: redis.Redis,
) -> str:
    """
    Generate CSRF token and store in Redis.

    Returns token value to be added to headers.

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

---

## Common Test Patterns

### Pattern 1: Unauthenticated Request Test

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

    # Build headers
    headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    # Make request
    client_data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
    }
    response = await client.post("/api/v1/clients", headers=headers, json=client_data)

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
    headers = get_auth_headers(workspace_1.id)  # Authenticate as workspace_1

    # Try to access workspace_2 client
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

### Parallel Execution (Future)

```bash
# Install pytest-xdist
uv add pytest-xdist

# Run with 4 parallel workers
uv run pytest tests/ -n 4

# Run with auto-detect CPU count
uv run pytest tests/ -n auto

# Distribute by test scope (better for database tests)
uv run pytest tests/ -n 4 --dist loadscope
```

---

## Troubleshooting

### Issue 1: asyncpg.exceptions.UniqueViolationError

**Error:**
```
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "workspaces_pkey"
```

**Cause:**
- Test trying to create workspace with same UUID as previous test
- Rollback not happening correctly

**Solution:**
1. Verify `db_session` fixture has `await session.rollback()` in teardown
2. Ensure test doesn't use `session.close()` instead of rollback
3. Check that workspace fixture uses deterministic UUID

### Issue 2: asyncpg.exceptions.DependentObjectsStillExistError

**Error:**
```
asyncpg.exceptions.DependentObjectsStillExistError: cannot drop table workspaces
```

**Cause:**
- Foreign key constraints preventing table drop
- Manual DROP TABLE without CASCADE

**Solution:**
1. Use `Base.metadata.drop_all()` (handles dependencies)
2. If using manual DROP, add CASCADE: `DROP TABLE workspaces CASCADE`
3. Ensure all foreign key relationships defined in SQLAlchemy models

### Issue 3: asyncpg.exceptions.InternalServerError: tuple concurrently updated

**Error:**
```
asyncpg.exceptions.InternalServerError: tuple concurrently updated
```

**Cause:**
- Multiple tests trying to `CREATE OR REPLACE FUNCTION` simultaneously
- PostgreSQL serializes DDL operations

**Solution:**
1. Use `CREATE OR REPLACE` (already implemented)
2. Use `CREATE IF NOT EXISTS` for extensions
3. Move function creation to session-scoped fixture (if needed)
4. Run tests sequentially: `pytest tests/ -n 0`

### Issue 4: Middleware State Leakage

**Symptoms:**
- Test passes in isolation but fails when run with others
- Mysterious "wrong workspace" or "wrong user" errors
- db_session contains data from previous test

**Cause:**
- Middleware not cleaned up between tests
- FastAPI caches middleware stack

**Solution:**
```python
# In client fixture teardown:
app.user_middleware = [
    m for m in app.user_middleware
    if m.cls.__name__ != 'DBSessionInjectorMiddleware'
]
app.middleware_stack = None  # Force rebuild
app.dependency_overrides.clear()
```

### Issue 5: Redis Connection Errors

**Error:**
```
redis.exceptions.ConnectionError: Error 61 connecting to localhost:6379. Connection refused.
```

**Cause:**
- Redis server not running
- Wrong Redis database or password

**Solution:**
1. Start Redis: `redis-server`
2. Verify connection: `redis-cli ping`
3. Check password in `.env` file
4. Ensure `TEST_REDIS_URL` uses database 1 (not 0)

### Issue 6: pgcrypto Extension Missing

**Error:**
```
psycopg.errors.UndefinedFunction: function encrypt(...) does not exist
```

**Cause:**
- pgcrypto extension not installed
- Functions not created in test database

**Solution:**
1. Verify `test_db_engine` fixture runs `CREATE EXTENSION IF NOT EXISTS pgcrypto`
2. Check `CREATE OR REPLACE FUNCTION` statements executed
3. Ensure test database user has CREATE EXTENSION privilege:
   ```sql
   GRANT CREATE ON DATABASE pazpaz_test TO pazpaz;
   ```

---

## Best Practices

### ✅ DO

1. **Use Function-Scoped Fixtures for Database Tests**
   - Prevents test contamination
   - Ensures clean state per test

2. **Always Rollback Transactions**
   ```python
   async with async_session_maker() as session:
       yield session
       await session.rollback()  # CRITICAL
   ```

3. **Use Deterministic UUIDs in Fixtures**
   ```python
   workspace = Workspace(
       id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
       ...
   )
   ```

4. **Clean Up Middleware and Overrides**
   ```python
   app.user_middleware = [...]
   app.middleware_stack = None
   app.dependency_overrides.clear()
   ```

5. **Use Idempotent Database Setup**
   ```python
   CREATE EXTENSION IF NOT EXISTS pgcrypto;
   CREATE OR REPLACE FUNCTION encrypt_phi_pgcrypto(...);
   ```

### ❌ DON'T

1. **Don't Share Database State Between Tests**
   ```python
   # ❌ WRONG: Session scope leaks state
   @pytest_asyncio.fixture(scope="session")
   async def workspace():
       ...
   ```

2. **Don't Commit in Tests Without Rollback**
   ```python
   # ❌ WRONG: Commits without rollback
   async def test_create_client(db_session):
       client = Client(...)
       db_session.add(client)
       await db_session.commit()  # No rollback = state leakage
   ```

3. **Don't Use Manual Cleanup Instead of Rollback**
   ```python
   # ❌ WRONG: Manual DELETE instead of rollback
   async def test_something(db_session, workspace):
       ...
       await db_session.execute(text("DELETE FROM workspaces"))
       await db_session.commit()
   ```

4. **Don't Mix Production and Test Databases**
   ```python
   # ❌ WRONG: Using production database URL
   TEST_DATABASE_URL = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz"

   # ✅ CORRECT: Use separate test database
   TEST_DATABASE_URL = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz_test"
   ```

5. **Don't Forget to Clean Up Redis**
   ```python
   # ❌ WRONG: No cleanup
   @pytest_asyncio.fixture
   async def redis_client():
       client = redis.from_url(...)
       yield client

   # ✅ CORRECT: Flush database before/after
   @pytest_asyncio.fixture
   async def redis_client():
       client = redis.from_url(...)
       await client.flushdb()
       yield client
       await client.flushdb()
       await client.aclose()
   ```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: pazpaz
          POSTGRES_PASSWORD: pazpaz
          POSTGRES_DB: pazpaz_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: uv sync

      - name: Run tests
        run: uv run pytest tests/ -v --cov=pazpaz --cov-report=xml
        env:
          DATABASE_URL: postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz_test
          REDIS_PASSWORD: ""
          SECRET_KEY: test-secret-key-for-ci-only-32-chars

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

## Performance Benchmarks

### Current Test Suite Metrics (197 tests)

| Metric | Value |
|--------|-------|
| Total Execution Time | 95-98 seconds |
| Per-Test Average | 0.47 seconds |
| Workspace Isolation Tests | 6.2 seconds (16 tests) |
| Encryption Tests | 1.3 seconds (12 tests) |
| Performance Tests | 18 seconds (16 tests) |

### Expected with pytest-xdist (4 workers)

| Metric | Value |
|--------|-------|
| Total Execution Time | 40-50 seconds (60% faster) |
| Per-Test Average | 0.47 seconds (unchanged) |
| Speedup Factor | 1.9-2.4x |

---

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [PazPaz Test Fixture Analysis](/Users/yussieik/Desktop/projects/pazpaz/backend/docs/TEST_FIXTURE_ANALYSIS.md)

---

**Last Updated:** 2025-10-05
**Maintained By:** database-architect
**Version:** 1.0
