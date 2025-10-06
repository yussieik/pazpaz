import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { useAppointmentDrag } from './useAppointmentDrag'
import type { AppointmentListItem } from '@/types/calendar'

// Mock the API client
vi.mock('@/api/client', () => ({
  checkAppointmentConflicts: vi.fn().mockResolvedValue({
    has_conflict: false,
    conflicting_appointments: [],
  }),
}))

describe('useAppointmentDrag', () => {
  let appointments: ReturnType<typeof ref<AppointmentListItem[]>>
  let onReschedule: ReturnType<typeof vi.fn>

  beforeEach(() => {
    appointments = ref([
      {
        id: 'apt-1',
        workspace_id: 'ws-1',
        client_id: 'client-1',
        scheduled_start: '2024-01-15T10:00:00Z',
        scheduled_end: '2024-01-15T11:00:00Z',
        location_type: 'clinic',
        location_details: null,
        status: 'scheduled',
        notes: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        client: {
          id: 'client-1',
          first_name: 'John',
          last_name: 'Doe',
          full_name: 'John Doe',
        },
      },
    ])

    onReschedule = vi.fn()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('keyboard navigation', () => {
    it('activates keyboard reschedule mode', () => {
      const { activateKeyboardReschedule, isKeyboardRescheduleActive } =
        useAppointmentDrag(appointments, onReschedule)

      expect(isKeyboardRescheduleActive.value).toBe(false)

      activateKeyboardReschedule('apt-1')

      expect(isKeyboardRescheduleActive.value).toBe(true)
    })

    it('navigates up (15 minutes earlier)', () => {
      const { activateKeyboardReschedule, handleKeyboardNavigation, keyboardState } =
        useAppointmentDrag(appointments, onReschedule)

      activateKeyboardReschedule('apt-1')
      const originalStart = new Date(keyboardState.value.currentStart!)

      handleKeyboardNavigation('ArrowUp')

      const newStart = new Date(keyboardState.value.currentStart!)
      const diff = originalStart.getTime() - newStart.getTime()
      expect(diff).toBe(15 * 60 * 1000) // 15 minutes
    })

    it('navigates down (15 minutes later)', () => {
      const { activateKeyboardReschedule, handleKeyboardNavigation, keyboardState } =
        useAppointmentDrag(appointments, onReschedule)

      activateKeyboardReschedule('apt-1')
      const originalStart = new Date(keyboardState.value.currentStart!)

      handleKeyboardNavigation('ArrowDown')

      const newStart = new Date(keyboardState.value.currentStart!)
      const diff = newStart.getTime() - originalStart.getTime()
      expect(diff).toBe(15 * 60 * 1000) // 15 minutes
    })

    it('navigates left (1 day earlier)', () => {
      const { activateKeyboardReschedule, handleKeyboardNavigation, keyboardState } =
        useAppointmentDrag(appointments, onReschedule)

      activateKeyboardReschedule('apt-1')
      const originalStart = new Date(keyboardState.value.currentStart!)

      handleKeyboardNavigation('ArrowLeft')

      const newStart = new Date(keyboardState.value.currentStart!)
      expect(newStart.getDate()).toBe(originalStart.getDate() - 1)
    })

    it('navigates right (1 day later)', () => {
      const { activateKeyboardReschedule, handleKeyboardNavigation, keyboardState } =
        useAppointmentDrag(appointments, onReschedule)

      activateKeyboardReschedule('apt-1')
      const originalStart = new Date(keyboardState.value.currentStart!)

      handleKeyboardNavigation('ArrowRight')

      const newStart = new Date(keyboardState.value.currentStart!)
      expect(newStart.getDate()).toBe(originalStart.getDate() + 1)
    })

    it('confirms reschedule and calls onReschedule callback', async () => {
      const {
        activateKeyboardReschedule,
        handleKeyboardNavigation,
        confirmKeyboardReschedule,
      } = useAppointmentDrag(appointments, onReschedule)

      activateKeyboardReschedule('apt-1')
      handleKeyboardNavigation('ArrowDown') // Move 15 minutes later

      await confirmKeyboardReschedule()

      expect(onReschedule).toHaveBeenCalledWith(
        'apt-1',
        expect.any(Date),
        expect.any(Date),
        false
      )
    })

    it('cancels reschedule and resets state', () => {
      const {
        activateKeyboardReschedule,
        cancelKeyboardReschedule,
        isKeyboardRescheduleActive,
      } = useAppointmentDrag(appointments, onReschedule)

      activateKeyboardReschedule('apt-1')
      expect(isKeyboardRescheduleActive.value).toBe(true)

      cancelKeyboardReschedule()
      expect(isKeyboardRescheduleActive.value).toBe(false)
    })
  })

  describe('drag state', () => {
    it('initializes with dragging false', () => {
      const { isDragging } = useAppointmentDrag(appointments, onReschedule)
      expect(isDragging.value).toBe(false)
    })

    it('provides time range formatting', () => {
      const { activateKeyboardReschedule, keyboardTimeRange } = useAppointmentDrag(
        appointments,
        onReschedule
      )

      activateKeyboardReschedule('apt-1')
      expect(keyboardTimeRange.value).toMatch(/\d+:\d+ (AM|PM) → \d+:\d+ (AM|PM)/)
    })
  })

  describe('duration preservation', () => {
    it('preserves appointment duration when navigating', () => {
      const { activateKeyboardReschedule, handleKeyboardNavigation, keyboardState } =
        useAppointmentDrag(appointments, onReschedule)

      activateKeyboardReschedule('apt-1')

      const originalDuration =
        new Date(keyboardState.value.currentEnd!).getTime() -
        new Date(keyboardState.value.currentStart!).getTime()

      handleKeyboardNavigation('ArrowDown')

      const newDuration =
        new Date(keyboardState.value.currentEnd!).getTime() -
        new Date(keyboardState.value.currentStart!).getTime()

      expect(newDuration).toBe(originalDuration)
    })
  })

  describe('cleanup', () => {
    it('provides cleanup function', () => {
      const { cleanup } = useAppointmentDrag(appointments, onReschedule)
      expect(cleanup).toBeDefined()
      expect(typeof cleanup).toBe('function')
    })
  })
})
