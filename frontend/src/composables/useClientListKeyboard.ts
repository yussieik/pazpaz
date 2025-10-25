import { ref, type Ref, onMounted, onUnmounted } from 'vue'
import type { ClientListItem } from '@/types/client'
import { useScreenReader } from './useScreenReader'

/**
 * Composable for keyboard navigation in the clients list
 *
 * Implements Priority 1 keyboard navigation features:
 * - Arrow keys (Up/Down) to navigate through client cards
 * - Home/End to jump to first/last client
 * - `/` to focus search input
 * - Escape to clear search (two-press: clear text, then blur)
 * - Focus restoration when returning from detail view
 *
 * @param filteredClients - Reactive array of clients currently visible
 * @param onClientSelect - Callback when user selects a client (Enter key)
 * @param searchInputRef - Reference to search input element
 */
export function useClientListKeyboard(
  filteredClients: Ref<ClientListItem[]>,
  onClientSelect: (client: ClientListItem) => void,
  searchInputRef: Ref<HTMLInputElement | undefined>
) {
  const focusedIndex = ref(-1)
  const cardRefs = ref<(HTMLElement | null)[]>([])
  const { announce } = useScreenReader()

  /**
   * Store reference to a card element by index
   */
  function setCardRef(el: HTMLElement | null, index: number) {
    cardRefs.value[index] = el
  }

  /**
   * Scroll the focused card into view smoothly
   * Respects prefers-reduced-motion setting
   */
  function scrollToFocused() {
    if (focusedIndex.value >= 0 && cardRefs.value[focusedIndex.value]) {
      const prefersReducedMotion = window.matchMedia(
        '(prefers-reduced-motion: reduce)'
      ).matches
      cardRefs.value[focusedIndex.value]?.scrollIntoView({
        behavior: prefersReducedMotion ? 'auto' : 'smooth',
        block: 'nearest',
      })
    }
  }

  /**
   * Move focus to a specific client by index
   * Announces to screen reader
   */
  function focusClient(index: number) {
    if (index < 0 || index >= filteredClients.value.length) return

    focusedIndex.value = index
    scrollToFocused()

    // Focus the card for keyboard interaction
    const card = cardRefs.value[index]
    if (card) {
      card.focus()
    }

    // Screen reader announcement
    const client = filteredClients.value[index]
    if (!client) return
    const position = index + 1
    const total = filteredClients.value.length
    announce(`Client ${position} of ${total}: ${client.full_name}`)
  }

  /**
   * Handle keyboard navigation
   */
  function handleKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement

    // Skip if typing in an input (except for / shortcut)
    const isTypingInInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA'

    // `/` to focus search from anywhere on page
    if (e.key === '/' && !isTypingInInput) {
      e.preventDefault()
      searchInputRef.value?.focus()
      if (searchInputRef.value) {
        searchInputRef.value.value = '' // Clear search for fresh start
        // Trigger input event to update filtered clients
        searchInputRef.value.dispatchEvent(new Event('input', { bubbles: true }))
      }
      return
    }

    // Arrow key navigation (works when NOT typing in input OR when in search input)
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (filteredClients.value.length === 0) return

      if (focusedIndex.value === -1) {
        focusClient(0)
      } else {
        const nextIndex = (focusedIndex.value + 1) % filteredClients.value.length
        focusClient(nextIndex)
      }
      return
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (filteredClients.value.length === 0) return

      if (focusedIndex.value === -1) {
        focusClient(filteredClients.value.length - 1)
      } else {
        const prevIndex =
          (focusedIndex.value - 1 + filteredClients.value.length) %
          filteredClients.value.length
        focusClient(prevIndex)
      }
      return
    }

    if (e.key === 'Home') {
      e.preventDefault()
      if (filteredClients.value.length === 0) return
      focusClient(0)
      return
    }

    if (e.key === 'End') {
      e.preventDefault()
      if (filteredClients.value.length === 0) return
      focusClient(filteredClients.value.length - 1)
      return
    }

    // Escape to clear search (two-press behavior)
    if (e.key === 'Escape' && target === searchInputRef.value) {
      if (searchInputRef.value?.value) {
        // First press: clear search text
        e.preventDefault()
        searchInputRef.value.value = ''
        // Trigger input event to update filtered clients
        searchInputRef.value.dispatchEvent(new Event('input', { bubbles: true }))
        announce('Search cleared, showing all clients')
      } else {
        // Second press: blur search and focus first card
        e.preventDefault()
        searchInputRef.value?.blur()
        if (filteredClients.value.length > 0) {
          focusClient(0)
        }
      }
      return
    }

    // Enter to select focused client
    if (e.key === 'Enter' && focusedIndex.value >= 0 && !isTypingInInput) {
      const client = filteredClients.value[focusedIndex.value]
      if (client) {
        onClientSelect(client)
      }
      return
    }
  }

  /**
   * Restore focus to a specific client by ID
   * Used when returning from client detail view
   */
  function restoreFocusToClient(clientId: string) {
    const index = filteredClients.value.findIndex((c) => c.id === clientId)
    if (index !== -1) {
      // Use setTimeout to ensure DOM is ready
      setTimeout(() => {
        focusClient(index)
        const client = filteredClients.value[index]
        if (client) {
          announce(`Returned to ${client.full_name}`)
        }
      }, 100)
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return {
    focusedIndex,
    setCardRef,
    restoreFocusToClient,
  }
}
