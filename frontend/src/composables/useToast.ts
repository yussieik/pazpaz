import { useToast as useVueToast } from 'vue-toastification'
import type { ToastOptions } from 'vue-toastification/dist/types/types'
import { h, type Component } from 'vue'

/**
 * Toast utility composable for PazPaz
 *
 * Provides unified toast notification interface with:
 * - Success/error/info/warning messages
 * - Undo functionality for reversible actions
 * - Custom action buttons
 * - Rich appointment notifications with context
 * - Accessible (screen reader announcements via ARIA)
 *
 * Timing standards:
 * - Simple success: 3000ms
 * - Success with action: 5000ms
 * - Appointment success: 5000ms
 * - Error: 6000ms
 */
export function useToast() {
  const toast = useVueToast()

  /**
   * Show success toast with optional undo action
   */
  function showSuccess(
    message: string,
    options?: {
      action?: {
        label: string
        onClick: () => void
      }
      timeout?: number
      toastId?: string | number
    }
  ) {
    const toastOptions: ToastOptions = {
      timeout: options?.timeout || (options?.action ? 5000 : 3000),
      closeButton: false,
      icon: true,
    }

    // Store toastId separately since it's not in TypeScript types
    const toastId = options?.toastId

    if (options?.action) {
      // Custom component with action button
      const content = h(
        'div',
        { class: 'flex items-center justify-between gap-3 w-full' },
        [
          h('span', {}, message),
          h(
            'button',
            {
              onClick: (e: Event) => {
                e.stopPropagation()
                // Find the toast element for immediate visual removal
                const toastElement = (e.target as HTMLElement).closest(
                  '.Vue-Toastification__toast'
                )
                if (toastElement) {
                  // Set opacity to 0 for instant visual feedback
                  ;(toastElement as HTMLElement).style.opacity = '0'
                  ;(toastElement as HTMLElement).style.transition = 'opacity 0.1s ease'
                }
                // Dismiss using API to maintain state consistency
                if (toastId) {
                  ;(toast as any).dismiss(toastId)
                }
                // Execute action
                options.action!.onClick()
              },
              class:
                'text-xs font-medium underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-emerald-600 rounded px-2 py-1',
            },
            options.action.label
          ),
        ]
      )

      // Cast to any to work around vue-toastification type limitations
      // toastId is a valid runtime option even if not in TypeScript types
      ;(toast as any).success(content, {
        ...toastOptions,
        ...(toastId && { toastId }),
      })
    } else {
      // Cast to any to work around vue-toastification type limitations
      // toastId is a valid runtime option even if not in TypeScript types
      ;(toast as any).success(message, {
        ...toastOptions,
        ...(toastId && { toastId }),
      })
    }
  }

  /**
   * Show appointment success toast with rich context
   * Used for important actions like appointment creation/scheduling
   *
   * @param message - Main message (e.g., "Appointment created")
   * @param options - Additional context and actions
   * @param options.clientName - Client name to display
   * @param options.datetime - Formatted datetime string
   * @param options.actions - Action buttons (e.g., View Details, View in Calendar)
   * @param options.timeout - Custom timeout (defaults to 5000ms)
   */
  async function showAppointmentSuccess(
    message: string,
    options?: {
      clientName?: string
      datetime?: string
      actions?: Array<{ label: string; onClick: () => void }>
      timeout?: number
    }
  ) {
    // Dynamically import the AppointmentToastContent component
    const { default: AppointmentToastContent } = await import(
      '@/components/common/AppointmentToastContent.vue'
    )

    const content = h(AppointmentToastContent as Component, {
      message,
      clientName: options?.clientName,
      datetime: options?.datetime,
      actions: options?.actions,
    })

    // Generate unique ID to prevent toast caching
    const uniqueId = `${message}-${Date.now()}-${Math.random()}`

    // Cast to any to work around vue-toastification type limitations
    // toastId is a valid runtime option even if not in TypeScript types
    ;(toast as any).success(content, {
      timeout: options?.timeout || 5000, // 5s for important actions with context
      closeButton: false,
      icon: true,
      toastId: uniqueId, // Unique ID prevents deduplication and caching
    })
  }

  /**
   * Show error toast
   */
  function showError(message: string, options?: { timeout?: number }) {
    toast.error(message, {
      timeout: options?.timeout || 6000,
      icon: true,
    })
  }

  /**
   * Show info toast
   */
  function showInfo(message: string, options?: { timeout?: number }) {
    toast.info(message, {
      timeout: options?.timeout || 3000,
      icon: true,
    })
  }

  /**
   * Show warning toast
   */
  function showWarning(message: string, options?: { timeout?: number }) {
    toast.warning(message, {
      timeout: options?.timeout || 4000,
      icon: true,
    })
  }

  /**
   * Show success toast with undo action
   * Used for reversible operations (reschedule, cancel, etc.)
   *
   * @param message - Success message (e.g., "Appointment rescheduled")
   * @param onUndo - Undo handler function
   * @param options - Additional options
   */
  function showSuccessWithUndo(
    message: string,
    onUndo: () => void,
    options?: {
      timeout?: number
    }
  ) {
    // Generate unique ID to prevent toast caching after dismissal
    // This ensures each action shows a toast, even if performed repeatedly
    const uniqueId = `${message}-${Date.now()}-${Math.random()}`

    showSuccess(message, {
      action: {
        label: 'Undo',
        onClick: onUndo,
      },
      timeout: options?.timeout || 5000, // 5s for undo actions
      toastId: uniqueId, // Unique ID prevents both deduplication and caching
    })
  }

  return {
    showSuccess,
    showAppointmentSuccess,
    showSuccessWithUndo,
    showError,
    showInfo,
    showWarning,
  }
}
