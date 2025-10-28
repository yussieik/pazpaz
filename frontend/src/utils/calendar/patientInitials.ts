/**
 * Patient Initials Utility
 *
 * Generates patient initials from full names for mobile calendar display.
 * Handles edge cases like single names, multi-word names, and special characters.
 *
 * @module utils/calendar/patientInitials
 */

/**
 * Generate patient initials from full name
 *
 * Strategy:
 * - Single name: Use first two letters (e.g., "Madonna" → "MA")
 * - Multiple names: First initial + Last initial (e.g., "John Smith" → "JS")
 * - Null/empty: Return "??" as unknown placeholder
 *
 * Edge cases handled:
 * - Special characters and emojis are stripped
 * - Multiple consecutive spaces are normalized
 * - Non-Latin characters (Unicode) are preserved
 *
 * @param fullName - Patient's full name (may be null or undefined)
 * @returns Two-letter uppercase initials or "??" for unknown
 *
 * @example
 * getPatientInitials("Itamar Hornik") // "IH"
 * getPatientInitials("Madonna") // "MA"
 * getPatientInitials("John Paul Smith") // "JS"
 * getPatientInitials(null) // "??"
 * getPatientInitials("") // "??"
 */
export function getPatientInitials(fullName: string | null | undefined): string {
  if (!fullName || fullName.trim() === '') {
    return '??'
  }

  // Strip emojis and special characters, keeping only letters, numbers, and spaces
  // \p{L} matches any Unicode letter, \p{N} matches any Unicode number
  const cleaned = fullName.replace(/[^\p{L}\p{N}\s]/gu, '').trim()

  if (!cleaned) {
    return '??'
  }

  // Split by whitespace and filter out empty strings
  const words = cleaned.split(/\s+/).filter(Boolean)

  if (words.length === 0) {
    return '??'
  }

  if (words.length === 1) {
    // Single name: use first two letters
    const word = words[0]
    if (!word) return '??'
    return word.substring(0, 2).toUpperCase()
  }

  // Multiple names: first initial + last initial
  const firstWord = words[0]
  const lastWord = words[words.length - 1]

  if (!firstWord || !lastWord || !firstWord[0] || !lastWord[0]) {
    return '??'
  }

  const firstInitial = firstWord[0]
  const lastInitial = lastWord[0]

  return (firstInitial + lastInitial).toUpperCase()
}
