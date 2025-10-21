<script setup lang="ts">
/**
 * AttachmentList Component
 *
 * Displays list of attachments for a session with download and delete functionality.
 *
 * Features:
 * - Display filename, file type icon, file size, upload date
 * - Image thumbnails for JPEG/PNG/WebP
 * - Download button (presigned URL, opens in new tab)
 * - Delete button with confirmation dialog
 * - Empty state
 * - Loading skeleton
 *
 * Usage:
 *   <AttachmentList :session-id="sessionId" />
 */

import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useFileUpload } from '@/composables/useFileUpload'
import { useToast } from '@/composables/useToast'
import { useAttachmentRename } from '@/composables/useAttachmentRename'
import { getFileExtension as getExtensionFromFilename } from '@/utils/filenameValidation'
import type { AttachmentResponse } from '@/types/attachments'
import { formatFileSize, isImageType, getFileExtension } from '@/types/attachments'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

interface Props {
  sessionId: string
}

interface Emits {
  (e: 'preview-image', attachment: AttachmentResponse): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const { listAttachments, downloadAttachment, deleteAttachment } = useFileUpload()
const { showSuccess, showError, showInfo } = useToast()
const {
  enterRenameMode,
  cancelRename,
  saveRename,
  isEditing,
  getEditedName,
  setEditedName,
  getError,
  isLoading: isRenaming,
} = useAttachmentRename()

// State
const attachments = ref<AttachmentResponse[]>([])
const isLoading = ref(true)
const loadError = ref<string | null>(null)
const isInitialLoad = ref(true) // Track if this is the first load

// Rename input refs (keyed by file ID)
const renameInputRefs = ref<Map<string, HTMLInputElement | null>>(new Map())

// Delete confirmation dialog
const showDeleteDialog = ref(false)
const attachmentToDelete = ref<AttachmentResponse | null>(null)
const isDeleting = ref(false)

// Load attachments
async function loadAttachmentsList() {
  isLoading.value = true
  loadError.value = null

  try {
    const response = await listAttachments(props.sessionId)
    attachments.value = response.items
  } catch (error) {
    console.error('[AttachmentList] Failed to load attachments:', error)
    if (error instanceof Error) {
      loadError.value = error.message
    } else {
      loadError.value = 'Failed to load attachments'
    }
  } finally {
    isLoading.value = false
    isInitialLoad.value = false // Mark initial load as complete
  }
}

// Download attachment
async function handleDownload(attachment: AttachmentResponse) {
  try {
    // Show info toast for download started
    showInfo(`Downloading ${attachment.file_name}...`, { timeout: 2000 })
    await downloadAttachment(props.sessionId, attachment.id, attachment.file_name)
  } catch (error) {
    console.error('Download error:', error)
    if (error instanceof Error) {
      showError(error.message)
    } else {
      showError('Failed to download file')
    }
  }
}

// Open delete confirmation dialog
function confirmDelete(attachment: AttachmentResponse) {
  attachmentToDelete.value = attachment
  showDeleteDialog.value = true
}

// Cancel delete
function cancelDelete() {
  showDeleteDialog.value = false
  attachmentToDelete.value = null
}

// Delete attachment
async function handleDelete() {
  if (!attachmentToDelete.value) return

  isDeleting.value = true

  try {
    await deleteAttachment(props.sessionId, attachmentToDelete.value.id)
    showSuccess(`Deleted ${attachmentToDelete.value.file_name}`)

    // Remove from local list
    attachments.value = attachments.value.filter(
      (a) => a.id !== attachmentToDelete.value!.id
    )

    // Close dialog
    showDeleteDialog.value = false
    attachmentToDelete.value = null
  } catch (error) {
    console.error('Delete error:', error)
    if (error instanceof Error) {
      showError(error.message)
    } else {
      showError('Failed to delete attachment')
    }
  } finally {
    isDeleting.value = false
  }
}

// Preview image (open modal)
function handlePreviewImage(attachment: AttachmentResponse) {
  if (isImageType(attachment.file_type)) {
    emit('preview-image', attachment)
  }
}

// Format date for display
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    return 'Today'
  } else if (days === 1) {
    return 'Yesterday'
  } else if (days < 7) {
    return `${days} days ago`
  } else {
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    })
  }
}

// Get file type icon (reserved for future enhancements - rendering file type badges)
/* function getFileTypeIcon(fileType: string): string {
  if (fileType === 'application/pdf') {
    return 'pdf'
  } else if (isImageType(fileType)) {
    return 'image'
  }
  return 'file'
} */

// Rename functionality
function handleRenameClick(file: AttachmentResponse) {
  const inputRefWrapper = ref(renameInputRefs.value.get(file.id) || null)
  enterRenameMode(file, inputRefWrapper)
}

function handleRenameKeydown(event: KeyboardEvent, file: AttachmentResponse) {
  if (event.key === 'Escape') {
    cancelRename(file.id)
  }
}

async function handleRenameSave(file: AttachmentResponse) {
  await saveRename(file, (updatedFile: AttachmentResponse) => {
    // Update local state with new filename
    const index = attachments.value.findIndex((f) => f.id === file.id)
    if (index !== -1) {
      attachments.value[index] = updatedFile
    }
  })
}

// Global keyboard handler for F2 shortcut
function handleGlobalKeydown(event: KeyboardEvent) {
  // F2 key pressed - enter rename mode for focused file
  if (event.key === 'F2') {
    event.preventDefault()

    // Find the focused file row
    const activeElement = document.activeElement
    if (activeElement && activeElement.closest('[data-file-id]')) {
      const fileRow = activeElement.closest('[data-file-id]') as HTMLElement
      const fileId = fileRow.getAttribute('data-file-id')

      if (fileId) {
        const file = attachments.value.find((f) => f.id === fileId)
        if (file && !isEditing(file.id)) {
          handleRenameClick(file)
        }
      }
    }
  }
}

// Lifecycle
onMounted(() => {
  loadAttachmentsList()

  // Add global keyboard listener for F2 shortcut
  document.addEventListener('keydown', handleGlobalKeydown)
})

// Cleanup
onBeforeUnmount(() => {
  // Remove global keyboard listener
  document.removeEventListener('keydown', handleGlobalKeydown)
})

// Watch for sessionId changes
watch(
  () => props.sessionId,
  () => {
    loadAttachmentsList()
  }
)

// Expose refresh method and attachments
defineExpose({
  refresh: loadAttachmentsList,
  attachments,
})
</script>

<template>
  <div class="attachment-list" :aria-busy="isLoading">
    <!-- Loading State (only show skeleton during initial load) -->
    <SkeletonLoader v-if="isLoading && isInitialLoad" type="attachment" :count="3" />

    <!-- Error State -->
    <div
      v-else-if="loadError"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-center"
    >
      <p class="text-sm text-red-800">{{ loadError }}</p>
      <button
        @click="loadAttachmentsList"
        class="mt-2 text-sm font-medium text-red-600 hover:text-red-700 focus:underline focus:outline-none"
      >
        Try again
      </button>
    </div>

    <!-- Attachments List -->
    <div v-else-if="attachments && attachments.length > 0" class="space-y-2">
      <div
        v-for="attachment in attachments"
        :key="attachment.id"
        :data-file-id="attachment.id"
        class="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-3 transition-shadow hover:shadow-md"
        tabindex="0"
      >
        <!-- Thumbnail or Icon -->
        <div
          class="flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-slate-100"
          :class="isImageType(attachment.file_type) && 'cursor-pointer'"
          @click="isImageType(attachment.file_type) && handlePreviewImage(attachment)"
        >
          <!-- Image Thumbnail (placeholder - will be enhanced with actual thumbnails) -->
          <div
            v-if="isImageType(attachment.file_type)"
            class="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-100 to-blue-200"
          >
            <svg
              class="h-8 w-8 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>

          <!-- PDF Icon -->
          <div
            v-else-if="attachment.file_type === 'application/pdf'"
            class="flex h-full w-full items-center justify-center bg-red-100"
          >
            <svg
              class="h-8 w-8 text-red-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
              />
            </svg>
          </div>

          <!-- Generic File Icon -->
          <div
            v-else
            class="flex h-full w-full items-center justify-center bg-slate-200"
          >
            <svg
              class="h-8 w-8 text-slate-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
        </div>

        <!-- File Info -->
        <div class="min-w-0 flex-1">
          <!-- Default State: Clickable filename -->
          <div v-if="!isEditing(attachment.id)" class="flex items-center gap-2">
            <button
              @click="handleRenameClick(attachment)"
              class="truncate text-left text-sm font-medium text-slate-900 transition-colors hover:text-blue-600 focus:text-blue-600 focus:underline focus:outline-none"
              :title="`${attachment.file_name} (Click or press F2 to rename)`"
              :aria-label="`Rename ${attachment.file_name}`"
            >
              {{ attachment.file_name }}
            </button>
            <span
              class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
              :class="
                attachment.file_type === 'application/pdf'
                  ? 'bg-red-100 text-red-800'
                  : 'bg-blue-100 text-blue-800'
              "
            >
              {{ getFileExtension(attachment.file_name) }}
            </span>
          </div>

          <!-- Edit Mode: Inline rename form -->
          <div v-else class="flex flex-col gap-1">
            <form
              @submit.prevent="handleRenameSave(attachment)"
              class="flex items-center gap-2"
            >
              <div class="relative flex-1">
                <input
                  :ref="
                    (el) =>
                      renameInputRefs.set(attachment.id, el as HTMLInputElement | null)
                  "
                  :value="getEditedName(attachment.id)"
                  type="text"
                  class="w-full rounded border-2 px-2 py-1 text-sm font-medium transition-colors focus:outline-none md:min-w-[16rem]"
                  :class="
                    getError(attachment.id)
                      ? 'border-red-500 focus:ring-2 focus:ring-red-500'
                      : 'border-blue-500 focus:ring-2 focus:ring-blue-500'
                  "
                  :disabled="isRenaming(attachment.id)"
                  :aria-label="'New filename'"
                  :aria-invalid="!!getError(attachment.id)"
                  :aria-describedby="
                    getError(attachment.id) ? `error-${attachment.id}` : undefined
                  "
                  @keydown="handleRenameKeydown($event, attachment)"
                  @input="
                    setEditedName(
                      attachment.id,
                      ($event.target as HTMLInputElement).value
                    )
                  "
                />
                <!-- Extension badge (read-only) -->
                <span
                  class="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                >
                  {{ getExtensionFromFilename(attachment.file_name) }}
                </span>
              </div>

              <!-- Save Button -->
              <button
                type="submit"
                :disabled="isRenaming(attachment.id)"
                class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded p-1 text-green-600 transition-colors hover:bg-green-50 focus:ring-2 focus:ring-green-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:h-auto md:w-auto md:px-3 md:py-1.5"
                :aria-label="'Save rename'"
                title="Save (Enter)"
              >
                <svg
                  v-if="!isRenaming(attachment.id)"
                  class="h-5 w-5 md:h-4 md:w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                <svg
                  v-else
                  class="h-4 w-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  />
                  <path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                <span class="ml-1.5 hidden text-sm font-medium md:inline">Save</span>
              </button>

              <!-- Cancel Button -->
              <button
                type="button"
                @click="cancelRename(attachment.id)"
                :disabled="isRenaming(attachment.id)"
                class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded p-1 text-red-600 transition-colors hover:bg-red-50 focus:ring-2 focus:ring-red-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:h-auto md:w-auto md:px-3 md:py-1.5"
                :aria-label="'Cancel rename'"
                title="Cancel (Esc)"
              >
                <svg
                  class="h-5 w-5 md:h-4 md:w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
                <span class="ml-1.5 hidden text-sm font-medium md:inline">Cancel</span>
              </button>
            </form>

            <!-- Inline error message -->
            <p
              v-if="getError(attachment.id)"
              :id="`error-${attachment.id}`"
              class="text-sm text-red-600"
              role="alert"
            >
              {{ getError(attachment.id) }}
            </p>
          </div>
          <div class="mt-1 flex items-center gap-2 text-xs text-slate-600">
            <span>{{ formatFileSize(attachment.file_size_bytes) }}</span>
            <span aria-hidden="true">•</span>
            <span>{{ formatDate(attachment.created_at) }}</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex flex-shrink-0 items-center gap-1">
          <!-- Download Button -->
          <button
            @click="handleDownload(attachment)"
            class="rounded p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:outline-none"
            :aria-label="`Download ${attachment.file_name}`"
            title="Download"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
          </button>

          <!-- Delete Button -->
          <button
            @click="confirmDelete(attachment)"
            class="rounded p-2 text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600 focus:ring-2 focus:ring-red-500 focus:ring-offset-1 focus:outline-none"
            :aria-label="`Delete ${attachment.file_name}`"
            title="Delete"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <Teleport to="body">
      <div
        v-if="showDeleteDialog"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        @click.self="cancelDelete"
      >
        <div
          class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
        >
          <div class="mb-4 flex items-start gap-3">
            <div
              class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-red-100"
            >
              <svg
                class="h-6 w-6 text-red-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div>
              <h3 id="delete-dialog-title" class="text-lg font-semibold text-slate-900">
                Delete Attachment
              </h3>
              <p class="mt-2 text-sm text-slate-600">
                Are you sure you want to delete
                <strong class="font-medium text-slate-900">{{
                  attachmentToDelete?.file_name
                }}</strong
                >? This action cannot be undone.
              </p>
            </div>
          </div>
          <div class="mt-6 flex justify-end gap-3">
            <button
              @click="cancelDelete"
              type="button"
              :disabled="isDeleting"
              class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              @click="handleDelete"
              type="button"
              :disabled="isDeleting"
              class="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:ring-2 focus:ring-red-600 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg
                v-if="isDeleting"
                class="h-4 w-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                />
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              {{ isDeleting ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* Smooth transitions */
.attachment-list button {
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}
</style>
