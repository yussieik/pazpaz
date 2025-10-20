<script setup lang="ts">
/**
 * PDFPreviewModal Component
 *
 * Full-screen modal for previewing PDF documents.
 *
 * Features:
 * - Full-screen PDF preview using browser's native viewer
 * - Download button
 * - Close button
 * - Keyboard navigation (Escape)
 * - Loading and error states
 *
 * Usage:
 *   <PDFPreviewModal
 *     :open="showModal"
 *     :attachment="pdfAttachment"
 *     @close="showModal = false"
 *     @download="handleDownload"
 *   />
 */

import { computed, watch, onBeforeUnmount, ref } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import apiClient from '@/api/client'
import type { AttachmentResponse } from '@/types/attachments'
import { formatFileSize } from '@/types/attachments'
import { useFocusTrap } from '@/composables/useFocusTrap'

interface Props {
  open: boolean
  attachment: AttachmentResponse | null
  sessionId?: string
  clientId?: string // Optional: for client-level files without sessionId
}

interface Emits {
  (e: 'close'): void
  (e: 'download', attachment: AttachmentResponse): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Modal container ref for focus trap
const modalRef = ref<HTMLElement | null>(null)
const { activate: activateFocusTrap, deactivate: deactivateFocusTrap } =
  useFocusTrap(modalRef)

// Current attachment
const currentAttachment = computed(() => props.attachment)

// Close modal
function close() {
  emit('close')
}

// Download current PDF
function download() {
  if (!currentAttachment.value) return
  emit('download', currentAttachment.value)
}

// Keyboard shortcuts and focus trap (only when modal is open)
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'
      // Activate focus trap
      activateFocusTrap()
    } else {
      // Restore body scroll
      document.body.style.overflow = ''
      // Deactivate focus trap and return focus
      deactivateFocusTrap()
    }
  }
)

// Keyboard navigation
onKeyStroke('Escape', () => {
  if (props.open) {
    close()
  }
})

// Fetch presigned URL for PDF display
const pdfUrl = ref<string | null>(null)
const pdfLoading = ref(false)
const pdfError = ref(false)

async function fetchPDFUrl() {
  if (!currentAttachment.value) {
    pdfUrl.value = null
    return
  }

  pdfLoading.value = true
  pdfError.value = false

  try {
    let response

    // For client-level files (no session_id), use client endpoint
    if (!currentAttachment.value.session_id && props.clientId) {
      response = await apiClient.get(
        `/clients/${props.clientId}/attachments/${currentAttachment.value.id}/download`
      )
    } else {
      // For session-level files, use session endpoint
      const sessionId =
        currentAttachment.value.session_id || props.sessionId || props.clientId
      if (!sessionId) {
        throw new Error('No session ID or client ID available')
      }
      response = await apiClient.get(
        `/sessions/${sessionId}/attachments/${currentAttachment.value.id}/download`
      )
    }

    pdfUrl.value = response.data.download_url
  } catch (error) {
    console.error('Failed to fetch PDF URL:', error)
    pdfError.value = true
    pdfUrl.value = null
  } finally {
    pdfLoading.value = false
  }
}

// Fetch PDF URL when attachment changes
watch(
  currentAttachment,
  () => {
    if (currentAttachment.value) {
      fetchPDFUrl()
    }
  },
  { immediate: true }
)

// Cleanup on unmount
onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="open && currentAttachment"
        ref="modalRef"
        class="fixed inset-0 z-50 flex flex-col bg-slate-900"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pdf-preview-title"
      >
        <!-- Header Bar -->
        <div
          class="flex items-center justify-between border-b border-slate-700 bg-slate-800 px-4 py-3"
        >
          <!-- PDF Info -->
          <div class="min-w-0 flex-1">
            <h2
              id="pdf-preview-title"
              class="truncate text-sm font-medium text-white"
              :title="currentAttachment.file_name"
            >
              {{ currentAttachment.file_name }}
            </h2>
            <p class="text-xs text-slate-400">
              {{ formatFileSize(currentAttachment.file_size_bytes) }}
            </p>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2">
            <!-- Download Button -->
            <button
              @click="download"
              class="rounded-lg bg-slate-700 p-2 text-white transition-colors hover:bg-slate-600 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-slate-800 focus:outline-none"
              aria-label="Download PDF"
              title="Download"
            >
              <svg
                class="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
            </button>

            <!-- Close Button -->
            <button
              @click="close"
              class="rounded-lg bg-slate-700 p-2 text-white transition-colors hover:bg-slate-600 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-slate-800 focus:outline-none"
              aria-label="Close PDF preview"
              title="Close (Esc)"
            >
              <svg
                class="h-5 w-5"
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
            </button>
          </div>
        </div>

        <!-- PDF Viewer Container -->
        <div class="relative flex-1 bg-slate-800">
          <!-- Loading State -->
          <div v-if="pdfLoading" class="flex h-full items-center justify-center">
            <div class="text-center">
              <svg
                class="mx-auto h-12 w-12 animate-spin text-white"
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
              <p class="mt-4 text-sm text-white">Loading PDF...</p>
            </div>
          </div>

          <!-- Error State -->
          <div v-else-if="pdfError" class="flex h-full items-center justify-center">
            <div class="text-center text-white">
              <svg
                class="mx-auto h-16 w-16 text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p class="mt-4 text-sm">Failed to load PDF</p>
              <button
                @click="fetchPDFUrl"
                class="mt-4 rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-600 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-slate-800 focus:outline-none"
              >
                Try Again
              </button>
            </div>
          </div>

          <!-- PDF Iframe -->
          <iframe
            v-else-if="pdfUrl"
            :src="pdfUrl"
            class="h-full w-full border-0"
            :title="`PDF preview: ${currentAttachment.file_name}`"
            @error="pdfError = true"
          />
        </div>

        <!-- Keyboard Shortcuts Hint (Bottom) -->
        <div
          class="border-t border-slate-700 bg-slate-800 px-4 py-2 text-center text-xs text-slate-400"
        >
          <span class="inline-flex items-center gap-1">
            Press
            <kbd
              class="mx-1 rounded bg-slate-700 px-2 py-1 font-mono text-white"
              aria-label="Escape key"
              >Esc</kbd
            >
            to close
          </span>
        </div>

        <!-- Screen reader announcements -->
        <div class="sr-only" role="status" aria-live="polite" aria-atomic="true">
          Viewing PDF: {{ currentAttachment.file_name }}
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Screen reader only utility */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* Modal fade transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .modal-fade-enter-active,
  .modal-fade-leave-active {
    transition: none;
  }
}
</style>
