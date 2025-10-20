import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { usePreviousSession } from './usePreviousSession'
import apiClient from '@/api/client'
import type { SessionResponse } from '@/types/sessions'

// Mock the API client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('usePreviousSession', () => {
  // Spy on console methods to verify no console.log pollution
  let consoleLogSpy: ReturnType<typeof vi.spyOn>
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.clearAllMocks()
    // Spy on console methods
    consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleLogSpy.mockRestore()
    consoleErrorSpy.mockRestore()
  })

  describe('fetchLatestFinalized', () => {
    it('should fetch and return latest finalized session', async () => {
      const mockSession: SessionResponse = {
        id: 'session-123',
        client_id: 'client-456',
        workspace_id: 'workspace-789',
        is_draft: false,
        session_date: '2025-10-20',
        finalized_at: '2025-10-20T10:00:00Z',
        created_at: '2025-10-20T09:00:00Z',
        updated_at: '2025-10-20T10:00:00Z',
        subjective: 'Patient reports improvement',
        objective: 'ROM increased by 10 degrees',
        assessment: 'Progressing well',
        plan: 'Continue current treatment',
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockSession })

      const { fetchLatestFinalized, session, loading, error, notFound } =
        usePreviousSession()

      expect(loading.value).toBe(false)
      expect(session.value).toBe(null)

      const result = await fetchLatestFinalized('client-456')

      expect(apiClient.get).toHaveBeenCalledWith(
        '/sessions/clients/client-456/latest-finalized'
      )
      expect(result).toEqual(mockSession)
      expect(session.value).toEqual(mockSession)
      expect(loading.value).toBe(false)
      expect(error.value).toBe(null)
      expect(notFound.value).toBe(false)

      // HIPAA Compliance: Verify no console.log was called (PHI protection)
      expect(consoleLogSpy).not.toHaveBeenCalled()
    })

    it('should start in loading state if startLoading is true', () => {
      const { loading } = usePreviousSession(true)
      expect(loading.value).toBe(true)
    })

    it('should handle 404 not found gracefully', async () => {
      const axiosError = {
        response: {
          status: 404,
          data: { detail: 'No finalized sessions found' },
        },
      }

      vi.mocked(apiClient.get).mockRejectedValueOnce(axiosError)

      const { fetchLatestFinalized, session, error, notFound } = usePreviousSession()

      const result = await fetchLatestFinalized('client-456')

      expect(result).toBe(null)
      expect(session.value).toBe(null)
      expect(error.value).toBe(null)
      expect(notFound.value).toBe(true)

      // Error handling should still use console.error (allowed for debugging)
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to load previous session:',
        expect.objectContaining({
          status: 404,
          clientId: 'client-456',
        })
      )

      // HIPAA Compliance: Verify no console.log was called
      expect(consoleLogSpy).not.toHaveBeenCalled()
    })

    it('should handle 403 forbidden error', async () => {
      const axiosError = {
        response: {
          status: 403,
          data: { detail: 'Client not in workspace' },
        },
      }

      vi.mocked(apiClient.get).mockRejectedValueOnce(axiosError)

      const { fetchLatestFinalized, error } = usePreviousSession()

      await fetchLatestFinalized('client-456')

      expect(error.value).toBe('Client not in workspace')

      // console.error should be called for error tracking
      expect(consoleErrorSpy).toHaveBeenCalled()
      // HIPAA Compliance: Verify no console.log was called
      expect(consoleLogSpy).not.toHaveBeenCalled()
    })

    it('should handle generic errors', async () => {
      const axiosError = {
        response: {
          status: 500,
          data: { detail: 'Internal server error' },
        },
      }

      vi.mocked(apiClient.get).mockRejectedValueOnce(axiosError)

      const { fetchLatestFinalized, error } = usePreviousSession()

      await fetchLatestFinalized('client-456')

      expect(error.value).toBe('Internal server error')

      // console.error should be called for error tracking
      expect(consoleErrorSpy).toHaveBeenCalled()
      // HIPAA Compliance: Verify no console.log was called
      expect(consoleLogSpy).not.toHaveBeenCalled()
    })

    it('should handle errors without detail message', async () => {
      const axiosError = {
        response: {
          status: 500,
          data: {},
        },
      }

      vi.mocked(apiClient.get).mockRejectedValueOnce(axiosError)

      const { fetchLatestFinalized, error } = usePreviousSession()

      await fetchLatestFinalized('client-456')

      expect(error.value).toBe('Failed to fetch previous session')
    })

    it('should reset state before fetching', async () => {
      const mockSession: SessionResponse = {
        id: 'session-123',
        client_id: 'client-456',
        workspace_id: 'workspace-789',
        is_draft: false,
        session_date: '2025-10-20',
        finalized_at: '2025-10-20T10:00:00Z',
        created_at: '2025-10-20T09:00:00Z',
        updated_at: '2025-10-20T10:00:00Z',
        subjective: 'Test',
        objective: 'Test',
        assessment: 'Test',
        plan: 'Test',
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockSession })

      const { fetchLatestFinalized, session, error, notFound } = usePreviousSession()

      // Set some initial state
      session.value = mockSession
      error.value = 'Previous error'
      notFound.value = true

      await fetchLatestFinalized('client-789')

      // State should be reset during fetch
      expect(error.value).toBe(null)
      expect(notFound.value).toBe(false)
    })
  })

  describe('reset', () => {
    it('should reset all state', async () => {
      const mockSession: SessionResponse = {
        id: 'session-123',
        client_id: 'client-456',
        workspace_id: 'workspace-789',
        is_draft: false,
        session_date: '2025-10-20',
        finalized_at: '2025-10-20T10:00:00Z',
        created_at: '2025-10-20T09:00:00Z',
        updated_at: '2025-10-20T10:00:00Z',
        subjective: 'Test',
        objective: 'Test',
        assessment: 'Test',
        plan: 'Test',
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockSession })

      const { fetchLatestFinalized, session, loading, error, notFound, reset } =
        usePreviousSession()

      await fetchLatestFinalized('client-456')

      expect(session.value).toEqual(mockSession)

      reset()

      expect(loading.value).toBe(false)
      expect(session.value).toBe(null)
      expect(error.value).toBe(null)
      expect(notFound.value).toBe(false)
    })
  })

  describe('HIPAA Compliance - Console Logging', () => {
    it('should never call console.log even on successful fetch', async () => {
      const mockSession: SessionResponse = {
        id: 'session-123',
        client_id: 'client-456',
        workspace_id: 'workspace-789',
        is_draft: false,
        session_date: '2025-10-20',
        finalized_at: '2025-10-20T10:00:00Z',
        created_at: '2025-10-20T09:00:00Z',
        updated_at: '2025-10-20T10:00:00Z',
        subjective: 'Patient reports improvement',
        objective: 'ROM increased by 10 degrees',
        assessment: 'Progressing well',
        plan: 'Continue current treatment',
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockSession })

      const { fetchLatestFinalized } = usePreviousSession()

      await fetchLatestFinalized('client-456')

      // Critical: Verify no console.log calls (could expose PHI)
      expect(consoleLogSpy).not.toHaveBeenCalled()
    })

    it('should allow console.error for legitimate error handling', async () => {
      const axiosError = {
        response: {
          status: 500,
          data: { detail: 'Internal server error' },
        },
      }

      vi.mocked(apiClient.get).mockRejectedValueOnce(axiosError)

      const { fetchLatestFinalized } = usePreviousSession()

      await fetchLatestFinalized('client-456')

      // console.error is allowed and should be called for error tracking
      expect(consoleErrorSpy).toHaveBeenCalled()
      // But console.log should never be called
      expect(consoleLogSpy).not.toHaveBeenCalled()
    })
  })
})
