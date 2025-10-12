<script setup lang="ts">
/**
 * SessionTimeline Component
 *
 * Displays a chronological timeline of treatment history combining:
 * - Session notes (SOAP documentation) with draft/finalized status
 * - Completed appointments without session notes (with option to create)
 *
 * Features:
 * - Chronological order (most recent first)
 * - SOAP preview for sessions
 * - Create session note from appointment
 * - Navigation to session detail view
 * - Empty state for new clients
 * - Loading and error states
 *
 * Usage:
 *   <SessionTimeline :client-id="clientId" />
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { format } from 'date-fns'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import SessionCard from '@/components/sessions/SessionCard.vue'

interface Props {
  clientId: string
}

const props = defineProps<Props>()

interface Emits {
  (e: 'session-deleted'): void
  (e: 'trigger-badge-pulse'): void
}

const emit = defineEmits<Emits>()
const router = useRouter()

// Session data interface
interface SessionItem {
  id: string
  client_id: string
  appointment_id: string | null
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  session_date: string
  duration_minutes: number | null
  is_draft: boolean
  draft_last_saved_at: string | null
  finalized_at: string | null
}

// Appointment data interface
interface AppointmentItem {
  id: string
  client_id: string
  scheduled_start: string
  scheduled_end: string
  location_type: 'clinic' | 'home' | 'online'
  notes: string | null
  status: 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show'
  service_name?: string | null
}

// Timeline item (unified interface)
interface TimelineItem {
  id: string
  type: 'session' | 'appointment'
  sortDate: Date
  data: SessionItem | AppointmentItem
}

// State
const sessions = ref<SessionItem[]>([])
const appointments = ref<AppointmentItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

// Merged timeline (sessions + appointments, sorted by date DESC)
const timeline = computed(() => {
  const items: TimelineItem[] = [
    ...sessions.value.map((s) => ({
      id: s.id,
      type: 'session' as const,
      sortDate: new Date(s.session_date),
      data: s,
    })),
    ...appointments.value.map((a) => ({
      id: a.id,
      type: 'appointment' as const,
      sortDate: new Date(a.scheduled_start),
      data: a,
    })),
  ]
  return items.sort((a, b) => b.sortDate.getTime() - a.sortDate.getTime())
})

const isEmpty = computed(
  () => sessions.value.length === 0 && appointments.value.length === 0
)

// Fetch data
onMounted(async () => {
  await Promise.all([fetchSessions(), fetchAppointments()])
})

async function fetchSessions() {
  try {
    const response = await apiClient.get(`/sessions?client_id=${props.clientId}`)
    sessions.value = response.data.items || []
  } catch (err) {
    console.error('Failed to fetch sessions:', err)
    const axiosError = err as AxiosError<{ detail?: string }>
    error.value = axiosError.response?.data?.detail || 'Failed to load session history'
  } finally {
    loading.value = false
  }
}

async function fetchAppointments() {
  try {
    // Fetch completed appointments for this client
    const response = await apiClient.get(
      `/appointments?client_id=${props.clientId}&status=completed`
    )
    // Filter out appointments that already have sessions
    const sessionAppointmentIds = new Set(
      sessions.value.map((s) => s.appointment_id).filter(Boolean)
    )
    appointments.value = (response.data.items || []).filter(
      (appt: AppointmentItem) => !sessionAppointmentIds.has(appt.id)
    )
  } catch (err) {
    console.error('Failed to fetch appointments:', err)
    // Don't set error - appointments are supplementary
  }
}

// Actions
function viewSession(sessionId: string) {
  router.push({
    path: `/sessions/${sessionId}`,
    state: {
      from: 'client-history',
      clientId: props.clientId,
      returnTo: 'client-detail',
    },
  })
}

async function createSession(appointmentId: string) {
  try {
    const appointment = appointments.value.find((a) => a.id === appointmentId)
    if (!appointment) return

    const response = await apiClient.post('/sessions', {
      client_id: props.clientId,
      appointment_id: appointmentId,
      session_date: appointment.scheduled_start,
      duration_minutes: calculateDuration(
        appointment.scheduled_start,
        appointment.scheduled_end
      ),
      is_draft: true,
    })

    router.push({
      path: `/sessions/${response.data.id}`,
      state: {
        from: 'client-history',
        clientId: props.clientId,
        returnTo: 'client-detail',
      },
    })
  } catch (err) {
    console.error('Failed to create session:', err)
    alert('Failed to create session note. Please try again.')
  }
}

function calculateDuration(start: string, end: string): number {
  const diffMs = new Date(end).getTime() - new Date(start).getTime()
  return Math.max(0, Math.round(diffMs / (1000 * 60)))
}

function formatDate(date: string): string {
  return format(new Date(date), 'MMM d, yyyy • h:mm a')
}

function truncate(text: string | null, length: number): string {
  if (!text) return ''
  return text.length > length ? text.substring(0, length) + '...' : text
}

function isSession(item: TimelineItem): item is TimelineItem & { data: SessionItem } {
  return item.type === 'session'
}

function isAppointment(
  item: TimelineItem
): item is TimelineItem & { data: AppointmentItem } {
  return item.type === 'appointment'
}

/**
 * Handle session deletion from SessionCard
 * Remove from local array and notify parent
 */
function handleSessionDeleted(sessionId: string) {
  // Remove from local sessions array (optimistic update)
  sessions.value = sessions.value.filter((s) => s.id !== sessionId)

  // Notify parent to refresh DeletedNotesSection
  emit('session-deleted')

  // Trigger badge pulse if Deleted Notes section is collapsed
  emit('trigger-badge-pulse')
}

/**
 * Handle view session from SessionCard
 */
function handleViewSession(sessionId: string) {
  viewSession(sessionId)
}

/**
 * Refresh the timeline by fetching both sessions and appointments
 * Exposed to parent components for manual refresh triggers
 */
async function refresh() {
  await Promise.all([fetchSessions(), fetchAppointments()])
}

// Expose refresh method to parent components
defineExpose({
  refresh,
})
</script>

<template>
  <div class="session-timeline">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div
        class="h-8 w-8 animate-spin rounded-full border-b-2 border-emerald-600"
      ></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="rounded-md bg-red-50 p-4">
      <p class="text-sm text-red-800">{{ error }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="isEmpty" class="py-12 text-center">
      <svg
        class="mx-auto h-12 w-12 text-slate-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-slate-900">No sessions yet</h3>
      <p class="mt-1 text-sm text-slate-500">
        Schedule an appointment to start documenting treatment.
      </p>
    </div>

    <!-- Timeline -->
    <TransitionGroup
      v-if="!isEmpty && !loading && !error"
      name="session-list"
      tag="div"
      class="space-y-4"
    >
      <!-- Session Note -->
      <SessionCard
        v-for="item in timeline.filter(isSession)"
        :key="`session-${item.id}`"
        :session="item.data"
        @deleted="handleSessionDeleted"
        @view="handleViewSession"
      >
        <template #content>
          <div class="flex items-start gap-3">
            <!-- Icon -->
            <div class="flex-shrink-0">
              <div
                class="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100"
              >
                <svg
                  class="h-5 w-5 text-blue-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
            </div>

            <!-- Content -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between gap-2">
                <h4 class="text-sm font-medium text-slate-900">
                  {{ formatDate(item.data.session_date) }}
                </h4>
                <span
                  :class="[
                    'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                    item.data.is_draft
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-green-100 text-green-800',
                  ]"
                >
                  {{ item.data.is_draft ? 'Draft' : 'Finalized' }}
                </span>
              </div>

              <!-- SOAP Preview -->
              <p
                v-if="item.data.subjective"
                class="mt-1 line-clamp-2 text-sm text-slate-600"
              >
                {{ truncate(item.data.subjective, 150) }}
              </p>
              <p v-else class="mt-1 text-sm text-slate-400 italic">No content yet</p>

              <!-- Duration -->
              <p v-if="item.data.duration_minutes" class="mt-1 text-xs text-slate-500">
                {{ item.data.duration_minutes }} minutes
              </p>

              <!-- Action Button -->
              <button
                @click="viewSession(item.data.id)"
                class="mt-2 text-sm font-medium text-blue-600 hover:text-blue-800"
              >
                {{ item.data.is_draft ? 'Continue Editing →' : 'View Full Note →' }}
              </button>
            </div>
          </div>
        </template>
      </SessionCard>

      <!-- Appointment (no session) -->
      <div
        v-for="item in timeline.filter(isAppointment)"
        :key="`appointment-${item.id}`"
        class="rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-slate-300"
      >
        <div class="flex items-start gap-3">
          <!-- Icon -->
          <div class="flex-shrink-0">
            <div
              class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100"
            >
              <svg
                class="h-5 w-5 text-slate-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </div>
          </div>

          <!-- Content -->
          <div class="min-w-0 flex-1">
            <h4 class="text-sm font-medium text-slate-900">
              {{ formatDate(item.data.scheduled_start) }}
            </h4>
            <p class="mt-1 text-sm text-slate-600">
              {{
                calculateDuration(item.data.scheduled_start, item.data.scheduled_end)
              }}
              minutes •
              {{ item.data.service_name || 'Appointment' }}
            </p>
            <p v-if="item.data.notes" class="mt-1 line-clamp-1 text-sm text-slate-500">
              {{ truncate(item.data.notes, 100) }}
            </p>

            <!-- Action Button -->
            <button
              @click="createSession(item.id)"
              class="mt-2 text-sm font-medium text-blue-600 hover:text-blue-800"
            >
              Create Session Note →
            </button>
          </div>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
/* Line clamp utility for text truncation */
.line-clamp-1 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.line-clamp-2 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

/* Session card deletion animation */
.session-list-leave-active {
  transition: all 0.3s ease-in-out;
}

.session-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
  max-height: 0;
  margin-bottom: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
