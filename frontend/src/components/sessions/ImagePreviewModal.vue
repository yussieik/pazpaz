<script setup lang="ts">
/**
 * ImagePreviewModal Component
 *
 * Full-screen modal for previewing images with gallery navigation.
 *
 * Features:
 * - Full-screen image preview
 * - Previous/Next navigation buttons
 * - Keyboard navigation (Arrow keys, Escape)
 * - Download button
 * - Close button
 * - Only shows for images (JPEG, PNG, WebP)
 *
 * Usage:
 *   <ImagePreviewModal
 *     :open="showModal"
 *     :attachments="imageAttachments"
 *     :current-index="currentIndex"
 *     @close="showModal = false"
 *     @download="handleDownload"
 *   />
 */

import { computed, watch, onBeforeUnmount, ref } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import apiClient from '@/api/client'
import type { AttachmentResponse } from '@/types/attachments'
import { formatFileSize, isImageType } from '@/types/attachments'
import { useFocusTrap } from '@/composables/useFocusTrap'

interface Props {
  open: boolean
  attachments: AttachmentResponse[]
  currentIndex: number
  sessionId: string
  clientId?: string // Optional: for client-level files without sessionId
}

interface Emits {
  (e: 'close'): void
  (e: 'download', attachment: AttachmentResponse): void
  (e: 'update:current-index', index: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Modal container ref for focus trap
const modalRef = ref<HTMLElement | null>(null)
const { activate: activateFocusTrap, deactivate: deactivateFocusTrap } =
  useFocusTrap(modalRef)

// Filter to only image attachments
const imageAttachments = computed(() =>
  props.attachments.filter((a) => isImageType(a.file_type))
)

// Current attachment
const currentAttachment = computed(
  () => imageAttachments.value[props.currentIndex] || null
)

// Navigation
const canGoPrevious = computed(() => props.currentIndex > 0)
const canGoNext = computed(() => props.currentIndex < imageAttachments.value.length - 1)

function goToPrevious() {
  if (canGoPrevious.value) {
    emit('update:current-index', props.currentIndex - 1)
  }
}

function goToNext() {
  if (canGoNext.value) {
    emit('update:current-index', props.currentIndex + 1)
  }
}

// Close modal
function close() {
  emit('close')
}

// Download current image
function download() {
  if (!currentAttachment.value) return

  // Emit to parent to handle download with proper disposition header
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

onKeyStroke('ArrowLeft', () => {
  if (props.open) {
    goToPrevious()
  }
})

onKeyStroke('ArrowRight', () => {
  if (props.open) {
    goToNext()
  }
})

// Fetch presigned URL for image display
const imageUrl = ref<string | null>(null)
const imageLoading = ref(false)
const imageError = ref(false)

async function fetchImageUrl() {
  if (!currentAttachment.value) {
    imageUrl.value = null
    return
  }

  imageLoading.value = true
  imageError.value = false

  try {
    let response

    // For client-level files (no session_id), use client endpoint
    if (!currentAttachment.value.session_id && props.clientId) {
      response = await apiClient.get(
        `/clients/${props.clientId}/attachments/${currentAttachment.value.id}/download`
      )
    } else {
      // For session-level files, use session endpoint
      const sessionId = currentAttachment.value.session_id || props.sessionId
      response = await apiClient.get(
        `/sessions/${sessionId}/attachments/${currentAttachment.value.id}/download`
      )
    }

    imageUrl.value = response.data.download_url
  } catch (error) {
    console.error('Failed to fetch image URL:', error)
    imageError.value = true
    imageUrl.value = null
  } finally {
    imageLoading.value = false
  }
}

// Fetch image URL when attachment changes
watch(
  currentAttachment,
  () => {
    fetchImageUrl()
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
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
        @click.self="close"
        role="dialog"
        aria-modal="true"
        aria-labelledby="image-preview-title"
      >
        <!-- Close Button (Top Right) -->
        <button
          @click="close"
          class="fixed top-4 right-4 z-10 rounded-full bg-black/50 p-3 text-white transition-colors hover:bg-black/70 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black focus:outline-none"
          aria-label="Close image preview"
          title="Close (Esc)"
        >
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>

        <!-- Download Button (Top Right, next to close) -->
        <button
          @click="download"
          class="fixed top-4 right-20 z-10 rounded-full bg-black/50 p-3 text-white transition-colors hover:bg-black/70 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black focus:outline-none"
          aria-label="Download image"
          title="Download"
        >
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
        </button>

        <!-- Previous Button -->
        <button
          v-if="canGoPrevious"
          @click="goToPrevious"
          class="fixed left-4 z-10 rounded-full bg-black/50 p-3 text-white transition-colors hover:bg-black/70 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black focus:outline-none"
          aria-label="Previous image"
          title="Previous (←)"
        >
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>

        <!-- Next Button -->
        <button
          v-if="canGoNext"
          @click="goToNext"
          class="fixed right-4 z-10 rounded-full bg-black/50 p-3 text-white transition-colors hover:bg-black/70 focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-black focus:outline-none"
          aria-label="Next image"
          title="Next (→)"
        >
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>

        <!-- Image Container -->
        <div class="flex h-full w-full flex-col items-center justify-center p-16">
          <!-- Image Info Bar (Top) -->
          <div
            class="mb-4 w-full max-w-4xl rounded-lg bg-black/50 px-4 py-2 text-white backdrop-blur-sm"
          >
            <div class="flex items-center justify-between">
              <div>
                <h2
                  id="image-preview-title"
                  class="text-sm font-medium"
                  :title="currentAttachment.file_name"
                >
                  {{ currentAttachment.file_name }}
                </h2>
                <p class="text-xs text-white/70">
                  {{ formatFileSize(currentAttachment.file_size_bytes) }}
                </p>
              </div>
              <div class="text-sm">
                {{ currentIndex + 1 }} / {{ imageAttachments.length }}
              </div>
            </div>
          </div>

          <!-- Image Display -->
          <div class="relative flex max-h-full max-w-full items-center justify-center">
            <!-- Loading State -->
            <div v-if="imageLoading" class="flex items-center justify-center">
              <svg
                class="h-12 w-12 animate-spin text-white"
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

            <!-- Error State -->
            <div v-else-if="imageError" class="text-center text-white">
              <svg
                class="mx-auto h-16 w-16 text-white/50"
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
              <p class="mt-4 text-sm">Failed to load image</p>
            </div>

            <!-- Image -->
            <img
              v-else-if="imageUrl"
              :src="imageUrl"
              :alt="currentAttachment.file_name"
              class="max-h-[calc(100vh-12rem)] max-w-[calc(100vw-8rem)] rounded-lg object-contain shadow-2xl"
              @click.stop
              @error="imageError = true"
            />
          </div>
        </div>

        <!-- Keyboard Shortcuts Hint (Bottom) -->
        <div
          class="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-lg bg-black/50 px-4 py-2 text-xs text-white/70 backdrop-blur-sm"
        >
          <span class="inline-flex items-center gap-1">
            <kbd
              class="rounded bg-white/20 px-1.5 py-0.5 font-mono text-white"
              aria-label="Left arrow key"
              >←</kbd
            >
            <kbd
              class="rounded bg-white/20 px-1.5 py-0.5 font-mono text-white"
              aria-label="Right arrow key"
              >→</kbd
            >
            Navigate
          </span>
          <span class="mx-2">•</span>
          <span class="inline-flex items-center gap-1">
            <kbd
              class="rounded bg-white/20 px-1.5 py-0.5 font-mono text-white"
              aria-label="Escape key"
              >Esc</kbd
            >
            Close
          </span>
        </div>

        <!-- Screen reader announcements -->
        <div class="sr-only" role="status" aria-live="polite" aria-atomic="true">
          Viewing image {{ currentIndex + 1 }} of {{ imageAttachments.length }}:
          {{ currentAttachment.file_name }}
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

/* Image fade transition */
.modal-fade-enter-active img,
.modal-fade-leave-active img {
  transition: transform 0.3s ease;
}

.modal-fade-enter-from img {
  transform: scale(0.95);
}

.modal-fade-leave-to img {
  transform: scale(0.95);
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .modal-fade-enter-active,
  .modal-fade-leave-active,
  .modal-fade-enter-active img,
  .modal-fade-leave-active img {
    transition: none;
  }
}
</style>
