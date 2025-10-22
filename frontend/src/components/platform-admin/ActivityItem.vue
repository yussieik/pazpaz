<script setup lang="ts">
export interface Activity {
  id: string
  type:
    | 'invitation-accepted'
    | 'invitation-sent'
    | 'invitation-expired'
    | 'workspace-created'
    | 'workspace-suspended'
    | 'workspace-reactivated'
    | 'workspace-deleted'
    | 'user-blacklisted'
    | 'user-unblacklisted'
    | string // Allow other types from backend
  timestamp: string
  description: string
  metadata?: Record<string, unknown>
}

interface Props {
  activity: Activity
}

defineProps<Props>()

const iconColors: Record<string, string> = {
  'invitation-accepted': 'bg-emerald-100 text-emerald-600',
  'invitation-sent': 'bg-blue-100 text-blue-600',
  'invitation-expired': 'bg-amber-100 text-amber-600',
  'workspace-created': 'bg-purple-100 text-purple-600',
  'workspace-suspended': 'bg-red-100 text-red-600',
  'workspace-reactivated': 'bg-emerald-100 text-emerald-600',
  'workspace-deleted': 'bg-red-100 text-red-600',
  'user-blacklisted': 'bg-red-100 text-red-600',
  'user-unblacklisted': 'bg-emerald-100 text-emerald-600',
}

const iconPaths: Record<string, string> = {
  'invitation-accepted': 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  'invitation-sent':
    'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  'invitation-expired': 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  'workspace-created': 'M12 4v16m8-8H4',
  'workspace-suspended':
    'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
  'workspace-reactivated': 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  'workspace-deleted':
    'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16',
  'user-blacklisted':
    'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
  'user-unblacklisted': 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
}

// Get color with fallback
function getColor(type: string): string {
  return iconColors[type] || 'bg-slate-100 text-slate-600'
}

// Get icon path with fallback
function getIconPath(type: string): string {
  return iconPaths[type] || 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
}
</script>

<template>
  <div class="flex gap-3">
    <!-- Icon -->
    <div
      :class="[
        getColor(activity.type),
        'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full',
      ]"
      aria-hidden="true"
    >
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          :d="getIconPath(activity.type)"
        />
      </svg>
    </div>

    <!-- Content -->
    <div class="flex-1 pt-0.5">
      <p class="text-sm text-slate-700">{{ activity.description }}</p>
      <p class="mt-0.5 text-xs text-slate-500">{{ activity.timestamp }}</p>
    </div>
  </div>
</template>
