import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionTimeout } from './useSessionTimeout'
import { useAuthStore } from '@/stores/auth'
import apiClient from '@/api/client'

// Mock vue-router
vi.mock('vue-router', () => ({
  useRouter: vi.fn(),
}))

// Mock API client
vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(),
    interceptors: {
      response: {
        use: vi.fn(() => 1), // Return interceptor ID
        eject: vi.fn(),
      },
    },
  },
}))

describe('useSessionTimeout', () => {
  let mockRouter: {
    push: ReturnType<typeof vi.fn>
    currentRoute: { value: { fullPath: string } }
  }
  let pinia: ReturnType<typeof createPinia>

  // Helper component to test composable
  const TestComponent = defineComponent({
    setup() {
      const sessionTimeout = useSessionTimeout()
      return {
        showWarning: sessionTimeout.showWarning,
        remainingSeconds: sessionTimeout.remainingSeconds,
        refreshSession: sessionTimeout.refreshSession,
        handleTimeout: sessionTimeout.handleTimeout,
        resetTimers: sessionTimeout.resetTimers,
      }
    },
    template: '<div></div>',
  })

  beforeEach(() => {
    // Setup Pinia
    pinia = createPinia()
    setActivePinia(pinia)

    // Mock router
    mockRouter = {
      push: vi.fn(),
      currentRoute: {
        value: {
          fullPath: '/dashboard',
        },
      },
    }
    vi.mocked(useRouter).mockReturnValue(mockRouter as any)

    // Mock timers
    vi.useFakeTimers()

    // Mock console methods
    vi.spyOn(console, 'info').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})

    // Clear API client mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  describe('initialization', () => {
    it('should initialize timers when user is authenticated', () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })

      expect(console.info).toHaveBeenCalledWith(
        '[SessionTimeout] Initializing session timeout tracking'
      )

      wrapper.unmount()
    })

    it('should not initialize timers when user is not authenticated', () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      mount(TestComponent, { global: { plugins: [pinia] } })

      expect(console.info).not.toHaveBeenCalledWith(
        '[SessionTimeout] Initializing session timeout tracking'
      )
    })
  })

  describe('warning modal display', () => {
    it('should show warning modal 5 minutes before session expires', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      expect(result.showWarning).toBe(false)

      // Fast-forward to warning threshold (10 minutes)
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()

      expect(result.showWarning).toBe(true)
      expect(result.remainingSeconds).toBe(300) // 5 minutes in seconds

      wrapper.unmount()
    })

    it('should start countdown when warning modal appears', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Fast-forward to warning threshold
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()

      expect(result.remainingSeconds).toBe(300)

      // Fast-forward 10 seconds
      vi.advanceTimersByTime(10 * 1000)
      await nextTick()

      expect(result.remainingSeconds).toBe(290)

      wrapper.unmount()
    })
  })

  describe('countdown timer', () => {
    it('should decrement countdown every second', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Trigger warning
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()

      const initialSeconds = result.remainingSeconds
      expect(initialSeconds).toBe(300)

      // Advance 1 second
      vi.advanceTimersByTime(1000)
      await nextTick()
      expect(result.remainingSeconds).toBe(299)

      // Advance 30 seconds
      vi.advanceTimersByTime(30 * 1000)
      await nextTick()
      expect(result.remainingSeconds).toBe(269)

      wrapper.unmount()
    })

    it('should stop countdown near 0 seconds', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Trigger warning
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()

      expect(result.remainingSeconds).toBe(300)

      // Fast-forward to near countdown end
      vi.advanceTimersByTime(299 * 1000)
      await nextTick()

      // Should be at 1 second remaining
      expect(result.remainingSeconds).toBe(1)

      // Advance one more second
      vi.advanceTimersByTime(1000)
      await nextTick()

      // Should be at or near 0
      expect(result.remainingSeconds).toBeLessThanOrEqual(1)

      wrapper.unmount()
    })
  })

  describe('session refresh', () => {
    it('should successfully refresh session and close modal', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      vi.mocked(apiClient.post).mockResolvedValue({ data: { status: 'ok' } })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Trigger warning
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()
      expect(result.showWarning).toBe(true)

      // Refresh session
      await result.refreshSession()
      await nextTick()

      expect(apiClient.post).toHaveBeenCalledWith('/auth/session/refresh')
      expect(result.showWarning).toBe(false)
      expect(console.info).toHaveBeenCalledWith(
        '[SessionTimeout] Session refreshed successfully'
      )

      wrapper.unmount()
    })

    it('should reset timers after successful refresh', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      vi.mocked(apiClient.post).mockResolvedValue({ data: { status: 'ok' } })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Trigger warning
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()

      // Refresh session
      await result.refreshSession()
      await nextTick()

      // Should not show warning again immediately
      expect(result.showWarning).toBe(false)

      // But should show warning again after another 10 minutes
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()
      expect(result.showWarning).toBe(true)

      wrapper.unmount()
    })

    it('should handle refresh failure by logging out', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      // Mock logout
      vi.spyOn(authStore, 'logout').mockResolvedValue()

      // Mock API failure
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Session expired'))

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Trigger warning
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()

      // Try to refresh (will fail)
      await result.refreshSession()
      await nextTick()

      expect(console.error).toHaveBeenCalledWith(
        '[SessionTimeout] Failed to refresh session:',
        expect.any(Error)
      )
      expect(authStore.logout).toHaveBeenCalled()
      expect(mockRouter.push).toHaveBeenCalledWith({
        path: '/login',
        query: {
          message: 'session_expired',
          redirect: '/dashboard',
        },
      })

      wrapper.unmount()
    })
  })

  describe('automatic logout', () => {
    it('should automatically logout after countdown expires', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      vi.spyOn(authStore, 'logout').mockResolvedValue()

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Fast-forward to session expiry (15 minutes)
      vi.advanceTimersByTime(15 * 60 * 1000)
      await nextTick()

      expect(console.info).toHaveBeenCalledWith(
        '[SessionTimeout] Session expired, logging out'
      )
      expect(authStore.logout).toHaveBeenCalled()
      expect(mockRouter.push).toHaveBeenCalledWith({
        path: '/login',
        query: {
          message: 'session_expired',
          redirect: '/dashboard',
        },
      })

      wrapper.unmount()
    })

    it('should logout immediately when handleTimeout is called', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      vi.spyOn(authStore, 'logout').mockResolvedValue()

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Call handleTimeout directly (user clicks "Log out now")
      await result.handleTimeout()
      await nextTick()

      expect(authStore.logout).toHaveBeenCalled()
      expect(mockRouter.push).toHaveBeenCalledWith({
        path: '/login',
        query: {
          message: 'session_expired',
          redirect: '/dashboard',
        },
      })

      wrapper.unmount()
    })

    it('should close warning modal on logout', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      vi.spyOn(authStore, 'logout').mockResolvedValue()

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Trigger warning
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()
      expect(result.showWarning).toBe(true)

      // Logout
      await result.handleTimeout()
      await nextTick()

      expect(result.showWarning).toBe(false)

      wrapper.unmount()
    })
  })

  describe('activity tracking', () => {
    it('should reset timers on user click activity', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Fast-forward 5 minutes
      vi.advanceTimersByTime(5 * 60 * 1000)
      await nextTick()

      // Simulate user click
      window.dispatchEvent(new Event('click'))
      await nextTick()

      // Should not show warning even after 10 minutes from start
      // (because click reset the timer at 5-minute mark)
      vi.advanceTimersByTime(6 * 60 * 1000) // Total: 11 minutes from start, 6 from click
      await nextTick()
      expect(result.showWarning).toBe(false)

      // Should show warning after 10 minutes from click
      vi.advanceTimersByTime(4 * 60 * 1000) // 10 minutes from click
      await nextTick()
      expect(result.showWarning).toBe(true)

      wrapper.unmount()
    })

    it('should reset timers on keyboard activity', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Fast-forward 8 minutes
      vi.advanceTimersByTime(8 * 60 * 1000)
      await nextTick()

      // Simulate keyboard activity
      window.dispatchEvent(new KeyboardEvent('keydown'))
      await nextTick()

      // Should not show warning yet
      vi.advanceTimersByTime(9 * 60 * 1000)
      await nextTick()
      expect(result.showWarning).toBe(false)

      wrapper.unmount()
    })

    it('should close warning modal if activity detected', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      const result = wrapper.vm as any

      // Trigger warning
      vi.advanceTimersByTime(10 * 60 * 1000)
      await nextTick()
      expect(result.showWarning).toBe(true)

      // User activity
      window.dispatchEvent(new Event('click'))
      await nextTick()

      expect(result.showWarning).toBe(false)

      wrapper.unmount()
    })
  })

  describe('cleanup', () => {
    it('should cleanup event listeners on unmount', () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      wrapper.unmount()

      expect(console.info).toHaveBeenCalledWith(
        '[SessionTimeout] Cleaning up session timeout tracking'
      )
      expect(removeEventListenerSpy).toHaveBeenCalledWith('click', expect.any(Function))
      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function))
    })

    it('should cleanup API interceptor on unmount', () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      const wrapper = mount(TestComponent, { global: { plugins: [pinia] } })
      wrapper.unmount()

      expect(apiClient.interceptors.response.eject).toHaveBeenCalledWith(1)
    })
  })
})
