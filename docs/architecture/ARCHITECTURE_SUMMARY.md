# Backend Architecture Summary

**Document:** Full architecture details in [BACKEND_ARCHITECTURE_DESIGN.md](./BACKEND_ARCHITECTURE_DESIGN.md)
**Date:** 2025-10-03

## Quick Reference

This document provides a high-level summary of the backend architecture for three features:
1. Session Documentation (SOAP Notes)
2. Plan of Care
3. Email Reminders

---

## Feature 1: SOAP Notes - Key Highlights

### Data Model
- **Session** table: SOAP fields (Subjective, Objective, Assessment, Plan)
- **SessionAttachment** table: File metadata (actual files in S3/MinIO)
- Status: `DRAFT` → `FINALIZED` → `ARCHIVED`
- 1:1 relationship with Appointment (one session per appointment)

### API Endpoints
```
POST   /api/v1/sessions                              # Create draft
GET    /api/v1/sessions                              # List (paginated)
GET    /api/v1/sessions/{id}                         # Get details
PUT    /api/v1/sessions/{id}                         # Autosave
PATCH  /api/v1/sessions/{id}/finalize                # Finalize
POST   /api/v1/sessions/{id}/attachments             # Upload file
GET    /api/v1/sessions/{id}/attachments/{id}        # Get presigned URL
POST   /api/v1/sessions/sync                         # Offline sync
```

### Critical Decisions

**File Storage:**
- Store files in MinIO/S3 (not database)
- Generate presigned URLs (15-minute expiration)
- Max file size: 10MB
- Allowed types: JPG, PNG, PDF
- Storage path: `{workspace_id}/{session_id}/{uuid}_{filename}`

**Autosave:**
- `PUT /sessions/{id}` supports partial updates
- No conflict resolution needed (last-write-wins for single therapist)
- Update `updated_at` timestamp on each save

**Offline Sync:**
- Client sends batch of offline sessions with client-generated IDs
- Server creates sessions and returns mapping (client_id → server_id)
- Handle conflicts (duplicate appointment sessions)

**Performance:**
- Index: `(workspace_id, appointment_id)` for lookups
- Index: `(workspace_id, status)` for filtering
- Cache session responses for 5 minutes
- Target: GET endpoints p95 < 150ms

---

## Feature 2: Plan of Care - Key Highlights

### Data Model
- **PlanOfCare** table: Treatment plan with goals, diagnosis, dates
- **PlanMilestone** table: Specific checkpoints (ordered)
- Status: `ACTIVE` → `COMPLETED` / `DISCONTINUED`
- Milestone status: `PENDING` → `IN_PROGRESS` → `ACHIEVED` / `DISCONTINUED`

### API Endpoints
```
POST   /api/v1/plans                                 # Create plan
GET    /api/v1/plans                                 # List plans
PUT    /api/v1/plans/{id}                            # Update plan
POST   /api/v1/plans/{id}/milestones                 # Create milestone
GET    /api/v1/plans/{id}/milestones                 # List milestones
PUT    /api/v1/plans/{id}/milestones/{mid}           # Update milestone

GET    /api/v1/clients/{id}/timeline                 # Chronological events
```

### Timeline Endpoint

**Aggregates events from:**
- Appointments (scheduled, completed, cancelled)
- Sessions (SOAP notes created/finalized)
- Plans of Care (created, updated, completed)
- Milestones (achieved)

**Response:**
```json
{
  "client_id": "uuid",
  "events": [
    {
      "event_type": "session",
      "event_date": "2025-10-01T10:00:00Z",
      "title": "SOAP Note - Lower back pain treatment",
      "description": "Completed session",
      "session_id": "uuid"
    },
    {
      "event_type": "milestone_achieved",
      "event_date": "2025-09-28T14:00:00Z",
      "title": "Pain reduced to 5/10",
      "milestone_id": "uuid"
    }
  ],
  "total_events": 45
}
```

**Performance:**
- Fetch all entities in parallel using `asyncio.gather`
- Limit to last 100 events by default
- Cache timeline for 10 minutes
- Target: p95 < 200ms

---

## Feature 3: Email Reminders - Key Highlights

### Data Model
- **ReminderConfiguration** table: Workspace settings (e.g., "24h before", "1h before")
- **ReminderLog** table: Delivery audit trail (sent/failed/bounced)

### Background Job Architecture

**Queue System:** Redis + `arq` (async task queue)

**Scheduler (Cron Job):**
- Runs every 5 minutes
- Finds appointments needing reminders
- Queues email tasks
- Creates `ReminderLog` entries with status `PENDING`

**Email Task:**
- Async SMTP delivery via `aiosmtplib`
- Retries: 3 attempts with exponential backoff
- Updates `ReminderLog` status: `SENT` / `FAILED` / `BOUNCED`
- Timeout: 30 seconds

**Scheduler Logic:**
```python
# For each ReminderConfiguration (e.g., hours_before=24):
target_time = now + timedelta(hours=24)
window = target_time ± 5 minutes

# Find appointments in window
appointments = query(
    scheduled_start BETWEEN window_start AND window_end,
    status = SCHEDULED,
)

# Check if reminder already sent (idempotency)
if not ReminderLog.exists(appointment_id, hours_before=24):
    queue_email_task(appointment)
```

### API Endpoints
```
POST   /api/v1/reminders/configurations              # Create config
GET    /api/v1/reminders/configurations              # List configs
GET    /api/v1/reminders/logs                        # Delivery logs
GET    /api/v1/appointments/{id}/reminders           # Reminders for appointment
```

---

## Cross-Cutting Concerns

### 1. Workspace Scoping (CRITICAL)

**Every endpoint MUST:**
```python
@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
    db: AsyncSession = Depends(get_db),
):
    # Always use get_or_404 with workspace_id
    session = await get_or_404(db, Session, session_id, workspace_id)
```

**Every database query MUST:**
```python
query = select(Session).where(
    Session.id == session_id,
    Session.workspace_id == workspace_id,  # CRITICAL
)
```

### 2. PHI Encryption

**Encrypt at rest:**
- Session: `subjective`, `objective`, `assessment`, `plan`
- PlanOfCare: `diagnosis`, `goals`
- PlanMilestone: `description`, `notes`

**Strategy:**
- PostgreSQL `pgcrypto` OR application-level encryption
- Decision pending (recommend `pgcrypto` for transparency)

### 3. Audit Logging

**Log all operations:**
```python
AuditEvent(
    workspace_id=workspace_id,
    user_id=user_id,
    action="session.create",  # create/read/update/delete
    entity_type="Session",
    entity_id=session_id,
    timestamp=now(),
)

# NEVER log PHI content - log IDs only
```

### 4. Error Handling

**Use RFC 7807 Problem Details format:**
```json
{
  "type": "https://pazpaz.com/errors/session-already-exists",
  "title": "Session Already Exists",
  "status": 409,
  "detail": "A session already exists for appointment {id}"
}
```

### 5. Rate Limiting

**Per workspace limits:**
- Write operations (POST/PUT/PATCH/DELETE): 100 requests/minute
- Read operations (GET): 1000 requests/minute

---

## Dependencies to Add

```bash
# From backend/ directory:
uv add boto3           # S3/MinIO client for file storage
uv add arq             # Async task queue for reminders
uv add aiosmtplib      # Async SMTP for email delivery
```

---

## Configuration Updates Needed

```python
# backend/src/pazpaz/core/config.py

class Settings(BaseSettings):
    # ... existing settings

    # S3/MinIO (for attachments)
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "pazpaz-attachments"

    # File uploads
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: list[str] = ["image/jpeg", "image/png", "application/pdf"]

    # Background jobs (ARQ)
    arq_redis_url: str = "redis://localhost:6379/0"

    # Reminders
    reminder_scheduler_interval_minutes: int = 5
```

---

## Docker Compose Updates Needed

```yaml
# docker-compose.yml

services:
  # ... existing services

  # MinIO for file storage
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

  # ARQ worker for background jobs
  worker:
    build:
      context: ./backend
    command: arq pazpaz.workers.worker.WorkerSettings
    depends_on:
      - db
      - redis
    environment:
      DATABASE_URL: postgresql+asyncpg://pazpaz:pazpaz@db:5432/pazpaz
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./backend:/app

volumes:
  minio_data:
```

---

## Implementation Phases (Estimated Timeline)

| Phase | Feature | Duration | Dependencies |
|-------|---------|----------|--------------|
| 1 | SOAP Notes Core (models, CRUD, tests) | 3-4 days | - |
| 2 | File Attachments (S3/MinIO integration) | 2-3 days | Phase 1, MinIO setup |
| 3 | Autosave & Offline Sync | 2 days | Phase 1 |
| 4 | Plan of Care (models, CRUD, timeline) | 3-4 days | - |
| 5 | Email Reminders (background jobs) | 4-5 days | ARQ setup |
| 6 | Security & Audit (encryption, logging) | 3-4 days | All phases |

**Total Estimated Duration:** 17-22 days (3.5-4.5 weeks)

---

## Testing Requirements

### Must-Have Tests

**Unit Tests:**
- [ ] Session service (create, update, finalize)
- [ ] Storage service (presigned URLs, validation)
- [ ] Plan service (CRUD, milestone ordering)
- [ ] Reminder scheduler (time window logic, idempotency)

**Integration Tests:**
- [ ] Session API endpoints (CRUD, autosave)
- [ ] File upload/download flow
- [ ] Timeline aggregation (correct ordering)
- [ ] Reminder email delivery

**Workspace Isolation Tests:**
- [ ] Cannot access sessions from other workspace
- [ ] Cannot access plans from other workspace
- [ ] Storage keys include workspace_id

**Performance Tests:**
- [ ] Session list endpoint: p95 < 150ms
- [ ] Timeline endpoint: p95 < 200ms
- [ ] File upload presigned URL: p95 < 50ms

---

## Security Checklist

- [ ] All endpoints enforce workspace scoping
- [ ] PHI fields encrypted at rest
- [ ] File uploads validated (type, size)
- [ ] Presigned URLs expire in 15 minutes
- [ ] S3 bucket not publicly accessible
- [ ] Audit logging for all data modifications
- [ ] Rate limiting per workspace
- [ ] Error responses don't leak PII
- [ ] Background jobs retry with backoff

---

## Next Steps

1. **Review with `database-architect`:**
   - Validate schema design (indexes, relationships)
   - Confirm encryption strategy (pgcrypto vs app-level)
   - Review migration approach

2. **Review with `security-auditor`:**
   - PHI protection patterns
   - File upload security
   - Audit logging completeness
   - Workspace isolation enforcement

3. **Begin Implementation:**
   - Start with Phase 1 (SOAP Notes Core)
   - Set up MinIO and ARQ infrastructure
   - Write database migrations
   - Implement service layer with tests

---

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Files in S3/MinIO (not DB) | Scalability, cost, performance |
| Presigned URLs (15min expiration) | Secure access without auth on S3 |
| Autosave = last-write-wins | Single therapist editing (no conflicts) |
| Timeline aggregation at query time | Real-time accuracy, simpler than materialized view |
| ARQ for background jobs | Async-native, integrates with FastAPI/SQLAlchemy |
| Cron scheduler every 5 minutes | Balance between timeliness and query load |
| ReminderLog for idempotency | Prevent duplicate sends, audit trail |

---

## Questions for Product/Team

1. **PHI Encryption:**
   - Preference for pgcrypto (database-level) vs application-level encryption?
   - Key management strategy?

2. **File Attachments:**
   - Should files persist after session deletion (soft delete)?
   - Virus scanning required before storage?

3. **Offline Sync:**
   - How to handle conflicts if appointment was deleted while offline?
   - Max age for offline sessions (e.g., reject if > 7 days old)?

4. **Email Reminders:**
   - Email template customization per workspace?
   - SMS reminders in V1 or defer to V2?
   - Unsubscribe mechanism required?

5. **Plan of Care:**
   - Multiple active plans per client allowed?
   - Archive/history of discontinued plans?

---

## API Endpoint Summary

### SOAP Notes (8 endpoints)
```
POST   /api/v1/sessions
GET    /api/v1/sessions
GET    /api/v1/sessions/{id}
PUT    /api/v1/sessions/{id}
PATCH  /api/v1/sessions/{id}/finalize
DELETE /api/v1/sessions/{id}
POST   /api/v1/sessions/{id}/attachments
GET    /api/v1/sessions/{id}/attachments/{aid}
POST   /api/v1/sessions/sync
```

### Plan of Care (7 endpoints)
```
POST   /api/v1/plans
GET    /api/v1/plans
GET    /api/v1/plans/{id}
PUT    /api/v1/plans/{id}
DELETE /api/v1/plans/{id}
POST   /api/v1/plans/{id}/milestones
PUT    /api/v1/plans/{id}/milestones/{mid}
GET    /api/v1/clients/{id}/timeline
```

### Email Reminders (3 endpoints)
```
POST   /api/v1/reminders/configurations
GET    /api/v1/reminders/configurations
GET    /api/v1/reminders/logs
```

**Total New Endpoints:** 18

---

For complete implementation details, code examples, and data models, see:
[BACKEND_ARCHITECTURE_DESIGN.md](./BACKEND_ARCHITECTURE_DESIGN.md)
