/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { PendingInvitation } from './PendingInvitation'
/**
 * Response schema for listing pending invitations.
 *
 * Example:
 * ```json
 * {
 * "invitations": [
 * {
 * "user_id": "987e6543-e21b-34c5-b678-123456789012",
 * "email": "sarah@example.com",
 * "full_name": "Sarah Chen",
 * "workspace_name": "Sarah's Massage Therapy",
 * "invited_at": "2025-10-15T10:30:00Z",
 * "expires_at": "2025-10-22T10:30:00Z"
 * }
 * ]
 * }
 * ```
 */
export type PendingInvitationsResponse = {
  /**
   * List of pending invitations (not yet accepted)
   */
  invitations?: Array<PendingInvitation>
}
