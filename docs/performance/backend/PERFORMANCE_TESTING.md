# Performance Testing Guide

## Overview

The PazPaz backend includes comprehensive performance baseline tests to validate that schedule endpoints meet the **p95 < 150ms** target specified in `PROJECT_OVERVIEW.md`.

## Performance Targets

- **Mean response time**: < 100ms
- **p95 response time**: < 150ms (CRITICAL)
- **p99 response time**: < 300ms

## Test Scenarios

### Dataset Sizes

Tests run against three different dataset sizes to validate scalability:

1. **Small Dataset**: 10 clients, 50 appointments
   - Represents: New therapist just starting practice

2. **Medium Dataset**: 50 clients, 500 appointments
   - Represents: Established therapist with moderate client load

3. **Large Dataset**: 100 clients, 1000 appointments
   - Represents: Very busy therapist or small clinic with extensive history

### Endpoints Tested

1. **Calendar View** (`GET /api/v1/appointments?start_date=...&end_date=...`)
   - Simulates viewing weekly/monthly calendar
   - Critical for UX - therapist accesses this constantly

2. **Client Timeline** (`GET /api/v1/appointments?client_id=...`)
   - Simulates viewing all appointments for a specific client
   - Used when reviewing client treatment history

3. **Conflict Detection** (`GET /api/v1/appointments/conflicts?...`)
   - Simulates real-time conflict checking during scheduling
   - Critical for drag-and-drop calendar UX

4. **Create Appointment** (`POST /api/v1/appointments`)
   - Simulates creating new appointments with conflict detection
   - Tests write performance with concurrent reads

5. **Concurrent Requests**
   - Simulates multiple therapists or browser tabs accessing simultaneously
   - Tests database connection pooling and query optimization

## Running Performance Tests

### Prerequisites

1. **Start PostgreSQL database:**
   ```bash
   cd /Users/yussieik/Desktop/projects/pazpaz
   docker compose up -d db
   ```

2. **Create test database:**
   ```bash
   docker exec -it pazpaz-db psql -U pazpaz -d pazpaz -c "DROP DATABASE IF EXISTS pazpaz_test;"
   docker exec -it pazpaz-db psql -U pazpaz -d pazpaz -c "CREATE DATABASE pazpaz_test;"
   ```

3. **Verify database connection:**
   ```bash
   docker exec -it pazpaz-db psql -U pazpaz -d pazpaz_test -c "SELECT 1;"
   ```

### Run All Performance Tests

```bash
cd /Users/yussieik/Desktop/projects/pazpaz/backend
uv run pytest -m performance -v -s
```

### Run Specific Test Classes

```bash
# Test only calendar view performance
uv run pytest tests/test_performance.py::TestAppointmentListPerformance -v -s

# Test only conflict detection performance
uv run pytest tests/test_performance.py::TestConflictDetectionPerformance -v -s

# Test only concurrent request performance
uv run pytest tests/test_performance.py::TestConcurrentRequestPerformance -v -s
```

### Run Performance Summary

Quick overview of system performance across all datasets:

```bash
uv run pytest tests/test_performance.py::TestPerformanceSummary::test_generate_performance_summary -v -s
```

## Understanding Test Output

Tests output detailed statistics for each scenario:

```
Calendar View - medium dataset:
  Mean: 45.23ms
  Median: 42.10ms
  p95: 67.89ms
  p99: 89.45ms
  Min: 28.34ms
  Max: 112.67ms
```

### What the metrics mean:

- **Mean**: Average response time across all requests
- **Median**: Middle value - 50% of requests are faster, 50% slower
- **p95**: 95th percentile - 95% of requests are faster than this
- **p99**: 99th percentile - 99% of requests are faster than this
- **Min/Max**: Fastest and slowest individual requests

### Test Assertions

Tests will FAIL if:
- p95 exceeds 150ms
- p99 exceeds 300ms (for most tests)
- Mean exceeds 100ms

## Performance Optimization Tips

If tests fail, investigate these areas:

### 1. Database Indexes

Verify indexes exist on critical columns:
```sql
-- Check existing indexes
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'appointments';
```

Required indexes:
- `ix_appointments_workspace_time_range` on `(workspace_id, scheduled_start, scheduled_end)`
- `ix_appointments_workspace_client` on `(workspace_id, client_id)`

### 2. Query Analysis

Profile slow queries using EXPLAIN ANALYZE:
```python
# Add to conftest.py for debugging
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    print(f"SQL: {statement}")
    print(f"Params: {params}")
```

### 3. Connection Pooling

Check SQLAlchemy pool settings:
- Pool size (default: 5)
- Max overflow (default: 10)
- Pool pre-ping (enabled for health checks)

### 4. Response Size

For calendar views with many appointments:
- Verify pagination is working correctly
- Ensure client relationships use `selectinload` (not lazy loading)
- Check JSON serialization performance

## CI/CD Integration

### Add to GitHub Actions

```yaml
name: Performance Tests

on: [pull_request]

jobs:
  performance:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
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

    steps:
      - uses: actions/checkout@v4
      - name: Run performance tests
        run: |
          cd backend
          uv run pytest -m performance -v
```

### Performance Regression Detection

Consider failing builds if:
- p95 regresses by > 20%
- p99 regresses by > 30%
- Any test exceeds targets by > 10%

## Test Data Cleanup

Tests automatically:
- Create test data at setup
- Clean up tables after each test (using `scope="function"`)
- Drop all tables after test suite completes

No manual cleanup needed.

## Troubleshooting

### Tests are slow on first run

**Cause**: Database table creation and initial data population.

**Solution**: Normal behavior. Subsequent runs will be faster.

### Tests fail with connection errors

**Cause**: Database not running or wrong credentials.

**Solution**:
```bash
# Check database is running
docker ps | grep pazpaz-db

# Check connection
docker exec -it pazpaz-db psql -U pazpaz -d pazpaz_test -c "SELECT 1;"

# Restart database
docker compose restart db
```

### p95 times are higher than expected

**Cause**: Could be system load, missing indexes, or inefficient queries.

**Solution**:
1. Run tests when system is not under load
2. Verify indexes exist (see "Database Indexes" section)
3. Profile queries with EXPLAIN ANALYZE
4. Check for N+1 query problems

### Concurrent tests fail but individual tests pass

**Cause**: Connection pool exhaustion or lock contention.

**Solution**:
1. Increase SQLAlchemy pool size
2. Review transaction isolation levels
3. Check for long-running transactions or locks

## Performance Monitoring in Production

These baseline tests establish performance expectations. In production:

1. **Add application metrics**:
   - Instrument endpoints with timing middleware
   - Track p95/p99 in production
   - Alert when > 150ms p95

2. **Database monitoring**:
   - Monitor slow query log
   - Track index usage
   - Watch for sequential scans on appointments table

3. **APM tools**:
   - Consider Sentry, DataDog, or New Relic
   - Track request latency distributions
   - Set up alerts for performance regressions

## References

- [PROJECT_OVERVIEW.md](../../docs/PROJECT_OVERVIEW.md) - Performance requirements
- [conftest.py](./tests/conftest.py) - Test fixtures
- [test_performance.py](./tests/test_performance.py) - Performance test implementation
