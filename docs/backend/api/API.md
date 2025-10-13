# PazPaz Backend API Documentation

**Base URL**: `http://localhost:8000`
**API Version**: v1
**OpenAPI Docs**: http://localhost:8000/docs
**Last Updated**: 2025-01-13

## Table of Contents

- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health Checks](#health-checks)
  - [Clients](#clients)
  - [Appointments](#appointments)
  - [Services](#services)
  - [Locations](#locations)
  - [Sessions (SOAP Notes)](#sessions-soap-notes)
  - [Session Attachments](#session-attachments)
  - [Authentication](#authentication-1)
  - [Audit Logs](#audit-logs)
- [Error Responses](#error-responses)
- [Performance](#performance)
- [Development](#development)

## Authentication

All API endpoints (except auth endpoints) require JWT authentication:
```
Authorization: Bearer <jwt-token>
```

The JWT token contains workspace_id for automatic workspace scoping. Obtain a token via the magic link authentication flow (see [Authentication endpoints](#authentication-1)).

## Endpoints

### Health Checks

#### GET /health
System health check

#### GET /api/v1/health
API v1 health check

---

### Clients

#### POST /api/v1/clients
Create a new client

**Request Body**:
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "phone": "+1234567890",
  "date_of_birth": "1990-01-01",
  "consent_status": true,
  "notes": "Optional notes",
  "tags": ["vip", "massage"]
}
```

**Response**: `201 Created`

#### GET /api/v1/clients
List clients (paginated)

**Query Parameters**:
- `page` (default: 1)
- `page_size` (default: 50, max: 100)

**Response**: `200 OK`

#### GET /api/v1/clients/{client_id}
Get client by ID

**Response**: `200 OK` or `404 Not Found`

#### PUT /api/v1/clients/{client_id}
Update client (partial updates supported)

**Request Body**: Same as POST (all fields optional)

**Response**: `200 OK` or `404 Not Found`

#### DELETE /api/v1/clients/{client_id}
Delete client (cascades to appointments)

**Response**: `204 No Content` or `404 Not Found`

---

### Appointments

#### POST /api/v1/appointments
Create appointment with conflict detection

**Request Body**:
```json
{
  "client_id": "uuid",
  "service_id": "uuid",
  "location_id": "uuid",
  "scheduled_start": "2025-10-01T10:00:00Z",
  "scheduled_end": "2025-10-01T11:00:00Z",
  "location_type": "clinic",
  "location_details": "Room 101",
  "status": "scheduled",
  "notes": "Initial consultation"
}
```

**Response**: `201 Created` or `409 Conflict` (if overlaps with existing appointment)

#### GET /api/v1/appointments
List appointments (paginated, filterable)

**Query Parameters**:
- `page`, `page_size` (pagination)
- `start_date`, `end_date` (ISO 8601 datetime, for calendar view)
- `client_id` (filter by client)
- `status` (filter by status: scheduled, completed, cancelled, no_show)

**Response**: `200 OK`

#### GET /api/v1/appointments/conflicts
Check for appointment conflicts

**Query Parameters**:
- `scheduled_start` (required, ISO 8601 datetime)
- `scheduled_end` (required, ISO 8601 datetime)
- `exclude_appointment_id` (optional, for update scenarios)

**Response**: `200 OK`
```json
{
  "has_conflict": false,
  "conflicting_appointments": []
}
```

#### GET /api/v1/appointments/{appointment_id}
Get appointment by ID

**Response**: `200 OK` or `404 Not Found`

#### PUT /api/v1/appointments/{appointment_id}
Update appointment (re-checks conflicts)

**Request Body**: Same as POST (all fields optional)

**Response**: `200 OK`, `404 Not Found`, or `409 Conflict`

#### DELETE /api/v1/appointments/{appointment_id}
Delete appointment

**Response**: `204 No Content` or `404 Not Found`

---

### Services

#### POST /api/v1/services
Create service

**Request Body**:
```json
{
  "name": "Deep Tissue Massage",
  "description": "Therapeutic massage focusing on deeper muscle layers",
  "default_duration_minutes": 60,
  "is_active": true
}
```

**Response**: `201 Created` or `409 Conflict` (duplicate name)

#### GET /api/v1/services
List services (paginated, filterable)

**Query Parameters**:
- `page`, `page_size` (pagination)
- `is_active` (filter by active status, default: true)

**Response**: `200 OK`

#### GET /api/v1/services/{service_id}
Get service by ID

**Response**: `200 OK` or `404 Not Found`

#### PUT /api/v1/services/{service_id}
Update service

**Request Body**: Same as POST (all fields optional)

**Response**: `200 OK` or `404 Not Found`

#### DELETE /api/v1/services/{service_id}
Delete service (soft delete if in use, hard delete otherwise)

**Response**: `204 No Content` or `404 Not Found`

---

### Locations

#### POST /api/v1/locations
Create location

**Request Body**:
```json
{
  "name": "Main Clinic",
  "location_type": "clinic",
  "address": "123 Therapy Lane, Suite 200, Toronto, ON M5H 2N2",
  "details": "Ground floor, free parking in back",
  "is_active": true
}
```

**Response**: `201 Created` or `409 Conflict` (duplicate name) or `422 Validation Error` (address required for clinic/home)

#### GET /api/v1/locations
List locations (paginated, filterable)

**Query Parameters**:
- `page`, `page_size` (pagination)
- `is_active` (filter by active status, default: true)
- `location_type` (filter by type: clinic, home, online)

**Response**: `200 OK`

#### GET /api/v1/locations/{location_id}
Get location by ID

**Response**: `200 OK` or `404 Not Found`

#### PUT /api/v1/locations/{location_id}
Update location

**Request Body**: Same as POST (all fields optional)

**Response**: `200 OK` or `404 Not Found`

#### DELETE /api/v1/locations/{location_id}
Delete location (soft delete if in use, hard delete otherwise)

**Response**: `204 No Content` or `404 Not Found`

---

### Sessions (SOAP Notes)

#### POST /api/v1/sessions
Create new session note for appointment

**Request Body**:
```json
{
  "appointment_id": "uuid",
  "subjective": "Patient reports feeling better...",
  "objective": "ROM improved to 120 degrees...",
  "assessment": "Good progress with treatment plan...",
  "plan": "Continue current protocol...",
  "is_draft": true
}
```

**Response**: `201 Created`

#### GET /api/v1/sessions
List session notes (paginated, filterable)

**Query Parameters**:
- `page`, `page_size` (pagination)
- `client_id` (filter by client)
- `is_draft` (filter by draft status)
- `start_date`, `end_date` (filter by date range)

**Response**: `200 OK`

#### GET /api/v1/sessions/{session_id}
Get session note by ID

**Response**: `200 OK` or `404 Not Found`

#### PUT /api/v1/sessions/{session_id}
Update session note (creates version if finalized)

**Request Body**: Same as POST (all fields optional)

**Response**: `200 OK` or `404 Not Found`

#### PATCH /api/v1/sessions/{session_id}/draft
Autosave draft updates (rate limited to 1 per 5 seconds)

**Request Body**:
```json
{
  "subjective": "Updated subjective text..."
}
```

**Response**: `200 OK` or `429 Too Many Requests`

#### POST /api/v1/sessions/{session_id}/finalize
Finalize session note (creates version 1)

**Response**: `200 OK` or `422 Unprocessable Entity` (if already finalized)

#### GET /api/v1/sessions/{session_id}/versions
Get version history of finalized session

**Response**: `200 OK` (array of versions in reverse chronological order)

#### DELETE /api/v1/sessions/{session_id}
Soft delete session note

**Response**: `204 No Content` or `404 Not Found`

#### POST /api/v1/sessions/{session_id}/restore
Restore soft-deleted session note

**Response**: `200 OK` or `404 Not Found`

#### DELETE /api/v1/sessions/{session_id}/permanent
Permanently delete session note (hard delete)

**Response**: `204 No Content` or `404 Not Found`

---

### Session Attachments

#### POST /api/v1/sessions/{session_id}/attachments
Upload attachment to session (max 10MB, images/PDFs only)

**Request**: Multipart form data
- `file` - File upload (image/jpeg, image/png, image/webp, application/pdf)
- `description` (optional) - File description

**Response**: `201 Created`
```json
{
  "id": "attachment-uuid",
  "session_id": "session-uuid",
  "file_name": "xray-front.jpg",
  "mime_type": "image/jpeg",
  "file_size": 2048576,
  "description": "Front view X-ray",
  "storage_path": "encrypted-path",
  "created_at": "2025-01-15T10:00:00Z"
}
```

#### GET /api/v1/sessions/{session_id}/attachments
List attachments for session

**Response**: `200 OK` (array of attachment metadata)

#### GET /api/v1/attachments/{attachment_id}
Download attachment file

**Response**: `200 OK` (file stream) or `404 Not Found`

#### DELETE /api/v1/attachments/{attachment_id}
Delete attachment

**Response**: `204 No Content` or `404 Not Found`

---

### Authentication

#### POST /api/v1/auth/request-magic-link
Request magic link for passwordless login

**Request Body**:
```json
{
  "email": "therapist@example.com"
}
```

**Response**: `200 OK` (always succeeds to prevent email enumeration)

**Rate Limit**: 3 requests per hour per IP

#### GET /api/v1/auth/verify-magic-link
Verify magic link token and get JWT

**Query Parameters**:
- `token` (required) - Magic link token from email

**Response**: `200 OK`
```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user": {
    "id": "user-uuid",
    "email": "therapist@example.com",
    "workspace_id": "workspace-uuid"
  }
}
```

#### POST /api/v1/auth/logout
Logout and blacklist JWT token

**Headers**:
- `Authorization: Bearer {jwt-token}`

**Response**: `200 OK`

---

### Audit Logs

#### GET /api/v1/audit
List audit events (paginated, filterable)

**Query Parameters**:
- `page`, `page_size` (pagination)
- `resource_type` (filter by type: Client, Appointment, Session)
- `resource_id` (filter by specific resource)
- `event_type` (filter by event: created, updated, deleted)
- `start_date`, `end_date` (filter by date range)
- `user_id` (filter by user who performed action)

**Response**: `200 OK`
```json
{
  "items": [
    {
      "id": "audit-uuid",
      "workspace_id": "workspace-uuid",
      "event_type": "appointment.deleted",
      "resource_type": "Appointment",
      "resource_id": "appt-uuid",
      "action": "DELETE",
      "user_id": "user-uuid",
      "metadata": {
        "appointment_status": "completed",
        "had_session_note": true,
        "deletion_reason": "Duplicate entry"
      },
      "created_at": "2025-01-15T10:00:00Z"
    }
  ],
  "total": 1234,
  "page": 1,
  "page_size": 50
}
```

#### GET /api/v1/audit/{audit_event_id}
Get specific audit event

**Response**: `200 OK` or `404 Not Found`

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message"
}
```

### Status Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `204 No Content` - Resource deleted
- `401 Unauthorized` - Missing or invalid workspace header
- `404 Not Found` - Resource not found or access denied
- `409 Conflict` - Duplicate resource or appointment conflict
- `422 Unprocessable Entity` - Validation error

---

## Performance

**Target**: p95 < 150ms for schedule endpoints

**Tested Scenarios**:
- Calendar view (7-day range)
- Client timeline
- Conflict detection
- Concurrent requests

See `PERFORMANCE_TESTING.md` for details.

---

## Development

**Start Server**:
```bash
cd backend
uv run uvicorn pazpaz.main:app --reload --host 0.0.0.0 --port 8000
```

**Run Tests**:
```bash
cd backend
export PYTHONPATH=src
uv run pytest tests/ -v
```

**Run Performance Tests**:
```bash
uv run pytest -m performance -v
```

**Interactive API Docs**:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

---

## See Also

### Implementation Guides
- [Flexible Record Management](./FLEXIBLE_RECORD_MANAGEMENT.md) - Appointment/session editing patterns
- [Rate Limiting Implementation](./RATE_LIMITING_IMPLEMENTATION.md) - Rate limiting patterns
- [API Documentation Index](./README.md) - API documentation overview

### Related Documentation
- [Backend Architecture](/backend/docs/README.md) - Overall backend structure
- [Database Schema](/backend/docs/database/) - Database design
- [PHI Encryption](/backend/docs/encryption/) - Encryption patterns
- [Security Patterns](/docs/security/) - HIPAA compliance
- [Testing Strategy](/backend/docs/testing/) - Testing patterns

### Source Code
- [API Implementations](/backend/src/pazpaz/api/) - Endpoint source code
- [Pydantic Schemas](/backend/src/pazpaz/schemas/) - Request/response models
- [Database Models](/backend/src/pazpaz/models/) - SQLAlchemy models
