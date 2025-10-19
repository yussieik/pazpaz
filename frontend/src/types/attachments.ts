/**
 * File attachment type definitions for session notes
 *
 * Matches backend API responses for file attachments
 */

/**
 * File attachment response (matches backend SessionAttachmentResponse)
 */
export interface AttachmentResponse {
  id: string
  session_id: string | null // null for client-level files
  client_id: string // always present
  file_name: string
  file_type: string
  file_size_bytes: number
  created_at: string
  session_date: string | null // from session.appointment_datetime
  is_session_file: boolean // true if session-level
}

/**
 * Download URL response (presigned URL with expiration)
 */
export interface DownloadUrlResponse {
  download_url: string
  expires_in_seconds: number
}

/**
 * List attachments response (paginated)
 */
export interface AttachmentListResponse {
  items: AttachmentResponse[]
  total: number
}

/**
 * Upload progress state
 */
export type UploadState = 'idle' | 'uploading' | 'success' | 'error'

/**
 * Upload progress tracking
 */
export interface UploadProgress {
  state: UploadState
  progress: number // 0-100
  error: string | null
}

/**
 * Allowed file types for attachments
 */
export const ALLOWED_FILE_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'application/pdf',
] as const

/**
 * File size limits
 */
export const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB
export const MAX_TOTAL_SIZE = 50 * 1024 * 1024 // 50 MB

/**
 * File type extensions for display
 */
export const FILE_TYPE_EXTENSIONS: Record<string, string> = {
  'image/jpeg': 'JPG',
  'image/png': 'PNG',
  'image/webp': 'WebP',
  'application/pdf': 'PDF',
}

/**
 * Check if file type is an image
 */
export function isImageType(fileType: string): boolean {
  return fileType.startsWith('image/')
}

/**
 * Format file size in human-readable format
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

/**
 * Validate file before upload
 * Returns error message or null if valid
 */
export function validateFile(file: File): string | null {
  // Type assertion is safe here - we're checking if file.type matches our allowed types
  type AllowedType = (typeof ALLOWED_FILE_TYPES)[number]
  if (!ALLOWED_FILE_TYPES.includes(file.type as AllowedType)) {
    return 'Unsupported file type. Please upload JPEG, PNG, WebP, or PDF.'
  }
  if (file.size > MAX_FILE_SIZE) {
    return `File too large (max ${formatFileSize(MAX_FILE_SIZE)})`
  }
  return null
}

/**
 * Get file extension from filename
 */
export function getFileExtension(filename: string): string {
  const parts = filename.split('.')
  const lastPart = parts[parts.length - 1]
  return parts.length > 1 && lastPart ? lastPart.toUpperCase() : ''
}

/**
 * Attachment with session context for client-level file views
 * Now an alias since AttachmentResponse includes all context fields
 */
export type AttachmentWithContext = AttachmentResponse
