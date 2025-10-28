/**
 * RTL Text Direction Directive
 *
 * Automatically detects and applies correct text direction (LTR/RTL) for text inputs.
 * Uses HTML5's native `dir="auto"` attribute for browser-native bidirectional text support.
 *
 * Features:
 * - Auto-detects RTL languages (Hebrew, Arabic, etc.) based on first strong directional character
 * - Works with input, textarea, and contenteditable elements
 * - No JavaScript detection needed - browser handles all bidirectional rendering
 * - Supports mixed LTR/RTL content seamlessly
 *
 * Usage:
 *   <input v-rtl />
 *   <textarea v-rtl />
 *   <div contenteditable v-rtl />
 *
 * Browser support:
 * - All modern browsers support dir="auto" natively
 * - Fallback behavior: defaults to LTR if not supported (graceful degradation)
 */

import type { Directive } from 'vue'

export const vRtl: Directive = {
  mounted(el: HTMLElement) {
    // Set dir="auto" to enable automatic text direction detection
    el.setAttribute('dir', 'auto')
  },
  updated(el: HTMLElement) {
    // Ensure dir="auto" persists after updates
    // This handles cases where the element might be re-rendered
    if (!el.hasAttribute('dir') || el.getAttribute('dir') !== 'auto') {
      el.setAttribute('dir', 'auto')
    }
  },
}
