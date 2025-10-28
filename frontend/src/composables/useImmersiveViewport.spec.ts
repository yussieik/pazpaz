import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { useImmersiveViewport } from './useImmersiveViewport'

// Create a test component that uses the composable
const TestComponent = defineComponent({
  setup() {
    useImmersiveViewport()
    return {}
  },
  template: '<div>Test</div>',
})

describe('useImmersiveViewport', () => {
  let setPropertySpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // Spy on CSS custom property setter
    setPropertySpy = vi.spyOn(document.documentElement.style, 'setProperty')
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('should set --app-height CSS variable on mount', () => {
    mount(TestComponent)

    expect(setPropertySpy).toHaveBeenCalledWith(
      '--app-height',
      expect.stringMatching(/^\d+(\.\d+)?px$/)
    )
  })

  it('should update --app-height on window resize', async () => {
    mount(TestComponent)

    setPropertySpy.mockClear()

    // Trigger resize event
    window.dispatchEvent(new Event('resize'))

    expect(setPropertySpy).toHaveBeenCalledWith(
      '--app-height',
      expect.stringMatching(/^\d+(\.\d+)?px$/)
    )
  })

  it('should update --app-height on orientation change', async () => {
    mount(TestComponent)

    setPropertySpy.mockClear()

    // Trigger orientationchange event
    window.dispatchEvent(new Event('orientationchange'))

    // Wait for setTimeout to complete
    await new Promise((resolve) => setTimeout(resolve, 150))

    expect(setPropertySpy).toHaveBeenCalledWith(
      '--app-height',
      expect.stringMatching(/^\d+(\.\d+)?px$/)
    )
  })

  it('should calculate viewport height correctly', () => {
    // Mock window.innerHeight
    Object.defineProperty(window, 'innerHeight', {
      writable: true,
      configurable: true,
      value: 800,
    })

    mount(TestComponent)

    expect(setPropertySpy).toHaveBeenCalledWith('--app-height', '800px')
  })

  it('should not throw errors when unmounted', () => {
    const wrapper = mount(TestComponent)

    expect(() => {
      wrapper.unmount()
    }).not.toThrow()
  })

  it('should clean up event listeners on unmount', () => {
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mount(TestComponent)

    wrapper.unmount()

    expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      'orientationchange',
      expect.any(Function)
    )
  })
})
