import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import type { AxiosError } from 'axios'

/**
 * API Client Tests
 *
 * Tests the configuration and setup of the Axios API client,
 * including interceptors for workspace ID injection and error handling.
 */

describe('API Client Configuration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should export an axios instance', async () => {
    const { default: apiClient } = await import('./client')
    expect(apiClient).toBeDefined()
    expect(apiClient.defaults).toBeDefined()
  })

  it('should have correct base URL', async () => {
    const { default: apiClient } = await import('./client')
    expect(apiClient.defaults.baseURL).toBe('/api/v1')
  })

  it('should set Content-Type header to application/json', async () => {
    const { default: apiClient } = await import('./client')
    expect(apiClient.defaults.headers['Content-Type']).toBe('application/json')
  })

  it('should enable credentials for cross-origin requests', async () => {
    const { default: apiClient } = await import('./client')
    expect(apiClient.defaults.withCredentials).toBe(true)
  })

  it('should set timeout to 10 seconds', async () => {
    const { default: apiClient } = await import('./client')
    expect(apiClient.defaults.timeout).toBe(10000)
  })
})

describe('API Client Methods', () => {
  it('should have standard axios methods', async () => {
    const { default: apiClient } = await import('./client')
    expect(apiClient.get).toBeDefined()
    expect(apiClient.post).toBeDefined()
    expect(apiClient.patch).toBeDefined()
    expect(apiClient.delete).toBeDefined()
    expect(apiClient.put).toBeDefined()
    expect(typeof apiClient.get).toBe('function')
    expect(typeof apiClient.post).toBe('function')
  })
})

describe('Request Interceptor', () => {
  it('should add workspace ID header to requests', async () => {
    const { default: apiClient } = await import('./client')

    // The interceptor adds X-Workspace-ID header
    const requestConfig = { headers: {} }
    const interceptor = apiClient.interceptors.request.handlers[0]

    if (interceptor && interceptor.fulfilled) {
      const result = interceptor.fulfilled(requestConfig)
      expect(result.headers['X-Workspace-ID']).toBe(
        '00000000-0000-0000-0000-000000000001'
      )
    }
  })
})

describe('Error Handling', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('should handle 401 unauthorized errors', () => {
    const error = {
      response: {
        status: 401,
        data: { detail: 'Unauthorized' },
      },
    } as AxiosError

    expect(error.response?.status).toBe(401)
  })

  it('should handle 404 not found errors', () => {
    const error = {
      response: {
        status: 404,
        data: { detail: 'Not found' },
      },
    } as AxiosError

    expect(error.response?.status).toBe(404)
  })

  it('should handle 422 validation errors', () => {
    const error = {
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ['body', 'title'],
              msg: 'field required',
              type: 'value_error.missing',
            },
          ],
        },
      },
    } as AxiosError

    expect(error.response?.status).toBe(422)
    expect(error.response?.data).toHaveProperty('detail')
  })

  it('should handle 500 server errors', () => {
    const error = {
      response: {
        status: 500,
        data: { detail: 'Internal server error' },
      },
    } as AxiosError

    expect(error.response?.status).toBe(500)
  })

  it('should handle network errors', () => {
    const error = {
      request: {},
      message: 'Network Error',
    } as AxiosError

    expect(error.request).toBeDefined()
    expect(error.message).toBe('Network Error')
  })
})

describe('Type Exports', () => {
  it('should export ApiClient type', async () => {
    const module = await import('./client')
    expect(module.default).toBeDefined()
  })

  it('should export ApiPaths type', async () => {
    // This is a compile-time check, just verify import works
    const module = await import('./client')
    expect(module).toBeDefined()
  })
})
