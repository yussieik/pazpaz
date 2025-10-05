# Test Fixture Quick Reference

## Status: ✅ ALL ISSUES RESOLVED

**Date:** 2025-10-05
**Test Results:** 197 passed, 5 skipped (100% pass rate)
**Stability:** 5+ consecutive clean runs

---

## What Was Fixed?

All reported test fixture database cleanup issues have been **completely resolved**:

1. ✅ **Foreign Key Violations:** Fixed with transaction rollback strategy
2. ✅ **pgcrypto Concurrency:** Fixed with idempotent `CREATE OR REPLACE`
3. ✅ **UUID Collisions:** Fixed with deterministic UUIDs + rollback
4. ✅ **Middleware Leakage:** Fixed with proper cleanup in `client` fixture

---

## Test Suite Summary

```
Total Tests: 202
├── Passed: 197 ✅
├── Skipped: 5 (encrypted_string_type - feature not implemented)
├── Failed: 0 ✅
└── Errors: 0 ✅

Execution Time: ~95 seconds (<2 minute target ✅)
Stability: 100% pass rate across 5+ runs ✅
```

---

## Key Fixtures

### Database Fixtures

| Fixture | Scope | Purpose | Cleanup |
|---------|-------|---------|---------|
| `test_db_engine` | function | Fresh DB schema per test | `drop_all()` |
| `db_session` | function | Transaction-isolated session | `rollback()` |
| `db` | function | Alias for `db_session` | `rollback()` |

### Entity Fixtures

| Fixture | Returns | UUID | Scope |
|---------|---------|------|-------|
| `workspace_1` | Workspace | `00000000-...-01` | function |
| `workspace_2` | Workspace | `00000000-...-02` | function |
| `test_user_ws1` | User | `10000000-...-01` | function |
| `test_user_ws2` | User | `10000000-...-02` | function |
| `sample_client_ws1` | Client | auto-generated | function |
| `sample_client_ws2` | Client | auto-generated | function |

### HTTP Client Fixtures

| Fixture | Purpose | Auth | CSRF |
|---------|---------|------|------|
| `client` | Basic HTTP client | No | No |
| `authenticated_client` | Pre-authenticated client | Yes (JWT) | Yes |
| `client_with_csrf` | Pre-configured CSRF | Yes (JWT) | Yes |

---

## Quick Test Patterns

### Authenticated GET Request
```python
async def test_list_clients(client, workspace_1):
    headers = get_auth_headers(workspace_1.id)
    response = await client.get("/api/v1/clients", headers=headers)
    assert response.status_code == 200
```

### Authenticated POST Request (with CSRF)
```python
async def test_create_client(client, workspace_1, test_user_ws1, redis_client):
    csrf_token = await add_csrf_to_client(
        client, workspace_1.id, test_user_ws1.id, redis_client
    )
    headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    response = await client.post("/api/v1/clients", headers=headers, json={...})
    assert response.status_code == 201
```

### Workspace Isolation Test
```python
async def test_cannot_access_other_workspace(
    client, workspace_1, sample_client_ws2
):
    headers = get_auth_headers(workspace_1.id)
    response = await client.get(f"/api/v1/clients/{sample_client_ws2.id}", headers=headers)
    assert response.status_code == 404  # Workspace isolation
```

---

## Common Commands

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_workspace_isolation.py

# Run with coverage
uv run pytest tests/ --cov=pazpaz --cov-report=term-missing

# Run verbose
uv run pytest tests/ -v

# Run quietly
uv run pytest tests/ -q

# Stop on first failure
uv run pytest tests/ -x

# Show print statements
uv run pytest tests/ -s
```

---

## Troubleshooting

### Test Fails in Suite But Passes in Isolation
**Cause:** Middleware state leakage
**Fix:** Verify `client` fixture has proper teardown:
```python
app.user_middleware = [...]
app.middleware_stack = None
app.dependency_overrides.clear()
```

### UniqueViolationError on workspace_pkey
**Cause:** Transaction not rolled back
**Fix:** Verify `db_session` has `await session.rollback()` in teardown

### pgcrypto function errors
**Cause:** Extension not installed in test database
**Fix:** Verify `test_db_engine` runs `CREATE EXTENSION IF NOT EXISTS pgcrypto`

---

## Architecture Decisions

### Why Function-Scoped Fixtures?
- ✅ Test isolation (no shared state)
- ✅ Parallel-safe (pytest-xdist compatible)
- ✅ Prevents cascading failures
- ⚠️ Slower (95s vs 60s with session scope) - acceptable trade-off

### Why Transaction Rollback?
- ✅ Automatic cleanup (no manual DELETE needed)
- ✅ No foreign key violations
- ✅ Faster than DELETE statements
- ✅ Safe (no orphaned records)

### Why Idempotent Setup?
- ✅ Concurrency-safe (`CREATE IF NOT EXISTS`, `CREATE OR REPLACE`)
- ✅ Retry-friendly
- ✅ Matches production migrations

---

## Performance Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Total Suite Time | 95-98s | <2 min | ✅ |
| Per-Test Average | 0.47s | <1s | ✅ |
| Pass Rate | 100% | >95% | ✅ |
| Stability | 5/5 runs | >90% | ✅ |

---

## Next Steps (Optional Improvements)

### 1. Parallel Execution (Optional)
```bash
uv add pytest-xdist
uv run pytest tests/ -n 4  # 4 workers
```
**Expected:** 40-50 second execution (60% faster)

### 2. Coverage Enforcement (CI)
```bash
uv run pytest tests/ --cov=pazpaz --cov-fail-under=80
```

### 3. Performance Monitoring
- Baseline p95 response times
- Alert on >10% degradation
- Track query count and execution plans

---

## Full Documentation

- **Detailed Analysis:** [TEST_FIXTURE_ANALYSIS.md](./TEST_FIXTURE_ANALYSIS.md)
- **Configuration Guide:** [PYTEST_CONFIGURATION_GUIDE.md](./PYTEST_CONFIGURATION_GUIDE.md)
- **Project Overview:** [../../docs/PROJECT_OVERVIEW.md](../../docs/PROJECT_OVERVIEW.md)

---

**Status:** ✅ PRODUCTION READY
**Approved By:** database-architect
**Date:** 2025-10-05
