<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { useClientSearch } from '@/composables/useClientSearch'
import { useScreenReader } from '@/composables/useScreenReader'
import { useDeviceType } from '@/composables/useDeviceType'
import ClientDropdownItem from './ClientDropdownItem.vue'
import ClientQuickAddForm from './ClientQuickAddForm.vue'
import type { Client, ClientListItem, ClientCreate } from '@/types/client'

interface Props {
  modelValue: string // client_id
  error?: string
  disabled?: boolean
  helpText?: string
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  error: '',
  disabled: false,
  helpText: undefined,
})

const emit = defineEmits<Emits>()

// Composables
const {
  searchResults,
  recentClients,
  isSearching,
  isLoadingRecent,
  isCreating,
  error: searchError,
  searchClients,
  fetchRecentClients,
  createClient,
  clearSearch,
} = useClientSearch()
const { announce } = useScreenReader()
const { shouldDeferKeyboard } = useDeviceType()

// Component state
const isOpen = ref(false)
const searchQuery = ref('')
const highlightedIndex = ref(-1)
const showQuickAddForm = ref(false)
const selectedClient = ref<Client | null>(null)

// Refs
const comboboxRef = ref<HTMLElement>()
const inputRef = ref<HTMLInputElement>()
const dropdownRef = ref<HTMLElement>()
const quickAddFormRef = ref<InstanceType<typeof ClientQuickAddForm>>()

// Close dropdown when clicking outside
onClickOutside(comboboxRef, () => {
  isOpen.value = false
  showQuickAddForm.value = false
})

// Generate unique IDs for ARIA
const comboboxId = `client-combobox-${Math.random().toString(36).substr(2, 9)}`
const listboxId = `${comboboxId}-listbox`

/**
 * Combined list of clients to display
 * Shows recent clients first, then search results
 */
const displayedClients = computed(() => {
  if (searchQuery.value.trim()) {
    return searchResults.value
  }
  return recentClients.value
})

/**
 * Check if there are any clients to display
 */
const hasClients = computed(() => displayedClients.value.length > 0)

// Removed unused displayValue computed property
// The input field uses searchQuery.value or selectedClient.value.full_name directly in placeholder

/**
 * Load recent clients on mount
 */
onMounted(() => {
  fetchRecentClients()

  // If modelValue is provided, fetch the client to display
  if (props.modelValue) {
    // TODO: Fetch client by ID to populate selectedClient
    // For now, we'll just use the ID
  }
})

/**
 * Watch for search query changes
 */
watch(searchQuery, (newQuery) => {
  if (newQuery.trim()) {
    searchClients(newQuery)
  } else {
    clearSearch()
  }
  highlightedIndex.value = -1
})

/**
 * Open dropdown
 */
function openDropdown() {
  if (props.disabled) return
  isOpen.value = true
  showQuickAddForm.value = false
  highlightedIndex.value = -1
}

/**
 * Close dropdown
 */
function closeDropdown() {
  isOpen.value = false
  showQuickAddForm.value = false
  highlightedIndex.value = -1
}

/**
 * Handle input focus
 */
function handleInputFocus() {
  openDropdown()
}

/**
 * Handle input click
 */
function handleInputClick() {
  openDropdown()
}

/**
 * Select a client
 */
function selectClient(client: Client) {
  selectedClient.value = client
  searchQuery.value = ''
  emit('update:modelValue', client.id)
  closeDropdown()
  announce(`Client selected: ${client.full_name}`)
}

/**
 * Clear selection
 */
function clearSelection() {
  selectedClient.value = null
  searchQuery.value = ''
  emit('update:modelValue', '')
  inputRef.value?.focus()
  announce('Client selection cleared')
}

/**
 * Show the quick add form
 */
function showAddNewClient() {
  showQuickAddForm.value = true
  nextTick(() => {
    quickAddFormRef.value?.focus()
  })
}

/**
 * Handle quick add form submission
 */
async function handleQuickAddSubmit(clientData: ClientCreate) {
  const newClient = await createClient(clientData)
  if (newClient) {
    selectClient(newClient)
    announce(`Client ${newClient.full_name} created and selected`)
  }
}

/**
 * Handle quick add form cancellation
 */
function handleQuickAddCancel() {
  showQuickAddForm.value = false
  inputRef.value?.focus()
}

/**
 * Keyboard navigation
 */
function handleKeydown(e: KeyboardEvent) {
  if (!isOpen.value && e.key !== 'Escape') {
    openDropdown()
    return
  }

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      if (showQuickAddForm.value) break
      if (highlightedIndex.value < displayedClients.value.length - 1) {
        highlightedIndex.value++
        scrollToHighlighted()
      } else if (highlightedIndex.value === displayedClients.value.length - 1) {
        // Move to "Add New Client" option
        highlightedIndex.value = displayedClients.value.length
      }
      break

    case 'ArrowUp':
      e.preventDefault()
      if (showQuickAddForm.value) break
      if (highlightedIndex.value > 0) {
        highlightedIndex.value--
        scrollToHighlighted()
      }
      break

    case 'Enter':
      e.preventDefault()
      if (showQuickAddForm.value) break
      if (
        highlightedIndex.value >= 0 &&
        highlightedIndex.value < displayedClients.value.length
      ) {
        const selectedItem = displayedClients.value[highlightedIndex.value]
        if (selectedItem) {
          selectClient(selectedItem)
        }
      } else if (highlightedIndex.value === displayedClients.value.length) {
        showAddNewClient()
      }
      break

    case 'Escape':
      e.preventDefault()
      if (showQuickAddForm.value) {
        handleQuickAddCancel()
      } else {
        closeDropdown()
      }
      break

    case 'Tab':
      closeDropdown()
      break
  }
}

/**
 * Scroll to the highlighted item in the dropdown
 */
function scrollToHighlighted() {
  if (!dropdownRef.value) return
  const highlightedElement = dropdownRef.value.querySelector(
    `[data-index="${highlightedIndex.value}"]`
  )
  if (highlightedElement) {
    highlightedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }
}

/**
 * Check if a client is in the recent list
 */
function isRecentClient(client: Client | undefined): boolean {
  if (!client) return false
  return recentClients.value.some((rc) => rc.id === client.id)
}

/**
 * Get last visit date for a client
 */
function getLastVisitDate(client: Client): string | null {
  return (client as ClientListItem).last_appointment || null
}

// Expose inputRef so parent components can focus the input
defineExpose({
  inputRef,
})
</script>

<template>
  <div ref="comboboxRef" class="relative">
    <!-- Label (if needed, can be passed via slot) -->
    <div class="flex items-center justify-between">
      <label :for="comboboxId" class="mb-1.5 block text-sm font-medium text-slate-900">
        Client <span class="ml-0.5 text-red-500">*</span>
      </label>
      <button
        v-if="selectedClient"
        @click="clearSelection"
        type="button"
        class="flex min-h-[44px] items-center text-xs text-slate-500 hover:text-slate-700 focus:outline-none focus-visible:underline sm:min-h-0"
        aria-label="Clear client selection"
      >
        Clear
      </button>
    </div>

    <!-- Input Field -->
    <div class="relative mt-1">
      <input
        :id="comboboxId"
        ref="inputRef"
        v-model="searchQuery"
        v-rtl
        type="text"
        role="combobox"
        :aria-expanded="isOpen"
        :aria-controls="listboxId"
        :aria-activedescendant="
          highlightedIndex >= 0 ? `${comboboxId}-option-${highlightedIndex}` : undefined
        "
        aria-autocomplete="list"
        :placeholder="
          selectedClient ? selectedClient.full_name : 'Search for a client...'
        "
        :disabled="disabled"
        @focus="handleInputFocus"
        @click="handleInputClick"
        @keydown="handleKeydown"
        :class="[
          'block min-h-[44px] w-full rounded-lg border px-3 py-2 pr-10 text-base transition-colors sm:text-sm',
          'focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none',
          error ? 'border-red-500' : 'border-slate-300',
          disabled
            ? 'cursor-not-allowed border-slate-200 bg-slate-50 text-slate-500'
            : 'text-slate-900 placeholder-slate-400',
          selectedClient && 'font-medium',
          shouldDeferKeyboard && 'cursor-pointer',
        ]"
      />

      <!-- Dropdown Icon -->
      <div
        class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3"
      >
        <svg
          :class="[
            'h-5 w-5 transition-transform',
            isOpen ? 'rotate-180 text-emerald-600' : 'text-slate-400',
          ]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </div>
    </div>

    <!-- Help Text -->
    <p v-if="helpText" class="mt-1 text-xs text-slate-500">{{ helpText }}</p>

    <!-- Error Message -->
    <p v-if="error" class="mt-1 text-sm text-red-600" role="alert">
      {{ error }}
    </p>

    <!-- Dropdown List -->
    <Transition
      enter-active-class="transition-opacity duration-100 ease-out"
      leave-active-class="transition-opacity duration-75 ease-in"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        :id="listboxId"
        ref="dropdownRef"
        role="listbox"
        :aria-labelledby="comboboxId"
        class="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg"
        :class="{ 'max-h-80 overflow-y-auto': !showQuickAddForm }"
      >
        <!-- Loading State -->
        <div
          v-if="isLoadingRecent || isSearching"
          class="flex items-center justify-center gap-2 px-4 py-8 text-sm text-slate-500"
        >
          <svg
            class="h-4 w-4 animate-spin text-slate-400"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            ></circle>
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          <span>{{ isSearching ? 'Searching...' : 'Loading...' }}</span>
        </div>

        <!-- Error State -->
        <div
          v-else-if="searchError"
          class="px-4 py-8 text-center text-sm text-red-600"
          role="alert"
        >
          {{ searchError }}
        </div>

        <!-- Client List -->
        <div v-else-if="!showQuickAddForm">
          <!-- Recent/Search Results -->
          <div v-if="hasClients">
            <!-- Section Header (only for recent clients) -->
            <div
              v-if="!searchQuery.trim() && recentClients.length > 0"
              class="border-b border-slate-200 bg-slate-50 px-4 py-2"
            >
              <h3 class="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Recent Clients
              </h3>
            </div>

            <!-- Client Items -->
            <button
              v-for="(client, index) in displayedClients"
              :key="client.id"
              :id="`${comboboxId}-option-${index}`"
              :data-index="index"
              type="button"
              @click="selectClient(client)"
              @mouseenter="highlightedIndex = index"
              class="w-full text-left focus:outline-none focus-visible:bg-emerald-50"
            >
              <ClientDropdownItem
                :client="client"
                :is-recent="isRecentClient(client) && !searchQuery.trim()"
                :last-visit-date="getLastVisitDate(client)"
                :is-selected="selectedClient?.id === client.id"
                :is-highlighted="highlightedIndex === index"
              />
            </button>
          </div>

          <!-- No Results -->
          <div
            v-else-if="searchQuery.trim()"
            class="px-4 py-6 text-center text-sm text-slate-500"
          >
            No clients found for "{{ searchQuery }}"
          </div>

          <!-- Add New Client Option -->
          <div class="border-t border-slate-200">
            <button
              :id="`${comboboxId}-option-${displayedClients.length}`"
              :data-index="displayedClients.length"
              type="button"
              @click="showAddNewClient"
              @mouseenter="highlightedIndex = displayedClients.length"
              :class="[
                'flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-medium transition-colors',
                'focus:outline-none focus-visible:bg-emerald-50',
                highlightedIndex === displayedClients.length
                  ? 'bg-emerald-50 text-emerald-700'
                  : 'text-emerald-600 hover:bg-emerald-50',
              ]"
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
                  d="M12 4v16m8-8H4"
                />
              </svg>
              <span>Add New Client</span>
            </button>
          </div>
        </div>

        <!-- Quick Add Form -->
        <ClientQuickAddForm
          v-if="showQuickAddForm"
          ref="quickAddFormRef"
          @submit="handleQuickAddSubmit"
          @cancel="handleQuickAddCancel"
        />

        <!-- Creating Indicator -->
        <div
          v-if="isCreating"
          class="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm"
        >
          <div class="flex items-center gap-2 text-sm text-slate-600">
            <svg
              class="h-5 w-5 animate-spin text-emerald-600"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            <span>Creating client...</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Mobile Full-Screen Overlay (TODO: Implement for mobile) -->
    <!-- <Teleport to="body">
      <div v-if="isOpen && isMobile" class="fixed inset-0 z-50 bg-white">
        Mobile full-screen picker
      </div>
    </Teleport> -->
  </div>
</template>
