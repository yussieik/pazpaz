# Rate Limiting Implementation

**Last Updated**: 2025-01-13

## Overview

PazPaz implements rate limiting using a Redis-based sliding window algorithm to prevent abuse and ensure fair resource usage. This document covers the rate limiting patterns used across the API.

## Table of Contents

- [Overview](#overview)
- [Current Rate Limits](#current-rate-limits)
- [Sliding Window Algorithm](#sliding-window-algorithm)
- [Implementation Details](#implementation-details)
- [Benefits](#benefits)
- [Magic Link Refactoring](#magic-link-refactoring)
- [Testing](#testing)
- [See Also](#see-also)

## Current Rate Limits

### Authentication
- **Magic Link Requests**: 3 per hour per IP address
- **JWT Verification**: No limit (tokens expire after 30 days)

### Session Management
- **Draft Autosave**: 1 request per 5 seconds per session
- **Session Updates**: Standard API rate limits apply

### General API
- **Default**: 1000 requests per minute per authenticated user
- **Burst**: Allow short bursts up to 100 requests in 10 seconds

## Sliding Window Algorithm

The sliding window algorithm provides more accurate rate limiting compared to fixed window approaches:

### How It Works
1. Each request is stored with a timestamp in a Redis sorted set
2. Old requests outside the window are automatically removed
3. The count of requests in the current window determines if limit is exceeded
4. Provides smooth rate limiting without boundary issues

### Redis Data Structure
```
rate_limit_key = {
    "request_uuid_1": timestamp_1,
    "request_uuid_2": timestamp_2,
    "request_uuid_3": timestamp_3
}  # Stored as Redis sorted set (zset)
```

## Magic Link Refactoring

### File: `/backend/src/pazpaz/services/auth_service.py`

#### 1. Added Import (Line 15)

```python
from pazpaz.core.rate_limiting import check_rate_limit_redis
```

#### 2. Replaced Rate Limiting Logic (Lines 54-71)

**BEFORE (Fixed Window Implementation):**
```python
# Check rate limit by IP
rate_limit_key = f"magic_link_rate_limit:{request_ip}"
current_count = await redis_client.get(rate_limit_key)

if current_count and int(current_count) >= RATE_LIMIT_MAX_REQUESTS:
    logger.warning(
        "magic_link_rate_limit_exceeded",
        ip=request_ip,
        email=email,
    )
    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded. Please try again in an hour.",
    )

# ... later in code (lines 108-111)...
# Increment rate limit counter
if not current_count:
    await redis_client.setex(rate_limit_key, RATE_LIMIT_WINDOW_SECONDS, 1)
else:
    await redis_client.incr(rate_limit_key)
```

**AFTER (Sliding Window Implementation):**
```python
# Check rate limit by IP (3 requests per hour using sliding window)
rate_limit_key = f"magic_link_rate_limit:{request_ip}"

if not await check_rate_limit_redis(
    redis_client=redis_client,
    key=rate_limit_key,
    max_requests=RATE_LIMIT_MAX_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
):
    logger.warning(
        "magic_link_rate_limit_exceeded",
        ip=request_ip,
        email=email,
    )
    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded. Please try again in an hour.",
    )
```

#### 3. Removed Unused Code

Removed the old rate limit increment code (previously at lines 108-111):
- No longer needed `current_count` variable
- No longer need manual `setex` and `incr` operations
- Rate limiting now handled atomically by the utility function

## Benefits

### 1. More Accurate Rate Limiting
- **Before:** Fixed window algorithm (vulnerable to burst attacks at window boundaries)
- **After:** Sliding window algorithm (accurate rate limiting across any time window)

### 2. Consistent Implementation
- Same rate limiting approach used across the entire codebase
- Both magic link auth and draft autosave now use identical rate limiting logic

### 3. Better Data Structure
- **Before:** Simple Redis key-value with counter
- **After:** Redis sorted set (zset) with timestamps for precise sliding window

### 4. Improved Security
- Prevents burst attacks at window boundaries
- More accurate request counting across distributed instances

### 5. Code Reuse
- Single rate limiting implementation in `/backend/src/pazpaz/core/rate_limiting.py`
- Changes to rate limiting logic only need to be made in one place
- Easier to maintain and test

## Implementation Details

### Rate Limiting Configuration (Unchanged)

```python
# Magic link rate limit per email (3 per hour)
RATE_LIMIT_MAX_REQUESTS = 3
RATE_LIMIT_WINDOW_SECONDS = 60 * 60
```

### Redis Data Structure

**Before:** Simple counter
```
magic_link_rate_limit:192.168.1.1 = "2"  (string)
```

**After:** Sorted set with timestamps
```
magic_link_rate_limit:192.168.1.1 = {
    "uuid1": 1760021601.32,
    "uuid2": 1760021602.45,
    "uuid3": 1760021603.78
}  (zset)
```

### Error Handling

The rate limiter has "fail-open" behavior:
- If Redis is unavailable, requests are allowed (prevents Redis outages from blocking all authentication)
- Errors are logged for monitoring
- Trade-off: Temporary rate limit bypass vs. service availability

## Testing

### Existing Tests
All existing auth endpoint tests still pass (SMTP service dependency is a separate issue):
- ✓ `test_request_magic_link_nonexistent_user` - PASSED
- ✓ `test_request_magic_link_inactive_user` - PASSED
- ✓ `test_request_magic_link_invalid_email` - PASSED

### Rate Limit Test
The `test_request_magic_link_rate_limit` test validates:
1. First 3 requests succeed (200 status)
2. 4th request fails with 429 (Rate Limited)

## Code Quality

- ✓ No linting errors (`ruff check --fix`)
- ✓ No formatting issues (`ruff format`)
- ✓ No type errors or diagnostics
- ✓ Follows Python 3.13 best practices

## Migration Path

No database migration required. The change is transparent to existing functionality:
- Same rate limits (3 per hour per IP)
- Same error messages
- Same HTTP status codes
- More accurate enforcement

## Related Files

- `/backend/src/pazpaz/core/rate_limiting.py` - Rate limiting utility (already exists)
- `/backend/src/pazpaz/services/auth_service.py` - Refactored (THIS CHANGE)
- `/backend/tests/test_auth_endpoints.py` - Tests (no changes needed)

## Verification Checklist

- [x] Import added for `check_rate_limit_redis`
- [x] Old fixed-window logic removed
- [x] New sliding-window logic implemented
- [x] Unused `current_count` variable removed
- [x] Rate limit parameters preserved (3 per hour)
- [x] Error messages unchanged
- [x] Code passes linting and formatting
- [x] No diagnostics errors
- [x] Existing tests still valid

## Implementation Details

The core rate limiting utility is implemented in:
- `/backend/src/pazpaz/core/rate_limiting.py` - Redis sliding window implementation

Rate limiting is applied in:
- `/backend/src/pazpaz/services/auth_service.py` - Magic link rate limiting
- `/backend/src/pazpaz/api/sessions.py` - Draft autosave rate limiting
- `/backend/src/pazpaz/middleware/rate_limit.py` - General API rate limiting

## See Also

- [API Endpoint Reference](./API.md) - Complete API documentation
- [Flexible Record Management](./FLEXIBLE_RECORD_MANAGEMENT.md) - Medical record patterns
- [Redis Configuration](/docs/security/REDIS_CONFIGURATION.md) - Redis setup
- [Security Patterns](/docs/security/) - Security implementation

## Conclusion

PazPaz uses a centralized Redis sliding window rate limiter for consistent rate limiting across all endpoints. This approach provides accurate rate limiting, prevents burst attacks, and maintains high performance while protecting the system from abuse.
