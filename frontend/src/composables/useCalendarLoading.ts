import { ref, watchEffect } from 'vue'
import { useAppointmentsStore } from '@/stores/appointments'

/**
 * Composable for managing debounced loading state
 *
 * Only shows loading indicator if request takes longer than 300ms
 * This prevents flash of loading state for fast network requests
 */
export function useCalendarLoading() {
  const appointmentsStore = useAppointmentsStore()
  const showLoadingSpinner = ref(false)
  let loadingDebounceTimer: ReturnType<typeof setTimeout> | null = null

  // Watch loading state and debounce the loading indicator
  watchEffect(() => {
    if (appointmentsStore.loading) {
      // Start debounce timer - only show spinner after 300ms
      loadingDebounceTimer = setTimeout(() => {
        showLoadingSpinner.value = true
      }, 300)
    } else {
      // Clear timer if loading finishes before 300ms
      if (loadingDebounceTimer) {
        clearTimeout(loadingDebounceTimer)
        loadingDebounceTimer = null
      }
      showLoadingSpinner.value = false
    }
  })

  return {
    showLoadingSpinner,
  }
}
