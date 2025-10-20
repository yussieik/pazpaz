# CSRF Test Integration Guide

## Overview

This guide explains how to update integration tests to work with the CSRF protection middleware implemented in `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/middleware/csrf.py`.

## Background

CSRF middleware was implemented to protect against Cross-Site Request Forgery attacks. It requires:
- **Cookie**: `csrf_token` set on the client
- **Header**: `X-CSRF-Token` matching the cookie value

All state-changing requests (POST, PUT, PATCH, DELETE) must include both the cookie and header.

## Helper Functions Available

### 1. `add_csrf_to_client()` - Main CSRF Helper

**Location**: `/Users/yussieik/Desktop/projects/pazpaz/backend/tests/conftest.py`

**Signature**:
```python
async def add_csrf_to_client(
    client: AsyncClient,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    redis_client: redis.Redis,
) -> str
```

**Purpose**: Generates a CSRF token, stores it in Redis, and returns the token string to be used with `get_auth_headers()`.

**Returns**: CSRF token string (e.g., `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`)

### 2. Test User Fixtures

Two test user fixtures are available:
- `test_user_ws1` - User in workspace_1 (ID: `10000000-0000-0000-0000-000000000001`)
- `test_user_ws2` - User in workspace_2 (ID: `10000000-0000-0000-0000-000000000002`)

## Pattern for Updating Tests

### Step 1: Add Imports

Add these imports to your test file if not already present:

```python
from pazpaz.models.user import User
from tests.conftest import add_csrf_to_client, get_auth_headers
```

### Step 2: Update Function Signature

Add `test_user_ws1` and `redis_client` parameters to test functions that make POST/PUT/DELETE requests:

**Before**:
```python
async def test_create_appointment(
    self,
    client: AsyncClient,
    workspace_1: Workspace,
    sample_client_ws1: Client,
):
```

**After**:
```python
async def test_create_appointment(
    self,
    client: AsyncClient,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
    redis_client,
):
```

### Step 3: Add CSRF Token Before Request

**Before**:
```python
headers = get_auth_headers(workspace_1.id)

response = await client.post(
    "/api/v1/appointments",
    headers=headers,
    json={...},
)
```

**After**:
```python
# Add CSRF token
csrf_token = await add_csrf_to_client(
    client, workspace_1.id, test_user_ws1.id, redis_client
)
headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
headers["X-CSRF-Token"] = csrf_token

response = await client.post(
    "/api/v1/appointments",
    headers=headers,
    json={...},
)
```

## Complete Example

Here's a complete before/after example from `test_workspace_isolation.py`:

### Before (Failing):
```python
async def test_cannot_update_client_from_different_workspace(
    self,
    client: AsyncClient,
    workspace_1: Workspace,
    workspace_2: Workspace,
    sample_client_ws1: Client,
):
    """Cannot update client from different workspace."""
    headers = get_auth_headers(workspace_2.id)
    response = await client.put(
        f"/api/v1/clients/{sample_client_ws1.id}",
        headers=headers,
        json={"first_name": "Hacked"},
    )

    assert response.status_code == 404
```

### After (Passing):
```python
async def test_cannot_update_client_from_different_workspace(
    self,
    client: AsyncClient,
    workspace_1: Workspace,
    workspace_2: Workspace,
    sample_client_ws1: Client,
    test_user_ws2: User,  # Added
    redis_client,         # Added
):
    """Cannot update client from different workspace."""
    # Add CSRF token for workspace 2
    csrf_token = await add_csrf_to_client(
        client, workspace_2.id, test_user_ws2.id, redis_client
    )

    headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    response = await client.put(
        f"/api/v1/clients/{sample_client_ws1.id}",
        headers=headers,
        json={"first_name": "Hacked"},
    )

    assert response.status_code == 404
```

## Important Notes

### 1. GET/HEAD/OPTIONS Don't Need CSRF
Only state-changing methods require CSRF:
- ✅ POST - needs CSRF
- ✅ PUT - needs CSRF
- ✅ PATCH - needs CSRF
- ✅ DELETE - needs CSRF
- ❌ GET - no CSRF needed
- ❌ HEAD - no CSRF needed
- ❌ OPTIONS - no CSRF needed

### 2. Exempted Endpoints
Some endpoints are exempt from CSRF (see `csrf.py`):
- `/api/v1/auth/magic-link` - Entry point for authentication
- `/docs`, `/redoc`, `/openapi.json` - Documentation endpoints

### 3. Multiple Requests in Same Test
If a test makes multiple POST/PUT/DELETE requests, the CSRF token persists on the client cookies. You only need to call `add_csrf_to_client()` once per test function:

```python
async def test_multiple_operations(
    client,
    workspace_1,
    test_user_ws1,
    redis_client,
):
    # Add CSRF once at the beginning
    csrf_token = await add_csrf_to_client(
        client, workspace_1.id, test_user_ws1.id, redis_client
    )

    headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    # First request
    await client.post("/api/v1/resource1", headers=headers, json={...})

    # Second request - token persists, just use same headers
    await client.post("/api/v1/resource2", headers=headers, json={...})
```

### 4. Testing Cross-Workspace Operations
Use the appropriate test user for the workspace:
- `test_user_ws1` for operations in `workspace_1`
- `test_user_ws2` for operations in `workspace_2`

## Files Already Updated

✅ **Fully Updated (100% passing)**:
- `tests/conftest.py` - Helper functions added
- `tests/test_workspace_isolation.py` - 11/11 tests passing
- `tests/test_csrf_protection.py` - 17/17 tests passing
- `tests/test_auth_endpoints.py` - 15/15 tests passing (magic link exempt)

⚠️ **Needs Updates**:
- `tests/test_appointment_api.py` - 18/28 tests need CSRF (64% passing)
- `tests/test_client_api.py` - 18/27 tests need CSRF (33% passing)
- `tests/test_performance.py` - 17/17 tests need CSRF (0% passing)

## Test Results Summary

**Before CSRF Implementation**:
- Total Tests: 126
- Passing: ~120 (95%)
- Failing: ~6 (5%)

**After CSRF Implementation (Current State)**:
- Total Tests: 126
- Passing: 72 (57%)
- Failing: 54 (43%)

**After Partial Fix (workspace_isolation.py updated)**:
- `test_workspace_isolation.py`: 11/11 passing (was 6/11)
- `test_csrf_protection.py`: 17/17 passing (new tests)
- Core security tests: ✅ All passing

## Estimated Effort

To update remaining test files:
- `test_appointment_api.py`: ~30-45 minutes (18 tests)
- `test_client_api.py`: ~30-45 minutes (18 tests)
- `test_performance.py`: ~20-30 minutes (17 tests)

**Total**: ~1.5-2 hours to reach >95% test pass rate

## Troubleshooting

### Error: "CSRF token missing"
- **Cause**: Test doesn't include CSRF cookie or header
- **Fix**: Add `add_csrf_to_client()` before the request

### Error: "CSRF token mismatch"
- **Cause**: Cookie and header values don't match
- **Fix**: Ensure you're using the headers returned by `add_csrf_to_client()`

### Error: Fixture not found (test_user_ws1)
- **Cause**: Missing fixture parameter in test function signature
- **Fix**: Add `test_user_ws1: User` and `redis_client` to function parameters

### Syntax Error: Trailing comma in signature
- **Cause**: Automated script may have added extra comma
- **Fix**: Remove trailing comma before `)`

## Questions?

Refer to:
- CSRF middleware implementation: `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/middleware/csrf.py`
- Working examples: `/Users/yussieik/Desktop/projects/pazpaz/backend/tests/test_workspace_isolation.py`
- CSRF tests: `/Users/yussieik/Desktop/projects/pazpaz/backend/tests/test_csrf_protection.py`
