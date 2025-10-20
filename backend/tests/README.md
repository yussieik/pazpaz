# PazPaz Backend Test Suite

## Overview

This document describes the organization and structure of the PazPaz backend test suite. The test suite is organized to provide comprehensive coverage while maintaining clear separation between test types and domains.

**Test Statistics:**
- Total Tests: 1099
- Test Files: 53
- Conftest Files: 2 (root + security-specific)

## Directory Structure

```
backend/tests/
├── conftest.py                 # Root conftest with shared fixtures (993 lines)
├── README.md                   # This file
│
├── integration/                # Integration tests (API endpoints, full stack)
│   ├── test_authentication_requirements.py  # Cross-cutting auth requirement tests
│   └── api/                    # API integration tests
│       ├── test_appointments.py     # Appointment CRUD and conflict detection
│       ├── test_auth.py             # Magic link and JWT authentication
│       ├── test_client_attachments.py  # Client file attachments
│       ├── test_clients.py          # Client CRUD operations
│       ├── test_session_attachments.py  # Session file attachments
│       ├── test_sessions.py         # Session CRUD operations
│       └── test_sessions_search.py  # Session search functionality
│
├── unit/                       # Unit tests (isolated component testing)
│   ├── core/                   # Core utilities and services unit tests
│   ├── models/                 # Database model unit tests
│   │   └── test_session.py
│   ├── services/               # Service layer unit tests
│   └── utils/                  # Utility function unit tests
│
├── security/                   # Security-focused tests
│   ├── conftest.py            # Security-specific fixtures (254 lines)
│   ├── authentication/        # Authentication & authorization tests
│   │   ├── test_argon2_password_security.py
│   │   ├── test_authentication_security.py
│   │   ├── test_jwt_expiration.py
│   │   ├── test_jwt_hardening.py
│   │   ├── test_magic_link_security.py
│   │   ├── test_session_idle_timeout.py
│   │   └── test_totp_2fa.py
│   ├── encryption/            # Encryption & PHI protection tests
│   │   ├── test_encryption_security.py
│   │   ├── test_key_entropy_validation.py
│   │   ├── test_production_key_enforcement.py
│   │   └── test_storage_encryption.py
│   ├── input_validation/      # Input validation & sanitization tests
│   │   ├── test_file_sanitization.py
│   │   ├── test_file_upload_security.py
│   │   ├── test_file_validation.py
│   │   └── test_input_validation.py
│   ├── middleware/            # Security middleware tests
│   │   ├── test_content_type.py
│   │   ├── test_csp_nonce.py
│   │   ├── test_rate_limit_security.py
│   │   ├── test_request_size_limit.py
│   │   └── test_security_headers.py
│   └── storage/               # Storage security tests
│       ├── test_malware_scanner.py
│       ├── test_s3_endpoint_validation.py
│       ├── test_storage_quota.py
│       └── test_storage_quota_race_condition.py
│
└── test_performance.py        # Performance benchmark tests
```

## Conftest Organization

### Root Conftest (`tests/conftest.py`)

**Purpose:** Provides shared fixtures for all tests across the entire test suite.

**Key Fixtures:**

**Database & Session Management:**
- `event_loop` (session) - Event loop for entire test session
- `test_db_engine` (session) - Test database engine with NullPool
- `create_sentinel_workspace` (session, autouse) - Creates sentinel workspace for unauthenticated events
- `truncate_tables` (function, autouse) - Truncates tables after each test (100x faster than DROP/CREATE)
- `db` (function) - Database session alias (matches service function parameter names)
- `db_session` (function) - Database session for testing

**Redis & Caching:**
- `redis_client` (function) - Redis client for testing (database 1)

**HTTP Clients:**
- `client` (function) - Test HTTP client with dependency overrides
- `client_with_csrf` (function) - Test HTTP client pre-configured with CSRF token
- `authenticated_client` (function) - Fully authenticated client with JWT + CSRF

**Test Data - Workspaces:**
- `workspace_1` (function) - Test workspace 1 (UUID: 00000000-0000-0000-0000-000000000001)
- `workspace_2` (function) - Test workspace 2 (UUID: 00000000-0000-0000-0000-000000000002)
- `test_workspace` (function) - Alias for workspace_1
- `test_workspace2` (function) - Alias for workspace_2

**Test Data - Users:**
- `test_user_ws1` (function) - Test user in workspace 1 (UUID: 10000000-0000-0000-0000-000000000001)
- `test_user_ws2` (function) - Test user in workspace 2 (UUID: 10000000-0000-0000-0000-000000000002)
- `test_user` (function) - Alias for test_user_ws1
- `test_user2` (function) - Alias for test_user_ws2

**Test Data - Clients:**
- `sample_client_ws1` (function) - Sample client in workspace 1
- `sample_client_ws2` (function) - Sample client in workspace 2
- `test_client` (function) - Alias for sample_client_ws1
- `test_client2` (function) - Alias for sample_client_ws2

**Test Data - Appointments:**
- `sample_appointment_ws1` (function) - Sample appointment in workspace 1
- `sample_appointment_ws2` (function) - Sample appointment in workspace 2
- `cancelled_appointment_ws1` (function) - Cancelled appointment in workspace 1

**Test Data - Sessions:**
- `test_session` (function) - Test session in workspace 1
- `test_session2` (function) - Test session in workspace 2

**Convenience Fixtures:**
- `auth_headers` (function) - Pre-configured auth headers for workspace 1
- `workspace_id` (function) - Workspace ID for tests
- `user_id` (function) - User ID for tests
- `client_id` (function) - Client ID for tests

**Helper Functions:**
- `get_auth_headers()` - Generate JWT auth headers with cookies
- `add_csrf_to_client()` - Add CSRF token to test client

### Security Conftest (`tests/security/conftest.py`)

**Purpose:** Provides security-specific fixtures to prevent test failures from rate limiting and ensure proper security test isolation.

**Key Fixtures:**

**Rate Limiting Management:**
- `clear_rate_limits` (autouse) - Clears all rate limit keys before/after each test
- `rate_limit_delay` - Adds 50ms delay to avoid rate limit bursts
- `mock_rate_limit_bypass` - Bypasses rate limiting for tests requiring many requests

**Security Test Data:**
- `clear_brute_force_counter` - Clears brute force detection counter
- `unauthenticated_workspace` - Creates sentinel workspace for unauthenticated events

**Failure Simulation:**
- `mock_redis_failure` - Mocks Redis to simulate connection failures

**Nuclear Options:**
- `clear_all_test_data` - Clears ALL test data from Redis and database (use sparingly)

**Encryption Key Management:**
- `init_encryption_key_registry` (autouse) - Initializes encryption key registry with v1 key

## Running Tests

### Run All Tests

```bash
# From backend directory
uv run pytest tests/

# With coverage
uv run pytest tests/ --cov=src/pazpaz --cov-report=html

# Parallel execution (faster)
uv run pytest tests/ -n auto
```

### Run Tests by Category

```bash
# Integration tests (API endpoints, full stack)
uv run pytest tests/integration/

# Unit tests (isolated components)
uv run pytest tests/unit/

# Security tests
uv run pytest tests/security/

# Specific security domains
uv run pytest tests/security/authentication/
uv run pytest tests/security/encryption/
uv run pytest tests/security/input_validation/
uv run pytest tests/security/middleware/
uv run pytest tests/security/storage/
```

### Run Tests by Mark

```bash
# Performance tests only
uv run pytest -m performance

# Tests that don't require database
uv run pytest -m no_db

# Quarterly disaster recovery drills
uv run pytest -m quarterly_drill

# All tests EXCEPT performance tests
uv run pytest -m "not performance"
```

### Run Specific Test Files

```bash
# Single file
uv run pytest tests/integration/api/test_auth.py

# Multiple files
uv run pytest tests/security/authentication/test_jwt_hardening.py tests/security/authentication/test_magic_link_security.py
```

### Run Specific Test Classes or Functions

```bash
# Single test class
uv run pytest tests/security/authentication/test_jwt_hardening.py::TestJWTAlgorithmValidation

# Single test function
uv run pytest tests/security/authentication/test_jwt_hardening.py::TestJWTAlgorithmValidation::test_rejects_algorithm_none

# Pattern matching
uv run pytest tests/ -k "jwt"
uv run pytest tests/ -k "test_encryption"
```

### Useful Pytest Options

```bash
# Show print statements
uv run pytest tests/ -s

# Stop on first failure
uv run pytest tests/ -x

# Show local variables on failures
uv run pytest tests/ -l

# Run only failed tests from last run
uv run pytest tests/ --lf

# Run failed tests first, then rest
uv run pytest tests/ --ff

# Verbose output with test names
uv run pytest tests/ -v

# Very verbose (show full diffs)
uv run pytest tests/ -vv

# Show test duration
uv run pytest tests/ --durations=10

# Collect tests without running
uv run pytest tests/ --collect-only
```

## Test Discovery

Pytest automatically discovers tests based on these naming conventions:

**Test Files:**
- Must start with `test_` or end with `_test.py`
- Example: `test_auth.py`, `test_encryption.py`

**Test Functions:**
- Must start with `test_`
- Example: `def test_login()`, `async def test_create_client()`

**Test Classes:**
- Must start with `Test` (no `__init__` method)
- Example: `class TestAuthentication:`, `class TestJWTHardening:`

## Pytest Configuration

Configuration is defined in `/backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
markers = [
    "performance: marks tests as performance tests",
    "no_db: marks tests that don't require database access",
    "quarterly_drill: marks tests for quarterly disaster recovery drills",
]
```

**Key Settings:**
- `testpaths` - Where pytest looks for tests
- `pythonpath` - Adds src/ to Python path (allows `from pazpaz.x import y`)
- `asyncio_mode = "auto"` - Automatically detects async tests
- `asyncio_default_fixture_loop_scope = "function"` - One event loop per test function

## Performance Optimizations

### Session-Scoped Database Setup

The test suite uses **session-scoped database setup** to create tables only once:

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_db_engine():
    """Create database engine and tables ONCE per session."""
    # Creates all tables, extensions, functions
    # Reused across all 1106 tests
    # Saves ~10 seconds per test
```

### Table Truncation (100x Faster)

Instead of DROP/CREATE tables after each test, we use **TRUNCATE**:

```python
@pytest_asyncio.fixture(scope="function", autouse=True)
async def truncate_tables(test_db_engine, create_sentinel_workspace):
    """Truncate all tables after each test (autouse=True)."""
    yield  # Let test run first
    # TRUNCATE is ~100x faster than DROP/CREATE
    await conn.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE"))
```

**Benefits:**
- 100x faster than DROP/CREATE
- Preserves table structure
- Resets AUTO_INCREMENT counters
- Runs automatically via `autouse=True`

### Redis Connection Per Test

To avoid event loop binding issues, Redis clients are created fresh per test:

```python
@pytest_asyncio.fixture(scope="function")
async def redis_client():
    """Create fresh Redis client for each test (single_connection_client=True)."""
    client = redis.from_url(redis_url, single_connection_client=True)
    # ...
```

## Workspace Isolation Testing

**CRITICAL:** All tests must verify workspace isolation. Use the provided fixtures:

```python
async def test_workspace_isolation(
    authenticated_client,
    workspace_1,
    workspace_2,
    sample_client_ws1,
    sample_client_ws2
):
    """Verify client in workspace_1 cannot access data from workspace_2."""
    # Make request to workspace_1
    response = await authenticated_client.get(f"/api/v1/clients/{sample_client_ws2.id}")

    # Should return 404 (not 403) to prevent info leakage
    assert response.status_code == 404
```

**Testing Checklist:**
- [ ] Query includes `workspace_id` filter
- [ ] Cross-workspace access returns 404 (not 403)
- [ ] Audit events log workspace_id
- [ ] No PII leaked in error messages

## Audit Logging Verification

All data modifications must be audited. Use provided fixtures:

```python
async def test_audit_logging(db_session, authenticated_client, workspace_1):
    """Verify audit event is created for client creation."""
    # Create client
    response = await authenticated_client.post("/api/v1/clients", json=client_data)

    # Verify audit event
    audit_events = await db_session.execute(
        select(AuditEvent).where(AuditEvent.workspace_id == workspace_1.id)
    )
    events = audit_events.scalars().all()
    assert len(events) == 1
    assert events[0].action == "create"
    assert events[0].entity_type == "client"
```

## Adding New Tests

### 1. Determine Test Category

**Integration Test** - Tests API endpoints or full stack interactions:
- Location: `tests/integration/api/test_<feature>.py`
- Uses `authenticated_client` fixture
- Tests HTTP request/response cycles

**Unit Test** - Tests isolated components:
- Location: `tests/unit/<domain>/test_<feature>.py`
- Uses `db_session` fixture only
- Tests pure functions or service layer

**Security Test** - Tests security properties:
- Location: `tests/security/<subdomain>/test_<feature>_security.py`
- Uses security conftest fixtures
- Tests authentication, encryption, input validation, etc.

### 2. Create Test File

```python
"""Tests for <feature> functionality.

This module tests:
- Key behavior 1
- Key behavior 2
- Edge cases
"""

import pytest
from pazpaz.models import ...

class Test<FeatureName>:
    """Test suite for <feature> functionality."""

    async def test_<scenario>(self, authenticated_client, workspace_1):
        """Test that <specific behavior> works correctly."""
        # Arrange
        ...

        # Act
        response = await authenticated_client.post(...)

        # Assert
        assert response.status_code == 200
```

### 3. Use Provided Fixtures

Always prefer provided fixtures over creating test data manually:

```python
# ✅ GOOD - Uses provided fixtures
async def test_create_session(authenticated_client, sample_client_ws1):
    response = await authenticated_client.post(
        f"/api/v1/sessions",
        json={"client_id": str(sample_client_ws1.id), ...}
    )

# ❌ BAD - Manually creates test data
async def test_create_session(authenticated_client, db_session, workspace_1):
    client = Client(workspace_id=workspace_1.id, ...)
    db_session.add(client)
    await db_session.commit()
    # ... rest of test
```

## Common Testing Patterns

### Testing Authentication

```python
async def test_authenticated_endpoint(authenticated_client, workspace_1):
    """Test endpoint requires valid JWT authentication."""
    response = await authenticated_client.get("/api/v1/clients")
    assert response.status_code == 200

async def test_unauthenticated_rejected(client):
    """Test unauthenticated request is rejected."""
    response = await client.get("/api/v1/clients")
    assert response.status_code == 401
```

### Testing CSRF Protection

```python
async def test_csrf_required(authenticated_client, workspace_1, test_user_ws1, redis_client):
    """Test CSRF token is required for state-changing requests."""
    # Get CSRF token
    csrf_token = await add_csrf_to_client(
        authenticated_client, workspace_1.id, test_user_ws1.id, redis_client
    )

    # Add to headers
    authenticated_client.headers.update({"X-CSRF-Token": csrf_token})

    response = await authenticated_client.post("/api/v1/clients", json=data)
    assert response.status_code == 201
```

### Testing Rate Limiting

```python
async def test_rate_limit(clear_rate_limits, authenticated_client):
    """Test rate limiting blocks excessive requests."""
    # Make requests up to limit
    for i in range(100):
        response = await authenticated_client.get("/api/v1/clients")
        assert response.status_code == 200

    # Next request should be rate limited
    response = await authenticated_client.get("/api/v1/clients")
    assert response.status_code == 429
```

### Testing Encryption

```python
async def test_phi_encryption(db_session, sample_client_ws1):
    """Test PHI fields are encrypted at rest."""
    # Fetch from database
    client = await db_session.get(Client, sample_client_ws1.id)

    # Check encrypted fields
    assert client.first_name != "John"  # Encrypted
    assert client.first_name.startswith("v1:")  # Version prefix

    # Decrypt
    decrypted = client.decrypt_field("first_name")
    assert decrypted == "John"
```

## Troubleshooting

### Tests Fail with "Too Many Requests" (429)

**Cause:** Rate limiting keys not cleared between tests.

**Solution:** Use `clear_rate_limits` fixture (autouse in security conftest):

```python
async def test_something(clear_rate_limits, authenticated_client):
    # Rate limits are cleared before this test
    ...
```

### Tests Fail with Event Loop Errors

**Cause:** Redis client bound to wrong event loop.

**Solution:** Always use the `redis_client` fixture, which creates a fresh connection per test.

### Tests Fail with "Sentinel Workspace Not Found"

**Cause:** Sentinel workspace was truncated.

**Solution:** The `truncate_tables` fixture automatically re-inserts the sentinel workspace after truncation. Ensure you're not manually deleting it.

### Tests Fail with Database Isolation Issues

**Cause:** Tables not truncated between tests.

**Solution:** The `truncate_tables` fixture runs automatically (autouse=True). Ensure your test doesn't override it.

## Contributing

When adding tests:

1. **Follow the directory structure** - Place tests in the correct category
2. **Use provided fixtures** - Don't reinvent the wheel
3. **Test workspace isolation** - Every query must filter by workspace_id
4. **Test audit logging** - Verify audit events are created
5. **Document intent** - Add docstrings explaining what you're testing
6. **Follow AAA pattern** - Arrange, Act, Assert
7. **Keep tests focused** - One assertion per test when possible
8. **Use descriptive names** - `test_create_client_requires_authentication` not `test_create`

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-Asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy Async Testing](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

## Questions?

If you have questions about the test suite structure or how to write tests:

1. Review existing tests in the same category
2. Check this README for patterns
3. Look at the conftest files for available fixtures
4. Ask the team in #engineering Slack channel
