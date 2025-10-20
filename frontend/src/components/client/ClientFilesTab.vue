<script setup lang="ts">
/**
 * ClientFilesTab Component
 *
 * Displays all file attachments for a client across all sessions.
 *
 * Features:
 * - Chronological file list grouped by month (newest first)
 * - Sticky month headers
 * - Session context links ("From: Session on [Date]")
 * - File preview, download, delete actions
 * - Client-level file upload
 * - Empty state
 * - Loading skeleton
 * - Responsive mobile layout
 *
 * Usage:
 *   <ClientFilesTab :client-id="clientId" />
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { format } from 'date-fns'
import axios from 'axios'
import apiClient from '@/api/client'
import { useFileUpload } from '@/composables/useFileUpload'
import { useToast } from '@/composables/useToast'
import { useAttachmentRename } from '@/composables/useAttachmentRename'
import { getFileExtension as getExtensionFromFilename } from '@/utils/filenameValidation'
import ImagePreviewModal from '@/components/sessions/ImagePreviewModal.vue'
import PDFPreviewModal from '@/components/sessions/PDFPreviewModal.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import SkeletonLoader from '@/components/common/SkeletonLoader.vue'
import type { AttachmentResponse } from '@/types/attachments'
import { formatFileSize, isImageType, getFileExtension } from '@/types/attachments'

interface Props {
  clientId: string
}

const props = defineProps<Props>()

const router = useRouter()
const { downloadAttachment, deleteAttachment } = useFileUpload()
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

// Rename input refs (keyed by file ID)
const renameInputRefs = ref<Map<string, HTMLInputElement | null>>(new Map())

// State
const loading = ref(true)
const loadError = ref<string | null>(null)
const allAttachments = ref<AttachmentResponse[]>([])

// Filter and search state
const filterType = ref<'all' | 'images' | 'pdfs'>('all')
const searchQuery = ref('')

// Upload state
const fileInputRef = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const uploadProgress = ref<Map<string, number>>(new Map())

// Drag and drop state
const isDragging = ref(false)
const dragCounter = ref(0) // Track nested drag events

// Delete confirmation
const showDeleteDialog = ref(false)
const attachmentToDelete = ref<AttachmentResponse | null>(null)
const isDeleting = ref(false)

// Bulk selection
const selectedFileIds = ref<Set<string>>(new Set())
const isBulkMode = ref(false)
const isBulkDeleting = ref(false)
const showBulkDeleteDialog = ref(false)
const isBulkDownloading = ref(false)

// Image preview
const showImagePreview = ref(false)
const previewImageIndex = ref(0)

// PDF preview
const showPDFPreview = ref(false)
const pdfToPreview = ref<AttachmentResponse | null>(null)

// Thumbnail cache (attachment ID -> presigned URL)
const thumbnailCache = ref<Map<string, string>>(new Map())
const thumbnailLoadingSet = ref<Set<string>>(new Set())
const thumbnailErrorSet = ref<Set<string>>(new Set())

// Filter image attachments for preview
const imageAttachments = computed(() =>
  allAttachments.value.filter((a) => isImageType(a.file_type))
)

// Bulk selection computed properties
const selectedFilesCount = computed(() => selectedFileIds.value.size)

const allVisibleFilesSelected = computed(() => {
  if (filteredAttachments.value.length === 0) return false
  return filteredAttachments.value.every((file) => selectedFileIds.value.has(file.id))
})

const someVisibleFilesSelected = computed(() => {
  if (filteredAttachments.value.length === 0) return false
  return (
    !allVisibleFilesSelected.value &&
    filteredAttachments.value.some((file) => selectedFileIds.value.has(file.id))
  )
})

// Note: selectedFiles removed as it's no longer needed (we now use attachment IDs directly)

// Helper function to group files by month
function groupFilesByMonth(files: AttachmentResponse[]): MonthGroup[] {
  const grouped = new Map<string, AttachmentResponse[]>()

  files.forEach((file) => {
    const date = new Date(file.created_at)
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

    if (!grouped.has(monthKey)) {
      grouped.set(monthKey, [])
    }
    grouped.get(monthKey)!.push(file)
  })

  // Sort descending (most recent first)
  return Array.from(grouped.entries())
    .sort(([keyA], [keyB]) => keyB.localeCompare(keyA))
    .map(([monthKey, files]) => {
      const firstFile = files[0]
      return {
        monthKey,
        label: firstFile
          ? new Date(firstFile.created_at).toLocaleDateString('en-US', {
              month: 'long',
              year: 'numeric',
            })
          : '',
        files: files.sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        ),
      }
    })
}

// Apply search and filter to attachments
const filteredAttachments = computed(() => {
  let filtered = allAttachments.value

  // Apply search filter
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter((file) => file.file_name.toLowerCase().includes(query))
  }

  // Apply file type filter
  if (filterType.value === 'images') {
    filtered = filtered.filter((file) => isImageType(file.file_type))
  } else if (filterType.value === 'pdfs') {
    filtered = filtered.filter((file) => file.file_type === 'application/pdf')
  }

  return filtered
})

// Group files by month (chronological, newest first)
interface MonthGroup {
  monthKey: string
  label: string
  files: AttachmentResponse[]
}

const filesByMonth = computed((): MonthGroup[] => {
  return groupFilesByMonth(filteredAttachments.value)
})

// Check if results are empty due to filtering
const hasNoResults = computed(() => {
  return (
    allAttachments.value.length > 0 &&
    filteredAttachments.value.length === 0 &&
    (searchQuery.value.trim() || filterType.value !== 'all')
  )
})

// Generate empty state message
const emptyResultsMessage = computed(() => {
  if (searchQuery.value.trim() && filterType.value !== 'all') {
    const typeLabel = filterType.value === 'images' ? 'images' : 'PDFs'
    return `No ${typeLabel} found for "${searchQuery.value}"`
  } else if (searchQuery.value.trim()) {
    return `No results found for "${searchQuery.value}"`
  } else if (filterType.value === 'images') {
    return 'No images found'
  } else if (filterType.value === 'pdfs') {
    return 'No PDFs found'
  }
  return 'No files found'
})

// Load all files for the client using the dedicated client-level attachments endpoint
async function loadClientFiles() {
  loading.value = true
  loadError.value = null

  try {
    // Use the new dedicated endpoint that returns all attachments (session + client-level)
    const response = await apiClient.get(`/clients/${props.clientId}/attachments`)
    allAttachments.value = response.data.items || []
  } catch (error) {
    console.error('Failed to load client files:', error)
    loadError.value = 'Failed to load files. Please try again.'
  } finally {
    loading.value = false
  }
}

// Navigate to session detail
function navigateToSession(sessionId: string) {
  router.push({
    path: `/sessions/${sessionId}`,
    query: { tab: 'attachments' }, // Could be used to scroll to attachments section
  })
}

// Download file (works for both session and client-level files)
async function handleDownload(file: AttachmentResponse) {
  try {
    showInfo(`Downloading ${file.file_name}...`, { timeout: 2000 })

    // For session files, use the session-based download
    // For client-level files, we'll need to use the client endpoint
    if (file.session_id) {
      await downloadAttachment(file.session_id, file.id, file.file_name)
    } else {
      // Client-level file download - get presigned URL directly
      const response = await apiClient.get(
        `/clients/${props.clientId}/attachments/${file.id}/download`
      )
      const downloadUrl = response.data.download_url

      // For cross-origin downloads (MinIO), we need to fetch the blob first
      // then create a blob URL to download it (browser security restriction)
      try {
        const fileResponse = await fetch(downloadUrl)
        if (!fileResponse.ok) {
          throw new Error('Failed to fetch file')
        }

        const blob = await fileResponse.blob()
        const blobUrl = URL.createObjectURL(blob)

        const link = document.createElement('a')
        link.href = blobUrl
        link.download = file.file_name
        link.style.display = 'none'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)

        // Clean up blob URL after a short delay
        setTimeout(() => URL.revokeObjectURL(blobUrl), 100)
      } catch (fetchError) {
        console.error('Blob download failed, falling back to direct link:', fetchError)
        // Fallback: open in new tab (will preview instead of download)
        window.open(downloadUrl, '_blank')
      }
    }
  } catch (error) {
    console.error('Download error:', error)
    if (error instanceof Error) {
      showError(error.message)
    } else {
      showError('Failed to download file')
    }
  }
}

// Preview image
function handlePreviewImage(file: AttachmentResponse) {
  const imageIndex = imageAttachments.value.findIndex((a) => a.id === file.id)
  if (imageIndex !== -1) {
    previewImageIndex.value = imageIndex
    showImagePreview.value = true
  }
}

// Preview PDF
function handlePreviewPDF(file: AttachmentResponse) {
  pdfToPreview.value = file
  showPDFPreview.value = true
}

// Delete confirmation
function confirmDelete(file: AttachmentResponse) {
  attachmentToDelete.value = file
  showDeleteDialog.value = true
}

function cancelDelete() {
  showDeleteDialog.value = false
  attachmentToDelete.value = null
}

// Delete file (works for both session and client-level files)
async function handleDelete() {
  if (!attachmentToDelete.value) return

  const fileToDelete = allAttachments.value.find(
    (f) => f.id === attachmentToDelete.value!.id
  )
  if (!fileToDelete) {
    showError('File not found')
    cancelDelete()
    return
  }

  isDeleting.value = true

  try {
    // Use appropriate delete endpoint based on file type
    if (fileToDelete.session_id) {
      // Session-level file
      await deleteAttachment(fileToDelete.session_id, attachmentToDelete.value.id)
    } else {
      // Client-level file
      await apiClient.delete(
        `/clients/${props.clientId}/attachments/${attachmentToDelete.value.id}`
      )
    }

    showSuccess(`Deleted ${attachmentToDelete.value.file_name}`)

    // Remove from local list
    allAttachments.value = allAttachments.value.filter(
      (a) => a.id !== attachmentToDelete.value!.id
    )

    showDeleteDialog.value = false
    attachmentToDelete.value = null
  } catch (error) {
    console.error('Delete error:', error)
    if (error instanceof Error) {
      showError(error.message)
    } else {
      showError('Failed to delete file')
    }
  } finally {
    isDeleting.value = false
  }
}

// Handle upload button click
function handleUploadClick() {
  fileInputRef.value?.click()
}

// Handle file selection and upload
async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files

  if (!files || files.length === 0) return

  isUploading.value = true

  try {
    // Upload each file to client-level endpoint
    for (const file of Array.from(files)) {
      await uploadClientFile(file)
    }

    // Refresh file list
    await loadClientFiles()

    showSuccess(
      `Successfully uploaded ${files.length} file${files.length !== 1 ? 's' : ''}`
    )
  } catch (error) {
    console.error('Upload error:', error)
    // Individual file errors are already shown in uploadClientFile
  } finally {
    isUploading.value = false
    // Reset file input
    if (target) {
      target.value = ''
    }
  }
}

// Drag and drop handlers
function handleDragEnter(e: DragEvent) {
  e.preventDefault()
  dragCounter.value++
  isDragging.value = true
}

function handleDragLeave(e: DragEvent) {
  e.preventDefault()
  dragCounter.value--
  if (dragCounter.value === 0) {
    isDragging.value = false
  }
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
}

async function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  dragCounter.value = 0

  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length === 0) return

  // Create a synthetic file input element for processing
  const fileList = e.dataTransfer?.files
  if (!fileList) return

  // Create synthetic event
  const syntheticEvent = {
    target: { files: fileList, value: '' },
  } as unknown as Event

  await handleFileSelect(syntheticEvent)
}

// Upload a single file to client-level endpoint
async function uploadClientFile(file: File): Promise<void> {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await apiClient.post(
      `/clients/${props.clientId}/attachments`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000, // 30 second timeout
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            )
            uploadProgress.value.set(file.name, percentCompleted)
          }
        },
      }
    )

    // Remove progress tracking
    uploadProgress.value.delete(file.name)

    console.log(`Uploaded ${file.name}`, response.data)
  } catch (error) {
    console.error(`Failed to upload ${file.name}:`, error)
    uploadProgress.value.delete(file.name)

    // Show error for this specific file
    showError(`Failed to upload ${file.name}`)
    throw error
  }
}

// Format date for display
function formatDate(dateString: string): string {
  return format(new Date(dateString), 'MMM d, yyyy')
}

// Intersection Observer for lazy loading thumbnails
const thumbnailObserver = ref<IntersectionObserver | null>(null)

// Lifecycle
onMounted(() => {
  loadClientFiles()

  // Set up Intersection Observer for lazy loading thumbnails
  if ('IntersectionObserver' in window) {
    thumbnailObserver.value = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const fileId = entry.target.getAttribute('data-file-id')
            if (fileId) {
              const file = allAttachments.value.find((f) => f.id === fileId)
              if (file && isImageType(file.file_type)) {
                fetchThumbnail(file)
              }
            }
          }
        })
      },
      {
        rootMargin: '100px', // Start loading 100px before entering viewport
        threshold: 0.01,
      }
    )
  }

  // Add global keyboard listener for F2 shortcut
  document.addEventListener('keydown', handleGlobalKeydown)
})

// Cleanup
onBeforeUnmount(() => {
  if (thumbnailObserver.value) {
    thumbnailObserver.value.disconnect()
  }

  // Remove global keyboard listener
  document.removeEventListener('keydown', handleGlobalKeydown)
})

// Download from preview modal
async function handleDownloadFromPreview(attachment: AttachmentResponse) {
  const file = allAttachments.value.find((f) => f.id === attachment.id)
  if (file) {
    await handleDownload(file)
  }
}

// Download from PDF preview modal
async function handleDownloadFromPDFPreview(attachment: AttachmentResponse) {
  const file = allAttachments.value.find((f) => f.id === attachment.id)
  if (file) {
    await handleDownload(file)
  }
}

// Update preview index
function updatePreviewIndex(index: number) {
  previewImageIndex.value = index
}

// Thumbnail management
async function fetchThumbnail(file: AttachmentResponse): Promise<void> {
  // Don't fetch if already cached, loading, or errored
  if (
    thumbnailCache.value.has(file.id) ||
    thumbnailLoadingSet.value.has(file.id) ||
    thumbnailErrorSet.value.has(file.id)
  ) {
    return
  }

  // Only fetch for images
  if (!isImageType(file.file_type)) {
    return
  }

  thumbnailLoadingSet.value.add(file.id)

  try {
    let response

    // For client-level files (no session_id), use client endpoint
    if (!file.session_id) {
      response = await apiClient.get(
        `/clients/${props.clientId}/attachments/${file.id}/download`
      )
    } else {
      // For session-level files, use session endpoint
      response = await apiClient.get(
        `/sessions/${file.session_id}/attachments/${file.id}/download`
      )
    }

    const downloadUrl = response.data.download_url

    // Cache the URL
    thumbnailCache.value.set(file.id, downloadUrl)
  } catch (error) {
    console.error(`Failed to fetch thumbnail for ${file.id}:`, error)
    thumbnailErrorSet.value.add(file.id)
  } finally {
    thumbnailLoadingSet.value.delete(file.id)
  }
}

// Get thumbnail URL from cache
function getThumbnailUrl(fileId: string): string | null {
  return thumbnailCache.value.get(fileId) || null
}

// Check if thumbnail is loading
function isThumbnailLoading(fileId: string): boolean {
  return thumbnailLoadingSet.value.has(fileId)
}

// Check if thumbnail failed to load
function hasThumbnailError(fileId: string): boolean {
  return thumbnailErrorSet.value.has(fileId)
}

// Ref callback for thumbnail elements (for IntersectionObserver)
function onThumbnailMounted(el: Element | null, file: AttachmentResponse) {
  if (el && thumbnailObserver.value && isImageType(file.file_type)) {
    el.setAttribute('data-file-id', file.id)
    thumbnailObserver.value.observe(el)
  }
}

// Bulk selection functions
function toggleBulkMode() {
  isBulkMode.value = !isBulkMode.value
  if (!isBulkMode.value) {
    selectedFileIds.value.clear()
  }
}

function toggleFileSelection(fileId: string) {
  if (selectedFileIds.value.has(fileId)) {
    selectedFileIds.value.delete(fileId)
  } else {
    selectedFileIds.value.add(fileId)
  }
}

function toggleSelectAll() {
  if (allVisibleFilesSelected.value) {
    // Deselect all visible files
    filteredAttachments.value.forEach((file) => {
      selectedFileIds.value.delete(file.id)
    })
  } else {
    // Select all visible files
    filteredAttachments.value.forEach((file) => {
      selectedFileIds.value.add(file.id)
    })
  }
}

function isFileSelected(fileId: string): boolean {
  return selectedFileIds.value.has(fileId)
}

/**
 * Extract filename from Content-Disposition header
 * Example: 'attachment; filename="client-files-20251019_123456.zip"'
 */
function extractFilename(contentDisposition: string | undefined): string | null {
  if (!contentDisposition) return null

  const filenameMatch = contentDisposition.match(
    /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/
  )
  if (filenameMatch && filenameMatch[1]) {
    return filenameMatch[1].replace(/['"]/g, '')
  }

  return null
}

// Bulk download as ZIP
async function handleBulkDownload() {
  if (selectedFilesCount.value === 0) return

  // Client-side validation: limit to 50 files
  if (selectedFilesCount.value > 50) {
    showError('Maximum 50 files can be downloaded at once')
    return
  }

  isBulkDownloading.value = true

  try {
    showInfo('Preparing ZIP file...', { timeout: 3000 })

    // Get list of selected attachment IDs
    const attachmentIds = Array.from(selectedFileIds.value)

    // Call backend ZIP download endpoint
    const response = await apiClient.post(
      `/clients/${props.clientId}/attachments/download-multiple`,
      { attachment_ids: attachmentIds },
      {
        responseType: 'blob', // Important: tells axios to treat response as binary
        timeout: 120000, // 2 minute timeout for large ZIPs
      }
    )

    // Create blob URL and trigger download
    const blob = new Blob([response.data], { type: 'application/zip' })
    const blobUrl = URL.createObjectURL(blob)

    // Extract filename from Content-Disposition header or use default
    const contentDisposition = response.headers['content-disposition']
    const filename =
      extractFilename(contentDisposition) || `client-files-${Date.now()}.zip`

    // Trigger download
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    // Clean up blob URL
    setTimeout(() => URL.revokeObjectURL(blobUrl), 100)

    showSuccess(`Downloaded ${selectedFilesCount.value} files as ZIP`)
  } catch (error) {
    console.error('Bulk download error:', error)

    // Handle specific error cases
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 400) {
        showError('Invalid request. Please try again.')
      } else if (error.response?.status === 403) {
        showError('Access denied to one or more files')
      } else if (error.response?.status === 404) {
        showError('One or more files not found')
      } else if (error.response?.status === 413) {
        showError('Total file size exceeds 100 MB. Please select fewer files.')
      } else if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        showError('Download timed out. Please try selecting fewer files.')
      } else {
        showError('Failed to download files. Please try again.')
      }
    } else {
      showError('Failed to download files')
    }
  } finally {
    isBulkDownloading.value = false
  }
}

// Bulk delete
function confirmBulkDelete() {
  if (selectedFilesCount.value === 0) return
  showBulkDeleteDialog.value = true
}

function cancelBulkDelete() {
  showBulkDeleteDialog.value = false
}

async function handleBulkDelete() {
  if (selectedFilesCount.value === 0) return

  isBulkDeleting.value = true

  try {
    const fileIds = Array.from(selectedFileIds.value)
    let successCount = 0
    let errorCount = 0

    // Delete each file
    for (const fileId of fileIds) {
      const file = allAttachments.value.find((f) => f.id === fileId)
      if (!file) continue

      try {
        // Use appropriate delete endpoint based on file type
        if (file.session_id) {
          await deleteAttachment(file.session_id, fileId)
        } else {
          await apiClient.delete(`/clients/${props.clientId}/attachments/${fileId}`)
        }

        // Remove from local list
        allAttachments.value = allAttachments.value.filter((a) => a.id !== fileId)
        selectedFileIds.value.delete(fileId)
        successCount++
      } catch (error) {
        console.error(`Failed to delete file ${fileId}:`, error)
        errorCount++
      }
    }

    // Show results
    if (successCount > 0) {
      showSuccess(`Deleted ${successCount} file${successCount !== 1 ? 's' : ''}`)
    }
    if (errorCount > 0) {
      showError(`Failed to delete ${errorCount} file${errorCount !== 1 ? 's' : ''}`)
    }

    // Exit bulk mode if all files deleted
    if (selectedFileIds.value.size === 0) {
      isBulkMode.value = false
    }

    showBulkDeleteDialog.value = false
  } catch (error) {
    console.error('Bulk delete error:', error)
    showError('Failed to delete files')
  } finally {
    isBulkDeleting.value = false
  }
}

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
    const index = allAttachments.value.findIndex((f) => f.id === file.id)
    if (index !== -1) {
      allAttachments.value[index] = updatedFile
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
        const file = allAttachments.value.find((f) => f.id === fileId)
        if (file && !isEditing(file.id)) {
          handleRenameClick(file)
        }
      }
    }
  }
}
</script>

<template>
  <div
    class="client-files-tab relative"
    @dragenter="handleDragEnter"
    @dragleave="handleDragLeave"
    @dragover="handleDragOver"
    @drop="handleDrop"
  >
    <!-- Drag and Drop Overlay -->
    <Transition name="drag-overlay">
      <div
        v-if="isDragging"
        class="pointer-events-none fixed inset-0 z-40 flex items-center justify-center bg-blue-500/10 backdrop-blur-sm"
      >
        <div
          class="rounded-2xl border-4 border-dashed border-blue-500 bg-white p-12 shadow-2xl"
        >
          <svg
            class="mx-auto h-16 w-16 text-blue-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <p class="mt-4 text-xl font-semibold text-slate-900">Drop files to upload</p>
          <p class="mt-2 text-sm text-slate-600">
            JPEG, PNG, WebP, or PDF up to 10 MB each
          </p>
        </div>
      </div>
    </Transition>

    <!-- Header -->
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-slate-900">Files & Documents</h2>
    </div>

    <!-- Search and Filter Bar -->
    <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
      <!-- Search Input -->
      <div class="relative flex-1">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search files..."
          class="w-full rounded-lg border border-slate-300 bg-white py-2 pr-10 pl-10 text-sm transition-colors focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none"
        />
        <!-- Search Icon -->
        <svg
          class="pointer-events-none absolute top-1/2 left-3 h-5 w-5 -translate-y-1/2 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <!-- Clear Button -->
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="absolute top-1/2 right-3 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-600 focus:outline-none"
          aria-label="Clear search"
        >
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <!-- Filter Dropdown -->
      <select
        v-model="filterType"
        class="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm transition-colors focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none"
      >
        <option value="all">All Files</option>
        <option value="images">Images Only</option>
        <option value="pdfs">PDFs Only</option>
      </select>

      <!-- Select Files Button (only show when files exist) -->
      <button
        v-if="allAttachments.length > 0"
        type="button"
        @click="toggleBulkMode"
        class="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors focus:ring-2 focus:ring-emerald-500/20 focus:outline-none"
        :class="
          isBulkMode
            ? 'border-emerald-600 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
        "
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            v-if="!isBulkMode"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
          />
          <path
            v-else
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
        {{ isBulkMode ? 'Cancel' : 'Select Files' }}
      </button>

      <!-- Upload Button -->
      <button
        type="button"
        @click="handleUploadClick"
        :disabled="isUploading"
        class="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        <svg
          v-if="!isUploading"
          class="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 4v16m8-8H4"
          />
        </svg>
        <svg v-else class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
        {{ isUploading ? 'Uploading...' : 'Upload Files' }}
      </button>
    </div>

    <!-- Bulk Actions Toolbar (appears when in bulk mode) -->
    <Transition name="bulk-toolbar">
      <div
        v-if="isBulkMode"
        class="mb-4 flex items-center justify-between rounded-lg border-2 border-emerald-500 bg-emerald-50 p-4"
      >
        <div class="flex items-center gap-4">
          <!-- Select All Checkbox -->
          <label class="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              :checked="allVisibleFilesSelected"
              :indeterminate.prop="someVisibleFilesSelected"
              @change="toggleSelectAll"
              class="h-5 w-5 cursor-pointer rounded border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            />
            <span class="text-sm font-medium text-slate-700">
              {{
                allVisibleFilesSelected
                  ? 'Deselect All'
                  : selectedFilesCount > 0
                    ? 'Select All'
                    : 'Select All'
              }}
            </span>
          </label>

          <!-- Selected Count -->
          <div
            v-if="selectedFilesCount > 0"
            class="text-sm font-medium text-emerald-700"
          >
            {{ selectedFilesCount }} file{{
              selectedFilesCount !== 1 ? 's' : ''
            }}
            selected
          </div>
        </div>

        <!-- Bulk Actions -->
        <div v-if="selectedFilesCount > 0" class="flex items-center gap-2">
          <!-- Bulk Download -->
          <button
            @click="handleBulkDownload"
            :disabled="isBulkDownloading"
            class="inline-flex items-center gap-2 rounded-lg border border-emerald-600 bg-white px-4 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-50 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            :aria-label="`Download ${selectedFilesCount} selected files`"
          >
            <svg
              v-if="isBulkDownloading"
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
            <svg
              v-else
              class="h-4 w-4"
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
            {{ isBulkDownloading ? 'Preparing ZIP...' : 'Download Selected' }}
          </button>

          <!-- Bulk Delete -->
          <button
            @click="confirmBulkDelete"
            class="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:outline-none"
            :aria-label="`Delete ${selectedFilesCount} selected files`"
          >
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
            Delete Selected
          </button>
        </div>
      </div>
    </Transition>

    <!-- Hidden file input -->
    <input
      ref="fileInputRef"
      type="file"
      accept="image/jpeg,image/png,image/webp,application/pdf"
      multiple
      class="hidden"
      @change="handleFileSelect"
    />

    <!-- Loading State -->
    <SkeletonLoader v-if="loading" type="attachment" :count="5" />

    <!-- Error State -->
    <div
      v-else-if="loadError"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-center"
    >
      <p class="text-sm text-red-800">{{ loadError }}</p>
      <button
        @click="loadClientFiles"
        class="mt-2 text-sm font-medium text-red-600 hover:text-red-700 focus:underline focus:outline-none"
      >
        Try again
      </button>
    </div>

    <!-- Empty State (No Files at All) -->
    <div
      v-else-if="allAttachments.length === 0"
      class="rounded-lg border-2 border-dashed border-slate-300 bg-slate-50"
    >
      <EmptyState
        icon="document"
        title="No files yet"
        description="Upload client documents, photos, and intake forms. Session-specific files will appear here automatically."
      >
        <template #action>
          <button
            @click="handleUploadClick"
            :disabled="isUploading"
            class="mt-4 inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            <svg
              v-if="!isUploading"
              class="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 4v16m8-8H4"
              />
            </svg>
            <svg v-else class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
            {{ isUploading ? 'Uploading...' : 'Upload Files' }}
          </button>
        </template>
      </EmptyState>
    </div>

    <!-- No Results State (Filtered/Searched) -->
    <div
      v-else-if="hasNoResults"
      class="rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 py-12 text-center"
    >
      <svg
        class="mx-auto h-12 w-12 text-slate-400"
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
      <h3 class="mt-2 text-sm font-medium text-slate-900">{{ emptyResultsMessage }}</h3>
      <p class="mt-1 text-sm text-slate-500">Try a different search term or filter</p>
      <button
        v-if="searchQuery || filterType !== 'all'"
        @click="
          () => {
            searchQuery = ''
            filterType = 'all'
          }
        "
        class="mt-4 text-sm font-medium text-emerald-600 hover:text-emerald-700 focus:underline focus:outline-none"
      >
        Clear filters
      </button>
    </div>

    <!-- Files List Grouped by Month -->
    <div v-else class="space-y-6">
      <div v-for="monthGroup in filesByMonth" :key="monthGroup.monthKey">
        <!-- Month Header (sticky) -->
        <h3
          class="sticky top-0 z-10 mb-3 rounded-lg border-b-2 border-slate-300 bg-slate-100/95 px-4 py-2 text-base font-semibold text-slate-900 backdrop-blur-sm"
        >
          {{ monthGroup.label }} ({{ monthGroup.files.length }})
        </h3>

        <!-- Files in Month -->
        <div class="space-y-2">
          <div
            v-for="file in monthGroup.files"
            :key="file.id"
            :data-file-id="file.id"
            class="flex items-center gap-3 rounded-lg border p-4 shadow-sm transition-all"
            :class="
              isBulkMode && isFileSelected(file.id)
                ? 'border-emerald-500 bg-emerald-50'
                : 'border-slate-200 bg-white hover:shadow-md'
            "
            tabindex="0"
          >
            <!-- Checkbox (bulk mode) -->
            <div v-if="isBulkMode" class="flex flex-shrink-0 items-center">
              <input
                type="checkbox"
                :checked="isFileSelected(file.id)"
                @change="toggleFileSelection(file.id)"
                class="h-5 w-5 cursor-pointer rounded border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
                :aria-label="`Select ${file.file_name}`"
              />
            </div>

            <!-- Thumbnail or Icon -->
            <div
              :ref="(el) => onThumbnailMounted(el as Element | null, file)"
              class="flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-slate-100"
              :class="
                (isImageType(file.file_type) || file.file_type === 'application/pdf') &&
                'cursor-pointer hover:opacity-80'
              "
              @click="
                isImageType(file.file_type)
                  ? handlePreviewImage(file)
                  : file.file_type === 'application/pdf'
                    ? handlePreviewPDF(file)
                    : null
              "
            >
              <!-- Image Thumbnail -->
              <div v-if="isImageType(file.file_type)" class="relative h-full w-full">
                <!-- Loading state -->
                <div
                  v-if="isThumbnailLoading(file.id)"
                  class="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-100 to-blue-200"
                >
                  <svg
                    class="h-6 w-6 animate-spin text-blue-600"
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

                <!-- Thumbnail image -->
                <template
                  v-if="getThumbnailUrl(file.id) && !hasThumbnailError(file.id)"
                >
                  <img
                    :src="getThumbnailUrl(file.id) || ''"
                    :alt="file.file_name"
                    class="h-full w-full object-cover transition-opacity"
                    loading="lazy"
                    @error="thumbnailErrorSet.add(file.id)"
                  />
                </template>

                <!-- Fallback icon (not loaded yet or error) -->
                <div
                  v-else
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
              </div>

              <!-- PDF Icon -->
              <div
                v-else-if="file.file_type === 'application/pdf'"
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
              <div v-if="!isEditing(file.id)" class="flex items-center gap-2">
                <button
                  @click="handleRenameClick(file)"
                  class="truncate text-left text-sm font-medium text-slate-900 transition-colors hover:text-blue-600 focus:text-blue-600 focus:underline focus:outline-none"
                  :title="`${file.file_name} (Click or press F2 to rename)`"
                  :aria-label="`Rename ${file.file_name}`"
                >
                  {{ file.file_name }}
                </button>
                <span
                  class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                  :class="
                    file.file_type === 'application/pdf'
                      ? 'bg-red-100 text-red-800'
                      : 'bg-blue-100 text-blue-800'
                  "
                >
                  {{ getFileExtension(file.file_name) }}
                </span>
              </div>

              <!-- Edit Mode: Inline rename form -->
              <div v-else class="flex flex-col gap-1">
                <form
                  @submit.prevent="handleRenameSave(file)"
                  class="flex items-center gap-2"
                >
                  <div class="relative flex-1">
                    <input
                      :ref="
                        (el) =>
                          renameInputRefs.set(file.id, el as HTMLInputElement | null)
                      "
                      :value="getEditedName(file.id)"
                      type="text"
                      class="w-full rounded border-2 px-2 py-1 text-sm font-medium transition-colors focus:outline-none md:min-w-[16rem]"
                      :class="
                        getError(file.id)
                          ? 'border-red-500 focus:ring-2 focus:ring-red-500'
                          : 'border-blue-500 focus:ring-2 focus:ring-blue-500'
                      "
                      :disabled="isRenaming(file.id)"
                      :aria-label="'New filename'"
                      :aria-invalid="!!getError(file.id)"
                      :aria-describedby="
                        getError(file.id) ? `error-${file.id}` : undefined
                      "
                      @keydown="handleRenameKeydown($event, file)"
                      @input="
                        setEditedName(
                          file.id,
                          ($event.target as HTMLInputElement).value
                        )
                      "
                    />
                    <!-- Extension badge (read-only) -->
                    <span
                      class="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                    >
                      {{ getExtensionFromFilename(file.file_name) }}
                    </span>
                  </div>

                  <!-- Save Button -->
                  <button
                    type="submit"
                    :disabled="isRenaming(file.id)"
                    class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded p-1 text-green-600 transition-colors hover:bg-green-50 focus:ring-2 focus:ring-green-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:h-auto md:w-auto md:px-3 md:py-1.5"
                    :aria-label="'Save rename'"
                    title="Save (Enter)"
                  >
                    <svg
                      v-if="!isRenaming(file.id)"
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
                    <span class="ml-1.5 hidden text-sm font-medium md:inline"
                      >Save</span
                    >
                  </button>

                  <!-- Cancel Button -->
                  <button
                    type="button"
                    @click="cancelRename(file.id)"
                    :disabled="isRenaming(file.id)"
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
                    <span class="ml-1.5 hidden text-sm font-medium md:inline"
                      >Cancel</span
                    >
                  </button>
                </form>

                <!-- Inline error message -->
                <p
                  v-if="getError(file.id)"
                  :id="`error-${file.id}`"
                  class="text-sm text-red-600"
                  role="alert"
                >
                  {{ getError(file.id) }}
                </p>
              </div>
              <div class="mt-1 flex items-center gap-2 text-xs text-slate-600">
                <span>{{ formatFileSize(file.file_size_bytes) }}</span>
                <span aria-hidden="true">•</span>
                <span>{{ formatDate(file.created_at) }}</span>
              </div>

              <!-- Session Context Link -->
              <div
                v-if="file.is_session_file && file.session_id && file.session_date"
                class="mt-1.5"
              >
                <button
                  @click="navigateToSession(file.session_id)"
                  class="text-xs font-medium text-blue-600 hover:text-blue-800 focus:underline focus:outline-none"
                >
                  From: Session on {{ formatDate(file.session_date) }} →
                </button>
              </div>
              <p v-else class="mt-1.5 text-xs text-slate-500">From: Client record</p>
            </div>

            <!-- Actions -->
            <div class="flex flex-shrink-0 items-center gap-1">
              <!-- Download Button -->
              <button
                @click="handleDownload(file)"
                class="rounded p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:outline-none"
                :aria-label="`Download ${file.file_name}`"
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

              <!-- Delete Button -->
              <button
                @click="confirmDelete(file)"
                class="rounded p-2 text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600 focus:ring-2 focus:ring-red-500 focus:ring-offset-1 focus:outline-none"
                :aria-label="`Delete ${file.file_name}`"
                title="Delete"
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
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bulk Delete Confirmation Dialog -->
    <Teleport to="body">
      <div
        v-if="showBulkDeleteDialog"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="cancelBulkDelete"
      >
        <div
          class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="bulk-delete-dialog-title"
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
              <h3
                id="bulk-delete-dialog-title"
                class="text-lg font-semibold text-slate-900"
              >
                Delete {{ selectedFilesCount }} File{{
                  selectedFilesCount !== 1 ? 's' : ''
                }}
              </h3>
              <p class="mt-2 text-sm text-slate-600">
                Are you sure you want to delete these
                <strong class="font-medium text-slate-900"
                  >{{ selectedFilesCount }} file{{
                    selectedFilesCount !== 1 ? 's' : ''
                  }}</strong
                >? This action cannot be undone.
              </p>
            </div>
          </div>
          <div class="mt-6 flex justify-end gap-3">
            <button
              @click="cancelBulkDelete"
              type="button"
              :disabled="isBulkDeleting"
              class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              @click="handleBulkDelete"
              type="button"
              :disabled="isBulkDeleting"
              class="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:ring-2 focus:ring-red-600 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg
                v-if="isBulkDeleting"
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
              {{ isBulkDeleting ? 'Deleting...' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete Confirmation Dialog -->
    <Teleport to="body">
      <div
        v-if="showDeleteDialog"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
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

    <!-- Image Preview Modal -->
    <!-- Note: For client-level files without session_id, we pass both session-id and client-id -->
    <!-- The modal will use the appropriate endpoint based on whether the file has a session_id -->
    <ImagePreviewModal
      v-if="imageAttachments.length > 0 && imageAttachments[previewImageIndex]"
      :open="showImagePreview"
      :attachments="imageAttachments"
      :current-index="previewImageIndex"
      :session-id="imageAttachments[previewImageIndex]?.session_id || clientId"
      :client-id="clientId"
      @close="showImagePreview = false"
      @download="handleDownloadFromPreview"
      @update:current-index="updatePreviewIndex"
    />

    <!-- PDF Preview Modal -->
    <PDFPreviewModal
      v-if="pdfToPreview"
      :open="showPDFPreview"
      :attachment="pdfToPreview"
      :session-id="pdfToPreview.session_id || clientId"
      :client-id="clientId"
      @close="showPDFPreview = false"
      @download="handleDownloadFromPDFPreview"
    />
  </div>
</template>

<style scoped>
/* Smooth transitions */
.client-files-tab button {
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

/* Bulk toolbar transition */
.bulk-toolbar-enter-active,
.bulk-toolbar-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.bulk-toolbar-enter-from,
.bulk-toolbar-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Drag overlay transition */
.drag-overlay-enter-active,
.drag-overlay-leave-active {
  transition:
    opacity 0.2s ease,
    backdrop-filter 0.2s ease;
}

.drag-overlay-enter-from,
.drag-overlay-leave-to {
  opacity: 0;
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .bulk-toolbar-enter-active,
  .bulk-toolbar-leave-active,
  .drag-overlay-enter-active,
  .drag-overlay-leave-active {
    transition: none;
  }
}
</style>
