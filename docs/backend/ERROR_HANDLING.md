# Backend Error Handling

## Overview

PazPaz implements centralized exception handling to prevent information disclosure and ensure HIPAA compliance. All error responses are sanitized to remove sensitive information (PHI, stack traces, internal implementation details) before being sent to clients.

## Exception Handlers

### 1. Generic Exception Handler

**Handler**: `@app.exception_handler(Exception)`
**Status Code**: 500 Internal Server Error
**Purpose**: Catch all unhandled exceptions

**Security Measures**:
- Logs full error with stack trace server-side (for debugging)
- Returns sanitized error to client (no stack trace, no internal details)
- Includes `request_id` for log correlation
- Development mode: Includes `error_type` for debugging
- Production mode: Generic message only

**Example Response (Production)**:
```json
{
  "detail": "An unexpected error occurred. Please contact support with this request ID.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Example Response (Development)**:
```json
{
  "detail": "Internal server error",
  "error_type": "ValueError",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

### 2. Database Integrity Error Handler

**Handler**: `@app.exception_handler(IntegrityError)`
**Status Code**: 409 Conflict
**Purpose**: Handle database integrity violations (unique constraints, foreign keys)

**Security Measures**:
- Does NOT expose database constraint names or internal schema
- Logs full error server-side with constraint details
- Returns generic conflict message to client

**Example Response**:
```json
{
  "detail": "A conflict occurred. The requested operation violates data constraints.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Example Scenario**:
- User tries to create a client with duplicate email
- Database raises `IntegrityError` with constraint `clients_email_key`
- Client receives generic conflict message (constraint name hidden)
- Server logs include full constraint details for debugging

### 3. Database Error Handler

**Handler**: `@app.exception_handler(DBAPIError)`
**Status Code**: 503 Service Unavailable
**Purpose**: Handle database connection/query errors

**Security Measures**:
- Does NOT expose database connection strings or query details
- Logs full error server-side for debugging
- Returns generic service unavailable message

**Example Response**:
```json
{
  "detail": "Database service temporarily unavailable. Please try again later.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Example Scenarios**:
- Database connection timeout
- Query execution failure
- Database server unavailable

### 4. Validation Error Handler (PHI Sanitization)

**Handler**: `@app.exception_handler(RequestValidationError)`
**Status Code**: 422 Unprocessable Entity
**Purpose**: Handle Pydantic request validation errors with PHI protection

**Security Measures**:
- Redacts input values for PHI fields (subjective, objective, assessment, plan, etc.)
- Removes `input` field from error details for PHI fields
- Logs sanitized errors (never logs PHI values)
- Non-PHI fields show full validation details

**PHI Fields (Automatically Redacted)**:
- `subjective`, `objective`, `assessment`, `plan`
- `medical_history`, `notes`, `treatment_notes`
- `first_name`, `last_name`, `email`, `phone`
- `address`, `date_of_birth`, `ssn`, `insurance_id`

**Example Response (PHI Field)**:
```json
{
  "detail": [
    {
      "loc": ["body", "subjective"],
      "msg": "Invalid value (details redacted for PHI protection)",
      "type": "value_error"
    }
  ],
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Example Response (Non-PHI Field)**:
```json
{
  "detail": [
    {
      "loc": ["body", "last_name"],
      "msg": "field required",
      "type": "value_error.missing",
      "input": null
    }
  ],
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

## Request ID Propagation

Every error response includes a unique `request_id` for traceability:

**Response Body**:
```json
{
  "detail": "Error message",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Response Header**:
```
X-Request-ID: 123e4567-e89b-12d3-a561-426614174000
```

**Server Logs**:
```json
{
  "event": "unhandled_exception",
  "request_id": "123e4567-e89b-12d3-a561-426614174000",
  "error": "Division by zero",
  "error_type": "ZeroDivisionError",
  "path": "/api/v1/clients",
  "method": "POST",
  "exc_info": "Traceback (most recent call last)..."
}
```

## Development vs Production Behavior

### Development Mode
**Conditions**: `DEBUG=True` AND `ENVIRONMENT=local`

**Error Responses Include**:
- Generic error message
- `error_type` (e.g., `ValueError`, `KeyError`)
- `request_id`

**What's NOT Included**:
- Stack traces (even in dev)
- Internal file paths
- Database query details

### Production Mode
**Conditions**: `DEBUG=False` OR `ENVIRONMENT=production|staging`

**Error Responses Include**:
- Generic error message only
- `request_id`

**What's NOT Included**:
- `error_type`
- Stack traces
- Internal implementation details
- Database schema information
- PHI field values

## How to Add Custom Exception Handlers

### 1. Define the Exception Handler

Add the handler in `/backend/src/pazpaz/main.py` after the existing handlers:

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from your_module import YourCustomError

@app.exception_handler(YourCustomError)
async def custom_error_handler(request: Request, exc: YourCustomError):
    """Handle custom errors with sanitized response."""
    logger = get_logger(__name__)

    # Get request_id from request state
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    # Log full error server-side
    logger.error(
        "custom_error",
        request_id=request_id,
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )

    # Return sanitized error to client
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Your custom error message (sanitized)",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )
```

### 2. Register in Startup Logs

Update the startup log in `lifespan()` function:

```python
logger.info(
    "exception_handlers_registered",
    handlers=[
        "Exception (generic)",
        "IntegrityError (database)",
        "DBAPIError (database)",
        "RequestValidationError (validation)",
        "YourCustomError (custom)",  # Add this
    ],
)
```

### 3. Add Tests

Create tests in `/backend/tests/security/test_exception_handlers.py`:

```python
@pytest.mark.asyncio
async def test_custom_error_handler(
    client: AsyncClient,
    authenticated_headers_ws1: dict[str, str],
):
    """Test custom error handler returns sanitized response."""
    # Trigger the custom error
    response = await client.post(
        "/api/v1/endpoint-that-raises-custom-error",
        headers=authenticated_headers_ws1,
    )

    # Verify sanitized response
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "request_id" in data
    assert "X-Request-ID" in response.headers
```

## Testing Exception Handlers

### Run All Exception Handler Tests

```bash
# Run all exception handler tests
uv run pytest tests/security/test_exception_handlers.py -v

# Run specific test class
uv run pytest tests/security/test_exception_handlers.py::TestGenericExceptionHandler -v

# Run with logs
uv run pytest tests/security/test_exception_handlers.py -v -s
```

### Test Coverage

The test suite includes:
- ✅ Generic exception returns 500
- ✅ Request ID included in response and headers
- ✅ No stack traces in production mode
- ✅ Error type included in development mode
- ✅ Database integrity errors return 409
- ✅ Database constraint names not leaked
- ✅ Database connection errors return 503
- ✅ PHI field values redacted from validation errors
- ✅ Request ID propagated in all errors
- ✅ Non-PHI fields show full validation details
- ✅ Full errors logged server-side

## Security Considerations

### What is Logged Server-Side

**Server logs include** (for debugging):
- Full error messages
- Stack traces (`exc_info=True`)
- Error types
- Request paths and methods
- Request IDs

**Server logs NEVER include**:
- PHI field values (redacted before logging)
- Passwords or secrets
- Session tokens or JWTs

### What is Sent to Client

**Client responses include**:
- Generic error messages
- Request IDs (for support)
- Error types (development only)

**Client responses NEVER include**:
- Stack traces
- Internal file paths
- Database schema details
- Constraint names
- PHI field values
- Connection strings
- Internal implementation details

## HIPAA Compliance

The centralized exception handling ensures HIPAA compliance:

**§164.312(a)(1) - Access Control**:
- Error messages don't leak PHI to unauthorized users
- Request IDs enable audit trail correlation

**§164.312(b) - Audit Controls**:
- All errors logged with request_id for audit trail
- Full error details available for incident investigation

**§164.312(e)(1) - Transmission Security**:
- Error responses sanitized before transmission
- No PHI leaked over the network in error messages

## Troubleshooting

### Error Response Missing Request ID

**Problem**: Error response doesn't include `request_id`

**Solution**: Ensure `RequestLoggingMiddleware` is registered and sets `request.state.request_id`. Check middleware order in `main.py`.

### PHI Values Appearing in Error Responses

**Problem**: Validation errors leak PHI field values

**Solution**: Add the field name to the `PHI_FIELDS` set in `main.py`:

```python
PHI_FIELDS = {
    "subjective",
    "objective",
    # ... existing fields
    "your_new_phi_field",  # Add this
}
```

### Production Mode Still Showing Error Types

**Problem**: Production responses include `error_type`

**Solution**: Verify environment configuration:
```bash
# Check environment variables
echo $DEBUG  # Should be "false" or unset
echo $ENVIRONMENT  # Should be "production" or "staging"
```

### Database Constraint Names Appearing in Responses

**Problem**: IntegrityError responses leak constraint names

**Solution**: This should not happen with the centralized handler. If it does:
1. Check that `IntegrityError` handler is registered
2. Verify no endpoint is catching `IntegrityError` and returning it directly
3. Check `app.exception_handler(IntegrityError)` is defined before endpoint registration

## Related Documentation

- [API Error Responses](/docs/backend/api/ERROR_RESPONSES.md) - Standardized error response format
- [Security Overview](/docs/security/OVERVIEW.md) - General security practices
- [Logging](/docs/backend/LOGGING.md) - Structured logging patterns
- [Testing](/docs/testing/backend/README.md) - Backend testing guide

## References

- FastAPI Exception Handlers: https://fastapi.tiangolo.com/tutorial/handling-errors/
- HIPAA §164.312 - Technical Safeguards
- OWASP Error Handling Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html
