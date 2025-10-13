# Session Soft Delete Purge Job Documentation

## Overview

This document describes the **automated purge job** that will be implemented in Week 5 (Background Jobs) of the SECURITY_FIRST_IMPLEMENTATION_PLAN. The purge job permanently deletes session notes that have exceeded their 30-day grace period after soft deletion.

## Current Implementation Status

**✅ Completed (Week 3):**
- Database schema with soft delete fields (`deleted_at`, `deleted_by_user_id`, `deleted_reason`, `permanent_delete_after`)
- Soft delete functionality in `DELETE /api/v1/sessions/{id}` endpoint
- Restore functionality in `POST /api/v1/sessions/{id}/restore` endpoint
- 30-day grace period calculation (automatically set when session is soft-deleted)
- Comprehensive audit logging for soft deletes and restorations
- Integration with appointment deletion flow

**⏳ Pending (Week 5):**
- Daily background job to automatically purge expired sessions
- Scheduled task orchestration
- Audit log snapshot before permanent deletion

## Business Requirements

### Soft Delete Flow
1. Therapist deletes an appointment with attached session notes
2. Session note is soft-deleted (not permanently removed)
3. `deleted_at`, `deleted_by_user_id`, and `permanent_delete_after` (deleted_at + 30 days) are set
4. Session note is excluded from normal queries (`WHERE deleted_at IS NULL`)
5. Session note can be restored within 30 days via `POST /api/v1/sessions/{id}/restore`

### Purge Flow
1. Daily background job runs (suggested time: 2:00 AM UTC)
2. Queries for sessions where `permanent_delete_after < NOW()`
3. For each expired session:
   - Creates audit log snapshot with full metadata
   - Permanently deletes session and related data (attachments, versions)
   - Logs deletion in audit trail
4. Sends summary report (optional) to admin/monitoring

## Database Schema

### Soft Delete Columns (Already Implemented)

```sql
-- sessions table
ALTER TABLE sessions ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE sessions ADD COLUMN deleted_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE sessions ADD COLUMN deleted_reason TEXT;
ALTER TABLE sessions ADD COLUMN permanent_delete_after TIMESTAMP WITH TIME ZONE;

-- Index for efficient purge job queries
CREATE INDEX ix_sessions_permanent_delete_after
ON sessions (permanent_delete_after)
WHERE permanent_delete_after IS NOT NULL;
```

### Relevant Fields
- `deleted_at`: Timestamp when session was soft-deleted
- `deleted_by_user_id`: User who deleted the session
- `deleted_reason`: Optional reason provided during deletion
- `permanent_delete_after`: Calculated as `deleted_at + 30 days`

## Purge Job Implementation Plan

### 1. Query for Expired Sessions

```python
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.session import Session

async def get_expired_sessions(db: AsyncSession) -> list[Session]:
    """
    Query sessions that have exceeded their 30-day grace period.

    Uses ix_sessions_permanent_delete_after index for efficiency.
    """
    now = datetime.now(UTC)

    query = (
        select(Session)
        .where(
            Session.deleted_at.isnot(None),
            Session.permanent_delete_after < now,
        )
        .order_by(Session.permanent_delete_after.asc())
    )

    result = await db.execute(query)
    return result.scalars().all()
```

### 2. Create Audit Log Snapshot

Before permanently deleting, capture complete metadata for forensic review:

```python
from pazpaz.models.audit_event import AuditAction, ResourceType
from pazpaz.services.audit_service import create_audit_event

async def create_purge_audit_log(
    db: AsyncSession,
    session: Session,
) -> None:
    """
    Create comprehensive audit log before permanent deletion.

    IMPORTANT: Do NOT log PHI (SOAP fields). Log metadata only.
    """
    await create_audit_event(
        db=db,
        user_id=session.deleted_by_user_id,  # User who originally deleted
        workspace_id=session.workspace_id,
        action=AuditAction.DELETE,
        resource_type=ResourceType.SESSION,
        resource_id=session.id,
        metadata={
            "purge": True,
            "purge_reason": "30_day_grace_period_expired",
            "deleted_at": session.deleted_at.isoformat(),
            "permanent_delete_after": session.permanent_delete_after.isoformat(),
            "deletion_reason": session.deleted_reason,
            "was_finalized": session.finalized_at is not None,
            "amendment_count": session.amendment_count,
            "had_attachments": len(session.attachments) > 0,
            "attachment_count": len(session.attachments),
            "client_id": str(session.client_id),
            "session_date": session.session_date.isoformat(),
            # Do NOT log PHI: subjective, objective, assessment, plan
        },
    )
```

### 3. Permanently Delete Session

```python
async def permanently_delete_session(
    db: AsyncSession,
    session: Session,
) -> None:
    """
    Permanently delete session and related data.

    CASCADE will delete:
    - session_attachments (files)
    - session_versions (amendment history)

    NOTE: S3/MinIO files must be deleted separately (see below).
    """
    # First, delete S3/MinIO files for attachments
    for attachment in session.attachments:
        await delete_s3_file(attachment.s3_key)

    # Then permanently delete session (CASCADE handles related tables)
    await db.delete(session)
    await db.commit()
```

### 4. Background Job Orchestration

**Option A: Celery (Recommended)**

```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery("pazpaz")

@celery_app.task
async def purge_expired_sessions():
    """
    Daily job to purge sessions that exceeded 30-day grace period.

    Schedule: Daily at 2:00 AM UTC
    """
    from pazpaz.db.session import get_async_db

    async with get_async_db() as db:
        expired_sessions = await get_expired_sessions(db)

        purged_count = 0
        errors = []

        for session in expired_sessions:
            try:
                # Create audit log snapshot
                await create_purge_audit_log(db, session)

                # Permanently delete
                await permanently_delete_session(db, session)

                purged_count += 1

            except Exception as e:
                errors.append({
                    "session_id": str(session.id),
                    "error": str(e),
                })
                # Log error but continue with other sessions
                logger.error(
                    "session_purge_failed",
                    session_id=str(session.id),
                    workspace_id=str(session.workspace_id),
                    error=str(e),
                )

        # Log summary
        logger.info(
            "session_purge_completed",
            total_expired=len(expired_sessions),
            purged_count=purged_count,
            error_count=len(errors),
        )

        return {
            "total_expired": len(expired_sessions),
            "purged_count": purged_count,
            "errors": errors,
        }

# Configure schedule
celery_app.conf.beat_schedule = {
    "purge-expired-sessions": {
        "task": "pazpaz.tasks.purge_expired_sessions",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2:00 AM UTC
    },
}
```

**Option B: APScheduler (Alternative)**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=2, minute=0)
async def purge_expired_sessions():
    # Same implementation as Celery version
    pass

# Start scheduler
scheduler.start()
```

## Error Handling

### Retry Logic
- Transient failures (database connection errors): Retry up to 3 times with exponential backoff
- Permanent failures (S3 file not found): Log error, continue with database deletion

### Partial Failure Handling
- Process each session independently (don't fail entire job if one session fails)
- Log all errors with session_id and workspace_id for investigation
- Send alert if error rate exceeds 10%

### Monitoring
- Track metrics: sessions_purged_count, purge_job_duration_seconds, purge_job_error_count
- Alert if job hasn't run in >25 hours (missed execution)
- Alert if error rate > 10%

## Security Considerations

### Audit Trail
- Every purge operation creates an audit log entry
- Audit log includes metadata but NEVER logs PHI (SOAP fields)
- Audit logs are append-only and immutable (database-enforced)

### Access Control
- Purge job runs with system-level credentials
- No user-facing API to trigger manual purge
- Workspace isolation maintained throughout purge process

### Data Retention Compliance
- 30-day grace period aligns with HIPAA "reasonable time" for data retention after deletion request
- Audit logs of purged sessions retained indefinitely for compliance
- S3/MinIO files deleted synchronously with database records

## Testing Strategy

### Unit Tests
- Test query for expired sessions
- Test audit log creation before purge
- Test CASCADE deletion behavior
- Test error handling and retries

### Integration Tests
- Test end-to-end purge flow
- Test partial failure scenarios
- Test workspace isolation during purge
- Test S3 file deletion

### Load Tests
- Simulate purging 1000+ sessions in single job run
- Verify job completes within acceptable time (< 5 minutes)
- Verify database performance under load

## Migration Guide

### Pre-Implementation Checklist
- [ ] Celery/APScheduler installed and configured
- [ ] Redis connection pool configured for Celery
- [ ] S3/MinIO client initialized
- [ ] Monitoring/alerting configured
- [ ] Backup strategy verified

### Deployment Steps
1. Deploy code with purge job (disabled)
2. Run manual test purge on staging environment
3. Verify audit logs created correctly
4. Verify S3 files deleted
5. Enable scheduled job in production
6. Monitor first 3 runs closely

## Edge Cases

### Session Deleted During Purge Window
- Query uses snapshot isolation (PostgreSQL default)
- Session won't appear in results if deleted after query starts

### User Restores Session After Purge Starts
- Restore endpoint checks `permanent_delete_after < NOW()`
- If expired, returns 410 Gone (can't restore)
- Race condition window is ~seconds (purge job runtime)

### Workspace Deleted Before Purge Runs
- CASCADE deletes session when workspace deleted
- Purge job skips (session no longer exists)

### Amended Session Purge
- Amended sessions can be soft-deleted
- Purge job treats them like any other expired session
- SessionVersion records deleted via CASCADE

## Future Enhancements

### Phase 1 (Week 5)
- Basic daily purge job with audit logging

### Phase 2 (Future)
- Admin UI to view pending purges
- Manual purge trigger for admin users
- Configurable grace period per workspace (7-90 days)
- Email notification to therapist before purge (7-day warning)

## References

- HIPAA Data Retention Guidelines: 6 years minimum for medical records
- Soft delete pattern: https://en.wikipedia.org/wiki/Soft_delete
- Celery best practices: https://docs.celeryproject.org/en/stable/userguide/tasks.html
- PostgreSQL CASCADE behavior: https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK

## Contact

For questions about this implementation plan, contact the backend team lead or reference:
- Migration: `/backend/alembic/versions/2de77d93d190_add_soft_delete_fields_to_sessions.py`
- Model: `/backend/src/pazpaz/models/session.py`
- API: `/backend/src/pazpaz/api/sessions.py`
- Tests: `/backend/tests/test_api/test_sessions.py::TestSessionSoftDelete`
