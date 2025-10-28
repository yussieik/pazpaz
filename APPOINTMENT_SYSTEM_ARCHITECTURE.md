# PazPaz Appointment System & Settings Architecture - Comprehensive Overview

## Project Context

**PazPaz** is a lightweight practice management web app for independent therapists (massage, physical therapy, psychology, etc.). It provides appointment scheduling, client management, SOAP-based session documentation, and email notifications/reminders.

**Tech Stack:**
- Backend: FastAPI (Python 3.13.5) + SQLAlchemy Async + PostgreSQL 16
- Frontend: Vue 3 (Composition API) + TypeScript + Tailwind CSS + FullCalendar
- Infrastructure: Docker Compose (api, web, db, redis)
- Auth: Passwordless (magic link) + optional 2FA
- Storage: PostgreSQL (relational data), MinIO/S3 (attachments)

---

## 1. APPOINTMENT SYSTEM

### 1.1 Database Model: Appointment

**File:** `/backend/src/pazpaz/models/appointment.py`

```python
class Appointment(Base):
    __tablename__ = "appointments"
    
    # Core fields
    id: UUID (primary_key)
    workspace_id: UUID (ForeignKey, indexed) - ensures workspace scoping
    client_id: UUID (ForeignKey, indexed) - client reference
    service_id: UUID (ForeignKey, optional) - predefined service type
    location_id: UUID (ForeignKey, optional) - saved location reference
    
    # Time fields (UTC, timezone-aware)
    scheduled_start: datetime(tz) - appointment start
    scheduled_end: datetime(tz) - appointment end
    
    # Location info
    location_type: Enum (clinic|home|online)
    location_details: Text (optional) - address, room, video link, etc.
    
    # Status & Notes
    status: Enum (scheduled|completed|cancelled|no_show)
    notes: Text (optional) - therapist notes
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    edited_at: datetime (optional) - when last edited
    edit_count: int - number of edits
    
    # Relationships
    workspace: Workspace (back_populates="appointments")
    client: Client (back_populates="appointments")
    service: Service (optional)
    location: Location (optional)
    session: Session (1:1, optional) - SOAP notes for this appointment
```

**Performance Indexes:**
- `ix_appointments_workspace_time_range(workspace_id, scheduled_start, scheduled_end)` - for conflict detection & calendar queries
- `ix_appointments_workspace_client_time(workspace_id, client_id, scheduled_start)` - for client timeline
- `ix_appointments_workspace_status(workspace_id, status)` - for filtering by status
- **Performance Target:** p95 <150ms for conflict detection queries

**Key Constraints:**
- All appointments scoped to workspace (privacy isolation)
- Time range overlaps treated as conflicts (except back-to-back adjacency)
- Status transitions validated (see appointment API)

---

### 1.2 Appointment API Endpoints

**File:** `/backend/src/pazpaz/api/appointments.py`

#### Create Appointment (POST /api/v1/appointments)
```python
@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    appointment_data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse
```
- **Validates:** Client belongs to workspace
- **Conflict Detection:** Checks for overlapping appointments (time_range index)
- **Response:** AppointmentResponse with client summary
- **Security:** workspace_id injected from JWT (server-side)
- **Audit:** Logs appointment creation

#### List Appointments (GET /api/v1/appointments)
```python
@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    start_date: datetime | None = Query(None),  # Date range filter
    end_date: datetime | None = Query(None),
    client_id: uuid.UUID | None = Query(None),  # Client filter
    status: AppointmentStatus | None = Query(None),  # Status filter
) -> AppointmentListResponse
```
- **Returns:** Paginated list with total count, ordered by scheduled_start DESC
- **Filters:** Date range, client, status
- **Workspace Scoped:** Only returns current user's workspace appointments

#### Get Single Appointment (GET /api/v1/appointments/{appointment_id})
- **Security:** Returns 404 for non-existent or cross-workspace appointments
- **Response:** Full AppointmentResponse with client details

#### Update Appointment (PUT /api/v1/appointments/{appointment_id})
```python
@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: uuid.UUID,
    appointment_data: AppointmentUpdate,
    allow_conflict: bool = Query(False),  # Allow if conflicts exist
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse
```
- **Partial Updates:** Only provided fields updated
- **Conflict Detection:** If time changes, re-checks conflicts (unless allow_conflict=True)
- **Status Validation:** Validates appointment status transitions
- **Edit Tracking:** Updates edited_at and edit_count
- **Audit:** Logs field-level changes

**Status Transitions (Validated):**
- SCHEDULED → COMPLETED, CANCELLED, NO_SHOW (always allowed)
- COMPLETED → NO_SHOW (correction)
- COMPLETED → CANCELLED (blocked if session exists - data protection)
- COMPLETED → SCHEDULED (blocked - data integrity)
- CANCELLED → SCHEDULED (restore allowed)
- NO_SHOW → SCHEDULED, COMPLETED (correction)

#### Check Conflicts (GET /api/v1/appointments/conflicts)
```python
@router.get("/conflicts", response_model=ConflictCheckResponse)
async def check_appointment_conflicts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scheduled_start: datetime = Query(...),
    scheduled_end: datetime = Query(...),
    exclude_appointment_id: uuid.UUID | None = Query(None),  # For updates
) -> ConflictCheckResponse
```
- **Used by Frontend:** Before submitting appointment form
- **Returns:** has_conflict boolean + list of conflicting appointments with client initials (privacy)
- **Conflict Logic:** Overlaps detected EXCEPT back-to-back (exact adjacency OK)

#### Delete Appointment (DELETE /api/v1/appointments/{appointment_id})
```python
@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    deletion_request: AppointmentDeleteRequest | None = Body(None),
) -> None
```
- **Handles Session Notes:** Can optionally soft-delete attached session notes
- **Prevents Amended Session Deletion:** Blocks if session has been amended (medical-legal)
- **Soft Delete:** Sessions get 30-day grace period with permanent_delete_after timestamp
- **Comprehensive Audit:** Logs appointment status, session action, deletion reason

---

### 1.3 Frontend Appointment System

**Calendar View:** `/frontend/src/views/CalendarView.vue`

**Features:**
- Weekly/Day/Month calendar views using FullCalendar
- Appointment creation via modal
- Appointment editing with drag-and-drop rescheduling
- Conflict detection with modal warnings
- Optimistic updates with undo support
- Mobile-responsive with time picker modal
- Keyboard navigation support

**Appointments Store:** `/frontend/src/stores/appointments.ts`
```typescript
type AppointmentListItem  // From OpenAPI schema
type AppointmentCreate    // From OpenAPI schema
type AppointmentUpdate    // From OpenAPI schema

// Computed
hasAppointments: boolean
loadedRange: { startDate, endDate } | null

// Methods
async fetchAppointments(startDate?, endDate?, page, pageSize)
async createAppointment(data)
async updateAppointment(id, data)
async deleteAppointment(id)
async checkConflicts(start, end, excludeId?)
```

**Composables:**
- `useCalendarEvents()` - manages event state and UI interactions
- `useAppointmentDrag()` - handles drag-and-drop rescheduling
- `useCalendarCreation()` - manages creation modal
- `useCalendarKeyboardShortcuts()` - keyboard accessibility
- `useCalendarLoading()` - loading state management

---

## 2. SETTINGS SYSTEM

### 2.1 User Notification Settings Model

**File:** `/backend/src/pazpaz/models/user_notification_settings.py`

**Purpose:** Stores notification preferences per user (one-to-one with User).

```python
class UserNotificationSettings(Base):
    __tablename__ = "user_notification_settings"
    
    # Foreign Keys
    id: UUID (primary_key)
    user_id: UUID (ForeignKey, unique) - one-to-one with User
    workspace_id: UUID (ForeignKey) - for workspace scoping
    
    # Master Toggle
    email_enabled: bool (default=True) - master switch for ALL emails
    
    # Event Notifications
    notify_appointment_booked: bool
    notify_appointment_cancelled: bool
    notify_appointment_rescheduled: bool
    notify_appointment_confirmed: bool
    
    # Today's Schedule Digest
    digest_enabled: bool (default=False)
    digest_time: str (HH:MM format, workspace timezone)
    digest_days: list[int] (0=Sunday, 1=Monday, ..., 6=Saturday)
    
    # Tomorrow's Schedule Digest
    tomorrow_digest_enabled: bool (default=False)
    tomorrow_digest_time: str (HH:MM, workspace timezone)
    tomorrow_digest_days: list[int]
    
    # Appointment Reminders
    reminder_enabled: bool (default=True)
    reminder_minutes: int (valid: 15, 30, 60, 120, 1440)
    
    # Session Notes Reminders
    notes_reminder_enabled: bool (default=True)
    notes_reminder_time: str (HH:MM, workspace timezone)
    
    # Future Extensibility
    extended_settings: dict (JSONB) - for SMS, push, quiet hours, etc.
    
    # Audit
    created_at: datetime
    updated_at: datetime
```

**Validation:**
- Time format: CHECK constraint enforces HH:MM pattern
- Reminder minutes: CHECK constraint allows only 15, 30, 60, 120, 1440
- At least one day required for digest (enforced on frontend)

**Indexes:**
- `idx_user_notification_settings_workspace_id` - for workspace queries
- `idx_user_notification_settings_workspace_user` - composite for user lookup
- `idx_user_notification_settings_digest` (partial) - for digest batch jobs
- `idx_user_notification_settings_tomorrow_digest` (partial) - for tomorrow digest jobs
- `idx_user_notification_settings_reminder` (partial) - for reminder batch jobs

**Helper Methods:**
```python
should_send_emails() -> bool  # Returns email_enabled
should_send_digest() -> bool  # Returns email_enabled AND digest_enabled
should_send_tomorrow_digest() -> bool
should_send_reminder() -> bool
should_send_notes_reminder() -> bool
get_extended_setting(key_path: str) -> Any  # Dot notation JSONB access
set_extended_setting(key_path: str, value: Any) -> None
validate() -> list[str]  # Returns validation errors
```

---

### 2.2 Notification Settings API

**File:** `/backend/src/pazpaz/api/notification_settings.py`

#### Get Settings (GET /api/v1/users/me/notification-settings)
```python
@router.get(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    status_code=200,
)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse
```
- Returns current user's settings (creates defaults if don't exist)
- **No filtering needed:** user_id from JWT

#### Update Settings (PUT /api/v1/users/me/notification-settings)
```python
@router.put(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    status_code=200,
)
async def update_notification_settings(
    updates: NotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse
```
- Partial updates (only provided fields modified)
- **Validation:** Time format, reminder minutes checked
- **Error Handling:** 400 on validation errors, 500 on DB errors
- **Auto-create:** Creates settings with defaults if don't exist
- **Commit & Refresh:** Ensures latest state returned

---

### 2.3 Frontend Settings UI

**Notifications Settings View:** `/frontend/src/views/settings/NotificationsView.vue`

**Features:**
1. **Master Toggle:**
   - Email notifications on/off
   - Warning banner when disabled

2. **Today's Schedule Digest:**
   - Toggle enable/disable
   - Send time picker (HH:MM)
   - Day-of-week selector (toggleable buttons)
   - Quick actions: "Weekdays only", "Every day"
   - Warning if no days selected

3. **Tomorrow's Schedule Digest:**
   - Same controls as today's digest
   - Different default time (8:00 PM)

4. **Appointment Reminders:**
   - Toggle enable/disable
   - Dropdown selector for reminder minutes (15, 30, 60, 120, 1440)

5. **Session Notes Reminders:**
   - Toggle enable/disable
   - Send time picker

**Composable:** `useNotificationSettings()`
```typescript
settings: Ref<NotificationSettings | null>
isLoading: Ref<boolean>
error: Ref<string | null>

loadSettings(): Promise<void>
// Auto-saves settings via composable (not shown in view)
```

**Components:**
- `SettingsCard.vue` - reusable card with toggle and content sections
- `ToggleSwitch.vue` - accessible toggle component
- Standard HTML inputs for time and day selection

---

### 2.4 Workspace Settings

**File:** `/backend/src/pazpaz/models/workspace.py`

**Relevant Fields:**
```python
timezone: str (default="UTC")  # IANA timezone (e.g., "America/New_York")
# Used for scheduling notification digest emails
```

**Time Interpretation:**
- All appointment times stored in UTC (timezone-aware)
- Notification times (digest_time, reminder_time) stored as "HH:MM" strings
- Interpreted in workspace timezone when scheduling digests/reminders
- Avoids DST complexity

---

## 3. WORKSPACE & USER STRUCTURE

### 3.1 Workspace Model

**File:** `/backend/src/pazpaz/models/workspace.py`

```python
class Workspace(Base):
    id: UUID
    name: str
    is_active: bool (default=True)
    status: Enum (active|suspended|deleted)
    deleted_at: datetime (optional)
    created_at: datetime
    updated_at: datetime
    
    # Storage Management
    storage_used_bytes: BigInteger
    storage_quota_bytes: BigInteger (default=10GB)
    storage_usage_percentage: float (property)
    is_quota_exceeded: bool (property)
    storage_remaining_bytes: int (property)
    
    # Timezone for notification scheduling
    timezone: str (default="UTC", IANA format)
    
    # Relationships
    users: list[User]
    clients: list[Client]
    appointments: list[Appointment]
    services: list[Service]
    locations: list[Location]
    audit_events: list[AuditEvent]
    sessions: list[Session]
    notification_settings: list[UserNotificationSettings]
```

**Workspace Scoping:**
- ALL data queries MUST filter by workspace_id
- Prevents cross-workspace data leakage
- Enforced at API layer with get_current_user dependency

---

### 3.2 User Model

**File:** `/backend/src/pazpaz/models/user.py`

```python
class User(Base):
    id: UUID
    workspace_id: UUID (ForeignKey) - single workspace per user
    email: str
    full_name: str
    role: Enum (owner|assistant)
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Platform Admin Access
    is_platform_admin: bool
    
    # Invitation Tracking
    invitation_token_hash: str (SHA256)
    invited_by_platform_admin: bool
    invited_at: datetime
    
    # 2FA/TOTP
    totp_secret: str (EncryptedString)
    totp_enabled: bool
    totp_backup_codes: str (EncryptedString, JSON array)
    totp_enrolled_at: datetime
    
    # Relationships
    workspace: Workspace
    audit_events: list[AuditEvent]
    notification_settings: UserNotificationSettings (1:1, cascade delete)
```

**Constraints:**
- Email unique per workspace (uq_users_workspace_email)
- Exactly one workspace per user
- Settings cascade delete with user

---

## 4. EVENT & AUDIT SYSTEM

### 4.1 Audit Event Model

**File:** `/backend/src/pazpaz/models/audit_event.py`

```python
class AuditEvent(Base):
    """Immutable audit log for HIPAA compliance."""
    
    id: UUID (primary_key)
    user_id: UUID (ForeignKey, optional)
    workspace_id: UUID (ForeignKey, optional)
    action: Enum (CREATE|READ|UPDATE|DELETE|LOGIN|LOGOUT|EXPORT|PRINT|SHARE)
    resource_type: Enum (User|Client|Appointment|Session|SessionAttachment|
                         PlanOfCare|Service|Location|Workspace)
    resource_id: UUID
    
    # Field-level changes (for UPDATE actions)
    changes: dict (JSONB, optional)  # {"field": {"old": "...", "new": "..."}}
    
    # Additional context (NO PII/PHI)
    metadata: dict (JSONB, optional)
    
    timestamp: datetime (auto-generated)
    ip_address: str (optional)
    user_agent: str (optional)
```

**Key Properties:**
- **Immutable:** Cannot be updated/deleted (enforced by DB triggers)
- **Workspace-scoped:** Most events belong to workspace (some system-level have NULL workspace_id)
- **Field-level Tracking:** Changes dict captures old/new values for UPDATE actions
- **No PII:** metadata field must NOT contain PII/PHI

**Audit Service:** `/backend/src/pazpaz/services/audit_service.py`
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

### 4.2 Current Event System

**Status:** No real-time event/webhook system yet implemented.

**Existing Notification System:**
- **Email Reminders:** Background jobs (Celery/APScheduler via Redis)
- **Notification Services:**
  - `notification_query_service.py` - queries for scheduled reminders
  - `notification_content_service.py` - renders email templates
  - `email_service.py` - sends emails
  - `reminder_tracking_service.py` - tracks sent reminders

**No Direct Event Emission:**
- Appointments create audit events (for compliance)
- No event broadcasting to other systems
- No webhooks for external calendar sync

---

## 5. CALENDAR SYNC REQUIREMENTS & ARCHITECTURE IMPLICATIONS

### Current Limitations for Sync Implementation

1. **No Event Streaming:**
   - No WebSocket events for appointment changes
   - No server-sent event (SSE) endpoints
   - Clients must poll for updates or refresh manually

2. **No Real-time Notification:**
   - Audit events created for compliance, not for triggering sync
   - Background jobs run on schedule, not event-driven

3. **ID Generation:**
   - UUIDs used (good for distributed systems)
   - Supports external calendar integration (UID in ICS)

4. **Timestamp Fields:**
   - All times timezone-aware UTC
   - updated_at field tracks changes
   - edited_at field optional (null if never edited)
   - edit_count tracks number of edits

5. **Status Tracking:**
   - Appointment status: scheduled, completed, cancelled, no_show
   - Can determine if appointment was deleted (no soft-delete flag currently)
   - Changes to status are audited

### For Calendar Sync Implementation

**Recommended Approach:**
1. **ICS/iCal Export Endpoint:**
   - Generate ICS for workspace appointments (time range)
   - Use appointment.id as UID (RFC 5545 compliant)
   - Include X-PAZPAZ-STATUS custom property
   - Use DTSTAMP = updated_at for change detection

2. **Polling-based Sync:**
   - Frontend periodically checks for updated_at >= last_sync_timestamp
   - Query: GET /appointments?start_date=X&end_date=Y&updated_since=Z
   - Efficient for low-frequency changes

3. **Server-Sent Events (Optional Enhancement):**
   - New endpoint: GET /appointments/stream
   - Stream changes in real-time
   - Requires frontend subscription management

4. **External Calendar Sync:**
   - Google Calendar: OAuth2 flow to push/pull events
   - Requires new CalendarIntegration model
   - Webhook from Google on changes
   - Sync status tracking

---

## 6. KEY DATA RELATIONSHIPS

```
Workspace (root context)
  ├── Users (therapists/assistants)
  │   └── UserNotificationSettings (1:1, cascade)
  ├── Clients
  ├── Appointments
  │   ├── Client (foreign key)
  │   ├── Service (optional)
  │   ├── Location (optional)
  │   └── Session (1:1, optional) - SOAP notes
  ├── Services
  ├── Locations
  ├── Sessions (SOAP notes)
  │   ├── Appointment (1:1)
  │   └── SessionAttachment
  └── AuditEvents (immutable logs)
```

---

## 7. SECURITY & PRIVACY

### Workspace Scoping
- All queries MUST check workspace_id = current_user.workspace_id
- Enforced at API layer via get_current_user dependency
- User belongs to exactly one workspace

### Data Encryption
- TOTP secrets: EncryptedString (app-level encryption)
- Session notes content: EncryptedString (all SOAP fields encrypted at rest)
- SessionAttachments: Encrypted in S3/MinIO

### Audit Logging
- All data access/modifications logged to AuditEvent table
- Immutable append-only table (no updates/deletes)
- Supports HIPAA compliance reporting
- No PII in audit metadata

### Authentication
- Passwordless (magic link) via email
- Optional 2FA (TOTP)
- JWT token includes workspace_id
- HttpOnly cookies with SameSite=Lax

---

## 8. FRONTEND ARCHITECTURE

### State Management (Pinia Stores)
- `auth.ts` - authentication state
- `appointments.ts` - appointment list, CRUD
- `clients.ts` - client list, CRUD

### API Integration
- Generated TypeScript client from OpenAPI spec
- apiClient wraps axios with auth headers
- Types extracted from OpenAPI paths

### Composables
- `useNotificationSettings()` - settings fetch/update
- `useCalendar()` - calendar view state
- `useCalendarEvents()` - event rendering
- `useAppointmentDrag()` - drag-drop logic
- `useToast()` - notification toasts

### Components
- Reusable: ToggleSwitch, SettingsCard, TimePickerDropdown
- Calendar: AppointmentFormModal, ConflictAlert, DragConflictModal
- Settings: NotificationsView with SettingsSidebar

---

## 9. IMPLEMENTATION CHECKLIST FOR CALENDAR SYNC

### Phase 1: Foundation (Minimal)
- [ ] Add sync_token/last_modified tracking to UserNotificationSettings
- [ ] Create ICS export endpoint (GET /api/v1/appointments/export.ics)
- [ ] Add updated_since query parameter to list appointments endpoint
- [ ] Frontend: Add "Export Calendar" button to toolbar
- [ ] Generate ICS with PRODID=-//PazPaz//EN, VERSION:2.0

### Phase 2: Google Calendar Integration (Medium)
- [ ] New model: CalendarIntegration (workspace, oauth_token, sync_direction)
- [ ] OAuth2 flow for Google Calendar authentication
- [ ] Sync service: push appointment changes to Google
- [ ] Sync service: pull events from Google Calendar
- [ ] Settings UI: connect/disconnect Google Calendar
- [ ] Webhook handler: receive Google Calendar change notifications

### Phase 3: Real-time Sync (Advanced)
- [ ] WebSocket/SSE endpoint for appointment changes
- [ ] Frontend: subscribe to live updates
- [ ] Calendar integration change streaming
- [ ] Conflict resolution policy (local vs. remote wins)

---

## 10. FILE STRUCTURE REFERENCE

### Backend Models
```
backend/src/pazpaz/models/
├── appointment.py (AppointmentStatus, LocationType, Appointment)
├── user.py (User, UserRole)
├── workspace.py (Workspace, WorkspaceStatus)
├── user_notification_settings.py (UserNotificationSettings)
├── audit_event.py (AuditEvent, AuditAction, ResourceType)
├── client.py
├── session.py
└── ... [others]
```

### Backend API
```
backend/src/pazpaz/api/
├── appointments.py (CRUD endpoints + conflict checking)
├── notification_settings.py (GET/PUT settings)
├── deps.py (get_current_user, get_db, verify_client_in_workspace)
└── ... [others]
```

### Backend Schemas
```
backend/src/pazpaz/schemas/
├── appointment.py (AppointmentCreate, AppointmentResponse, ConflictCheckResponse)
├── notification_settings.py (NotificationSettingsResponse, NotificationSettingsUpdate)
└── ... [others]
```

### Backend Services
```
backend/src/pazpaz/services/
├── notification_settings_service.py (get/update settings)
├── audit_service.py (create_audit_event)
├── email_service.py (send emails)
├── notification_query_service.py (batch query settings)
└── ... [others]
```

### Frontend Views
```
frontend/src/views/
├── CalendarView.vue (appointment calendar)
├── settings/
│   └── NotificationsView.vue (notification settings)
└── ... [others]
```

### Frontend Stores
```
frontend/src/stores/
├── appointments.ts (appointment CRUD)
├── auth.ts (authentication)
└── clients.ts (client management)
```

### Frontend Components
```
frontend/src/components/
├── settings/
│   ├── SettingsCard.vue
│   └── SettingsSidebar.vue
├── calendar/
│   ├── AppointmentFormModal.vue
│   ├── ConflictAlert.vue
│   ├── DragConflictModal.vue
│   └── ... [others]
└── ... [others]
```

---

## 11. PERFORMANCE & CONSTRAINTS

### Performance Targets
- Conflict detection: p95 <150ms (indexed query)
- List appointments: p95 <150ms (pagination + date filters)
- Settings update: p95 <100ms (direct row update)

### Database Constraints
- PostgreSQL 16 with async SQLAlchemy ORM
- Workspace scoping: mandatory in WHERE clauses
- Indexes optimized for time-range queries

### Frontend Constraints
- Calendar renders max 50-100 events per view (pagination)
- Smart fetching: only refetch if date outside loaded range
- Optimistic updates with undo support

---

## 12. NEXT STEPS FOR CALENDAR SYNC

Based on this architecture:

1. **Design Event Model:** CalendarIntegration or CalendarSyncToken
2. **Define ICS Generation:** RFC 5545 compliance, UID=appointment.id
3. **Implement Sync Endpoints:** Export endpoint, polling endpoint
4. **Add Frontend Settings:** Calendar sync toggles, connection UI
5. **OAuth2 Integration:** For Google Calendar / Apple Calendar
6. **Webhook Handling:** Receive external calendar changes
7. **Conflict Resolution:** Policy when local ≠ remote
8. **Testing:** Unit, integration, e2e for sync workflows

