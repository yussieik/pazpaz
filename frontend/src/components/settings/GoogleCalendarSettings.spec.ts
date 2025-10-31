import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import GoogleCalendarSettings from './GoogleCalendarSettings.vue'

/**
 * GoogleCalendarSettings Component Tests
 *
 * Tests OAuth flow, connection states, and user interactions.
 */

// Mock composables
const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
const mockUpdateSettings = vi.fn()
const mockFetchStatus = vi.fn()

vi.mock('@/composables/useGoogleCalendarIntegration', () => ({
  useGoogleCalendarIntegration: () => ({
    isConnected: vi.fn(() => false),
    settings: {
      auto_sync_enabled: false,
      include_client_names: false,
    },
    lastSyncTime: null,
    isLoading: false,
    connect: mockConnect,
    disconnect: mockDisconnect,
    updateSettings: mockUpdateSettings,
    fetchStatus: mockFetchStatus,
  }),
}))

const mockShowSuccess = vi.fn()
const mockShowError = vi.fn()

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    showSuccess: mockShowSuccess,
    showError: mockShowError,
  }),
}))

// Mock LoadingSpinner component
vi.mock('@/components/common/LoadingSpinner.vue', () => ({
  default: {
    name: 'LoadingSpinner',
    template: '<div class="loading-spinner">Loading...</div>',
  },
}))

// Mock ToggleSwitch component
vi.mock('@/components/common/ToggleSwitch.vue', () => ({
  default: {
    name: 'ToggleSwitch',
    props: ['modelValue', 'label'],
    emits: ['update:modelValue'],
    template: `
      <button
        type="button"
        @click="$emit('update:modelValue', !modelValue)"
      >
        {{ label }}: {{ modelValue ? 'ON' : 'OFF' }}
      </button>
    `,
  },
}))

describe('GoogleCalendarSettings', () => {
  let wrapper: VueWrapper

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('Not Connected State', () => {
    it('renders "Connect to Google Calendar" button when not connected', () => {
      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      expect(wrapper.text()).toContain('Connect to Google Calendar')
      expect(wrapper.text()).toContain('Google Calendar Integration')
    })

    it('displays HIPAA warning accordion (collapsed by default)', () => {
      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      expect(wrapper.text()).toContain('Important: HIPAA Compliance')
      // Warning content should not be visible initially
      expect(wrapper.text()).not.toContain('Google Calendar is not HIPAA-compliant')
    })

    it('expands HIPAA warning when clicked', async () => {
      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      // Find and click the warning accordion button
      const warningButton = wrapper.find('button[aria-expanded]')
      expect(warningButton.exists()).toBe(true)

      await warningButton.trigger('click')
      await nextTick()

      // Warning should now be expanded
      expect(warningButton.attributes('aria-expanded')).toBe('true')
    })

    it('calls connect() and opens popup when "Connect" button clicked', async () => {
      const authUrl = 'https://accounts.google.com/o/oauth2/auth?...'
      mockConnect.mockResolvedValue(authUrl)

      // Mock window.open
      const mockPopup = { closed: false }
      const windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(mockPopup as any)

      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      const connectButton = wrapper.find('button:not([aria-expanded])')
      await connectButton.trigger('click')
      await nextTick()

      // Should call connect to get auth URL
      expect(mockConnect).toHaveBeenCalledTimes(1)

      // Wait for promise to resolve
      await vi.waitFor(() => {
        expect(windowOpenSpy).toHaveBeenCalledWith(
          authUrl,
          'GoogleCalendarAuth',
          'width=600,height=700,left=100,top=100,menubar=no,toolbar=no,location=no,status=no'
        )
      })

      windowOpenSpy.mockRestore()
    })

    it('shows error when popup is blocked', async () => {
      mockConnect.mockResolvedValue('https://accounts.google.com/o/oauth2/auth?...')

      // Mock window.open returning null (popup blocked)
      const windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(null)

      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      const connectButton = wrapper.find('button:not([aria-expanded])')
      await connectButton.trigger('click')
      await nextTick()

      // Wait for error to be shown
      await vi.waitFor(() => {
        expect(mockShowError).toHaveBeenCalledWith(
          'Pop-up blocked. Please allow pop-ups and try again.'
        )
      })

      windowOpenSpy.mockRestore()
    })
  })

  describe('Connected State', () => {
    beforeEach(() => {
      // Mock as connected
      vi.mocked(
        require('@/composables/useGoogleCalendarIntegration')
          .useGoogleCalendarIntegration
      ).mockReturnValue({
        isConnected: vi.fn(() => true),
        settings: {
          auto_sync_enabled: true,
          include_client_names: false,
        },
        lastSyncTime: '2025-10-28T10:00:00Z',
        isLoading: false,
        connect: mockConnect,
        disconnect: mockDisconnect,
        updateSettings: mockUpdateSettings,
        fetchStatus: mockFetchStatus,
      })
    })

    it('renders "Connected to Google Calendar" banner', () => {
      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      expect(wrapper.text()).toContain('Connected to Google Calendar')
      expect(wrapper.text()).toContain('Last synced:')
    })

    it('displays sync settings with toggle switch', () => {
      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      expect(wrapper.text()).toContain('Sync Settings')
      expect(wrapper.text()).toContain('Automatic sync')
    })

    it('shows disconnect button', () => {
      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      const disconnectButton = wrapper.find('button:not([aria-expanded])')
      expect(disconnectButton.text()).toContain('Disconnect')
    })

    it('opens confirmation modal when disconnect button clicked', async () => {
      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      const disconnectButton = wrapper.find('button:not([aria-expanded])')
      await disconnectButton.trigger('click')
      await nextTick()

      // Modal should be visible
      expect(wrapper.text()).toContain('Disconnect Google Calendar?')
      expect(wrapper.text()).toContain('This will stop syncing appointments')
    })

    it('calls disconnect() when confirmed in modal', async () => {
      mockDisconnect.mockResolvedValue(undefined)

      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      // Open modal
      const disconnectButton = wrapper.find('button:not([aria-expanded])')
      await disconnectButton.trigger('click')
      await nextTick()

      // Confirm disconnect
      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text() === 'Disconnect')
      expect(confirmButton).toBeDefined()
      await confirmButton!.trigger('click')
      await nextTick()

      // Wait for disconnect to be called
      await vi.waitFor(() => {
        expect(mockDisconnect).toHaveBeenCalledTimes(1)
      })
    })

    it('calls updateSettings() when auto sync toggle is clicked', async () => {
      mockUpdateSettings.mockResolvedValue(undefined)

      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      // Find and click toggle switch (mocked component)
      const toggleButton = wrapper.find('button:not([aria-expanded])')
      await toggleButton.trigger('click')
      await nextTick()

      // Should call updateSettings
      await vi.waitFor(() => {
        expect(mockUpdateSettings).toHaveBeenCalled()
      })
    })
  })

  describe('Loading State', () => {
    it('shows loading spinner when fetching initial status', () => {
      vi.mocked(
        require('@/composables/useGoogleCalendarIntegration')
          .useGoogleCalendarIntegration
      ).mockReturnValue({
        isConnected: vi.fn(() => false),
        settings: {
          auto_sync_enabled: false,
          include_client_names: false,
        },
        lastSyncTime: null,
        isLoading: true,
        connect: mockConnect,
        disconnect: mockDisconnect,
        updateSettings: mockUpdateSettings,
        fetchStatus: mockFetchStatus,
      })

      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      expect(wrapper.find('.loading-spinner').exists()).toBe(true)
    })
  })

  describe('Error Handling', () => {
    it('shows error toast when connect fails', async () => {
      mockConnect.mockRejectedValue(new Error('Network error'))

      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      const connectButton = wrapper.find('button:not([aria-expanded])')
      await connectButton.trigger('click')
      await nextTick()

      // Wait for error to be shown
      await vi.waitFor(() => {
        expect(mockShowError).toHaveBeenCalledWith(
          'Failed to connect. Please try again.'
        )
      })
    })

    it('shows error toast when disconnect fails', async () => {
      mockDisconnect.mockRejectedValue(new Error('Network error'))

      vi.mocked(
        require('@/composables/useGoogleCalendarIntegration')
          .useGoogleCalendarIntegration
      ).mockReturnValue({
        isConnected: vi.fn(() => true),
        settings: {
          auto_sync_enabled: true,
          include_client_names: false,
        },
        lastSyncTime: null,
        isLoading: false,
        connect: mockConnect,
        disconnect: mockDisconnect,
        updateSettings: mockUpdateSettings,
        fetchStatus: mockFetchStatus,
      })

      wrapper = mount(GoogleCalendarSettings, {
        global: {
          stubs: {
            Teleport: true,
          },
        },
      })

      // Open modal
      const disconnectButton = wrapper.find('button:not([aria-expanded])')
      await disconnectButton.trigger('click')
      await nextTick()

      // Confirm disconnect
      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text() === 'Disconnect')
      await confirmButton!.trigger('click')
      await nextTick()

      // Wait for error to be shown
      await vi.waitFor(() => {
        expect(mockShowError).toHaveBeenCalledWith(
          'Failed to disconnect. Please try again.'
        )
      })
    })
  })
})
