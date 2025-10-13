# API Documentation

FastAPI endpoint implementation guides and patterns for the PazPaz backend API.

**Last Updated**: 2025-01-13

## 📚 Documentation Structure

This directory contains comprehensive documentation for PazPaz's RESTful API:

### Core Documentation

- **[API.md](./API.md)** - Complete endpoint reference with request/response examples
  - Health check endpoints
  - Clients CRUD operations
  - Appointments with conflict detection
  - Services and Locations management
  - Sessions (SOAP notes) with versioning
  - Session attachments (file uploads)
  - Audit log viewer

### Implementation Guides

- **[FLEXIBLE_RECORD_MANAGEMENT.md](./FLEXIBLE_RECORD_MANAGEMENT.md)** - Medical record management patterns
  - Appointment deletion with audit trails
  - Session note amendments and version history
  - Field-level change tracking
  - Soft-delete strategies

- **[RATE_LIMITING_IMPLEMENTATION.md](./RATE_LIMITING_IMPLEMENTATION.md)** - Rate limiting refactoring
  - Magic link authentication rate limiting
  - Sliding window algorithm implementation
  - Redis-based rate limiter utility

## 🎯 API Design Principles

### Performance Targets
- **p95 < 150ms** for schedule endpoints
- Optimized database queries with proper indexing
- Efficient pagination for large datasets
- Redis caching for frequently accessed data

### Security First
- **JWT authentication** with workspace scoping
- **CSRF protection** on state-changing operations
- **Rate limiting** to prevent abuse
- **Audit logging** for all data modifications
- **PHI encryption** at rest (AES-256-GCM)

### Developer Experience
- **OpenAPI 3.0** documentation (auto-generated)
- **TypeScript client** generation from OpenAPI spec
- **Consistent error responses** (RFC 7807 format)
- **Comprehensive examples** in documentation

## 🔗 Quick Links

### API Implementation Files
- `/backend/src/pazpaz/api/` - All endpoint implementations
  - `clients.py` - Client management endpoints
  - `appointments.py` - Appointment scheduling with conflicts
  - `sessions.py` - SOAP notes and versioning
  - `session_attachments.py` - File upload/download
  - `services.py` - Service definitions
  - `locations.py` - Location management
  - `auth.py` - Authentication (magic link)
  - `audit.py` - Audit log viewer

### Related Documentation
- [Backend Architecture](/backend/docs/README.md) - Overall backend structure
- [Database Schema](/backend/docs/database/) - Database design and migrations
- [Security Patterns](/docs/security/) - HIPAA compliance and security
- [Testing Strategy](/backend/docs/testing/) - API testing patterns
- [Performance Benchmarks](/backend/docs/performance/) - Performance testing results

## 🚀 Getting Started

### Running the API Server
```bash
cd backend
uv run uvicorn pazpaz.main:app --reload --host 0.0.0.0 --port 8000
```

### Accessing API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

### Running API Tests
```bash
cd backend
export PYTHONPATH=src
uv run pytest tests/test_*_endpoints.py -v
```

## 📝 Common Patterns

### Workspace Scoping
All endpoints automatically scope data to the authenticated user's workspace:
```python
# Automatically injected via dependency
workspace_id = Depends(get_current_workspace_id)

# All queries filtered by workspace
query = select(Client).where(Client.workspace_id == workspace_id)
```

### Pagination
Standard pagination pattern for list endpoints:
```python
# Request: GET /api/v1/clients?page=2&page_size=50
# Response includes total count
{
  "items": [...],
  "total": 234,
  "page": 2,
  "page_size": 50
}
```

### Error Handling
Consistent error format across all endpoints:
```json
{
  "detail": "Client not found"
}
```

### Audit Logging
Automatic audit logging for all modifications:
```python
# Automatically logged to AuditEvent table
await log_audit_event(
    db=db,
    workspace_id=workspace_id,
    event_type="client.created",
    resource_type="Client",
    resource_id=client.id,
    action="CREATE",
    metadata={"tags": client.tags}
)
```

## 🔒 Authentication Flow

1. **Request Magic Link**: `POST /api/v1/auth/request-magic-link`
2. **Verify Token**: `GET /api/v1/auth/verify-magic-link?token=...`
3. **Use JWT**: Include in Authorization header for subsequent requests
4. **Logout**: `POST /api/v1/auth/logout` (blacklists JWT)

## 📊 Performance Monitoring

### Key Metrics
- Request latency (p50, p95, p99)
- Database query time
- Redis cache hit rate
- Concurrent request handling

### Monitoring Endpoints
- `/metrics` - Prometheus metrics
- `/health` - Basic health check
- `/api/v1/health` - API version health

## 🎓 See Also

- [Security First Implementation Plan](/docs/SECURITY_FIRST_IMPLEMENTATION_PLAN.md)
- [Project Overview](/docs/PROJECT_OVERVIEW.md)
- [Encryption Usage Guide](/backend/docs/encryption/ENCRYPTION_USAGE_GUIDE.md)
