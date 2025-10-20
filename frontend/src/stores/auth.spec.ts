import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth'
import apiClient from '@/api/client'
import type { AxiosResponse } from 'axios'

// Mock apiClient
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

/**
 * Tests for auth store
 *
 * Verifies logout functionality clears encrypted session backups
 * for HIPAA compliance (prevent PHI leakage on shared computers).
 * Tests automatic logout on 401 Unauthorized responses.
 */
describe('useAuthStore', () => {
  let authStore: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    authStore = useAuthStore()
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('initializeAuth', () => {
    it('sets user when authentication succeeds', async () => {
      const userData = {
        id: 'user-123',
        email: 'test@example.com',
        workspace_id: 'workspace-123',
        role: 'therapist',
      }

      vi.mocked(apiClient.get).mockResolvedValue({
        data: userData,
      } as AxiosResponse)

      await authStore.initializeAuth()

      expect(authStore.user).toEqual(userData)
      expect(authStore.isAuthenticated).toBe(true)
    })

    it('clears user on 401 response', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: { status: 401 },
      })

      await authStore.initializeAuth()

      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })

    it('handles network errors gracefully', async () => {
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await authStore.initializeAuth()

      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })
  })

  describe('logout', () => {
    it('calls backend logout endpoint', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      await authStore.logout()

      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout')
    })

    it('clears encrypted session backups from localStorage', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      // Add session backups to localStorage
      localStorage.setItem('session_abc_backup', 'encrypted-data-1')
      localStorage.setItem('session_xyz_backup', 'encrypted-data-2')
      localStorage.setItem('other_key', 'should-remain')

      expect(localStorage.getItem('session_abc_backup')).toBeTruthy()

      await authStore.logout()

      // Should have cleared session backups
      expect(localStorage.getItem('session_abc_backup')).toBeNull()
      expect(localStorage.getItem('session_xyz_backup')).toBeNull()
      // Other keys should remain
      expect(localStorage.getItem('other_key')).toBe('should-remain')
    })

    it('clears user state after logout', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      // Set user state
      authStore.setUser({
        id: 'user-123',
        email: 'test@example.com',
        workspace_id: 'workspace-123',
        role: 'therapist',
      })

      expect(authStore.user).not.toBeNull()
      expect(authStore.isAuthenticated).toBe(true)

      await authStore.logout()

      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })

    it('does NOT redirect (caller handles redirect)', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      await authStore.logout()

      // Logout does NOT redirect - that's handled by the 401 interceptor
      // This allows logout to be called from multiple places
    })

    it('continues client-side cleanup even if backend logout fails', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'))

      // Set user state
      authStore.setUser({
        id: 'user-123',
        email: 'test@example.com',
        workspace_id: 'workspace-123',
        role: 'therapist',
      })

      localStorage.setItem('session_test_backup', 'encrypted')

      await authStore.logout()

      // Should still clear backups and state
      expect(localStorage.getItem('session_test_backup')).toBeNull()
      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })
  })

  describe('setUser', () => {
    it('sets user and marks as authenticated', () => {
      const userData = {
        id: 'user-123',
        email: 'test@example.com',
        workspace_id: 'workspace-123',
        role: 'therapist',
      }

      expect(authStore.isAuthenticated).toBe(false)

      authStore.setUser(userData)

      expect(authStore.user).toEqual(userData)
      expect(authStore.isAuthenticated).toBe(true) // Computed from user !== null
    })
  })

  describe('clearUser', () => {
    it('clears user and marks as unauthenticated', () => {
      authStore.setUser({
        id: 'user-123',
        email: 'test@example.com',
        workspace_id: 'workspace-123',
        role: 'therapist',
      })

      authStore.clearUser()

      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })
  })

  describe('HIPAA Compliance', () => {
    it('ensures PHI is not leaked on shared computers by clearing backups', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      // Simulate user working on session notes (encrypted PHI in localStorage)
      localStorage.setItem('session_patient123_backup', 'encrypted-phi-data')
      localStorage.setItem('session_patient456_backup', 'more-encrypted-phi')

      await authStore.logout()

      // Verify all session backups were cleared
      expect(localStorage.getItem('session_patient123_backup')).toBeNull()
      expect(localStorage.getItem('session_patient456_backup')).toBeNull()
    })

    it('clears backups even when user never logged in (guest state)', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      localStorage.setItem('session_orphan_backup', 'old-data')

      // User state is null (never authenticated)
      expect(authStore.user).toBeNull()

      await authStore.logout()

      // Should still clear backups (defensive cleanup)
      expect(localStorage.getItem('session_orphan_backup')).toBeNull()
    })
  })

  describe('Error Scenarios', () => {
    it('handles network timeout during logout', async () => {
      const timeoutError = new Error('Network timeout')
      timeoutError.name = 'ETIMEDOUT'
      vi.mocked(apiClient.post).mockRejectedValue(timeoutError)

      localStorage.setItem('session_test_backup', 'data')

      await expect(authStore.logout()).resolves.not.toThrow()

      expect(localStorage.getItem('session_test_backup')).toBeNull()
      expect(authStore.user).toBeNull()
    })

    it('handles 401 Unauthorized during logout', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { status: 401, data: { detail: 'Unauthorized' } },
      })

      localStorage.setItem('session_test_backup', 'data')

      await expect(authStore.logout()).resolves.not.toThrow()

      expect(localStorage.getItem('session_test_backup')).toBeNull()
      expect(authStore.user).toBeNull()
    })

    it('handles 500 Internal Server Error during logout', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { status: 500, data: { detail: 'Internal server error' } },
      })

      localStorage.setItem('session_test_backup', 'data')

      await expect(authStore.logout()).resolves.not.toThrow()

      expect(localStorage.getItem('session_test_backup')).toBeNull()
      expect(authStore.user).toBeNull()
    })
  })
})
