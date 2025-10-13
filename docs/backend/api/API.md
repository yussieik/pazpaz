# PazPaz Backend API Documentation

**Base URL**: `http://localhost:8000`
**API Version**: v1
**OpenAPI Docs**: http://localhost:8000/docs

## Authentication

All API endpoints require workspace authentication via header:
```
X-Workspace-ID: <workspace-uuid>
```

**Note**: Current implementation is for M1 development/testing only. Production requires JWT-based authentication.

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

## Next Steps (M2)

- [ ] Generate TypeScript API client from OpenAPI
- [ ] Build Vue 3 calendar UI
- [ ] Implement drag-and-drop scheduling
- [ ] Add email reminder service
