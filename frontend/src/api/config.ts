/**
 * API Client Configuration
 *
 * Configures the auto-generated OpenAPI client to:
 * - Use the correct base URL
 * - Include credentials (cookies) in requests
 * - Add CSRF tokens to state-changing requests
 *
 * NOTE: The generated OpenAPI client creates its own axios instance,
 * so it doesn't benefit from the interceptors in client.ts.
 * We configure it here to match the same CSRF protection behavior.
 */

import { OpenAPI } from './generated/index'
import { getCsrfToken } from './client'

// Configure the generated API client
export function configureApiClient() {
  // Set base URL to empty string since generated paths already include /api/v1
  // The generated service paths are like: '/api/v1/platform-admin/invite-therapist'
  OpenAPI.BASE = ''

  // Include credentials (cookies) in all requests for session-based auth
  OpenAPI.WITH_CREDENTIALS = true
  OpenAPI.CREDENTIALS = 'include'

  // Add CSRF token header for state-changing requests
  OpenAPI.HEADERS = async () => {
    const headers: Record<string, string> = {}

    // Add CSRF token for POST/PUT/PATCH/DELETE requests
    // The generated client will call this function for each request
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken
    }

    return headers
  }
}
