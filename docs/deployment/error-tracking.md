# Error Tracking with Sentry

## Overview

PazPaz uses Sentry for real-time error tracking and performance monitoring in production. This document covers the setup, configuration, and best practices for integrating Sentry with both backend (FastAPI) and frontend (Vue 3) applications.

## Architecture

```
Application Error → Sentry SDK → Sentry Cloud → Alert Rules → Notifications
        ↓                ↓              ↓              ↓            ↓
   Capture Context   Send Event    Process/Store   Evaluate    Email/Slack
```

## Sentry Account Setup

### 1. Create Account

1. Visit [Sentry.io](https://sentry.io)
2. Sign up for free account (10K events/month free)
3. Create organization: `pazpaz`
4. Verify email and enable 2FA

### 2. Create Projects

Create separate projects for better organization:

```yaml
Projects:
  - pazpaz-backend (Python/FastAPI)
  - pazpaz-frontend (JavaScript/Vue)
  - pazpaz-worker (Python/ARQ)
```

### 3. Get DSN Keys

Each project has a unique DSN (Data Source Name):

```bash
# Backend DSN
SENTRY_DSN_BACKEND=https://abc123@o123456.ingest.sentry.io/1234567

# Frontend DSN
SENTRY_DSN_FRONTEND=https://def456@o123456.ingest.sentry.io/2345678

# Worker DSN
SENTRY_DSN_WORKER=https://ghi789@o123456.ingest.sentry.io/3456789
```

## Backend Integration (FastAPI)

### 1. Install Dependencies

```bash
# Add to backend/pyproject.toml
uv add sentry-sdk[fastapi]
```

### 2. Configure Sentry

```python
# backend/src/pazpaz/core/sentry.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import logging
from pazpaz.core.config import settings

def init_sentry():
    """Initialize Sentry error tracking for production"""

    if not settings.SENTRY_DSN or settings.ENVIRONMENT == "development":
        logging.info("Sentry not initialized (development or no DSN)")
        return

    # Configure integrations
    integrations = [
        FastApiIntegration(
            transaction_style="endpoint",
            failed_request_status_codes=[400, 401, 403, 404, 405, 500, 502, 503, 504],
        ),
        SqlalchemyIntegration(),
        RedisIntegration(),
        LoggingIntegration(
            level=logging.INFO,  # Capture info and above
            event_level=logging.ERROR  # Send errors as events
        ),
    ]

    # Initialize Sentry
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.VERSION,
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,  # 10% profiling
        integrations=integrations,

        # Performance monitoring
        enable_tracing=True,

        # Session tracking
        release_health=True,

        # Filtering
        before_send=before_send_filter,
        before_send_transaction=before_send_transaction_filter,

        # Options
        attach_stacktrace=True,
        send_default_pii=False,  # HIPAA: Don't send PII
        max_breadcrumbs=50,
        debug=False,

        # Ignore certain errors
        ignore_errors=[
            "KeyboardInterrupt",
            "SystemExit",
            "GeneratorExit",
            "asyncio.CancelledError",
        ],
    )

def before_send_filter(event, hint):
    """Filter sensitive data before sending to Sentry"""

    # HIPAA: Remove any PII from events
    if "request" in event:
        request = event["request"]

        # Sanitize headers
        if "headers" in request:
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                if header in request["headers"]:
                    request["headers"][header] = "[REDACTED]"

        # Sanitize data
        if "data" in request:
            request["data"] = sanitize_data(request["data"])

    # Sanitize user context
    if "user" in event:
        event["user"] = {
            "id": event["user"].get("id"),
            # Don't include email, username, or IP
        }

    # Add custom context
    event["tags"]["service"] = "backend"

    return event

def before_send_transaction_filter(event, hint):
    """Filter performance transactions"""

    # Skip health check transactions
    if event.get("transaction") == "/api/v1/health":
        return None

    return event

def sanitize_data(data):
    """Remove sensitive fields from data"""
    if isinstance(data, dict):
        sensitive_fields = [
            "password", "token", "secret", "ssn",
            "credit_card", "api_key", "phone", "email",
            "date_of_birth", "medical_record"
        ]

        sanitized = {}
        for key, value in data.items():
            if any(field in key.lower() for field in sensitive_fields):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [sanitize_data(item) if isinstance(item, dict) else item for item in value]
            else:
                sanitized[key] = value

        return sanitized

    return data
```

### 3. Initialize in Application

```python
# backend/src/pazpaz/main.py
from fastapi import FastAPI
from pazpaz.core.sentry import init_sentry

def create_app():
    # Initialize Sentry before creating app
    init_sentry()

    app = FastAPI()

    # Add Sentry context middleware
    @app.middleware("http")
    async def add_sentry_context(request, call_next):
        # Add user context
        if hasattr(request.state, "user"):
            sentry_sdk.set_user({
                "id": str(request.state.user.id),
                "workspace_id": str(request.state.user.workspace_id),
            })

        # Add request context
        sentry_sdk.set_tag("endpoint", request.url.path)
        sentry_sdk.set_context("request", {
            "method": request.method,
            "url": str(request.url),
            "client_host": request.client.host if request.client else None,
        })

        response = await call_next(request)
        return response

    return app
```

### 4. Environment Variables

```bash
# .env.production
SENTRY_DSN=https://abc123@o123456.ingest.sentry.io/1234567
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
SENTRY_TRACES_SAMPLE_RATE=0.1
```

## Frontend Integration (Vue 3)

### 1. Install Dependencies

```bash
# frontend/
npm install --save @sentry/vue
```

### 2. Configure Sentry

```typescript
// frontend/src/sentry.ts
import * as Sentry from "@sentry/vue";
import { BrowserTracing } from "@sentry/tracing";
import { App } from "vue";
import router from "./router";

export function initSentry(app: App) {
  // Don't initialize in development
  if (import.meta.env.DEV) {
    console.log("Sentry not initialized in development");
    return;
  }

  Sentry.init({
    app,
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_APP_ENV || "production",
    release: import.meta.env.VITE_APP_VERSION,

    integrations: [
      new BrowserTracing({
        routingInstrumentation: Sentry.vueRouterInstrumentation(router),
        tracingOrigins: ["localhost", "pazpaz.com", /^\//],
      }),
    ],

    // Performance monitoring
    tracesSampleRate: 0.1,

    // Session replay (Pro feature)
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,

    // Filtering
    beforeSend(event, hint) {
      // HIPAA: Filter sensitive data
      if (event.request?.cookies) {
        event.request.cookies = "[REDACTED]";
      }

      // Remove PII from errors
      if (event.exception?.values) {
        event.exception.values = event.exception.values.map(sanitizeException);
      }

      return event;
    },

    // Ignore certain errors
    ignoreErrors: [
      "ResizeObserver loop limit exceeded",
      "Non-Error promise rejection captured",
      /Failed to fetch/,
    ],

    // Don't send PII
    sendDefaultPii: false,
  });
}

function sanitizeException(exception: any) {
  // Remove sensitive data from exception values
  const sanitized = { ...exception };

  if (sanitized.value) {
    // Remove emails
    sanitized.value = sanitized.value.replace(
      /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
      "[EMAIL]"
    );

    // Remove phone numbers
    sanitized.value = sanitized.value.replace(
      /\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/g,
      "[PHONE]"
    );
  }

  return sanitized;
}
```

### 3. Initialize in Main

```typescript
// frontend/src/main.ts
import { createApp } from "vue";
import App from "./App.vue";
import { initSentry } from "./sentry";

const app = createApp(App);

// Initialize Sentry
initSentry(app);

app.mount("#app");
```

### 4. Environment Variables

```bash
# frontend/.env.production
VITE_SENTRY_DSN=https://def456@o123456.ingest.sentry.io/2345678
VITE_APP_ENV=production
VITE_APP_VERSION=1.0.0
```

## Worker Integration (ARQ)

```python
# backend/src/pazpaz/workers/sentry.py
import sentry_sdk
from sentry_sdk.integrations.redis import RedisIntegration
from pazpaz.core.config import settings

def init_worker_sentry():
    """Initialize Sentry for background workers"""

    if not settings.SENTRY_DSN_WORKER:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN_WORKER,
        environment=settings.ENVIRONMENT,
        integrations=[RedisIntegration()],
        traces_sample_rate=0.1,
        before_send=filter_worker_events,
    )

def filter_worker_events(event, hint):
    """Filter worker-specific events"""
    event["tags"]["service"] = "worker"
    return event

# In worker startup
async def startup(ctx):
    init_worker_sentry()
    # ... other startup tasks
```

## Alert Configuration

### 1. Alert Rules

Create alert rules in Sentry dashboard:

```yaml
Critical Alerts:
  - Name: High Error Rate
    Conditions:
      - Event frequency > 10 in 5 minutes
      - Environment = production
    Actions:
      - Send email to ops@pazpaz.com
      - Send Slack to #alerts-critical

  - Name: New Error Type
    Conditions:
      - First seen error
      - Level = error or fatal
      - Environment = production
    Actions:
      - Send email to dev@pazpaz.com

  - Name: Performance Degradation
    Conditions:
      - P95 transaction duration > 1s
      - Transaction count > 100
    Actions:
      - Send Slack to #alerts-performance

Warning Alerts:
  - Name: Elevated Error Rate
    Conditions:
      - Event frequency > 5 in 10 minutes
      - Environment = production
    Actions:
      - Send Slack to #alerts-warning

  - Name: Memory Leak Detection
    Conditions:
      - Memory usage increasing pattern
      - Duration > 1 hour
    Actions:
      - Send email to dev@pazpaz.com
```

### 2. Slack Integration

```yaml
Webhook URL: https://hooks.slack.com/services/T00/B00/XXX
Channel: #alerts-production
Username: Sentry Bot

Message Template:
🚨 *{{rule.name}}*
Project: {{project.name}}
Level: {{level}}
Error: {{title}}
User: {{user.id}}
URL: {{url}}
```

### 3. Email Templates

```yaml
Subject: [{{level}}] {{rule.name}} - {{project.name}}

Body:
Error Details:
- Message: {{title}}
- Level: {{level}}
- Project: {{project.name}}
- Environment: {{environment}}
- Release: {{release}}
- User: {{user.id}}
- Time: {{datetime}}

View in Sentry: {{url}}

Stack Trace:
{{culprit}}
{{message}}
```

## Testing Error Tracking

### Test Script

```bash
#!/bin/bash
# scripts/test-error-tracking.sh

set -euo pipefail

ENVIRONMENT=${1:-local}
BASE_URL="http://localhost:8000"

if [[ "$ENVIRONMENT" == "production" ]]; then
    BASE_URL="https://api.pazpaz.com"
fi

echo "Testing Sentry error tracking on $ENVIRONMENT..."

# Test backend error
echo "1. Testing backend error capture..."
curl -X POST "$BASE_URL/api/v1/test/error" \
     -H "Content-Type: application/json" \
     -d '{"error_type": "test", "message": "Test error from script"}'

# Test frontend error (if accessible)
echo "2. Testing frontend error capture..."
cat << 'EOF' > /tmp/test-sentry.html
<!DOCTYPE html>
<html>
<head>
    <script src="https://browser.sentry-cdn.com/7.0.0/bundle.min.js"></script>
    <script>
        Sentry.init({
            dsn: "YOUR_FRONTEND_DSN",
            environment: "test"
        });

        // Trigger test error
        throw new Error("Test error from test script");
    </script>
</head>
<body>Testing Sentry...</body>
</html>
EOF

echo "3. Checking Sentry dashboard for errors..."
echo "   Visit https://sentry.io/organizations/pazpaz/issues/"

echo "Test complete! Check Sentry dashboard for captured errors."
```

### Test Endpoints

```python
# backend/src/pazpaz/api/test.py (DO NOT DEPLOY TO PRODUCTION)
from fastapi import APIRouter, HTTPException
import sentry_sdk

router = APIRouter(prefix="/test", tags=["test"])

@router.post("/error")
async def trigger_test_error(error_type: str = "test"):
    """Endpoint to test Sentry error capture"""

    if error_type == "exception":
        raise Exception("Test exception for Sentry")
    elif error_type == "http":
        raise HTTPException(status_code=500, detail="Test HTTP error")
    elif error_type == "capture":
        sentry_sdk.capture_exception(Exception("Test captured exception"))
        return {"message": "Error captured"}
    elif error_type == "message":
        sentry_sdk.capture_message("Test message", level="error")
        return {"message": "Message captured"}
    else:
        1 / 0  # Division by zero
```

## Performance Monitoring

### Transaction Tracking

```python
# backend/src/pazpaz/api/appointments.py
import sentry_sdk

@router.get("/appointments")
async def list_appointments():
    with sentry_sdk.start_transaction(op="query", name="list_appointments"):
        with sentry_sdk.start_span(op="db", description="fetch_appointments"):
            appointments = await db.fetch_appointments()

        with sentry_sdk.start_span(op="serialize", description="serialize_response"):
            response = serialize_appointments(appointments)

        return response
```

### Custom Metrics

```python
# Track custom metrics
sentry_sdk.set_measurement("appointment.count", len(appointments))
sentry_sdk.set_measurement("response.size", len(response))
sentry_sdk.set_tag("feature", "appointments")
```

## Dashboard Configuration

### 1. Issues Dashboard

Configure views:
- Unresolved Issues
- High Volume Issues
- Recent Regressions
- Issues by User
- Issues by Release

### 2. Performance Dashboard

Monitor metrics:
- Transaction Summary (p50, p95, p99)
- Slowest Endpoints
- Database Query Performance
- API Response Times
- Frontend Web Vitals

### 3. Release Health

Track:
- Crash-free sessions
- Error rate by release
- Adoption rate
- Session duration
- User satisfaction

## Best Practices

### 1. Error Handling

```python
# Good error handling
try:
    result = await risky_operation()
except SpecificError as e:
    # Log with context
    sentry_sdk.capture_exception(e, extras={
        "operation": "risky_operation",
        "context": {"user_id": user_id}
    })
    # Handle gracefully
    return error_response()
```

### 2. Breadcrumbs

```python
# Add breadcrumbs for debugging
sentry_sdk.add_breadcrumb(
    category="auth",
    message="User login attempt",
    level="info",
    data={"user_id": user_id}
)
```

### 3. User Context

```python
# Set user context for better debugging
sentry_sdk.set_user({
    "id": user_id,
    "workspace_id": workspace_id,
    # Don't include PII
})
```

### 4. Tags and Context

```python
# Add tags for filtering
sentry_sdk.set_tag("feature", "appointments")
sentry_sdk.set_tag("workspace", workspace_id)

# Add extra context
sentry_sdk.set_context("appointment", {
    "id": appointment_id,
    "type": appointment_type,
    "status": status
})
```

## HIPAA Compliance

### Data Sanitization Rules

1. **Never send PHI to Sentry:**
   - Patient names
   - Dates of birth
   - SSN/ID numbers
   - Medical record numbers
   - Diagnosis codes
   - Treatment details

2. **Sanitize all data:**
   ```python
   # Use before_send hooks
   # Redact sensitive fields
   # Strip PII from stack traces
   ```

3. **Use generic user IDs:**
   ```python
   # Good
   sentry_sdk.set_user({"id": "user_123"})

   # Bad
   sentry_sdk.set_user({
       "email": "john.doe@example.com",
       "username": "johndoe"
   })
   ```

## Troubleshooting

### Common Issues

**1. Events not appearing:**
```bash
# Check DSN configuration
echo $SENTRY_DSN

# Test connection
curl https://sentry.io/api/0/projects/

# Check SDK initialization
grep -r "sentry_sdk.init" backend/src/
```

**2. High event volume:**
```python
# Adjust sample rates
traces_sample_rate=0.01  # 1% sampling
```

**3. Missing context:**
```python
# Ensure middleware is setting context
# Check user authentication flow
# Verify workspace isolation
```

## Cost Management

### Free Tier Limits
- 5K errors/month
- 10K transactions/month
- 1 project
- 1 user

### Optimization Tips

1. **Filter noise:**
   ```python
   ignore_errors=[
       "BrokenPipeError",
       "ConnectionResetError",
   ]
   ```

2. **Sample transactions:**
   ```python
   traces_sample_rate=0.1  # 10% sampling
   ```

3. **Use quotas:**
   - Set project quotas
   - Configure rate limits
   - Archive old issues

## Related Documentation

- [Logging Configuration](./logging-configuration.md)
- [Uptime Monitoring](./uptime-monitoring.md)
- [Performance Monitoring](./performance-monitoring.md)
- [Infrastructure Security](./INFRASTRUCTURE_SECURITY_CHECKLIST.md)

---

**Last Updated:** 2024-10-24
**Version:** 1.0.0
**Status:** Ready for Implementation