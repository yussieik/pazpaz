<script setup lang="ts">
/**
 * SessionAttachments Component
 *
 * Simple wrapper component that combines file upload and attachment list.
 *
 * Features:
 * - File upload with drag-and-drop
 * - Attachment list with download/delete/rename
 * - Image preview modal with gallery navigation
 *
 * Usage:
 *   <SessionAttachments :session-id="sessionId" />
 */

import { ref, computed } from 'vue'
import { useFileUpload } from '@/composables/useFileUpload'
import { useToast } from '@/composables/useToast'
import FileUpload from './FileUpload.vue'
import AttachmentList from './AttachmentList.vue'
import ImagePreviewModal from './ImagePreviewModal.vue'
import type { AttachmentResponse } from '@/types/attachments'
import { isImageType } from '@/types/attachments'

interface Props {
  sessionId: string
}

const props = defineProps<Props>()

const { downloadAttachment } = useFileUpload()
const { showError } = useToast()

// Attachment list ref
const attachmentListRef = ref<InstanceType<typeof AttachmentList> | null>(null)

// Image preview state
const showImagePreview = ref(false)
const previewImageIndex = ref(0)
const allAttachments = ref<AttachmentResponse[]>([])

// Filter image attachments for preview
const imageAttachments = computed(() =>
  allAttachments.value.filter((a) => isImageType(a.file_type))
)

// Handle upload complete
async function handleUploadComplete() {
  console.log('[SessionAttachments] Upload complete, refreshing list...')
  // Refresh attachment list
  await attachmentListRef.value?.refresh()
  console.log('[SessionAttachments] Refresh complete, attachments:', attachmentListRef.value?.attachments)
}

// Handle image preview
function handlePreviewImage(attachment: AttachmentResponse) {
  // Store all attachments for navigation
  allAttachments.value = attachmentListRef.value?.attachments || []

  // Find index of clicked image in image-only list
  const imageIndex = imageAttachments.value.findIndex((a) => a.id === attachment.id)
  if (imageIndex !== -1) {
    previewImageIndex.value = imageIndex
    showImagePreview.value = true
  }
}

// Handle download from preview modal
async function handleDownloadFromPreview(attachment: AttachmentResponse) {
  try {
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

// Update current index when navigating in preview
function updatePreviewIndex(index: number) {
  previewImageIndex.value = index
}
</script>

<template>
  <div class="session-attachments space-y-4">
    <!-- File Upload -->
    <FileUpload :session-id="sessionId" @upload-complete="handleUploadComplete" />

    <!-- Attachment List -->
    <AttachmentList
      ref="attachmentListRef"
      :session-id="sessionId"
      @preview-image="handlePreviewImage"
    />

    <!-- Image Preview Modal -->
    <ImagePreviewModal
      :open="showImagePreview"
      :attachments="imageAttachments"
      :current-index="previewImageIndex"
      :session-id="sessionId"
      @close="showImagePreview = false"
      @download="handleDownloadFromPreview"
      @update:current-index="updatePreviewIndex"
    />
  </div>
</template>
