# ADR 0004: Observability & Monitoring Stack - Implementation Guide

**Parent Document:** [ADR 0004: Observability & Monitoring Stack](./0004-observability-monitoring-stack.md)
**Last Updated:** 2025-11-12
**Status:** Ready for Implementation

---

## Existing Infrastructure Audit ✅

**Purpose:** Identify reusable components to avoid duplicating work

### What's Already Implemented

| Component | Status | Location | Reuse Strategy |
|-----------|--------|----------|----------------|
| **Health Endpoints** | ✅ **EXISTS** | `backend/src/pazpaz/main.py:732-742` | **ENHANCE** with DB connection check |
| **Prometheus `/metrics` Endpoint** | ✅ **EXISTS** | `backend/src/pazpaz/api/metrics.py:10-47` | **REUSE** as-is, add HTTP instrumentation |
| **Prometheus Client Library** | ✅ **INSTALLED** | `backend/pyproject.toml` (`prometheus-client>=0.23.1`) | **REUSE** for new metrics |
| **AI Metrics** | ✅ **COMPLETE** | `backend/src/pazpaz/ai/metrics.py` (138 lines, 16 metrics) | **PATTERN** for business metrics |
| **Structured JSON Logging** | ✅ **PRODUCTION-READY** | `backend/src/pazpaz/core/logging.py` (124 lines) | **REUSE** unchanged |
| **Request Logging Middleware** | ✅ **PRODUCTION-READY** | `backend/src/pazpaz/main.py:328-393` | **INTEGRATE** with Sentry |
| **Docker Compose (Production)** | ✅ **COMPLETE** | `docker-compose.prod.yml` (698 lines) | **EXTEND** with monitoring services |
| **PHI Constants** | ✅ **EXISTS** | `backend/src/pazpaz/main.py:404-420` | **REUSE** for PII stripping |
| **Environment Variable Placeholder** | ✅ **DOCUMENTED** | `backend/.env.example:318` (`SENTRY_DSN`) | **POPULATE** with actual value |

### What Needs to Be Built

| Component | Status | Effort | Priority |
|-----------|--------|--------|----------|
| **Sentry SDK (Backend)** | ❌ **NOT INSTALLED** | 1.5 hours | **CRITICAL** |
| **Sentry SDK (Frontend)** | ❌ **NOT INSTALLED** | 1 hour | **CRITICAL** |
| **HTTP Request Instrumentation** | ❌ **MISSING** | 1.5 hours | **HIGH** |
| **Business Metrics** | ❌ **NOT EXISTS** | 1 hour | **MEDIUM** |
| **DB Health Check** | ⚠️ **NEEDS ENHANCEMENT** | 0.5 hours | **HIGH** |
| **Prometheus + Grafana (Docker)** | ❌ **NOT IN COMPOSE** | 2 hours | **HIGH** |
| **Grafana Dashboards** | ❌ **NOT EXISTS** | 3 hours | **MEDIUM** |
| **Grafana Alert Rules** | ❌ **NOT EXISTS** | 2 hours | **MEDIUM** |
| **UptimeRobot Configuration** | ❌ **NOT CONFIGURED** | 1 hour | **CRITICAL** |
| **Postgres/Redis Exporters** | ❌ **NOT IN COMPOSE** | 1 hour | **MEDIUM** |

**Total New Effort:** 15 hours (vs. original estimate of 28 hours)
**Savings from Reuse:** 13 hours (46% reduction)

---

## Revised Implementation Roadmap

### Phase 1: Essential Monitoring (Week 1, 6 hours) ⏱️ REDUCED from 8 hours

**Time Savings:** 2 hours (leveraging existing health endpoints, logging, request IDs)

**STATUS:** ✅ **COMPLETED** (2025-11-12)

**Completion Summary:**
- ✅ **Task 1.1:** Sentry Error Tracking - COMPLETED (3 hours)
  - Backend Sentry SDK installed (`sentry-sdk[fastapi]>=2.39.0`)
  - Frontend Sentry SDK installed (`@sentry/vue`)
  - PII/PHI stripping configured for both backend and frontend
  - PHI_FIELDS constant centralized to `backend/src/pazpaz/core/constants.py`
  - Test endpoint added (`/test/sentry`)
  - Production deployment verified

- ✅ **Task 1.3:** Enhanced Health Endpoint - COMPLETED (2 hours)
  - Health endpoint enhanced with database connectivity check
  - Returns JSON: `{"status":"healthy","database":"connected","timestamp":"..."}`
  - Cascading health checks: Database → Backend API → Frontend Nginx → Main Nginx
  - Main nginx (`nginx/nginx-ssl.conf`) proxies to frontend
  - Frontend nginx (`frontend/nginx.prod.conf`) proxies to backend API
  - CI deployment verification fixed and tested
  - Production deployment verified working

- ⏱️ **Task 1.2:** UptimeRobot Configuration - PENDING (1 hour)
  - Manual configuration required (see instructions below)
  - 3 monitors needed: Database connectivity, Frontend availability, API availability

**Production Health Endpoint:** `https://pazpaz.health/health`

---

#### Task 1.1: Sentry Error Tracking (3 hours)

**Reuse:**
- ✅ Existing `PHI_FIELDS` constant (`main.py:404-420`) for PII detection
- ✅ Existing `request.state.request_id` from `RequestLoggingMiddleware`
- ✅ Existing structured logging (`core/logging.py`)

**Steps:**

**A. Backend Integration (1.5 hours)**

1. **Install Sentry SDK** (5 min):
```bash
cd backend
uv add sentry-sdk[fastapi]
```

2. **Create PII Stripping Module** (30 min):

Create `backend/src/pazpaz/monitoring/sentry_config.py`:

```python
"""Sentry configuration with HIPAA-compliant PII stripping."""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from pazpaz.core.config import settings
from pazpaz.main import PHI_FIELDS  # REUSE existing PHI detection

def strip_pii_from_sentry_event(event, hint):
    """
    Remove PII/PHI before sending to Sentry (HIPAA compliance).

    Removes:
    - User emails, names, phone numbers
    - Session notes (S/O/A/P fields)
    - Client data
    - Authentication tokens
    """
    # Remove user PII (keep UUID only)
    if 'user' in event:
        event['user'] = {'id': event['user'].get('id')}

    # Scrub request data
    if 'request' in event:
        event['request'].pop('cookies', None)
        # Keep only safe headers
        safe_headers = {'content-type', 'user-agent', 'host'}
        if 'headers' in event['request']:
            event['request']['headers'] = {
                k: v for k, v in event['request']['headers'].items()
                if k.lower() in safe_headers
            }
        event['request'].pop('query_string', None)

    # Scrub breadcrumbs (may contain SQL queries with PHI)
    if 'breadcrumbs' in event:
        for crumb in event['breadcrumbs'].get('values', []):
            if crumb.get('category') == 'query':
                crumb['message'] = '[REDACTED SQL QUERY]'

    # Remove local variables from stack traces (may contain PHI)
    if 'exception' in event:
        for exception in event['exception'].get('values', []):
            if 'stacktrace' in exception:
                for frame in exception['stacktrace'].get('frames', []):
                    frame.pop('vars', None)

    # Scrub POST/PUT body if contains PHI fields
    if 'request' in event and 'data' in event['request']:
        body = event['request']['data']
        if isinstance(body, dict):
            for field in PHI_FIELDS:  # REUSE from main.py
                if field in body:
                    body[field] = '[REDACTED PHI]'

    return event

def init_sentry():
    """Initialize Sentry with PII stripping."""
    if not settings.sentry_dsn:
        return  # Sentry not configured (acceptable in local dev)

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,  # "production" or "staging" or "local"
        traces_sample_rate=0.1,  # 10% of transactions (cost control)
        profiles_sample_rate=0.1,  # 10% of profiles
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
        ],
        before_send=strip_pii_from_sentry_event,
        # Ignore noisy errors
        ignore_errors=[
            "ConnectionClosed",  # WebSocket disconnects
            "CancelledError",  # Client cancelled requests
        ],
    )
```

3. **Add to Settings** (5 min):

Edit `backend/src/pazpaz/core/config.py`, add:

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # Sentry Error Tracking
    sentry_dsn: str | None = None  # Optional (not required for local dev)
```

4. **Initialize in FastAPI** (10 min):

Edit `backend/src/pazpaz/main.py`, add import and call in lifespan:

```python
# Add import at top
from pazpaz.monitoring.sentry_config import init_sentry

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    configure_logging(debug=settings.debug)
    logger = get_logger(__name__)

    # Initialize Sentry (NEW)
    init_sentry()
    if settings.sentry_dsn:
        logger.info("sentry_initialized", environment=settings.environment)

    # ... rest of lifespan ...
```

5. **Test Backend Error Tracking** (40 min):
   - Add test endpoint:
```python
@app.get("/test/sentry")
async def test_sentry():
    """Test endpoint to verify Sentry error capture."""
    raise ValueError("Test error for Sentry - if you see this in Sentry, it works!")
```
   - Create Sentry account at https://sentry.io (free trial)
   - Create project "pazpaz-backend"
   - Copy DSN
   - Add to `backend/.env`: `SENTRY_DSN=https://...@sentry.io/...`
   - Restart backend: `docker compose restart api`
   - Trigger error: `curl http://localhost:8000/test/sentry`
   - Verify in Sentry dashboard (should appear within 30s)
   - **CRITICAL CHECK:** Verify no PHI in error details (check stack trace, request data)

**B. Frontend Integration (1 hour)**

1. **Install Sentry SDK** (5 min):
```bash
cd frontend
npm install @sentry/vue
```

2. **Create Sentry Config** (15 min):

Create `frontend/src/monitoring/sentry.ts`:

```typescript
/**
 * Sentry configuration with PII stripping for frontend errors.
 */

import * as Sentry from "@sentry/vue"

/**
 * Strip PII from Sentry events (HIPAA compliance).
 */
function stripPii(event: Sentry.Event): Sentry.Event | null {
  // Remove user email/phone (keep ID only)
  if (event.user) {
    event.user = { id: event.user.id }
  }

  // Scrub request data
  if (event.request) {
    delete event.request.cookies
    delete event.request.headers
    delete event.request.query_string
  }

  // Scrub breadcrumbs (may contain PHI in API responses)
  if (event.breadcrumbs) {
    event.breadcrumbs = event.breadcrumbs.map((crumb) => {
      if (crumb.category === 'fetch' || crumb.category === 'xhr') {
        // Redact API response data
        if (crumb.data && crumb.data.response) {
          crumb.data.response = '[REDACTED]'
        }
      }
      return crumb
    })
  }

  return event
}

/**
 * Initialize Sentry for Vue app.
 */
export function initSentry(app: any, router: any) {
  const dsn = import.meta.env.VITE_SENTRY_DSN

  if (!dsn) {
    console.warn('[Sentry] DSN not configured, error tracking disabled')
    return
  }

  Sentry.init({
    app,
    dsn,
    environment: import.meta.env.MODE,  // "production" or "development"
    integrations: [
      Sentry.browserTracingIntegration({ router }),
      Sentry.replayIntegration(),
    ],
    tracesSampleRate: 0.1,  // 10% of transactions
    replaysSessionSampleRate: 0.1,  // 10% of sessions
    replaysOnErrorSampleRate: 1.0,  // 100% of errors get replay
    beforeSend: stripPii,
  })

  console.log('[Sentry] Initialized for environment:', import.meta.env.MODE)
}
```

3. **Initialize in Vue App** (10 min):

Edit `frontend/src/main.ts`:

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { initSentry } from './monitoring/sentry'  // NEW

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Initialize Sentry AFTER app and router are created
initSentry(app, router)

app.mount('#app')
```

4. **Add Environment Variable** (5 min):

Create `frontend/.env.production`:
```bash
# Sentry Error Tracking (Frontend)
VITE_SENTRY_DSN=https://...@sentry.io/...
```

5. **Test Frontend Error Tracking** (25 min):
   - Create Sentry project "pazpaz-frontend" (or reuse backend project)
   - Copy DSN
   - Add to `frontend/.env.production`
   - Build frontend: `npm run build`
   - Add test button to a Vue component:
```vue
<button @click="throwTestError">Test Sentry</button>

<script setup>
function throwTestError() {
  throw new Error('Test frontend error - if you see this in Sentry, it works!')
}
</script>
```
   - Click button
   - Verify error in Sentry dashboard
   - **CRITICAL CHECK:** Verify no PII in error (check breadcrumbs, request data)

**C. Configuration & Alerts** (30 min):

1. **GitHub Secrets** (10 min):
   - Navigate to https://github.com/your-org/pazpaz/settings/secrets/actions
   - Add secret: `SENTRY_DSN` = `https://...@sentry.io/...`
   - Add secret: `VITE_SENTRY_DSN` = `https://...@sentry.io/...` (can be same or different project)

2. **Sentry Alert Rules** (15 min):
   - Open Sentry project → Alerts → Create Alert Rule
   - **Rule 1:** Email on 500 errors
     - Condition: `http.status_code:500`
     - Action: Email `alerts@pazpaz.app`
   - **Rule 2:** Slack on high error rate (optional)
     - Condition: Error count > 10 in 5 minutes
     - Action: Slack `#alerts` channel

3. **Document DSN Storage** (5 min):
   - Update `backend/.env.example` with comment: `SENTRY_DSN=<get-from-bitwarden>` - Backup DSN in Bitwarden: "Sentry DSN" entry

**Deliverables:**
- ✅ Backend errors visible in Sentry within 30s
- ✅ Frontend errors visible in Sentry within 30s
- ✅ Email alerts configured for critical errors (500 status codes)
- ✅ PII stripping verified: No client names, session notes, emails, or PHI in Sentry events
- ✅ Request IDs propagate to Sentry for correlation with logs

**Time Breakdown:**
- Backend: 1.5 hours
- Frontend: 1 hour
- Configuration: 0.5 hours
**Total:** 3 hours

---

#### Task 1.2: UptimeRobot Configuration (1 hour)

**Reuse:** ✅ Existing `/health` and `/api/v1/health` endpoints

**Steps:**

1. **Create Account** (5 min):
   - Navigate to https://uptimerobot.com
   - Sign up for free account
   - Verify email

2. **Add Monitors** (20 min):
   - **Monitor 1:** API Health Check
     - Type: HTTP(S)
     - URL: `https://pazpaz.app/health`
     - Monitoring Interval: 5 minutes
     - Expected Status Code: 200
   - **Monitor 2:** Frontend Availability
     - Type: HTTP(S)
     - URL: `https://pazpaz.app/`
     - Monitoring Interval: 5 minutes
     - Expected Status Code: 200
   - **Monitor 3:** SSL Certificate Expiration
     - Type: SSL Certificate
     - URL: `https://pazpaz.app`
     - Alert When: Certificate expires in < 7 days

3. **Configure Alerts** (15 min):
   - Add alert contact: `alerts@pazpaz.app` (email)
   - Set alert threshold: Send alert after 3 failures (15 min downtime)
   - Enable: "Send up alert" (notify when service recovers)

4. **Test Downtime Detection** (20 min):
   - **Test 1:** Stop production server (if safe) OR use UptimeRobot "Pause" feature
   - Wait 15 minutes
   - Verify email alert received
   - Restart server / Unpause monitor
   - Verify "UP" notification received
   - **Test 2:** Simulate 503 error (stop database temporarily)
   - Verify UptimeRobot detects 503 status and alerts

**Deliverables:**
- ✅ 3 monitors active and green in UptimeRobot dashboard
- ✅ Email alerts configured and tested
- ✅ Downtime detection verified (15-minute threshold)

**Time:** 1 hour

---

#### Task 1.3: Enhanced Health Endpoint (2 hours)

**Reuse:** ✅ Existing `/health` endpoint, `get_db()` dependency, `get_logger()` utility

**Steps:**

1. **Modify Health Endpoint** (45 min):

Edit `backend/src/pazpaz/main.py:732-735`:

```python
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from pazpaz.db.session import get_db
from pazpaz.core.logging import get_logger

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint for uptime monitoring.

    Verifies:
    - Application is running
    - Database connection is alive

    Returns:
        200: Healthy (all systems operational)
        503: Unhealthy (database unavailable)
    """
    try:
        # Verify database connection with simple query
        result = await db.execute(text("SELECT 1"))
        result.scalar_one()  # Ensure query executed successfully

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(
            "health_check_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
```

2. **Test Healthy State** (15 min):
```bash
# Start all services
docker compose up -d

# Test health endpoint
curl -v http://localhost:8000/health

# Expected response:
# HTTP/1.1 200 OK
# {
#   "status": "healthy",
#   "database": "connected",
#   "timestamp": "2025-11-12T10:30:45.123456"
# }
```

3. **Test Unhealthy State** (30 min):
```bash
# Stop database container
docker compose stop db

# Wait 10 seconds for connection pool to detect failure
sleep 10

# Test health endpoint
curl -v http://localhost:8000/health

# Expected response:
# HTTP/1.1 503 Service Unavailable
# {
#   "detail": "Database connection unavailable",
#   "request_id": "..."
# }

# Restart database
docker compose start db

# Wait for database to be ready
sleep 10

# Verify health restored
curl -v http://localhost:8000/health
# Expected: 200 OK
```

4. **Update nginx Health Check** (15 min):

Edit `docker-compose.prod.yml`, nginx service health check (line 57):

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://api:8000/health"]  # Use backend health check
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

**Why:** Nginx health check should verify backend is healthy, not just that nginx is running.

5. **Verify UptimeRobot Detects 503** (15 min):
   - In UptimeRobot dashboard, view `https://pazpaz.app/health` monitor
   - If status is 503, monitor should show "DOWN" and send alert
   - Verify alert received within 15 minutes

**Deliverables:**
- ✅ `/health` endpoint verifies database connectivity (not just static response)
- ✅ Returns 200 when healthy, 503 when database is down
- ✅ Logs errors with stack trace for debugging
- ✅ UptimeRobot detects 503 errors and alerts
- ✅ nginx health check uses backend health (cascading health checks)

**Time:** 2 hours

---

### Phase 2: Metrics & Dashboards (Week 2, 9 hours) ⏱️ REDUCED from 12 hours

**Time Savings:** 3 hours (Prometheus client + /metrics endpoint + AI metrics already exist)

---

#### Task 2.1: HTTP Request Instrumentation (2.5 hours)

**Reuse:** ✅ Existing Prometheus `/metrics` endpoint, `prometheus-client` library

**Steps:**

1. **Install Instrumentator** (5 min):
```bash
cd backend
uv add prometheus-fastapi-instrumentator
```

2. **Add HTTP Instrumentation** (30 min):

Edit `backend/src/pazpaz/main.py`, add after app initialization (line 190):

```python
from prometheus_fastapi_instrumentator import Instrumentator

# Prometheus HTTP metrics instrumentation (AFTER app initialization)
# Reuses existing /metrics endpoint (backend/src/pazpaz/api/metrics.py)
Instrumentator(
    should_group_status_codes=False,  # Track 200, 201, 404, 500 separately (not 2xx, 4xx)
    should_ignore_untemplated=True,  # Ignore dynamic paths like /api/v1/clients/{uuid}
    should_respect_env_var=True,  # Disable in tests via ENABLE_METRICS=false
    excluded_handlers=["/metrics", "/health"],  # Don't track monitoring endpoints
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
).instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")
```

**Note:** This adds HTTP request metrics to the **existing** `/metrics` endpoint. No new endpoint needed.

3. **Verify Metrics** (15 min):
```bash
# Make some API requests
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/workspaces

# Check metrics endpoint
curl http://localhost:8000/metrics | grep http_

# Expected output (among others):
# http_requests_total{method="GET",handler="/api/v1/health",status="200"} 1.0
# http_request_duration_seconds_bucket{method="GET",handler="/api/v1/health",le="0.1"} 1.0
# http_requests_inprogress{method="GET",handler="/api/v1/workspaces"} 0.0
```

4. **Add Custom Business Metrics** (1 hour):

Create `backend/src/pazpaz/api/business_metrics.py`:

```python
"""Custom business metrics for Prometheus."""

from prometheus_client import Counter, Gauge

# Appointment metrics
appointments_created_total = Counter(
    "appointments_created_total",
    "Total appointments created",
    ["workspace_id"],  # No PII, just UUID
)

appointments_cancelled_total = Counter(
    "appointments_cancelled_total",
    "Total appointments cancelled",
    ["workspace_id", "reason"],  # reason: "client_request", "therapist_cancelled", "no_show"
)

# Session notes metrics
session_notes_saved_total = Counter(
    "session_notes_saved_total",
    "Total SOAP session notes saved",
    ["workspace_id"],
)

# Active users
active_sessions_gauge = Gauge(
    "active_websocket_sessions",
    "Number of active WebSocket connections (real-time updates)",
)

# Workspace metrics
active_workspaces_24h_gauge = Gauge(
    "active_workspaces_24h",
    "Number of workspaces with activity in last 24 hours",
)

__all__ = [
    "appointments_created_total",
    "appointments_cancelled_total",
    "session_notes_saved_total",
    "active_sessions_gauge",
    "active_workspaces_24h_gauge",
]
```

5. **Instrument Appointment Creation** (30 min):

Edit `backend/src/pazpaz/api/appointments.py`, add metrics to create endpoint:

```python
from pazpaz.api.business_metrics import appointments_created_total

@router.post("/", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(...):
    # ... existing code ...

    # Increment appointment counter (NEW)
    appointments_created_total.labels(workspace_id=str(current_user.workspace_id)).inc()

    return appointment
```

Similarly, instrument:
- Appointment cancellation → `appointments_cancelled_total.labels(...).inc()`
- Session note save → `session_notes_saved_total.labels(...).inc()`

6. **Verify Business Metrics** (10 min):
```bash
# Create an appointment via API
curl -X POST http://localhost:8000/api/v1/appointments -H "Content-Type: application/json" -d '{...}'

# Check metrics
curl http://localhost:8000/metrics | grep appointments_created_total

# Expected:
# appointments_created_total{workspace_id="..."} 1.0
```

**Deliverables:**
- ✅ HTTP request metrics (count, duration, in-progress) visible in `/metrics`
- ✅ Business metrics (appointments, sessions, active users) instrumented
- ✅ No PII in metrics (only workspace_id UUIDs)
- ✅ Performance overhead < 2ms per request (validated via p95 latency)

**Time:** 2.5 hours

---

#### Task 2.2: Prometheus + Grafana + Exporters (3 hours)

**Reuse:** ✅ Existing `docker-compose.prod.yml` structure, network configuration

**Steps:**

1. **Extend Docker Compose** (45 min):

Edit `docker-compose.prod.yml`, add at end (before volumes section):

```yaml
  # =============================================================================
  # Prometheus - Metrics Storage & Scraping
  # =============================================================================
  prometheus:
    image: prom/prometheus:latest
    container_name: pazpaz-prometheus
    networks:
      - backend  # Can reach API /metrics endpoint
    # NO ports exposed to host - internal only (access via SSH tunnel)
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
    healthcheck:
      test: ["CMD", "wget", "--spider", "--quiet", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    labels:
      - "app=pazpaz"
      - "component=monitoring"

  # =============================================================================
  # Grafana - Metrics Visualization & Alerting
  # =============================================================================
  grafana:
    image: grafana/grafana:latest
    container_name: pazpaz-grafana
    networks:
      - backend  # Can query Prometheus
    # NO ports exposed to host - access via SSH tunnel: ssh -L 3001:localhost:3000 root@pazpaz.app
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_SERVER_ROOT_URL=http://localhost:3000
      - GF_SECURITY_DISABLE_GRAVATAR=true
      - GF_ANALYTICS_REPORTING_ENABLED=false  # Privacy-first
      - GF_ANALYTICS_CHECK_FOR_UPDATES=false
      - GF_AUTH_ANONYMOUS_ENABLED=false  # No anonymous access
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
    healthcheck:
      test: ["CMD", "wget", "--spider", "--quiet", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    labels:
      - "app=pazpaz"
      - "component=monitoring"

  # =============================================================================
  # PostgreSQL Exporter - Database Metrics for Prometheus
  # =============================================================================
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    container_name: pazpaz-postgres-exporter
    networks:
      - database  # Can reach PostgreSQL
      - backend   # Can be scraped by Prometheus
    environment:
      - DATA_SOURCE_NAME=postgresql://pazpaz:${POSTGRES_PASSWORD}@db:5432/pazpaz?sslmode=disable
    healthcheck:
      test: ["CMD", "wget", "--spider", "--quiet", "http://localhost:9187/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    labels:
      - "app=pazpaz"
      - "component=monitoring"

  # =============================================================================
  # Redis Exporter - Cache Metrics for Prometheus
  # =============================================================================
  redis-exporter:
    image: oliver006/redis_exporter:latest
    container_name: pazpaz-redis-exporter
    networks:
      - database  # Can reach Redis
      - backend   # Can be scraped by Prometheus
    environment:
      - REDIS_ADDR=redis:6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "wget", "--spider", "--quiet", "http://localhost:9121/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    labels:
      - "app=pazpaz"
      - "component=monitoring"
```

Add volumes:

```yaml
volumes:
  # ... existing volumes ...

  # Monitoring volumes
  prometheus-data:
    driver: local
    labels:
      - "app=pazpaz"
      - "type=monitoring"
      - "retention=30d"

  grafana-data:
    driver: local
    labels:
      - "app=pazpaz"
      - "type=monitoring"
```

2. **Create Prometheus Config** (30 min):

Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s  # Scrape targets every 15s
  evaluation_interval: 15s  # Evaluate rules every 15s

scrape_configs:
  # FastAPI application metrics
  - job_name: 'fastapi'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s

  # PostgreSQL database metrics
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Redis cache metrics
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

3. **Create Grafana Data Source** (20 min):

Create `monitoring/grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

4. **Deploy Monitoring Stack** (10 min):
```bash
cd /path/to/pazpaz

# Validate docker-compose syntax
docker compose -f docker-compose.prod.yml config

# Deploy monitoring services
docker compose -f docker-compose.prod.yml up -d prometheus grafana postgres-exporter redis-exporter

# Verify services are healthy
docker compose -f docker-compose.prod.yml ps
```

5. **Verify Prometheus Scraping** (15 min):
```bash
# SSH tunnel to Prometheus (not exposed to internet)
ssh -L 9090:localhost:9090 root@pazpaz.app

# Open in browser: http://localhost:9090

# Check targets:
# Navigate to Status → Targets
# Expected: All targets (fastapi, postgres, redis, prometheus) should be "UP"

# Test query:
# Navigate to Graph
# Query: rate(http_requests_total[5m])
# Expected: Chart showing HTTP request rate
```

6. **Access Grafana** (10 min):
```bash
# SSH tunnel to Grafana
ssh -L 3001:localhost:3000 root@pazpaz.app

# Open in browser: http://localhost:3001

# Login:
# Username: admin
# Password: <GRAFANA_PASSWORD from .env.production>

# Verify Prometheus datasource:
# Configuration → Data Sources → Prometheus
# Click "Test" → Should show "Data source is working"
```

**Deliverables:**
- ✅ Prometheus scraping all targets (API, PostgreSQL, Redis)
- ✅ Grafana connected to Prometheus datasource
- ✅ All services healthy in `docker compose ps`
- ✅ Access via SSH tunnel (not exposed to internet)

**Time:** 3 hours

---

#### Task 2.3: Grafana Dashboards & Alerts (3.5 hours)

**Reuse:** ✅ Existing metrics from AI agent, audit logging, HTTP instrumentation

**Steps:**

1. **Create Application Performance Dashboard** (1 hour):

Create `monitoring/grafana/provisioning/dashboards/application.json` (use Grafana UI to build, then export JSON):

**Panels:**
- **Request Rate:** `rate(http_requests_total[5m])`
- **Response Time (p50, p95, p99):**
  ```promql
  histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))
  histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
  histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
  ```
- **Error Rate (4xx, 5xx):**
  ```promql
  sum(rate(http_requests_total{status=~"4.."}[5m])) by (status)
  sum(rate(http_requests_total{status=~"5.."}[5m])) by (status)
  ```
- **Slowest Endpoints (Top 10):**
  ```promql
  topk(10, avg(rate(http_request_duration_seconds_sum[5m])) by (handler))
  ```

2. **Create Database Performance Dashboard** (45 min):

**Panels:**
- **Connection Pool Usage:** `pg_stat_activity_count / pg_settings_max_connections`
- **Slow Queries (>100ms):** `pg_stat_statements_mean_time_ms`
- **Query Rate:** `rate(pg_stat_database_xact_commit[5m])`
- **Cache Hit Rate:** `pg_stat_database_blks_hit / (pg_stat_database_blks_hit + pg_stat_database_blks_read)`

3. **Create Infrastructure Dashboard** (30 min):

**Panels:**
- **CPU Usage:** `container_cpu_usage_seconds_total`
- **Memory Usage:** `container_memory_usage_bytes`
- **Disk I/O:** `container_fs_io_current`

4. **Create Business Metrics Dashboard** (30 min):

**Panels:**
- **Appointments Created (Hourly):** `increase(appointments_created_total[1h])`
- **Session Notes Saved (Daily):** `increase(session_notes_saved_total[24h])`
- **Active Workspaces:** `active_workspaces_24h`

5. **Create Alert Rules** (45 min):

Create `monitoring/grafana/provisioning/alerting/rules.yml`:

```yaml
apiVersion: 1

groups:
  - name: api_performance
    interval: 1m
    rules:
      - uid: high_api_latency
        title: High API Latency (p95 > 200ms)
        condition: A
        data:
          - refId: A
            queryType: ''
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.2
              refId: A
        annotations:
          summary: "API p95 latency is {{ $value }}s, above 150ms SLA target"
        labels:
          severity: warning
        for: 5m

      - uid: high_error_rate
        title: High 5xx Error Rate
        condition: A
        data:
          - refId: A
            queryType: ''
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
              refId: A
        annotations:
          summary: "{{ $value }} errors/sec in the last 5 minutes"
        labels:
          severity: critical
        for: 5m

  - name: database_health
    interval: 1m
    rules:
      - uid: db_connection_pool_exhausted
        title: Database Connection Pool Nearly Exhausted
        condition: A
        data:
          - refId: A
            queryType: ''
            relativeTimeRange:
              from: 120
              to: 0
            datasourceUid: prometheus
            model:
              expr: pg_stat_activity_count / pg_settings_max_connections > 0.9
              refId: A
        annotations:
          summary: "PostgreSQL connection pool is {{ $value | humanizePercentage }} full"
        labels:
          severity: critical
        for: 2m

  - name: infrastructure
    interval: 5m
    rules:
      - uid: high_memory_usage
        title: Container Memory Usage Above 85%
        condition: A
        data:
          - refId: A
            queryType: ''
            relativeTimeRange:
              from: 600
              to: 0
            datasourceUid: prometheus
            model:
              expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.85
              refId: A
        annotations:
          summary: "Container {{ $labels.name }} memory usage is {{ $value | humanizePercentage }}"
        labels:
          severity: warning
        for: 10m
```

6. **Configure Alert Notifications** (30 min):
   - Grafana UI → Alerting → Contact Points
   - Add Email contact: `alerts@pazpaz.app`
   - Test notification (should receive email)

**Deliverables:**
- ✅ 4 Grafana dashboards (Application, Database, Infrastructure, Business)
- ✅ 5 alert rules configured (latency, errors, DB pool, memory, disk)
- ✅ Email notifications working (tested)

**Time:** 3.5 hours

---

### Phase 3: Advanced Logging (Week 3, 5 hours) - Optional

**Status:** Structured JSON logging already exists, Loki is nice-to-have but not critical

**Decision:** **DEFER to Phase 4** - Current structlog JSON logging is sufficient for MVP. Loki adds complexity without immediate value. Revisit after Phase 1-2 are stable.

**Why Defer:**
- Sentry already captures errors (most critical log events)
- Prometheus captures metrics (performance data)
- Docker JSON logs are searchable via `docker compose logs`
- Loki requires additional services (Loki + Promtail) + maintenance
- **Value/Effort Ratio:** Low (logging works fine without Loki)

**When to Revisit:**
- Need centralized log search across multiple servers (scaling beyond 1 server)
- Need log retention > 7 days (Docker log rotation is limited)
- Security team requires log aggregation for compliance audits

---

## Summary: Total Implementation Effort

| Phase | Original Estimate | Revised Estimate | Savings | Status |
|-------|-------------------|------------------|---------|--------|
| **Phase 1: Essential Monitoring** | 8 hours | **6 hours** | 2 hours | **PRIORITY 1** |
| **Phase 2: Metrics & Dashboards** | 12 hours | **9 hours** | 3 hours | **PRIORITY 2** |
| **Phase 3: Advanced Logging** | 8 hours | **DEFERRED** | 8 hours | **Optional** |
| **Total** | 28 hours | **15 hours** | **13 hours (46% reduction)** | |

---

## Key Reusable Components

| Component | Location | Lines | Value |
|-----------|----------|-------|-------|
| **Health Endpoints** | `main.py:732-742` | 11 | **ENHANCE** (add DB check) |
| **Prometheus /metrics** | `api/metrics.py:10-47` | 38 | **REUSE** as-is |
| **AI Metrics** | `ai/metrics.py` | 138 | **PATTERN** for new metrics |
| **Structured Logging** | `core/logging.py` | 124 | **REUSE** unchanged |
| **Request Logging Middleware** | `main.py:328-393` | 66 | **INTEGRATE** with Sentry |
| **PHI Constants** | `main.py:404-420` | 17 | **REUSE** for PII stripping |
| **Docker Compose** | `docker-compose.prod.yml` | 698 | **EXTEND** with monitoring |
| **Total Reusable Code** | | **1,092 lines** | **46% time savings** |

---

## Next Steps

1. **Review & Approve** this implementation guide
2. **Phase 1:** Implement essential monitoring (6 hours, 1-2 days)
3. **Validate:** Verify Sentry, UptimeRobot, and health checks working
4. **Phase 2:** Implement metrics & dashboards (9 hours, 2-3 days)
5. **Validate:** Verify Prometheus scraping, Grafana dashboards, alerts
6. **Phase 3:** Optional (defer until post-MVP)

**Total Time to Production-Ready Monitoring:** **15 hours (2 weeks)**

---

**Document Status:** ✅ Ready for Implementation
**Last Reviewed:** 2025-11-12
**Next Review:** After Phase 1 completion
