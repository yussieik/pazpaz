# API Error Responses

## Overview

All API endpoints in PazPaz return standardized error responses with consistent structure. This document describes the error response format, status codes, and examples.

## Standard Error Response Format

All error responses follow this structure:

```json
{
  "detail": "Error message or array of validation errors",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Fields**:
- `detail` (string | array): Error message or array of validation error objects
- `request_id` (string): UUID for log correlation and support

**Headers**:
- `X-Request-ID`: Same UUID as in response body

## HTTP Status Codes

### 4xx Client Errors

#### 400 Bad Request
**Meaning**: The request is malformed or contains invalid data

**Example**:
```json
{
  "detail": "Invalid date format. Expected ISO 8601 format (YYYY-MM-DD).",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

#### 401 Unauthorized
**Meaning**: Authentication is required or has failed

**Example**:
```json
{
  "detail": "Not authenticated. Please log in.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

#### 403 Forbidden
**Meaning**: Authenticated user lacks permission for the resource

**Example**:
```json
{
  "detail": "You do not have permission to access this workspace.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

#### 404 Not Found
**Meaning**: The requested resource does not exist

**Example**:
```json
{
  "detail": "Client not found",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

#### 409 Conflict
**Meaning**: The request conflicts with existing data (e.g., duplicate email)

**Example**:
```json
{
  "detail": "A conflict occurred. The requested operation violates data constraints.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Common Scenarios**:
- Creating client with duplicate email
- Creating appointment with time slot conflict
- Violating unique constraints

#### 422 Unprocessable Entity
**Meaning**: Request validation failed (Pydantic validation errors)

**Example**:
```json
{
  "detail": [
    {
      "loc": ["body", "last_name"],
      "msg": "field required",
      "type": "value_error.missing"
    },
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ],
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Validation Error Object**:
- `loc` (array): Location of the error (e.g., `["body", "field_name"]`)
- `msg` (string): Error message
- `type` (string): Error type (e.g., `value_error.missing`)
- `input` (any, optional): The invalid input value (omitted for PHI fields)

**PHI Field Sanitization**:
For PHI fields (subjective, objective, assessment, plan, etc.), validation errors are redacted:

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

#### 429 Too Many Requests
**Meaning**: Rate limit exceeded

**Example**:
```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Headers**:
- `Retry-After`: Seconds until rate limit resets
- `X-RateLimit-Limit`: Rate limit threshold
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when limit resets

### 5xx Server Errors

#### 500 Internal Server Error
**Meaning**: Unexpected server error occurred

**Example (Production)**:
```json
{
  "detail": "An unexpected error occurred. Please contact support with this request ID.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Example (Development)**:
```json
{
  "detail": "Internal server error",
  "error_type": "ValueError",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

**Note**: Stack traces are NEVER included in responses (logged server-side only)

#### 503 Service Unavailable
**Meaning**: Service is temporarily unavailable (e.g., database down)

**Example**:
```json
{
  "detail": "Database service temporarily unavailable. Please try again later.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

## Error Response Examples by Endpoint

### POST /api/v1/clients

#### Missing Required Field (422)
```json
{
  "detail": [
    {
      "loc": ["body", "last_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ],
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

#### Duplicate Email (409)
```json
{
  "detail": "A conflict occurred. The requested operation violates data constraints.",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

### GET /api/v1/clients/{client_id}

#### Client Not Found (404)
```json
{
  "detail": "Client not found",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

#### Invalid UUID Format (422)
```json
{
  "detail": [
    {
      "loc": ["path", "client_id"],
      "msg": "value is not a valid uuid",
      "type": "type_error.uuid"
    }
  ],
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

### POST /api/v1/sessions

#### PHI Validation Error (422)
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

#### Appointment Not Found (404)
```json
{
  "detail": "Appointment not found",
  "request_id": "123e4567-e89b-12d3-a561-426614174000"
}
```

## Frontend Error Handling

### Parsing Error Responses

```typescript
interface ErrorResponse {
  detail: string | ValidationError[];
  request_id: string;
}

interface ValidationError {
  loc: string[];
  msg: string;
  type: string;
  input?: any;
}

// Example: Handle API error
try {
  const response = await api.post('/clients', clientData);
} catch (error) {
  if (error.response) {
    const errorData: ErrorResponse = error.response.data;

    // Single error message
    if (typeof errorData.detail === 'string') {
      showErrorToast(errorData.detail);
    }

    // Validation errors
    else if (Array.isArray(errorData.detail)) {
      errorData.detail.forEach((err) => {
        const field = err.loc[err.loc.length - 1];
        showFieldError(field, err.msg);
      });
    }

    // Log request_id for support
    console.error('Request ID:', errorData.request_id);
  }
}
```

### Displaying Request IDs

When displaying error messages to users, include the request_id for support:

```typescript
function showErrorWithRequestId(errorResponse: ErrorResponse) {
  const message = typeof errorResponse.detail === 'string'
    ? errorResponse.detail
    : 'Validation failed. Please check your input.';

  // Display error with request ID
  toast.error(
    `${message}\n\nRequest ID: ${errorResponse.request_id}`,
    { duration: 8000 }
  );
}
```

### Handling Rate Limits

```typescript
try {
  const response = await api.post('/clients', clientData);
} catch (error) {
  if (error.response?.status === 429) {
    const retryAfter = error.response.headers['retry-after'];
    showErrorToast(
      `Rate limit exceeded. Please try again in ${retryAfter} seconds.`
    );
  }
}
```

## Testing Error Responses

### Example Test: Validation Error

```python
@pytest.mark.asyncio
async def test_create_client_missing_required_field(
    client: AsyncClient,
    authenticated_headers_ws1: dict[str, str],
):
    """Test validation error for missing required field."""
    response = await client.post(
        "/api/v1/clients",
        json={"first_name": "John"},  # Missing last_name
        headers=authenticated_headers_ws1,
    )

    assert response.status_code == 422
    data = response.json()

    # Check response format
    assert "detail" in data
    assert "request_id" in data
    assert "X-Request-ID" in response.headers

    # Check validation error details
    errors = data["detail"]
    assert isinstance(errors, list)
    assert any(err["loc"][-1] == "last_name" for err in errors)
```

### Example Test: Not Found Error

```python
@pytest.mark.asyncio
async def test_get_nonexistent_client(
    client: AsyncClient,
    authenticated_headers_ws1: dict[str, str],
):
    """Test 404 error for non-existent client."""
    client_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/clients/{client_id}",
        headers=authenticated_headers_ws1,
    )

    assert response.status_code == 404
    data = response.json()

    assert "detail" in data
    assert "request_id" in data
    assert "not found" in data["detail"].lower()
```

## Security Considerations

### What is NOT Included in Error Responses

For security and HIPAA compliance, error responses **NEVER** include:

- Stack traces or exception details
- Internal file paths or line numbers
- Database query strings or schema details
- Database constraint names
- PHI field values (redacted in validation errors)
- Connection strings or credentials
- Internal implementation details

### Request IDs for Support

The `request_id` in error responses serves two purposes:

1. **User Support**: Users can provide request_id when contacting support
2. **Audit Trail**: Links error response to server logs for investigation

**Server logs include full details** (stack traces, error types, etc.) that are hidden from clients.

## Related Documentation

- [Backend Error Handling](/docs/backend/ERROR_HANDLING.md) - Exception handler implementation
- [Security Overview](/docs/security/OVERVIEW.md) - Security practices
- [API Design Patterns](/docs/backend/api/PATTERNS.md) - General API patterns

## OpenAPI Specification

Error responses are documented in the OpenAPI specification:

```yaml
components:
  schemas:
    ErrorResponse:
      type: object
      properties:
        detail:
          oneOf:
            - type: string
            - type: array
              items:
                $ref: '#/components/schemas/ValidationError'
        request_id:
          type: string
          format: uuid
      required:
        - detail
        - request_id

    ValidationError:
      type: object
      properties:
        loc:
          type: array
          items:
            type: string
        msg:
          type: string
        type:
          type: string
        input:
          type: object
          nullable: true
```

All endpoints should document their error responses:

```yaml
/api/v1/clients:
  post:
    responses:
      '201':
        description: Client created successfully
      '422':
        description: Validation error
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
      '409':
        description: Conflict (duplicate email)
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
```
