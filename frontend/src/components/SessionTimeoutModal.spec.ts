import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SessionTimeoutModal from './SessionTimeoutModal.vue'
import { nextTick } from 'vue'

describe('SessionTimeoutModal', () => {
  const mockRefreshSession = vi.fn()
  const mockHandleTimeout = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('rendering', () => {
    it('should not render when showWarning is false', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: false,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    })

    it('should render when showWarning is true', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })

    it('should render with correct title', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const title = wrapper.find('#session-timeout-title')
      expect(title.text()).toBe('Session Expiring Soon')
    })

    it('should render both action buttons', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const buttons = wrapper.findAll('button')
      expect(buttons).toHaveLength(2)
      expect(buttons[0].text()).toContain('Stay Logged In')
      expect(buttons[1].text()).toBe('Log Out Now')
    })

    it('should render HIPAA compliance notice', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const notice = wrapper.find('.text-xs.text-gray-500')
      expect(notice.text()).toContain('HIPAA compliance')
    })
  })

  describe('countdown formatting', () => {
    it('should format 300 seconds as 5:00', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const description = wrapper.find('#session-timeout-description')
      expect(description.text()).toContain('5:00')
    })

    it('should format 290 seconds as 4:50', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 290,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const description = wrapper.find('#session-timeout-description')
      expect(description.text()).toContain('4:50')
    })

    it('should format 60 seconds as 1:00', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 60,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const description = wrapper.find('#session-timeout-description')
      expect(description.text()).toContain('1:00')
    })

    it('should format 59 seconds as 0:59', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 59,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const description = wrapper.find('#session-timeout-description')
      expect(description.text()).toContain('0:59')
    })

    it('should format 5 seconds as 0:05', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 5,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const description = wrapper.find('#session-timeout-description')
      expect(description.text()).toContain('0:05')
    })

    it('should format 0 seconds as 0:00', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 0,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const description = wrapper.find('#session-timeout-description')
      expect(description.text()).toContain('0:00')
    })

    it('should update countdown display when prop changes', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      expect(wrapper.find('#session-timeout-description').text()).toContain('5:00')

      await wrapper.setProps({ remainingSeconds: 120 })

      expect(wrapper.find('#session-timeout-description').text()).toContain('2:00')
    })
  })

  describe('refresh session action', () => {
    it('should call refreshSession when "Stay Logged In" is clicked', async () => {
      mockRefreshSession.mockResolvedValue(undefined)

      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const stayLoggedInButton = wrapper.findAll('button')[0]
      await stayLoggedInButton.trigger('click')

      expect(mockRefreshSession).toHaveBeenCalledTimes(1)
    })

    it('should show loading state while refreshing', async () => {
      let resolveRefresh: () => void
      const refreshPromise = new Promise<void>((resolve) => {
        resolveRefresh = resolve
      })
      mockRefreshSession.mockReturnValue(refreshPromise)

      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const stayLoggedInButton = wrapper.findAll('button')[0]
      await stayLoggedInButton.trigger('click')
      await nextTick()

      // Button should show loading text
      expect(stayLoggedInButton.text()).toBe('Refreshing...')

      // Both buttons should be disabled during refresh
      expect(stayLoggedInButton.attributes('disabled')).toBeDefined()
      expect(wrapper.findAll('button')[1].attributes('disabled')).toBeDefined()

      // Resolve refresh
      resolveRefresh!()
      await nextTick()

      // Button should return to normal state
      expect(stayLoggedInButton.text()).toContain('Stay Logged In')
      expect(stayLoggedInButton.attributes('disabled')).toBeUndefined()
    })

    it('should reset loading state even if refresh fails', async () => {
      mockRefreshSession.mockRejectedValue(new Error('Network error'))

      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const stayLoggedInButton = wrapper.findAll('button')[0]
      await stayLoggedInButton.trigger('click')
      await nextTick()

      // Wait for promise rejection
      await new Promise((resolve) => setTimeout(resolve, 0))
      await nextTick()

      // Loading state should be reset
      expect(stayLoggedInButton.text()).toContain('Stay Logged In')
    })
  })

  describe('logout action', () => {
    it('should call handleTimeout when "Log Out Now" is clicked', async () => {
      mockHandleTimeout.mockResolvedValue(undefined)

      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const logOutButton = wrapper.findAll('button')[1]
      await logOutButton.trigger('click')

      expect(mockHandleTimeout).toHaveBeenCalledTimes(1)
    })

    it('should not call handleTimeout when clicking refresh button', async () => {
      mockRefreshSession.mockResolvedValue(undefined)

      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const stayLoggedInButton = wrapper.findAll('button')[0]
      await stayLoggedInButton.trigger('click')

      expect(mockHandleTimeout).not.toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA attributes', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const dialog = wrapper.find('[role="dialog"]')
      expect(dialog.attributes('aria-modal')).toBe('true')
      expect(dialog.attributes('aria-labelledby')).toBe('session-timeout-title')
      expect(dialog.attributes('aria-describedby')).toBe('session-timeout-description')
    })

    it('should have alertdialog role on inner container', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const alertDialog = wrapper.find('[role="alertdialog"]')
      expect(alertDialog.exists()).toBe(true)
    })

    it('should have aria-hidden on warning icon', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const icon = wrapper.find('svg')
      expect(icon.attributes('aria-hidden')).toBe('true')
    })

    it('should have proper button types', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const buttons = wrapper.findAll('button')
      buttons.forEach((button) => {
        expect(button.attributes('type')).toBe('button')
      })
    })

    it('should have visible focus indicators', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const buttons = wrapper.findAll('button')
      buttons.forEach((button) => {
        const classes = button.classes().join(' ')
        expect(classes).toContain('focus:ring')
      })
    })
  })

  describe('visual design', () => {
    it('should use yellow warning color for icon', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const icon = wrapper.find('svg')
      expect(icon.classes()).toContain('text-yellow-500')
    })

    it('should use blue for primary action button', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const stayLoggedInButton = wrapper.findAll('button')[0]
      expect(stayLoggedInButton.classes()).toContain('bg-blue-600')
    })

    it('should use gray for secondary action button', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const logOutButton = wrapper.findAll('button')[1]
      expect(logOutButton.classes()).toContain('bg-gray-200')
    })

    it('should have backdrop overlay', () => {
      const wrapper = mount(SessionTimeoutModal, {
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      const backdrop = wrapper.find('.fixed.inset-0')
      expect(backdrop.classes()).toContain('bg-black/50')
    })
  })
})
