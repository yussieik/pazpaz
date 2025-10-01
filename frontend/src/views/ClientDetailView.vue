<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Client } from '@/types/client'

const route = useRoute()
const router = useRouter()

// State
const client = ref<Client | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const activeTab = ref<'overview' | 'history' | 'plan-of-care' | 'files'>('overview')

const clientId = computed(() => route.params.id as string)

// Fetch client data
async function fetchClient() {
  loading.value = true
  error.value = null

  try {
    // TODO (M3): Call API
    // const response = await apiClient.get(`/api/v1/clients/${clientId.value}`)
    // client.value = response.data

    // Placeholder
    throw new Error('Client API not yet implemented')
  } catch (err) {
    error.value = 'Failed to load client'
    console.error('Error fetching client:', err)
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/clients')
}

function editClient() {
  // TODO (M3): Open edit client modal
  console.log('Edit client:', clientId.value)
}

function scheduleAppointment() {
  // TODO (M3): Open appointment modal with client pre-selected
  router.push('/')
}

onMounted(() => {
  fetchClient()
})
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Back Button -->
    <button
      @click="goBack"
      class="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15 19l-7-7 7-7"
        />
      </svg>
      <span>Back to Clients</span>
    </button>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="text-center">
        <div
          class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-emerald-600 border-r-transparent"
        ></div>
        <p class="mt-4 text-sm text-slate-600">Loading client...</p>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">Error loading client</p>
      <p class="mt-1 text-sm">{{ error }}</p>
    </div>

    <!-- Client Profile -->
    <div v-else-if="client">
      <!-- Hero Header -->
      <header class="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <!-- Client Info -->
          <div class="flex items-start gap-4">
            <div
              class="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-2xl font-semibold text-emerald-700"
            >
              {{ client.first_name[0] }}{{ client.last_name[0] }}
            </div>
            <div>
              <h1 class="text-2xl font-semibold text-slate-900">
                {{ client.full_name }}
              </h1>
              <div class="mt-1 space-y-0.5 text-sm text-slate-600">
                <p v-if="client.email">{{ client.email }}</p>
                <p v-if="client.phone">{{ client.phone }}</p>
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex gap-2">
            <button
              @click="editClient"
              class="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              Edit
            </button>
            <button
              @click="scheduleAppointment"
              class="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
            >
              <svg
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              Schedule
            </button>
          </div>
        </div>
      </header>

      <!-- Tabs -->
      <div class="mb-6 border-b border-slate-200">
        <nav class="flex space-x-8" aria-label="Tabs">
          <button
            @click="activeTab = 'overview'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'overview'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            Overview
          </button>
          <button
            @click="activeTab = 'history'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'history'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            History
          </button>
          <button
            @click="activeTab = 'plan-of-care'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'plan-of-care'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            Plan of Care
          </button>
          <button
            @click="activeTab = 'files'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'files'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            Files
          </button>
        </nav>
      </div>

      <!-- Tab Content -->
      <div class="rounded-lg border border-slate-200 bg-white p-6">
        <!-- Overview Tab -->
        <div v-if="activeTab === 'overview'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Client Information</h2>
          <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt class="text-sm font-medium text-slate-500">Date of Birth</dt>
              <dd class="mt-1 text-sm text-slate-900">
                {{
                  client.date_of_birth
                    ? new Date(client.date_of_birth).toLocaleDateString()
                    : 'Not provided'
                }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">Address</dt>
              <dd class="mt-1 text-sm text-slate-900">
                {{ client.address || 'Not provided' }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">Emergency Contact</dt>
              <dd class="mt-1 text-sm text-slate-900">
                {{ client.emergency_contact_name || 'Not provided' }}
                <span
                  v-if="client.emergency_contact_phone"
                  class="block text-slate-600"
                >
                  {{ client.emergency_contact_phone }}
                </span>
              </dd>
            </div>
          </dl>

          <div v-if="client.medical_history" class="mt-6">
            <h3 class="text-sm font-medium text-slate-500">Medical History</h3>
            <p class="mt-2 text-sm whitespace-pre-wrap text-slate-900">
              {{ client.medical_history }}
            </p>
          </div>

          <div v-if="client.notes" class="mt-6">
            <h3 class="text-sm font-medium text-slate-500">Notes</h3>
            <p class="mt-2 text-sm whitespace-pre-wrap text-slate-900">
              {{ client.notes }}
            </p>
          </div>
        </div>

        <!-- History Tab -->
        <div v-else-if="activeTab === 'history'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Treatment History</h2>
          <p class="text-sm text-slate-600">
            Coming in M4 - Chronological timeline of appointments and sessions
          </p>
        </div>

        <!-- Plan of Care Tab -->
        <div v-else-if="activeTab === 'plan-of-care'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Plan of Care</h2>
          <p class="text-sm text-slate-600">
            Coming in M4 - Treatment plans, goals, and milestones
          </p>
        </div>

        <!-- Files Tab -->
        <div v-else-if="activeTab === 'files'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Files & Documents</h2>
          <p class="text-sm text-slate-600">
            Coming in M4 - Uploaded documents, consent forms, images
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
