# PazPaz Codebase - Quick Reference with Absolute Paths

## Exploration Complete
Date: 2025-10-28
Full Architecture Document: `/Users/yussieik/Desktop/projects/pazpaz/APPOINTMENT_SYSTEM_ARCHITECTURE.md`

---

## 1. Appointment System

### Database Model
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/appointment.py`

Key Classes:
- `Appointment` - appointment record with timing, location, status
- `AppointmentStatus` enum: scheduled, completed, cancelled, no_show
- `LocationType` enum: clinic, home, online

Key Fields:
- `id: UUID` - appointment ID
- `workspace_id: UUID` - workspace scoping (privacy isolation)
- `client_id: UUID` - which client
- `scheduled_start, scheduled_end: datetime` - UTC times
- `location_type, location_details` - where/how
- `status: AppointmentStatus` - current state
- `created_at, updated_at, edited_at` - audit timestamps
- `edit_count: int` - tracks modifications

Performance Indexes:
- `ix_appointments_workspace_time_range(workspace_id, scheduled_start, scheduled_end)`
- `ix_appointments_workspace_client_time(workspace_id, client_id, scheduled_start)`
- `ix_appointments_workspace_status(workspace_id, status)`

### API Endpoints
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/api/appointments.py`

```
POST   /api/v1/appointments
       - Create appointment with conflict detection
       - Input: AppointmentCreate
       - Output: AppointmentResponse

GET    /api/v1/appointments
       - List appointments (paginated)
       - Query params: page, page_size, start_date, end_date, client_id, status
       - Output: AppointmentListResponse

GET    /api/v1/appointments/{appointment_id}
       - Get single appointment
       - Output: AppointmentResponse

PUT    /api/v1/appointments/{appointment_id}
       - Update appointment
       - Query param: allow_conflict (bool)
       - Input: AppointmentUpdate
       - Output: AppointmentResponse

DELETE /api/v1/appointments/{appointment_id}
       - Delete appointment (with session note handling)
       - Body: AppointmentDeleteRequest (optional)
       - Returns: 204 No Content

GET    /api/v1/appointments/conflicts
       - Check for conflicts in time range
       - Query: scheduled_start, scheduled_end, exclude_appointment_id
       - Output: ConflictCheckResponse
```

### API Schemas
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/schemas/appointment.py`

- `AppointmentCreate` - create request
- `AppointmentUpdate` - update request (all fields optional)
- `AppointmentResponse` - response with client summary
- `AppointmentListResponse` - paginated list response
- `ConflictCheckResponse` - conflict check result
- `ConflictingAppointmentDetail` - privacy-preserving conflict info

### Frontend Calendar View
**File:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/CalendarView.vue`

Features:
- FullCalendar integration (week/day/month views)
- Appointment CRUD via modals
- Drag-and-drop rescheduling
- Conflict detection with warnings
- Optimistic updates with undo
- Mobile-responsive (time picker modal on mobile)
- Keyboard navigation

Key Composables Used:
- `useCalendar()` - view/date navigation
- `useCalendarEvents()` - event state & rendering
- `useAppointmentDrag()` - drag-drop rescheduling
- `useCalendarCreation()` - create modal management
- `useCalendarKeyboardShortcuts()` - a11y support

### Frontend Appointments Store
**File:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/stores/appointments.ts`

State:
- `appointments: AppointmentListItem[]`
- `loading: boolean`
- `error: string | null`
- `total: number`
- `loadedRange: { startDate, endDate } | null`

Methods:
- `fetchAppointments(startDate?, endDate?, page, pageSize)`
- `createAppointment(data)`
- `updateAppointment(id, data)`
- `deleteAppointment(id)`
- `checkConflicts(start, end, excludeId?)`

---

## 2. Settings System

### Notification Settings Model
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/user_notification_settings.py`

One-to-one relationship with User. Settings per user include:

Master Control:
- `email_enabled: bool` - master toggle for ALL emails

Event Notifications:
- `notify_appointment_booked: bool`
- `notify_appointment_cancelled: bool`
- `notify_appointment_rescheduled: bool`
- `notify_appointment_confirmed: bool`

Daily Digest (Today's Schedule):
- `digest_enabled: bool`
- `digest_time: str` (HH:MM format)
- `digest_days: list[int]` (0=Sun, 1=Mon, ..., 6=Sat)

Tomorrow's Digest:
- `tomorrow_digest_enabled: bool`
- `tomorrow_digest_time: str` (HH:MM)
- `tomorrow_digest_days: list[int]`

Appointment Reminders:
- `reminder_enabled: bool`
- `reminder_minutes: int` (15, 30, 60, 120, 1440)

Session Notes Reminders:
- `notes_reminder_enabled: bool`
- `notes_reminder_time: str` (HH:MM)

Future:
- `extended_settings: dict` (JSONB) - for SMS, push, quiet hours, etc.

Helper Methods:
- `should_send_emails() -> bool`
- `should_send_digest() -> bool`
- `should_send_tomorrow_digest() -> bool`
- `should_send_reminder() -> bool`
- `should_send_notes_reminder() -> bool`
- `validate() -> list[str]` - returns validation errors

### Notification Settings API
**File:** `/Users/yussieik/Desktop/projects/pazpaz/api/notification_settings.py`

```
GET    /api/v1/users/me/notification-settings
       - Get current user's settings
       - Output: NotificationSettingsResponse

PUT    /api/v1/users/me/notification-settings
       - Update settings (partial updates)
       - Input: NotificationSettingsUpdate
       - Output: NotificationSettingsResponse
```

### Notification Settings Schemas
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/schemas/notification_settings.py`

- `NotificationSettingsResponse` - response model
- `NotificationSettingsUpdate` - partial update model

### Frontend Settings UI
**File:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/settings/NotificationsView.vue`

Sections:
1. Email Notifications (master toggle)
2. Today's Schedule (digest toggle + time + day selector)
3. Tomorrow's Schedule (same as above)
4. Appointment Reminders (toggle + minutes dropdown)
5. Session Notes Reminder (toggle + time)

Components Used:
- `SettingsCard.vue` - reusable card component
- `ToggleSwitch.vue` - accessible toggle
- Standard HTML inputs (time, buttons)

Composable:
- `useNotificationSettings()` - fetch/update state with auto-save

---

## 3. Workspace & User Structure

### Workspace Model
**File:** `/Users/yussieik/Desktop/projects/pazpaz/models/workspace.py`

- `id: UUID`
- `name: str`
- `is_active: bool`
- `status: Enum` (active, suspended, deleted)
- `timezone: str` (IANA format, e.g., "America/New_York")
- `storage_used_bytes: BigInteger`
- `storage_quota_bytes: BigInteger`
- Relationships: users, clients, appointments, services, locations, audit_events, sessions, notification_settings

**Privacy Critical:** ALL data filtered by workspace_id

### User Model
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/user.py`

- `id: UUID`
- `workspace_id: UUID` - single workspace per user
- `email: str`
- `full_name: str`
- `role: Enum` (owner, assistant)
- `is_active: bool`
- Relationships: workspace, audit_events, notification_settings (1:1 cascade)

### Authentication Dependencies
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/api/deps.py`

Key functions:
- `get_current_user()` - extracts user from JWT token
- `get_db()` - database session
- `verify_client_in_workspace()` - validates client belongs to workspace

---

## 4. Audit & Compliance

### Audit Event Model
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/models/audit_event.py`

- `id: UUID`
- `user_id: UUID` (optional)
- `workspace_id: UUID` (optional, NULL for system-level)
- `action: Enum` (CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT, EXPORT, PRINT, SHARE)
- `resource_type: Enum` (User, Client, Appointment, Session, SessionAttachment, PlanOfCare, Service, Location, Workspace)
- `resource_id: UUID`
- `changes: dict` (JSONB, field-level changes)
- `metadata: dict` (JSONB, NO PII)
- `timestamp: datetime`
- `ip_address: str` (optional)
- `user_agent: str` (optional)

**Important:** Immutable append-only table (no updates/deletes allowed)

### Audit Service
**File:** `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/services/audit_service.py`

Function:
```python
async def create_audit_event(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    action: AuditAction,
    resource_type: ResourceType,
    resource_id: UUID,
    metadata: dict = None,
) -> AuditEvent
```

---

## 5. Performance Targets

- Conflict detection: p95 <150ms (indexed queries)
- List appointments: p95 <150ms (pagination + filters)
- Settings update: p95 <100ms (direct row update)

Key Optimizations:
- Composite indexes on (workspace_id, scheduled_start, scheduled_end)
- Partial indexes for batch job queries
- Frontend smart fetching (only refetch if outside loaded range)
- Optimistic updates with undo

---

## 6. Key Dependencies

Backend:
- FastAPI (Python 3.13.5)
- SQLAlchemy async ORM
- PostgreSQL 16
- Pydantic for validation

Frontend:
- Vue 3 (Composition API)
- TypeScript
- Tailwind CSS
- FullCalendar (@fullcalendar/vue3)
- Pinia (state management)

---

## 7. No Current Event System

Important Limitations:
- NO WebSocket events for appointment changes
- NO server-sent events (SSE)
- NO webhook system for external sync
- Audit events created but NOT for triggering external actions
- Background jobs (email reminders) run on schedule, not event-driven

This means:
- Calendar sync must use polling or ICS export
- No real-time event streaming
- Integration requires building new sync mechanisms

---

## 8. Timezone Handling

- Appointment times: stored in UTC (timezone-aware datetime)
- Notification times: stored as "HH:MM" strings
- Workspace timezone: IANA format (e.g., "America/New_York")
- Interpretation: notification times interpreted in workspace timezone
- Benefits: avoids DST complexity, supports scheduling in user's timezone

---

## File Tree Summary

```
backend/src/pazpaz/
├── models/
│   ├── appointment.py ..................... Appointment model
│   ├── user_notification_settings.py ...... Settings model
│   ├── workspace.py ....................... Workspace model
│   ├── user.py ............................ User model
│   ├── audit_event.py ..................... Audit log model
│   └── ... [others]
├── api/
│   ├── appointments.py .................... Appointment endpoints
│   ├── notification_settings.py ........... Settings endpoints
│   ├── deps.py ............................ Auth/workspace validation
│   └── ... [others]
├── schemas/
│   ├── appointment.py ..................... Appointment schemas
│   ├── notification_settings.py ........... Settings schemas
│   └── ... [others]
├── services/
│   ├── audit_service.py .................. Audit logging
│   ├── notification_settings_service.py .. Settings CRUD
│   ├── email_service.py .................. Email sending
│   └── ... [others]
└── ... [others]

frontend/src/
├── views/
│   ├── CalendarView.vue .................. Main calendar
│   └── settings/
│       └── NotificationsView.vue ......... Settings page
├── stores/
│   ├── appointments.ts ................... Appointment state
│   ├── auth.ts ........................... Auth state
│   └── clients.ts ........................ Client state
├── components/
│   ├── settings/
│   │   ├── SettingsCard.vue
│   │   └── SettingsSidebar.vue
│   ├── calendar/
│   │   ├── AppointmentFormModal.vue
│   │   ├── ConflictAlert.vue
│   │   └── ... [others]
│   └── ... [others]
├── composables/
│   ├── useNotificationSettings.ts
│   ├── useCalendarEvents.ts
│   ├── useAppointmentDrag.ts
│   └── ... [others]
└── ... [others]
```

---

## Next Steps for Calendar Sync

1. Design CalendarIntegration model for sync tracking
2. Implement ICS export endpoint (RFC 5545)
3. Add updated_since filtering to list appointments
4. Build OAuth2 flow for Google Calendar
5. Create conflict resolution policy
6. Implement webhook handlers for external calendars
7. Add real-time sync with WebSocket/SSE (phase 2)

