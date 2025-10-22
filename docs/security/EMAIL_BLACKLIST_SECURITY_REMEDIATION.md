# Email Blacklist Security Remediation Plan

**Status**: 🔴 **CRITICAL - DO NOT DEPLOY**
**Date**: 2025-10-22
**Priority**: P0 - Immediate Action Required

---

## Executive Summary

The email blacklist enforcement implementation contains **4 critical security vulnerabilities** that must be fixed before production deployment:

1. **Database case sensitivity bypass** - Attackers can bypass blacklist using mixed-case emails
2. **Race condition (TOCTOU)** - Users can be created/activated during blacklist check window
3. **Email enumeration via timing** - Valid emails can be discovered through response time analysis
4. **Fail-open on database errors** - Database failures allow blacklisted users through

**Risk Level**: **HIGH**
**Recommended Action**: **Block deployment until P0 fixes complete**

---

## Quick Fixes (Can Deploy Today)

### Fix #1: Database Case Sensitivity (2 hours)

**Problem**: PostgreSQL VARCHAR comparison is case-sensitive, allowing bypass if mixed-case entries exist.

**Solution**: Use CITEXT column type for case-insensitive storage and comparison.

**Migration**:
```sql
-- File: backend/alembic/versions/XXXX_fix_email_blacklist_case_sensitivity.py

def upgrade():
    # Enable CITEXT extension
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    # Change email column to CITEXT
    op.execute("""
        ALTER TABLE email_blacklist
          ALTER COLUMN email TYPE CITEXT
          USING LOWER(email);
    """)

    # Ensure all existing emails are lowercase
    op.execute("""
        UPDATE email_blacklist
        SET email = LOWER(email);
    """)

    # Add database-level check constraint
    op.execute("""
        ALTER TABLE email_blacklist
          ADD CONSTRAINT email_must_be_lowercase
          CHECK (email = LOWER(email));
    """)

def downgrade():
    op.execute("ALTER TABLE email_blacklist DROP CONSTRAINT email_must_be_lowercase;")
    op.execute("ALTER TABLE email_blacklist ALTER COLUMN email TYPE VARCHAR(255);")
```

**Code Changes**: None required - CITEXT handles case-insensitivity at DB level.

**Testing**:
```python
# Test mixed-case blacklist entry
async def test_case_insensitive_blacklist():
    # Manually insert uppercase entry (simulating direct DB insert)
    await db.execute(
        text("INSERT INTO email_blacklist (id, email, reason) "
             "VALUES (gen_random_uuid(), 'SPAM@EXAMPLE.COM', 'Test')")
    )
    await db.commit()

    # Verify lowercase query matches
    assert await is_email_blacklisted(db, "spam@example.com") is True
    assert await is_email_blacklisted(db, "SPAM@EXAMPLE.COM") is True
    assert await is_email_blacklisted(db, "Spam@Example.Com") is True
```

---

### Fix #2: Fail-Closed on Database Errors (3 hours)

**Problem**: If database query fails, function may return False by default, allowing blacklisted users.

**Solution**: Explicit error handling with fail-closed behavior.

**File**: `backend/src/pazpaz/core/blacklist.py`

```python
from fastapi import HTTPException

async def is_email_blacklisted(db: AsyncSession, email: str) -> bool:
    """
    Check if an email address is blacklisted (case-insensitive).

    SECURITY: Fails CLOSED on database errors (rejects request).

    Args:
        db: Database session (async)
        email: Email address to check

    Returns:
        True if email is blacklisted, False otherwise

    Raises:
        HTTPException: 503 if database check fails (fail-closed)
    """
    try:
        # Normalize email to lowercase
        normalized_email = email.strip().lower()

        # Validate email format
        if not normalized_email or '@' not in normalized_email:
            logger.warning(
                "invalid_email_format_in_blacklist_check",
                email=email,
            )
            return False

        # Query blacklist table (indexed on email column)
        result = await db.scalar(
            select(EmailBlacklist.id)
            .where(EmailBlacklist.email == normalized_email)
            .limit(1)
        )

        is_blacklisted = result is not None

        if is_blacklisted:
            # Use SHA256 for secure hash logging
            import hashlib
            email_hash = hashlib.sha256(normalized_email.encode()).hexdigest()[:16]

            logger.warning(
                "blacklisted_email_detected",
                email_hash=email_hash,
            )

        return is_blacklisted

    except Exception as e:
        # FAIL CLOSED: If we can't check blacklist, REJECT the request
        logger.error(
            "blacklist_check_failed_rejecting_request",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # Raise 503 to indicate service unavailability
        # Prevents user creation/authentication when blacklist is down
        raise HTTPException(
            status_code=503,
            detail="Email verification temporarily unavailable. Please try again later.",
        ) from e
```

**Testing**:
```python
from unittest.mock import patch
from sqlalchemy.exc import OperationalError

async def test_blacklist_check_fails_closed_on_db_error():
    """Verify that database errors cause fail-closed behavior."""
    # Mock database to raise OperationalError
    with patch("pazpaz.core.blacklist.db.scalar", side_effect=OperationalError("DB down", None, None)):
        with pytest.raises(HTTPException) as exc_info:
            await is_email_blacklisted(db, "test@example.com")

        assert exc_info.value.status_code == 503
        assert "unavailable" in exc_info.value.detail.lower()
```

---

### Fix #3: Whitespace Normalization (1 hour)

**Problem**: Email normalization only lowercases, doesn't strip whitespace.

**Solution**: Add `.strip()` to normalization (already implemented in Fix #2 above).

**Additional Validation**:
```python
# In platform_onboarding_service.py::create_workspace_and_invite_therapist
# Validate and normalize email at service layer
therapist_email = therapist_email.strip().lower()

if not therapist_email or '@' not in therapist_email:
    raise ValueError("Invalid email address format")
```

**Testing**:
```python
async def test_whitespace_stripped_in_blacklist_check():
    """Test that leading/trailing whitespace is stripped."""
    # Add blacklist entry
    entry = EmailBlacklist(email="spam@example.com", reason="Test")
    db.add(entry)
    await db.commit()

    # Test with whitespace
    assert await is_email_blacklisted(db, "  spam@example.com  ") is True
    assert await is_email_blacklisted(db, "\tspam@example.com\n") is True
```

---

## Critical Fixes (Deploy This Week)

### Fix #4: Race Condition Prevention (4 hours)

**Problem**: Blacklist check and user creation are in separate transactions, allowing TOCTOU race.

**Solution A: Database Trigger** (Recommended)

Create database trigger to prevent activation of blacklisted users:

```sql
-- Migration: backend/alembic/versions/XXXX_add_blacklist_activation_trigger.py

def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_blacklisted_user_activation()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Check if user is being activated
            IF NEW.is_active = TRUE AND (OLD.is_active IS NULL OR OLD.is_active = FALSE) THEN
                -- Check if email is blacklisted
                IF EXISTS (
                    SELECT 1 FROM email_blacklist
                    WHERE LOWER(email) = LOWER(NEW.email)
                ) THEN
                    RAISE EXCEPTION 'Cannot activate user with blacklisted email: %', NEW.email
                        USING ERRCODE = '23514';  -- check_violation
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER check_blacklist_before_activation
            BEFORE INSERT OR UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION prevent_blacklisted_user_activation();
    """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS check_blacklist_before_activation ON users;")
    op.execute("DROP FUNCTION IF EXISTS prevent_blacklisted_user_activation;")
```

**Solution B: Application-Level Recheck** (Fallback)

Add re-check before commit in critical flows:

```python
# In platform_onboarding_service.py::accept_invitation
async def accept_invitation(self, db: AsyncSession, token: str) -> User:
    try:
        # ... existing token verification ...

        # Check blacklist BEFORE activation
        from pazpaz.core.blacklist import is_email_blacklisted

        if await is_email_blacklisted(db, user.email):
            logger.warning(
                "invitation_acceptance_blocked_blacklisted_email",
                user_id=str(user.id),
                email=user.email,
            )
            raise InvalidInvitationTokenError(
                "This email address is not eligible to accept invitations"
            )

        # Activate user
        user.is_active = True
        user.invitation_token_hash = None

        # RE-CHECK blacklist before commit (prevents TOCTOU)
        if await is_email_blacklisted(db, user.email):
            await db.rollback()
            logger.critical(
                "race_condition_detected_blacklist_added_during_activation",
                user_id=str(user.id),
                email=user.email,
            )
            raise InvalidInvitationTokenError(
                "This email address was blacklisted during activation"
            )

        await db.commit()
        # ...
```

**Testing**:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def test_race_condition_prevented_by_trigger():
    """Test that database trigger prevents race condition."""
    # Create pending invitation
    user = User(
        email="race@example.com",
        is_active=False,
        invitation_token_hash="test_hash",
    )
    db.add(user)
    await db.commit()

    async def activate_user():
        await asyncio.sleep(0.01)  # Small delay
        user.is_active = True
        await db.commit()

    async def blacklist_email():
        entry = EmailBlacklist(email="race@example.com", reason="Test")
        db.add(entry)
        await db.commit()

    # Run concurrently
    with pytest.raises(Exception) as exc_info:
        await asyncio.gather(activate_user(), blacklist_email())

    # Verify trigger prevented activation
    assert "blacklisted email" in str(exc_info.value).lower()

    # Verify user is NOT active
    await db.refresh(user)
    assert user.is_active is False
```

---

### Fix #5: Timing Attack Mitigation (6 hours)

**Problem**: Response time differs between blacklisted, non-existent, and valid users, enabling enumeration.

**Solution**: Constant-time responses by moving email sending to background queue.

**File**: `backend/src/pazpaz/services/auth_service.py`

```python
from fastapi import BackgroundTasks

async def request_magic_link(
    email: str,
    db: AsyncSession,
    redis_client: redis.Redis,
    request_ip: str,
    background_tasks: BackgroundTasks,  # ✅ Add parameter
) -> None:
    """
    Generate and send magic link to user email with audit logging.

    SECURITY: Constant-time response to prevent email enumeration via timing.
    """
    # ... existing rate limit check ...

    # ALWAYS check blacklist (don't early return)
    is_blacklisted = await is_email_blacklisted(db, email)

    # ALWAYS look up user (same code path for all requests)
    from sqlalchemy.orm import selectinload

    query = (
        select(User).where(User.email == email).options(selectinload(User.workspace))
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # ALWAYS create audit event (generic action)
    from pazpaz.models.audit_event import AuditAction, ResourceType
    from pazpaz.services.audit_service import create_audit_event

    # Determine action and send email based on combined state
    should_send_email = False
    audit_action = "magic_link_request_blocked"

    if is_blacklisted:
        audit_result = "email_blacklisted"
        logger.warning("magic_link_request_blocked_blacklisted_email", email=email, ip=request_ip)

    elif not user:
        audit_result = "user_not_found"
        logger.info("magic_link_requested_nonexistent_email", email=email)

    elif not user.is_active:
        audit_result = "user_inactive"
        logger.warning("magic_link_requested_inactive_user", email=email, user_id=str(user.id))

    elif user.workspace.status != WorkspaceStatus.ACTIVE:
        audit_result = "workspace_not_active"
        logger.warning("magic_link_request_rejected_workspace_not_active", ...)
        raise HTTPException(status_code=403, detail="Your workspace is not active.")

    else:
        # Valid user - send email
        should_send_email = True
        audit_action = "magic_link_generated"
        audit_result = "success"

        # Generate token
        token = secrets.token_urlsafe(48)

        # Store token with encryption
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=MAGIC_LINK_EXPIRY_SECONDS,
        )

        # Queue email in background (constant time!)
        background_tasks.add_task(send_magic_link_email, user.email, token)

        logger.info("magic_link_generated", email=email, user_id=str(user.id))

    # ALWAYS create audit event
    try:
        await create_audit_event(
            db=db,
            user_id=user.id if user else None,
            workspace_id=user.workspace_id if user else None,
            action=AuditAction.READ,
            resource_type=ResourceType.USER,
            resource_id=user.id if user else None,
            ip_address=request_ip,
            metadata={
                "action": audit_action,
                "result": audit_result,
            },
        )
    except Exception as e:
        logger.error("failed_to_create_audit_event", error=str(e), exc_info=True)

    # Return IMMEDIATELY (don't wait for email)
    # Response time is now constant regardless of user state
```

**Update API Endpoint**:
```python
# In backend/src/pazpaz/api/auth.py

@router.post("/magic-link")
async def request_magic_link_endpoint(
    data: MagicLinkRequest,
    request: Request,
    background_tasks: BackgroundTasks,  # ✅ Add dependency
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> MagicLinkResponse:
    client_ip = request.client.host if request.client else "unknown"

    # ... email rate limiting ...

    await request_magic_link(
        email=data.email,
        db=db,
        redis_client=redis_client,
        request_ip=client_ip,
        background_tasks=background_tasks,  # ✅ Pass background tasks
    )

    return MagicLinkResponse()
```

**Testing**:
```python
import time
import statistics

async def test_magic_link_timing_is_constant():
    """Test that response time is constant regardless of email status."""
    # Create test data
    blacklisted_email = "blacklisted@example.com"
    valid_email = "valid@example.com"
    fake_email = "fake@example.com"

    # Add blacklist entry
    db.add(EmailBlacklist(email=blacklisted_email, reason="Test"))

    # Add valid user
    db.add(User(email=valid_email, is_active=True, ...))
    await db.commit()

    # Measure timing for each category
    async def measure_timing(email, iterations=50):
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            response = await client.post("/api/v1/auth/request-magic-link", json={"email": email})
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert response.status_code == 200  # All return 200

        return statistics.median(times)

    blacklisted_time = await measure_timing(blacklisted_email)
    valid_time = await measure_timing(valid_email)
    fake_time = await measure_timing(fake_email)

    # Verify timing difference is minimal (<50ms)
    assert abs(blacklisted_time - valid_time) < 0.05
    assert abs(blacklisted_time - fake_time) < 0.05
    assert abs(valid_time - fake_time) < 0.05

    # Verify all times are under 100ms (fast response)
    assert blacklisted_time < 0.1
    assert valid_time < 0.1
    assert fake_time < 0.1
```

---

## Testing Checklist

Before deploying fixes:

### Unit Tests
- [ ] Case-insensitive blacklist check (uppercase, lowercase, mixed)
- [ ] Whitespace normalization (leading, trailing, tabs, newlines)
- [ ] Database error handling (OperationalError, TimeoutError)
- [ ] Invalid email format handling

### Integration Tests
- [ ] Blacklist enforcement in invitation creation
- [ ] Blacklist enforcement in invitation acceptance
- [ ] Blacklist enforcement in magic link request
- [ ] Error responses are consistent (403 for blacklist)

### Security Tests
- [ ] Race condition prevention (concurrent blacklist + invitation)
- [ ] Timing attack resistance (constant response time)
- [ ] Database trigger prevents activation of blacklisted users
- [ ] Fail-closed behavior on database errors

### Performance Tests
- [ ] Blacklist check latency <10ms (p95)
- [ ] No N+1 queries in blacklist operations
- [ ] Database index is used (EXPLAIN ANALYZE)

---

## Deployment Plan

### Phase 1: Database Changes (30 minutes)
1. Deploy migration for CITEXT column type
2. Deploy migration for activation trigger
3. Verify migrations in staging
4. Run smoke tests

### Phase 2: Application Code (1 hour)
1. Deploy updated `blacklist.py` with fail-closed handling
2. Deploy updated `auth_service.py` with background email sending
3. Deploy updated `platform_onboarding_service.py` with whitespace normalization
4. Restart application servers

### Phase 3: Verification (30 minutes)
1. Run security test suite
2. Verify audit logs are created
3. Verify blacklist enforcement works
4. Monitor error rates and latency

### Phase 4: Monitoring (Ongoing)
1. Set up alerts for blacklist hit rate
2. Set up alerts for database errors
3. Monitor response time distribution
4. Review audit logs daily

---

## Rollback Plan

If issues occur after deployment:

### Immediate Rollback
```bash
# Rollback database migrations
cd backend
alembic downgrade -1  # Rollback trigger
alembic downgrade -1  # Rollback CITEXT

# Rollback application code
git revert HEAD
git push origin main
```

### Partial Rollback
If only one fix is problematic, you can:
- Disable trigger: `ALTER TABLE users DISABLE TRIGGER check_blacklist_before_activation;`
- Revert specific code file: `git checkout HEAD~1 -- backend/src/pazpaz/core/blacklist.py`

---

## Success Criteria

Deployment is successful when:

- [ ] All 4 critical vulnerabilities are fixed
- [ ] Test suite passes (100% on security tests)
- [ ] No increase in error rates (< 0.1%)
- [ ] Response times remain stable (p95 < 100ms)
- [ ] Audit logs show blacklist enforcement working
- [ ] No user complaints about blocked access (false positives)

---

## Questions / Escalation

**For questions about this remediation plan:**
- Security Team: security@pazpaz.com
- Backend Team: backend@pazpaz.com

**For production issues:**
- On-call Engineer: [PagerDuty link]
- Escalation: CTO

---

**Prepared by**: Security Auditor Agent
**Date**: 2025-10-22
**Version**: 1.0
