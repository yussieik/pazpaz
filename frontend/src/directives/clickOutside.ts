/**
 * Click Outside Directive
 *
 * Vue directive that calls a handler when a click occurs outside the bound element.
 * Used for closing popovers, dropdowns, and modals.
 *
 * Usage:
 *   <div v-click-outside="handleClickOutside">...</div>
 *
 * The handler will be called with the click event when a click occurs
 * outside the element (and its descendants).
 */

import type { Directive, DirectiveBinding } from 'vue'

interface ClickOutsideElement extends HTMLElement {
  __clickOutsideHandler?: (event: MouseEvent) => void
}

export const vClickOutside: Directive = {
  mounted(el: ClickOutsideElement, binding: DirectiveBinding) {
    // Create handler that checks if click is outside element
    el.__clickOutsideHandler = (event: MouseEvent) => {
      const target = event.target as Node

      // Check if click is outside element and its descendants
      if (!(el === target || el.contains(target))) {
        // Call the provided handler
        binding.value(event)
      }
    }

    // Add listener on next tick to avoid immediate triggering
    // (the click that opened the popover would otherwise close it immediately)
    setTimeout(() => {
      document.addEventListener('click', el.__clickOutsideHandler!)
    }, 0)
  },

  unmounted(el: ClickOutsideElement) {
    // Clean up event listener
    if (el.__clickOutsideHandler) {
      document.removeEventListener('click', el.__clickOutsideHandler)
      delete el.__clickOutsideHandler
    }
  },
}
