<script setup lang="ts">
/**
 * SessionView - Session Detail Page
 *
 * Route: /sessions/:id
 *
 * Displays a SOAP session note with client context and metadata.
 * Wraps the SessionEditor component and handles data loading.
 *
 * Features:
 * - Loads session and client data
 * - Shows PageHeader with client name
 * - Handles session finalized event
 * - Back navigation to client detail or calendar
 */

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { onKeyStroke } from '@vueuse/core'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import type { SessionResponse } from '@/types/sessions'
import PageHeader from '@/components/common/PageHeader.vue'
import SessionEditor from '@/components/sessions/SessionEditor.vue'

const route = useRoute()
const router = useRouter()

interface ClientData {
  id: string
  first_name: string
  last_name: string
  email: string | null
  phone: string | null
  date_of_birth: string | null
  created_at: string
  updated_at: string
}

// State
const session = ref<SessionResponse | null>(null)
const client = ref<ClientData | null>(null)
const isLoadingSession = ref(true)
const isLoadingClient = ref(false)
const loadError = ref<string | null>(null)

// Computed
const sessionId = computed(() => route.params.id as string)

const pageTitle = computed(() => {
  if (client.value) {
    return `Session Note - ${client.value.first_name} ${client.value.last_name}`
  }
  return 'Session Note'
})

const pageMetadata = computed(() => {
  if (session.value) {
    const date = new Date(session.value.session_date)
    const formattedDate = date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
    const formattedTime = date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    })

    const status = session.value.is_draft ? 'Draft' : 'Finalized'
    return `${formattedDate} at ${formattedTime} • ${status}`
  }
  return ''
})

// Load session data
async function loadSession(silent = false) {
  if (!silent) {
    isLoadingSession.value = true
  }
  loadError.value = null

  try {
    // Parallel loading to prevent waterfall and reduce glitches
    const [sessionResponse, clientResponse] = await Promise.allSettled([
      apiClient.get<SessionResponse>(`/sessions/${sessionId.value}`),
      // Pre-emptively load client if we already know the client_id
      session.value?.client_id
        ? apiClient.get<ClientData>(`/clients/${session.value.client_id}`)
        : Promise.resolve(null),
    ])

    if (sessionResponse.status === 'fulfilled') {
      const previousSession = session.value
      session.value = sessionResponse.value.data

      // If client_id changed or not loaded yet, load client data
      if (
        sessionResponse.value.data.client_id &&
        sessionResponse.value.data.client_id !== previousSession?.client_id
      ) {
        // Only load if we don't already have it from parallel fetch
        if (clientResponse.status !== 'fulfilled' || !clientResponse.value) {
          isLoadingClient.value = true
          try {
            const response = await apiClient.get<ClientData>(
              `/clients/${sessionResponse.value.data.client_id}`
            )
            client.value = response.data
          } catch (error) {
            console.error('Failed to load client:', error)
          } finally {
            isLoadingClient.value = false
          }
        } else if (clientResponse.value) {
          client.value = (clientResponse.value as { data: ClientData }).data
        }
      }
    } else {
      throw sessionResponse.reason
    }
  } catch (error) {
    console.error('Failed to load session:', error)
    const axiosError = error as AxiosError<{ detail?: string }>

    if (axiosError.response?.status === 404) {
      loadError.value = 'Session not found'
    } else if (axiosError.response?.status === 403) {
      loadError.value = 'You do not have permission to view this session'
    } else {
      loadError.value = axiosError.response?.data?.detail || 'Failed to load session'
    }
  } finally {
    if (!silent) {
      isLoadingSession.value = false
    }
  }
}

// Load client data
async function loadClient(clientId: string) {
  isLoadingClient.value = true

  try {
    const response = await apiClient.get<ClientData>(`/clients/${clientId}`)
    client.value = response.data
  } catch (error) {
    console.error('Failed to load client:', error)
    // Don't set error - client data is supplementary
  } finally {
    isLoadingClient.value = false
  }
}

// Handle session finalized - optimistic update instead of full reload
function handleSessionFinalized() {
  // Optimistic update: immediately update session status
  if (session.value) {
    session.value.is_draft = false
    session.value.finalized_at = new Date().toISOString()
  }

  // Silent background sync to ensure we have latest server state
  // This won't cause a glitch since we're not showing loading state
  loadSession(true)
}

// Navigate back
function goBack() {
  const state = window.history.state as {
    from?: string
    clientId?: string
    appointmentId?: string
    returnTo?: string
  }

  // Return to client detail history tab
  if (
    state?.from === 'client-history' &&
    state?.clientId &&
    state?.returnTo === 'client-detail'
  ) {
    router.push({
      path: `/clients/${state.clientId}`,
      query: { tab: 'history' },
    })
  }
  // Return to calendar with appointment modal
  else if (
    state?.from === 'appointment' &&
    state?.appointmentId &&
    state?.returnTo === 'calendar'
  ) {
    router.push({
      path: '/',
      query: { appointment: state.appointmentId },
    })
  }
  // Default: Return to client detail
  else if (session.value?.client_id) {
    router.push(`/clients/${session.value.client_id}`)
  }
  // Fallback: Calendar
  else {
    router.push('/')
  }
}

// Lifecycle
onMounted(() => {
  loadSession()
})

// Keyboard shortcuts
onKeyStroke('Escape', (e) => {
  e.preventDefault()
  goBack()
})
</script>

<template>
  <div class="session-view mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
    <!-- Back Button - Reserve space to prevent layout shift -->
    <div class="mb-6 min-h-[32px]">
      <Transition name="fade" mode="out-in">
        <button
          v-if="!isLoadingSession"
          key="back-button"
          type="button"
          @click="goBack"
          class="inline-flex items-center text-sm font-medium text-slate-700 transition-colors hover:text-slate-900 focus:ring-2 focus:ring-blue-600 focus:ring-offset-2 focus:outline-none"
        >
          <svg
            class="mr-2 h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to {{ session?.client_id ? 'Client' : 'Calendar' }}
        </button>
      </Transition>
    </div>

    <!-- Page Header -->
    <PageHeader
      :title="pageTitle"
      :metadata="pageMetadata"
      :loading="isLoadingSession || isLoadingClient"
    />

    <!-- Error State -->
    <div v-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-6">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clip-rule="evenodd"
            />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">Error Loading Session</h3>
          <div class="mt-2 text-sm text-red-700">
            <p>{{ loadError }}</p>
          </div>
          <div class="mt-4">
            <button
              type="button"
              @click="goBack"
              class="rounded-md bg-red-100 px-3 py-2 text-sm font-semibold text-red-800 transition-colors hover:bg-red-200 focus:ring-2 focus:ring-red-600 focus:ring-offset-2 focus:ring-offset-red-50 focus:outline-none"
            >
              Go Back
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Session Editor -->
    <div v-else-if="!isLoadingSession">
      <SessionEditor :session-id="sessionId" @finalized="handleSessionFinalized" />
    </div>
  </div>
</template>

<style scoped>
/* Smooth fade transitions for content appearing/disappearing */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease-in-out;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Prevent layout shifts during transitions */
.session-view {
  min-height: 100vh;
}
</style>
