import { onMounted, onUnmounted, type Ref } from 'vue'
import type { ViewType, AppointmentListItem } from '@/types/calendar'

export interface KeyboardShortcutHandlers {
  onToday: () => void
  onPrevious: () => void
  onNext: () => void
  onChangeView: (view: ViewType) => void
  onCreateAppointment?: () => void
  selectedAppointment: Ref<AppointmentListItem | null>
}

/**
 * Composable for keyboard shortcuts in calendar view
 *
 * Shortcuts:
 * - t: Go to today
 * - w: Switch to week view
 * - d: Switch to day view
 * - m: Switch to month view
 * - ⌘N/Ctrl+N: Create new appointment
 * - Arrow Left: Previous period
 * - Arrow Right: Next period
 * - Escape: Close appointment details modal
 */
export function useCalendarKeyboardShortcuts(handlers: KeyboardShortcutHandlers) {
  /**
   * Keyboard shortcuts handler
   */
  function handleKeyboardShortcuts(event: KeyboardEvent) {
    // Don't trigger if user is typing in an input
    if (
      event.target instanceof HTMLInputElement ||
      event.target instanceof HTMLTextAreaElement
    ) {
      return
    }

    switch (event.key) {
      case 't':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onToday()
        }
        break
      case 'w':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onChangeView('timeGridWeek')
        }
        break
      case 'd':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onChangeView('timeGridDay')
        }
        break
      case 'm':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onChangeView('dayGridMonth')
        }
        break
      case 'n':
        if (event.metaKey || event.ctrlKey) {
          event.preventDefault()
          handlers.onCreateAppointment?.()
        }
        break
      case 'ArrowLeft':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onPrevious()
        }
        break
      case 'ArrowRight':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onNext()
        }
        break
      case 'Escape':
        if (handlers.selectedAppointment.value) {
          handlers.selectedAppointment.value = null
        }
        break
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeyboardShortcuts)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyboardShortcuts)
  })
}
