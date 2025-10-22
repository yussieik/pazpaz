/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Request schema for renaming an attachment.
 *
 * The filename is validated and normalized:
 * - Whitespace is trimmed
 * - Length must be 1-255 characters
 * - Invalid characters are rejected: / \ : * ? " < > |
 * - File extension is preserved automatically
 * - Duplicate filenames are rejected
 */
export type AttachmentRenameRequest = {
  /**
   * New filename (extension will be preserved automatically)
   */
  file_name: string
}
