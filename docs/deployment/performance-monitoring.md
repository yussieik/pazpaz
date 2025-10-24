# Performance Monitoring

## Overview

PazPaz implements comprehensive performance monitoring to ensure the application meets its SLA target of p95 response time <150ms for schedule endpoints. This document covers performance metrics, monitoring setup, optimization strategies, and troubleshooting procedures.

## Performance Requirements

### SLA Targets

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| P50 Response Time | <50ms | >100ms |
| P95 Response Time | <150ms | >500ms |
| P99 Response Time | <500ms | >1000ms |
| Error Rate | <0.1% | >1% |
| Availability | >99.9% | <99% |
| Throughput | >100 req/s | <50 req/s |

### Critical Endpoints

Priority endpoints requiring strict performance monitoring:

```yaml
Critical (P95 <150ms):
  - GET /api/v1/appointments
  - GET /api/v1/appointments/{id}
  - GET /api/v1/schedule
  - POST /api/v1/appointments
  - GET /api/v1/clients
  - GET /api/v1/clients/{id}

Important (P95 <300ms):
  - GET /api/v1/sessions
  - POST /api/v1/sessions
  - GET /api/v1/services
  - GET /api/v1/users/me

Standard (P95 <500ms):
  - All other endpoints
```

## Metrics Collection

### Application Metrics

```python
# backend/src/pazpaz/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import FastAPI, Request, Response
import time

# Define metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

active_requests = Gauge(
    'http_requests_active',
    'Active HTTP requests'
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type', 'table']
)

cache_hit_rate = Counter(
    'cache_hits_total',
    'Cache hit/miss rate',
    ['cache_type', 'hit']
)

def setup_metrics(app: FastAPI):
    """Setup Prometheus metrics middleware"""

    @app.middleware("http")
    async def track_metrics(request: Request, call_next):
        # Track active requests
        active_requests.inc()

        # Start timer
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Record metrics
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        active_requests.dec()

        # Add response header
        response.headers["X-Response-Time"] = str(duration)

        return response

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint"""
        return Response(content=generate_latest(), media_type="text/plain")
```

### Database Metrics

```python
# backend/src/pazpaz/core/database.py
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info["query_start_time"].pop(-1)

    # Extract query type and table
    query_type = statement.split()[0].upper()
    table = extract_table_name(statement)

    # Record metric
    db_query_duration.labels(
        query_type=query_type,
        table=table
    ).observe(total)

    # Log slow queries
    if total > 1.0:
        logger.warning(f"Slow query ({total:.2f}s): {statement[:100]}")
```

## Monitoring Infrastructure

### 1. Prometheus Setup (Optional - Phase 2)

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: pazpaz-prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "9090:9090"
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    container_name: pazpaz-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=redis-datasource
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning
    ports:
      - "3001:3000"
    networks:
      - monitoring

volumes:
  prometheus_data:
  grafana_data:

networks:
  monitoring:
    driver: bridge
```

### 2. Prometheus Configuration

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'pazpaz-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['db:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

## Performance Testing

### Load Testing with Locust

```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between
import random

class PazPazUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Login and get token"""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@pazpaz.com",
            "password": "testpass"
        })
        self.token = response.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    @task(10)
    def view_appointments(self):
        """Most common operation"""
        self.client.get("/api/v1/appointments")

    @task(5)
    def view_schedule(self):
        """Schedule view"""
        self.client.get("/api/v1/schedule")

    @task(3)
    def view_clients(self):
        """Client list"""
        self.client.get("/api/v1/clients")

    @task(2)
    def create_appointment(self):
        """Create appointment"""
        self.client.post("/api/v1/appointments", json={
            "client_id": random.randint(1, 100),
            "service_id": random.randint(1, 10),
            "start_time": "2024-10-25T10:00:00",
            "duration_minutes": 60
        })

    @task(1)
    def view_client_detail(self):
        """View specific client"""
        client_id = random.randint(1, 100)
        self.client.get(f"/api/v1/clients/{client_id}")
```

### Running Load Tests

```bash
# Install Locust
pip install locust

# Run test with 100 users
locust -f tests/performance/locustfile.py \
       --host=https://api.pazpaz.com \
       --users=100 \
       --spawn-rate=10 \
       --time=5m \
       --headless \
       --csv=results

# View results
cat results_stats.csv
```

## Performance Check Script

Create `scripts/check-performance.sh`:

```bash
#!/bin/bash
# See actual implementation below
```

## Query Optimization

### Database Indexes

```sql
-- Critical indexes for performance
CREATE INDEX CONCURRENTLY idx_appointments_workspace_start
    ON appointments(workspace_id, start_time);

CREATE INDEX CONCURRENTLY idx_appointments_therapist_date
    ON appointments(therapist_id, DATE(start_time));

CREATE INDEX CONCURRENTLY idx_clients_workspace_active
    ON clients(workspace_id, is_active)
    WHERE is_active = true;

CREATE INDEX CONCURRENTLY idx_sessions_appointment
    ON sessions(appointment_id);

-- Analyze tables after indexing
ANALYZE appointments;
ANALYZE clients;
ANALYZE sessions;
```

### Query Performance Analysis

```sql
-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View slowest queries
SELECT
    query,
    mean_exec_time,
    calls,
    total_exec_time,
    min_exec_time,
    max_exec_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Explain analyze for specific query
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM appointments
WHERE workspace_id = 1
  AND start_time >= '2024-10-24'
  AND start_time < '2024-10-31'
ORDER BY start_time;
```

## Caching Strategy

### Redis Caching

```python
# backend/src/pazpaz/core/cache.py
import redis
import json
from functools import wraps
import hashlib

redis_client = redis.Redis(
    host='redis',
    port=6379,
    decode_responses=True
)

def cache_key(*args, **kwargs):
    """Generate cache key from arguments"""
    key_data = f"{args}:{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()

def cached(expire=300):
    """Cache decorator with expiration"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            cached_value = redis_client.get(key)
            if cached_value:
                cache_hit_rate.labels(cache_type="redis", hit="true").inc()
                return json.loads(cached_value)

            # Cache miss - execute function
            cache_hit_rate.labels(cache_type="redis", hit="false").inc()
            result = await func(*args, **kwargs)

            # Store in cache
            redis_client.setex(key, expire, json.dumps(result))

            return result
        return wrapper
    return decorator

# Usage example
@cached(expire=600)
async def get_appointments(workspace_id: int, date: str):
    """Cached appointment query"""
    return await db.fetch_appointments(workspace_id, date)
```

### Cache Invalidation

```python
def invalidate_cache(pattern: str):
    """Invalidate cache entries matching pattern"""
    for key in redis_client.scan_iter(match=pattern):
        redis_client.delete(key)

# Invalidate on update
async def update_appointment(appointment_id: int, data: dict):
    result = await db.update_appointment(appointment_id, data)

    # Invalidate related caches
    invalidate_cache(f"get_appointments:*")
    invalidate_cache(f"get_schedule:*")

    return result
```

## Application Performance

### FastAPI Optimization

```python
# backend/src/pazpaz/main.py
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI()

# Enable response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["pazpaz.com", "*.pazpaz.com"]
)

# Connection pooling
from sqlalchemy.pool import NullPool, QueuePool

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

### Async Optimization

```python
# Parallel queries
import asyncio

async def get_dashboard_data(user_id: int):
    """Fetch dashboard data in parallel"""
    appointments, clients, stats = await asyncio.gather(
        get_user_appointments(user_id),
        get_user_clients(user_id),
        get_user_statistics(user_id)
    )

    return {
        "appointments": appointments,
        "clients": clients,
        "statistics": stats
    }
```

## Frontend Performance

### Vue 3 Optimization

```javascript
// Lazy loading routes
const routes = [
  {
    path: '/appointments',
    component: () => import('./views/Appointments.vue')
  },
  {
    path: '/clients',
    component: () => import('./views/Clients.vue')
  }
]

// Component lazy loading
const HeavyComponent = defineAsyncComponent(() =>
  import('./components/HeavyComponent.vue')
)

// Virtual scrolling for long lists
import { VirtualList } from '@tanstack/vue-virtual'
```

### Bundle Optimization

```javascript
// vite.config.js
export default {
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          utils: ['lodash', 'date-fns']
        }
      }
    },
    // Enable compression
    compression: 'gzip',
    // Optimize dependencies
    optimizeDeps: {
      include: ['vue', 'vue-router', 'pinia']
    }
  }
}
```

## Performance Dashboard

### Key Metrics to Display

```yaml
Real-time Metrics:
  - Current response time (p50, p95, p99)
  - Requests per second
  - Active connections
  - Error rate
  - Cache hit ratio

Historical Metrics:
  - Response time trends (24h, 7d, 30d)
  - Peak traffic periods
  - Error spike analysis
  - Slow endpoint identification
  - Database query performance

Alerts:
  - P95 > 200ms for 5 minutes
  - Error rate > 1% for 2 minutes
  - Database connection pool exhausted
  - Cache hit ratio < 50%
  - Memory usage > 80%
```

## Performance Troubleshooting

### Slow Response Diagnosis

```bash
# 1. Check current performance
./scripts/check-performance.sh

# 2. Identify slow endpoints
curl -s https://api.pazpaz.com/metrics | grep http_request_duration

# 3. Check database performance
docker exec pazpaz-db psql -U pazpaz -c "
  SELECT query, mean_exec_time, calls
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;
"

# 4. Check cache hit ratio
docker exec pazpaz-redis redis-cli INFO stats | grep hit

# 5. Profile specific endpoint
python -m cProfile -o profile.stats scripts/profile_endpoint.py
```

### Common Performance Issues

| Issue | Symptoms | Solution |
|-------|----------|----------|
| N+1 Queries | Slow list endpoints | Use eager loading |
| Missing Indexes | Slow filters/searches | Add appropriate indexes |
| Cache Misses | Repeated slow queries | Implement caching |
| Large Payloads | Slow network transfer | Paginate, compress |
| Connection Exhaustion | Intermittent timeouts | Increase pool size |
| Memory Leaks | Growing memory usage | Profile and fix leaks |

## Performance Optimization Checklist

### Backend Optimization

- [ ] Database indexes on foreign keys and filter columns
- [ ] Query optimization (EXPLAIN ANALYZE)
- [ ] Connection pooling configured
- [ ] Redis caching for frequent queries
- [ ] Async/await for I/O operations
- [ ] Response compression enabled
- [ ] Pagination for list endpoints
- [ ] Bulk operations where appropriate

### Frontend Optimization

- [ ] Code splitting and lazy loading
- [ ] Image optimization and lazy loading
- [ ] Bundle size optimization
- [ ] Browser caching headers
- [ ] CDN for static assets
- [ ] Virtual scrolling for long lists
- [ ] Debounced API calls
- [ ] Optimistic UI updates

### Infrastructure Optimization

- [ ] Horizontal scaling capability
- [ ] Load balancing configured
- [ ] Database read replicas
- [ ] Redis clustering
- [ ] CDN configured
- [ ] SSL/TLS optimization
- [ ] HTTP/2 enabled
- [ ] Resource limits set

## Monitoring Tools

### Command-Line Tools

```bash
# Apache Bench
ab -n 1000 -c 10 https://api.pazpaz.com/api/v1/health

# curl with timing
curl -w "@curl-format.txt" -o /dev/null -s https://api.pazpaz.com/api/v1/appointments

# hey (better than ab)
hey -n 1000 -c 10 -m GET https://api.pazpaz.com/api/v1/health

# vegeta attack
echo "GET https://api.pazpaz.com/api/v1/health" | vegeta attack -duration=30s -rate=100 | vegeta report
```

### Python Profiling

```python
# Profile specific function
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
result = await expensive_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

## Performance Budget

### Target Metrics

```yaml
Page Load:
  - Time to First Byte (TTFB): <200ms
  - First Contentful Paint (FCP): <1s
  - Largest Contentful Paint (LCP): <2.5s
  - Time to Interactive (TTI): <3s
  - Cumulative Layout Shift (CLS): <0.1

API Response:
  - Authentication: <100ms
  - List endpoints: <150ms
  - Detail endpoints: <100ms
  - Create/Update: <200ms
  - Search: <300ms
  - Reports: <1000ms

Database:
  - Simple queries: <10ms
  - Complex queries: <50ms
  - Aggregations: <100ms
  - Transactions: <200ms
```

## Related Documentation

- [Logging Configuration](./logging-configuration.md)
- [Uptime Monitoring](./uptime-monitoring.md)
- [Error Tracking](./error-tracking.md)
- [Infrastructure Security](./INFRASTRUCTURE_SECURITY_CHECKLIST.md)

---

**Last Updated:** 2024-10-24
**Version:** 1.0.0
**Status:** Production Ready