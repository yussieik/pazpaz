import { ref, type Ref } from 'vue'
import {
  PlatformAdminService,
  type InviteTherapistRequest,
  type InviteTherapistResponse,
  type PendingInvitation,
  type ResendInvitationResponse,
  ApiError,
} from '@/api/generated'

/**
 * Composable for platform admin operations
 *
 * Provides:
 * - Fetching pending invitations
 * - Inviting new therapists
 * - Resending invitations
 *
 * Security:
 * - All operations require platform admin authentication
 * - Operations are workspace-scoped
 * - Invitation tokens are SHA256 hashed
 *
 * Usage:
 *   const { pendingInvitations, loading, error, fetchPendingInvitations, ... } = usePlatformAdmin()
 */
export function usePlatformAdmin() {
  const pendingInvitations: Ref<PendingInvitation[]> = ref([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /**
   * Fetch all pending invitations (users who haven't accepted yet)
   *
   * Returns inactive users sorted by invited_at (newest first)
   * Includes expiration status calculated from invited_at + 7 days
   *
   * Error responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   */
  async function fetchPendingInvitations(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response =
        await PlatformAdminService.getPendingInvitationsApiV1PlatformAdminPendingInvitationsGet()

      pendingInvitations.value = response.invitations || []
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to load pending invitations'
      console.error('Failed to fetch pending invitations:', apiError)
      pendingInvitations.value = []
    } finally {
      loading.value = false
    }
  }

  /**
   * Invite a new therapist to the platform
   *
   * Creates a new workspace and user account, then generates an invitation token.
   * Platform admin receives invitation URL to send via email.
   *
   * Flow:
   * 1. Platform admin provides workspace name, therapist email, and full name
   * 2. System creates workspace and inactive user account
   * 3. System generates invitation token (256-bit entropy, expires in 7 days)
   * 4. Platform admin receives invitation URL to send via email
   * 5. Therapist clicks link to accept invitation and activate account
   *
   * After successful invitation, refreshes the pending invitations list.
   *
   * Error responses:
   * - 400: Email already exists (duplicate)
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 422: Validation error (invalid email, empty fields)
   *
   * @param request - Invitation details (workspace name, email, full name)
   * @returns Promise<InviteTherapistResponse> - Contains workspace_id, user_id, and invitation_url
   * @throws Error if invitation fails
   */
  async function inviteTherapist(
    request: InviteTherapistRequest
  ): Promise<InviteTherapistResponse> {
    loading.value = true
    error.value = null

    try {
      const response =
        await PlatformAdminService.inviteTherapistApiV1PlatformAdminInviteTherapistPost(
          request
        )

      // Refresh pending invitations to include the newly invited user
      await fetchPendingInvitations()

      return response
    } catch (err) {
      const apiError = err as ApiError
      if (apiError.status === 400) {
        error.value = apiError.body?.detail || 'This email is already in use'
      } else {
        error.value = apiError.body?.detail || 'Failed to send invitation'
      }
      console.error('Failed to invite therapist:', apiError)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Resend invitation to a pending user
   *
   * Generates a new invitation token for a user who has not yet accepted.
   * Old token is invalidated and replaced with new one (7-day expiration).
   *
   * Use cases:
   * - Original invitation expired (>7 days)
   * - Therapist lost invitation email
   * - Invitation token compromised
   *
   * After successful resend, refreshes the pending invitations list
   * to update the invited_at timestamp.
   *
   * Error responses:
   * - 400: User is already active (invitation already accepted)
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 404: User not found
   * - 422: Invalid UUID format
   *
   * @param userId - UUID of the user to resend invitation to
   * @returns Promise<ResendInvitationResponse> - Contains new invitation_url
   * @throws Error if resend fails
   */
  async function resendInvitation(userId: string): Promise<ResendInvitationResponse> {
    loading.value = true
    error.value = null

    try {
      const response =
        await PlatformAdminService.resendInvitationApiV1PlatformAdminResendInvitationUserIdPost(
          userId
        )

      // Refresh pending invitations to update invited_at timestamp
      await fetchPendingInvitations()

      return response
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to resend invitation'
      console.error('Failed to resend invitation:', apiError)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Clear error state
   *
   * Useful for dismissing error messages in UI
   */
  function clearError(): void {
    error.value = null
  }

  return {
    // State
    pendingInvitations,
    loading,
    error,

    // Methods
    fetchPendingInvitations,
    inviteTherapist,
    resendInvitation,
    clearError,
  }
}
