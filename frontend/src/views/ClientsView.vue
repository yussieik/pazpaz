<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import { useClientsStore } from '@/stores/clients'
import { useClientListKeyboard } from '@/composables/useClientListKeyboard'
import { useScreenReader } from '@/composables/useScreenReader'
import { useToast } from '@/composables/useToast'
import { useDeviceType } from '@/composables/useDeviceType'
import type { ClientListItem, ClientCreate } from '@/types/client'
import FloatingActionButton from '@/components/common/FloatingActionButton.vue'
import ClientFormModal from '@/components/clients/ClientFormModal.vue'

const { t } = useI18n()
const router = useRouter()
const clientsStore = useClientsStore()
const { showSuccess, showError } = useToast()
const { shouldDeferKeyboard } = useDeviceType()

// Local state for search
const searchQuery = ref('')
const searchInputRef = ref<HTMLInputElement>()

// Modal state
const showClientFormModal = ref(false)

// Filtered clients based on search
const filteredClients = computed(() => {
  if (!searchQuery.value) return clientsStore.clients

  const query = searchQuery.value.toLowerCase()
  return clientsStore.clients.filter((client) => {
    return (
      client.full_name.toLowerCase().includes(query) ||
      client.email?.toLowerCase().includes(query) ||
      client.phone?.includes(query)
    )
  })
})

// Navigate to client detail
function viewClient(client: ClientListItem) {
  // Store focused client ID in sessionStorage for restoration
  sessionStorage.setItem('lastFocusedClientId', client.id)
  router.push(`/clients/${client.id}`)
}

// Keyboard navigation
const { focusedIndex, setCardRef, restoreFocusToClient } = useClientListKeyboard(
  filteredClients,
  viewClient,
  searchInputRef
)

// Screen reader announcements
const { announcement } = useScreenReader()

// Navigate to new client form
function createNewClient() {
  showClientFormModal.value = true
}

// Handle client creation from modal
async function handleCreateClient(data: ClientCreate) {
  try {
    const newClient = await clientsStore.createClient(data)

    // Close modal immediately
    showClientFormModal.value = false

    // Navigate to client detail page
    router.push(`/clients/${newClient.id}`)

    // Show success toast
    showSuccess(t('clients.view.toasts.clientAdded', {
      firstName: newClient.first_name,
      lastName: newClient.last_name
    }))
  } catch (error) {
    // Keep modal open and show error
    console.error('Failed to create client:', error)
    showError(t('clients.view.toasts.addFailed'))
  }
}

// Keyboard shortcut handler for Cmd+N / Ctrl+N
function handleGlobalKeydown(event: KeyboardEvent) {
  // Cmd+N (Mac) or Ctrl+N (Windows/Linux) to create new client
  if ((event.metaKey || event.ctrlKey) && event.key === 'n') {
    event.preventDefault() // Prevent browser's default "New Window"
    createNewClient()
  }
}

onMounted(async () => {
  await clientsStore.fetchClients()

  // Add global keyboard shortcut listener
  document.addEventListener('keydown', handleGlobalKeydown)

  // Auto-focus search bar on desktop only (not on mobile)
  if (!shouldDeferKeyboard.value && searchInputRef.value) {
    await nextTick()
    searchInputRef.value.focus()
  }

  // Restore focus if returning from client detail view
  const lastFocusedClientId = sessionStorage.getItem('lastFocusedClientId')
  if (lastFocusedClientId) {
    // Only restore focus if we came from a client detail page
    // Check if the previous route was a client detail route
    const fromClientDetail = document.referrer.includes('/clients/')

    if (fromClientDetail) {
      await nextTick() // Ensure DOM is ready
      restoreFocusToClient(lastFocusedClientId)
    }

    // Clear the stored ID after attempting restoration
    sessionStorage.removeItem('lastFocusedClientId')
  }
})

onUnmounted(() => {
  // Clean up keyboard event listener to prevent memory leaks
  document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <div class="container mx-auto px-4 py-8 pb-20">
    <!-- Search + Metadata Toolbar (only shown when clients exist) -->
    <div
      v-if="
        !clientsStore.loading && !clientsStore.error && clientsStore.clients.length > 0
      "
      class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <!-- Search input (full width on mobile, grows on desktop) -->
      <div class="relative flex-1">
        <div
          class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3"
        >
          <svg
            class="h-5 w-5 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
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
          v-rtl
          type="search"
          :placeholder="
            shouldDeferKeyboard
              ? t('clients.view.searchPlaceholderMobile')
              : t('clients.view.searchPlaceholderDesktop')
          "
          :aria-label="shouldDeferKeyboard ? t('clients.view.searchAriaLabel') : undefined"
          class="block w-full rounded-lg border border-slate-300 bg-white py-3 pr-3 pl-10 text-sm text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
        />
      </div>

      <!-- Client count (subtle, right-aligned on desktop) -->
      <div class="text-sm text-slate-600" aria-live="polite" aria-atomic="true">
        {{ filteredClients.length === 1
          ? t('clients.view.clientCountSingular', { count: filteredClients.length })
          : t('clients.view.clientCountPlural', { count: filteredClients.length })
        }}
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="clientsStore.loading" class="flex items-center justify-center py-12">
      <div class="text-center">
        <div
          class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-emerald-600 border-r-transparent"
        ></div>
        <p class="mt-4 text-sm text-slate-600">{{ t('clients.view.loadingMessage') }}</p>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="clientsStore.error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">{{ t('clients.view.errorTitle') }}</p>
      <p class="mt-1 text-sm">{{ clientsStore.error }}</p>
    </div>

    <!-- Empty State (No Clients) -->
    <div
      v-else-if="clientsStore.clients.length === 0"
      class="mx-auto max-w-2xl py-12 text-center"
    >
      <div class="mb-4 flex justify-center">
        <svg
          class="h-16 w-16 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
          />
        </svg>
      </div>
      <h2 class="mb-3 text-xl font-semibold text-slate-900">{{ t('clients.view.emptyState.title') }}</h2>
      <p class="mb-6 text-slate-600">
        {{ t('clients.view.emptyState.description') }}
      </p>
      <button
        @click="createNewClient"
        class="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 4v16m8-8H4"
          />
        </svg>
        <span>{{ t('clients.view.emptyState.button') }}</span>
      </button>
    </div>

    <!-- Empty Search Results -->
    <div
      v-else-if="filteredClients.length === 0"
      class="mx-auto max-w-2xl py-12 text-center"
    >
      <p class="text-slate-600">{{ t('clients.view.emptySearch.message') }}</p>
      <button
        @click="searchQuery = ''"
        class="mt-4 text-sm font-medium text-emerald-600 hover:text-emerald-700"
      >
        {{ t('clients.view.emptySearch.clearButton') }}
      </button>
    </div>

    <!-- Client List -->
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <button
        v-for="(client, index) in filteredClients"
        :key="client.id"
        :ref="(el) => setCardRef(el as HTMLElement, index)"
        :data-client-id="client.id"
        @click="viewClient(client)"
        :class="[
          'group block rounded-lg border bg-white p-4 text-left transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
          focusedIndex === index
            ? 'scale-[1.02] border-emerald-500 bg-emerald-50 shadow-md ring-2 ring-emerald-500/20'
            : 'border-slate-200',
        ]"
      >
        <!-- Client Avatar -->
        <div class="mb-3 flex items-center gap-3">
          <div
            class="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-lg font-semibold text-emerald-700"
          >
            {{ client.first_name[0] }}{{ client.last_name[0] }}
          </div>
          <div class="min-w-0 flex-1">
            <h3
              class="truncate font-semibold text-slate-900 group-hover:text-emerald-600"
            >
              {{ client.full_name }}
            </h3>
            <p v-if="client.email" class="truncate text-sm text-slate-500">
              {{ client.email }}
            </p>
          </div>
        </div>

        <!-- Client Metadata -->
        <div class="space-y-1 text-sm text-slate-600">
          <p v-if="client.phone">
            <span class="font-medium">{{ t('clients.view.clientCard.phoneLabel') }}</span> {{ client.phone }}
          </p>
          <p v-if="client.next_appointment">
            <span class="font-medium">{{ t('clients.view.clientCard.nextLabel') }}</span>
            {{ new Date(client.next_appointment).toLocaleDateString() }}
          </p>
          <p v-else-if="client.last_appointment">
            <span class="font-medium">{{ t('clients.view.clientCard.lastLabel') }}</span>
            {{ new Date(client.last_appointment).toLocaleDateString() }}
          </p>
          <p v-if="client.appointment_count !== undefined">
            <span class="font-medium">{{ t('clients.view.clientCard.appointmentsLabel') }}</span>
            {{ client.appointment_count }}
          </p>
        </div>
      </button>
    </div>

    <!-- Floating Action Button -->
    <FloatingActionButton
      :label="t('clients.view.floatingButton.label')"
      :title="t('clients.view.floatingButton.title')"
      @click="createNewClient"
    />

    <!-- Client Form Modal -->
    <ClientFormModal
      :visible="showClientFormModal"
      mode="create"
      @update:visible="showClientFormModal = $event"
      @submit="handleCreateClient"
    />

    <!-- Screen Reader Announcements -->
    <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
      {{ announcement }}
    </div>
  </div>
</template>

<style scoped>
/* Screen reader only class */
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

/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .transition-all {
    transition: none !important;
  }
}
</style>
