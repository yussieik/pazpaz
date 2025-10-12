<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

interface Props {
  modelValue: string // ISO 8601 datetime string or datetime-local format
  label: string
  error?: string
  minTime?: string // e.g., "06:00"
  maxTime?: string // e.g., "22:00"
  interval?: number // minutes (default: 15)
  disabled?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  minTime: '06:00',
  maxTime: '22:00',
  interval: 15,
  disabled: false,
})

const emit = defineEmits<Emits>()

// Component state
const isOpen = ref(false)
const dropdownRef = ref<HTMLElement>()
const triggerRef = ref<HTMLButtonElement>()
const highlightedIndex = ref(-1)

/**
 * Parse datetime string to extract time portion
 */
function extractTime(datetimeString: string): string {
  if (!datetimeString) return ''

  try {
    const date = new Date(datetimeString)
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${hours}:${minutes}`
  } catch {
    return ''
  }
}

/**
 * Format time as 12-hour with AM/PM
 */
function formatTime12Hour(hours: number, mins: number): string {
  const period = hours >= 12 ? 'PM' : 'AM'
  const displayHours = hours % 12 || 12
  const displayMins = String(mins).padStart(2, '0')
  return `${displayHours}:${displayMins} ${period}`
}

/**
 * Generate time options based on interval
 */
const timeOptions = computed(() => {
  const options: Array<{ value: string; label: string }> = []
  const [minHours, minMins] = props.minTime.split(':').map(Number)
  const [maxHours, maxMins] = props.maxTime.split(':').map(Number)

  const startMinutes = minHours * 60 + minMins
  const endMinutes = maxHours * 60 + maxMins
  const interval = props.interval

  for (
    let totalMinutes = startMinutes;
    totalMinutes <= endMinutes;
    totalMinutes += interval
  ) {
    const hours = Math.floor(totalMinutes / 60)
    const mins = totalMinutes % 60

    const value = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`
    const label = formatTime12Hour(hours, mins)

    options.push({ value, label })
  }

  return options
})

/**
 * Get current selected time
 */
const selectedTime = computed(() => {
  return extractTime(props.modelValue)
})

/**
 * Get display label for selected time
 */
const selectedLabel = computed(() => {
  const time = selectedTime.value
  if (!time) return 'Select time'

  const [hours, mins] = time.split(':').map(Number)
  return formatTime12Hour(hours, mins)
})

/**
 * Round time to nearest interval
 */
function roundTimeToInterval(timeStr: string): string {
  if (!timeStr) return ''

  const [hours, mins] = timeStr.split(':').map(Number)
  const totalMinutes = hours * 60 + mins

  // Round to nearest interval
  const roundedMinutes = Math.round(totalMinutes / props.interval) * props.interval

  const roundedHours = Math.floor(roundedMinutes / 60)
  const roundedMins = roundedMinutes % 60

  return `${String(roundedHours).padStart(2, '0')}:${String(roundedMins).padStart(2, '0')}`
}

/**
 * Get current selected index
 */
const selectedIndex = computed(() => {
  const time = selectedTime.value
  if (!time) return -1

  // Round to nearest interval to find matching option in dropdown
  const roundedTime = roundTimeToInterval(time)

  return timeOptions.value.findIndex((opt) => opt.value === roundedTime)
})

/**
 * Update highlighted index when dropdown opens
 */
watch(isOpen, async (open) => {
  if (open) {
    highlightedIndex.value = selectedIndex.value >= 0 ? selectedIndex.value : 0
    // Wait for DOM to update and transition to complete
    await nextTick()
    // Additional delay for transition animation
    setTimeout(() => {
      scrollToHighlighted()
    }, 120)
  }
})

/**
 * Scroll highlighted option into view
 * Centers the selected time with context around it
 */
function scrollToHighlighted() {
  if (!dropdownRef.value || highlightedIndex.value < 0) return

  const items = dropdownRef.value.querySelectorAll('[role="option"]')
  const highlighted = items[highlightedIndex.value] as HTMLElement

  if (!highlighted) return

  const dropdownHeight = dropdownRef.value.clientHeight
  const itemHeight = highlighted.offsetHeight

  // Calculate position based on index (more reliable than offsetTop)
  const itemPositionFromTop = highlightedIndex.value * itemHeight

  // Calculate scroll position to center the item
  const scrollTop = itemPositionFromTop - dropdownHeight / 2 + itemHeight / 2

  dropdownRef.value.scrollTop = scrollTop
}

/**
 * Toggle dropdown open/close
 */
function toggleDropdown() {
  if (props.disabled) return
  isOpen.value = !isOpen.value
}

/**
 * Select a time option
 */
function selectTime(timeValue: string) {
  if (props.disabled) return

  // Parse the current modelValue to get date portion
  const currentDate = new Date(props.modelValue)

  // If invalid date, use today
  const date = isNaN(currentDate.getTime()) ? new Date() : currentDate

  // Set the time
  const [hours, mins] = timeValue.split(':').map(Number)
  date.setHours(hours, mins, 0, 0)

  // Format as datetime-local format (YYYY-MM-DDTHH:mm)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const formattedTime = `${year}-${month}-${day}T${timeValue}`

  emit('update:modelValue', formattedTime)
  isOpen.value = false
}

/**
 * Handle keyboard navigation
 */
function handleKeyDown(event: KeyboardEvent) {
  if (props.disabled) return

  if (!isOpen.value) {
    // Open dropdown on Enter or Space
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      isOpen.value = true
    }
    return
  }

  switch (event.key) {
    case 'Escape':
      event.preventDefault()
      isOpen.value = false
      triggerRef.value?.focus()
      break

    case 'ArrowDown':
      event.preventDefault()
      highlightedIndex.value = Math.min(
        highlightedIndex.value + 1,
        timeOptions.value.length - 1
      )
      scrollToHighlighted()
      break

    case 'ArrowUp':
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
      scrollToHighlighted()
      break

    case 'PageDown': {
      event.preventDefault()
      // Jump 1 hour (60 min / interval)
      const pageDownSteps = Math.floor(60 / props.interval)
      highlightedIndex.value = Math.min(
        highlightedIndex.value + pageDownSteps,
        timeOptions.value.length - 1
      )
      scrollToHighlighted()
      break
    }

    case 'PageUp': {
      event.preventDefault()
      // Jump 1 hour (60 min / interval)
      const pageUpSteps = Math.floor(60 / props.interval)
      highlightedIndex.value = Math.max(highlightedIndex.value - pageUpSteps, 0)
      scrollToHighlighted()
      break
    }

    case 'Home':
      event.preventDefault()
      highlightedIndex.value = 0
      scrollToHighlighted()
      break

    case 'End':
      event.preventDefault()
      highlightedIndex.value = timeOptions.value.length - 1
      scrollToHighlighted()
      break

    case 'Enter':
    case ' ':
      event.preventDefault()
      if (highlightedIndex.value >= 0) {
        selectTime(timeOptions.value[highlightedIndex.value].value)
      }
      break

    default:
      // Type-ahead search (e.g., "2p" jumps to "2:00 PM")
      handleTypeAhead(event.key)
      break
  }
}

/**
 * Type-ahead buffer for quick navigation
 */
const typeAheadBuffer = ref('')
let typeAheadTimeout: number | null = null

function handleTypeAhead(key: string) {
  if (key.length !== 1) return

  // Add to buffer
  typeAheadBuffer.value += key.toLowerCase()

  // Clear timeout and set new one
  if (typeAheadTimeout !== null) {
    clearTimeout(typeAheadTimeout)
  }

  typeAheadTimeout = window.setTimeout(() => {
    typeAheadBuffer.value = ''
  }, 1000)

  // Find matching option
  const matchIndex = timeOptions.value.findIndex((opt) =>
    opt.label.toLowerCase().startsWith(typeAheadBuffer.value)
  )

  if (matchIndex >= 0) {
    highlightedIndex.value = matchIndex
    scrollToHighlighted()
  }
}

/**
 * Close dropdown when clicking outside
 */
function handleClickOutside(event: MouseEvent) {
  if (!isOpen.value) return

  const target = event.target as Node
  if (
    dropdownRef.value &&
    !dropdownRef.value.contains(target) &&
    triggerRef.value &&
    !triggerRef.value.contains(target)
  ) {
    isOpen.value = false
  }
}

// Lifecycle hooks
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (typeAheadTimeout !== null) {
    clearTimeout(typeAheadTimeout)
  }
})
</script>

<template>
  <div class="relative">
    <!-- Label -->
    <label v-if="label" class="mb-1 block text-sm font-medium text-slate-700">
      {{ label }}
    </label>

    <!-- Trigger Button -->
    <button
      ref="triggerRef"
      type="button"
      @click="toggleDropdown"
      @keydown="handleKeyDown"
      :disabled="disabled"
      :aria-label="label"
      :aria-expanded="isOpen"
      :aria-haspopup="true"
      :class="[
        'flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition-all',
        error
          ? 'border-red-500 focus:ring-red-500'
          : isOpen
            ? 'border-emerald-500 ring-2 ring-emerald-500'
            : 'border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500',
        disabled
          ? 'cursor-not-allowed bg-slate-100 text-slate-400'
          : 'bg-white text-slate-900',
      ]"
      class="focus:outline-none"
    >
      <span>{{ selectedLabel }}</span>
      <svg
        class="h-4 w-4 text-slate-400 transition-transform"
        :class="{ 'rotate-180': isOpen }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </button>

    <!-- Error Message -->
    <p v-if="error" class="mt-1 text-sm text-red-600">
      {{ error }}
    </p>

    <!-- Dropdown List -->
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
        ref="dropdownRef"
        class="absolute z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg"
        role="listbox"
        :aria-label="`${label} options`"
      >
        <button
          v-for="(option, index) in timeOptions"
          :key="option.value"
          type="button"
          @click="selectTime(option.value)"
          @mouseenter="highlightedIndex = index"
          :data-highlighted="highlightedIndex === index"
          :aria-selected="option.value === selectedTime"
          role="option"
          :class="[
            'w-full px-3 py-2 text-left text-sm transition-colors',
            highlightedIndex === index
              ? 'bg-slate-100'
              : option.value === selectedTime
                ? 'bg-emerald-50 font-medium text-emerald-900'
                : 'text-slate-700 hover:bg-slate-50',
          ]"
        >
          {{ option.label }}
        </button>
      </div>
    </Transition>
  </div>
</template>
