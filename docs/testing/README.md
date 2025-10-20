# PazPaz Testing Documentation

**Last Updated:** 2025-10-20
**Test Suite Status:** 916 backend tests (100% passing)

---

## Documentation Structure

```
docs/testing/
├── README.md (this file)
├── backend/
│   ├── BACKEND_TESTING_GUIDE.md          # Comprehensive backend testing guide
│   └── CSRF_TEST_GUIDE.md                # CSRF integration testing patterns
└── frontend/
    └── (frontend testing docs)
```

---

## Backend Testing

### Primary Documentation

**[BACKEND_TESTING_GUIDE.md](./backend/BACKEND_TESTING_GUIDE.md)** - Comprehensive guide covering:
- Quick Start
- pytest Configuration
- Test Fixtures
- Common Test Patterns
- Running Tests
- Authentication & CSRF
- Workspace Isolation Testing
- Performance Testing
- Troubleshooting
- Best Practices

**Key Topics:**
- Session-scoped database setup with function-scoped table truncation
- JWT authentication with CSRF protection
- Workspace isolation patterns
- Performance benchmarks (<150ms p95)
- 916 tests covering all API endpoints and security controls

### Specialized Guides

**[CSRF_TEST_GUIDE.md](./backend/CSRF_TEST_GUIDE.md)** - CSRF middleware integration:
- Helper functions (`add_csrf_to_client()`)
- Which methods require CSRF
- Update patterns for existing tests
- Exempted endpoints

---

## Quality Assurance Reports

Located in `/docs/reports/qa/`:

### Security Testing

**[X_FORWARDED_FOR_SECURITY_TEST_REPORT.md](../reports/qa/X_FORWARDED_FOR_SECURITY_TEST_REPORT.md)**
- Critical IP spoofing vulnerability fix (2025-10-20)
- 77 comprehensive tests covering trusted proxy validation
- Attack scenario testing (SQL injection, XSS, null byte injection)
- Production-ready security posture

### Feature QA

**[QA_REPORT_PDF_METADATA_STRIPPING.md](../reports/qa/QA_REPORT_PDF_METADATA_STRIPPING.md)**
- PDF metadata sanitization (PHI protection)
- HIPAA compliance verification
- Performance benchmarks (0.3-1.4ms processing time)
- Production deployment approval

---

## Quick Reference

### Running Backend Tests

```bash
# All tests
cd /Users/yussieik/Desktop/projects/pazpaz/backend
uv run pytest tests/

# With coverage
uv run pytest tests/ --cov=pazpaz --cov-report=term-missing

# Parallel execution (4 workers)
uv run pytest tests/ -n 4

# Performance tests only
uv run pytest tests/ -m performance

# Specific test file
uv run pytest tests/test_api/test_sessions.py -v
```

### Common Test Patterns

**Authenticated GET Request:**
```python
async def test_list_clients(client, workspace_1):
    headers = get_auth_headers(workspace_1.id)
    response = await client.get("/api/v1/clients", headers=headers)
    assert response.status_code == 200
```

**POST with CSRF:**
```python
async def test_create_client(client, workspace_1, test_user_ws1, redis_client):
    csrf_token = await add_csrf_to_client(
        client, workspace_1.id, test_user_ws1.id, redis_client
    )
    headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
    headers["X-CSRF-Token"] = csrf_token

    response = await client.post("/api/v1/clients", headers=headers, json=data)
    assert response.status_code == 201
```

**Workspace Isolation:**
```python
async def test_isolation(client, workspace_1, resource_in_workspace_2):
    headers = get_auth_headers(workspace_1.id)
    response = await client.get(f"/api/v1/resource/{resource_in_workspace_2.id}", headers=headers)
    assert response.status_code == 404  # Cross-workspace access blocked
```

---

## Test Suite Statistics

**Current Status (2025-10-20):**
- **Total Tests:** 916
- **Passing:** 916 (100%)
- **Failed:** 0
- **Execution Time:** ~95s (sequential), ~40s (parallel 4 workers)

**Coverage Breakdown:**
- Session API: 78 tests
- Appointment API: 84 tests
- Client API: 35 tests
- Authentication: 13 tests
- Workspace Isolation: 16 tests
- CSRF Protection: 18 tests
- Encryption: 27 tests
- Security Tests: 50+ tests
- Performance Tests: 17 tests
- Other: 578 tests

**Performance Benchmarks:**
- All critical endpoints: p95 < 150ms ✅
- Encryption overhead: <10ms per field ✅
- API response times: 2-3x better than targets ✅

---

## Test Infrastructure

### Database Setup

**Test Database:** `pazpaz_test`
- **Session-scoped:** Database engine, pgcrypto extension, encryption functions, table creation
- **Function-scoped:** Table truncation (TRUNCATE CASCADE after each test)
- **Performance:** ~100x faster than DROP/CREATE per test

**Redis:** `redis://localhost:6379/1` (database 1 for tests)
- Flushed before and after each test

### Key Fixtures

- `test_db_engine` - Database engine (session scope)
- `truncate_tables` - Auto-cleanup (function scope, autouse)
- `db_session` - Database session (function scope)
- `redis_client` - Redis client (function scope)
- `client` - HTTP test client (function scope)
- `workspace_1`, `workspace_2` - Test workspaces
- `test_user_ws1`, `test_user_ws2` - Test users
- `sample_client_ws1`, `sample_client_ws2` - Sample clients

### Helper Functions

- `get_auth_headers(workspace_id, ...)` - Generate JWT headers
- `add_csrf_to_client(client, workspace_id, user_id, redis_client)` - Add CSRF token

---

## Troubleshooting

### Common Issues

1. **Test database not found**
   ```bash
   docker-compose exec -T db psql -U pazpaz -c "CREATE DATABASE pazpaz_test;"
   ```

2. **Encryption key not found**
   - Verify `.env` file exists in `/backend/.env`
   - Conftest.py auto-loads `.env` if `ENCRYPTION_MASTER_KEY` not set

3. **Redis connection error**
   ```bash
   redis-server  # Start Redis
   redis-cli ping  # Verify connection
   ```

4. **Tests hanging**
   ```bash
   uv run pytest tests/ -v -s  # Verbose + show print statements
   ```

For detailed troubleshooting, see [BACKEND_TESTING_GUIDE.md](./backend/BACKEND_TESTING_GUIDE.md#troubleshooting).

---

## Best Practices

### ✅ DO

1. Use function-scoped fixtures for database tests
2. Always test workspace isolation (404 for cross-workspace access)
3. Add CSRF tokens for POST/PUT/PATCH/DELETE requests
4. Use deterministic UUIDs in fixtures for debugging
5. Test both success and error cases
6. Add performance tests for critical endpoints

### ❌ DON'T

1. Share database state between tests (no session-scoped data fixtures)
2. Forget CSRF for state-changing requests
3. Use manual cleanup instead of truncate_tables
4. Mix production and test databases
5. Skip workspace isolation tests
6. Commit to test database (auto-truncated)

---

## References

- **Backend Testing Guide:** [backend/BACKEND_TESTING_GUIDE.md](./backend/BACKEND_TESTING_GUIDE.md)
- **CSRF Testing:** [backend/CSRF_TEST_GUIDE.md](./backend/CSRF_TEST_GUIDE.md)
- **QA Reports:** [../reports/qa/](../reports/qa/)
- **pytest Documentation:** https://docs.pytest.org/
- **pytest-asyncio:** https://pytest-asyncio.readthedocs.io/
- **FastAPI Testing:** https://fastapi.tiangolo.com/tutorial/testing/

---

**Maintained By:** Backend QA Specialist
**Status:** Production Guidelines
**Version:** 2.0
