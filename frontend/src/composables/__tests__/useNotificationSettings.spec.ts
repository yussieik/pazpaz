/**
 * useNotificationSettings Composable Tests
 *
 * Tests for notification settings composable including:
 * - Loading settings from API
 * - Auto-save with debounce
 * - Error handling
 * - State management
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'
import { useNotificationSettings } from '../useNotificationSettings'
import * as notificationApi from '@/api/notification-settings'
import type { NotificationSettings } from '@/types/notification-settings'

// Mock the API module
vi.mock('@/api/notification-settings')

// Mock the toast composable
vi.mock('../useToast', () => ({
  useToast: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}))

// Mock useDebounceFn from @vueuse/core
vi.mock('@vueuse/core', () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-function-type
  useDebounceFn: (fn: Function) => {
    // Return a mock debounced function that executes immediately for testing
     
    const mockFn = vi.fn(async (...args: any[]) => {
      return fn(...args)
    })
    mockFn.cancel = vi.fn()
    return mockFn
  },
}))

describe('useNotificationSettings', () => {
  const mockSettings: NotificationSettings = {
    id: '1',
    user_id: 'user-1',
    workspace_id: 'workspace-1',
    email_enabled: true,
    notify_appointment_booked: true,
    notify_appointment_cancelled: true,
    notify_appointment_rescheduled: true,
    notify_appointment_confirmed: true,
    digest_enabled: false,
    digest_time: null,
    digest_skip_weekends: false,
    reminder_enabled: true,
    reminder_minutes: 30,
    notes_reminder_enabled: false,
    notes_reminder_time: null,
    extended_settings: {},
    created_at: '2025-10-22T00:00:00Z',
    updated_at: '2025-10-22T00:00:00Z',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('loadSettings', () => {
    it('loads settings successfully', async () => {
      vi.mocked(notificationApi.getNotificationSettings).mockResolvedValue(mockSettings)
      // Mock updateNotificationSettings to handle the auto-save triggered by watch
      vi.mocked(notificationApi.updateNotificationSettings).mockResolvedValue(
        mockSettings
      )

      const { settings, isLoading, error, loadSettings } = useNotificationSettings()

      expect(settings.value).toBeNull()
      expect(isLoading.value).toBe(false)

      const loadPromise = loadSettings()
      expect(isLoading.value).toBe(true)

      await loadPromise
      await nextTick()

      expect(isLoading.value).toBe(false)
      expect(settings.value).toEqual(mockSettings)
      expect(error.value).toBeNull()
    })

    it('handles API errors gracefully', async () => {
      const mockError = {
        response: {
          data: {
            detail: 'Failed to fetch settings',
          },
        },
        requestId: 'req-123',
      }

      vi.mocked(notificationApi.getNotificationSettings).mockRejectedValue(mockError)

      const { settings, isLoading, error, loadSettings } = useNotificationSettings()

      await loadSettings()
      await nextTick()

      expect(isLoading.value).toBe(false)
      expect(settings.value).toBeNull()
      expect(error.value).toBe('Failed to fetch settings')
    })

    it('handles API errors without detail', async () => {
      const mockError = new Error('Network error')

      vi.mocked(notificationApi.getNotificationSettings).mockRejectedValue(mockError)

      const { error, loadSettings } = useNotificationSettings()

      await loadSettings()
      await nextTick()

      expect(error.value).toBe('Failed to load notification settings')
    })
  })

  describe('saveSettings', () => {
    it('saves settings successfully', async () => {
      const updatedSettings = { ...mockSettings, email_enabled: false }

      vi.mocked(notificationApi.getNotificationSettings).mockResolvedValue(mockSettings)
      vi.mocked(notificationApi.updateNotificationSettings).mockResolvedValue(
        updatedSettings
      )

      const { settings, isSaving, error, loadSettings, saveNow } =
        useNotificationSettings()

      await loadSettings()
      await nextTick()

      // Modify settings
      settings.value!.email_enabled = false

      // Trigger manual save
      const savePromise = saveNow()
      expect(isSaving.value).toBe(true)

      await savePromise
      await nextTick()

      expect(isSaving.value).toBe(false)
      expect(settings.value?.email_enabled).toBe(false)
      expect(error.value).toBeNull()
      expect(notificationApi.updateNotificationSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          email_enabled: false,
        })
      )
    })

    it('handles save errors gracefully', async () => {
      const mockError = {
        response: {
          data: {
            detail: 'Failed to save settings',
          },
        },
        requestId: 'req-456',
      }

      vi.mocked(notificationApi.getNotificationSettings).mockResolvedValue(mockSettings)
      vi.mocked(notificationApi.updateNotificationSettings).mockRejectedValue(mockError)

      const { settings, isSaving, error, loadSettings, saveNow } =
        useNotificationSettings()

      await loadSettings()
      await nextTick()

      // Modify settings
      settings.value!.email_enabled = false

      // Trigger manual save
      await saveNow()
      await nextTick()

      expect(isSaving.value).toBe(false)
      expect(error.value).toBe('Failed to save settings')
    })

    it('does not save when settings is null', async () => {
      const { saveNow } = useNotificationSettings()

      await saveNow()
      await nextTick()

      expect(notificationApi.updateNotificationSettings).not.toHaveBeenCalled()
    })
  })

  describe('Auto-save behavior', () => {
    it('updates lastSaved after successful load', async () => {
      vi.mocked(notificationApi.getNotificationSettings).mockResolvedValue(mockSettings)

      const { lastSaved, loadSettings } = useNotificationSettings()

      expect(lastSaved.value).toBeNull()

      await loadSettings()
      await nextTick()

      expect(lastSaved.value).toBe('just now')
    })

    it('updates lastSaved after successful save', async () => {
      vi.mocked(notificationApi.getNotificationSettings).mockResolvedValue(mockSettings)
      vi.mocked(notificationApi.updateNotificationSettings).mockResolvedValue(
        mockSettings
      )

      const { lastSaved, loadSettings, saveNow } = useNotificationSettings()

      await loadSettings()
      await nextTick()

      // Clear lastSaved
      lastSaved.value = null

      await saveNow()
      await nextTick()

      expect(lastSaved.value).toBe('just now')
    })
  })

  describe('State management', () => {
    it('initializes with correct default values', () => {
      const { settings, isLoading, isSaving, lastSaved, error } =
        useNotificationSettings()

      expect(settings.value).toBeNull()
      expect(isLoading.value).toBe(false)
      expect(isSaving.value).toBe(false)
      expect(lastSaved.value).toBeNull()
      expect(error.value).toBeNull()
    })

    it('clears error on successful load', async () => {
      // First, cause an error
      vi.mocked(notificationApi.getNotificationSettings).mockRejectedValueOnce(
        new Error('Network error')
      )

      const { error, loadSettings } = useNotificationSettings()

      await loadSettings()
      await nextTick()
      expect(error.value).toBeTruthy()

      // Now succeed
      vi.mocked(notificationApi.getNotificationSettings).mockResolvedValue(mockSettings)

      await loadSettings()
      await nextTick()
      expect(error.value).toBeNull()
    })

    it('clears error on successful save', async () => {
      vi.mocked(notificationApi.getNotificationSettings).mockResolvedValue(mockSettings)

      const mockError = {
        response: {
          data: {
            detail: 'Save error',
          },
        },
      }

      vi.mocked(notificationApi.updateNotificationSettings)
        .mockResolvedValueOnce(mockSettings) // First call from initial load auto-save
        .mockRejectedValueOnce(mockError) // Second call fails
        .mockResolvedValueOnce(mockSettings) // Third call succeeds

      const { settings, error, loadSettings, saveNow } = useNotificationSettings()

      await loadSettings()
      await nextTick()

      // First save fails
      settings.value!.email_enabled = false
      await saveNow()
      await nextTick()
      expect(error.value).toBeTruthy()

      // Second save succeeds
      settings.value!.email_enabled = true
      await saveNow()
      await nextTick()
      expect(error.value).toBeNull()
    })
  })
})
