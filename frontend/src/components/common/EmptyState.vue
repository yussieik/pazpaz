<script setup lang="ts">
/**
 * EmptyState Component
 *
 * Reusable empty state component with icon, title, description, and optional action.
 *
 * Features:
 * - Heroicons SVG icon support
 * - Clear messaging with title and description
 * - Optional call-to-action button
 * - Accessible and responsive
 *
 * Usage:
 *   <EmptyState
 *     icon="document"
 *     title="No attachments yet"
 *     description="Upload photos or documents to this session"
 *     action-label="Upload File"
 *     @action="handleUpload"
 *   />
 */

interface Props {
  icon?: 'document' | 'photo' | 'folder' | 'calendar' | 'user' | 'clipboard' | 'search'
  title: string
  description?: string
  actionLabel?: string
  actionVariant?: 'primary' | 'secondary'
}

withDefaults(defineProps<Props>(), {
  icon: 'document',
  actionVariant: 'primary',
})

interface Emits {
  (e: 'action'): void
}

const emit = defineEmits<Emits>()

function handleAction() {
  emit('action')
}
</script>

<template>
  <div class="empty-state text-center py-12">
    <!-- Icon -->
    <div class="mx-auto h-12 w-12 text-slate-400" aria-hidden="true">
      <!-- Document Icon -->
      <svg
        v-if="icon === 'document'"
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

      <!-- Photo Icon -->
      <svg v-else-if="icon === 'photo'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
        />
      </svg>

      <!-- Folder Icon -->
      <svg v-else-if="icon === 'folder'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
        />
      </svg>

      <!-- Calendar Icon -->
      <svg
        v-else-if="icon === 'calendar'"
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

      <!-- User Icon -->
      <svg v-else-if="icon === 'user'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
        />
      </svg>

      <!-- Clipboard Icon -->
      <svg
        v-else-if="icon === 'clipboard'"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
        />
      </svg>

      <!-- Search Icon -->
      <svg v-else-if="icon === 'search'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
    </div>

    <!-- Title -->
    <h3 class="mt-4 text-sm font-medium text-slate-900">{{ title }}</h3>

    <!-- Description -->
    <p v-if="description" class="mt-2 text-sm text-slate-600 max-w-md mx-auto">
      {{ description }}
    </p>

    <!-- Action Button -->
    <div v-if="actionLabel" class="mt-6">
      <button
        @click="handleAction"
        :class="[
          'inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
          actionVariant === 'primary'
            ? 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-600'
            : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-slate-500',
        ]"
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
            d="M12 4v16m8-8H4"
          />
        </svg>
        <span>{{ actionLabel }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  /* Ensure minimum height to prevent layout shift */
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
</style>
