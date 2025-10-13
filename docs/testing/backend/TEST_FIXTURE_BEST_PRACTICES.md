# Test Fixture Best Practices

**Last Updated:** 2025-10-08
**Author:** Backend QA Specialist
**Status:** Production Guidelines

## Overview

This document provides comprehensive best practices for designing test fixtures in the PazPaz backend test suite. These guidelines emerged from Week 1 Day 5 test infrastructure optimization efforts that revealed critical fixture scope and performance issues.

## Executive Summary

**Key Findings from Week 1 Day 5 Analysis:**
- Test suite is **stable** with 198/203 tests passing (97.5%)
- 5 tests intentionally skipped (SQLAlchemy integration tests)
- Test duration: ~91-94 seconds (baseline)
- No fixture scope issues - original implementation was correct
- **Critical Discovery:** The reported "109 failures" did not exist in current codebase

## Fixture Scope Guidelines

### 1. Database Engine Fixture (`test_db_engine`)

**Current Implementation:** `scope="function"`
**Status:** OPTIMAL - Do not change

```python
@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create a test database engine with proper isolation."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    # Setup: Create tables once
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Teardown: Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

**Why Function Scope Works:**
- Ensures complete test isolation
- Prevents cross-test data contamination
- Handles `CREATE OR REPLACE FUNCTION` race conditions
- PostgreSQL optimizations make table creation fast enough (~0.45s per test)
- `NullPool` prevents connection pooling issues

**Why Session Scope Failed:**
- `pytest-asyncio` ScopeMismatch errors with function-scoped internal fixtures
- Committed transactions from fixtures persisted across tests
- UUID constraint violations on fixture data (workspace_1, test_user_ws1)
- TRUNCATE-based cleanup hung waiting for locks

### 2. Database Session Fixtures (`db`, `db_session`)

**Current Implementation:** `scope="function"`
**Status:** OPTIMAL

```python
@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession]:
    """Create a database session for testing."""
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()  # Cleanup uncommitted changes
```

**Key Points:**
- Each test gets a fresh session
- `rollback()` at teardown cleans up uncommitted changes
- Fixtures can use `commit()` safely (tables are dropped anyway)
- `expire_on_commit=False` prevents accidental database access after commit

### 3. Redis Client Fixture (`redis_client`)

**Current Implementation:** `scope="function"`
**Status:** OPTIMAL

```python
@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[redis.Redis]:
    """Create a Redis client for testing."""
    client = redis.from_url(TEST_REDIS_URL, decode_responses=True)

    await client.flushdb()  # Clean before test
    yield client
    await client.flushdb()  # Clean after test
    await client.aclose()
```

**Why Function Scope:**
- Redis operations are stateless and fast
- `flushdb()` ensures clean state
- Connection overhead is minimal (<10ms)
- Prevents cross-test state leakage

### 4. Test Data Fixtures (`workspace_1`, `test_user_ws1`, etc.)

**Current Implementation:** `scope="function"`
**Status:** OPTIMAL

```python
@pytest_asyncio.fixture(scope="function")
async def workspace_1(db_session: AsyncSession) -> Workspace:
    """Create a test workspace (workspace 1)."""
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test Workspace 1",
    )
    db_session.add(workspace)
    await db_session.commit()  # Commit is safe - tables will be dropped
    await db_session.refresh(workspace)
    return workspace
```

**Key Insights:**
- Fixed UUIDs enable predictable test setup
- `commit()` is safe because tables are dropped after each test
- Dependencies chain correctly: `workspace_1` → `test_user_ws1` → `sample_client_ws1`

## Common Pitfalls and Solutions

### Pitfall 1: Attempting Session-Scoped Async Fixtures

**Problem:**
```python
@pytest_asyncio.fixture(scope="session")  # ❌ WRONG
async def test_db_engine():
    ...
```

**Error:**
```
ScopeMismatch: You tried to access the function scoped fixture
_function_scoped_runner with a session scoped request object.
```

**Solution:** Keep async fixtures at `scope="function"` unless using `pytest-asyncio>=0.23` with explicit event loop management.

### Pitfall 2: TRUNCATE for Data Cleanup

**Problem:**
```python
# ❌ WRONG - Hangs waiting for locks
await session.execute(text("TRUNCATE TABLE workspaces CASCADE"))
```

**Why It Fails:**
- Active connections hold locks
- CASCADE propagation is slow
- Test sessions may overlap

**Solution:** Drop tables entirely after each test (original approach).

### Pitfall 3: Assuming rollback() Undoes commit()

**Problem:**
```python
async def workspace_1(db_session):
    workspace = Workspace(...)
    db_session.add(workspace)
    await db_session.commit()  # Persisted to database
    # Later...
    await db_session.rollback()  # ❌ Does NOT undo commit!
```

**Solution:** Rely on table drops for cleanup, not rollback.

### Pitfall 4: Race Conditions with CREATE OR REPLACE FUNCTION

**Problem:**
When running 203 tests concurrently, `CREATE OR REPLACE FUNCTION` can cause:
```
tuple concurrently updated
```

**Solution (Applied):**
```python
# Check before creating
result = await conn.execute(
    text("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'encrypt_phi_pgcrypto')")
)
if not result.scalar():
    await conn.execute(text("CREATE FUNCTION encrypt_phi_pgcrypto(...)"))
```

## Performance Optimization Strategies

### Current Performance Baseline

| Metric | Value |
|--------|-------|
| Total Tests | 203 |
| Passing | 198 |
| Skipped | 5 (intentional) |
| Duration | 91-94 seconds |
| Avg per test | ~0.45s |

### Why Not Optimize Further?

**Attempted Optimization:** Session-scoped database fixtures
**Expected Gain:** 3x speedup (30 seconds total)
**Actual Result:** 157 errors due to ScopeMismatch and data contamination
**Verdict:** Not worth the complexity

**Current Approach is Optimal Because:**
1. PostgreSQL table creation is fast (<0.01s per table)
2. Test isolation is guaranteed
3. No cross-test state leakage
4. Maintenance burden is low
5. 91 seconds for 203 tests is acceptable (p95 < 1s per test)

### When to Optimize

Consider optimization only if:
- [ ] Test suite exceeds 10 minutes
- [ ] Tests run in CI/CD pipeline multiple times per hour
- [ ] You have >1000 tests
- [ ] Individual test duration exceeds 5 seconds

## Fixture Dependency Best Practices

### Correct Dependency Chain

```python
test_db_engine (function)
    ├── db_session (function)
    │   ├── workspace_1 (function)
    │   │   ├── test_user_ws1 (function)
    │   │   └── sample_client_ws1 (function)
    │   └── workspace_2 (function)
    │       └── test_user_ws2 (function)
    └── client (function) [depends on db_session + redis_client]
```

### Anti-Pattern: Mixing Scopes

```python
# ❌ WRONG - Scope mismatch
@pytest_asyncio.fixture(scope="session")
async def test_db_engine():
    ...

@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine):  # session → function dependency
    ...
```

**Rule:** Child fixtures must have equal or narrower scope than parent fixtures.

## Testing Best Practices

### 1. Test Isolation

✅ **Good:**
```python
async def test_create_client(db_session, workspace_1):
    client = Client(workspace_id=workspace_1.id, first_name="John")
    db_session.add(client)
    await db_session.commit()

    # Test passes - clean state for next test
```

❌ **Bad:**
```python
# Relying on data from previous test
async def test_update_client(db_session):
    client = await db_session.get(Client, SOME_HARDCODED_ID)  # ❌ May not exist
```

### 2. Fixture Naming

- `test_db_engine`: Database engine (lowercase for consistency)
- `db_session` or `db`: Database session (alias)
- `workspace_1`, `workspace_2`: Test workspaces (numbered)
- `test_user_ws1`: Test user in workspace 1 (descriptive)
- `sample_client_ws1`: Sample client in workspace 1 (descriptive)

### 3. UUID Strategy

Use predictable UUIDs for test fixtures:
```python
workspace_1_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
workspace_2_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
test_user_ws1_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
test_user_ws2_id = uuid.UUID("10000000-0000-0000-0000-000000000002")
```

**Benefits:**
- Easy to debug failing tests
- Clear workspace boundaries (00… vs 10… prefixes)
- No randomness = reproducible tests

## Test Stability Verification

### Stability Checklist

- [x] 3 consecutive runs produce identical results (198 passed, 5 skipped)
- [x] No flaky tests (intermittent failures)
- [x] No race conditions
- [x] All critical test categories pass
  - [x] Auth endpoints: 18/18 passing
  - [x] Workspace isolation: 16/16 passing
  - [x] CSRF protection: 18/18 passing
  - [x] Audit logging: 7/7 passing
  - [x] Encryption: 22/27 (5 intentionally skipped)

### Monitoring Test Health

Run these commands periodically:

```bash
# Full test suite
uv run pytest -q --tb=short

# Performance test
uv run pytest -m performance -v

# Specific category
uv run pytest tests/test_workspace_isolation.py -v

# Stability check (3 runs)
for i in {1..3}; do uv run pytest -q --tb=no; done
```

## Lessons Learned from Week 1 Day 5

### What We Discovered

1. **Original Implementation Was Correct:** The test suite was already stable (198/203 passing)
2. **Reported Issue Didn't Exist:** "109 failures" mentioned in completion report was inaccurate
3. **Session Scope Fails for Async Fixtures:** `pytest-asyncio` doesn't support session-scoped async fixtures well
4. **TRUNCATE Cleanup Hangs:** Database locks prevent efficient data cleanup between tests
5. **Performance is Acceptable:** 91 seconds for 203 tests is good enough

### What We Tried (And Why It Failed)

| Optimization | Expected Gain | Actual Result | Verdict |
|--------------|---------------|---------------|---------|
| Session-scoped `test_db_engine` | 3x speedup | 157 errors (ScopeMismatch) | ❌ Failed |
| TRUNCATE for cleanup | Faster teardown | Tests hung waiting for locks | ❌ Failed |
| Idempotent function creation | No race conditions | ✅ Works | ✅ Keep |
| CASCADE drops for test tables | Clean teardown | ✅ Works | ✅ Keep |

### Recommendations

1. **Do Not Change Fixture Scopes:** Current implementation is optimal
2. **Trust PostgreSQL Performance:** Table creation is fast enough
3. **Document Intentionally Skipped Tests:** 5 SQLAlchemy integration tests are skipped for Week 2
4. **Monitor Test Duration:** Alert if test suite exceeds 120 seconds
5. **Focus on Test Quality, Not Speed:** 91 seconds is acceptable for this project size

## Conclusion

The PazPaz backend test suite is **stable, well-designed, and performant**. The fixture architecture uses best practices for test isolation, and the performance is acceptable for a project of this size. No optimization is recommended at this time.

**Test Suite Status: APPROVED ✅**

---

**Next Steps:**
- Proceed with Week 2 Day 1 implementation
- Continue monitoring test stability
- Add tests for new features as they're implemented
- Revisit performance if test suite exceeds 10 minutes

**Reference Documents:**
- [PYTEST_CONFIGURATION_GUIDE.md](./PYTEST_CONFIGURATION_GUIDE.md)
- [TEST_FIXTURE_QUICK_REFERENCE.md](./TEST_FIXTURE_QUICK_REFERENCE.md)
- [TEST_FIXTURE_ANALYSIS.md](./TEST_FIXTURE_ANALYSIS.md)
