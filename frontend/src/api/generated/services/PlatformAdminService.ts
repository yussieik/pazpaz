/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { InviteTherapistRequest } from '../models/InviteTherapistRequest'
import type { InviteTherapistResponse } from '../models/InviteTherapistResponse'
import type { PendingInvitationsResponse } from '../models/PendingInvitationsResponse'
import type { ResendInvitationResponse } from '../models/ResendInvitationResponse'
import type { CancelablePromise } from '../core/CancelablePromise'
import { OpenAPI } from '../core/OpenAPI'
import { request as __request } from '../core/request'
export class PlatformAdminService {
  /**
   * Invite a new therapist
   * Create a new workspace and invite a therapist to join the platform.
   *
   * Security:
   * - Requires platform admin authentication
   * - Email uniqueness enforced (400 if duplicate)
   * - Invitation token SHA256 hashed in database
   * - Token expires in 7 days
   * - Audit logging for all invitations
   *
   * Flow:
   * 1. Platform admin provides workspace name, therapist email, and full name
   * 2. System creates workspace and inactive user account
   * 3. System generates invitation token (256-bit entropy)
   * 4. Platform admin receives invitation URL to send via email
   * 5. Therapist clicks link and accepts invitation to activate account
   *
   * Error Responses:
   * - 400: Email already exists (duplicate)
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 422: Validation error (invalid email, empty fields)
   * @param requestBody
   * @param accessToken
   * @returns InviteTherapistResponse Successful Response
   * @throws ApiError
   */
  public static inviteTherapistApiV1PlatformAdminInviteTherapistPost(
    requestBody: InviteTherapistRequest,
    accessToken?: string | null
  ): CancelablePromise<InviteTherapistResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/platform-admin/invite-therapist',
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
   * Resend invitation to pending user
   * Generate a new invitation token for a user who has not yet accepted
   * their invitation.
   *
   * Security:
   * - Requires platform admin authentication
   * - Only works for inactive users (is_active=False)
   * - Old token is invalidated (replaced with new one)
   * - New 7-day expiration window
   * - Audit logging for resends
   *
   * Use Cases:
   * - Original invitation expired (>7 days)
   * - Therapist lost invitation email
   * - Invitation token compromised
   *
   * Error Responses:
   * - 400: User is already active (invitation already accepted)
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 404: User not found
   * - 422: Invalid UUID format
   * @param userId
   * @param accessToken
   * @returns ResendInvitationResponse Successful Response
   * @throws ApiError
   */
  public static resendInvitationApiV1PlatformAdminResendInvitationUserIdPost(
    userId: string,
    accessToken?: string | null
  ): CancelablePromise<ResendInvitationResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/platform-admin/resend-invitation/{user_id}',
      path: {
        user_id: userId,
      },
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * List all pending invitations
   * Get a list of all users who have been invited but have not yet accepted
   * their invitation.
   *
   * Security:
   * - Requires platform admin authentication
   * - Returns only inactive users (is_active=False)
   * - Includes expiration status (calculated from invited_at + 7 days)
   * - Sorted by invited_at (newest first)
   *
   * Response includes:
   * - user_id: UUID of the user
   * - email: Email address
   * - full_name: Full name
   * - workspace_name: Name of workspace user will join
   * - invited_at: When invitation was sent (UTC)
   * - expires_at: When invitation expires (UTC)
   *
   * Use Cases:
   * - Monitor pending onboarding
   * - Identify expired invitations for cleanup
   * - Follow up with therapists who haven't accepted
   *
   * Error Responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   * @param accessToken
   * @returns PendingInvitationsResponse Successful Response
   * @throws ApiError
   */
  public static getPendingInvitationsApiV1PlatformAdminPendingInvitationsGet(
    accessToken?: string | null
  ): CancelablePromise<PendingInvitationsResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/platform-admin/pending-invitations',
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
}
