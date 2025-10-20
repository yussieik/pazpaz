/**
 * Attachment Rename Composable
 *
 * Provides inline file renaming functionality for both session-level
 * and client-level attachments.
 *
 * Features:
 * - Inline editing with keyboard shortcuts (F2, Enter, Esc)
 * - Client-side validation with instant feedback
 * - Loading states and error handling
 * - Success/error toast notifications
 * - Focus management for accessibility
 *
 * Usage:
 *   const { renameAttachment } = useAttachmentRename()
 *   await renameAttachment({ sessionId, clientId, attachmentId, newName })
 */

import { ref, type Ref } from 'vue'
import apiClient from '@/api/client'
import { useToast } from '@/composables/useToast'
import { validateFilename, sanitizeFilenameForRename } from '@/utils/filenameValidation'
import type { AttachmentResponse } from '@/types/attachments'

/**
 * Rename attachment options
 */
export interface RenameAttachmentOptions {
  /** Session ID (required for session-level files) */
  sessionId?: string
  /** Client ID (required for client-level files) */
  clientId?: string
  /** Attachment ID */
  attachmentId: string
  /** New filename (without extension - backend will preserve it) */
  newName: string
}

/**
 * Rename result
 */
export interface RenameResult {
  success: boolean
  data?: AttachmentResponse
  error?: string
}

/**
 * Edit state for a single attachment
 */
export interface EditState {
  isEditing: boolean
  editedName: string
  error: string | null
  isLoading: boolean
}

/**
 * Map of attachment IDs to their edit states
 */
export type EditStatesMap = Map<string, EditState>

export function useAttachmentRename() {
  const { showSuccess, showError } = useToast()

  /**
   * Edit states for all attachments (keyed by attachment ID)
   */
  const editStates: Ref<EditStatesMap> = ref(new Map())

  /**
   * Get or create edit state for an attachment
   */
  function getEditState(attachmentId: string): EditState {
    if (!editStates.value.has(attachmentId)) {
      editStates.value.set(attachmentId, {
        isEditing: false,
        editedName: '',
        error: null,
        isLoading: false,
      })
    }
    return editStates.value.get(attachmentId)!
  }

  /**
   * Enter rename mode for an attachment
   *
   * @param attachment - Attachment to rename
   * @param inputRef - Input element ref for focus management
   */
  function enterRenameMode(
    attachment: AttachmentResponse,
    inputRef?: Ref<HTMLInputElement | null>
  ) {
    const state = getEditState(attachment.id)
    state.isEditing = true
    state.editedName = sanitizeFilenameForRename(attachment.file_name)
    state.error = null

    // Focus input on next tick (after DOM update)
    if (inputRef?.value) {
      setTimeout(() => {
        inputRef.value?.focus()
        inputRef.value?.select()
      }, 0)
    }
  }

  /**
   * Cancel rename mode
   */
  function cancelRename(attachmentId: string) {
    const state = getEditState(attachmentId)
    state.isEditing = false
    state.editedName = ''
    state.error = null
  }

  /**
   * Validate filename before submitting
   *
   * @returns true if valid, false otherwise (sets error state)
   */
  function validateBeforeSubmit(attachmentId: string, newName: string): boolean {
    const state = getEditState(attachmentId)
    const validationResult = validateFilename(newName)

    if (!validationResult.valid) {
      state.error = validationResult.error
      return false
    }

    state.error = null
    return true
  }

  /**
   * Rename an attachment
   *
   * @param options - Rename options
   * @returns Rename result with updated attachment or error
   */
  async function renameAttachment(
    options: RenameAttachmentOptions
  ): Promise<RenameResult> {
    const { sessionId, clientId, attachmentId, newName } = options
    const state = getEditState(attachmentId)

    // Validate
    if (!validateBeforeSubmit(attachmentId, newName)) {
      return {
        success: false,
        error: state.error || 'Invalid filename',
      }
    }

    state.isLoading = true
    state.error = null

    try {
      let response

      // Determine endpoint based on file type (session-level vs client-level)
      if (sessionId) {
        // Session-level file
        response = await apiClient.patch(
          `/sessions/${sessionId}/attachments/${attachmentId}`,
          { file_name: newName.trim() }
        )
      } else if (clientId) {
        // Client-level file
        response = await apiClient.patch(
          `/clients/${clientId}/attachments/${attachmentId}`,
          { file_name: newName.trim() }
        )
      } else {
        throw new Error('Either sessionId or clientId must be provided')
      }

      // Success
      const updatedAttachment: AttachmentResponse = response.data
      showSuccess(`File renamed to "${updatedAttachment.file_name}"`, { timeout: 3000 })

      // Exit edit mode
      state.isEditing = false
      state.editedName = ''
      state.error = null

      return {
        success: true,
        data: updatedAttachment,
      }
    } catch (error: any) {
      console.error('Rename error:', error)

      // Handle specific error codes
      if (error.response?.status === 409) {
        // Conflict - duplicate filename
        state.error = 'A file with this name already exists'
        return {
          success: false,
          error: state.error,
        }
      } else if (error.response?.status === 400) {
        // Bad request - validation error
        const errorMessage = error.response?.data?.detail || 'Invalid filename'
        state.error = errorMessage
        return {
          success: false,
          error: state.error,
        }
      } else if (error.response?.status === 404) {
        // Not found
        showError('File not found')
        state.isEditing = false
        return {
          success: false,
          error: 'File not found',
        }
      } else {
        // Network or server error
        showError('Failed to rename file. Please try again.')
        state.isEditing = false
        return {
          success: false,
          error: 'Failed to rename file',
        }
      }
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Save rename (wrapper for keyboard/button triggers)
   *
   * @param attachment - Attachment being renamed
   * @param onSuccess - Callback after successful rename
   */
  async function saveRename(
    attachment: AttachmentResponse,
    onSuccess?: (updated: AttachmentResponse) => void
  ) {
    const state = getEditState(attachment.id)

    const result = await renameAttachment({
      sessionId: attachment.session_id || undefined,
      clientId: attachment.client_id,
      attachmentId: attachment.id,
      newName: state.editedName,
    })

    if (result.success && result.data && onSuccess) {
      onSuccess(result.data)
    }
  }

  /**
   * Check if attachment is in edit mode
   */
  function isEditing(attachmentId: string): boolean {
    return getEditState(attachmentId).isEditing
  }

  /**
   * Get edited name for attachment
   */
  function getEditedName(attachmentId: string): string {
    return getEditState(attachmentId).editedName
  }

  /**
   * Set edited name for attachment
   */
  function setEditedName(attachmentId: string, name: string) {
    getEditState(attachmentId).editedName = name
  }

  /**
   * Get error message for attachment
   */
  function getError(attachmentId: string): string | null {
    return getEditState(attachmentId).error
  }

  /**
   * Check if attachment is loading
   */
  function isLoading(attachmentId: string): boolean {
    return getEditState(attachmentId).isLoading
  }

  /**
   * Clear all edit states (cleanup)
   */
  function clearAll() {
    editStates.value.clear()
  }

  return {
    // Core actions
    enterRenameMode,
    cancelRename,
    saveRename,
    renameAttachment,

    // State getters
    isEditing,
    getEditedName,
    setEditedName,
    getError,
    isLoading,

    // Utilities
    clearAll,
    editStates,
  }
}
