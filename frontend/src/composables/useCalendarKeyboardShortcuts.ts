import { onMounted, onUnmounted, type Ref } from 'vue'
import type { ViewType, AppointmentListItem } from '@/types/calendar'

export interface ToolbarButtonRefs {
  todayButton?: HTMLButtonElement
  previousButton?: HTMLButtonElement
  nextButton?: HTMLButtonElement
  weekButton?: HTMLButtonElement
  dayButton?: HTMLButtonElement
  monthButton?: HTMLButtonElement
}

export interface KeyboardShortcutHandlers {
  onToday: () => void
  onPrevious: () => void
  onNext: () => void
  onChangeView: (view: ViewType) => void
  onCreateAppointment?: () => void
  selectedAppointment: Ref<AppointmentListItem | null>
  buttonRefs?: Ref<ToolbarButtonRefs>
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
   * Triggers visual feedback by briefly focusing the button
   */
  function triggerButtonFeedback(button?: HTMLButtonElement) {
    if (!button) return
    button.focus()
    setTimeout(() => button.blur(), 150)
  }

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

    // Don't handle Escape if it's coming from within a modal
    // Modals have their own Escape handlers and we shouldn't interfere
    if (event.key === 'Escape') {
      const target = event.target as HTMLElement
      const isInsideModal = target.closest('[role="dialog"]') !== null

      if (isInsideModal) {
        return
      }
    }

    const buttonRefs = handlers.buttonRefs?.value

    switch (event.key) {
      case 't':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onToday()
          triggerButtonFeedback(buttonRefs?.todayButton)
        }
        break
      case 'w':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onChangeView('timeGridWeek')
          triggerButtonFeedback(buttonRefs?.weekButton)
        }
        break
      case 'd':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onChangeView('timeGridDay')
          triggerButtonFeedback(buttonRefs?.dayButton)
        }
        break
      case 'm':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onChangeView('dayGridMonth')
          triggerButtonFeedback(buttonRefs?.monthButton)
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
          triggerButtonFeedback(buttonRefs?.previousButton)
        }
        break
      case 'ArrowRight':
        if (!event.metaKey && !event.ctrlKey) {
          handlers.onNext()
          triggerButtonFeedback(buttonRefs?.nextButton)
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
