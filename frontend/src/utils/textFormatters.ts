/**
 * Text formatting utilities
 *
 * Shared utility functions for text manipulation and display.
 * Used across components for consistent text formatting.
 */

/**
 * Truncate text to a maximum length with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated text with ellipsis if needed
 */
export function truncate(text: string | null | undefined, maxLength: number): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

/**
 * Intelligently truncate text to a maximum length, preserving whole words
 * @param text - Text to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated text with ellipsis if needed, preserving word boundaries
 */
export function smartTruncate(
  text: string | null | undefined,
  maxLength: number
): string {
  if (!text) return ''
  if (text.length <= maxLength) return text

  // Find the last space before maxLength
  const truncated = text.substring(0, maxLength)
  const lastSpaceIndex = truncated.lastIndexOf(' ')

  // If there's a space, truncate at word boundary
  // Otherwise, just use the hard limit
  if (lastSpaceIndex > maxLength * 0.7) {
    // Only use word boundary if we're not losing too much (>70% of target length)
    return truncated.substring(0, lastSpaceIndex).trim() + '...'
  }

  return truncated.trim() + '...'
}
