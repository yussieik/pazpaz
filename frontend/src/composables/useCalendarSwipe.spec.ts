import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useCalendarSwipe } from './useCalendarSwipe'

describe('useCalendarSwipe', () => {
  let targetRef: ReturnType<typeof ref<HTMLElement | null>>
  let onPrevious: ReturnType<typeof vi.fn>
  let onNext: ReturnType<typeof vi.fn>

  beforeEach(() => {
    targetRef = ref<HTMLElement | null>(document.createElement('div'))
    onPrevious = vi.fn()
    onNext = vi.fn()
  })

  it('should initialize without errors', () => {
    expect(() => {
      useCalendarSwipe(targetRef, onPrevious, onNext)
    }).not.toThrow()
  })

  it('should return direction object', () => {
    const result = useCalendarSwipe(targetRef, onPrevious, onNext)
    expect(result).toHaveProperty('direction')
  })

  it('should handle null target gracefully', () => {
    const nullRef = ref<HTMLElement | null>(null)
    expect(() => {
      useCalendarSwipe(nullRef, onPrevious, onNext)
    }).not.toThrow()
  })
})
