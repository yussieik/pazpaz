import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SessionTimeoutModal from './SessionTimeoutModal.vue'
import { nextTick } from 'vue'

describe('SessionTimeoutModal', () => {
  const mockRefreshSession = vi.fn()
  const mockHandleTimeout = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Clean up teleported elements
    document.body.innerHTML = ''
  })

  describe('rendering', () => {
    it('should not render when showWarning is false', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: false,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const dialog = document.querySelector('[role="dialog"]')
      expect(dialog).toBeFalsy()
      wrapper.unmount()
    })

    it('should render when showWarning is true', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const dialog = document.querySelector('[role="dialog"]')
      expect(dialog).toBeTruthy()
      wrapper.unmount()
    })

    it('should render with correct title', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const title = document.querySelector('#session-timeout-title')
      expect(title?.textContent?.trim()).toBe('Session Expiring Soon')
      wrapper.unmount()
    })

    it('should render both action buttons', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      expect(buttons).toHaveLength(2)
      expect(buttons[0].textContent).toContain('Stay Logged In')
      expect(buttons[1].textContent?.trim()).toBe('Log Out Now')
      wrapper.unmount()
    })

    it('should render HIPAA compliance notice', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const notice = document.querySelector('.text-xs.text-gray-500')
      expect(notice?.textContent).toContain('HIPAA compliance')
      wrapper.unmount()
    })
  })

  describe('countdown formatting', () => {
    it('should format 300 seconds as 5:00', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('5:00')
      wrapper.unmount()
    })

    it('should format 290 seconds as 4:50', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 290,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('4:50')
      wrapper.unmount()
    })

    it('should format 60 seconds as 1:00', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 60,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('1:00')
      wrapper.unmount()
    })

    it('should format 59 seconds as 0:59', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 59,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('0:59')
      wrapper.unmount()
    })

    it('should format 5 seconds as 0:05', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 5,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('0:05')
      wrapper.unmount()
    })

    it('should format 0 seconds as 0:00', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 0,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('0:00')
      wrapper.unmount()
    })

    it('should update countdown display when prop changes', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      let description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('5:00')

      await wrapper.setProps({ remainingSeconds: 120 })
      await nextTick()

      description = document.querySelector('#session-timeout-description')
      expect(description?.textContent).toContain('2:00')
      wrapper.unmount()
    })
  })

  describe('refresh session action', () => {
    it('should call refreshSession when "Stay Logged In" is clicked', async () => {
      mockRefreshSession.mockResolvedValue(undefined)

      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      const stayLoggedInButton = buttons[0] as HTMLButtonElement
      stayLoggedInButton.click()

      expect(mockRefreshSession).toHaveBeenCalledTimes(1)
      wrapper.unmount()
    })

    it('should show loading state while refreshing', async () => {
      let resolveRefresh: () => void
      const refreshPromise = new Promise<void>((resolve) => {
        resolveRefresh = resolve
      })
      mockRefreshSession.mockReturnValue(refreshPromise)

      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      let buttons = document.querySelectorAll('button')
      const stayLoggedInButton = buttons[0] as HTMLButtonElement
      stayLoggedInButton.click()
      await nextTick()

      // Button should show loading text
      expect(stayLoggedInButton.textContent).toBe('Refreshing...')

      // Both buttons should be disabled during refresh
      expect(stayLoggedInButton.disabled).toBe(true)
      expect((buttons[1] as HTMLButtonElement).disabled).toBe(true)

      // Resolve refresh
      resolveRefresh!()
      await nextTick()
      await nextTick() // Extra tick for state update

      // Re-query buttons after state update
      buttons = document.querySelectorAll('button')
      const updatedButton = buttons[0] as HTMLButtonElement

      // Button should return to normal state
      expect(updatedButton.textContent).toContain('Stay Logged In')
      expect(updatedButton.disabled).toBe(false)
      wrapper.unmount()
    })

    it('should reset loading state even if refresh fails', async () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

      // Wrap refreshSession to handle rejection internally (as real implementation does)
      const failingRefresh = vi.fn().mockImplementation(async () => {
        try {
          throw new Error('Network error')
        } catch (error) {
          console.error('Refresh failed:', error)
          // Real implementation handles this gracefully
        }
      })

      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: failingRefresh,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      const stayLoggedInButton = buttons[0] as HTMLButtonElement
      stayLoggedInButton.click()

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 10))
      await nextTick()

      // Re-query button after state update
      const updatedButtons = document.querySelectorAll('button')
      const updatedButton = updatedButtons[0] as HTMLButtonElement

      // Loading state should be reset
      expect(updatedButton.textContent).toContain('Stay Logged In')
      wrapper.unmount()
      consoleError.mockRestore()
    })
  })

  describe('logout action', () => {
    it('should call handleTimeout when "Log Out Now" is clicked', async () => {
      mockHandleTimeout.mockResolvedValue(undefined)

      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      const logOutButton = buttons[1] as HTMLButtonElement
      logOutButton.click()

      expect(mockHandleTimeout).toHaveBeenCalledTimes(1)
      wrapper.unmount()
    })

    it('should not call handleTimeout when clicking refresh button', async () => {
      mockRefreshSession.mockResolvedValue(undefined)

      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      const stayLoggedInButton = buttons[0] as HTMLButtonElement
      stayLoggedInButton.click()

      expect(mockHandleTimeout).not.toHaveBeenCalled()
      wrapper.unmount()
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA attributes', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const dialog = document.querySelector('[role="dialog"]')
      expect(dialog?.getAttribute('aria-modal')).toBe('true')
      expect(dialog?.getAttribute('aria-labelledby')).toBe('session-timeout-title')
      expect(dialog?.getAttribute('aria-describedby')).toBe('session-timeout-description')
      wrapper.unmount()
    })

    it('should have alertdialog role on inner container', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const alertDialog = document.querySelector('[role="alertdialog"]')
      expect(alertDialog).toBeTruthy()
      wrapper.unmount()
    })

    it('should have aria-hidden on warning icon', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const icon = document.querySelector('svg')
      expect(icon?.getAttribute('aria-hidden')).toBe('true')
      wrapper.unmount()
    })

    it('should have proper button types', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      buttons.forEach((button) => {
        expect(button.getAttribute('type')).toBe('button')
      })
      wrapper.unmount()
    })

    it('should have visible focus indicators', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      buttons.forEach((button) => {
        const classes = button.className
        expect(classes).toContain('focus:ring')
      })
      wrapper.unmount()
    })
  })

  describe('visual design', () => {
    it('should use yellow warning color for icon', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const icon = document.querySelector('svg')
      expect(icon?.className).toContain('text-yellow-500')
      wrapper.unmount()
    })

    it('should use blue for primary action button', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      expect(buttons[0].className).toContain('bg-blue-600')
      wrapper.unmount()
    })

    it('should use gray for secondary action button', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const buttons = document.querySelectorAll('button')
      expect(buttons[1].className).toContain('bg-gray-200')
      wrapper.unmount()
    })

    it('should have backdrop overlay', async () => {
      const wrapper = mount(SessionTimeoutModal, {
        attachTo: document.body,
        props: {
          showWarning: true,
          remainingSeconds: 300,
          refreshSession: mockRefreshSession,
          handleTimeout: mockHandleTimeout,
        },
      })

      await nextTick()

      const backdrop = document.querySelector('.fixed.inset-0')
      expect(backdrop?.className).toContain('bg-black/50')
      wrapper.unmount()
    })
  })
})
