<script setup lang="ts">
import { ref } from 'vue'

export interface Workspace {
  id: string
  name: string
  email: string
  status: 'active' | 'pending' | 'suspended'
  createdAt: string
  userCount: number
  activeUsers: number
  appointmentCount: number
}

interface Props {
  workspace: Workspace
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'view-details': [workspaceId: string]
  'suspend': [workspaceId: string]
  'resend': [workspaceId: string]
  'reactivate': [workspaceId: string]
}>()

const showActionsMenu = ref(false)

const statusConfig = {
  active: {
    label: 'Active',
    color: 'bg-emerald-100 text-emerald-700',
    icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  pending: {
    label: 'Pending',
    color: 'bg-amber-100 text-amber-700',
    icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  suspended: {
    label: 'Suspended',
    color: 'bg-red-100 text-red-700',
    icon: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function toggleActionsMenu() {
  showActionsMenu.value = !showActionsMenu.value
}

function closeActionsMenu() {
  showActionsMenu.value = false
}

function handleViewDetails() {
  emit('view-details', props.workspace.id)
  closeActionsMenu()
}

function handleSuspend() {
  emit('suspend', props.workspace.id)
  closeActionsMenu()
}

function handleReactivate() {
  emit('reactivate', props.workspace.id)
  closeActionsMenu()
}

function handleResend() {
  emit('resend', props.workspace.id)
  closeActionsMenu()
}

// Close menu when clicking outside
function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('.actions-menu-container')) {
    closeActionsMenu()
  }
}

// Setup click outside listener
if (typeof window !== 'undefined') {
  document.addEventListener('click', handleClickOutside)
}
</script>

<template>
  <div
    class="rounded-xl border border-slate-200 bg-white p-6 transition hover:shadow-md"
    :aria-label="`Workspace: ${workspace.name}`"
  >
    <div class="flex items-start justify-between">
      <!-- Workspace Info -->
      <div class="flex-1">
        <div class="flex items-center gap-3">
          <!-- Avatar -->
          <div
            class="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-lg font-semibold text-emerald-700"
            aria-hidden="true"
          >
            {{ workspace.name[0]?.toUpperCase() || 'W' }}
          </div>

          <div>
            <h3 class="text-lg font-semibold text-slate-900">{{ workspace.name }}</h3>
            <p class="text-sm text-slate-600">{{ workspace.email }}</p>
          </div>
        </div>

        <!-- Stats Row -->
        <div class="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-500">
          <div class="flex items-center gap-1">
            <svg
              class="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
            <span>{{ workspace.userCount }} {{ workspace.userCount === 1 ? 'user' : 'users' }}</span>
          </div>
          <div class="flex items-center gap-1">
            <svg
              class="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>{{ workspace.activeUsers }} active</span>
          </div>
          <div class="flex items-center gap-1">
            <svg
              class="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <span>{{ workspace.appointmentCount }} {{ workspace.appointmentCount === 1 ? 'appointment' : 'appointments' }}</span>
          </div>
          <div class="flex items-center gap-1">
            <svg
              class="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <span>Created {{ formatDate(workspace.createdAt) }}</span>
          </div>
        </div>
      </div>

      <!-- Status Badge & Actions -->
      <div class="ml-4 flex flex-col items-end gap-2">
        <!-- Status Badge -->
        <span
          :class="[statusConfig[workspace.status].color, 'flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold']"
          role="status"
          :aria-label="`Status: ${statusConfig[workspace.status].label}`"
        >
          <svg
            class="h-3 w-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              :d="statusConfig[workspace.status].icon"
            />
          </svg>
          {{ statusConfig[workspace.status].label }}
        </span>

        <!-- Actions Menu -->
        <div class="actions-menu-container relative">
          <button
            @click="toggleActionsMenu"
            class="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            :aria-label="`Actions for ${workspace.name}`"
            aria-haspopup="true"
            :aria-expanded="showActionsMenu"
          >
            <svg
              class="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
              />
            </svg>
          </button>

          <!-- Dropdown Menu -->
          <Transition name="menu">
            <div
              v-if="showActionsMenu"
              class="absolute right-0 z-10 mt-2 w-48 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
              role="menu"
              aria-orientation="vertical"
            >
              <button
                @click="handleViewDetails"
                class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                role="menuitem"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                  />
                </svg>
                View Details
              </button>

              <button
                v-if="workspace.status === 'pending'"
                @click="handleResend"
                class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                role="menuitem"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
                Resend Invitation
              </button>

              <button
                v-if="workspace.status === 'active'"
                @click="handleSuspend"
                class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-red-600 transition hover:bg-red-50"
                role="menuitem"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Suspend Workspace
              </button>

              <button
                v-if="workspace.status === 'suspended'"
                @click="handleReactivate"
                class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-emerald-600 transition hover:bg-emerald-50"
                role="menuitem"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Reactivate Workspace
              </button>
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Menu transition */
.menu-enter-active,
.menu-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .transition,
  .menu-enter-active,
  .menu-leave-active {
    transition: none !important;
  }

  .menu-enter-from,
  .menu-leave-to {
    transform: none !important;
  }
}
</style>
