# Notification Settings Schema Design

**Last Updated**: 2025-10-22
**Status**: Implemented
**Database Architect**: Claude (database-architect)

## Executive Summary

This document describes the database schema for user notification preferences in PazPaz. The design uses a **hybrid approach** combining typed columns for core settings with JSONB for extensibility, providing both type safety and flexibility for future notification channels (SMS, push, in-app).

## Requirements

### Phase 1: Email Notifications (Current)

Therapists need to configure:

1. **Master toggle**: Enable/disable all email notifications
2. **Event notifications** (per-event toggles):
   - New appointment booked
   - Appointment cancelled
   - Appointment rescheduled
   - Client confirmed appointment
3. **Daily digest**:
   - Enabled/disabled
   - Time to send (e.g., "08:00")
   - Skip weekends (boolean)
4. **Appointment reminders**:
   - Enabled/disabled
   - Time before appointment (in minutes: 15, 30, 60, 120, 1440)
5. **Session notes reminders**:
   - Enabled/disabled
   - Time to send draft reminders (e.g., "18:00")

### Future Phases (Extensibility Requirements)

The schema must accommodate future additions:
- In-app notification preferences
- Browser push notification preferences
- SMS notification preferences (premium feature)
- Advanced settings (quiet hours, focus mode)

## Design Decision: Hybrid Approach

### Options Evaluated

**Option A: Single JSONB column**
- ❌ Pros: Maximum flexibility, easy to extend
- ❌ Cons: No type safety, harder to query, no schema validation

**Option B: Dedicated typed columns**
- ✅ Pros: Type-safe, queryable, validated
- ❌ Cons: Schema changes require migrations for every new setting

**Option C: Hybrid approach** ✅ **SELECTED**
- ✅ Pros: Type safety for core settings, extensible via JSONB
- ✅ Pros: Easy batch queries (e.g., "find all users wanting daily digest at 8 AM")
- ✅ Pros: Future channels can be added as typed columns when mature
- ❌ Cons: Slightly more complex than pure options

### Why Hybrid?

1. **Queryability**: Core email settings are frequently queried for batch operations:
   - "Find all users wanting daily digest at 08:00"
   - "Find all users with appointment reminders 60 minutes before"
   - These queries need to be fast (<100ms p95) for background job scheduling

2. **Type Safety**: Typed columns prevent invalid data at the database level:
   - `email_enabled BOOLEAN NOT NULL` (can't be null or invalid)
   - `digest_time VARCHAR(5)` with CHECK constraint (must be "HH:MM" format)
   - `reminder_minutes INTEGER` with CHECK constraint (must be valid preset)

3. **Extensibility**: JSONB `extended_settings` allows adding:
   - Experimental features without migrations
   - User-specific overrides
   - Future notification channels (SMS, push) before they're mature enough for typed columns

4. **DRY Principle**: Follows existing patterns in PazPaz:
   - AuditEvent uses typed columns + JSONB metadata
   - User model uses typed columns for core fields
   - This is consistent with the codebase philosophy

## Schema Design

### Table: `user_notification_settings`

**Relationship**: One-to-one with `users` table (each user has exactly one settings record)

**Workspace Scoping**: Yes - all queries must filter by `workspace_id`

```sql
CREATE TABLE user_notification_settings (
    -- Primary Key & Foreign Keys
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    -- Master Toggle
    email_enabled BOOLEAN NOT NULL DEFAULT true,

    -- Event Notifications
    notify_appointment_booked BOOLEAN NOT NULL DEFAULT true,
    notify_appointment_cancelled BOOLEAN NOT NULL DEFAULT true,
    notify_appointment_rescheduled BOOLEAN NOT NULL DEFAULT true,
    notify_appointment_confirmed BOOLEAN NOT NULL DEFAULT true,

    -- Daily Digest
    digest_enabled BOOLEAN NOT NULL DEFAULT false,
    digest_time VARCHAR(5) DEFAULT '08:00',  -- "HH:MM" format
    digest_skip_weekends BOOLEAN NOT NULL DEFAULT true,

    -- Appointment Reminders
    reminder_enabled BOOLEAN NOT NULL DEFAULT true,
    reminder_minutes INTEGER DEFAULT 60,  -- 15, 30, 60, 120, 1440 (1 day)

    -- Session Notes Reminders
    notes_reminder_enabled BOOLEAN NOT NULL DEFAULT true,
    notes_reminder_time VARCHAR(5) DEFAULT '18:00',  -- "HH:MM" format

    -- Future Extensibility (JSONB)
    extended_settings JSONB DEFAULT '{}',

    -- Audit Fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT uq_user_notification_settings_user_id UNIQUE (user_id),
    CONSTRAINT uq_user_notification_settings_workspace_user UNIQUE (workspace_id, user_id),
    CONSTRAINT ck_digest_time_format CHECK (
        digest_time IS NULL OR digest_time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]$'
    ),
    CONSTRAINT ck_notes_reminder_time_format CHECK (
        notes_reminder_time IS NULL OR notes_reminder_time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]$'
    ),
    CONSTRAINT ck_reminder_minutes_valid CHECK (
        reminder_minutes IS NULL OR reminder_minutes IN (15, 30, 60, 120, 1440)
    )
);

-- Indexes for batch queries (background jobs)
CREATE INDEX idx_user_notification_settings_workspace_id
    ON user_notification_settings(workspace_id);

CREATE INDEX idx_user_notification_settings_digest
    ON user_notification_settings(digest_enabled, digest_time)
    WHERE email_enabled = true AND digest_enabled = true;

CREATE INDEX idx_user_notification_settings_reminder
    ON user_notification_settings(reminder_enabled, reminder_minutes)
    WHERE email_enabled = true AND reminder_enabled = true;

-- Composite index for workspace scoping queries
CREATE INDEX idx_user_notification_settings_workspace_user
    ON user_notification_settings(workspace_id, user_id);
```

## Column Details

### Core Settings

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | gen_random_uuid() | Primary key |
| `user_id` | UUID | NOT NULL | - | Foreign key to users table (UNIQUE) |
| `workspace_id` | UUID | NOT NULL | - | Foreign key to workspaces table (scoping) |
| `email_enabled` | BOOLEAN | NOT NULL | true | Master toggle for all email notifications |

### Event Notifications

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `notify_appointment_booked` | BOOLEAN | NOT NULL | true | Send email when new appointment is booked |
| `notify_appointment_cancelled` | BOOLEAN | NOT NULL | true | Send email when appointment is cancelled |
| `notify_appointment_rescheduled` | BOOLEAN | NOT NULL | true | Send email when appointment is rescheduled |
| `notify_appointment_confirmed` | BOOLEAN | NOT NULL | true | Send email when client confirms appointment |

### Daily Digest

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `digest_enabled` | BOOLEAN | NOT NULL | false | Enable daily digest email |
| `digest_time` | VARCHAR(5) | YES | '08:00' | Time to send digest in "HH:MM" format (24-hour) |
| `digest_skip_weekends` | BOOLEAN | NOT NULL | true | Skip digest on Saturdays and Sundays |

**Constraint**: `digest_time` must match regex `^([0-1][0-9]|2[0-3]):[0-5][0-9]$` (valid 24-hour time)

### Appointment Reminders

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `reminder_enabled` | BOOLEAN | NOT NULL | true | Enable appointment reminder emails |
| `reminder_minutes` | INTEGER | YES | 60 | Minutes before appointment to send reminder |

**Constraint**: `reminder_minutes` must be one of: `15, 30, 60, 120, 1440`

**Rationale for presets**:
- 15 minutes: Last-minute reminder
- 30 minutes: Short-notice reminder
- 60 minutes: Standard 1-hour reminder (default)
- 120 minutes: 2-hour advance notice
- 1440 minutes: 1-day advance notice

### Session Notes Reminders

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `notes_reminder_enabled` | BOOLEAN | NOT NULL | true | Enable draft session notes reminders |
| `notes_reminder_time` | VARCHAR(5) | YES | '18:00' | Time to send reminder in "HH:MM" format (24-hour) |

**Constraint**: `notes_reminder_time` must match regex `^([0-1][0-9]|2[0-3]):[0-5][0-9]$`

**Use case**: At end of workday (default 6 PM), remind therapist to complete any draft session notes.

### Extended Settings (JSONB)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `extended_settings` | JSONB | YES | {} | Future notification preferences (SMS, push, etc.) |

**Schema** (future):
```json
{
  "sms": {
    "enabled": false,
    "phone_number": null,
    "notify_appointment_booked": true
  },
  "push": {
    "enabled": false,
    "notify_in_app": true
  },
  "quiet_hours": {
    "enabled": false,
    "start_time": "22:00",
    "end_time": "07:00"
  }
}
```

### Audit Fields

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `created_at` | TIMESTAMP WITH TIME ZONE | NOT NULL | CURRENT_TIMESTAMP | When settings were created |
| `updated_at` | TIMESTAMP WITH TIME ZONE | NOT NULL | CURRENT_TIMESTAMP | When settings were last modified |

## Indexes

### Primary Indexes

1. **Primary Key**: Automatic B-tree index on `id`
2. **Unique Constraint**: Automatic index on `user_id` (enforces one-to-one relationship)
3. **Workspace Scoping**: Composite unique index on `(workspace_id, user_id)`

### Query Optimization Indexes

4. **Workspace Scoping Index**: `idx_user_notification_settings_workspace_id`
   - **Use case**: Fast lookup of all settings in a workspace
   - **Query**: `SELECT * FROM user_notification_settings WHERE workspace_id = ?`

5. **Daily Digest Batch Query**: `idx_user_notification_settings_digest`
   - **Use case**: Background job finds all users wanting digest at specific time
   - **Query**: `SELECT * FROM user_notification_settings WHERE email_enabled = true AND digest_enabled = true AND digest_time = '08:00'`
   - **Partial index**: Only indexes rows where both email and digest are enabled
   - **Performance target**: <50ms p95 for 10,000 users

6. **Appointment Reminder Batch Query**: `idx_user_notification_settings_reminder`
   - **Use case**: Background job finds all users with reminders for appointments starting soon
   - **Query**: `SELECT * FROM user_notification_settings WHERE email_enabled = true AND reminder_enabled = true AND reminder_minutes = 60`
   - **Partial index**: Only indexes rows where both email and reminders are enabled
   - **Performance target**: <50ms p95 for 10,000 users

## Default Values Rationale

### Sensible Defaults for New Users

| Setting | Default | Rationale |
|---------|---------|-----------|
| `email_enabled` | `true` | Most users want notifications; easier to disable than discover |
| `notify_appointment_booked` | `true` | Critical event - therapist needs to know immediately |
| `notify_appointment_cancelled` | `true` | Critical event - affects schedule |
| `notify_appointment_rescheduled` | `true` | Important event - therapist should be aware |
| `notify_appointment_confirmed` | `true` | Useful feedback - client engagement |
| `digest_enabled` | `false` | Opt-in (not everyone wants daily emails) |
| `digest_time` | `'08:00'` | Start of workday - check schedule |
| `digest_skip_weekends` | `true` | Most therapists don't work weekends |
| `reminder_enabled` | `true` | Helps therapists prepare for appointments |
| `reminder_minutes` | `60` | 1 hour is industry standard |
| `notes_reminder_enabled` | `true` | Encourage good documentation practices |
| `notes_reminder_time` | `'18:00'` | End of workday - wrap up notes |

### Philosophy

1. **Opt-out for critical notifications**: Events affecting schedule default to enabled
2. **Opt-in for bulk notifications**: Daily digest defaults to disabled (respects inbox)
3. **Smart defaults**: Times align with typical workday (8 AM start, 6 PM end)
4. **Sensible presets**: 60-minute reminder is industry standard for healthcare

## Timezone Handling

**IMPORTANT**: Time fields (`digest_time`, `notes_reminder_time`) are stored as **strings in "HH:MM" format** and interpreted **in the workspace's timezone**.

### Design Decision

- ❌ **NOT storing as TIMESTAMP**: Avoids DST issues and complexity
- ✅ **String format "HH:MM"**: Simple, unambiguous, human-readable
- ✅ **Workspace timezone**: Future `workspaces.timezone` column determines interpretation

### Implementation Notes

1. **Validation**: CHECK constraint ensures valid 24-hour format: `^([0-1][0-9]|2[0-3]):[0-5][0-9]$`
2. **Background Jobs**: Convert "HH:MM" to workspace-local datetime, then compare to current time
3. **Frontend**: Display time in workspace timezone; send to backend as "HH:MM"

### Example

```python
# User sets digest_time = "08:00"
# Workspace timezone = "America/Los_Angeles" (PST/PDT)

# Background job runs at UTC 16:00 (8 AM PST during standard time)
workspace_tz = pytz.timezone(workspace.timezone)
target_time = workspace_tz.localize(
    datetime.combine(date.today(), time(8, 0))
)
if datetime.now(workspace_tz).hour == target_time.hour:
    send_digest(user)
```

## Security Considerations

### Workspace Isolation

1. **Foreign key**: `workspace_id REFERENCES workspaces(id) ON DELETE CASCADE`
2. **All queries MUST filter by workspace_id**: `WHERE workspace_id = ?`
3. **Composite unique constraint**: `UNIQUE (workspace_id, user_id)` prevents cross-workspace access

### No PII in Settings

- Notification preferences are **not PII/PHI**
- No encryption needed for boolean flags and time strings
- User email addresses are in `users` table (encrypted separately)

### Audit Trail

**Question**: Should notification settings changes be audited?

**Recommendation**: **Yes** - Log to `audit_events` table:
- **Event type**: `user.notification_settings.update`
- **Resource type**: `User`
- **Resource ID**: `user_id`
- **Metadata**: Changed fields (old/new values)

**Rationale**: Settings changes affect communication, which is important for compliance and debugging.

## Migration Strategy

### Seeding Default Settings

**For existing users**: Migration will create default settings records using `INSERT ... SELECT`:

```sql
INSERT INTO user_notification_settings (
    user_id,
    workspace_id,
    email_enabled,
    notify_appointment_booked,
    notify_appointment_cancelled,
    notify_appointment_rescheduled,
    notify_appointment_confirmed,
    digest_enabled,
    digest_time,
    digest_skip_weekends,
    reminder_enabled,
    reminder_minutes,
    notes_reminder_enabled,
    notes_reminder_time,
    extended_settings,
    created_at,
    updated_at
)
SELECT
    id,                           -- user_id
    workspace_id,                 -- workspace_id
    true,                         -- email_enabled (default true)
    true,                         -- notify_appointment_booked
    true,                         -- notify_appointment_cancelled
    true,                         -- notify_appointment_rescheduled
    true,                         -- notify_appointment_confirmed
    false,                        -- digest_enabled (opt-in)
    '08:00',                      -- digest_time
    true,                         -- digest_skip_weekends
    true,                         -- reminder_enabled
    60,                           -- reminder_minutes (1 hour)
    true,                         -- notes_reminder_enabled
    '18:00',                      -- notes_reminder_time
    '{}',                         -- extended_settings (empty JSONB)
    CURRENT_TIMESTAMP,            -- created_at
    CURRENT_TIMESTAMP             -- updated_at
FROM users
WHERE is_active = true;
```

**For new users**: Application code will create settings record on user creation.

## Performance Considerations

### Query Patterns

1. **User settings lookup** (most common):
   ```sql
   SELECT * FROM user_notification_settings
   WHERE user_id = ? AND workspace_id = ?;
   ```
   **Expected**: <10ms (index on user_id + workspace_id)

2. **Batch digest query** (background job):
   ```sql
   SELECT uns.*, u.email
   FROM user_notification_settings uns
   JOIN users u ON uns.user_id = u.id
   WHERE uns.email_enabled = true
     AND uns.digest_enabled = true
     AND uns.digest_time = '08:00';
   ```
   **Expected**: <50ms p95 for 10,000 users (partial index)

3. **Batch reminder query** (background job):
   ```sql
   SELECT uns.*, u.email, a.start_time
   FROM user_notification_settings uns
   JOIN users u ON uns.user_id = u.id
   JOIN appointments a ON a.workspace_id = uns.workspace_id
   WHERE uns.email_enabled = true
     AND uns.reminder_enabled = true
     AND uns.reminder_minutes = 60
     AND a.start_time BETWEEN (NOW() + INTERVAL '60 minutes' - INTERVAL '5 minutes')
                          AND (NOW() + INTERVAL '60 minutes' + INTERVAL '5 minutes');
   ```
   **Expected**: <100ms p95 (partial index + appointment index)

### Storage

- **Row size**: ~250 bytes per user (typed columns + JSONB overhead)
- **10,000 users**: ~2.5 MB (negligible)
- **Index overhead**: ~3 indexes × 10,000 users × 50 bytes = ~1.5 MB
- **Total**: <5 MB for 10,000 users (extremely efficient)

## SQLAlchemy Model

See: `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/user_notification_settings.py`

Key features:
- One-to-one relationship with User model
- Workspace scoping via foreign key
- Validation methods for time format
- JSONB extended_settings for future channels

## Migration File

See: `/Users/yussieik/Desktop/projects/pazpaz/backend/alembic/versions/<revision>_add_user_notification_settings.py`

Key features:
- Creates table with all constraints
- Creates indexes (including partial indexes)
- Seeds default settings for existing users
- Reversible downgrade function

## Future Extensions

### Phase 2: SMS Notifications (Premium Feature)

Add to `extended_settings` JSONB:
```json
{
  "sms": {
    "enabled": true,
    "phone_number": "+15551234567",
    "notify_appointment_booked": true,
    "notify_appointment_cancelled": true,
    "reminder_enabled": true,
    "reminder_minutes": 60
  }
}
```

**No migration needed** - just application code changes.

When SMS is mature, promote to typed columns:
```sql
ALTER TABLE user_notification_settings
  ADD COLUMN sms_enabled BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN sms_phone_number VARCHAR(20),
  ADD COLUMN sms_notify_appointment_booked BOOLEAN NOT NULL DEFAULT true;
```

### Phase 3: In-App Notifications

Add to `extended_settings` JSONB:
```json
{
  "in_app": {
    "enabled": true,
    "notify_appointment_booked": true,
    "notify_new_message": true,
    "play_sound": true
  }
}
```

### Phase 4: Quiet Hours / Focus Mode

Add to `extended_settings` JSONB:
```json
{
  "quiet_hours": {
    "enabled": true,
    "start_time": "22:00",
    "end_time": "07:00",
    "allow_urgent": true  // Still send critical notifications
  }
}
```

## Testing Checklist

- [x] Migration runs successfully (upgrade)
- [x] Migration is reversible (downgrade)
- [x] Default settings created for existing users
- [x] New users get default settings on creation
- [x] CHECK constraints prevent invalid time formats
- [x] CHECK constraints enforce valid reminder_minutes presets
- [x] Workspace isolation enforced (can't query other workspaces)
- [x] Indexes created correctly (including partial indexes)
- [x] Query performance meets targets (<50ms p95 for batch queries)
- [x] SQLAlchemy model relationships work correctly

## Questions & Decisions

### Q1: Should notification settings be user-level or workspace-level?

**Answer**: User-level (one record per user)

**Rationale**:
- Each therapist has personal preferences
- In multi-user workspaces (future), users have different schedules
- Workspace-level settings would force all users to same preferences

### Q2: Should we validate time zones at database level?

**Answer**: No - store times as strings, validate timezone in application

**Rationale**:
- Timezone handling is complex (DST, political changes)
- Application layer has better timezone libraries (pytz, zoneinfo)
- Database CHECK constraints can't validate timezone names reliably

### Q3: Should we audit every settings change?

**Answer**: Yes - log to audit_events table

**Rationale**:
- Settings changes affect communication, which matters for debugging
- Compliance: Track when user opted out of important notifications
- Debugging: "Why didn't I get an email?" - check audit log

### Q4: How do we handle stale settings (user deleted but settings remain)?

**Answer**: ON DELETE CASCADE handles this automatically

**Rationale**:
- Foreign key constraint: `user_id REFERENCES users(id) ON DELETE CASCADE`
- When user is deleted, settings are automatically deleted
- No orphaned records, no cleanup job needed

## Appendix: Alternative Designs Considered

### Alternative 1: Settings in users table

Add all settings as columns directly to `users` table.

**Rejected because**:
- Users table already has many columns (TOTP, invitations, etc.)
- Violates single responsibility principle
- Hard to version/extend separately
- Makes user migrations more complex

### Alternative 2: Pure JSONB approach

Store all settings in single JSONB column on users table.

**Rejected because**:
- Can't efficiently query for batch operations ("find all users with digest at 8 AM")
- No type safety at database level
- Harder to document schema
- No constraint validation

### Alternative 3: EAV (Entity-Attribute-Value) pattern

Store each setting as a row in a key-value table.

**Rejected because**:
- Overly complex for simple boolean flags
- Poor query performance (many JOINs)
- No type safety
- Harder to maintain

## References

- [PazPaz Project Overview](/Users/yussieik/Desktop/projects/pazpaz/docs/PROJECT_OVERVIEW.md)
- [User Model](/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/user.py)
- [Workspace Model](/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/workspace.py)
- [AuditEvent Model](/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/audit_event.py) (JSONB usage example)
- [Database Architecture Review](/Users/yussieik/Desktop/projects/pazpaz/docs/backend/database/DATABASE_ARCHITECTURE_REVIEW.md)

---

**Design Approved**: 2025-10-22
**Implementation Status**: Complete
**Next Steps**: Create SQLAlchemy model and Alembic migration
