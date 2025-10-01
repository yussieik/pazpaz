<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { ClientListItem } from '@/types/client'

const router = useRouter()

// State
const clients = ref<ClientListItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const searchQuery = ref('')

// Filtered clients based on search
const filteredClients = computed(() => {
  if (!searchQuery.value) return clients.value

  const query = searchQuery.value.toLowerCase()
  return clients.value.filter((client) => {
    return (
      client.full_name.toLowerCase().includes(query) ||
      client.email?.toLowerCase().includes(query) ||
      client.phone?.includes(query)
    )
  })
})

// Fetch clients (TODO: Replace with API call)
async function fetchClients() {
  loading.value = true
  error.value = null

  try {
    // TODO (M3): Call API
    // const response = await apiClient.get('/api/v1/clients')
    // clients.value = response.data.items

    // Placeholder: Empty list for now
    clients.value = []
  } catch (err) {
    error.value = 'Failed to load clients'
    console.error('Error fetching clients:', err)
  } finally {
    loading.value = false
  }
}

// Navigate to client detail
function viewClient(clientId: string) {
  router.push(`/clients/${clientId}`)
}

// Navigate to new client form
function createNewClient() {
  // TODO (M3): Open create client modal
  console.log('Create new client')
}

onMounted(() => {
  fetchClients()
})
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <header
      class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <h1 class="text-2xl font-semibold text-slate-900">Clients</h1>
        <p v-if="!loading && clients.length > 0" class="mt-1.5 text-sm text-slate-600">
          {{ filteredClients.length }} client{{
            filteredClients.length === 1 ? '' : 's'
          }}
        </p>
      </div>

      <button
        @click="createNewClient"
        class="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 4v16m8-8H4"
          />
        </svg>
        <span>New Client</span>
      </button>
    </header>

    <!-- Search Bar -->
    <div v-if="!loading && !error" class="mb-6">
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
          v-model="searchQuery"
          type="search"
          placeholder="Search clients by name, email, or phone..."
          autofocus
          class="block w-full rounded-lg border border-slate-300 bg-white py-3 pr-3 pl-10 text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
        />
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="text-center">
        <div
          class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-emerald-600 border-r-transparent"
        ></div>
        <p class="mt-4 text-sm text-slate-600">Loading clients...</p>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">Error loading clients</p>
      <p class="mt-1 text-sm">{{ error }}</p>
    </div>

    <!-- Empty State (No Clients) -->
    <div v-else-if="clients.length === 0" class="mx-auto max-w-2xl py-12 text-center">
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
      <h2 class="mb-3 text-xl font-semibold text-slate-900">No clients yet</h2>
      <p class="mb-6 text-slate-600">
        Get started by adding your first client to begin managing their treatment
        journey.
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
        <span>Add First Client</span>
      </button>
    </div>

    <!-- Empty Search Results -->
    <div
      v-else-if="filteredClients.length === 0"
      class="mx-auto max-w-2xl py-12 text-center"
    >
      <p class="text-slate-600">No clients match your search.</p>
      <button
        @click="searchQuery = ''"
        class="mt-4 text-sm font-medium text-emerald-600 hover:text-emerald-700"
      >
        Clear search
      </button>
    </div>

    <!-- Client List -->
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <button
        v-for="client in filteredClients"
        :key="client.id"
        @click="viewClient(client.id)"
        class="group block rounded-lg border border-slate-200 bg-white p-4 text-left transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
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
            <span class="font-medium">Phone:</span> {{ client.phone }}
          </p>
          <p v-if="client.next_appointment">
            <span class="font-medium">Next:</span>
            {{ new Date(client.next_appointment).toLocaleDateString() }}
          </p>
          <p v-else-if="client.last_appointment">
            <span class="font-medium">Last:</span>
            {{ new Date(client.last_appointment).toLocaleDateString() }}
          </p>
          <p v-if="client.appointment_count !== undefined">
            <span class="font-medium">Sessions:</span> {{ client.appointment_count }}
          </p>
        </div>
      </button>
    </div>
  </div>
</template>
