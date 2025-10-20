import axios, { type AxiosInstance, type AxiosResponse, type AxiosError } from 'axios'
import type { paths } from './schema'

/**
 * API Client for PazPaz backend
 *
 * Provides typed axios client for all API endpoints.
 * Automatically includes workspace ID in headers for authentication.
 * Extracts request_id from responses for debugging and support.
 *
 * Usage:
 *   import apiClient from '@/api/client'
 *   const response = await apiClient.get('/clients')  // baseURL already includes /api/v1
 */

// Extend AxiosResponse and AxiosError to include requestId
declare module 'axios' {
  export interface AxiosResponse {
    requestId?: string
  }
  export interface AxiosError {
    requestId?: string
  }
}

// Create axios instance with default configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies for session-based auth
  timeout: 10000, // 10 second timeout
})

/**
 * Helper function to get CSRF token from cookie
 */
function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrf_token=([^;]+)/)
  return match?.[1] ?? null
}

/**
 * Request interceptor
 * Adds workspace ID and CSRF token to all requests
 * TODO: Replace hardcoded workspace ID with real auth when implemented
 */
apiClient.interceptors.request.use(
  (config) => {
    // TODO: Get workspace ID from auth store/context
    // For now, use test workspace ID
    config.headers['X-Workspace-ID'] = '00000000-0000-0000-0000-000000000001'

    // Add CSRF token for state-changing requests (POST, PUT, PATCH, DELETE)
    if (
      config.method &&
      ['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())
    ) {
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
      } else {
        console.warn('CSRF token not found in cookies for state-changing request')
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

/**
 * Response interceptor
 * Extracts request_id and handles common error cases
 */
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Extract request_id from successful responses
    const requestId =
      response.data?.request_id || response.headers?.['x-request-id'] || null

    if (requestId) {
      response.requestId = requestId
      // Log successful requests with request_id in development
      if (import.meta.env.DEV) {
        console.debug(
          `[API Success] ${response.config.method?.toUpperCase()} ${response.config.url} - Request ID: ${requestId}`
        )
      }
    }

    return response
  },
  (error: AxiosError) => {
    // Extract request_id from error responses
    const errorData = error.response?.data as { request_id?: string } | undefined
    const requestId =
      errorData?.request_id || error.response?.headers?.['x-request-id'] || null

    if (requestId) {
      error.requestId = requestId
      console.error(`[API Error] Request ID: ${requestId}`, {
        method: error.config?.method?.toUpperCase(),
        url: error.config?.url,
        status: error.response?.status,
        statusText: error.response?.statusText,
      })
    } else {
      console.error('[API Error] No request ID available', {
        method: error.config?.method?.toUpperCase(),
        url: error.config?.url,
        message: error.message,
      })
    }

    // Handle common HTTP errors
    if (error.response) {
      switch (error.response.status) {
        case 401: {
          // Session expired or invalid - trigger automatic logout
          const currentPath = window.location.pathname

          // Avoid infinite loops - don't redirect if already on auth pages
          const isAuthPage =
            currentPath === '/login' || currentPath.startsWith('/auth/')

          if (!isAuthPage) {
            console.warn('[API] 401 Unauthorized - Session expired, logging out')

            // Dynamically import auth store to avoid circular dependencies
            import('@/stores/auth').then(async ({ useAuthStore }) => {
              const authStore = useAuthStore()

              // Only logout if user thinks they're authenticated
              if (authStore.isAuthenticated) {
                await authStore.logout()

                // Dynamically import router to avoid circular dependencies
                const { router } = await import('@/router')

                // Redirect to login with session expired message
                router.push({
                  path: '/login',
                  query: {
                    redirect: currentPath,
                    message: 'session_expired',
                  },
                })
              } else {
                // User not authenticated, just redirect to login
                const { router } = await import('@/router')
                router.push({
                  path: '/login',
                  query: { redirect: currentPath },
                })
              }
            })
          }
          break
        }
        case 403: {
          const forbiddenData = error.response.data as { detail?: string } | undefined
          const detail = forbiddenData?.detail || ''
          if (detail.toLowerCase().includes('csrf')) {
            console.error(
              '[API] CSRF token validation failed - Please refresh the page'
            )
          } else {
            console.error('Forbidden - insufficient permissions')
          }
          break
        }
        case 404:
          console.error('Resource not found')
          break
        case 422:
          console.error('Validation error:', error.response.data)
          break
        case 500:
          console.error('Server error')
          break
        default:
          console.error('API error:', error.response.status)
      }
    } else if (error.request) {
      console.error('Network error - no response received')
    } else {
      console.error('Request error:', error.message)
    }
    return Promise.reject(error)
  }
)

// Type-safe API client methods
export type ApiClient = AxiosInstance

// Export typed paths for type-safe API calls
export type ApiPaths = paths

/**
 * Conflict detection API
 */
export interface ConflictCheckParams {
  scheduled_start: string
  scheduled_end: string
  exclude_appointment_id?: string
}

export interface ConflictingAppointment {
  id: string
  scheduled_start: string
  scheduled_end: string
  client_initials: string
  location_type: 'clinic' | 'home' | 'online'
  status: 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show'
}

export interface ConflictCheckResponse {
  has_conflict: boolean
  conflicting_appointments: ConflictingAppointment[]
}

/**
 * Check for appointment conflicts in a time range
 *
 * @param params - Conflict check parameters
 * @returns Promise<ConflictCheckResponse>
 * @throws Error if API call fails
 */
export const checkAppointmentConflicts = async (
  params: ConflictCheckParams
): Promise<ConflictCheckResponse> => {
  const queryParams = new URLSearchParams({
    scheduled_start: params.scheduled_start,
    scheduled_end: params.scheduled_end,
  })

  if (params.exclude_appointment_id) {
    queryParams.append('exclude_appointment_id', params.exclude_appointment_id)
  }

  const response = await apiClient.get<ConflictCheckResponse>(
    `/appointments/conflicts?${queryParams.toString()}`
  )

  return response.data
}

export default apiClient
