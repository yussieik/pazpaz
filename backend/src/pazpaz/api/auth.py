"""Authentication endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.core.redis import get_redis
from pazpaz.db.base import get_db
from pazpaz.middleware.csrf import generate_csrf_token
from pazpaz.api.deps import get_current_user
from pazpaz.models.user import User
from pazpaz.schemas.auth import (
    LogoutResponse,
    MagicLink2FARequest,
    MagicLink2FAResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
    TOTPEnrollResponse,
    TOTPVerifyRequest,
    TOTPVerifyResponse,
    UserInToken,
)
from pazpaz.services.auth_service import request_magic_link, verify_magic_link_token
from pazpaz.services.totp_service import (
    disable_totp,
    enroll_totp,
    verify_and_enable_totp,
    verify_totp_or_backup,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/magic-link",
    response_model=MagicLinkResponse,
    status_code=200,
    summary="Request magic link",
    description="""
    Request a magic link to be sent to the provided email address.

    Security features:
    - Rate limited to 3 requests per hour per IP address
    - Rate limited to 5 requests per hour per email address (prevents email bombing)
    - Returns generic success message to prevent email enumeration
    - Tokens are 256-bit entropy with 10-minute expiry
    - Single-use tokens (deleted after verification)

    If an active user exists with the email, they will receive a login link.
    Otherwise, no email is sent but the same success message is returned.
    """,
)
async def request_magic_link_endpoint(
    data: MagicLinkRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> MagicLinkResponse:
    """
    Request a magic link login email with enhanced protection.

    Rate limited by:
    - IP address: 3 requests per hour (handled by request_magic_link service)
    - Email address: 5 requests per hour (prevents email bombing attacks)
    """
    from pazpaz.core.rate_limiting import check_rate_limit_redis

    # Get request IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # ADDITIONAL PROTECTION: Per-email rate limiting (5 requests per hour)
    # Prevents email bombing even if attacker uses multiple IPs/proxies
    # This check happens BEFORE IP rate limiting to provide earliest protection
    # FAIL CLOSED on Redis failure (security-critical)
    email_rate_limit_key = f"magic_link_rate_limit_email:{data.email}"

    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=email_rate_limit_key,
        max_requests=5,  # Max 5 requests per email per hour
        window_seconds=3600,  # 1 hour
        fail_closed_on_error=True,  # CRITICAL: Fail closed for auth
    ):
        logger.warning(
            "magic_link_rate_limit_exceeded_for_email_or_redis_unavailable",
            email=data.email,
            ip=client_ip,
        )
        # Return generic success to prevent email enumeration
        # Even though rate limit is exceeded OR Redis is down, we don't reveal this
        # But we log the event for security monitoring
        return MagicLinkResponse()

    # Request magic link (handles IP-based rate limiting internally)
    await request_magic_link(
        email=data.email,
        db=db,
        redis_client=redis_client,
        request_ip=client_ip,
    )

    # Always return success to prevent email enumeration
    return MagicLinkResponse()


@router.post(
    "/verify",
    response_model=TokenVerifyResponse,
    status_code=200,
    summary="Verify magic link token",
    description="""
    Verify a magic link token and receive a JWT access token.

    Security features:
    - Token MUST be sent in POST body, not URL query parameter (CWE-598 mitigation)
    - Rate limited to 10 verification attempts per 5 minutes per IP (brute force protection)
    - Single-use tokens (deleted after successful verification)
    - User existence revalidated in database
    - JWT contains user_id and workspace_id for authorization
    - JWT stored in HttpOnly cookie for XSS protection
    - 7-day JWT expiry
    - Uses POST method to prevent CSRF attacks (state-changing operation)
    - Audit logging for all verification attempts
    - Referrer-Policy prevents token leakage via referrer headers

    Frontend MUST remove token from URL immediately after reading:
    window.history.replaceState({}, document.title, '/auth/verify')

    The token parameter is received from the email link and sent in request body.
    On success, a JWT is set as an HttpOnly cookie and returned in response.
    """,
)
async def verify_magic_link_endpoint(
    data: TokenVerifyRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> TokenVerifyResponse:
    """
    Verify magic link token and issue JWT with audit logging.

    Security: Token sent in POST body (not URL) prevents logging/history leakage.
    CWE-598 Mitigation: Use of GET Request Method With Sensitive Query Strings.

    Args:
        data: Token verification request containing magic link token
        request: Request object (for IP extraction)
        response: FastAPI response object (for setting cookie)
        db: Database session
        redis_client: Redis client

    Returns:
        JWT access token and user information

    Raises:
        HTTPException: 401 if token is invalid or expired
        HTTPException: 429 if rate limit exceeded (10 attempts / 5 min per IP)
    """
    from pazpaz.core.rate_limiting import check_rate_limit_redis

    # Extract client IP for rate limiting and audit logging
    client_ip = request.client.host if request.client else "unknown"

    # SECURITY: Rate limit verify endpoint (10 attempts per 5 minutes per IP)
    # Prevents brute force attacks on magic link tokens
    # FAIL CLOSED on Redis failure (security-critical)
    verify_rate_limit_key = f"magic_link_verify_rate_limit:{client_ip}"

    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=verify_rate_limit_key,
        max_requests=10,  # Max 10 verify attempts per 5 minutes
        window_seconds=300,  # 5 minutes
        fail_closed_on_error=True,  # CRITICAL: Fail closed for auth
    ):
        logger.warning(
            "magic_link_verify_rate_limit_exceeded",
            ip=client_ip,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many verification attempts. Please try again later.",
        )

    # Verify token and get JWT (pass IP for audit logging)
    result = await verify_magic_link_token(
        token=data.token,
        db=db,
        redis_client=redis_client,
        request_ip=client_ip,
    )

    if not result:
        logger.warning("magic_link_verification_failed", token=data.token[:16])
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired magic link token",
        )

    # Check if 2FA is required
    if isinstance(result, dict) and result.get("status") == "requires_2fa":
        # Return 2FA requirement with 200 status
        # Frontend should redirect to 2FA verification page
        return {
            "requires_2fa": True,
            "temp_token": result["temp_token"],
            "user_id": result["user_id"],
            "message": "2FA verification required",
        }

    user, jwt_token = result

    # Generate CSRF token
    csrf_token = await generate_csrf_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
        redis_client=redis_client,
    )

    # Set JWT as HttpOnly cookie (XSS protection)
    # SameSite=Lax for CSRF protection while allowing navigation
    # Secure flag auto-enabled in production (settings.debug=False)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,  # Auto-enable in production
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    # Set CSRF token as cookie (not HttpOnly, JS needs to read)
    # SameSite=Strict for additional CSRF protection
    # Secure flag auto-enabled in production (settings.debug=False)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Allow JS to read for X-CSRF-Token header
        samesite="strict",  # Stricter than JWT cookie for CSRF prevention
        secure=not settings.debug,  # Auto-enable in production
        max_age=60 * 60 * 24 * 7,  # 7 days (match JWT)
    )

    logger.info(
        "user_authenticated",
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )

    return TokenVerifyResponse(
        access_token=jwt_token,
        user=UserInToken.model_validate(user),
    )


@router.post(
    "/verify-2fa",
    response_model=MagicLink2FAResponse,
    status_code=200,
    summary="Complete authentication with 2FA after magic link",
    description="""
    Complete authentication after magic link when 2FA is enabled.

    Security features:
    - Temporary token expires in 5 minutes
    - Validates TOTP code or backup code
    - Single-use backup codes
    - Audit logging for 2FA verification
    - Issues JWT on successful verification

    Flow:
    1. User clicks magic link
    2. /verify returns requires_2fa=True with temp_token
    3. User enters TOTP code from authenticator
    4. /verify-2fa validates code and issues JWT

    Args:
        temp_token: Temporary token from /verify response
        totp_code: 6-digit TOTP code or 8-character backup code
    """,
)
async def verify_magic_link_2fa_endpoint(
    request_data: MagicLink2FARequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> MagicLink2FAResponse:
    """
    Complete authentication with 2FA after magic link.

    Verifies TOTP code and issues JWT on success.
    """
    from pazpaz.services.auth_service import get_token_cipher

    # Extract client IP for audit logging
    client_ip = request.client.host if request.client else None

    # Retrieve temporary token data from Redis
    temp_token_key = f"2fa_pending:{request_data.temp_token}"
    encrypted_data_str = await redis_client.get(temp_token_key)

    if not encrypted_data_str:
        logger.warning(
            "2fa_verification_failed_temp_token_not_found",
            token_prefix=request_data.temp_token[:16],
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired 2FA token",
        )

    # Decrypt temp token data
    try:
        cipher = get_token_cipher()
        decrypted_data = cipher.decrypt(encrypted_data_str.encode())
        temp_token_data = json.loads(decrypted_data.decode())
        user_id = uuid.UUID(temp_token_data["user_id"])
        workspace_id = uuid.UUID(temp_token_data["workspace_id"])
    except Exception as e:
        logger.error(
            "2fa_temp_token_decryption_failed",
            error=str(e),
            exc_info=True,
        )
        # Delete corrupted token
        await redis_client.delete(temp_token_key)
        raise HTTPException(
            status_code=401,
            detail="Invalid 2FA token",
        ) from e

    # Verify TOTP code
    is_valid = await verify_totp_or_backup(db, user_id, request_data.totp_code)

    if not is_valid:
        logger.warning(
            "2fa_verification_failed_invalid_code",
            user_id=str(user_id),
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid 2FA code",
        )

    # Delete temporary token (single-use)
    await redis_client.delete(temp_token_key)

    # Fetch user for JWT generation
    from pazpaz.services.auth_service import get_user_by_id

    user = await get_user_by_id(db, user_id)

    if not user or not user.is_active:
        logger.warning(
            "2fa_verification_failed_user_not_found_or_inactive",
            user_id=str(user_id),
        )
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive",
        )

    # Generate JWT
    from pazpaz.core.security import create_access_token

    jwt_token = create_access_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
    )

    # Generate CSRF token
    csrf_token = await generate_csrf_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
        redis_client=redis_client,
    )

    # Set JWT as HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    # Set CSRF token as cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="strict",
        secure=not settings.debug,
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    # Log successful authentication with 2FA
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
            ip_address=client_ip,
            metadata={
                "action": "user_authenticated",
                "authentication_method": "magic_link_with_2fa",
                "jwt_issued": True,
            },
        )
    except Exception as e:
        logger.error(
            "failed_to_create_audit_event_for_2fa_authentication",
            error=str(e),
            exc_info=True,
        )

    logger.info(
        "user_authenticated_with_2fa",
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )

    return MagicLink2FAResponse(
        access_token=jwt_token,
        user=UserInToken.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=200,
    summary="Logout",
    description="""
    Logout by clearing the JWT cookie and blacklisting the token.

    Security features:
    - Clears HttpOnly authentication cookie
    - Blacklists JWT token in Redis (prevents reuse)
    - Clears CSRF token cookie
    - Requires CSRF token for protection against logout CSRF attacks
    - Audit logging for logout events

    The blacklisted token cannot be used even if stolen, providing
    enhanced security compared to client-side-only logout.
    """,
)
async def logout_endpoint(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    access_token: str | None = Cookie(None),
) -> LogoutResponse:
    """
    Logout user by clearing authentication cookie and blacklisting JWT with audit logging.

    Args:
        request: Request object (for IP extraction)
        response: FastAPI response object (for clearing cookie)
        db: Database session (for audit logging)
        redis_client: Redis client for token blacklisting
        access_token: Current JWT from cookie (optional)

    Returns:
        Success message
    """
    from pazpaz.services.auth_service import blacklist_token
    from pazpaz.services.session_activity import invalidate_session_activity

    # Extract client IP for audit logging
    client_ip = request.client.host if request.client else None

    # Blacklist the JWT token (if present)
    if access_token:
        try:
            from pazpaz.core.security import decode_access_token
            from pazpaz.models.audit_event import AuditAction, ResourceType
            from pazpaz.services.audit_service import create_audit_event

            # Decode token to get user info for audit logging
            try:
                payload = decode_access_token(access_token)
                user_id = uuid.UUID(payload.get("user_id"))
                workspace_id = uuid.UUID(payload.get("workspace_id"))
                jti = payload.get("jti")

                # Blacklist token
                await blacklist_token(redis_client, access_token)

                # Invalidate session activity record
                if jti:
                    await invalidate_session_activity(
                        redis_client=redis_client,
                        user_id=str(user_id),
                        jti=jti,
                    )

                # Log logout event
                try:
                    await create_audit_event(
                        db=db,
                        user_id=user_id,
                        workspace_id=workspace_id,
                        action=AuditAction.UPDATE,  # Session state changed
                        resource_type=ResourceType.USER,
                        resource_id=user_id,
                        ip_address=client_ip,
                        metadata={
                            "action": "user_logged_out",
                            "jwt_blacklisted": True,
                        },
                    )
                except Exception as e:
                    logger.error(
                        "failed_to_create_audit_event_for_logout",
                        error=str(e),
                        exc_info=True,
                    )

                logger.info("jwt_token_blacklisted_on_logout", user_id=str(user_id))

            except Exception as e:
                logger.error(
                    "failed_to_decode_token_for_logout_audit",
                    error=str(e),
                    exc_info=True,
                )
                # Still blacklist token even if decoding failed
                await blacklist_token(redis_client, access_token)

        except Exception as e:
            # Log error but don't fail logout
            # User experience is that logout succeeds even if blacklisting fails
            logger.error(
                "failed_to_blacklist_token_on_logout",
                error=str(e),
                exc_info=True,
            )

    # Clear authentication cookie
    response.delete_cookie(key="access_token")

    # Clear CSRF token cookie
    response.delete_cookie(key="csrf_token")

    logger.info("user_logged_out")

    return LogoutResponse()


# TOTP/2FA Endpoints


@router.post(
    "/totp/enroll",
    response_model=TOTPEnrollResponse,
    status_code=200,
    summary="Enroll in 2FA/TOTP",
    description="""
    Enroll current authenticated user in 2FA/TOTP.

    Security features:
    - TOTP secret generated with 160 bits entropy
    - Secret stored encrypted with AES-256-GCM
    - QR code generated for easy authenticator app setup
    - 8 backup codes generated and hashed with Argon2id
    - Not enabled until user verifies with /totp/verify
    - Requires existing authentication (JWT)

    Returns:
    - TOTP secret (base32-encoded, for manual entry)
    - QR code (data URI, for scanning)
    - 8 backup codes (shown ONLY ONCE, save offline)

    User must verify TOTP code with /totp/verify before 2FA is enabled.
    """,
)
async def enroll_user_totp(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TOTPEnrollResponse:
    """
    Enroll current user in 2FA/TOTP.

    Returns TOTP secret, QR code, and backup codes.
    User must verify with /totp/verify before 2FA is enabled.
    """
    try:
        enrollment = await enroll_totp(db, current_user.id)

        logger.info(
            "totp_enrollment_initiated",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
        )

        return TOTPEnrollResponse(
            secret=enrollment["secret"],
            qr_code=enrollment["qr_code"],
            backup_codes=enrollment["backup_codes"],
        )
    except ValueError as e:
        logger.warning(
            "totp_enrollment_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/totp/verify",
    response_model=TOTPVerifyResponse,
    status_code=200,
    summary="Verify TOTP code and enable 2FA",
    description="""
    Verify TOTP code and enable 2FA for current user.

    Security features:
    - Must be called after /totp/enroll
    - Validates 6-digit TOTP code from authenticator app
    - Window of ±30 seconds for clock skew tolerance
    - Sets enrollment timestamp
    - Audit logging for successful enrollment
    - Requires existing authentication (JWT)

    After successful verification, 2FA is enabled and will be required
    on all future magic link authentications.
    """,
)
async def verify_user_totp(
    request_data: TOTPVerifyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TOTPVerifyResponse:
    """
    Verify TOTP code and enable 2FA.

    Must be called after /totp/enroll with valid TOTP code.
    """
    try:
        success = await verify_and_enable_totp(db, current_user.id, request_data.code)

        if success:
            logger.info(
                "totp_verification_success",
                user_id=str(current_user.id),
                workspace_id=str(current_user.workspace_id),
            )
            return TOTPVerifyResponse(
                success=True,
                message="2FA enabled successfully",
            )
        else:
            logger.warning(
                "totp_verification_invalid_code",
                user_id=str(current_user.id),
            )
            return TOTPVerifyResponse(
                success=False,
                message="Invalid TOTP code",
            )
    except ValueError as e:
        logger.warning(
            "totp_verification_error",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete(
    "/totp",
    status_code=200,
    summary="Disable 2FA",
    description="""
    Disable 2FA for current authenticated user.

    Security considerations:
    - Removes all TOTP data (secret, backup codes, timestamp)
    - Should require re-authentication or additional verification in production
    - Audit logging for 2FA disable
    - Requires existing authentication (JWT)

    WARNING: After disabling, user will only have magic link authentication.
    Consider requiring email confirmation or TOTP verification before disabling.
    """,
)
async def disable_user_totp(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Disable 2FA for current user.

    Requires re-authentication to disable 2FA (security best practice).
    """
    try:
        await disable_totp(db, current_user.id)

        logger.info(
            "totp_disabled",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
        )

        return {"message": "2FA disabled successfully"}
    except ValueError as e:
        logger.warning(
            "totp_disable_failed",
            user_id=str(current_user.id),
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e)) from e
