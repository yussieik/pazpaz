import { ref, type Ref } from 'vue'
import {
  PlatformAdminService,
  type InviteTherapistRequest,
  type InviteTherapistResponse,
  type PendingInvitation,
  type ResendInvitationResponse,
  ApiError,
} from '@/api/generated'
import apiClient from '@/api/client'
import type { Workspace } from '@/components/platform-admin/WorkspaceCard.vue'

export interface BlacklistEntry {
  email: string
  reason: string
  addedAt: string
  addedBy?: string | null
}

/**
 * Composable for platform admin operations
 *
 * Provides:
 * - Fetching pending invitations
 * - Inviting new therapists
 * - Resending invitations
 * - Managing workspaces (list, suspend, reactivate, delete)
 * - Managing blacklist (list, add, remove)
 *
 * Security:
 * - All operations require platform admin authentication
 * - Operations are workspace-scoped
 * - Invitation tokens are SHA256 hashed
 * - All actions create audit trail
 *
 * Usage:
 *   const { pendingInvitations, loading, error, fetchPendingInvitations, ... } = usePlatformAdmin()
 */
export function usePlatformAdmin() {
  const pendingInvitations: Ref<PendingInvitation[]> = ref([])
  const workspaces: Ref<Workspace[]> = ref([])
  const blacklist: Ref<BlacklistEntry[]> = ref([])
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

  // ==================== WORKSPACE MANAGEMENT ====================

  /**
   * Fetch all workspaces
   *
   * GET /api/v1/platform-admin/workspaces
   *
   * Error responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   */
  async function fetchWorkspaces(search?: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get<{
        workspaces: Array<{
          id: string
          name: string
          owner_email: string
          status: string
          created_at: string
          user_count: number
          session_count: number
        }>
      }>('/platform-admin/workspaces', {
        params: search ? { search } : undefined,
      })

      // Transform API response to Workspace format
      workspaces.value = response.data.workspaces.map((ws) => ({
        id: ws.id,
        name: ws.name,
        email: ws.owner_email,
        status: ws.status as 'active' | 'pending' | 'suspended',
        createdAt: ws.created_at,
        userCount: ws.user_count,
        activeUsers: ws.user_count, // Backend doesn't provide this separately yet
        appointmentCount: ws.session_count,
      }))
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to load workspaces'
      console.error('Failed to fetch workspaces:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Suspend a workspace
   *
   * POST /api/v1/platform-admin/workspaces/:id/suspend
   *
   * Error responses:
   * - 400: Workspace already suspended or deleted
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 404: Workspace not found
   */
  async function suspendWorkspace(workspaceId: string, reason: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      await apiClient.post(`/platform-admin/workspaces/${workspaceId}/suspend`, {
        reason,
      })

      // Optimistically update workspace status
      const workspace = workspaces.value.find((w) => w.id === workspaceId)
      if (workspace) {
        workspace.status = 'suspended'
      }
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to suspend workspace'
      console.error('Failed to suspend workspace:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Reactivate a suspended workspace
   *
   * POST /api/v1/platform-admin/workspaces/:id/reactivate
   *
   * Error responses:
   * - 400: Workspace not suspended (already active or deleted)
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 404: Workspace not found
   */
  async function reactivateWorkspace(workspaceId: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      await apiClient.post(`/platform-admin/workspaces/${workspaceId}/reactivate`)

      // Optimistically update workspace status
      const workspace = workspaces.value.find((w) => w.id === workspaceId)
      if (workspace) {
        workspace.status = 'active'
      }
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to reactivate workspace'
      console.error('Failed to reactivate workspace:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete a workspace (soft delete)
   *
   * DELETE /api/v1/platform-admin/workspaces/:id
   *
   * Error responses:
   * - 400: Workspace already deleted
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 404: Workspace not found
   */
  async function deleteWorkspace(workspaceId: string, reason: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      await apiClient.delete(`/platform-admin/workspaces/${workspaceId}`, {
        data: { reason },
      })

      // Remove workspace from local state
      workspaces.value = workspaces.value.filter((w) => w.id !== workspaceId)
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to delete workspace'
      console.error('Failed to delete workspace:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  // ==================== BLACKLIST MANAGEMENT ====================

  /**
   * Fetch blacklist from backend
   *
   * GET /api/v1/platform-admin/blacklist
   *
   * Error responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   */
  async function fetchBlacklist(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get<{
        blacklist: Array<{
          email: string
          reason: string
          added_at: string
          added_by: string | null
        }>
      }>('/platform-admin/blacklist')

      // Transform API response to BlacklistEntry format
      blacklist.value = response.data.blacklist.map((entry) => ({
        email: entry.email,
        reason: entry.reason,
        addedAt: entry.added_at,
        addedBy: entry.added_by,
      }))
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to load blacklist'
      console.error('Failed to fetch blacklist:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Add email to blacklist
   *
   * POST /api/v1/platform-admin/blacklist
   *
   * Error responses:
   * - 400: Email already blacklisted
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 422: Invalid email format
   */
  async function addToBlacklist(email: string, reason: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      await apiClient.post('/platform-admin/blacklist', {
        email,
        reason,
      })

      // Refetch blacklist to get complete entry with metadata
      await fetchBlacklist()
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to add to blacklist'
      console.error('Failed to add to blacklist:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Remove email from blacklist
   *
   * DELETE /api/v1/platform-admin/blacklist/:email
   *
   * Error responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 404: Email not found in blacklist
   */
  async function removeFromBlacklist(email: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      await apiClient.delete(`/platform-admin/blacklist/${encodeURIComponent(email)}`)

      // Remove from local state
      blacklist.value = blacklist.value.filter((entry) => entry.email !== email)
    } catch (err) {
      const apiError = err as ApiError
      error.value = apiError.body?.detail || 'Failed to remove from blacklist'
      console.error('Failed to remove from blacklist:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    pendingInvitations,
    workspaces,
    blacklist,
    loading,
    error,

    // Methods - Invitations
    fetchPendingInvitations,
    inviteTherapist,
    resendInvitation,

    // Methods - Workspaces
    fetchWorkspaces,
    suspendWorkspace,
    reactivateWorkspace,
    deleteWorkspace,

    // Methods - Blacklist
    fetchBlacklist,
    addToBlacklist,
    removeFromBlacklist,

    // Utilities
    clearError,
  }
}
