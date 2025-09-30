import axios, { type AxiosInstance } from 'axios'
import type { paths } from './schema'

/**
 * API Client for PazPaz backend
 *
 * Provides typed axios client for all API endpoints.
 * Automatically includes workspace ID in headers for authentication.
 *
 * Usage:
 *   import apiClient from '@/api/client'
 *   const response = await apiClient.get('/api/v1/clients')
 */

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
 * Request interceptor
 * Adds workspace ID to all requests
 * TODO: Replace hardcoded workspace ID with real auth when implemented
 */
apiClient.interceptors.request.use(
  (config) => {
    // TODO: Get workspace ID from auth store/context
    // For now, use test workspace ID
    config.headers['X-Workspace-ID'] = '00000000-0000-0000-0000-000000000001'
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

/**
 * Response interceptor
 * Handles common error cases
 */
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // Handle common HTTP errors
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // TODO: Redirect to login or refresh token
          console.error('Unauthorized - authentication required')
          break
        case 403:
          console.error('Forbidden - insufficient permissions')
          break
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

export default apiClient
