/**
 * Filename Validation Utilities
 *
 * Client-side validation for file renaming.
 * Matches backend validation rules for instant feedback.
 *
 * Backend implementation reference:
 * /backend/src/pazpaz/utils/filename_validation.py
 */

/**
 * Validation error type
 */
export interface FilenameValidationError {
  valid: false
  error: string
}

/**
 * Validation success type
 */
export interface FilenameValidationSuccess {
  valid: true
  trimmed: string
}

/**
 * Validation result
 */
export type FilenameValidationResult = FilenameValidationSuccess | FilenameValidationError

/**
 * Invalid characters pattern (matches backend)
 * Prohibited: / \ : * ? " < > |
 */
const INVALID_CHARS_PATTERN = /[/\\:*?"<>|]/

/**
 * Maximum filename length (matches backend)
 */
const MAX_FILENAME_LENGTH = 255

/**
 * Validate filename according to backend rules
 *
 * Rules:
 * 1. Cannot be empty (after trimming)
 * 2. Cannot exceed 255 characters
 * 3. Cannot contain invalid characters: / \ : * ? " < > |
 *
 * @param filename - The filename to validate (without extension)
 * @returns Validation result with error message or trimmed filename
 */
export function validateFilename(filename: string): FilenameValidationResult {
  // Rule 1: Trim whitespace
  const trimmed = filename.trim()

  // Rule 2: Check if empty
  if (trimmed.length === 0) {
    return {
      valid: false,
      error: 'Filename cannot be empty',
    }
  }

  // Rule 3: Check length
  if (trimmed.length > MAX_FILENAME_LENGTH) {
    return {
      valid: false,
      error: `Filename too long (max ${MAX_FILENAME_LENGTH} characters)`,
    }
  }

  // Rule 4: Check for invalid characters
  if (INVALID_CHARS_PATTERN.test(trimmed)) {
    return {
      valid: false,
      error: 'Filename contains invalid characters (/ \\ : * ? " < > |)',
    }
  }

  return {
    valid: true,
    trimmed,
  }
}

/**
 * Extract filename without extension
 *
 * @param filename - Full filename with extension
 * @returns Filename without extension
 *
 * @example
 * getFilenameWithoutExtension('document.pdf') // 'document'
 * getFilenameWithoutExtension('photo.backup.jpg') // 'photo.backup'
 * getFilenameWithoutExtension('noextension') // 'noextension'
 */
export function getFilenameWithoutExtension(filename: string): string {
  const lastDotIndex = filename.lastIndexOf('.')
  if (lastDotIndex === -1 || lastDotIndex === 0) {
    // No extension or hidden file (e.g., '.gitignore')
    return filename
  }
  return filename.substring(0, lastDotIndex)
}

/**
 * Extract file extension from filename
 *
 * @param filename - Full filename with extension
 * @returns Extension including dot (e.g., '.jpg') or empty string
 *
 * @example
 * getFileExtension('document.pdf') // '.pdf'
 * getFileExtension('photo.backup.jpg') // '.jpg'
 * getFileExtension('noextension') // ''
 */
export function getFileExtension(filename: string): string {
  const lastDotIndex = filename.lastIndexOf('.')
  if (lastDotIndex === -1 || lastDotIndex === 0) {
    return ''
  }
  return filename.substring(lastDotIndex)
}

/**
 * Sanitize filename for display in rename input
 *
 * - Removes extension for editing (backend will re-add it)
 * - Trims whitespace
 *
 * @param filename - Full filename with extension
 * @returns Sanitized filename for editing
 */
export function sanitizeFilenameForRename(filename: string): string {
  return getFilenameWithoutExtension(filename).trim()
}
