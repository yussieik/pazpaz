<script setup lang="ts">
/**
 * FileUpload Component
 *
 * Adaptive drag-and-drop file upload for session attachments with UX improvements.
 *
 * Features:
 * - Unified upload zone that adapts based on state (empty vs with-files)
 * - Responsive text (drag-drop hint on desktop, tap on mobile)
 * - Visual drag-and-drop area with hover states
 * - File type validation (JPEG, PNG, WebP, PDF)
 * - File size validation (10 MB max per file)
 * - Multiple file support (batch upload)
 * - Upload progress indicator (percentage)
 * - Success/error states with clear messages
 * - Keyboard accessible (Enter/Space trigger upload)
 *
 * Design:
 * - Empty state: Large, centered upload zone with icon, responsive text, and de-emphasized constraints
 * - With files: Compact "Add more files" button below attachment list
 * - Mobile-friendly: No drag-drop hint on small screens (where it doesn't work)
 * - Professional aesthetic: Clean, calm, reduced cognitive load
 *
 * Usage:
 *   <FileUpload :session-id="sessionId" :has-attachments="false" @upload-complete="handleUploadComplete" />
 */

import { ref, computed, unref, type Ref } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useFileUpload } from '@/composables/useFileUpload'
import { useToast } from '@/composables/useToast'
import type { UploadProgress } from '@/types/attachments'
import { validateFile } from '@/types/attachments'

interface Props {
  sessionId: string
}

interface Emits {
  (e: 'upload-complete'): void
}

const props = defineProps<Props>()

const emit = defineEmits<Emits>()

const { t } = useI18n()
const { uploadFiles } = useFileUpload()
const { showSuccess, showError } = useToast()

// Drag and drop state
const isDragging = ref(false)
const isUploading = ref(false)

// File input ref
const fileInputRef = ref<HTMLInputElement | null>(null)

// Upload progress tracking (internal refs)
const uploadingFilesRefs = ref<{ name: string; progressRef: Ref<UploadProgress> }[]>([])

// Unwrapped upload progress for template (to avoid .value in template)
const uploadingFiles = computed<Array<{ name: string; progress: UploadProgress }>>(() =>
  uploadingFilesRefs.value.map((item) => ({
    name: item.name,
    progress: unref(item.progressRef),
  }))
)

// Drag event handlers
function handleDragEnter(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave(e: DragEvent) {
  e.preventDefault()
  // Only set to false if leaving the drop zone entirely
  if (e.currentTarget === e.target) {
    isDragging.value = false
  }
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
}

async function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false

  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length === 0) return

  await processFiles(files)
}

// File input change handler
function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  const files = Array.from(target.files || [])
  if (files.length === 0) return

  processFiles(files)

  // Reset input to allow selecting the same file again
  target.value = ''
}

// Process and upload files
async function processFiles(files: File[]) {
  // Validate all files first
  const validFiles: File[] = []
  const errors: string[] = []

  for (const file of files) {
    const error = validateFile(file)
    if (error) {
      errors.push(`${file.name}: ${error}`)
    } else {
      validFiles.push(file)
    }
  }

  // Show validation errors (no request ID for client-side validation)
  if (errors.length > 0) {
    errors.forEach((error) => showError(error))
  }

  // Upload valid files
  if (validFiles.length === 0) return

  isUploading.value = true

  // Create progress refs for each file
  const progressRefs = validFiles.map(() =>
    ref<UploadProgress>({
      state: 'idle',
      progress: 0,
      error: null,
    })
  )

  // Track uploading files for UI display
  uploadingFilesRefs.value = validFiles
    .map((file, i) => {
      const progressRef = progressRefs[i]
      if (!progressRef) return null
      return {
        name: file.name,
        progressRef,
      }
    })
    .filter(
      (item): item is { name: string; progressRef: Ref<UploadProgress> } =>
        item !== null
    )

  try {
    const results = await uploadFiles(props.sessionId, validFiles, progressRefs)

    // Show success messages
    const successCount = results.length
    if (successCount > 0) {
      const firstFile = validFiles[0]
      showSuccess(
        successCount === 1 && firstFile
          ? t('sessions.attachments.upload.successSingle', { fileName: firstFile.name })
          : t('sessions.attachments.upload.successMultiple', { count: successCount })
      )

      // Emit event to refresh attachment list
      emit('upload-complete')
    }
  } catch (error) {
    console.error('Upload error:', error)
    if (error instanceof Error) {
      // Extract request ID if available (from FileUploadError)
      const requestId = (error as { requestId?: string }).requestId
      showError(error.message, requestId)
    }
  } finally {
    isUploading.value = false
    // Clear uploading files after a short delay to show completion
    setTimeout(() => {
      uploadingFilesRefs.value = []
    }, 1000)
  }
}

// Open file picker
function triggerFileInput() {
  fileInputRef.value?.click()
}

// Keyboard event handler for upload zone
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    triggerFileInput()
  }
}
</script>

<template>
  <div class="file-upload">
    <!-- Upload Zone -->
    <div
      @dragenter="handleDragEnter"
      @dragleave="handleDragLeave"
      @dragover="handleDragOver"
      @drop="handleDrop"
      @click="triggerFileInput"
      @keydown="handleKeydown"
      :class="[
        'relative cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-all duration-200',
        isDragging
          ? 'border-blue-400 bg-blue-50'
          : 'border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100',
        isUploading && 'pointer-events-none opacity-60',
      ]"
      role="button"
      tabindex="0"
      :aria-label="
        isUploading
          ? t('sessions.attachments.upload.ariaLabelUploading')
          : t('sessions.attachments.upload.ariaLabelDefault')
      "
      :aria-busy="isUploading"
    >
      <!-- Upload Icon -->
      <svg
        class="mx-auto h-10 w-10"
        :class="isDragging ? 'text-blue-500' : 'text-gray-400'"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
        />
      </svg>

      <!-- Primary Action Text -->
      <p class="mt-3 text-sm text-gray-700">
        <span class="font-medium text-blue-600">{{
          t('sessions.attachments.upload.clickToUpload')
        }}</span>
        {{ t('sessions.attachments.upload.dragAndDrop') }}
      </p>

      <!-- File Constraints -->
      <p class="mt-1 text-xs text-gray-500">
        {{ t('sessions.attachments.upload.fileConstraints') }}
      </p>

      <!-- Hidden file input -->
      <input
        ref="fileInputRef"
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp,application/pdf"
        @change="handleFileSelect"
        class="hidden"
        aria-hidden="true"
      />
    </div>

    <!-- Upload Progress (shown during uploads) -->
    <div v-if="uploadingFiles.length > 0" class="mt-4 space-y-2">
      <div
        v-for="(item, index) in uploadingFiles"
        :key="index"
        class="rounded-lg border border-gray-200 bg-white p-3"
      >
        <div class="flex items-center justify-between gap-3">
          <div class="flex-1 overflow-hidden">
            <p class="truncate text-sm font-medium text-gray-900">{{ item.name }}</p>
            <div class="mt-1 flex items-center gap-2">
              <!-- Progress Bar -->
              <div class="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
                <div
                  class="h-full rounded-full transition-all duration-300"
                  :class="
                    item.progress.state === 'error'
                      ? 'bg-red-500'
                      : item.progress.state === 'success'
                        ? 'bg-green-500'
                        : 'bg-blue-500'
                  "
                  :style="{ width: `${item.progress.progress}%` }"
                  role="progressbar"
                  :aria-valuenow="item.progress.progress"
                  aria-valuemin="0"
                  aria-valuemax="100"
                ></div>
              </div>
              <!-- Progress Percentage -->
              <span class="text-xs font-medium text-gray-600">
                {{ item.progress.progress }}%
              </span>
            </div>
            <!-- Error Message -->
            <p
              v-if="item.progress.state === 'error' && item.progress.error"
              class="mt-1 text-xs text-red-600"
            >
              {{ item.progress.error }}
            </p>
          </div>

          <!-- Status Icon -->
          <div class="flex-shrink-0">
            <svg
              v-if="item.progress.state === 'success'"
              class="h-5 w-5 text-green-600"
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
              v-else-if="item.progress.state === 'error'"
              class="h-5 w-5 text-red-600"
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
            <svg
              v-else
              class="h-5 w-5 animate-spin text-blue-600"
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
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth transitions for drag state and hover */
.file-upload > div[role='button'] {
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease;
}

/* Focus visible styles for accessibility */
.file-upload > div[role='button']:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
  border-color: #3b82f6;
}

/* Button focus styles */
.file-upload button:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}
</style>
