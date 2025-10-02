# Backend Integration Tasks - Client Schema Updates

**From:** database-architect
**To:** fullstack-backend-specialist
**Priority:** CRITICAL (Blocks Frontend)
**Migration Created:** `83680210d7d2_add_client_healthcare_fields.py`

---

## Overview

The database schema has been updated to include 5 missing Client fields that the frontend expects. The database migration and SQLAlchemy models have been updated. You need to update the Pydantic schemas and API endpoints to expose these fields.

---

## What I've Done (database-architect)

1. **Created Migration:** `/backend/alembic/versions/83680210d7d2_add_client_healthcare_fields.py`
   - Adds: `address`, `medical_history`, `emergency_contact_name`, `emergency_contact_phone`, `is_active`
   - Adds partial index for active clients: `ix_clients_workspace_active`

2. **Updated Client Model:** `/backend/src/pazpaz/models/client.py`
   - Added all 5 new fields with proper types and comments
   - Added partial index definition in `__table_args__`

3. **Created Review Report:** `/backend/DATABASE_ARCHITECTURE_REVIEW.md`
   - Comprehensive analysis of database schema, indexes, and performance

---

## What You Need to Do (fullstack-backend-specialist)

### Task 1: Update Pydantic Schemas

**File:** `/backend/src/pazpaz/schemas/client.py`

#### 1.1 Update `ClientBase` Schema

Add the new fields to the base schema:

```python
class ClientBase(BaseModel):
    """Base schema with common client fields."""

    first_name: str = Field(
        ..., min_length=1, max_length=255, description="Client's first name"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=255, description="Client's last name"
    )
    email: EmailStr | None = Field(None, description="Client's email address")
    phone: str | None = Field(None, max_length=50, description="Client's phone number")
    date_of_birth: date | None = Field(None, description="Client's date of birth")

    # NEW FIELDS - Add these:
    address: str | None = Field(None, description="Client's physical address")
    medical_history: str | None = Field(
        None, description="Relevant medical history and conditions (PHI)"
    )
    emergency_contact_name: str | None = Field(
        None, max_length=255, description="Emergency contact person's name"
    )
    emergency_contact_phone: str | None = Field(
        None, max_length=50, description="Emergency contact phone number"
    )
    is_active: bool = Field(
        default=True, description="Active status (false = archived/soft deleted)"
    )

    consent_status: bool = Field(
        default=False, description="Client consent to store and process data"
    )
    notes: str | None = Field(None, description="General notes about the client")
    tags: list[str] | None = Field(
        None, description="Tags for categorization and filtering"
    )
```

#### 1.2 Update `ClientUpdate` Schema

Add the new fields as optional (for partial updates):

```python
class ClientUpdate(BaseModel):
    """Schema for updating an existing client."""

    first_name: str | None = Field(None, min_length=1, max_length=255)
    last_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None)
    phone: str | None = Field(None, max_length=50)
    date_of_birth: date | None = Field(None)

    # NEW FIELDS - Add these:
    address: str | None = Field(None)
    medical_history: str | None = Field(None)
    emergency_contact_name: str | None = Field(None, max_length=255)
    emergency_contact_phone: str | None = Field(None, max_length=50)
    is_active: bool | None = Field(None)

    consent_status: bool | None = Field(None)
    notes: str | None = Field(None)
    tags: list[str] | None = Field(None)
```

#### 1.3 Add Computed Fields to `ClientResponse`

The frontend expects these computed fields:

```python
from pydantic import computed_field

class ClientResponse(ClientBase):
    """Schema for client API responses."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Computed fields (read-only)
    @computed_field  # type: ignore[misc]
    @property
    def full_name(self) -> str:
        """Full name of the client."""
        return f"{self.first_name} {self.last_name}"

    # These three fields should be populated by the API endpoint
    # (See Task 2 for implementation)
    next_appointment: datetime | None = Field(
        None, description="Next scheduled appointment after now"
    )
    last_appointment: datetime | None = Field(
        None, description="Most recent completed appointment"
    )
    appointment_count: int = Field(
        default=0, description="Total number of appointments"
    )

    model_config = ConfigDict(from_attributes=True)
```

---

### Task 2: Update API Endpoints

**File:** `/backend/src/pazpaz/api/clients.py`

#### 2.1 Update `create_client` Endpoint

The endpoint already handles all fields via `ClientCreate` schema, so once you update the schema, it will work automatically. Just verify:

```python
@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Client:
    # This already handles all fields from ClientCreate
    client = Client(
        workspace_id=workspace_id,
        first_name=client_data.first_name,
        last_name=client_data.last_name,
        email=client_data.email,
        phone=client_data.phone,
        date_of_birth=client_data.date_of_birth,
        # ADD THESE:
        address=client_data.address,
        medical_history=client_data.medical_history,
        emergency_contact_name=client_data.emergency_contact_name,
        emergency_contact_phone=client_data.emergency_contact_phone,
        is_active=client_data.is_active,
        # EXISTING:
        consent_status=client_data.consent_status,
        notes=client_data.notes,
        tags=client_data.tags,
    )
    # ... rest of the code
```

#### 2.2 Add Computed Fields Helper Function

Create a helper to efficiently compute appointment-related fields:

```python
from datetime import UTC, datetime
from sqlalchemy import func, select

async def enrich_client_response(
    db: AsyncSession,
    client: Client,
) -> ClientResponse:
    """
    Enrich client response with computed appointment fields.

    Efficiently fetches:
    - next_appointment: Next scheduled appointment after now
    - last_appointment: Most recent completed appointment
    - appointment_count: Total appointments for this client

    Uses 3 optimized queries with proper indexes.
    """
    from pazpaz.models.appointment import Appointment, AppointmentStatus

    # Query 1: Get next scheduled appointment
    next_apt_query = (
        select(Appointment.scheduled_start)
        .where(
            Appointment.workspace_id == client.workspace_id,
            Appointment.client_id == client.id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_start > datetime.now(UTC),
        )
        .order_by(Appointment.scheduled_start.asc())
        .limit(1)
    )
    next_result = await db.execute(next_apt_query)
    next_appointment = next_result.scalar_one_or_none()

    # Query 2: Get last completed appointment
    last_apt_query = (
        select(Appointment.scheduled_start)
        .where(
            Appointment.workspace_id == client.workspace_id,
            Appointment.client_id == client.id,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
        .order_by(Appointment.scheduled_start.desc())
        .limit(1)
    )
    last_result = await db.execute(last_apt_query)
    last_appointment = last_result.scalar_one_or_none()

    # Query 3: Get total appointment count
    count_query = select(func.count(Appointment.id)).where(
        Appointment.workspace_id == client.workspace_id,
        Appointment.client_id == client.id,
    )
    count_result = await db.execute(count_query)
    appointment_count = count_result.scalar_one()

    # Build response
    response = ClientResponse.model_validate(client)
    response.next_appointment = next_appointment
    response.last_appointment = last_appointment
    response.appointment_count = appointment_count

    return response
```

#### 2.3 Update `get_client` Endpoint

Use the helper to add computed fields:

```python
@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> ClientResponse:
    """Get a single client by ID with computed appointment fields."""
    client = await get_or_404(db, Client, client_id, workspace_id)

    # Enrich with computed fields
    return await enrich_client_response(db, client)
```

#### 2.4 Update `list_clients` Endpoint (Performance Consideration)

For list endpoints, adding 3 extra queries per client could be expensive. Two options:

**Option A: Make computed fields optional (recommended for list views)**
```python
@router.get("", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_appointments: bool = Query(
        False, description="Include appointment stats (slower)"
    ),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> ClientListResponse:
    # ... existing query code ...

    if include_appointments:
        # Enrich each client with appointment data
        items = [await enrich_client_response(db, client) for client in clients]
    else:
        # Just return basic client data (fast)
        items = [ClientResponse.model_validate(client) for client in clients]

    return ClientListResponse(items=items, total=total, ...)
```

**Option B: Use a single JOIN with aggregation (more complex but faster)**
```python
# Use LEFT JOIN with aggregation to get all computed fields in one query
query = (
    select(
        Client,
        func.min(
            case(
                (
                    and_(
                        Appointment.status == AppointmentStatus.SCHEDULED,
                        Appointment.scheduled_start > datetime.now(UTC),
                    ),
                    Appointment.scheduled_start,
                )
            )
        ).label("next_appointment"),
        func.max(
            case(
                (Appointment.status == AppointmentStatus.COMPLETED, Appointment.scheduled_start)
            )
        ).label("last_appointment"),
        func.count(Appointment.id).label("appointment_count"),
    )
    .outerjoin(Appointment, Client.id == Appointment.client_id)
    .where(Client.workspace_id == workspace_id)
    .group_by(Client.id)
    .order_by(Client.last_name, Client.first_name)
    .offset(offset)
    .limit(page_size)
)
```

**Recommendation:** Start with Option A (make it optional). If users always want the data, implement Option B for performance.

#### 2.5 Update `list_clients` to Filter Active Clients by Default

Add a query parameter to filter by `is_active`:

```python
@router.get("", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_inactive: bool = Query(
        False, description="Include archived/inactive clients"
    ),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> ClientListResponse:
    # Build base query
    base_query = select(Client).where(Client.workspace_id == workspace_id)

    # Filter active clients by default
    if not include_inactive:
        base_query = base_query.where(Client.is_active == True)

    # ... rest of query code
```

#### 2.6 Add Soft Delete Endpoint

Instead of hard deleting clients, mark them as inactive:

```python
@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> None:
    """
    Soft delete a client by marking as inactive.

    CHANGED: This now performs a soft delete (is_active = false)
    instead of hard delete to preserve audit trail and appointment history.
    """
    client = await get_or_404(db, Client, client_id, workspace_id)

    # Soft delete: mark as inactive
    client.is_active = False
    await db.commit()

    logger.info(
        "client_soft_deleted",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
    )
```

If you want to keep the hard delete option, add a new endpoint:

```python
@router.delete("/{client_id}/permanent", status_code=204)
async def permanently_delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> None:
    """
    PERMANENTLY delete a client and all associated data.

    WARNING: This cannot be undone. All appointments and sessions
    for this client will also be deleted due to CASCADE.
    """
    client = await get_or_404(db, Client, client_id, workspace_id)
    await db.delete(client)
    await db.commit()

    logger.warning(
        "client_permanently_deleted",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
    )
```

---

### Task 3: Run Database Migration

Before testing, apply the migration:

```bash
cd backend
uv run alembic upgrade head
```

Verify the migration:

```bash
uv run alembic current
# Should show: 83680210d7d2 (head)
```

Check the database schema:

```bash
uv run python -c "
from sqlalchemy import create_engine, inspect
from pazpaz.core.config import settings
engine = create_engine(settings.database_url.replace('+asyncpg', ''))
inspector = inspect(engine)
columns = inspector.get_columns('clients')
for col in columns:
    print(f'{col[\"name\"]}: {col[\"type\"]}')
"
```

Expected output should include:
- `address: TEXT`
- `medical_history: TEXT`
- `emergency_contact_name: VARCHAR`
- `emergency_contact_phone: VARCHAR`
- `is_active: BOOLEAN`

---

### Task 4: Update Tests

You'll need to update existing tests to account for the new fields:

#### 4.1 Update Test Fixtures

```python
# In tests/conftest.py or similar
@pytest.fixture
def client_create_data():
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "date_of_birth": "1980-01-01",
        # ADD THESE:
        "address": "123 Main St, City, Country",
        "medical_history": "No known allergies",
        "emergency_contact_name": "Jane Doe",
        "emergency_contact_phone": "+0987654321",
        "is_active": True,
        # EXISTING:
        "consent_status": True,
        "notes": "Test client",
        "tags": ["test"],
    }
```

#### 4.2 Test Computed Fields

```python
async def test_get_client_includes_appointment_stats(client, db_session):
    """Test that GET /clients/{id} includes appointment statistics."""
    from pazpaz.models.appointment import Appointment, AppointmentStatus
    from datetime import timedelta

    # Create test appointments
    past_apt = Appointment(
        workspace_id=client.workspace_id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC) - timedelta(days=7),
        scheduled_end=datetime.now(UTC) - timedelta(days=7, hours=-1),
        status=AppointmentStatus.COMPLETED,
        location_type="clinic",
    )
    future_apt = Appointment(
        workspace_id=client.workspace_id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=7),
        scheduled_end=datetime.now(UTC) + timedelta(days=7, hours=1),
        status=AppointmentStatus.SCHEDULED,
        location_type="clinic",
    )
    db_session.add_all([past_apt, future_apt])
    await db_session.commit()

    # Get client
    response = await client_api.get_client(client.id)

    assert response.appointment_count == 2
    assert response.last_appointment is not None
    assert response.next_appointment is not None
```

#### 4.3 Test Soft Delete

```python
async def test_delete_client_soft_deletes(client, db_session):
    """Test that DELETE /clients/{id} performs soft delete."""
    await client_api.delete_client(client.id)

    # Client still exists in database
    db_client = await db_session.get(Client, client.id)
    assert db_client is not None
    assert db_client.is_active == False

    # Client not returned in default list (active only)
    clients = await client_api.list_clients()
    assert client.id not in [c.id for c in clients.items]

    # Client returned when including inactive
    clients_with_inactive = await client_api.list_clients(include_inactive=True)
    assert client.id in [c.id for c in clients_with_inactive.items]
```

---

## Performance Considerations

### Indexes
The migration adds a partial index for active clients:
```sql
CREATE INDEX ix_clients_workspace_active
ON clients(workspace_id, is_active)
WHERE is_active = true;
```

This makes queries like `WHERE workspace_id = ? AND is_active = true` very fast (most common use case).

### Computed Fields
Each call to `enrich_client_response()` executes 3 additional queries:
- For `GET /clients/{id}`: Acceptable (3 queries total)
- For `GET /clients` with 50 clients: 150 extra queries (may be slow)

**Solution:** Use the `include_appointments` query parameter to make computed fields optional in list views.

---

## Security Notes (from database-architect)

### Encryption at Rest
The following fields contain PII/PHI and should be encrypted at rest in production:

- `address` (PII)
- `medical_history` (PHI - CRITICAL)
- `emergency_contact_name`, `emergency_contact_phone` (PII)

Current implementation stores these in plaintext. Coordinate with **security-auditor** to implement:
- Application-level encryption (recommended for PHI)
- Database-level transparent data encryption
- Key management via AWS KMS or HashiCorp Vault

### Audit Logging
All client modifications should be logged to the AuditEvent table (not yet implemented). Future task.

---

## Checklist

- [ ] Update `ClientBase` schema with 5 new fields
- [ ] Update `ClientUpdate` schema with 5 new fields
- [ ] Add computed fields to `ClientResponse`
- [ ] Create `enrich_client_response()` helper function
- [ ] Update `create_client()` endpoint to handle new fields
- [ ] Update `get_client()` to include computed fields
- [ ] Update `list_clients()` to filter active by default
- [ ] Add `include_appointments` query param to `list_clients()`
- [ ] Change `delete_client()` to soft delete
- [ ] Add `permanently_delete_client()` endpoint (optional)
- [ ] Run migration: `uv run alembic upgrade head`
- [ ] Update test fixtures with new fields
- [ ] Add tests for computed fields
- [ ] Add tests for soft delete behavior
- [ ] Verify API returns correct data to frontend

---

## Questions?

If you encounter issues or have questions:
1. Check `/backend/DATABASE_ARCHITECTURE_REVIEW.md` for detailed analysis
2. Review the migration file: `/backend/alembic/versions/83680210d7d2_add_client_healthcare_fields.py`
3. Review the updated model: `/backend/src/pazpaz/models/client.py`
4. Consult **backend-qa-specialist** for performance testing
5. Consult **security-auditor** for encryption implementation

---

**Next Step:** After completing these tasks, request **backend-qa-specialist** to review the implementation and validate performance targets are met.
