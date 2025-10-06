<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { KEYBOARD_SHORTCUTS, type ShortcutConfig } from '@/config/keyboardShortcuts'
import { useShortcutSearch } from '@/composables/useShortcutSearch'

interface Props {
  visible: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Search functionality
const {
  searchQuery,
  filteredShortcuts,
  filteredCount,
  totalCount,
  isSearching,
  clearSearch,
} = useShortcutSearch(KEYBOARD_SHORTCUTS)

// Search input ref for autofocus
const searchInputRef = ref<HTMLInputElement | null>(null)

// Group filtered shortcuts by category for two-column layout
const groupedShortcuts = computed(() => {
  const groups: Record<string, ShortcutConfig[]> = {
    navigation: [],
    calendar: [],
    'clients-list': [],
    client: [],
  }

  filteredShortcuts.value.forEach((shortcut) => {
    const categoryGroup = groups[shortcut.category]
    if (categoryGroup) {
      categoryGroup.push(shortcut)
    }
  })

  return groups
})

// Category display names
const categoryNames: Record<string, string> = {
  navigation: 'Navigation',
  calendar: 'Calendar',
  'clients-list': 'Clients List',
  client: 'Client Detail',
}

// Organize categories into two columns for balanced layout
const leftColumnCategories = computed(() => ['navigation', 'clients-list'])
const rightColumnCategories = computed(() => ['calendar', 'client'])

function closeModal() {
  clearSearch()
  emit('update:visible', false)
}

// Handle Escape key: clear search first, then close modal
function handleEscapeKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    e.preventDefault()
    if (isSearching.value) {
      clearSearch()
      // Keep focus on search input after clearing
      nextTick(() => {
        searchInputRef.value?.focus()
      })
    } else {
      closeModal()
    }
  }
}

// Autofocus search input when modal opens
watch(
  () => props.visible,
  (newVisible) => {
    if (newVisible) {
      nextTick(() => {
        searchInputRef.value?.focus()
      })
    }
  }
)

onMounted(() => {
  window.addEventListener('keydown', handleEscapeKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleEscapeKey)
})
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out"
      leave-active-class="transition-opacity duration-150 ease-in"
      enter-from-class="opacity-0"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible"
        class="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm"
        @click="closeModal"
        aria-hidden="true"
      ></div>
    </Transition>

    <!-- Modal Content -->
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-modal-title"
        aria-describedby="shortcuts-results-count"
      >
        <div
          class="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl bg-white shadow-xl"
          @click.stop
        >
          <!-- Header -->
          <div
            class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4"
          >
            <h2 id="shortcuts-modal-title" class="text-xl font-semibold text-slate-900">
              Keyboard Shortcuts
            </h2>
            <button
              @click="closeModal"
              class="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              aria-label="Close dialog"
            >
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          <!-- Search Input -->
          <div class="border-b border-slate-200 bg-white px-6 py-4">
            <div class="relative">
              <div
                class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3"
              >
                <svg
                  class="h-5 w-5 text-slate-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </div>
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                class="block w-full rounded-lg border border-slate-300 bg-white py-2.5 pr-10 pl-10 text-slate-900 placeholder-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none"
                placeholder="Search shortcuts..."
                aria-label="Search keyboard shortcuts"
              />
              <button
                v-if="isSearching"
                @click="clearSearch"
                class="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600"
                aria-label="Clear search"
              >
                <svg
                  class="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            <!-- Results count (for screen readers) -->
            <p
              id="shortcuts-results-count"
              class="sr-only"
              aria-live="polite"
              aria-atomic="true"
            >
              {{
                isSearching
                  ? `Showing ${filteredCount} of ${totalCount} shortcuts`
                  : `Showing all ${totalCount} shortcuts`
              }}
            </p>
          </div>

          <!-- Body with Two-Column Grid -->
          <div class="px-6 py-6">
            <!-- No results message -->
            <div v-if="filteredCount === 0" class="py-12 text-center text-slate-500">
              <svg
                class="mx-auto h-12 w-12 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <p class="mt-4 text-lg font-medium">No shortcuts found</p>
              <p class="mt-1 text-sm">Try a different search term</p>
            </div>

            <!-- Two-column grid layout -->
            <div v-else class="grid grid-cols-1 gap-x-8 gap-y-6 md:grid-cols-2">
              <!-- Left Column -->
              <div class="space-y-6">
                <div
                  v-for="category in leftColumnCategories"
                  :key="category"
                  v-show="
                    groupedShortcuts[category] && groupedShortcuts[category].length > 0
                  "
                >
                  <h3
                    class="mb-3 border-b border-slate-200 pb-2 text-sm font-semibold tracking-wide text-slate-500 uppercase"
                  >
                    {{ categoryNames[category] }}
                  </h3>
                  <div class="space-y-3">
                    <div
                      v-for="shortcut in groupedShortcuts[category]"
                      :key="shortcut.keys + shortcut.description"
                      class="flex items-start justify-between gap-4"
                    >
                      <span class="flex-1 text-slate-700">{{
                        shortcut.description
                      }}</span>
                      <kbd
                        class="flex-shrink-0 rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                      >
                        {{ shortcut.keys }}
                      </kbd>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Right Column -->
              <div class="space-y-6">
                <div
                  v-for="category in rightColumnCategories"
                  :key="category"
                  v-show="
                    groupedShortcuts[category] && groupedShortcuts[category].length > 0
                  "
                >
                  <h3
                    class="mb-3 border-b border-slate-200 pb-2 text-sm font-semibold tracking-wide text-slate-500 uppercase"
                  >
                    {{ categoryNames[category] }}
                  </h3>
                  <div class="space-y-3">
                    <div
                      v-for="shortcut in groupedShortcuts[category]"
                      :key="shortcut.keys + shortcut.description"
                      class="flex items-start justify-between gap-4"
                    >
                      <span class="flex-1 text-slate-700">{{
                        shortcut.description
                      }}</span>
                      <kbd
                        class="flex-shrink-0 rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                      >
                        {{ shortcut.keys }}
                      </kbd>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div
            class="border-t border-slate-200 bg-slate-50 px-6 py-4 text-center text-sm text-slate-600"
          >
            Press
            <kbd class="rounded bg-white px-2 py-1 text-sm font-medium text-slate-900"
              >Esc</kbd
            >
            to {{ isSearching ? 'clear search or close' : 'close' }}
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
