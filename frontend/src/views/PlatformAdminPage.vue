<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePlatformAdmin } from '@/composables/usePlatformAdmin'
import CreateWorkspaceModal from '@/components/platform-admin/CreateWorkspaceModal.vue'
import type { InviteTherapistRequest } from '@/api/generated'

const {
  pendingInvitations,
  loading,
  error,
  fetchPendingInvitations,
  inviteTherapist,
  resendInvitation,
  clearError,
} = usePlatformAdmin()

const showInviteModal = ref(false)

onMounted(async () => {
  await fetchPendingInvitations()
})

async function handleInviteTherapist(data: InviteTherapistRequest) {
  try {
    await inviteTherapist(data)
    // Show success message and close modal
    showInviteModal.value = false
    alert('Invitation sent successfully!')
  } catch (err) {
    // Error already set in composable - modal will display it
    console.error('Failed to invite therapist:', err)
  }
}

function openInviteModal() {
  clearError() // Clear any previous errors before opening modal
  showInviteModal.value = true
}

async function handleResendInvitation(userId: string) {
  try {
    await resendInvitation(userId)
    // Show success message (simple alert for now, can be toast later)
    alert('Invitation resent successfully!')
  } catch (err) {
    // Error already set in composable
    console.error('Failed to resend invitation:', err)
  }
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function calculateExpiresAt(invitedAt: string): string {
  const date = new Date(invitedAt)
  date.setDate(date.getDate() + 7)
  return formatDate(date.toISOString())
}

function isExpired(invitedAt: string): boolean {
  const expirationDate = new Date(invitedAt)
  expirationDate.setDate(expirationDate.getDate() + 7)
  return expirationDate < new Date()
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
    <!-- Header -->
    <header class="border-b border-slate-200 bg-white shadow-sm">
      <div class="mx-auto max-w-7xl px-6 py-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-slate-900">PazPaz Platform Admin</h1>
            <p class="mt-1 text-slate-600">
              Manage therapist invitations and workspaces
            </p>
          </div>
          <div class="text-right">
            <div class="text-2xl font-semibold text-emerald-600">
              {{ pendingInvitations.length }}
            </div>
            <div class="text-sm text-slate-600">pending invitations</div>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="mx-auto max-w-7xl px-6 py-8">
      <!-- Action Bar -->
      <div class="mb-6 flex items-center justify-between">
        <h2 class="text-xl font-semibold text-slate-900">Pending Invitations</h2>
        <button
          @click="openInviteModal"
          class="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          + Invite Therapist
        </button>
      </div>

      <!-- Error Message -->
      <div
        v-if="error"
        class="mb-6 rounded-lg border border-red-200 bg-red-50 p-4"
        role="alert"
      >
        <div class="flex items-start">
          <svg
            class="mt-0.5 mr-3 h-5 w-5 text-red-600"
            fill="currentColor"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              fill-rule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clip-rule="evenodd"
            />
          </svg>
          <div class="flex-1">
            <p class="text-sm font-medium text-red-800">{{ error }}</p>
          </div>
          <button
            @click="clearError"
            class="text-red-600 hover:text-red-800"
            aria-label="Dismiss error"
          >
            <svg
              class="h-5 w-5"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading && !pendingInvitations.length" class="py-12 text-center">
        <div
          class="inline-block h-12 w-12 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"
          role="status"
          aria-label="Loading pending invitations"
        ></div>
        <p class="mt-4 text-slate-600">Loading pending invitations...</p>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="!loading && !pendingInvitations.length"
        class="rounded-lg border border-slate-200 bg-white py-12 text-center"
      >
        <svg
          class="mx-auto h-16 w-16 text-slate-400"
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
        <h3 class="mt-4 text-lg font-medium text-slate-900">No pending invitations</h3>
        <p class="mt-2 text-sm text-slate-600">
          Get started by inviting your first therapist to PazPaz.
        </p>
        <button
          @click="openInviteModal"
          class="mt-6 rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
        >
          Invite Therapist
        </button>
      </div>

      <!-- Invitations List -->
      <div v-else class="space-y-4">
        <div
          v-for="invitation in pendingInvitations"
          :key="invitation.user_id"
          class="rounded-lg border border-slate-200 bg-white p-6 transition hover:shadow-md"
        >
          <div class="flex items-start justify-between">
            <!-- Invitation Info -->
            <div class="flex-1">
              <div class="flex items-center gap-3">
                <!-- Avatar -->
                <div
                  class="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-lg font-semibold text-emerald-700"
                  aria-hidden="true"
                >
                  {{ invitation.full_name.split(' ')[0]?.[0] || 'T'
                  }}{{ invitation.full_name.split(' ')[1]?.[0] || '' }}
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-slate-900">
                    {{ invitation.full_name }}
                  </h3>
                  <p class="mt-1 text-sm text-slate-600">{{ invitation.email }}</p>
                </div>
              </div>

              <p class="mt-3 text-sm text-slate-500">
                <span class="font-medium">Workspace:</span>
                {{ invitation.workspace_name }}
              </p>

              <div
                class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500"
              >
                <div>
                  <span class="font-medium">Invited:</span>
                  {{ formatDate(invitation.invited_at) }}
                </div>
                <div
                  :class="{
                    'font-medium text-red-600': isExpired(invitation.invited_at),
                  }"
                >
                  <span class="font-medium">Expires:</span>
                  {{ calculateExpiresAt(invitation.invited_at) }}
                  <span v-if="isExpired(invitation.invited_at)" class="ml-1"
                    >(Expired)</span
                  >
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="ml-4">
              <button
                @click="handleResendInvitation(invitation.user_id)"
                :disabled="loading"
                class="rounded-lg border border-emerald-600 px-3 py-1 text-sm text-emerald-600 transition hover:bg-emerald-50 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                :aria-label="`Resend invitation to ${invitation.full_name}`"
              >
                Resend Invitation
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Invite Modal -->
    <CreateWorkspaceModal
      v-if="showInviteModal"
      :error="error"
      :isLoading="loading"
      @close="showInviteModal = false"
      @submit="handleInviteTherapist"
    />
  </div>
</template>

<style scoped>
/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .transition,
  .animate-spin {
    animation: none !important;
    transition: none !important;
  }
}
</style>
