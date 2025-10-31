import { useToast as useVueToast } from 'vue-toastification'
import type { ToastOptions } from 'vue-toastification/dist/types/types'
import { h, type Component } from 'vue'

/**
 * Extended toast interface with runtime methods not in TypeScript types
 */
interface ExtendedToast {
  success: (message: unknown, options?: Record<string, unknown>) => void
  dismiss: (toastId: string) => void
}

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
  const toast = useVueToast() as unknown as ExtendedToast

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
                  toast.dismiss(toastId)
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

      toast.success(content, {
        ...toastOptions,
        ...(toastId && { toastId }),
      })
    } else {
      toast.success(message, {
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

    toast.success(content, {
      timeout: options?.timeout || 5000, // 5s for important actions with context
      closeButton: false,
      icon: true,
      toastId: uniqueId, // Unique ID prevents deduplication and caching
    })
  }

  /**
   * Show error toast with optional request ID for debugging
   *
   * @param message - Error message to display
   * @param requestId - Optional request ID from API error response
   * @param options - Additional options like timeout
   */
  function showError(
    message: string,
    requestId?: string,
    options?: { timeout?: number }
  ) {
    if (requestId) {
      // Create custom error content with request ID
      const content = h('div', { class: 'flex flex-col gap-2 w-full' }, [
        h('span', { class: 'font-medium' }, message),
        h('div', { class: 'flex items-center gap-2 text-xs' }, [
          h('span', { class: 'text-red-200' }, 'Request ID:'),
          h(
            'code',
            {
              class:
                'bg-red-900 bg-opacity-30 px-2 py-0.5 rounded font-mono text-red-100',
            },
            requestId
          ),
          h(
            'button',
            {
              onClick: async () => {
                try {
                  await navigator.clipboard.writeText(requestId)
                  // Show brief feedback toast
                  toast.success('Request ID copied', {
                    timeout: 2000,
                    icon: false,
                  })
                } catch (err) {
                  console.error('Failed to copy request ID:', err)
                }
              },
              class:
                'text-red-200 hover:text-red-100 underline focus:outline-none focus:ring-2 focus:ring-red-200 focus:ring-offset-2 focus:ring-offset-red-600 rounded px-1',
              type: 'button',
            },
            'Copy'
          ),
        ]),
      ])

      toast.error(content, {
        timeout: options?.timeout || 0, // Don't auto-dismiss errors with request IDs
        icon: true,
      })
    } else {
      // Simple error without request ID
      toast.error(message, {
        timeout: options?.timeout || 6000,
        icon: true,
      })
    }
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
   * Show rate limit error toast with countdown timer
   * Special handling for 429 Too Many Requests responses
   *
   * @param message - Rate limit message (e.g., "Too many requests")
   * @param endpoint - API endpoint that was rate limited
   * @param retryAfter - Seconds until rate limit expires
   * @param requestId - Optional request ID for debugging
   */
  function showRateLimitError(
    message: string,
    endpoint: string,
    retryAfter: number,
    requestId?: string
  ) {
    // Format endpoint for display (remove /api/v1/ prefix and show last segment)
    const endpointDisplay = endpoint.split('/').filter(Boolean).pop() || endpoint

    // Create custom rate limit content with countdown and endpoint info
    const content = h('div', { class: 'flex flex-col gap-2 w-full' }, [
      h('div', { class: 'flex items-center gap-2' }, [
        h(
          'svg',
          {
            class: 'w-5 h-5 flex-shrink-0',
            fill: 'none',
            stroke: 'currentColor',
            viewBox: '0 0 24 24',
          },
          h('path', {
            'stroke-linecap': 'round',
            'stroke-linejoin': 'round',
            'stroke-width': '2',
            d: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
          })
        ),
        h('span', { class: 'font-medium' }, message),
      ]),
      h('div', { class: 'flex items-center gap-2 text-sm opacity-90' }, [
        h('span', {}, `Endpoint: ${endpointDisplay}`),
        h('span', { class: 'text-xs' }, '•'),
        h('span', {}, `Wait ${retryAfter}s`),
      ]),
      requestId
        ? h('div', { class: 'flex items-center gap-2 text-xs mt-1' }, [
            h('span', { class: 'opacity-75' }, 'Request ID:'),
            h(
              'code',
              {
                class:
                  'bg-yellow-900 bg-opacity-30 px-2 py-0.5 rounded font-mono opacity-90',
              },
              requestId
            ),
            h(
              'button',
              {
                onClick: async () => {
                  try {
                    await navigator.clipboard.writeText(requestId)
                    toast.success('Request ID copied', {
                      timeout: 2000,
                      icon: false,
                    })
                  } catch (err) {
                    console.error('Failed to copy request ID:', err)
                  }
                },
                class:
                  'opacity-75 hover:opacity-100 underline focus:outline-none focus:ring-2 focus:ring-yellow-200 focus:ring-offset-2 focus:ring-offset-yellow-600 rounded px-1',
                type: 'button',
              },
              'Copy'
            ),
          ])
        : null,
    ])

    toast.warning(content, {
      timeout: retryAfter * 1000, // Auto-dismiss after cooldown
      icon: false, // Custom icon in content
      closeButton: true,
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
    showRateLimitError,
  }
}
