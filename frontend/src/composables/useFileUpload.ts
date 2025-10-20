/**
 * File Upload Composable
 *
 * Provides file upload, download, and management functionality for session attachments.
 *
 * Features:
 * - Single and batch file uploads with progress tracking
 * - Download via presigned URLs
 * - Delete with confirmation
 * - Comprehensive error handling
 * - File validation before upload
 *
 * Usage:
 *   const { uploadFile, listAttachments, getDownloadUrl, deleteAttachment } = useFileUpload()
 */

import type { Ref } from 'vue'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import type {
  AttachmentResponse,
  AttachmentListResponse,
  DownloadUrlResponse,
  UploadProgress,
} from '@/types/attachments'
import { validateFile } from '@/types/attachments'

/**
 * Extended error type that includes request ID for debugging
 */
export interface FileUploadError extends Error {
  requestId?: string
}

/**
 * Extended AxiosError type that includes request ID
 */
interface AxiosErrorWithRequestId extends AxiosError<{ detail?: string }> {
  requestId?: string
}

export function useFileUpload() {
  /**
   * Upload a single file to a session with automatic retry on failure
   * @param sessionId - Session ID to attach file to
   * @param file - File to upload
   * @param progressRef - Optional ref to track upload progress
   * @param maxRetries - Maximum number of retry attempts (default: 3)
   * @returns Promise<AttachmentResponse>
   */
  async function uploadFile(
    sessionId: string,
    file: File,
    progressRef?: Ref<UploadProgress>,
    maxRetries = 3
  ): Promise<AttachmentResponse> {
    // Validate file before upload
    const validationError = validateFile(file)
    if (validationError) {
      throw new Error(validationError)
    }

    let lastError: Error | null = null

    // Retry logic
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        // Initialize progress tracking
        if (progressRef) {
          progressRef.value = {
            state: 'uploading',
            progress: 0,
            error: null,
          }
        }

        // Create FormData for multipart upload
        const formData = new FormData()
        formData.append('file', file)

        // Upload with progress tracking
        const response = await apiClient.post<AttachmentResponse>(
          `/sessions/${sessionId}/attachments`,
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
            timeout: 30000, // 30 second timeout
            onUploadProgress: (progressEvent) => {
              if (progressRef && progressEvent.total) {
                const percentCompleted = Math.round(
                  (progressEvent.loaded * 100) / progressEvent.total
                )
                progressRef.value = {
                  state: 'uploading',
                  progress: percentCompleted,
                  error: null,
                }
              }
            },
          }
        )

        // Update progress to success
        if (progressRef) {
          progressRef.value = {
            state: 'success',
            progress: 100,
            error: null,
          }
        }

        return response.data
      } catch (error) {
        const axiosError = error as AxiosErrorWithRequestId
        const errorMessage = getUploadErrorMessage(axiosError)
        const requestId = axiosError.requestId

        // Create error with request ID
        const uploadError = new Error(errorMessage) as FileUploadError
        if (requestId) {
          uploadError.requestId = requestId
        }
        lastError = uploadError

        // Don't retry for client errors (4xx) except 408 (timeout) and 429 (rate limit)
        const status = axiosError.response?.status
        const shouldRetry =
          !status || // Network error
          status === 408 || // Request timeout
          status === 429 || // Rate limit
          status >= 500 // Server error

        if (!shouldRetry || attempt === maxRetries) {
          // Update progress to error
          if (progressRef) {
            progressRef.value = {
              state: 'error',
              progress: 0,
              error: errorMessage,
            }
          }
          throw lastError
        }

        // Wait before retry (exponential backoff)
        const delayMs = Math.min(1000 * Math.pow(2, attempt), 5000)
        await new Promise((resolve) => setTimeout(resolve, delayMs))
      }
    }

    // Should never reach here, but TypeScript needs this
    throw lastError || new Error('Upload failed after retries')
  }

  /**
   * Upload multiple files to a session
   * @param sessionId - Session ID to attach files to
   * @param files - Files to upload
   * @param progressRefs - Optional array of refs to track individual upload progress
   * @returns Promise<AttachmentResponse[]>
   */
  async function uploadFiles(
    sessionId: string,
    files: File[],
    progressRefs?: Ref<UploadProgress>[]
  ): Promise<AttachmentResponse[]> {
    const results: AttachmentResponse[] = []

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      if (!file) continue

      const progressRef = progressRefs?.[i]

      try {
        const result = await uploadFile(sessionId, file, progressRef)
        results.push(result)
      } catch (error) {
        // Continue with other files even if one fails
        console.error(`Failed to upload ${file.name}:`, error)
      }
    }

    return results
  }

  /**
   * List all attachments for a session
   * @param sessionId - Session ID
   * @returns Promise<AttachmentListResponse>
   */
  async function listAttachments(sessionId: string): Promise<AttachmentListResponse> {
    try {
      const response = await apiClient.get<AttachmentListResponse>(
        `/sessions/${sessionId}/attachments`
      )
      return response.data
    } catch (error) {
      const axiosError = error as AxiosErrorWithRequestId
      const status = axiosError.response?.status
      const detail = axiosError.response?.data?.detail
      const requestId = axiosError.requestId

      let errorMessage = 'Failed to load attachments'
      if (status === 404) {
        errorMessage = 'Session not found. It may have been deleted.'
      } else if (status === 403) {
        errorMessage = "You don't have permission to view attachments for this session."
      } else if (detail) {
        errorMessage = detail
      }

      const uploadError = new Error(errorMessage) as FileUploadError
      if (requestId) {
        uploadError.requestId = requestId
      }
      throw uploadError
    }
  }

  /**
   * Get presigned download URL for an attachment
   * @param sessionId - Session ID
   * @param attachmentId - Attachment ID
   * @param expiresInMinutes - URL expiration time (default: 15 minutes)
   * @returns Promise<DownloadUrlResponse>
   */
  async function getDownloadUrl(
    sessionId: string,
    attachmentId: string,
    expiresInMinutes = 15
  ): Promise<DownloadUrlResponse> {
    try {
      const response = await apiClient.get<DownloadUrlResponse>(
        `/sessions/${sessionId}/attachments/${attachmentId}/download`,
        {
          params: {
            expires_in_minutes: expiresInMinutes,
          },
        }
      )
      return response.data
    } catch (error) {
      const axiosError = error as AxiosErrorWithRequestId
      const requestId = axiosError.requestId
      const errorMessage =
        axiosError.response?.data?.detail || 'Failed to get download URL'

      const uploadError = new Error(errorMessage) as FileUploadError
      if (requestId) {
        uploadError.requestId = requestId
      }
      throw uploadError
    }
  }

  /**
   * Download an attachment (opens in new tab)
   * @param sessionId - Session ID
   * @param attachmentId - Attachment ID
   * @param _filename - Filename for display purposes (reserved for future use)
   */
  async function downloadAttachment(
    sessionId: string,
    attachmentId: string,
    _filename: string
  ): Promise<void> {
    try {
      const { download_url } = await getDownloadUrl(sessionId, attachmentId)

      // Open in new tab
      const newTab = window.open(download_url, '_blank')
      if (!newTab) {
        throw new Error('Popup blocked. Please allow popups for this site.')
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('Failed to download file')
    }
  }

  /**
   * Delete an attachment (soft delete)
   * @param sessionId - Session ID
   * @param attachmentId - Attachment ID
   * @returns Promise<void>
   */
  async function deleteAttachment(
    sessionId: string,
    attachmentId: string
  ): Promise<void> {
    try {
      await apiClient.delete(`/sessions/${sessionId}/attachments/${attachmentId}`)
    } catch (error) {
      const axiosError = error as AxiosErrorWithRequestId
      const status = axiosError.response?.status
      const detail = axiosError.response?.data?.detail
      const requestId = axiosError.requestId

      let errorMessage = 'Failed to delete attachment'
      if (status === 404) {
        errorMessage = 'Attachment not found. It may have already been deleted.'
      } else if (status === 403) {
        errorMessage = "You don't have permission to delete this attachment."
      } else if (detail) {
        errorMessage = detail
      }

      const uploadError = new Error(errorMessage) as FileUploadError
      if (requestId) {
        uploadError.requestId = requestId
      }
      throw uploadError
    }
  }

  /**
   * Get user-friendly error message from API error
   */
  function getUploadErrorMessage(error: AxiosError<{ detail?: string }>): string {
    // Network error (no response)
    if (!error.response) {
      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        return 'Upload is taking longer than expected. The file may be too large or your connection may be slow.'
      }
      return 'Connection lost. Please check your internet connection and try again.'
    }

    const status = error.response.status
    const detail = error.response.data?.detail

    switch (status) {
      case 401:
        return 'Session expired. Please log in again.'
      case 403:
        return "You don't have permission to upload files to this session."
      case 404:
        return 'Session not found. It may have been deleted.'
      case 413:
        return detail || 'File too large (max 10 MB). Consider compressing the file.'
      case 415:
        return 'Unsupported file type. Accepted: JPEG, PNG, WebP, PDF.'
      case 422:
        return 'File validation failed. The file may be corrupted or in an unsupported format.'
      case 429:
        return 'Upload rate limit exceeded. Please wait 60 seconds and try again.'
      case 500:
        return 'Upload failed due to a server error. Please try again.'
      default:
        return detail || 'Upload failed. Please try again.'
    }
  }

  return {
    uploadFile,
    uploadFiles,
    listAttachments,
    getDownloadUrl,
    downloadAttachment,
    deleteAttachment,
  }
}
