# Email Blacklist Enforcement

**Status**: ✅ Implemented
**Last Updated**: 2025-10-22
**Author**: Backend Security Team

## Overview

The email blacklist system prevents specific email addresses from accessing the PazPaz platform. This document describes how blacklist enforcement works across all entry points and provides guidelines for platform administrators.

## Purpose

The email blacklist serves multiple security and operational purposes:

1. **Abuse Prevention**: Block users who violate terms of service
2. **Spam Prevention**: Stop spam signups and bot accounts
3. **Fraud Prevention**: Block known fraudulent email addresses
4. **Policy Enforcement**: Enforce platform access policies

## How It Works

### Data Model

The `EmailBlacklist` table stores blacklisted email addresses:

```sql
CREATE TABLE email_blacklist (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,  -- Normalized to lowercase
    reason TEXT NOT NULL,                 -- Required for audit trail
    added_at TIMESTAMP WITH TIME ZONE NOT NULL,
    added_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_email_blacklist_email ON email_blacklist(email);
CREATE INDEX idx_email_blacklist_added_at ON email_blacklist(added_at);
```

### Key Features

- **Case-Insensitive**: All email comparisons are case-insensitive (normalized to lowercase)
- **Indexed Lookups**: Fast O(1) lookups using database index
- **Audit Trail**: Every blacklist entry requires a reason and tracks who added it
- **Immediate Effect**: Blacklist changes take effect immediately (no caching)

## Enforcement Points

The blacklist is enforced at **three critical entry points**:

### 1. Invitation Creation

**Location**: `backend/src/pazpaz/services/platform_onboarding_service.py::create_workspace_and_invite_therapist()`

**Behavior**:
- Checks if email is blacklisted BEFORE creating workspace or user
- Raises `EmailBlacklistedError` if blacklisted
- Returns HTTP 403 with clear error message

**Example**:
```python
# Platform admin tries to invite blacklisted email
POST /api/v1/platform-admin/invite-therapist
{
  "workspace_name": "Test Clinic",
  "therapist_email": "blocked@example.com",
  "therapist_full_name": "Blocked User"
}

# Response: HTTP 403 Forbidden
{
  "detail": "This email address is blacklisted and cannot receive invitations"
}
```

**Audit Logging**:
```python
logger.warning(
    "invitation_blocked_blacklisted_email",
    email=therapist_email,
)
```

### 2. Magic Link Request

**Location**: `backend/src/pazpaz/services/auth_service.py::request_magic_link()`

**Behavior**:
- Checks if email is blacklisted BEFORE looking up user
- Returns success (HTTP 200) but does NOT send magic link email
- Creates audit log for security monitoring

**Why Silent Success?**
To prevent email enumeration attacks. If we returned an error, attackers could discover which emails exist in the system.

**Example**:
```python
# User requests magic link for blacklisted email
POST /api/v1/auth/request-magic-link
{
  "email": "blocked@example.com"
}

# Response: HTTP 200 OK (appears successful)
# But NO email is sent, and audit log is created
```

**Audit Logging**:
```python
await create_audit_event(
    db=db,
    user_id=None,
    workspace_id=None,
    action=AuditAction.READ,
    resource_type=ResourceType.USER,
    resource_id=None,
    ip_address=request_ip,
    metadata={
        "action": "magic_link_request_blacklisted_email",
        "result": "email_blacklisted",
    },
)
```

### 3. Invitation Acceptance

**Location**: `backend/src/pazpaz/services/platform_onboarding_service.py::accept_invitation()`

**Behavior**:
- Checks if email is blacklisted AFTER token verification
- Raises `InvalidInvitationTokenError` if blacklisted
- Prevents activation even if invitation was sent before blacklisting

**Example**:
```python
# User tries to accept invitation after being blacklisted
GET /api/v1/auth/accept-invitation?token=abc123...

# Response: HTTP 400 Bad Request
{
  "detail": "This email address is not eligible to accept invitations"
}
```

**Audit Logging**:
```python
logger.warning(
    "invitation_acceptance_blocked_blacklisted_email",
    user_id=str(user.id),
    email=user.email,
)
```

## Implementation Details

### Core Utility Function

The shared utility function provides consistent blacklist checking:

**File**: `backend/src/pazpaz/core/blacklist.py`

```python
async def is_email_blacklisted(db: AsyncSession, email: str) -> bool:
    """
    Check if an email address is blacklisted (case-insensitive).

    Args:
        db: Database session (async)
        email: Email address to check

    Returns:
        True if email is blacklisted, False otherwise
    """
    normalized_email = email.lower()

    result = await db.scalar(
        select(EmailBlacklist.id)
        .where(EmailBlacklist.email == normalized_email)
        .limit(1)
    )

    return result is not None
```

### Performance Characteristics

- **Query Time**: O(1) - indexed lookup on `email` column
- **Case Sensitivity**: Normalized to lowercase before comparison
- **Caching**: None (intentionally - blacklist changes take effect immediately)
- **Database Load**: Minimal - single indexed query per check

## Platform Admin Operations

### Adding Email to Blacklist

```http
POST /api/v1/platform-admin/blacklist
{
  "email": "spam@example.com",
  "reason": "Repeated spam signups"
}
```

**Effects**:
1. Email is added to `email_blacklist` table
2. Any pending invitations for this email are revoked
3. Audit event is created
4. User cannot request magic links immediately
5. User cannot accept pending invitations

### Removing Email from Blacklist

```http
DELETE /api/v1/platform-admin/blacklist/spam@example.com
```

**Effects**:
1. Email is removed from blacklist
2. User can now request magic links
3. User can now accept invitations
4. Audit event is created

### Viewing Blacklist

```http
GET /api/v1/platform-admin/blacklist
```

**Response**:
```json
{
  "blacklist": [
    {
      "email": "spam@example.com",
      "reason": "Repeated spam signups",
      "added_at": "2025-10-22T10:30:00Z",
      "added_by": "admin@pazpaz.com"
    }
  ]
}
```

## Security Considerations

### Email Enumeration Prevention

**Problem**: If blacklist checks returned different errors than non-existent users, attackers could enumerate valid emails.

**Solution**: Magic link requests return success (HTTP 200) for blacklisted emails, but don't send emails. This matches the behavior for non-existent users.

### Timing Attacks

**Risk**: Blacklist checks could reveal information through timing differences.

**Mitigation**:
- Database query is indexed (consistent O(1) performance)
- No conditional logic that varies execution time significantly
- Returns immediately after check (no additional processing)

### Race Conditions

**Scenario**: User added to blacklist while magic link is being sent.

**Handling**:
- Blacklist check happens BEFORE user lookup and token generation
- No caching of blacklist status
- Database transaction ensures consistency

### Case Sensitivity

**Handling**:
- All emails normalized to lowercase before comparison
- Works for `user@EXAMPLE.COM`, `User@Example.Com`, etc.
- Consistent with email address standards (case-insensitive local part)

## Testing

Comprehensive test coverage is provided in:

**File**: `backend/tests/security/authentication/test_email_blacklist_enforcement.py`

### Test Categories

1. **Unit Tests**: `is_email_blacklisted()` function
   - Blacklisted email detection
   - Non-blacklisted email handling
   - Case-insensitive comparison
   - Empty/invalid email handling

2. **Service Layer Tests**: Platform onboarding and auth services
   - Invitation creation blocking
   - Magic link request blocking
   - Invitation acceptance blocking
   - Case-insensitive enforcement

3. **API Integration Tests**: Full request/response cycle
   - HTTP 403 for blocked invitations
   - HTTP 200 (silent) for blocked magic links
   - Proper error messages
   - Case-insensitive API behavior

4. **Edge Cases**:
   - Blacklist added after invitation sent
   - Special characters in emails
   - Multiple rapid checks (performance)
   - Removing from blacklist re-enables access

5. **Audit Logging Tests**:
   - Blocked attempts create audit events
   - Audit events contain proper metadata
   - IP addresses are logged

### Running Tests

```bash
# Run all blacklist enforcement tests
pytest backend/tests/security/authentication/test_email_blacklist_enforcement.py -v

# Run specific test class
pytest backend/tests/security/authentication/test_email_blacklist_enforcement.py::TestBlacklistAPIEnforcement -v

# Run with coverage
pytest backend/tests/security/authentication/test_email_blacklist_enforcement.py --cov=pazpaz.core.blacklist --cov-report=html
```

## Monitoring and Alerts

### Key Metrics to Monitor

1. **Blacklist Hit Rate**: How often blacklisted emails attempt access
   - Log key: `invitation_blocked_blacklisted_email`
   - Log key: `magic_link_request_blocked_blacklisted_email`
   - Log key: `invitation_acceptance_blocked_blacklisted_email`

2. **Blacklist Size**: Number of entries in blacklist table
   - Query: `SELECT COUNT(*) FROM email_blacklist`

3. **Recent Additions**: Newly blacklisted emails
   - Query: `SELECT * FROM email_blacklist WHERE added_at > NOW() - INTERVAL '24 hours'`

### Log Queries

**Find blocked invitation attempts**:
```sql
SELECT * FROM audit_events
WHERE event_metadata->>'action' = 'magic_link_request_blacklisted_email'
ORDER BY created_at DESC
LIMIT 100;
```

**Find blacklist activity**:
```sql
SELECT * FROM audit_events
WHERE event_type IN ('email.blacklisted', 'email.unblacklisted')
ORDER BY created_at DESC
LIMIT 100;
```

## Best Practices

### When to Blacklist

1. **Confirmed Abuse**: User repeatedly violates terms of service
2. **Spam/Bot Activity**: Multiple signup attempts, automated behavior
3. **Fraud**: Confirmed fraudulent activity
4. **Legal Requirements**: Court orders or legal compliance

### What NOT to Blacklist

1. **Single Complaints**: One complaint does not justify blacklist
2. **Technical Issues**: Don't blacklist for bugs or system errors
3. **Expired Accounts**: Use workspace suspension instead
4. **Payment Issues**: Use workspace suspension instead

### Documentation Requirements

Every blacklist entry MUST include:
- Clear, specific reason for blacklisting
- Date and time of decision
- Who made the decision (added_by field)
- Supporting evidence (link to ticket, incident report, etc.)

## Related Documentation

- [SECURITY_ARCHITECTURE.md](./SECURITY_ARCHITECTURE.md) - Overall security design
- [AUDIT_LOGGING_SCHEMA.md](./AUDIT_LOGGING_SCHEMA.md) - Audit event structure
- [magic-link-token-handling.md](./magic-link-token-handling.md) - Magic link authentication
- [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md) - Handling security incidents

## Migration Notes

### Existing Users

If a user already has an active account when added to blacklist:
- They cannot request new magic links
- Existing sessions remain valid until expiration
- To immediately revoke access, also suspend their workspace

### Pending Invitations

When email is added to blacklist:
- Pending invitation tokens are automatically revoked
- User cannot accept invitation even with valid token
- Platform admin must resend invitation after removal from blacklist

## Changelog

### 2025-10-22: Initial Implementation
- Added `EmailBlacklist` model
- Implemented `is_email_blacklisted()` utility
- Added enforcement in 3 critical points:
  1. Invitation creation (`create_workspace_and_invite_therapist`)
  2. Magic link request (`request_magic_link`)
  3. Invitation acceptance (`accept_invitation`)
- Added comprehensive test coverage (30+ test cases)
- Created platform admin CRUD endpoints
- Implemented audit logging for all blocked attempts

## Support

For questions or issues related to email blacklist enforcement:

1. Check audit logs for blacklist activity
2. Review test cases for expected behavior
3. Consult security team for policy decisions
4. See [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md) for escalation procedures
