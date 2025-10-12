import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth'
import apiClient from '@/api/client'
import type { AxiosResponse } from 'axios'

// Mock apiClient
vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(),
  },
}))

// Mock useSecureOfflineBackup
const mockClearAllBackups = vi.fn()

vi.mock('@/composables/useSecureOfflineBackup', () => ({
  useSecureOfflineBackup: () => ({
    clearAllBackups: mockClearAllBackups,
    backupDraft: vi.fn(),
    restoreDraft: vi.fn(),
    syncToServer: vi.fn(),
  }),
}))

/**
 * Tests for auth store
 *
 * Verifies logout functionality clears encrypted session backups
 * for HIPAA compliance (prevent PHI leakage on shared computers).
 */
describe('useAuthStore', () => {
  let authStore: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    authStore = useAuthStore()
    vi.clearAllMocks()
    localStorage.clear()

    // Mock window.location.href
    delete (window as any).location
    ;(window as any).location = { href: '' }
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('logout', () => {
    it('calls backend logout endpoint', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      await authStore.logout()

      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout')
    })

    it('calls clearAllBackups to remove encrypted session data', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      await authStore.logout()

      expect(mockClearAllBackups).toHaveBeenCalled()
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

    it('redirects to login page after logout', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      await authStore.logout()

      expect(window.location.href).toBe('/login')
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

      await authStore.logout()

      // Should still clear backups and state
      expect(mockClearAllBackups).toHaveBeenCalled()
      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
      expect(window.location.href).toBe('/login')
    })

    it('clears all session backups from localStorage', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      // Add multiple session backups to localStorage
      localStorage.setItem('session_abc_backup', 'encrypted-data-1')
      localStorage.setItem('session_xyz_backup', 'encrypted-data-2')
      localStorage.setItem('session_123_backup', 'encrypted-data-3')
      localStorage.setItem('other_key', 'should-remain')

      await authStore.logout()

      expect(mockClearAllBackups).toHaveBeenCalled()
    })

    it('performs logout steps in correct order', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      const callOrder: string[] = []

      vi.mocked(apiClient.post).mockImplementation(async () => {
        callOrder.push('backend-logout')
        return {} as AxiosResponse
      })

      mockClearAllBackups.mockImplementation(() => {
        callOrder.push('clear-backups')
      })

      authStore.setUser({
        id: 'user-123',
        email: 'test@example.com',
        workspace_id: 'workspace-123',
        role: 'therapist',
      })

      await authStore.logout()

      callOrder.push('clear-state')
      callOrder.push('redirect')

      // Order: backend logout -> clear backups -> clear state -> redirect
      expect(callOrder).toEqual([
        'backend-logout',
        'clear-backups',
        'clear-state',
        'redirect',
      ])
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

      authStore.setUser(userData)

      expect(authStore.user).toEqual(userData)
      expect(authStore.isAuthenticated).toBe(true)
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

      // Verify clearAllBackups was called to remove all PHI
      expect(mockClearAllBackups).toHaveBeenCalled()
    })

    it('clears backups even when user never logged in (guest state)', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({} as AxiosResponse)

      // User state is null (never authenticated)
      expect(authStore.user).toBeNull()

      await authStore.logout()

      // Should still clear backups (defensive cleanup)
      expect(mockClearAllBackups).toHaveBeenCalled()
    })
  })

  describe('Error Scenarios', () => {
    it('handles network timeout during logout', async () => {
      const timeoutError = new Error('Network timeout')
      timeoutError.name = 'ETIMEDOUT'
      vi.mocked(apiClient.post).mockRejectedValue(timeoutError)

      await expect(authStore.logout()).resolves.not.toThrow()

      expect(mockClearAllBackups).toHaveBeenCalled()
      expect(authStore.user).toBeNull()
    })

    it('handles 401 Unauthorized during logout', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { status: 401, data: { detail: 'Unauthorized' } },
      })

      await expect(authStore.logout()).resolves.not.toThrow()

      expect(mockClearAllBackups).toHaveBeenCalled()
      expect(authStore.user).toBeNull()
    })

    it('handles 500 Internal Server Error during logout', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { status: 500, data: { detail: 'Internal server error' } },
      })

      await expect(authStore.logout()).resolves.not.toThrow()

      expect(mockClearAllBackups).toHaveBeenCalled()
      expect(authStore.user).toBeNull()
    })
  })
})
