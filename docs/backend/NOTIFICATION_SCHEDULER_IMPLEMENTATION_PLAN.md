# Notification Scheduler Implementation Plan

**Objective:** Implement scheduled email notifications using `arq` (Redis-based task queue) to send session notes reminders, daily digests, and appointment reminders based on user notification settings.

**Approach:** Start with arq-only implementation using existing `email_service.py`, then migrate to Novu later when adding SMS/push notifications.

**Timeline:** ~3-4 hours for Phase 1 (arq setup + basic notifications)

---

## Phase 1: arq Infrastructure Setup (Foundation)

### 1.1 Install Dependencies

- [ ] Add `arq` to backend dependencies
  ```bash
  cd backend
  uv add arq
  ```

- [ ] Verify Redis is running (already in docker-compose.yml)
  ```bash
  docker compose ps redis
  ```

### 1.2 Create Worker Configuration

- [ ] Create `src/pazpaz/workers/__init__.py`
  ```python
  """Background workers for scheduled tasks."""
  ```

- [ ] Create `src/pazpaz/workers/settings.py`
  - Redis connection configuration
  - Worker settings (max_jobs, job_timeout, etc.)
  - Health check configuration
  - Queue name configuration

- [ ] Create `src/pazpaz/workers/scheduler.py`
  - Define `WorkerSettings` class
  - Configure Redis connection from settings
  - Set up cron_jobs list (initially empty)
  - Configure job retry settings

### 1.3 Test arq Worker Setup

- [ ] Start arq worker manually
  ```bash
  cd backend
  PYTHONPATH=src uv run arq pazpaz.workers.scheduler.WorkerSettings
  ```

- [ ] Verify worker connects to Redis
- [ ] Check worker logs for successful startup
- [ ] Stop worker (Ctrl+C)

---

## Phase 2: Notification Service Layer

### 2.1 Create Notification Query Service

- [ ] Create `src/pazpaz/services/notification_query_service.py`
  - Function: `get_users_needing_session_notes_reminder(current_time: time) -> List[User]`
    - Query users where `notes_reminder_enabled=True`
    - Filter by `notes_reminder_time` matching current hour:minute
    - Join with workspace to get timezone
    - Return users with email addresses

  - Function: `get_users_needing_daily_digest(current_time: time) -> List[User]`
    - Query users where `digest_enabled=True`
    - Filter by `digest_time` matching current hour:minute
    - Check `digest_skip_weekends` against current day
    - Join with workspace for timezone
    - Return users with workspace context

  - Function: `get_appointments_needing_reminders(current_time: datetime) -> List[Tuple[Appointment, User]]`
    - Query appointments in next 15min, 30min, 1hr, 2hr, 24hr windows
    - Join with user notification settings
    - Filter by `reminder_enabled=True` and matching `reminder_minutes`
    - Check if reminder already sent (need tracking mechanism)
    - Return appointment + user pairs

### 2.2 Create Email Content Builder Service

- [ ] Create `src/pazpaz/services/notification_content_service.py`
  - Function: `build_session_notes_reminder_email(user: User) -> dict`
    - Query draft sessions for user
    - Build email subject/body with session count
    - Return email data dict

  - Function: `build_daily_digest_email(user: User, date: date) -> dict`
    - Query appointments for user on date
    - Build email with appointment list
    - Include client names, times, services
    - Return email data dict

  - Function: `build_appointment_reminder_email(appointment: Appointment, user: User) -> dict`
    - Format appointment details
    - Include client name, time, location, service
    - Add "minutes until" context
    - Return email data dict

### 2.3 Extend Email Service

- [ ] Update `src/pazpaz/services/email_service.py`
  - Function: `send_session_notes_reminder(email: str, draft_count: int)`
    - Create EmailMessage
    - Set subject: "You have {draft_count} draft session notes"
    - Set body with link to sessions page
    - Send via SMTP
    - Log success/failure

  - Function: `send_daily_digest(email: str, appointments: List[dict])`
    - Create EmailMessage
    - Set subject: "Your schedule for {date}"
    - Format appointment list in body
    - Send via SMTP
    - Log success/failure

  - Function: `send_appointment_reminder(email: str, appointment: dict, minutes_until: int)`
    - Create EmailMessage
    - Set subject: "Appointment in {minutes_until} minutes"
    - Format appointment details
    - Send via SMTP
    - Log success/failure

---

## Phase 3: Scheduled Tasks (arq Jobs)

### 3.1 Create Session Notes Reminder Task

- [ ] Add to `src/pazpaz/workers/scheduler.py`
  - Function: `async def send_session_notes_reminders(ctx: dict)`
    - Get current time in UTC
    - For each timezone offset (-12 to +14):
      - Calculate local time for that timezone
      - Get users needing reminder at this local time
      - For each user:
        - Build email content
        - Send email via email_service
        - Log success/failure with user_id
    - Return summary stats (sent count, error count)

- [ ] Add cron job to `WorkerSettings`
  ```python
  # Run every minute to check all timezones
  cron(send_session_notes_reminders, minute={0,1,2,...,59})
  ```

### 3.2 Create Daily Digest Task

- [ ] Add to `src/pazpaz/workers/scheduler.py`
  - Function: `async def send_daily_digests(ctx: dict)`
    - Get current time in UTC
    - For each timezone offset:
      - Calculate local time
      - Get users needing digest at this local time
      - Check if today is weekend and user has skip_weekends=True
      - For each eligible user:
        - Build digest email with today's appointments
        - Send email via email_service
        - Log success/failure
    - Return summary stats

- [ ] Add cron job to `WorkerSettings`
  ```python
  # Run every minute to check all timezones
  cron(send_daily_digests, minute={0,1,2,...,59})
  ```

### 3.3 Create Appointment Reminder Task

- [ ] Add to `src/pazpaz/workers/scheduler.py`
  - Function: `async def send_appointment_reminders(ctx: dict)`
    - Get appointments in next 24 hours
    - For each appointment:
      - Calculate minutes until start
      - Check if matches user's reminder_minutes setting
      - Check if reminder already sent (use cache/db flag)
      - If eligible:
        - Build reminder email
        - Send email
        - Mark reminder as sent
        - Log success/failure
    - Return summary stats

- [ ] Add cron job to `WorkerSettings`
  ```python
  # Run every 5 minutes (reminders don't need minute precision)
  cron(send_appointment_reminders, minute={0,5,10,15,20,25,30,35,40,45,50,55})
  ```

---

## Phase 4: Reminder Tracking (Prevent Duplicates)

### 4.1 Database Schema for Sent Reminders

- [ ] Create migration: `add_appointment_reminder_tracking`
  - Add table `appointment_reminders_sent`:
    - `id` (UUID, PK)
    - `appointment_id` (UUID, FK to appointments)
    - `user_id` (UUID, FK to users)
    - `sent_at` (timestamp with timezone)
    - `reminder_type` (enum: '15min', '30min', '1hr', '2hr', '24hr')
    - Unique constraint on (appointment_id, user_id, reminder_type)
    - Index on appointment_id
    - Index on sent_at (for cleanup queries)

- [ ] Create SQLAlchemy model `src/pazpaz/models/appointment_reminder.py`
  - AppointmentReminderSent model
  - Relationships to Appointment and User
  - Enum for ReminderType

### 4.2 Reminder Tracking Service

- [ ] Create `src/pazpaz/services/reminder_tracking_service.py`
  - Function: `async def was_reminder_sent(appointment_id: UUID, user_id: UUID, reminder_type: str) -> bool`
    - Query appointment_reminders_sent table
    - Return True if exists

  - Function: `async def mark_reminder_sent(appointment_id: UUID, user_id: UUID, reminder_type: str)`
    - Insert record into appointment_reminders_sent
    - Handle unique constraint violations gracefully

  - Function: `async def cleanup_old_reminders(days_old: int = 30)`
    - Delete records older than X days
    - Run weekly via cron job

### 4.3 Update Appointment Reminder Task

- [ ] Modify `send_appointment_reminders()` in scheduler.py
  - Check `was_reminder_sent()` before sending
  - Call `mark_reminder_sent()` after successful send
  - Add error handling for tracking failures

---

## Phase 5: Docker Integration

### 5.1 Add arq Worker to Docker Compose

- [ ] Update `docker-compose.yml`
  - Add new service: `arq-worker`
    ```yaml
    arq-worker:
      build: ./backend
      command: arq pazpaz.workers.scheduler.WorkerSettings
      environment:
        - DATABASE_URL=postgresql+asyncpg://...
        - REDIS_URL=redis://redis:6379/0
        - SMTP_HOST=mailhog
        - SMTP_PORT=1025
      depends_on:
        - db
        - redis
        - mailhog
      volumes:
        - ./backend/src:/app/src
      restart: unless-stopped
    ```

- [ ] Update backend Dockerfile if needed
  - Ensure arq is installed
  - Verify PYTHONPATH is set correctly

### 5.2 Test Worker in Docker

- [ ] Rebuild containers
  ```bash
  docker compose build arq-worker
  ```

- [ ] Start arq worker container
  ```bash
  docker compose up arq-worker
  ```

- [ ] Check logs for successful startup
  ```bash
  docker compose logs -f arq-worker
  ```

- [ ] Verify Redis connection in logs
- [ ] Stop container

---

## Phase 6: Testing

### 6.1 Unit Tests for Services

- [ ] Create `tests/unit/services/test_notification_query_service.py`
  - Test `get_users_needing_session_notes_reminder()`
  - Test timezone handling
  - Test filtering by time
  - Mock database queries

- [ ] Create `tests/unit/services/test_notification_content_service.py`
  - Test email content builders
  - Verify subject/body formatting
  - Test edge cases (no appointments, multiple sessions)

- [ ] Create `tests/unit/services/test_reminder_tracking_service.py`
  - Test reminder deduplication
  - Test cleanup of old reminders

### 6.2 Integration Tests for Workers

- [ ] Create `tests/integration/workers/test_scheduler.py`
  - Test `send_session_notes_reminders()` with mock users
  - Test `send_daily_digests()` with mock appointments
  - Test `send_appointment_reminders()` end-to-end
  - Verify emails sent to MailHog
  - Test timezone edge cases
  - Test weekend skipping for digest

### 6.3 Manual Testing

- [ ] Set notification settings in UI to trigger in 2 minutes
- [ ] Start arq worker
- [ ] Wait for scheduled time
- [ ] Check MailHog (http://localhost:8025) for email
- [ ] Verify email content is correct
- [ ] Check worker logs for success message
- [ ] Verify no duplicate emails sent

---

## Phase 7: Monitoring & Observability

### 7.1 Add Structured Logging

- [ ] Update worker tasks to log:
  - Task start/end times
  - Number of users/appointments processed
  - Number of emails sent successfully
  - Number of errors encountered
  - Processing duration

- [ ] Add log levels appropriately:
  - INFO: Task started/completed, emails sent
  - WARNING: User has no email, reminder already sent
  - ERROR: Email send failure, database errors

### 7.2 Health Check Endpoint

- [ ] Create `src/pazpaz/api/health.py` (if doesn't exist)
  - Add endpoint: `GET /api/v1/health/workers`
  - Check arq worker status via Redis
  - Return last job execution times
  - Return queue length

### 7.3 Admin Dashboard (Future)

- [ ] Document future work for admin UI:
  - View scheduled jobs status
  - Manually trigger notification jobs
  - View recent email send history
  - Retry failed notifications

---

## Phase 8: Documentation

### 8.1 Architecture Documentation

- [ ] Create `docs/backend/NOTIFICATION_ARCHITECTURE.md`
  - Explain arq scheduler design
  - Document timezone handling approach
  - Explain reminder deduplication
  - Include sequence diagrams

### 8.2 Operational Documentation

- [ ] Create `docs/operations/NOTIFICATION_WORKER_RUNBOOK.md`
  - How to start/stop arq worker
  - How to monitor worker health
  - How to debug failed notifications
  - How to manually trigger jobs for testing
  - Common issues and solutions

### 8.3 Development Documentation

- [ ] Update `docs/backend/api/NOTIFICATION_SETTINGS.md`
  - Add section on how scheduled notifications work
  - Document timing/timezone behavior
  - Add examples of notification triggers

### 8.4 Code Documentation

- [ ] Add comprehensive docstrings to all new services
- [ ] Add inline comments for complex timezone logic
- [ ] Document retry strategies and error handling

---

## Phase 9: Deployment & Rollout

### 9.1 Staging Deployment

- [ ] Deploy to staging environment
- [ ] Run database migration for reminder tracking
- [ ] Start arq worker in staging
- [ ] Monitor logs for 24 hours
- [ ] Test all notification types
- [ ] Verify no duplicate emails

### 9.2 Production Deployment

- [ ] Run database migration in production
- [ ] Deploy updated backend code
- [ ] Start arq worker in production
- [ ] Monitor worker health metrics
- [ ] Check error rates in logs
- [ ] Verify MailHog/SMTP is receiving emails

### 9.3 Rollback Plan

- [ ] Document rollback procedure:
  - Stop arq worker
  - Revert code deployment
  - Keep database migration (backward compatible)
  - Resume when ready

---

## Phase 10: Future Enhancements (Post-Launch)

### 10.1 Novu Integration (Multi-Channel)

- [ ] Research Novu setup and configuration
- [ ] Set up Novu in Docker Compose
- [ ] Migrate email templates to Novu
- [ ] Add SMS provider (Twilio)
- [ ] Add push notification provider (FCM/APNs)
- [ ] Update notification services to use Novu SDK

### 10.2 Advanced Features

- [ ] Notification batching (digest multiple reminders)
- [ ] Smart send times (machine learning optimal times)
- [ ] Notification preferences per notification type
- [ ] Quiet hours support (don't send 10pm-8am)
- [ ] Notification analytics dashboard

### 10.3 Performance Optimization

- [ ] Add Redis caching for user queries
- [ ] Batch email sends (multiple recipients per SMTP connection)
- [ ] Optimize database queries with proper indexes
- [ ] Monitor worker memory usage and optimize

---

## Success Criteria

### Functional Requirements
- [x] User sets session notes reminder time in UI
- [ ] User receives email at specified time (within 1 minute accuracy)
- [ ] Email contains correct content (draft count, link)
- [ ] No duplicate reminders sent
- [ ] Timezone handling works correctly
- [ ] Weekend skipping works for daily digest

### Performance Requirements
- [ ] Worker processes all notifications within 1 minute per cycle
- [ ] Email delivery <5 seconds after worker processes user
- [ ] Worker handles 1000+ users without issues
- [ ] No memory leaks over 24+ hour runs

### Reliability Requirements
- [ ] Worker auto-restarts on failure (Docker restart policy)
- [ ] Failed emails logged with details for debugging
- [ ] Reminder deduplication prevents duplicates 100% of time
- [ ] Worker survives Redis connection drops

### Operational Requirements
- [ ] Clear logs for debugging notification issues
- [ ] Health check endpoint responds accurately
- [ ] Documentation enables new dev to understand system
- [ ] Runbook enables ops team to troubleshoot issues

---

## Timeline Estimate

| Phase | Description | Estimated Time |
|-------|-------------|----------------|
| 1 | arq Infrastructure Setup | 30 minutes |
| 2 | Notification Service Layer | 1.5 hours |
| 3 | Scheduled Tasks | 1 hour |
| 4 | Reminder Tracking | 1 hour |
| 5 | Docker Integration | 30 minutes |
| 6 | Testing | 2 hours |
| 7 | Monitoring & Observability | 1 hour |
| 8 | Documentation | 1 hour |
| 9 | Deployment & Rollout | 1 hour |
| **Total** | | **~9.5 hours** |

**Note:** Phase 10 (Novu integration) is future work, estimated at 8-12 hours when needed.

---

## Risk Mitigation

### Risk: Timezone handling complexity
- **Mitigation:** Use UTC internally, convert at query time
- **Mitigation:** Extensive testing with multiple timezones
- **Mitigation:** Document timezone assumptions clearly

### Risk: Email delivery failures
- **Mitigation:** Comprehensive error logging
- **Mitigation:** Retry logic in arq (built-in)
- **Mitigation:** Monitor bounce rates in production

### Risk: Duplicate notifications
- **Mitigation:** Database-backed deduplication
- **Mitigation:** Unique constraints on reminder tracking
- **Mitigation:** Integration tests for duplicate scenarios

### Risk: Worker failures
- **Mitigation:** Docker restart policy
- **Mitigation:** Health check monitoring
- **Mitigation:** Alerting on worker downtime

### Risk: Performance degradation with scale
- **Mitigation:** Batch processing where possible
- **Mitigation:** Database query optimization
- **Mitigation:** Redis caching for hot paths
- **Mitigation:** Load testing before production

---

## Dependencies

- ✅ Redis (already running in docker-compose.yml)
- ✅ PostgreSQL with notification settings table (already implemented)
- ✅ Email service (already implemented: `email_service.py`)
- ✅ SMTP server (MailHog for dev, production SMTP for prod)
- ⚠️ arq library (needs to be added)
- ⚠️ Appointment reminder tracking table (needs migration)

---

## Next Steps

1. Review this plan with team
2. Confirm approach and timeline
3. Create tracking issue/epic in project management tool
4. Begin Phase 1: arq Infrastructure Setup
5. Commit progress after each major phase
6. Deploy to staging after Phase 6 (Testing)
7. Monitor staging for 24 hours before production deployment

---

**Document Version:** 1.0
**Last Updated:** 2025-10-22
**Status:** Ready for Implementation
**Assigned To:** TBD
**Estimated Completion:** 2025-10-23 (if starting today)
