import { describe, it, expect } from 'vitest'
import {
  roundToNearest15Minutes,
  getAppointmentDuration,
  calculateEndTime,
  formatTimeRange,
  formatDateAndTime,
  checkTimeOverlap,
  crossesDayBoundary,
  addMinutes,
  addDays,
  isWithinBusinessHours,
} from './dragHelpers'

describe('dragHelpers', () => {
  describe('roundToNearest15Minutes', () => {
    it('rounds down to nearest 15-minute increment', () => {
      const date = new Date('2024-01-15T10:07:00')
      const rounded = roundToNearest15Minutes(date)
      expect(rounded.getMinutes()).toBe(0)
    })

    it('rounds up to nearest 15-minute increment', () => {
      const date = new Date('2024-01-15T10:08:00')
      const rounded = roundToNearest15Minutes(date)
      expect(rounded.getMinutes()).toBe(15)
    })

    it('keeps exact 15-minute increments unchanged', () => {
      const date = new Date('2024-01-15T10:15:00')
      const rounded = roundToNearest15Minutes(date)
      expect(rounded.getMinutes()).toBe(15)
    })

    it('rounds to hour boundaries correctly', () => {
      const date = new Date('2024-01-15T09:53:00')
      const rounded = roundToNearest15Minutes(date)
      expect(rounded.getHours()).toBe(10)
      expect(rounded.getMinutes()).toBe(0)
    })
  })

  describe('getAppointmentDuration', () => {
    it('calculates duration in milliseconds for Date objects', () => {
      const start = new Date('2024-01-15T10:00:00')
      const end = new Date('2024-01-15T11:30:00')
      const duration = getAppointmentDuration(start, end)
      expect(duration).toBe(90 * 60 * 1000) // 90 minutes
    })

    it('calculates duration for ISO strings', () => {
      const start = '2024-01-15T10:00:00Z'
      const end = '2024-01-15T11:30:00Z'
      const duration = getAppointmentDuration(start, end)
      expect(duration).toBe(90 * 60 * 1000)
    })
  })

  describe('calculateEndTime', () => {
    it('adds duration to start time correctly', () => {
      const start = new Date('2024-01-15T10:00:00')
      const duration = 60 * 60 * 1000 // 1 hour
      const end = calculateEndTime(start, duration)
      expect(end.getHours()).toBe(11)
      expect(end.getMinutes()).toBe(0)
    })

    it('handles durations that cross day boundaries', () => {
      const start = new Date('2024-01-15T23:30:00')
      const duration = 2 * 60 * 60 * 1000 // 2 hours
      const end = calculateEndTime(start, duration)
      expect(end.getDate()).toBe(16)
      expect(end.getHours()).toBe(1)
      expect(end.getMinutes()).toBe(30)
    })
  })

  describe('formatTimeRange', () => {
    it('formats time range with AM/PM', () => {
      const start = new Date('2024-01-15T10:00:00')
      const end = new Date('2024-01-15T11:30:00')
      const formatted = formatTimeRange(start, end)
      expect(formatted).toBe('10:00 AM → 11:30 AM')
    })

    it('formats time range crossing noon', () => {
      const start = new Date('2024-01-15T11:00:00')
      const end = new Date('2024-01-15T13:00:00')
      const formatted = formatTimeRange(start, end)
      expect(formatted).toBe('11:00 AM → 1:00 PM')
    })

    it('handles ISO strings', () => {
      const formatted = formatTimeRange('2024-01-15T14:30:00Z', '2024-01-15T16:00:00Z')
      expect(formatted).toContain('→')
    })
  })

  describe('formatDateAndTime', () => {
    it('formats date and time with day name', () => {
      const date = new Date('2024-01-15T14:30:00') // Monday
      const formatted = formatDateAndTime(date)
      expect(formatted).toMatch(/Mon, Jan 15 • \d+:\d+ (AM|PM)/)
    })
  })

  describe('checkTimeOverlap', () => {
    it('detects overlapping appointments', () => {
      const start1 = new Date('2024-01-15T10:00:00')
      const end1 = new Date('2024-01-15T11:00:00')
      const start2 = new Date('2024-01-15T10:30:00')
      const end2 = new Date('2024-01-15T11:30:00')

      expect(checkTimeOverlap(start1, end1, start2, end2)).toBe(true)
    })

    it('returns false for back-to-back appointments', () => {
      const start1 = new Date('2024-01-15T10:00:00')
      const end1 = new Date('2024-01-15T11:00:00')
      const start2 = new Date('2024-01-15T11:00:00')
      const end2 = new Date('2024-01-15T12:00:00')

      expect(checkTimeOverlap(start1, end1, start2, end2)).toBe(false)
    })

    it('returns false for non-overlapping appointments', () => {
      const start1 = new Date('2024-01-15T10:00:00')
      const end1 = new Date('2024-01-15T11:00:00')
      const start2 = new Date('2024-01-15T12:00:00')
      const end2 = new Date('2024-01-15T13:00:00')

      expect(checkTimeOverlap(start1, end1, start2, end2)).toBe(false)
    })

    it('detects complete containment', () => {
      const start1 = new Date('2024-01-15T10:00:00')
      const end1 = new Date('2024-01-15T12:00:00')
      const start2 = new Date('2024-01-15T10:30:00')
      const end2 = new Date('2024-01-15T11:00:00')

      expect(checkTimeOverlap(start1, end1, start2, end2)).toBe(true)
    })
  })

  describe('crossesDayBoundary', () => {
    it('returns true when dates are on different days', () => {
      const date1 = new Date('2024-01-15T10:00:00')
      const date2 = new Date('2024-01-16T10:00:00')
      expect(crossesDayBoundary(date1, date2)).toBe(true)
    })

    it('returns false when dates are on same day', () => {
      const date1 = new Date('2024-01-15T10:00:00')
      const date2 = new Date('2024-01-15T15:00:00')
      expect(crossesDayBoundary(date1, date2)).toBe(false)
    })

    it('returns true when months are different', () => {
      const date1 = new Date('2024-01-31T10:00:00')
      const date2 = new Date('2024-02-01T10:00:00')
      expect(crossesDayBoundary(date1, date2)).toBe(true)
    })
  })

  describe('addMinutes', () => {
    it('adds positive minutes correctly', () => {
      const date = new Date('2024-01-15T10:00:00')
      const result = addMinutes(date, 30)
      expect(result.getHours()).toBe(10)
      expect(result.getMinutes()).toBe(30)
    })

    it('subtracts negative minutes correctly', () => {
      const date = new Date('2024-01-15T10:30:00')
      const result = addMinutes(date, -15)
      expect(result.getHours()).toBe(10)
      expect(result.getMinutes()).toBe(15)
    })

    it('handles hour boundaries', () => {
      const date = new Date('2024-01-15T10:50:00')
      const result = addMinutes(date, 20)
      expect(result.getHours()).toBe(11)
      expect(result.getMinutes()).toBe(10)
    })
  })

  describe('addDays', () => {
    it('adds positive days correctly', () => {
      const date = new Date('2024-01-15T10:00:00')
      const result = addDays(date, 1)
      expect(result.getDate()).toBe(16)
    })

    it('subtracts negative days correctly', () => {
      const date = new Date('2024-01-15T10:00:00')
      const result = addDays(date, -1)
      expect(result.getDate()).toBe(14)
    })

    it('handles month boundaries', () => {
      const date = new Date('2024-01-31T10:00:00')
      const result = addDays(date, 1)
      expect(result.getMonth()).toBe(1) // February
      expect(result.getDate()).toBe(1)
    })
  })

  describe('isWithinBusinessHours', () => {
    it('returns true for 9 AM', () => {
      const date = new Date('2024-01-15T09:00:00')
      expect(isWithinBusinessHours(date)).toBe(true)
    })

    it('returns true for 5 PM', () => {
      const date = new Date('2024-01-15T17:00:00')
      expect(isWithinBusinessHours(date)).toBe(true)
    })

    it('returns false for 7 AM', () => {
      const date = new Date('2024-01-15T07:00:00')
      expect(isWithinBusinessHours(date)).toBe(false)
    })

    it('returns false for 6 PM', () => {
      const date = new Date('2024-01-15T18:00:00')
      expect(isWithinBusinessHours(date)).toBe(false)
    })
  })
})
