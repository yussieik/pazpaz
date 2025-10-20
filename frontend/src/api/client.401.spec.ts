import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

/**
 * 401 Unauthorized Response Handling Tests
 *
 * Tests automatic logout and redirect when API returns 401 Unauthorized.
 * Ensures users are not left in broken session state.
 *
 * Key scenarios:
 * - Auto-logout on 401 (when authenticated)
 * - Redirect to login with session_expired message
 * - Clear encrypted backups on logout
 * - Extract and log request_id from error responses
 * - Prevent redirect loops (already on login page)
 */

// Mock the auth store
const mockLogout = vi.fn()
const mockUseAuthStore = vi.fn(() => ({
  isAuthenticated: true,
  user: {
    id: '123',
    email: 'test@example.com',
    workspace_id: 'ws-123',
    role: 'therapist',
  },
  logout: mockLogout,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: mockUseAuthStore,
}))

// Mock the router
const mockRouterPush = vi.fn()
vi.mock('@/router', () => ({
  router: {
    push: mockRouterPush,
  },
}))

describe('401 Unauthorized Handling', () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let apiClient: any
  let consoleWarnSpy: ReturnType<typeof vi.spyOn>
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    // Reset window.location
    Object.defineProperty(window, 'location', {
      value: { pathname: '/clients' },
      writable: true,
      configurable: true,
    })

    // Dynamically import apiClient to get fresh instance
    const module = await import('./client')
    apiClient = module.default
  })

  afterEach(() => {
    consoleWarnSpy.mockRestore()
    consoleErrorSpy.mockRestore()
  })

  describe('Automatic Logout on 401', () => {
    it('logs out user when 401 response received', async () => {
      mockUseAuthStore.mockReturnValue({
        isAuthenticated: true,
        user: { id: '123', email: 'test@example.com', workspace_id: 'ws-123' },
        logout: mockLogout,
      })

      const error = {
        response: {
          status: 401,
          data: { detail: 'Invalid authentication credentials' },
          headers: {},
        },
        config: {
          url: '/some-endpoint',
          method: 'get',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      // Trigger the response interceptor's error handler
      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch {
          // Expected to reject
        }
      }

      // Give dynamic import time to resolve
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should have called logout
      expect(mockLogout).toHaveBeenCalled()
    })

    it('does not logout if user is not authenticated', async () => {
      mockUseAuthStore.mockReturnValue({
        isAuthenticated: false,
        user: null,
        logout: mockLogout,
      })

      const error = {
        response: {
          status: 401,
          data: {},
          headers: {},
        },
        config: {
          url: '/some-endpoint',
          method: 'get',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should still redirect but not call logout
      expect(mockLogout).not.toHaveBeenCalled()
      expect(mockRouterPush).toHaveBeenCalledWith({
        path: '/login',
        query: { redirect: '/clients' },
      })
    })
  })

  describe('Redirect to Login', () => {
    it('redirects to login with session_expired message', async () => {
      mockUseAuthStore.mockReturnValue({
        isAuthenticated: true,
        user: { id: '123', email: 'test@example.com', workspace_id: 'ws-123' },
        logout: mockLogout,
      })

      Object.defineProperty(window, 'location', {
        value: { pathname: '/clients' },
        writable: true,
        configurable: true,
      })

      const error = {
        response: {
          status: 401,
          data: {},
          headers: {},
        },
        config: {
          url: '/clients',
          method: 'get',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(mockRouterPush).toHaveBeenCalledWith({
        path: '/login',
        query: {
          redirect: '/clients',
          message: 'session_expired',
        },
      })
    })

    it('preserves current path in redirect query', async () => {
      mockUseAuthStore.mockReturnValue({
        isAuthenticated: true,
        user: { id: '123', email: 'test@example.com', workspace_id: 'ws-123' },
        logout: mockLogout,
      })

      Object.defineProperty(window, 'location', {
        value: { pathname: '/sessions/abc-123' },
        writable: true,
        configurable: true,
      })

      const error = {
        response: {
          status: 401,
          data: {},
          headers: {},
        },
        config: {
          url: '/sessions/abc-123',
          method: 'get',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(mockRouterPush).toHaveBeenCalledWith({
        path: '/login',
        query: {
          redirect: '/sessions/abc-123',
          message: 'session_expired',
        },
      })
    })
  })

  describe('Prevent Redirect Loops', () => {
    it('does not redirect if already on /login', async () => {
      Object.defineProperty(window, 'location', {
        value: { pathname: '/login' },
        writable: true,
        configurable: true,
      })

      const error = {
        response: {
          status: 401,
          data: {},
          headers: {},
        },
        config: {
          url: '/auth/magic-link',
          method: 'post',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should not redirect (already on login)
      expect(mockRouterPush).not.toHaveBeenCalled()
      expect(mockLogout).not.toHaveBeenCalled()
    })

    it('does not redirect if on /auth/* pages', async () => {
      Object.defineProperty(window, 'location', {
        value: { pathname: '/auth/verify' },
        writable: true,
        configurable: true,
      })

      const error = {
        response: {
          status: 401,
          data: {},
          headers: {},
        },
        config: {
          url: '/auth/verify',
          method: 'post',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should not redirect (already on auth page)
      expect(mockRouterPush).not.toHaveBeenCalled()
      expect(mockLogout).not.toHaveBeenCalled()
    })
  })

  describe('Request ID Extraction', () => {
    it('extracts request_id from error response data', async () => {
      const error = {
        response: {
          status: 401,
          data: { request_id: 'req-abc-123', detail: 'Unauthorized' },
          headers: {},
        },
        config: {
          url: '/clients',
          method: 'get',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err: unknown) {
          // Should have requestId attached
          expect((err as { requestId?: string }).requestId).toBe('req-abc-123')
        }
      }

      // Should log error with request ID
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[API Error] Request ID: req-abc-123',
        expect.any(Object)
      )
    })

    it('extracts request_id from response headers', async () => {
      const error = {
        response: {
          status: 401,
          data: {},
          headers: { 'x-request-id': 'req-xyz-456' },
        },
        config: {
          url: '/appointments',
          method: 'get',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err: unknown) {
          expect((err as { requestId?: string }).requestId).toBe('req-xyz-456')
        }
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[API Error] Request ID: req-xyz-456',
        expect.any(Object)
      )
    })

    it('prioritizes data.request_id over header', async () => {
      const error = {
        response: {
          status: 401,
          data: { request_id: 'req-from-data' },
          headers: { 'x-request-id': 'req-from-header' },
        },
        config: {
          url: '/sessions',
          method: 'patch',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err: unknown) {
          expect((err as { requestId?: string }).requestId).toBe('req-from-data')
        }
      }
    })
  })

  describe('Console Logging', () => {
    it('logs warning message on 401', async () => {
      mockUseAuthStore.mockReturnValue({
        isAuthenticated: true,
        user: { id: '123', email: 'test@example.com', workspace_id: 'ws-123' },
        logout: mockLogout,
      })

      Object.defineProperty(window, 'location', {
        value: { pathname: '/clients' },
        writable: true,
        configurable: true,
      })

      const error = {
        response: {
          status: 401,
          data: {},
          headers: {},
        },
        config: {
          url: '/clients',
          method: 'get',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        '[API] 401 Unauthorized - Session expired, logging out'
      )
    })
  })

  describe('CSRF 403 Handling', () => {
    it('logs specific message for CSRF validation failures', async () => {
      const error = {
        response: {
          status: 403,
          data: { detail: 'CSRF token validation failed' },
          headers: {},
        },
        config: {
          url: '/clients',
          method: 'post',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[API] CSRF token validation failed - Please refresh the page'
      )
    })

    it('handles generic 403 errors', async () => {
      const error = {
        response: {
          status: 403,
          data: { detail: 'Insufficient permissions' },
          headers: {},
        },
        config: {
          url: '/admin/settings',
          method: 'patch',
        } as InternalAxiosRequestConfig,
      } as AxiosError

      const interceptor = apiClient.interceptors.response.handlers[0]
      if (interceptor && interceptor.rejected) {
        try {
          await interceptor.rejected(error)
        } catch (err) {
          // Expected
        }
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Forbidden - insufficient permissions'
      )
    })
  })
})
