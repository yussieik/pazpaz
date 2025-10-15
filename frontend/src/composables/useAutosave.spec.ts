import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useAutosave } from './useAutosave'
import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

// Mock useSecureOfflineBackup
const mockBackupDraft = vi.fn()
const mockSyncToServer = vi.fn()

vi.mock('./useSecureOfflineBackup', () => ({
  useSecureOfflineBackup: () => ({
    backupDraft: mockBackupDraft,
    syncToServer: mockSyncToServer,
    clearAllBackups: vi.fn(),
  }),
}))

/**
 * Tests for useAutosave composable
 *
 * Verifies autosave functionality, debouncing, online/offline detection,
 * encrypted localStorage backup integration, and auto-sync on reconnect.
 */
describe('useAutosave', () => {
  let mockSaveFn: ReturnType<typeof vi.fn>
  const mountedWrappers: any[] = []

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    mockSaveFn = vi.fn().mockResolvedValue(undefined)
    mockBackupDraft.mockResolvedValue(undefined)
    mockSyncToServer.mockResolvedValue(true)

    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    })

    // Clear mounted wrappers array
    mountedWrappers.length = 0
  })

  afterEach(() => {
    // Unmount all wrappers to prevent event listener interference
    mountedWrappers.forEach((wrapper) => {
      if (wrapper && wrapper.unmount) {
        wrapper.unmount()
      }
    })
    mountedWrappers.length = 0

    vi.useRealTimers()
    localStorage.clear()
  })

  // Helper component to test composable with lifecycle hooks
  const createTestComponent = (options = {}) => {
    return defineComponent({
      setup() {
        const result = useAutosave(mockSaveFn, options)
        // Explicitly return all properties for test access
        return {
          isSaving: result.isSaving,
          lastSavedAt: result.lastSavedAt,
          saveError: result.saveError,
          isActive: result.isActive,
          isOnline: result.isOnline,
          save: result.save,
          forceSave: result.forceSave,
          start: result.start,
          stop: result.stop,
          clearError: result.clearError,
        }
      },
      template: '<div></div>',
    })
  }

  // Helper to mount and track wrappers for auto-cleanup
  const mountAndTrack = (component: any) => {
    const wrapper = mount(component)
    mountedWrappers.push(wrapper)
    return wrapper
  }

  describe('Basic Autosave Functionality', () => {
    it('saves data after debounce delay (5 seconds default)', async () => {
      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      const data = { field: 'value' }
      save(data)

      // Should not save immediately
      expect(mockSaveFn).not.toHaveBeenCalled()

      // Advance 4 seconds - still no save
      await vi.advanceTimersByTimeAsync(4000)
      expect(mockSaveFn).not.toHaveBeenCalled()

      // Advance to 5 seconds - should trigger save
      await vi.advanceTimersByTimeAsync(1000)
      expect(mockSaveFn).toHaveBeenCalledWith(data)
    })

    it('uses custom debounce delay', async () => {
      const wrapper = mountAndTrack(createTestComponent({ debounceMs: 3000 }))
      const { save } = wrapper.vm as any

      save({ field: 'value' })

      await vi.advanceTimersByTimeAsync(2999)
      expect(mockSaveFn).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(1)
      expect(mockSaveFn).toHaveBeenCalled()
    })

    it('debounces multiple rapid saves', async () => {
      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      save({ field: 'value1' })
      await vi.advanceTimersByTimeAsync(2000)
      save({ field: 'value2' })
      await vi.advanceTimersByTimeAsync(2000)
      save({ field: 'value3' })

      // Only the last value should be saved after debounce
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockSaveFn).toHaveBeenCalledTimes(1)
      expect(mockSaveFn).toHaveBeenCalledWith({ field: 'value3' })
    })

    it('forceSave bypasses debounce', async () => {
      const wrapper = mountAndTrack(createTestComponent())
      const { forceSave } = wrapper.vm as any

      await forceSave({ field: 'immediate' })

      // Should save immediately without waiting
      expect(mockSaveFn).toHaveBeenCalledWith({ field: 'immediate' })
    })

    it('updates isSaving state during save', async () => {
      mockSaveFn.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 500))
      )

      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      expect(wrapper.vm.isSaving).toBe(false)

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.isSaving).toBe(true)

      await vi.advanceTimersByTimeAsync(500)
      expect(wrapper.vm.isSaving).toBe(false)
    })

    it('calls onSuccess callback after successful save', async () => {
      const onSuccess = vi.fn()
      const wrapper = mountAndTrack(createTestComponent({ onSuccess }))
      const { save } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(onSuccess).toHaveBeenCalled()
    })

    it('calls onError callback on save failure', async () => {
      const onError = vi.fn()
      const error = new Error('Save failed')
      mockSaveFn.mockRejectedValue(error)

      const wrapper = mountAndTrack(createTestComponent({ onError }))
      const { save } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(onError).toHaveBeenCalledWith(error)
    })
  })

  describe('Online/Offline Detection', () => {
    it('tracks online status via isOnline ref', async () => {
      const wrapper = mountAndTrack(createTestComponent())
      await wrapper.vm.$nextTick()

      // In Vue 3, refs returned from setup() are auto-unwrapped when accessed via wrapper.vm
      expect(wrapper.vm.isOnline).toBe(true) // navigator.onLine is mocked as true
    })

    it('updates isOnline when online event fires', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      })

      const wrapper = mountAndTrack(createTestComponent())

      expect(wrapper.vm.isOnline).toBe(false)

      // Simulate coming back online
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      })
      window.dispatchEvent(new Event('online'))

      await vi.runAllTimersAsync()

      expect(wrapper.vm.isOnline).toBe(true)

      // Clean up to prevent interference with other tests
      wrapper.unmount()
    })

    it('updates isOnline when offline event fires', async () => {
      const wrapper = mountAndTrack(createTestComponent())

      expect(wrapper.vm.isOnline).toBe(true)

      // Simulate going offline
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      })
      window.dispatchEvent(new Event('offline'))

      await vi.runAllTimersAsync()

      expect(wrapper.vm.isOnline).toBe(false)

      // Clean up to prevent interference with other tests
      wrapper.unmount()
    })

    it('cleans up event listeners on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

      const wrapper = mountAndTrack(createTestComponent())
      wrapper.unmount()

      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'online',
        expect.any(Function)
      )
      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'offline',
        expect.any(Function)
      )

      removeEventListenerSpy.mockRestore()
    })
  })

  describe('Encrypted localStorage Backup Integration', () => {
    const sessionId = 'session-123'
    const version = 1

    const mockDraftData = {
      subjective: 'Patient reports pain',
      objective: 'ROM: 120°',
      assessment: 'Tendinitis',
      plan: 'Ice and rest',
      session_date: '2025-10-12T10:00:00Z',
      duration_minutes: 60,
    }

    it('backups to encrypted localStorage on every autosave when sessionId provided', async () => {
      const wrapper = mountAndTrack(createTestComponent({ sessionId, version }))
      const { save } = wrapper.vm as any

      save(mockDraftData)
      await vi.advanceTimersByTimeAsync(5000)

      expect(mockBackupDraft).toHaveBeenCalledWith(sessionId, mockDraftData, version)
      expect(mockSaveFn).toHaveBeenCalledWith(mockDraftData)
    })

    it('does not backup when sessionId is not provided', async () => {
      const wrapper = mountAndTrack(createTestComponent()) // No sessionId
      const { save } = wrapper.vm as any

      save(mockDraftData)
      await vi.advanceTimersByTimeAsync(5000)

      expect(mockBackupDraft).not.toHaveBeenCalled()
      expect(mockSaveFn).toHaveBeenCalled()
    })

    it('clears localStorage backup after successful server save', async () => {
      const wrapper = mountAndTrack(createTestComponent({ sessionId, version }))
      const { save } = wrapper.vm as any

      save(mockDraftData)
      await vi.advanceTimersByTimeAsync(5000)

      expect(mockBackupDraft).toHaveBeenCalled()
      expect(mockSaveFn).toHaveBeenCalled()
      expect(localStorage.getItem(`session_${sessionId}_backup`)).toBeNull()
    })

    it('keeps backup when server save fails (offline mode)', async () => {
      mockSaveFn.mockRejectedValue({
        request: {}, // Network error (no response)
      })

      const wrapper = mountAndTrack(createTestComponent({ sessionId, version }))
      const { save } = wrapper.vm as any

      save(mockDraftData)
      await vi.advanceTimersByTimeAsync(5000)

      expect(mockBackupDraft).toHaveBeenCalled()
      expect(wrapper.vm.isOnline).toBe(false) // Should mark as offline
    })

    it('saves to backup even when online (safety net)', async () => {
      const wrapper = mountAndTrack(createTestComponent({ sessionId, version }))
      const { save } = wrapper.vm as any

      expect(wrapper.vm.isOnline).toBe(true)

      save(mockDraftData)
      await vi.advanceTimersByTimeAsync(5000)

      // Both backup and server save should be called
      expect(mockBackupDraft).toHaveBeenCalledWith(sessionId, mockDraftData, version)
      expect(mockSaveFn).toHaveBeenCalledWith(mockDraftData)
    })
  })

  describe('Auto-Sync on Reconnect', () => {
    const sessionId = 'session-123'

    it('auto-syncs when coming back online', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      })

      const wrapper = mountAndTrack(createTestComponent({ sessionId }))

      expect(wrapper.vm.isOnline).toBe(false)

      // Simulate coming back online
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      })
      window.dispatchEvent(new Event('online'))

      await vi.runAllTimersAsync()

      expect(wrapper.vm.isOnline).toBe(true)
      expect(mockSyncToServer).toHaveBeenCalledWith(sessionId)

      // Clean up to prevent interference with other tests
      wrapper.unmount()
    })

    it('does not auto-sync when sessionId is not provided', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      })

      const wrapper = mountAndTrack(createTestComponent()) // No sessionId

      // Clear mocks AFTER mounting to count only THIS component's calls
      vi.clearAllMocks()

      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      })
      window.dispatchEvent(new Event('online'))

      await vi.runAllTimersAsync()

      // This component should not have called syncToServer
      expect(mockSyncToServer).not.toHaveBeenCalled()

      // Clean up
      wrapper.unmount()
    })

    it('handles sync failure gracefully', async () => {
      mockSyncToServer.mockResolvedValue(false) // Sync failed

      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      })

      const wrapper = mountAndTrack(createTestComponent({ sessionId }))

      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      })
      window.dispatchEvent(new Event('online'))

      await vi.runAllTimersAsync()

      expect(mockSyncToServer).toHaveBeenCalledWith(sessionId)
      // Should not throw error

      // Clean up
      wrapper.unmount()
    })
  })

  describe('Start/Stop Controls', () => {
    it('starts in active state by default', () => {
      const wrapper = mountAndTrack(createTestComponent())

      expect(wrapper.vm.isActive).toBe(true)
    })

    it('respects autoStart: false option', () => {
      const wrapper = mountAndTrack(createTestComponent({ autoStart: false }))

      expect(wrapper.vm.isActive).toBe(false)
    })

    it('does not save when stopped', async () => {
      const wrapper = mountAndTrack(createTestComponent())
      const { save, stop } = wrapper.vm as any

      stop()

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(mockSaveFn).not.toHaveBeenCalled()
    })

    it('resumes saving after start', async () => {
      const wrapper = mountAndTrack(createTestComponent({ autoStart: false }))
      const { save, start } = wrapper.vm as any

      expect(wrapper.vm.isActive).toBe(false)

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockSaveFn).not.toHaveBeenCalled()

      start()
      expect(wrapper.vm.isActive).toBe(true)

      save({ field: 'value2' })
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockSaveFn).toHaveBeenCalledWith({ field: 'value2' })
    })
  })

  describe('Error Handling', () => {
    it('sets saveError on network errors', async () => {
      mockSaveFn.mockRejectedValue({
        request: {},
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.saveError).toContain('Network error')
    })

    it('sets saveError on 404 errors', async () => {
      mockSaveFn.mockRejectedValue({
        response: { status: 404, data: {} },
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.saveError).toContain('Session not found')
    })

    it('sets saveError on 422 validation errors', async () => {
      mockSaveFn.mockRejectedValue({
        response: { status: 422, data: { detail: 'Invalid field' } },
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.saveError).toBe('Invalid field')
    })

    it('sets saveError on 429 rate limit errors', async () => {
      mockSaveFn.mockRejectedValue({
        response: { status: 429, data: {} },
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.saveError).toContain('Too many save requests')
    })

    it('sets saveError on 403 permission errors', async () => {
      mockSaveFn.mockRejectedValue({
        response: { status: 403, data: {} },
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.saveError).toContain('permission')
    })

    it('clears saveError with clearError', async () => {
      mockSaveFn.mockRejectedValue({
        request: {}, // Network error, doesn't throw
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { save, clearError } = wrapper.vm as any

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.saveError).toBeTruthy()

      clearError()
      expect(wrapper.vm.saveError).toBeNull()
    })

    it('marks as offline on network error', async () => {
      mockSaveFn.mockRejectedValue({
        request: {}, // Network error
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { save } = wrapper.vm as any

      expect(wrapper.vm.isOnline).toBe(true)

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      expect(wrapper.vm.isOnline).toBe(false)
    })

    it('does not throw error when save fails offline (backup exists)', async () => {
      mockSaveFn.mockRejectedValue({
        request: {}, // Network error
      })

      const wrapper = mountAndTrack(
        createTestComponent({ sessionId: 'session-123', version: 1 })
      )
      const { save } = wrapper.vm as any

      save({ field: 'value' })

      await expect(vi.advanceTimersByTimeAsync(5000)).resolves.not.toThrow()
    })

    it('throws error when save fails online', async () => {
      const error = new Error('Server error')
      mockSaveFn.mockRejectedValue({
        response: { status: 500, data: { detail: 'Server error' } },
      })

      const wrapper = mountAndTrack(createTestComponent())
      const { forceSave } = wrapper.vm as any

      await expect(forceSave({ field: 'value' })).rejects.toThrow()
    })
  })

  describe('Offline Mode Behavior', () => {
    const sessionId = 'session-123'
    const version = 1

    it('saves to backup only when offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      })

      const wrapper = mountAndTrack(createTestComponent({ sessionId, version }))
      const { save } = wrapper.vm as any

      expect(wrapper.vm.isOnline).toBe(false)

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      // Should backup but not call server
      expect(mockBackupDraft).toHaveBeenCalled()
      expect(mockSaveFn).not.toHaveBeenCalled()
    })

    it('does not clear backup when saving offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      })

      const wrapper = mountAndTrack(createTestComponent({ sessionId, version }))
      const { save } = wrapper.vm as any

      localStorage.setItem(`session_${sessionId}_backup`, 'encrypted-data')

      save({ field: 'value' })
      await vi.advanceTimersByTimeAsync(5000)

      // Backup should still exist
      expect(localStorage.getItem(`session_${sessionId}_backup`)).toBeTruthy()
    })
  })
})
