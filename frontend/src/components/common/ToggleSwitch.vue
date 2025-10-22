<script setup lang="ts">
/**
 * ToggleSwitch Component
 *
 * Fully accessible toggle switch component for PazPaz settings.
 * Follows WCAG 2.1 AA accessibility guidelines.
 *
 * @example
 * <ToggleSwitch
 *   v-model="emailEnabled"
 *   label="Enable email notifications"
 *   description="Receive email updates about appointments"
 * />
 */

import { computed } from 'vue'

interface Props {
  /**
   * Current value of the toggle (true = on, false = off)
   */
  modelValue: boolean
  /**
   * Optional label for the toggle (for accessibility)
   */
  label?: string
  /**
   * Optional description (for accessibility)
   */
  description?: string
  /**
   * Disabled state
   */
  disabled?: boolean
  /**
   * Custom ID (generated if not provided)
   */
  id?: string
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

/**
 * Generate unique ID for toggle if not provided
 */
const toggleId = computed(
  () => props.id || `toggle-${Math.random().toString(36).slice(2, 9)}`
)

/**
 * Handle toggle click/keyboard interaction
 */
function handleToggle() {
  if (!props.disabled) {
    emit('update:modelValue', !props.modelValue)
  }
}

/**
 * Handle keyboard events (Space and Enter)
 */
function handleKeydown(event: KeyboardEvent) {
  if ((event.key === ' ' || event.key === 'Enter') && !props.disabled) {
    event.preventDefault()
    handleToggle()
  }
}
</script>

<template>
  <button
    :id="toggleId"
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :aria-label="label"
    :aria-describedby="description ? `${toggleId}-description` : undefined"
    :disabled="disabled"
    class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
    :class="{
      'bg-emerald-600': modelValue,
      'bg-slate-300': !modelValue,
      'cursor-not-allowed opacity-50': disabled,
    }"
    @click="handleToggle"
    @keydown="handleKeydown"
  >
    <!-- Screen reader only text -->
    <span v-if="label" class="sr-only">{{ label }}</span>

    <!-- Toggle thumb -->
    <span
      aria-hidden="true"
      class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
      :class="{
        'translate-x-5': modelValue,
        'translate-x-0': !modelValue,
      }"
    />
  </button>

  <!-- Hidden description for screen readers -->
  <span v-if="description" :id="`${toggleId}-description`" class="sr-only">
    {{ description }}
  </span>
</template>

<style scoped>
/**
 * Screen reader only utility class
 * Hides content visually but keeps it accessible to screen readers
 */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
