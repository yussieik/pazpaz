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
import type { SessionResponse } from '@/types/sessions'
import SessionCard from '@/components/sessions/SessionCard.vue'
import IconDocument from '@/components/icons/IconDocument.vue'
import { smartTruncate } from '@/utils/textFormatters'
import { getDurationMinutes } from '@/utils/calendar/dateFormatters'

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
  data: SessionResponse | AppointmentItem
}

// State
const sessions = ref<SessionResponse[]>([])
const appointments = ref<AppointmentItem[]>([])
const sessionAppointments = ref<Map<string, AppointmentItem>>(new Map())
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
  // IMPORTANT: Must fetch sessions FIRST before appointments
  // fetchAppointments() depends on sessions.value to filter out appointments with existing sessions
  await fetchSessions()
  await fetchAppointments()
})

async function fetchSessions() {
  try {
    const response = await apiClient.get(`/sessions?client_id=${props.clientId}`)
    const fetchedSessions = response.data.items || []
    sessions.value = fetchedSessions

    // Fetch appointment details for sessions that have appointment_id
    const appointmentIds = fetchedSessions
      .map((s: SessionResponse) => s.appointment_id)
      .filter(Boolean) as string[]

    if (appointmentIds.length > 0) {
      // Fetch appointments in parallel
      const appointmentPromises = appointmentIds.map((id) =>
        apiClient.get(`/appointments/${id}`).catch(() => null)
      )
      const appointmentResponses = await Promise.all(appointmentPromises)

      // Build map of session_id -> appointment
      sessionAppointments.value.clear()
      fetchedSessions.forEach((session: SessionResponse, index: number) => {
        if (session.appointment_id && appointmentResponses[index]?.data) {
          sessionAppointments.value.set(session.id, appointmentResponses[index].data)
        }
      })
    }
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

    const filteredAppointments = (response.data.items || []).filter(
      (appt: AppointmentItem) => !sessionAppointmentIds.has(appt.id)
    )
    appointments.value = filteredAppointments
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
      duration_minutes: getDurationMinutes(
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

function formatDate(date: string): string {
  return format(new Date(date), 'MMM d, yyyy • h:mm a')
}

function isSession(item: TimelineItem): item is TimelineItem & { data: SessionResponse } {
  return item.type === 'session'
}

function isAppointment(
  item: TimelineItem
): item is TimelineItem & { data: AppointmentItem } {
  return item.type === 'appointment'
}

/**
 * Get appointment details for a session
 */
function getAppointmentForSession(sessionId: string): AppointmentItem | undefined {
  return sessionAppointments.value.get(sessionId)
}

/**
 * Format appointment context for display
 * Format: "Service Name • Location • Duration"
 */
function formatAppointmentContext(appointment: AppointmentItem): string {
  const parts: string[] = []

  if (appointment.service_name) {
    parts.push(appointment.service_name)
  }

  if (appointment.location_type) {
    const locationLabel: Record<string, string> = {
      clinic: 'Clinic',
      home: 'Home Visit',
      online: 'Online',
    }
    parts.push(locationLabel[appointment.location_type] || appointment.location_type)
  }

  const duration = getDurationMinutes(
    appointment.scheduled_start,
    appointment.scheduled_end
  )
  if (duration > 0) {
    parts.push(`${duration} min`)
  }

  return parts.join(' • ')
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
 * Format full SOAP preview for timeline display
 * Shows all 4 SOAP fields with labels and intelligent truncation
 * @param session - Session data with SOAP fields
 * @param isMobile - Whether to use mobile truncation (40 chars) or desktop (60 chars)
 * @returns Formatted SOAP preview string or "Draft - incomplete" if empty
 */
function formatSOAPPreview(session: SessionResponse, isMobile: boolean = false): string {
  const maxLength = isMobile ? 40 : 60
  const fields = [
    { label: 'S', value: session.subjective },
    { label: 'O', value: session.objective },
    { label: 'A', value: session.assessment },
    { label: 'P', value: session.plan },
  ]

  // Check if all fields are empty
  const hasContent = fields.some((field) => field.value && field.value.trim().length > 0)
  if (!hasContent) {
    return ''
  }

  // Format each field with label and truncated value
  const formattedFields = fields
    .map((field) => {
      if (!field.value || field.value.trim().length === 0) {
        return `${field.label}: —`
      }
      const truncated = smartTruncate(field.value, maxLength)
      return `${field.label}: ${truncated}`
    })
    .join(' | ')

  return formattedFields
}

/**
 * Check if session has any SOAP content
 */
function hasSOAPContent(session: SessionResponse): boolean {
  return !!(
    session.subjective ||
    session.objective ||
    session.assessment ||
    session.plan
  )
}

/**
 * Refresh the timeline by fetching both sessions and appointments
 * Exposed to parent components for manual refresh triggers
 * IMPORTANT: Must fetch sessions FIRST before appointments (fetchAppointments depends on sessions.value)
 */
async function refresh() {
  await fetchSessions()
  await fetchAppointments()
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
      <IconDocument size="lg" class="mx-auto text-slate-400" />
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
      class="space-y-3"
    >
      <!-- Session Note -->
      <SessionCard
        v-for="item in timeline.filter(isSession)"
        :key="`session-${item.id}`"
        :session="item.data"
        :class="[
          'border-l-4',
          item.data.is_draft ? 'border-l-blue-500' : 'border-l-green-500',
        ]"
        :style="{ paddingLeft: '1rem' }"
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
                <h4 class="text-sm font-semibold text-slate-900">
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

              <!-- Appointment Context (if appointment exists) -->
              <div
                v-if="getAppointmentForSession(item.data.id)"
                class="mt-1 text-sm text-slate-600"
              >
                <span class="inline-flex items-center gap-1">
                  <svg
                    class="h-3.5 w-3.5 text-slate-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                    />
                  </svg>
                  {{
                    formatAppointmentContext(getAppointmentForSession(item.data.id)!)
                  }}
                </span>
              </div>

              <!-- Standalone session label -->
              <div
                v-else-if="item.data.appointment_id === null"
                class="mt-1 text-sm text-slate-500 italic"
              >
                Standalone session
              </div>

              <!-- Full SOAP Preview (all 4 fields) -->
              <div v-if="hasSOAPContent(item.data)" class="mt-2">
                <!-- Desktop: 60 chars per field -->
                <p class="hidden text-xs text-slate-600 sm:block">
                  {{ formatSOAPPreview(item.data, false) }}
                </p>
                <!-- Mobile: 40 chars per field -->
                <p class="text-xs text-slate-600 sm:hidden">
                  {{ formatSOAPPreview(item.data, true) }}
                </p>
              </div>

              <!-- Empty state for drafts with no content -->
              <div v-else>
                <span
                  class="mt-2 inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500"
                >
                  Draft - incomplete
                </span>
              </div>

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
        class="rounded-lg border border-slate-200 bg-slate-50 p-3.5 transition-colors hover:border-slate-300 hover:bg-slate-100"
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
                getDurationMinutes(item.data.scheduled_start, item.data.scheduled_end)
              }}
              minutes •
              {{ item.data.service_name || 'Appointment' }}
            </p>
            <p v-if="item.data.notes" class="mt-1 line-clamp-1 text-sm text-slate-500">
              {{ smartTruncate(item.data.notes, 100) }}
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
