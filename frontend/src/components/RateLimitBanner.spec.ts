import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RateLimitBanner from './RateLimitBanner.vue'
import { useRateLimitStore } from '@/stores/rateLimit'

/**
 * Rate Limit Banner Component Tests
 *
 * Tests the global banner that displays when API endpoints are rate limited.
 * Verifies:
 * - Banner shows/hides based on rate limit state
 * - Countdown timers update correctly
 * - Multiple rate limits displayed simultaneously
 * - Endpoint names formatted for display
 * - Accessibility attributes present
 */

describe('RateLimitBanner', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('visibility', () => {
    it('hides banner when no rate limits', () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      expect(store.hasActiveRateLimits).toBe(false)
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    })

    it('shows banner when rate limit is active', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    })

    it('hides banner when rate limit expires', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 2)
      await wrapper.vm.$nextTick()

      expect(wrapper.find('[role="alert"]').exists()).toBe(true)

      // Advance past expiry
      vi.advanceTimersByTime(2100)
      await wrapper.vm.$nextTick()

      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    })

    it('shows banner again for new rate limit after clearing', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)

      store.clearRateLimit('/api/v1/auth/login')
      await wrapper.vm.$nextTick()
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)

      store.setRateLimit('/api/v1/clients', 30)
      await wrapper.vm.$nextTick()
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    })
  })

  describe('content and messaging', () => {
    it('displays rate limit active message', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Rate limit active')
    })

    it('displays explanation message', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('sending requests too quickly')
    })

    it('displays warning icon', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const icon = wrapper.find('svg')
      expect(icon.exists()).toBe(true)
      expect(icon.classes()).toContain('text-yellow-600')
    })
  })

  describe('countdown timer', () => {
    it('displays countdown timer', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/clients', 45)
      await wrapper.vm.$nextTick()

      // Advance to trigger the first interval callback (setInterval runs every 1000ms)
      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()

      // Should show countdown (45s or 44s depending on timing)
      expect(wrapper.text()).toMatch(/4[45]s/)
    })

    it('updates countdown every second', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/clients', 10)
      await wrapper.vm.$nextTick()

      // First interval callback (1s has now elapsed, showing 9s)
      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()

      const initialText = wrapper.text()
      expect(initialText).toMatch(/[89]s/) // Should show 9s or close

      // Advance 3 more seconds (total 4 seconds elapsed, should show 6s)
      vi.advanceTimersByTime(3000)
      await wrapper.vm.$nextTick()

      const updatedText = wrapper.text()
      // Should now show 6s or 5s (10 - 4 = 6)
      expect(updatedText).toMatch(/[56]s/)
    })

    it('counts down to 0', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/clients', 3)
      await wrapper.vm.$nextTick()

      // First interval callback (after 1s, should show 2s remaining)
      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toMatch(/[12]s/)

      // After 2s total (1s remaining)
      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toMatch(/[01]s/)

      // After 3s total (0s remaining or expired)
      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()
      // Banner may still be visible briefly at 0s or may have disappeared

      // After full expiry + auto-clear timeout, banner should definitely disappear
      vi.advanceTimersByTime(200)
      await wrapper.vm.$nextTick()
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    })
  })

  describe('endpoint display', () => {
    it('formats endpoint names for display', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 30)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('login')
    })

    it('extracts last segment from complex endpoint paths', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/appointments/conflicts', 30)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('conflicts')
    })

    it('handles simple endpoint paths', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/clients', 30)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('clients')
    })
  })

  describe('multiple rate limits', () => {
    it('displays multiple rate limits simultaneously', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      store.setRateLimit('/api/v1/clients', 30)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('login')
      expect(wrapper.text()).toContain('clients')
    })

    it('shows separate countdowns for each endpoint', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      store.setRateLimit('/api/v1/clients', 30)
      await wrapper.vm.$nextTick()

      // First interval callback
      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()

      const text = wrapper.text()
      // Should show both 60s and 30s (or close to it)
      expect(text).toMatch(/[56][0-9]s/)
      expect(text).toMatch(/[23][0-9]s/)
    })

    it('removes individual rate limits as they expire', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 5)
      store.setRateLimit('/api/v1/clients', 2)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('login')
      expect(wrapper.text()).toContain('clients')

      // Advance past clients expiry (2s)
      vi.advanceTimersByTime(2100)
      await wrapper.vm.$nextTick()

      // clients should be gone, login still visible
      expect(wrapper.text()).toContain('login')
      expect(wrapper.text()).not.toContain('clients')

      // Advance past login expiry
      vi.advanceTimersByTime(3000)
      await wrapper.vm.$nextTick()

      // Banner should be hidden
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    })
  })

  describe('accessibility', () => {
    it('has role="alert" for screen readers', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const alert = wrapper.find('[role="alert"]')
      expect(alert.exists()).toBe(true)
    })

    it('has aria-live="polite" for updates', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const alert = wrapper.find('[aria-live="polite"]')
      expect(alert.exists()).toBe(true)
    })

    it('has aria-atomic for complete announcements', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const alert = wrapper.find('[aria-atomic="true"]')
      expect(alert.exists()).toBe(true)
    })

    it('has aria-hidden on decorative icon', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const icon = wrapper.find('svg')
      expect(icon.attributes('aria-hidden')).toBe('true')
    })

    it('has aria-label on countdown timer', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const countdown = wrapper.find('.tabular-nums')
      expect(countdown.attributes('aria-label')).toMatch(/\d+ seconds remaining/)
    })
  })

  describe('styling', () => {
    it('has warning color scheme', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const banner = wrapper.find('[role="alert"]')
      expect(banner.classes()).toContain('bg-yellow-50')
      expect(banner.classes()).toContain('border-yellow-200')
    })

    it('is fixed at top of viewport', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const banner = wrapper.find('[role="alert"]')
      expect(banner.classes()).toContain('fixed')
      expect(banner.classes()).toContain('top-0')
    })

    it('has high z-index to appear above content', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/auth/login', 60)
      await wrapper.vm.$nextTick()

      const banner = wrapper.find('[role="alert"]')
      expect(banner.classes()).toContain('z-40')
    })
  })

  describe('lifecycle', () => {
    it('starts countdown interval on mount', async () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/clients', 10)
      await wrapper.vm.$nextTick()

      // First interval callback (1s has elapsed, 9s remaining)
      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toMatch(/[89]s/) // Should show 9s or close

      vi.advanceTimersByTime(1000)
      await wrapper.vm.$nextTick()

      // Countdown should update (2 seconds have passed, 8s remaining)
      expect(wrapper.text()).toMatch(/[78]s/)
    })

    it('cleans up interval on unmount', () => {
      const wrapper = mount(RateLimitBanner)
      const store = useRateLimitStore()

      store.setRateLimit('/api/v1/clients', 60)

      wrapper.unmount()

      // Should not throw errors after unmount
      expect(() => {
        vi.advanceTimersByTime(5000)
      }).not.toThrow()
    })
  })
})
