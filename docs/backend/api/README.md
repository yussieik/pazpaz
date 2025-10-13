# API Documentation

FastAPI endpoint implementation guides and patterns.

## 📋 Contents

This directory will contain:

- **Endpoint Patterns** - Common CRUD patterns, pagination, filtering
- **Request/Response Schemas** - Pydantic schema design patterns
- **Authentication Guards** - JWT dependencies, workspace scoping
- **Error Handling** - Custom exceptions, error response formats
- **Validation Patterns** - Input validation, sanitization
- **OpenAPI Configuration** - Swagger documentation best practices

## 🚀 Coming in Week 2+

API documentation will be added as we implement:
- SOAP Notes API (Week 2 Day 7)
- Plan of Care API (Week 3 Day 13)
- File Upload API (Week 3 Day 12)
- Email Reminder API (Week 4 Day 17-18)

## 📝 Current Patterns

See existing API implementations:
- `/backend/src/pazpaz/api/clients.py` - Client CRUD (workspace scoping pattern)
- `/backend/src/pazpaz/api/appointments.py` - Appointment CRUD (conflict detection)
- `/backend/src/pazpaz/api/auth.py` - Authentication endpoints
- `/backend/src/pazpaz/api/audit.py` - Audit log viewer
