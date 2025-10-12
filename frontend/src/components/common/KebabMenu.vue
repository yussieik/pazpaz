<script setup lang="ts">
/**
 * KebabMenu Component
 *
 * A reusable, accessible kebab menu (three-dot menu) component with full keyboard
 * navigation and touch device support.
 *
 * Features:
 * - Full WCAG 2.1 AA keyboard accessibility (Tab, Enter, Space, Arrow keys, Escape)
 * - Touch-optimized with configurable mobile visibility
 * - Focus management and keyboard trapping
 * - Customizable menu positioning
 * - Support for destructive actions, icons, shortcuts, and dividers
 * - Loading states for async actions
 * - Smooth animations
 *
 * Usage:
 * ```vue
 * <KebabMenu
 *   aria-label="More actions for client John Doe"
 *   :items="menuItems"
 *   position="bottom-right"
 *   :always-visible-on-mobile="true"
 * />
 * ```
 *
 * @example
 * const menuItems: MenuItem[] = [
 *   {
 *     label: 'Edit',
 *     action: () => editItem(),
 *     shortcut: 'E'
 *   },
 *   {
 *     label: 'Delete',
 *     action: async () => await deleteItem(),
 *     destructive: true,
 *     icon: TrashIcon,
 *     divider: true
 *   }
 * ]
 */

import { ref, computed, nextTick, type Component } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import { vClickOutside } from '@/directives/clickOutside'

/**
 * MenuItem configuration interface
 */
export interface MenuItem {
  /** Menu item label */
  label: string

  /** Click handler - can be async */
  action: () => void | Promise<void>

  /** Icon component (optional) */
  icon?: Component

  /** Destructive action styling (red) */
  destructive?: boolean

  /** Keyboard shortcut hint (displayed but not bound) */
  shortcut?: string

  /** Disabled state */
  disabled?: boolean

  /** Show divider after this item */
  divider?: boolean
}

/**
 * Component props
 */
export interface Props {
  /** Label for screen readers */
  ariaLabel: string

  /** Menu items configuration */
  items: MenuItem[]

  /** Position of menu relative to button */
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left'

  /** Always visible on mobile (true) or hover-revealed (false) */
  alwaysVisibleOnMobile?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  position: 'bottom-right',
  alwaysVisibleOnMobile: false,
})

// State
const isOpen = ref(false)
const focusedIndex = ref(0)
const menuId = ref(`kebab-menu-${Math.random().toString(36).substring(2, 9)}`)
const triggerButtonRef = ref<HTMLButtonElement | null>(null)
const menuRef = ref<HTMLDivElement | null>(null)
const menuItemRefs = ref<HTMLButtonElement[]>([])
const isExecutingAction = ref(false)

/**
 * Position classes for menu positioning
 */
const positionClasses = computed(() => {
  const positions = {
    'bottom-right': 'top-12 right-4',
    'bottom-left': 'top-12 left-4',
    'top-right': 'bottom-12 right-4',
    'top-left': 'bottom-12 left-4',
  }
  return positions[props.position]
})

/**
 * Button visibility classes for mobile/desktop
 */
const buttonVisibilityClasses = computed(() => {
  if (props.alwaysVisibleOnMobile) {
    // Always visible on mobile, hover-revealed on desktop
    return 'opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100'
  } else {
    // Hover-revealed on all devices
    return 'opacity-0 group-hover:opacity-100 focus:opacity-100'
  }
})

/**
 * Open the menu and focus first item
 */
async function openMenu() {
  isOpen.value = true
  focusedIndex.value = 0

  // Focus first menu item on next tick
  await nextTick()
  focusFirstItem()
}

/**
 * Close the menu and return focus to trigger button
 */
function closeMenu() {
  isOpen.value = false
  focusedIndex.value = 0

  // Return focus to trigger button
  nextTick(() => {
    triggerButtonRef.value?.focus()
  })
}

/**
 * Toggle menu open/close
 */
function toggleMenu() {
  if (isOpen.value) {
    closeMenu()
  } else {
    openMenu()
  }
}

/**
 * Focus the first menu item
 */
function focusFirstItem() {
  if (menuItemRefs.value.length > 0) {
    menuItemRefs.value[0]?.focus()
  }
}

/**
 * Focus the last menu item
 */
function focusLastItem() {
  if (menuItemRefs.value.length > 0) {
    menuItemRefs.value[menuItemRefs.value.length - 1]?.focus()
  }
}

/**
 * Focus the next menu item (with wrapping)
 */
function focusNextItem() {
  if (menuItemRefs.value.length === 0) return

  focusedIndex.value = (focusedIndex.value + 1) % menuItemRefs.value.length
  menuItemRefs.value[focusedIndex.value]?.focus()
}

/**
 * Focus the previous menu item (with wrapping)
 */
function focusPreviousItem() {
  if (menuItemRefs.value.length === 0) return

  focusedIndex.value =
    focusedIndex.value === 0 ? menuItemRefs.value.length - 1 : focusedIndex.value - 1
  menuItemRefs.value[focusedIndex.value]?.focus()
}

/**
 * Execute a menu item action
 */
async function executeAction(item: MenuItem) {
  if (item.disabled || isExecutingAction.value) return

  isExecutingAction.value = true

  try {
    await item.action()
  } catch (error) {
    console.error('Menu action failed:', error)
  } finally {
    isExecutingAction.value = false
    closeMenu()
  }
}

/**
 * Handle keyboard navigation on the trigger button
 */
function handleTriggerKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    toggleMenu()
  }
}

/**
 * Handle keyboard navigation inside the menu
 */
function handleMenuKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case 'Escape':
      event.preventDefault()
      closeMenu()
      break

    case 'ArrowDown':
      event.preventDefault()
      focusNextItem()
      break

    case 'ArrowUp':
      event.preventDefault()
      focusPreviousItem()
      break

    case 'Home':
      event.preventDefault()
      focusFirstItem()
      break

    case 'End':
      event.preventDefault()
      focusLastItem()
      break

    case 'Tab':
      // Close menu when tabbing out
      event.preventDefault()
      closeMenu()
      break
  }
}

/**
 * Handle menu item click
 */
async function handleItemClick(item: MenuItem) {
  await executeAction(item)
}

/**
 * Handle menu item keydown
 */
async function handleItemKeydown(event: KeyboardEvent, item: MenuItem) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    await executeAction(item)
  }
}

/**
 * Set menu item ref
 */
function setMenuItemRef(el: unknown, index: number) {
  if (el) {
    menuItemRefs.value[index] = el as HTMLButtonElement
  }
}

// Global keyboard shortcuts (Escape to close)
onKeyStroke('Escape', (e) => {
  if (isOpen.value) {
    e.preventDefault()
    closeMenu()
  }
})
</script>

<template>
  <div class="relative">
    <!-- Kebab Menu Trigger Button -->
    <button
      ref="triggerButtonRef"
      type="button"
      :aria-label="ariaLabel"
      aria-haspopup="true"
      :aria-expanded="isOpen"
      :aria-controls="menuId"
      @click="toggleMenu"
      @keydown="handleTriggerKeydown"
      :class="[
        'kebab-menu-button',
        'rounded-md p-1.5 text-slate-400 transition-opacity duration-150',
        'hover:bg-slate-50 hover:text-slate-600',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500',
        'touch-manipulation',
        buttonVisibilityClasses,
      ]"
      style="min-width: 28px; min-height: 28px"
    >
      <!-- Ellipsis Vertical Icon (20x20px) -->
      <svg
        class="h-5 w-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
        />
      </svg>
    </button>

    <!-- Menu Popover -->
    <Transition
      enter-active-class="transition duration-100 ease-out"
      leave-active-class="transition duration-75 ease-in"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="isOpen"
        :id="menuId"
        ref="menuRef"
        v-click-outside="closeMenu"
        role="menu"
        aria-orientation="vertical"
        tabindex="-1"
        @keydown="handleMenuKeydown"
        :class="[
          'absolute z-10 w-40 rounded-lg border border-slate-200 bg-white py-1 shadow-lg',
          positionClasses,
        ]"
      >
        <template v-for="(item, index) in items" :key="index">
          <!-- Menu Item -->
          <button
            :ref="(el) => setMenuItemRef(el, index)"
            role="menuitem"
            :disabled="item.disabled || isExecutingAction"
            @click="handleItemClick(item)"
            @keydown="(e) => handleItemKeydown(e, item)"
            :class="[
              'flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset',
              item.destructive
                ? 'text-red-700 hover:bg-red-50'
                : 'text-slate-700 hover:bg-slate-50',
              item.disabled || isExecutingAction
                ? 'cursor-not-allowed opacity-50'
                : 'cursor-pointer',
            ]"
          >
            <!-- Icon (if provided) -->
            <component
              v-if="item.icon"
              :is="item.icon"
              class="h-4 w-4 flex-shrink-0"
              aria-hidden="true"
            />

            <!-- Label -->
            <span class="flex-1">{{ item.label }}</span>

            <!-- Keyboard Shortcut Hint -->
            <span
              v-if="item.shortcut"
              class="text-xs text-slate-400"
              aria-label="Keyboard shortcut"
            >
              {{ item.shortcut }}
            </span>
          </button>

          <!-- Divider -->
          <hr v-if="item.divider" class="my-1 border-slate-200" aria-hidden="true" />
        </template>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/**
 * Touch optimization
 * Prevents 300ms delay on touch devices
 */
.kebab-menu-button {
  touch-action: manipulation;
}

/**
 * Ensure minimum touch target size (WCAG 2.1 AA)
 * 44x44px for touch devices
 */
@media (pointer: coarse) {
  .kebab-menu-button {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
