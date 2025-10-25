<script setup lang="ts">
import { ref, watch } from 'vue'
import { format, formatDistanceToNow } from 'date-fns'
import type { SessionVersion, SessionWithAmendments } from '@/types/calendar'
import apiClient from '@/api/client'

interface Props {
  sessionId: string
  session: SessionWithAmendments | null
  open: boolean
}

interface Emits {
  (e: 'close'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// State
const versions = ref<SessionVersion[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const expandedVersion = ref<string | null>(null)

/**
 * Fetch version history from API
 */
async function fetchVersionHistory() {
  if (!props.sessionId) return

  isLoading.value = true
  error.value = null

  try {
    const response = await apiClient.get<{ versions: SessionVersion[] }>(
      `/sessions/${props.sessionId}/versions`
    )
    versions.value = response.data.versions || []
  } catch (err) {
    console.error('Error fetching version history:', err)
    error.value = 'Failed to load version history'
  } finally {
    isLoading.value = false
  }
}

/**
 * Toggle version expansion
 */
function toggleVersion(versionId: string) {
  expandedVersion.value = expandedVersion.value === versionId ? null : versionId
}

/**
 * Format absolute time
 */
function formatAbsoluteTime(isoString: string): string {
  return format(new Date(isoString), "MMM d, yyyy 'at' h:mm a")
}

/**
 * Format relative time
 */
function formatRelativeTime(isoString: string): string {
  return formatDistanceToNow(new Date(isoString), { addSuffix: true })
}

/**
 * Format date and time for session
 */
function formatDateTime(isoString: string): string {
  return format(new Date(isoString), "EEEE, MMMM d, yyyy 'at' h:mm a")
}

/**
 * Close modal
 */
function closeModal() {
  emit('close')
}

/**
 * Handle Escape key
 */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    closeModal()
  }
}

/**
 * Fetch versions when modal opens
 */
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      fetchVersionHistory()
    } else {
      // Reset state when closed
      versions.value = []
      expandedVersion.value = null
      error.value = null
    }
  }
)
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
        v-if="open"
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
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="version-history-title"
        @keydown="handleKeydown"
      >
        <div
          class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white shadow-xl"
          @click.stop
        >
          <!-- Header -->
          <div
            class="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white px-6 py-4"
          >
            <div>
              <h3
                id="version-history-title"
                class="text-lg font-semibold text-slate-900"
              >
                Note History
              </h3>
              <p v-if="session" class="mt-1 text-sm text-slate-600">
                Session from {{ formatDateTime(session.created_at || '') }}
              </p>
            </div>
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

          <!-- Loading State -->
          <div v-if="isLoading" class="flex items-center justify-center p-12">
            <svg
              class="h-8 w-8 animate-spin text-emerald-600"
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
          </div>

          <!-- Error State -->
          <div
            v-else-if="error"
            class="m-6 rounded-lg border border-red-200 bg-red-50 p-4"
          >
            <div class="flex gap-3">
              <svg
                class="h-5 w-5 flex-shrink-0 text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <div>
                <h3 class="text-sm font-medium text-red-800">Error</h3>
                <p class="mt-1 text-sm text-red-700">{{ error }}</p>
              </div>
            </div>
          </div>

          <!-- Versions List -->
          <div v-else class="space-y-4 p-6">
            <!-- Current Version (if session exists) -->
            <div
              v-if="session"
              class="rounded-lg border-2 border-emerald-200 bg-emerald-50"
            >
              <button
                @click="toggleVersion('current')"
                class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-emerald-100"
              >
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <p class="font-medium text-slate-900">Current Version</p>
                    <span
                      class="rounded bg-emerald-200 px-2 py-0.5 text-xs font-medium text-emerald-800"
                    >
                      Latest
                    </span>
                  </div>
                  <p v-if="session.amended_at" class="mt-1 text-sm text-slate-600">
                    Amended {{ formatRelativeTime(session.amended_at) }}
                  </p>
                  <p
                    v-else-if="session.finalized_at"
                    class="mt-1 text-sm text-slate-600"
                  >
                    Finalized {{ formatRelativeTime(session.finalized_at) }}
                  </p>
                </div>
                <svg
                  class="h-5 w-5 text-slate-400 transition-transform"
                  :class="{ 'rotate-180': expandedVersion === 'current' }"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>
              <div
                v-if="expandedVersion === 'current'"
                class="space-y-4 border-t border-emerald-200 bg-white p-4"
              >
                <div v-if="session.subjective">
                  <p class="text-xs font-medium text-slate-500 uppercase">Subjective</p>
                  <p class="mt-1 text-sm text-slate-900">{{ session.subjective }}</p>
                </div>
                <div v-if="session.objective">
                  <p class="text-xs font-medium text-slate-500 uppercase">Objective</p>
                  <p class="mt-1 text-sm text-slate-900">{{ session.objective }}</p>
                </div>
                <div v-if="session.assessment">
                  <p class="text-xs font-medium text-slate-500 uppercase">Assessment</p>
                  <p class="mt-1 text-sm text-slate-900">{{ session.assessment }}</p>
                </div>
                <div v-if="session.plan">
                  <p class="text-xs font-medium text-slate-500 uppercase">Plan</p>
                  <p class="mt-1 text-sm text-slate-900">{{ session.plan }}</p>
                </div>
              </div>
            </div>

            <!-- Version History -->
            <div
              v-for="version in versions"
              :key="version.id"
              class="rounded-lg border border-slate-200 bg-slate-50"
            >
              <button
                @click="toggleVersion(version.id)"
                class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-100"
              >
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <p class="font-medium text-slate-700">
                      Version {{ version.version_number }}
                    </p>
                    <span
                      v-if="version.version_number === 1"
                      class="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800"
                    >
                      Original
                    </span>
                  </div>
                  <p class="mt-1 text-sm text-slate-600">
                    {{ formatAbsoluteTime(version.created_at) }}
                  </p>
                </div>
                <svg
                  class="h-5 w-5 text-slate-400 transition-transform"
                  :class="{ 'rotate-180': expandedVersion === version.id }"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>
              <div
                v-if="expandedVersion === version.id"
                class="space-y-4 border-t border-slate-200 bg-white p-4"
              >
                <div v-if="version.subjective">
                  <p class="text-xs font-medium text-slate-500 uppercase">Subjective</p>
                  <p class="mt-1 text-sm text-slate-700">{{ version.subjective }}</p>
                </div>
                <div v-if="version.objective">
                  <p class="text-xs font-medium text-slate-500 uppercase">Objective</p>
                  <p class="mt-1 text-sm text-slate-700">{{ version.objective }}</p>
                </div>
                <div v-if="version.assessment">
                  <p class="text-xs font-medium text-slate-500 uppercase">Assessment</p>
                  <p class="mt-1 text-sm text-slate-700">{{ version.assessment }}</p>
                </div>
                <div v-if="version.plan">
                  <p class="text-xs font-medium text-slate-500 uppercase">Plan</p>
                  <p class="mt-1 text-sm text-slate-700">{{ version.plan }}</p>
                </div>
              </div>
            </div>

            <!-- Empty State -->
            <div
              v-if="!session && versions.length === 0"
              class="py-12 text-center text-slate-500"
            >
              <p>No version history available</p>
            </div>
          </div>

          <!-- Footer -->
          <div class="sticky bottom-0 border-t border-slate-200 bg-slate-50 px-6 py-4">
            <div class="flex justify-end">
              <button
                @click="closeModal"
                class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
