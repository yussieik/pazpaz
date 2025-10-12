import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useSecureOfflineBackup } from './useSecureOfflineBackup'
import apiClient from '@/api/client'
import type { AxiosResponse } from 'axios'

// Mock apiClient
vi.mock('@/api/client', () => ({
  default: {
    patch: vi.fn(),
  },
}))

/**
 * Tests for useSecureOfflineBackup composable
 *
 * Verifies encryption/decryption functionality, TTL enforcement,
 * localStorage persistence, and error handling for offline SOAP notes backup.
 */
describe('useSecureOfflineBackup', () => {
  const mockSessionId = 'session-123'
  const mockJwtToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'

  const mockDraft = {
    subjective: 'Patient reports shoulder pain',
    objective: 'ROM: 120° abduction',
    assessment: 'Rotator cuff tendinitis',
    plan: 'Ice 15min 3x/day',
    session_date: '2025-10-12T10:00:00Z',
    duration_minutes: 60,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()

    // Mock document.cookie for JWT token
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: `access_token=${mockJwtToken}`,
    })
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('Encryption and Decryption', () => {
    it('encrypts and decrypts draft data correctly', async () => {
      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      // Backup encrypted draft
      await backupDraft(mockSessionId, mockDraft, 1)

      // Verify localStorage contains encrypted data
      const storedItem = localStorage.getItem(`session_${mockSessionId}_backup`)
      expect(storedItem).toBeTruthy()

      const parsed = JSON.parse(storedItem!)
      expect(parsed.encrypted_data).toBeTruthy()
      expect(parsed.iv).toBeTruthy()
      expect(parsed.timestamp).toBeTruthy()
      expect(parsed.version).toBe(1)

      // Verify data is encrypted (not plaintext)
      expect(storedItem).not.toContain('shoulder pain')
      expect(storedItem).not.toContain('Rotator cuff')

      // Restore and decrypt
      const restored = await restoreDraft(mockSessionId)
      expect(restored).toBeTruthy()
      expect(restored?.draft).toEqual(mockDraft)
      expect(restored?.version).toBe(1)
    })

    it('generates random IV for each encryption', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      // Encrypt same data twice
      await backupDraft(mockSessionId, mockDraft, 1)
      const firstEncrypted = localStorage.getItem(`session_${mockSessionId}_backup`)

      localStorage.removeItem(`session_${mockSessionId}_backup`)

      await backupDraft(mockSessionId, mockDraft, 1)
      const secondEncrypted = localStorage.getItem(`session_${mockSessionId}_backup`)

      // IVs should be different (randomized)
      const first = JSON.parse(firstEncrypted!)
      const second = JSON.parse(secondEncrypted!)
      expect(first.iv).not.toBe(second.iv)
      expect(first.encrypted_data).not.toBe(second.encrypted_data)
    })

    it('handles empty fields in draft data', async () => {
      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      const emptyDraft = {
        subjective: null,
        objective: null,
        assessment: null,
        plan: null,
        session_date: '2025-10-12T10:00:00Z',
        duration_minutes: null,
      }

      await backupDraft(mockSessionId, emptyDraft, 1)
      const restored = await restoreDraft(mockSessionId)

      expect(restored).toBeTruthy()
      expect(restored?.draft).toEqual(emptyDraft)
    })

    it('preserves version number across encryption/decryption', async () => {
      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      await backupDraft(mockSessionId, mockDraft, 5)
      const restored = await restoreDraft(mockSessionId)

      expect(restored?.version).toBe(5)
    })
  })

  describe('JWT Token Handling', () => {
    it('returns null when JWT token is missing', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: '',
      })

      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      // Backup should fail silently without JWT
      await backupDraft(mockSessionId, mockDraft, 1)
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()

      // Restore should return null without JWT
      // First, manually add encrypted data to test restore path
      localStorage.setItem(
        `session_${mockSessionId}_backup`,
        JSON.stringify({
          encrypted_data: 'fake-encrypted-data',
          iv: 'fake-iv',
          timestamp: Date.now(),
          version: 1,
        })
      )

      const restored = await restoreDraft(mockSessionId)
      expect(restored).toBeNull()

      // Verify backup was removed
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })

    it('uses first 32 characters of JWT for key derivation', async () => {
      const shortToken = 'short-jwt-token'
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: `access_token=${shortToken}`,
      })

      const { backupDraft } = useSecureOfflineBackup()

      // Should work even with short token (uses substring safely)
      await backupDraft(mockSessionId, mockDraft, 1)
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeTruthy()
    })

    it('fails to decrypt with different JWT token', async () => {
      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      // Encrypt with first token
      await backupDraft(mockSessionId, mockDraft, 1)

      // Change JWT token
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'access_token=different-token-with-different-key-material',
      })

      // Decrypt should fail and remove backup
      const restored = await restoreDraft(mockSessionId)
      expect(restored).toBeNull()
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })
  })

  describe('24-Hour TTL Enforcement', () => {
    it('returns draft when backup is fresh (< 24 hours)', async () => {
      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      await backupDraft(mockSessionId, mockDraft, 1)
      const restored = await restoreDraft(mockSessionId)

      expect(restored).toBeTruthy()
      expect(restored?.draft).toEqual(mockDraft)
    })

    it('deletes backup when expired (> 24 hours)', async () => {
      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      await backupDraft(mockSessionId, mockDraft, 1)

      // Manually modify timestamp to 25 hours ago
      const storedItem = localStorage.getItem(`session_${mockSessionId}_backup`)
      const parsed = JSON.parse(storedItem!)
      const twentyFiveHoursAgo = Date.now() - 25 * 60 * 60 * 1000
      parsed.timestamp = twentyFiveHoursAgo

      localStorage.setItem(`session_${mockSessionId}_backup`, JSON.stringify(parsed))

      // Restore should return null and delete expired backup
      const restored = await restoreDraft(mockSessionId)
      expect(restored).toBeNull()
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })

    it('stores timestamp when backup is created', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      const beforeBackup = Date.now()
      await backupDraft(mockSessionId, mockDraft, 1)
      const afterBackup = Date.now()

      const storedItem = localStorage.getItem(`session_${mockSessionId}_backup`)
      const parsed = JSON.parse(storedItem!)

      expect(parsed.timestamp).toBeGreaterThanOrEqual(beforeBackup)
      expect(parsed.timestamp).toBeLessThanOrEqual(afterBackup)
    })
  })

  describe('localStorage Operations', () => {
    it('returns null when no backup exists', async () => {
      const { restoreDraft } = useSecureOfflineBackup()

      const restored = await restoreDraft('non-existent-session')
      expect(restored).toBeNull()
    })

    it('handles corrupted localStorage data gracefully', async () => {
      const { restoreDraft } = useSecureOfflineBackup()

      // Store invalid JSON
      localStorage.setItem(`session_${mockSessionId}_backup`, 'invalid-json-{{{')

      const restored = await restoreDraft(mockSessionId)
      expect(restored).toBeNull()

      // Verify corrupted data was removed
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })

    it('handles missing fields in stored backup', async () => {
      const { restoreDraft } = useSecureOfflineBackup()

      // Store incomplete backup (missing iv)
      localStorage.setItem(
        `session_${mockSessionId}_backup`,
        JSON.stringify({
          encrypted_data: 'some-data',
          timestamp: Date.now(),
          version: 1,
          // Missing 'iv' field
        })
      )

      const restored = await restoreDraft(mockSessionId)
      expect(restored).toBeNull()
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })

    it('uses correct localStorage key format', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      await backupDraft('my-session-id', mockDraft, 1)

      expect(localStorage.getItem('session_my-session-id_backup')).toBeTruthy()
      expect(localStorage.getItem('my-session-id')).toBeNull()
    })

    it('overwrites existing backup for same session', async () => {
      const { backupDraft, restoreDraft } = useSecureOfflineBackup()

      // First backup
      await backupDraft(mockSessionId, mockDraft, 1)
      const firstRestored = await restoreDraft(mockSessionId)
      expect(firstRestored?.version).toBe(1)

      // Second backup with different version
      const updatedDraft = { ...mockDraft, subjective: 'Updated pain level' }
      await backupDraft(mockSessionId, updatedDraft, 2)

      const secondRestored = await restoreDraft(mockSessionId)
      expect(secondRestored?.version).toBe(2)
      expect(secondRestored?.draft.subjective).toBe('Updated pain level')
    })
  })

  describe('clearAllBackups', () => {
    it('removes all session backups from localStorage', () => {
      const { clearAllBackups } = useSecureOfflineBackup()

      // Add multiple session backups
      localStorage.setItem('session_abc_backup', 'data1')
      localStorage.setItem('session_xyz_backup', 'data2')
      localStorage.setItem('session_123_backup', 'data3')
      localStorage.setItem('other_key', 'should-remain')

      clearAllBackups()

      expect(localStorage.getItem('session_abc_backup')).toBeNull()
      expect(localStorage.getItem('session_xyz_backup')).toBeNull()
      expect(localStorage.getItem('session_123_backup')).toBeNull()
      expect(localStorage.getItem('other_key')).toBe('should-remain')
    })

    it('handles empty localStorage', () => {
      const { clearAllBackups } = useSecureOfflineBackup()

      localStorage.clear()
      expect(() => clearAllBackups()).not.toThrow()
    })

    it('only removes keys matching session_*_backup pattern', () => {
      const { clearAllBackups } = useSecureOfflineBackup()

      // Set up keys with correct and incorrect patterns
      localStorage.setItem('not_a_session_key', 'stays')
      localStorage.setItem('other_data', 'also-stays')
      localStorage.setItem('session_abc_backup', 'should-be-removed')
      localStorage.setItem('session_xyz_backup', 'should-be-removed-too')

      // Verify keys exist before clearing
      expect(localStorage.getItem('session_abc_backup')).toBe('should-be-removed')
      expect(localStorage.getItem('not_a_session_key')).toBe('stays')

      clearAllBackups()

      // Only session_*_backup keys should be removed
      expect(localStorage.getItem('session_abc_backup')).toBeNull()
      expect(localStorage.getItem('session_xyz_backup')).toBeNull()
      expect(localStorage.getItem('not_a_session_key')).toBe('stays')
      expect(localStorage.getItem('other_data')).toBe('also-stays')
    })
  })

  describe('syncToServer', () => {
    it('syncs restored draft to server', async () => {
      const { backupDraft, syncToServer } = useSecureOfflineBackup()

      vi.mocked(apiClient.patch).mockResolvedValue({} as AxiosResponse)

      // Create backup
      await backupDraft(mockSessionId, mockDraft, 1)

      // Sync to server
      const success = await syncToServer(mockSessionId)

      expect(success).toBe(true)
      expect(apiClient.patch).toHaveBeenCalledWith(`/sessions/${mockSessionId}/draft`, {
        subjective: mockDraft.subjective,
        objective: mockDraft.objective,
        assessment: mockDraft.assessment,
        plan: mockDraft.plan,
        session_date: mockDraft.session_date,
        duration_minutes: mockDraft.duration_minutes,
      })
    })

    it('removes localStorage backup after successful sync', async () => {
      const { backupDraft, syncToServer } = useSecureOfflineBackup()

      vi.mocked(apiClient.patch).mockResolvedValue({} as AxiosResponse)

      await backupDraft(mockSessionId, mockDraft, 1)
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeTruthy()

      await syncToServer(mockSessionId)

      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })

    it('returns false when no backup exists', async () => {
      const { syncToServer } = useSecureOfflineBackup()

      const success = await syncToServer('non-existent-session')

      expect(success).toBe(false)
      expect(apiClient.patch).not.toHaveBeenCalled()
    })

    it('returns false and keeps backup when sync fails', async () => {
      const { backupDraft, syncToServer } = useSecureOfflineBackup()

      vi.mocked(apiClient.patch).mockRejectedValue(new Error('Network error'))

      await backupDraft(mockSessionId, mockDraft, 1)

      const success = await syncToServer(mockSessionId)

      expect(success).toBe(false)
      // Backup should still exist for retry
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeTruthy()
    })

    it('handles expired backup during sync', async () => {
      const { backupDraft, syncToServer } = useSecureOfflineBackup()

      await backupDraft(mockSessionId, mockDraft, 1)

      // Manually expire backup
      const storedItem = localStorage.getItem(`session_${mockSessionId}_backup`)
      const parsed = JSON.parse(storedItem!)
      parsed.timestamp = Date.now() - 25 * 60 * 60 * 1000
      localStorage.setItem(`session_${mockSessionId}_backup`, JSON.stringify(parsed))

      const success = await syncToServer(mockSessionId)

      expect(success).toBe(false)
      expect(apiClient.patch).not.toHaveBeenCalled()
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })
  })

  describe('Error Handling', () => {
    it('handles encryption errors gracefully', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      // Mock crypto.subtle to throw error
      const originalEncrypt = crypto.subtle.encrypt
      crypto.subtle.encrypt = vi.fn().mockRejectedValue(new Error('Encryption failed'))

      // Should not throw, just log error
      await expect(backupDraft(mockSessionId, mockDraft, 1)).resolves.not.toThrow()

      // Verify nothing was stored
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()

      // Restore original
      crypto.subtle.encrypt = originalEncrypt
    })

    it('handles decryption errors gracefully', async () => {
      const { restoreDraft } = useSecureOfflineBackup()

      // Store invalid encrypted data
      localStorage.setItem(
        `session_${mockSessionId}_backup`,
        JSON.stringify({
          encrypted_data: 'invalid-base64-data-!@#$%',
          iv: 'invalid-iv-data-!@#$%',
          timestamp: Date.now(),
          version: 1,
        })
      )

      const restored = await restoreDraft(mockSessionId)

      expect(restored).toBeNull()
      expect(localStorage.getItem(`session_${mockSessionId}_backup`)).toBeNull()
    })

    it('handles localStorage quota exceeded', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      // Mock localStorage.setItem to throw quota error
      const originalSetItem = Storage.prototype.setItem
      Storage.prototype.setItem = vi.fn().mockImplementation(() => {
        const error = new Error('QuotaExceededError')
        error.name = 'QuotaExceededError'
        throw error
      })

      // Should not throw, just log error
      await expect(backupDraft(mockSessionId, mockDraft, 1)).resolves.not.toThrow()

      // Restore original
      Storage.prototype.setItem = originalSetItem
    })
  })

  describe('Security Properties', () => {
    it('uses AES-256-GCM encryption', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      const deriveSpy = vi.spyOn(crypto.subtle, 'deriveKey')

      await backupDraft(mockSessionId, mockDraft, 1)

      expect(deriveSpy).toHaveBeenCalled()

      // Check the deriveKey call arguments
      // Arguments: (algorithm, baseKey, derivedKeyAlgorithm, extractable, keyUsages)
      const callArgs = deriveSpy.mock.calls[0]
      const derivedKeyAlgorithm = callArgs[2] // Third argument

      expect(derivedKeyAlgorithm).toMatchObject({ name: 'AES-GCM', length: 256 })

      deriveSpy.mockRestore()
    })

    it('uses PBKDF2 with 100,000 iterations', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      const deriveSpy = vi.spyOn(crypto.subtle, 'deriveKey')

      await backupDraft(mockSessionId, mockDraft, 1)

      expect(deriveSpy).toHaveBeenCalled()
      const call = deriveSpy.mock.calls[0]
      // Check PBKDF2 parameters
      expect(call[0]).toMatchObject({
        name: 'PBKDF2',
        iterations: 100000,
        hash: 'SHA-256',
      })

      deriveSpy.mockRestore()
    })

    it('uses 12-byte IV for AES-GCM', async () => {
      const { backupDraft } = useSecureOfflineBackup()

      await backupDraft(mockSessionId, mockDraft, 1)

      const storedItem = localStorage.getItem(`session_${mockSessionId}_backup`)
      const parsed = JSON.parse(storedItem!)

      // Decode base64 IV and check length
      const ivBytes = atob(parsed.iv).length
      expect(ivBytes).toBe(12) // 12 bytes = 96 bits (standard for AES-GCM)
    })
  })
})
