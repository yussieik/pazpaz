/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LogoutResponse } from '../models/LogoutResponse'
import type { MagicLink2FARequest } from '../models/MagicLink2FARequest'
import type { MagicLink2FAResponse } from '../models/MagicLink2FAResponse'
import type { MagicLinkRequest } from '../models/MagicLinkRequest'
import type { MagicLinkResponse } from '../models/MagicLinkResponse'
import type { TokenVerifyRequest } from '../models/TokenVerifyRequest'
import type { TokenVerifyResponse } from '../models/TokenVerifyResponse'
import type { TOTPDisableRequest } from '../models/TOTPDisableRequest'
import type { TOTPEnrollResponse } from '../models/TOTPEnrollResponse'
import type { TOTPVerifyRequest } from '../models/TOTPVerifyRequest'
import type { TOTPVerifyResponse } from '../models/TOTPVerifyResponse'
import type { UserInToken } from '../models/UserInToken'
import type { CancelablePromise } from '../core/CancelablePromise'
import { OpenAPI } from '../core/OpenAPI'
import { request as __request } from '../core/request'
export class AuthenticationService {
  /**
   * Request magic link
   * Request a magic link to be sent to the provided email address.
   *
   * Security features:
   * - Rate limited to 3 requests per hour per IP address
   * - Rate limited to 5 requests per hour per email address (prevents email bombing)
   * - Returns generic success message to prevent email enumeration
   * - Tokens are 256-bit entropy with 10-minute expiry
   * - Single-use tokens (deleted after verification)
   *
   * If an active user exists with the email, they will receive a login link.
   * Otherwise, no email is sent but the same success message is returned.
   * @param requestBody
   * @returns MagicLinkResponse Successful Response
   * @throws ApiError
   */
  public static requestMagicLinkEndpointApiV1AuthMagicLinkPost(
    requestBody: MagicLinkRequest
  ): CancelablePromise<MagicLinkResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/magic-link',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Verify magic link token
   * Verify a magic link token and receive a JWT access token.
   *
   * Security features:
   * - Token MUST be sent in POST body, not URL query parameter (CWE-598 mitigation)
   * - Rate limited to 10 verification attempts per 5 minutes per IP (brute force protection)
   * - Single-use tokens (deleted after successful verification)
   * - User existence revalidated in database
   * - JWT contains user_id and workspace_id for authorization
   * - JWT stored in HttpOnly cookie for XSS protection
   * - 7-day JWT expiry
   * - Uses POST method to prevent CSRF attacks (state-changing operation)
   * - Audit logging for all verification attempts
   * - Referrer-Policy prevents token leakage via referrer headers
   *
   * Frontend MUST remove token from URL immediately after reading:
   * window.history.replaceState({}, document.title, '/auth/verify')
   *
   * The token parameter is received from the email link and sent in request body.
   * On success, a JWT is set as an HttpOnly cookie and returned in response.
   * @param requestBody
   * @returns TokenVerifyResponse Successful Response
   * @throws ApiError
   */
  public static verifyMagicLinkEndpointApiV1AuthVerifyPost(
    requestBody: TokenVerifyRequest
  ): CancelablePromise<TokenVerifyResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/verify',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Complete authentication with 2FA after magic link
   * Complete authentication after magic link when 2FA is enabled.
   *
   * Security features:
   * - Temporary token expires in 5 minutes
   * - Validates TOTP code or backup code
   * - Single-use backup codes
   * - Audit logging for 2FA verification
   * - Issues JWT on successful verification
   *
   * Flow:
   * 1. User clicks magic link
   * 2. /verify returns requires_2fa=True with temp_token
   * 3. User enters TOTP code from authenticator
   * 4. /verify-2fa validates code and issues JWT
   *
   * Args:
   * temp_token: Temporary token from /verify response
   * totp_code: 6-digit TOTP code or 8-character backup code
   * @param requestBody
   * @returns MagicLink2FAResponse Successful Response
   * @throws ApiError
   */
  public static verifyMagicLink2FaEndpointApiV1AuthVerify2FaPost(
    requestBody: MagicLink2FARequest
  ): CancelablePromise<MagicLink2FAResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/verify-2fa',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Accept therapist invitation
   * Accept therapist invitation and activate account via magic link.
   *
   * Security features:
   * - Single-use invitation tokens (7-day expiration)
   * - Token verification uses timing-safe comparison (SHA256)
   * - Activates user account and creates session
   * - HttpOnly cookies for XSS protection
   * - Audit logging for invitation acceptance
   * - Generic error messages (no token leakage)
   *
   * Flow:
   * 1. Therapist clicks invitation link in email
   * 2. Token verified and user activated
   * 3. JWT session created and cookies set
   * 4. Redirect to app (logged in)
   *
   * Error handling:
   * - Invalid/expired tokens redirect to /login with error parameter
   * - Already accepted redirects to /login with info message
   * - All errors are logged server-side for security monitoring
   * @param token Invitation token from email
   * @returns void
   * @throws ApiError
   */
  public static acceptInvitationApiV1AuthAcceptInviteGet(
    token: string
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/accept-invite',
      query: {
        token: token,
      },
      errors: {
        303: `Successful Response`,
        422: `Validation Error`,
      },
    })
  }
  /**
   * Get current user
   * Get information about the currently authenticated user.
   *
   * Security features:
   * - Requires valid JWT authentication (HttpOnly cookie)
   * - Returns user information from validated session
   * - Used by frontend to check authentication status
   *
   * This endpoint is typically called:
   * - On app startup to restore authentication state
   * - After login to verify successful authentication
   * - To check if session is still valid
   *
   * Returns 401 Unauthorized if not authenticated or session expired.
   * @param accessToken
   * @returns UserInToken Successful Response
   * @throws ApiError
   */
  public static getCurrentUserEndpointApiV1AuthMeGet(
    accessToken?: string | null
  ): CancelablePromise<UserInToken> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/me',
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Logout
   * Logout by clearing the JWT cookie and blacklisting the token.
   *
   * Security features:
   * - Clears HttpOnly authentication cookie
   * - Blacklists JWT token in Redis (prevents reuse)
   * - Clears CSRF token cookie
   * - Requires CSRF token for protection against logout CSRF attacks
   * - Audit logging for logout events
   *
   * The blacklisted token cannot be used even if stolen, providing
   * enhanced security compared to client-side-only logout.
   * @param accessToken
   * @returns LogoutResponse Successful Response
   * @throws ApiError
   */
  public static logoutEndpointApiV1AuthLogoutPost(
    accessToken?: string | null
  ): CancelablePromise<LogoutResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/logout',
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Enroll in 2FA/TOTP
   * Enroll current authenticated user in 2FA/TOTP.
   *
   * Security features:
   * - TOTP secret generated with 160 bits entropy
   * - Secret stored encrypted with AES-256-GCM
   * - QR code generated for easy authenticator app setup
   * - 8 backup codes generated and hashed with Argon2id
   * - Not enabled until user verifies with /totp/verify
   * - Requires existing authentication (JWT)
   *
   * Returns:
   * - TOTP secret (base32-encoded, for manual entry)
   * - QR code (data URI, for scanning)
   * - 8 backup codes (shown ONLY ONCE, save offline)
   *
   * User must verify TOTP code with /totp/verify before 2FA is enabled.
   * @param accessToken
   * @returns TOTPEnrollResponse Successful Response
   * @throws ApiError
   */
  public static enrollUserTotpApiV1AuthTotpEnrollPost(
    accessToken?: string | null
  ): CancelablePromise<TOTPEnrollResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/totp/enroll',
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Verify TOTP code and enable 2FA
   * Verify TOTP code and enable 2FA for current user.
   *
   * Security features:
   * - Must be called after /totp/enroll
   * - Validates 6-digit TOTP code from authenticator app
   * - Window of ±30 seconds for clock skew tolerance
   * - Sets enrollment timestamp
   * - Audit logging for successful enrollment
   * - Requires existing authentication (JWT)
   *
   * After successful verification, 2FA is enabled and will be required
   * on all future magic link authentications.
   * @param requestBody
   * @param accessToken
   * @returns TOTPVerifyResponse Successful Response
   * @throws ApiError
   */
  public static verifyUserTotpApiV1AuthTotpVerifyPost(
    requestBody: TOTPVerifyRequest,
    accessToken?: string | null
  ): CancelablePromise<TOTPVerifyResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/totp/verify',
      cookies: {
        access_token: accessToken,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Refresh user session
   * Refresh user session to extend JWT expiry.
   *
   * Security features:
   * - HIPAA compliance for session timeout warnings (§164.312(a)(2)(iii))
   * - Extends JWT expiry by resetting activity timestamp
   * - Prevents data loss from silent session expiration
   * - Used by frontend session timeout warning modal
   *
   * This endpoint:
   * - Validates current JWT authentication
   * - Updates session activity timestamp
   * - Returns success response (JWT automatically refreshed via dependency)
   * - Frontend should call this when user clicks "Stay logged in" button
   *
   * Returns 401 Unauthorized if session already expired.
   * @param accessToken
   * @returns any Successful Response
   * @throws ApiError
   */
  public static refreshSessionEndpointApiV1AuthSessionRefreshPost(
    accessToken?: string | null
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/session/refresh',
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Disable 2FA
   * Disable 2FA for current authenticated user.
   *
   * SECURITY: Requires TOTP verification before disabling.
   * This prevents attackers with stolen sessions from disabling 2FA.
   *
   * Security considerations:
   * - Removes all TOTP data (secret, backup codes, timestamp)
   * - Requires valid TOTP code verification before disabling
   * - Audit logging for 2FA disable (both success and failure)
   * - Requires existing authentication (JWT)
   *
   * WARNING: After disabling, user will only have magic link authentication.
   * @param requestBody
   * @param accessToken
   * @returns any Successful Response
   * @throws ApiError
   */
  public static disableUserTotpApiV1AuthTotpDelete(
    requestBody: TOTPDisableRequest,
    accessToken?: string | null
  ): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/v1/auth/totp',
      cookies: {
        access_token: accessToken,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    })
  }
}
