"""Authentication service for magic link and JWT management."""

from __future__ import annotations

import json
import secrets
import uuid
from base64 import urlsafe_b64encode
from hashlib import sha256

import redis.asyncio as redis
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.security import create_access_token
from pazpaz.models.user import User
from pazpaz.models.workspace import WorkspaceStatus
from pazpaz.services.email_service import send_magic_link_email

logger = get_logger(__name__)

# Magic link token expiry (10 minutes)
MAGIC_LINK_EXPIRY_SECONDS = 60 * 10

# Magic link rate limit per email (3 per hour)
RATE_LIMIT_MAX_REQUESTS = 3
RATE_LIMIT_WINDOW_SECONDS = 60 * 60

# Brute force detection (100 failed attempts = 5-min lockout)
BRUTE_FORCE_THRESHOLD = 100
BRUTE_FORCE_LOCKOUT_SECONDS = 300  # 5 minutes


def get_token_cipher() -> Fernet:
    """
    Get Fernet cipher for encrypting tokens in Redis.

    Derives encryption key from SECRET_KEY to avoid additional key management.
    This provides defense-in-depth protection against Redis memory dumps.

    Returns:
        Fernet cipher instance

    Security:
        - Derives 32-byte key from SECRET_KEY using SHA256
        - Uses Fernet (symmetric encryption with HMAC authentication)
        - Protects token data at rest in Redis
    """
    # Derive 32-byte key from SECRET_KEY
    key_material = sha256(settings.secret_key.encode()).digest()
    key = urlsafe_b64encode(key_material)
    return Fernet(key)


async def store_magic_link_token(
    redis_client: redis.Redis,
    token: str,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    email: str,
    expiry_seconds: int,
) -> None:
    """
    Store magic link token data in Redis with encryption.

    Encrypts token data before storing to protect against Redis memory dumps
    or unauthorized Redis access (defense-in-depth).

    Args:
        redis_client: Redis client
        token: Magic link token (384-bit)
        user_id: User ID
        workspace_id: Workspace ID
        email: User email
        expiry_seconds: Token expiration time in seconds

    Security:
        - Encrypts all token data with Fernet (AES-128 + HMAC)
        - Token data never stored in plaintext in Redis
        - Encryption key derived from SECRET_KEY
    """
    # Prepare token data
    token_data = {
        "user_id": str(user_id),
        "workspace_id": str(workspace_id),
        "email": email,
    }

    # Encrypt token data before storing in Redis (defense-in-depth)
    cipher = get_token_cipher()
    encrypted_data = cipher.encrypt(json.dumps(token_data).encode())

    # Store encrypted data in Redis
    token_key = f"magic_link:{token}"
    await redis_client.setex(
        token_key,
        expiry_seconds,
        encrypted_data.decode(),
    )

    logger.debug(
        "magic_link_token_stored_encrypted",
        user_id=str(user_id),
        expiry_seconds=expiry_seconds,
    )


async def retrieve_magic_link_token(
    redis_client: redis.Redis,
    token: str,
) -> dict[str, str] | None:
    """
    Retrieve and decrypt magic link token data from Redis.

    Args:
        redis_client: Redis client
        token: Magic link token

    Returns:
        Token data dictionary or None if not found/invalid

    Security:
        - Decrypts token data from Redis
        - Returns None if token not found or decryption fails
        - Deletes corrupted tokens automatically
    """
    token_key = f"magic_link:{token}"
    encrypted_data_str = await redis_client.get(token_key)

    if not encrypted_data_str:
        return None

    try:
        # Decrypt token data
        cipher = get_token_cipher()
        decrypted_data = cipher.decrypt(encrypted_data_str.encode())
        token_data = json.loads(decrypted_data.decode())
        return token_data

    except Exception as e:
        logger.error(
            "magic_link_token_decryption_failed",
            error=str(e),
            exc_info=True,
        )
        # Delete corrupted token
        await redis_client.delete(token_key)
        return None


async def request_magic_link(
    email: str,
    db: AsyncSession,
    redis_client: redis.Redis,
    request_ip: str,
) -> None:
    """
    Generate and send magic link to user email with audit logging.

    Security features:
    - Rate limiting: 3 requests per hour per IP
    - Generic response to prevent email enumeration
    - 384-bit entropy tokens (quantum-resistant margin)
    - Token data encrypted in Redis (defense-in-depth)
    - 10-minute expiry
    - Audit logging for all attempts (success, failure, inactive user)

    Args:
        email: User email address
        db: Database session
        redis_client: Redis client
        request_ip: Request IP address for rate limiting

    Raises:
        HTTPException: If rate limit exceeded
    """
    # Check rate limit by IP (3 requests per hour using sliding window)
    # FAIL CLOSED on Redis failure (security-critical)
    rate_limit_key = f"magic_link_rate_limit:{request_ip}"

    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=rate_limit_key,
        max_requests=RATE_LIMIT_MAX_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        fail_closed_on_error=True,  # CRITICAL: Fail closed for auth endpoints
    ):
        # Rate limit exceeded OR Redis unavailable (both cases block)
        logger.warning(
            "magic_link_rate_limit_exceeded_or_redis_unavailable",
            ip=request_ip,
            email=email,
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )

    # Look up user by email
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        # Log failed attempt (potential reconnaissance)
        from pazpaz.models.audit_event import AuditAction, ResourceType
        from pazpaz.services.audit_service import create_audit_event

        try:
            await create_audit_event(
                db=db,
                user_id=None,  # No user (failed attempt)
                workspace_id=None,  # No workspace context
                action=AuditAction.READ,  # Attempted to read user data
                resource_type=ResourceType.USER,
                resource_id=None,
                ip_address=request_ip,
                metadata={
                    "action": "magic_link_request_nonexistent_email",
                    "email_provided": email,
                    "result": "user_not_found",
                },
            )
        except Exception as e:
            # Log error but don't fail authentication flow
            logger.error(
                "failed_to_create_audit_event_for_nonexistent_email",
                error=str(e),
                exc_info=True,
            )

        logger.info(
            "magic_link_requested_nonexistent_email",
            email=email,
        )
        # Return success to prevent email enumeration
        return

    if not user.is_active:
        # Log failed attempt (inactive user)
        from pazpaz.models.audit_event import AuditAction, ResourceType
        from pazpaz.services.audit_service import create_audit_event

        try:
            await create_audit_event(
                db=db,
                user_id=user.id,
                workspace_id=user.workspace_id,
                action=AuditAction.READ,
                resource_type=ResourceType.USER,
                resource_id=user.id,
                ip_address=request_ip,
                metadata={
                    "action": "magic_link_request_inactive_user",
                    "result": "user_inactive",
                },
            )
        except Exception as e:
            # Log error but don't fail authentication flow
            logger.error(
                "failed_to_create_audit_event_for_inactive_user",
                error=str(e),
                exc_info=True,
            )

        logger.warning(
            "magic_link_requested_inactive_user",
            email=email,
            user_id=str(user.id),
        )
        # Return success to prevent user status enumeration
        return

    # Generate secure token (384-bit entropy for defense-in-depth)
    # secrets.token_urlsafe(48) generates 48 bytes * 8 bits = 384 bits
    # This provides additional security margin against theoretical quantum attacks
    token = secrets.token_urlsafe(48)  # 48 bytes = 384 bits

    # Store token with encryption (defense-in-depth)
    await store_magic_link_token(
        redis_client=redis_client,
        token=token,
        user_id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
        expiry_seconds=MAGIC_LINK_EXPIRY_SECONDS,
    )

    # Send magic link email
    await send_magic_link_email(user.email, token)

    # Log successful magic link generation
    from pazpaz.models.audit_event import AuditAction, ResourceType
    from pazpaz.services.audit_service import create_audit_event

    try:
        await create_audit_event(
            db=db,
            user_id=user.id,
            workspace_id=user.workspace_id,
            action=AuditAction.READ,  # Reading user data to generate link
            resource_type=ResourceType.USER,
            resource_id=user.id,
            ip_address=request_ip,
            metadata={
                "action": "magic_link_generated",
                "token_expiry_seconds": MAGIC_LINK_EXPIRY_SECONDS,
            },
        )
    except Exception as e:
        # Log error but don't fail authentication flow
        logger.error(
            "failed_to_create_audit_event_for_magic_link_generation",
            error=str(e),
            exc_info=True,
        )

    logger.info(
        "magic_link_generated",
        email=email,
        user_id=str(user.id),
    )


async def verify_magic_link_token(
    token: str,
    db: AsyncSession,
    redis_client: redis.Redis,
    request_ip: str | None = None,
) -> tuple[User, str] | dict | None:
    """
    Verify magic link token and generate JWT with brute force detection.

    If user has 2FA enabled, returns a dict with status='requires_2fa'
    and temporary token for the 2FA verification step. Otherwise returns
    tuple of (User, JWT token).

    Args:
        token: Magic link token
        db: Database session
        redis_client: Redis client
        request_ip: Request IP address for audit logging (optional)

    Returns:
        - Tuple of (User, JWT token) if valid and 2FA not enabled
        - Dict with {'status': 'requires_2fa', 'user_id': str,
          'temp_token': str} if 2FA enabled
        - None if invalid/expired

    Security:
        - Token is single-use (deleted after verification)
        - User existence is revalidated in database
        - JWT contains workspace_id for workspace scoping
        - Brute force detection (100 failed attempts = 5-min lockout)
        - Token data decrypted from Redis
        - Audit logging for all verification attempts
        - 2FA check before issuing JWT

    Raises:
        HTTPException: If brute force lockout is active
    """
    # Track failed verification attempts (detect brute force)
    attempt_key = "magic_link_failed_attempts"

    try:
        # Check if too many failed attempts globally (brute force detection)
        failed_attempts_str = await redis_client.get(attempt_key)

        if failed_attempts_str:
            failed_attempts = int(failed_attempts_str)
            if failed_attempts >= BRUTE_FORCE_THRESHOLD:
                lockout_remaining = await redis_client.ttl(attempt_key)
                logger.critical(
                    "magic_link_brute_force_detected",
                    failed_attempts=failed_attempts,
                    lockout_remaining=lockout_remaining,
                )
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Too many failed login attempts. "
                        f"Try again in {lockout_remaining} seconds."
                    ),
                )

        # Retrieve and decrypt token data
        token_data = await retrieve_magic_link_token(redis_client, token)

        if not token_data:
            # Failed attempt - increment counter
            await redis_client.incr(attempt_key)
            await redis_client.expire(attempt_key, BRUTE_FORCE_LOCKOUT_SECONDS)

            # Log failed verification attempt
            from pazpaz.models.audit_event import AuditAction, ResourceType
            from pazpaz.services.audit_service import create_audit_event

            try:
                await create_audit_event(
                    db=db,
                    user_id=None,
                    workspace_id=None,
                    action=AuditAction.READ,
                    resource_type=ResourceType.USER,
                    resource_id=None,
                    ip_address=request_ip,
                    metadata={
                        "action": "magic_link_verification_failed",
                        "reason": "token_not_found_or_expired",
                        "token_prefix": token[:16],
                    },
                )
            except Exception as e:
                logger.error(
                    "failed_to_create_audit_event_for_token_not_found",
                    error=str(e),
                    exc_info=True,
                )

            logger.warning(
                "magic_link_token_not_found_or_expired",
                token_prefix=token[:16],  # Log first 16 chars only
            )
            return None

        # Parse token data
        try:
            user_id = uuid.UUID(token_data["user_id"])
            # workspace_id validated but not used (kept for security validation)
            _workspace_id = uuid.UUID(token_data["workspace_id"])
        except (KeyError, ValueError) as e:
            # Failed attempt - increment counter
            await redis_client.incr(attempt_key)
            await redis_client.expire(attempt_key, BRUTE_FORCE_LOCKOUT_SECONDS)

            logger.error("magic_link_token_parse_error", error=str(e))
            return None

        # Validate user still exists and is active
        # Eagerly load workspace to check status
        from sqlalchemy.orm import selectinload

        query = (
            select(User).where(User.id == user_id).options(selectinload(User.workspace))
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            # Failed verification - increment counter
            await redis_client.incr(attempt_key)
            await redis_client.expire(attempt_key, BRUTE_FORCE_LOCKOUT_SECONDS)

            # Log failed verification (user not found or inactive)
            from pazpaz.models.audit_event import AuditAction, ResourceType
            from pazpaz.services.audit_service import create_audit_event

            try:
                await create_audit_event(
                    db=db,
                    user_id=user_id if user else None,
                    workspace_id=user.workspace_id if user else None,
                    action=AuditAction.READ,
                    resource_type=ResourceType.USER,
                    resource_id=user_id if user else None,
                    ip_address=request_ip,
                    metadata={
                        "action": "magic_link_verification_failed",
                        "reason": "user_not_found_or_inactive",
                    },
                )
            except Exception as e:
                logger.error(
                    "failed_to_create_audit_event_for_user_not_found_or_inactive",
                    error=str(e),
                    exc_info=True,
                )

            logger.warning(
                "magic_link_verification_failed",
                reason="user_not_found_or_inactive",
                user_id=str(user_id),
            )
            # Delete invalid token
            token_key = f"magic_link:{token}"
            await redis_client.delete(token_key)
            return None

        # CRITICAL SECURITY CHECK: Verify workspace status
        # Users from SUSPENDED or DELETED workspaces cannot authenticate
        if user.workspace.status != WorkspaceStatus.ACTIVE:
            # Failed verification - increment counter
            await redis_client.incr(attempt_key)
            await redis_client.expire(attempt_key, BRUTE_FORCE_LOCKOUT_SECONDS)

            # Log failed verification (workspace not active)
            from pazpaz.models.audit_event import AuditAction, ResourceType
            from pazpaz.services.audit_service import create_audit_event

            try:
                await create_audit_event(
                    db=db,
                    user_id=user.id,
                    workspace_id=user.workspace_id,
                    action=AuditAction.READ,
                    resource_type=ResourceType.USER,
                    resource_id=user.id,
                    ip_address=request_ip,
                    metadata={
                        "action": "magic_link_verification_failed",
                        "reason": "workspace_not_active",
                        "workspace_status": user.workspace.status.value,
                    },
                )
            except Exception as e:
                logger.error(
                    "failed_to_create_audit_event_for_workspace_not_active",
                    error=str(e),
                    exc_info=True,
                )

            logger.warning(
                "magic_link_verification_failed_workspace_not_active",
                reason="workspace_suspended_or_deleted",
                user_id=str(user.id),
                workspace_id=str(user.workspace_id),
                workspace_status=user.workspace.status.value,
            )

            # Delete token (single-use even on failure)
            token_key = f"magic_link:{token}"
            await redis_client.delete(token_key)
            return None

        # Success - reset attempt counter
        await redis_client.delete(attempt_key)

        # Check if 2FA is enabled
        if user.totp_enabled:
            # Store temporary token in Redis for 2FA verification (5 minutes)
            temp_token = secrets.token_urlsafe(48)  # 384-bit token
            temp_token_key = f"2fa_pending:{temp_token}"
            temp_token_data = {
                "user_id": str(user.id),
                "workspace_id": str(user.workspace_id),
                "email": user.email,
            }

            # Encrypt temp token data
            cipher = get_token_cipher()
            encrypted_data = cipher.encrypt(json.dumps(temp_token_data).encode())

            # Store with 5-minute expiry
            await redis_client.setex(temp_token_key, 300, encrypted_data.decode())

            # Delete magic link token (single-use)
            token_key = f"magic_link:{token}"
            await redis_client.delete(token_key)

            logger.info(
                "magic_link_verified_2fa_required",
                user_id=str(user.id),
                workspace_id=str(user.workspace_id),
            )

            # Return 2FA requirement
            return {
                "status": "requires_2fa",
                "user_id": str(user.id),
                "email": user.email,
                "temp_token": temp_token,
            }

        # No 2FA required - generate JWT
        jwt_token = create_access_token(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
        )

        # Delete token from Redis (single-use)
        token_key = f"magic_link:{token}"
        await redis_client.delete(token_key)

        # Log successful authentication
        from pazpaz.models.audit_event import AuditAction, ResourceType
        from pazpaz.services.audit_service import create_audit_event

        try:
            await create_audit_event(
                db=db,
                user_id=user.id,
                workspace_id=user.workspace_id,
                action=AuditAction.READ,  # Authenticated access
                resource_type=ResourceType.USER,
                resource_id=user.id,
                ip_address=request_ip,
                metadata={
                    "action": "user_authenticated",
                    "authentication_method": "magic_link",
                    "jwt_issued": True,
                },
            )
        except Exception as e:
            # Log error but don't fail authentication
            logger.error(
                "failed_to_create_audit_event_for_successful_authentication",
                error=str(e),
                exc_info=True,
            )

        logger.info(
            "magic_link_verified",
            user_id=str(user.id),
            workspace_id=str(user.workspace_id),
        )

        return user, jwt_token

    except HTTPException:
        raise
    except Exception as e:
        # Any error during verification counts as failed attempt
        await redis_client.incr(attempt_key)
        await redis_client.expire(attempt_key, BRUTE_FORCE_LOCKOUT_SECONDS)
        logger.error("magic_link_verification_error", error=str(e), exc_info=True)
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Get user by email address.

    Args:
        db: Database session
        email: User email address

    Returns:
        User if found, None otherwise
    """
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    Get user by ID.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        User if found, None otherwise
    """
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def blacklist_token(redis_client: redis.Redis, token: str) -> None:
    """
    Add a JWT token to the blacklist.

    Stores the token's JTI (JWT ID) in Redis with TTL equal to token expiry.
    This prevents the token from being used after logout.

    Args:
        redis_client: Redis client instance
        token: JWT token to blacklist

    Raises:
        ValueError: If token is invalid or missing JTI claim
    """
    from datetime import UTC, datetime

    from jose import jwt
    from jose.exceptions import ExpiredSignatureError

    from pazpaz.core.config import settings

    try:
        # Decode token to extract JTI and expiration
        # Use verify_exp=True to validate token before blacklisting
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True},  # Validate it's not already expired
        )

        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti or not exp:
            raise ValueError("Token missing JTI or exp claim")

        # Calculate TTL (time until token expires)
        now = datetime.now(UTC).timestamp()
        ttl = int(exp - now)

        if ttl <= 0:
            # Token already expired, no need to blacklist
            logger.debug("token_already_expired_skip_blacklist", jti=jti)
            return

        # Store JTI in Redis with TTL
        blacklist_key = f"blacklist:jwt:{jti}"
        await redis_client.setex(blacklist_key, ttl, "1")

        logger.info("jwt_token_blacklisted", jti=jti, ttl=ttl)

    except ExpiredSignatureError:
        logger.debug("attempted_to_blacklist_expired_token")
        # Don't raise error, just skip blacklisting expired tokens
        return
    except Exception as e:
        logger.error(
            "failed_to_blacklist_token",
            error=str(e),
            exc_info=True,
        )
        raise


async def is_token_blacklisted(redis_client: redis.Redis, token: str) -> bool:
    """
    Check if a JWT token has been blacklisted.

    Args:
        redis_client: Redis client instance
        token: JWT token to check

    Returns:
        True if token is blacklisted, False otherwise
    """
    from jose import jwt
    from jose.exceptions import ExpiredSignatureError

    from pazpaz.core.config import settings

    try:
        # Decode token to extract JTI (WITH expiration validation)
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            # Removed verify_exp=False - use default expiration validation
        )

        jti = payload.get("jti")
        if not jti:
            # Old tokens without JTI should be rejected
            logger.warning("token_missing_jti_treating_as_blacklisted")
            return True

        # Check if JTI exists in blacklist
        blacklist_key = f"blacklist:jwt:{jti}"
        result = await redis_client.get(blacklist_key)

        is_blacklisted = result is not None
        if is_blacklisted:
            logger.info("token_is_blacklisted", jti=jti)

        return is_blacklisted

    except ExpiredSignatureError:
        # Expired tokens are implicitly invalid
        logger.debug("token_expired_treating_as_blacklisted")
        return True
    except Exception as e:
        logger.error(
            "failed_to_check_blacklist",
            error=str(e),
            exc_info=True,
        )
        # Fail closed: if we can't check blacklist, reject token
        return True
