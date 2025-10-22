<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePlatformAdmin } from '@/composables/usePlatformAdmin'
import { usePlatformMetrics } from '@/composables/usePlatformMetrics'
import { useToast } from '@/composables/useToast'
import type { InviteTherapistRequest } from '@/api/generated'

// Components
import MetricCard from '@/components/platform-admin/MetricCard.vue'
import ActivityTimeline from '@/components/platform-admin/ActivityTimeline.vue'
import QuickActions from '@/components/platform-admin/QuickActions.vue'
import WorkspaceCard from '@/components/platform-admin/WorkspaceCard.vue'
import WorkspaceDetailsModal from '@/components/platform-admin/WorkspaceDetailsModal.vue'
import CreateWorkspaceModal from '@/components/platform-admin/CreateWorkspaceModal.vue'
import ConfirmationModal from '@/components/platform-admin/ConfirmationModal.vue'

// Composables
const platformAdmin = usePlatformAdmin()
const platformMetrics = usePlatformMetrics()
const { showSuccess, showError } = useToast()

// Tab management
type Tab = 'overview' | 'workspaces' | 'invitations' | 'blacklist'
const activeTab = ref<Tab>('overview')

// Search and filter
const searchQuery = ref('')
const invitationFilter = ref<'all' | 'active' | 'expired'>('all')

// Modals
const showInviteModal = ref(false)
const showWorkspaceDetailsModal = ref(false)
const selectedWorkspace = ref<any>(null)

// Confirmation modals
const showSuspendConfirmation = ref(false)
const showReactivateConfirmation = ref(false)
const showDeleteConfirmation = ref(false)
const showRemoveBlacklistConfirmation = ref(false)
const pendingAction = ref<{ type: string; id: string } | null>(null)

// Blacklist management
const showAddBlacklistForm = ref(false)
const blacklistForm = ref({ email: '', reason: '' })
const selectedBlacklistEmail = ref('')

// Initialize - load all data on mount
onMounted(async () => {
  try {
    await Promise.all([
      platformMetrics.fetchMetrics(),
      platformMetrics.fetchActivity(),
      platformAdmin.fetchPendingInvitations(),
      platformAdmin.fetchWorkspaces(),
      platformAdmin.fetchBlacklist(),
    ])
  } catch (err) {
    console.error('Failed to load platform admin data:', err)
    showError('Failed to load platform data. Please refresh the page.')
  }
})

// Computed - Filtered workspaces
const filteredWorkspaces = computed(() => {
  if (!searchQuery.value) return platformAdmin.workspaces.value

  const query = searchQuery.value.toLowerCase()
  return platformAdmin.workspaces.value.filter(
    w =>
      w.name.toLowerCase().includes(query) ||
      w.email.toLowerCase().includes(query) ||
      w.status.toLowerCase().includes(query)
  )
})

// Computed - Filtered invitations
const filteredInvitations = computed(() => {
  const invitations = platformAdmin.pendingInvitations.value

  if (invitationFilter.value === 'all') return invitations

  return invitations.filter(inv => {
    const expirationDate = new Date(inv.invited_at)
    expirationDate.setDate(expirationDate.getDate() + 7)
    const isExpired = expirationDate < new Date()

    if (invitationFilter.value === 'expired') return isExpired
    if (invitationFilter.value === 'active') return !isExpired

    return true
  })
})

// Tab navigation
function switchTab(tab: Tab) {
  activeTab.value = tab
  searchQuery.value = ''
}

// Invitation handlers
async function handleInviteTherapist(data: InviteTherapistRequest) {
  try {
    await platformAdmin.inviteTherapist(data)
    showInviteModal.value = false
    showSuccess('Invitation sent successfully!')
  } catch (err) {
    console.error('Failed to invite therapist:', err)
    // Error already shown via platformAdmin.error
  }
}

async function handleResendInvitation(userId: string) {
  try {
    await platformAdmin.resendInvitation(userId)
    showSuccess('Invitation resent successfully!')
  } catch (err) {
    console.error('Failed to resend invitation:', err)
    // Error already shown via platformAdmin.error
  }
}

// Workspace handlers
function handleViewWorkspaceDetails(workspaceId: string) {
  selectedWorkspace.value = platformAdmin.workspaces.value.find(w => w.id === workspaceId)
  showWorkspaceDetailsModal.value = true
}

function handleSuspendWorkspace(workspaceId: string) {
  pendingAction.value = { type: 'suspend', id: workspaceId }
  showSuspendConfirmation.value = true
}

async function confirmSuspend(reason?: string) {
  if (!pendingAction.value || !reason) return

  try {
    await platformAdmin.suspendWorkspace(pendingAction.value.id, reason)
    showSuspendConfirmation.value = false
    showWorkspaceDetailsModal.value = false
    pendingAction.value = null
    showSuccess('Workspace suspended successfully')
  } catch (err) {
    console.error('Failed to suspend workspace:', err)
    // Error already shown via platformAdmin.error
  }
}

function handleReactivateWorkspace(workspaceId: string) {
  pendingAction.value = { type: 'reactivate', id: workspaceId }
  showReactivateConfirmation.value = true
}

async function confirmReactivate() {
  if (!pendingAction.value) return

  try {
    await platformAdmin.reactivateWorkspace(pendingAction.value.id)
    showReactivateConfirmation.value = false
    pendingAction.value = null
    showSuccess('Workspace reactivated successfully')
  } catch (err) {
    console.error('Failed to reactivate workspace:', err)
    // Error already shown via platformAdmin.error
  }
}

function handleDeleteWorkspace(workspaceId: string) {
  pendingAction.value = { type: 'delete', id: workspaceId }
  showDeleteConfirmation.value = true
}

async function confirmDelete(reason?: string) {
  if (!pendingAction.value || !reason) return

  try {
    await platformAdmin.deleteWorkspace(pendingAction.value.id, reason)
    showDeleteConfirmation.value = false
    showWorkspaceDetailsModal.value = false
    pendingAction.value = null
    showSuccess('Workspace deleted successfully')
  } catch (err) {
    console.error('Failed to delete workspace:', err)
    // Error already shown via platformAdmin.error
  }
}

// Blacklist handlers
async function handleAddToBlacklist() {
  if (!blacklistForm.value.email || !blacklistForm.value.reason) return

  try {
    await platformAdmin.addToBlacklist(blacklistForm.value.email, blacklistForm.value.reason)
    blacklistForm.value = { email: '', reason: '' }
    showAddBlacklistForm.value = false
    showSuccess('Email added to blacklist')
  } catch (err) {
    console.error('Failed to add to blacklist:', err)
    // Error already shown via platformAdmin.error
  }
}

function handleRemoveFromBlacklist(email: string) {
  selectedBlacklistEmail.value = email
  showRemoveBlacklistConfirmation.value = true
}

async function confirmRemoveFromBlacklist() {
  if (!selectedBlacklistEmail.value) return

  try {
    await platformAdmin.removeFromBlacklist(selectedBlacklistEmail.value)
    showRemoveBlacklistConfirmation.value = false
    selectedBlacklistEmail.value = ''
    showSuccess('Email removed from blacklist')
  } catch (err) {
    console.error('Failed to remove from blacklist:', err)
    // Error already shown via platformAdmin.error
  }
}

// Utility functions
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

function openInviteModal() {
  platformAdmin.clearError()
  showInviteModal.value = true
}
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Header -->
    <header class="border-b border-slate-200 bg-white shadow-sm">
      <div class="mx-auto max-w-7xl px-6 py-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-slate-900">PazPaz Platform Admin</h1>
            <p class="mt-1 text-slate-600">
              Manage therapist onboarding and platform health
            </p>
          </div>
          <div v-if="activeTab === 'workspaces'" class="w-64">
            <input
              v-model="searchQuery"
              type="search"
              placeholder="Search workspaces..."
              class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        <!-- Tab Navigation -->
        <nav class="mt-6 flex gap-1" role="tablist">
          <button
            @click="switchTab('overview')"
            :class="[
              'rounded-t-lg px-6 py-3 font-semibold transition',
              activeTab === 'overview'
                ? 'bg-white text-emerald-600 border-b-2 border-emerald-600'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            ]"
            role="tab"
            :aria-selected="activeTab === 'overview'"
          >
            Overview
          </button>
          <button
            @click="switchTab('workspaces')"
            :class="[
              'rounded-t-lg px-6 py-3 font-semibold transition',
              activeTab === 'workspaces'
                ? 'bg-white text-emerald-600 border-b-2 border-emerald-600'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            ]"
            role="tab"
            :aria-selected="activeTab === 'workspaces'"
          >
            Workspaces
          </button>
          <button
            @click="switchTab('invitations')"
            :class="[
              'rounded-t-lg px-6 py-3 font-semibold transition',
              activeTab === 'invitations'
                ? 'bg-white text-emerald-600 border-b-2 border-emerald-600'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            ]"
            role="tab"
            :aria-selected="activeTab === 'invitations'"
          >
            Invitations
            <span
              v-if="platformAdmin.pendingInvitations.value.length"
              class="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700"
            >
              {{ platformAdmin.pendingInvitations.value.length }}
            </span>
          </button>
          <button
            @click="switchTab('blacklist')"
            :class="[
              'rounded-t-lg px-6 py-3 font-semibold transition',
              activeTab === 'blacklist'
                ? 'bg-white text-emerald-600 border-b-2 border-emerald-600'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            ]"
            role="tab"
            :aria-selected="activeTab === 'blacklist'"
          >
            Blacklist
          </button>
        </nav>
      </div>
    </header>

    <!-- Main Content -->
    <main class="mx-auto max-w-7xl px-6 py-8">
      <!-- Error Message (Global) -->
      <div
        v-if="platformAdmin.error.value"
        class="mb-6 rounded-lg border border-red-200 bg-red-50 p-4"
        role="alert"
      >
        <div class="flex items-start">
          <svg
            class="mt-0.5 mr-3 h-5 w-5 text-red-600"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fill-rule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clip-rule="evenodd"
            />
          </svg>
          <div class="flex-1">
            <p class="text-sm font-medium text-red-800">{{ platformAdmin.error.value }}</p>
          </div>
          <button
            @click="platformAdmin.clearError"
            class="text-red-600 hover:text-red-800"
            aria-label="Dismiss error"
          >
            <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>

      <!-- OVERVIEW TAB -->
      <div v-if="activeTab === 'overview'" role="tabpanel">
        <!-- Metrics Grid -->
        <div class="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Total Workspaces"
            :value="platformMetrics.metrics.value.totalWorkspaces"
            icon="workspaces"
            :loading="platformMetrics.loading.value"
          />
          <MetricCard
            title="Active Users"
            :value="platformMetrics.metrics.value.activeUsers"
            icon="users"
            :loading="platformMetrics.loading.value"
          />
          <MetricCard
            title="Pending Invitations"
            :value="platformMetrics.metrics.value.pendingInvitations"
            icon="invitations"
            :loading="platformMetrics.loading.value"
          />
          <MetricCard
            title="Blacklisted Users"
            :value="platformMetrics.metrics.value.blacklistedUsers"
            icon="blacklist"
            :loading="platformMetrics.loading.value"
          />
        </div>

        <!-- Quick Actions -->
        <div class="mb-8">
          <h2 class="mb-4 text-xl font-semibold text-slate-900">Quick Actions</h2>
          <QuickActions
            @invite-therapist="openInviteModal"
            @view-workspaces="switchTab('workspaces')"
            @view-invitations="switchTab('invitations')"
          />
        </div>

        <!-- Activity Timeline -->
        <ActivityTimeline
          :activities="platformMetrics.activity.value"
          :loading="platformMetrics.loading.value"
        />
      </div>

      <!-- WORKSPACES TAB -->
      <div v-if="activeTab === 'workspaces'" role="tabpanel">
        <div class="mb-6 flex items-center justify-between">
          <h2 class="text-xl font-semibold text-slate-900">All Workspaces</h2>
          <button
            @click="openInviteModal"
            class="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            + Invite Therapist
          </button>
        </div>

        <!-- Loading State -->
        <div v-if="platformAdmin.loading.value && !platformAdmin.workspaces.value.length" class="py-12 text-center">
          <div
            class="inline-block h-12 w-12 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"
          ></div>
          <p class="mt-4 text-slate-600">Loading workspaces...</p>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="!platformAdmin.loading.value && filteredWorkspaces.length === 0"
          class="rounded-lg border border-slate-200 bg-white py-12 text-center"
        >
          <svg
            class="mx-auto h-16 w-16 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
            />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-slate-900">No workspaces found</h3>
          <p class="mt-2 text-sm text-slate-600">
            {{ searchQuery ? 'Try a different search term' : 'Get started by inviting your first therapist' }}
          </p>
        </div>

        <!-- Workspaces Grid -->
        <div v-else class="grid grid-cols-1 gap-6">
          <WorkspaceCard
            v-for="workspace in filteredWorkspaces"
            :key="workspace.id"
            :workspace="workspace"
            @view-details="handleViewWorkspaceDetails"
            @suspend="handleSuspendWorkspace"
            @reactivate="handleReactivateWorkspace"
            @resend="handleResendInvitation"
          />
        </div>
      </div>

      <!-- INVITATIONS TAB -->
      <div v-if="activeTab === 'invitations'" role="tabpanel">
        <div class="mb-6 flex items-center justify-between">
          <div class="flex items-center gap-4">
            <h2 class="text-xl font-semibold text-slate-900">Pending Invitations</h2>
            <!-- Filter -->
            <div class="flex gap-2">
              <button
                @click="invitationFilter = 'all'"
                :class="[
                  'rounded-lg px-3 py-1 text-sm font-medium transition',
                  invitationFilter === 'all'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                ]"
              >
                All
              </button>
              <button
                @click="invitationFilter = 'active'"
                :class="[
                  'rounded-lg px-3 py-1 text-sm font-medium transition',
                  invitationFilter === 'active'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                ]"
              >
                Active
              </button>
              <button
                @click="invitationFilter = 'expired'"
                :class="[
                  'rounded-lg px-3 py-1 text-sm font-medium transition',
                  invitationFilter === 'expired'
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                ]"
              >
                Expired
              </button>
            </div>
          </div>
          <button
            @click="openInviteModal"
            class="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            + Invite Therapist
          </button>
        </div>

        <!-- Loading State -->
        <div v-if="platformAdmin.loading.value && !platformAdmin.pendingInvitations.value.length" class="py-12 text-center">
          <div
            class="inline-block h-12 w-12 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"
          ></div>
          <p class="mt-4 text-slate-600">Loading invitations...</p>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="!platformAdmin.loading.value && filteredInvitations.length === 0"
          class="rounded-lg border border-slate-200 bg-white py-12 text-center"
        >
          <svg
            class="mx-auto h-16 w-16 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
            />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-slate-900">
            {{ invitationFilter === 'all' ? 'No pending invitations' : `No ${invitationFilter} invitations` }}
          </h3>
          <p class="mt-2 text-sm text-slate-600">
            {{ invitationFilter === 'all' ? 'Get started by inviting your first therapist' : 'Try a different filter' }}
          </p>
        </div>

        <!-- Invitations List -->
        <div v-else class="space-y-4">
          <div
            v-for="invitation in filteredInvitations"
            :key="invitation.user_id"
            class="rounded-xl border border-slate-200 bg-white p-6 transition hover:shadow-md"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-3">
                  <div
                    class="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-lg font-semibold text-emerald-700"
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

                <div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
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
                    <span v-if="isExpired(invitation.invited_at)" class="ml-1">(Expired)</span>
                  </div>
                </div>
              </div>

              <div class="ml-4">
                <button
                  @click="handleResendInvitation(invitation.user_id)"
                  :disabled="platformAdmin.loading.value"
                  class="rounded-lg border-2 border-emerald-600 px-4 py-2 text-sm font-semibold text-emerald-600 transition hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Resend
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- BLACKLIST TAB -->
      <div v-if="activeTab === 'blacklist'" role="tabpanel">
        <div class="mb-6 flex items-center justify-between">
          <h2 class="text-xl font-semibold text-slate-900">Email Blacklist</h2>
          <button
            v-if="!showAddBlacklistForm"
            @click="showAddBlacklistForm = true"
            class="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            + Add to Blacklist
          </button>
        </div>

        <!-- Add to Blacklist Form -->
        <div v-if="showAddBlacklistForm" class="mb-6 rounded-xl border border-slate-200 bg-white p-6">
          <h3 class="mb-4 text-lg font-semibold text-slate-900">Add Email to Blacklist</h3>
          <div class="space-y-4">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Email</label>
              <input
                v-model="blacklistForm.email"
                type="email"
                placeholder="user@example.com"
                class="w-full rounded-lg border border-slate-300 px-3 py-2 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Reason</label>
              <textarea
                v-model="blacklistForm.reason"
                rows="3"
                placeholder="Why is this email being blacklisted?"
                class="w-full rounded-lg border border-slate-300 px-3 py-2 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div class="flex gap-3">
              <button
                @click="showAddBlacklistForm = false"
                class="rounded-lg border border-slate-300 px-4 py-2 font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
              >
                Cancel
              </button>
              <button
                @click="handleAddToBlacklist"
                :disabled="!blacklistForm.email || !blacklistForm.reason"
                class="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Add to Blacklist
              </button>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div
          v-if="platformAdmin.blacklist.value.length === 0"
          class="rounded-lg border border-slate-200 bg-white py-12 text-center"
        >
          <svg
            class="mx-auto h-16 w-16 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
            />
          </svg>
          <h3 class="mt-4 text-lg font-medium text-slate-900">No blacklisted emails</h3>
          <p class="mt-2 text-sm text-slate-600">
            Blacklisted emails will appear here
          </p>
        </div>

        <!-- Blacklist Table -->
        <div v-else class="rounded-xl border border-slate-200 bg-white overflow-hidden">
          <table class="w-full">
            <thead class="bg-slate-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase text-slate-600">
                  Email
                </th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase text-slate-600">
                  Reason
                </th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase text-slate-600">
                  Added
                </th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase text-slate-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-200">
              <tr v-for="entry in platformAdmin.blacklist.value" :key="entry.email" class="hover:bg-slate-50">
                <td class="px-6 py-4 text-sm text-slate-900">{{ entry.email }}</td>
                <td class="px-6 py-4 text-sm text-slate-600">{{ entry.reason }}</td>
                <td class="px-6 py-4 text-sm text-slate-600">{{ formatDate(entry.addedAt) }}</td>
                <td class="px-6 py-4 text-right">
                  <button
                    @click="handleRemoveFromBlacklist(entry.email)"
                    class="rounded-lg border border-red-600 px-3 py-1 text-sm font-medium text-red-600 transition hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>

    <!-- Modals -->
    <CreateWorkspaceModal
      v-if="showInviteModal"
      :error="platformAdmin.error.value"
      :isLoading="platformAdmin.loading.value"
      @close="showInviteModal = false"
      @submit="handleInviteTherapist"
    />

    <WorkspaceDetailsModal
      :visible="showWorkspaceDetailsModal"
      :workspace="selectedWorkspace"
      @close="showWorkspaceDetailsModal = false"
      @suspend="handleSuspendWorkspace"
      @delete="handleDeleteWorkspace"
    />

    <ConfirmationModal
      :visible="showSuspendConfirmation"
      title="Suspend Workspace"
      message="Are you sure you want to suspend this workspace? Users will not be able to access their data until reactivated."
      confirmText="Suspend"
      confirmStyle="danger"
      :showReasonField="true"
      reasonLabel="Reason for suspension"
      reasonPlaceholder="Explain why this workspace is being suspended..."
      :reasonRequired="true"
      @confirm="confirmSuspend"
      @cancel="showSuspendConfirmation = false; pendingAction = null"
    />

    <ConfirmationModal
      :visible="showReactivateConfirmation"
      title="Reactivate Workspace"
      message="Are you sure you want to reactivate this workspace? Users will regain access to their data."
      confirmText="Reactivate"
      confirmStyle="primary"
      @confirm="confirmReactivate"
      @cancel="showReactivateConfirmation = false; pendingAction = null"
    />

    <ConfirmationModal
      :visible="showDeleteConfirmation"
      title="Delete Workspace"
      message="This will permanently delete the workspace and all associated data. This action cannot be undone."
      confirmText="Delete Forever"
      confirmStyle="danger"
      :showReasonField="true"
      reasonLabel="Reason for deletion"
      reasonPlaceholder="Explain why this workspace is being deleted..."
      :reasonRequired="true"
      @confirm="confirmDelete"
      @cancel="showDeleteConfirmation = false; pendingAction = null"
    />

    <ConfirmationModal
      :visible="showRemoveBlacklistConfirmation"
      title="Remove from Blacklist"
      message="Are you sure you want to remove this email from the blacklist? They will be able to register again."
      confirmText="Remove"
      confirmStyle="primary"
      @confirm="confirmRemoveFromBlacklist"
      @cancel="showRemoveBlacklistConfirmation = false; selectedBlacklistEmail = ''"
    />
  </div>
</template>

<style scoped>
@media (prefers-reduced-motion: reduce) {
  .transition,
  .animate-spin {
    animation: none !important;
    transition: none !important;
  }
}
</style>
