import { ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { useAppointmentsStore } from '@/stores/appointments'
import { useScreenReader } from '@/composables/useScreenReader'

/**
 * Composable for auto-saving appointment changes
 *
 * Provides:
 * - Debounced save on blur (500ms for textarea, immediate for other fields)
 * - Save status indicators (saving, saved, error)
 * - Automatic screen reader announcements
 *
 * TODO: Implement optimistic locking with If-Unmodified-Since header
 * for concurrent edit detection
 *
 * Usage:
 *   const { isSaving, lastSaved, saveError, saveField } = useAppointmentAutoSave(appointmentId)
 *   await saveField('notes', 'Updated notes')
 */
export function useAppointmentAutoSave(appointmentId: string) {
  const appointmentsStore = useAppointmentsStore()
  const isSaving = ref(false)
  const lastSaved = ref<Date | null>(null)
  const saveError = ref<string | null>(null)
  const { announce } = useScreenReader()

  /**
   * Debounced save function (500ms delay)
   * Used for textarea fields to avoid excessive API calls while typing
   */
  const debouncedSave = useDebounceFn(async (field: string, value: any) => {
    await performSave(field, value)
  }, 500)

  /**
   * Immediate save function
   * Used for select, date, and other non-text fields
   */
  async function immediateSave(field: string, value: any) {
    await performSave(field, value)
  }

  /**
   * Perform the actual save operation using the appointments store
   * This ensures the local state is updated immediately
   */
  async function performSave(field: string, value: any) {
    isSaving.value = true
    saveError.value = null

    try {
      // Use the store's updateAppointment method to update both API and local state
      await appointmentsStore.updateAppointment(appointmentId, {
        [field]: value,
      })

      lastSaved.value = new Date()
      announce('Saved')
    } catch (error: any) {
      console.error(`Failed to save ${field}:`, error)

      // Check for conflict (412 Precondition Failed for optimistic locking)
      if (error.response?.status === 412) {
        saveError.value = 'Someone else modified this appointment. Please refresh.'
        announce('Save failed: Conflict detected')
      } else {
        saveError.value = `Failed to save ${field}`
        announce(`Failed to save ${field}`)
      }

      throw error
    } finally {
      isSaving.value = false
    }
  }

  /**
   * Save a field with automatic debouncing based on field type
   *
   * @param field - Field name to save
   * @param value - New value
   * @param debounce - Whether to debounce the save (true for textarea, false for others)
   */
  async function saveField(field: string, value: any, debounce = false) {
    if (debounce) {
      await debouncedSave(field, value)
    } else {
      await immediateSave(field, value)
    }
  }

  /**
   * Clear any save errors
   */
  function clearError() {
    saveError.value = null
  }

  return {
    // State
    isSaving,
    lastSaved,
    saveError,

    // Methods
    saveField,
    clearError,
  }
}
