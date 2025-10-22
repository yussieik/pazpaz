<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import type { Workspace } from './WorkspaceCard.vue'

interface Props {
  visible: boolean
  workspace: Workspace | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  suspend: [workspaceId: string]
  delete: [workspaceId: string]
}>()

const modalRef = ref<HTMLDivElement | null>(null)

watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    setTimeout(() => {
      modalRef.value?.querySelector<HTMLElement>('button')?.focus()
    }, 0)
  }
})

onMounted(() => {
  document.addEventListener('keydown', handleEscapeKey)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscapeKey)
})

function handleEscapeKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    emit('close')
  }
}

function handleSuspend() {
  if (props.workspace) {
    emit('suspend', props.workspace.id)
  }
}

function handleDelete() {
  if (props.workspace) {
    emit('delete', props.workspace.id)
  }
}
</script>

<template>
  <Transition name="modal">
    <div
      v-if="visible && workspace"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      @click.self="$emit('close')"
      role="dialog"
      aria-modal="true"
      aria-labelledby="workspace-details-title"
    >
      <div ref="modalRef" class="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl">
        <!-- Header -->
        <div class="mb-6 flex items-start justify-between">
          <div>
            <h2 id="workspace-details-title" class="text-2xl font-bold text-slate-900">
              {{ workspace.name }}
            </h2>
            <p class="mt-1 text-sm text-slate-600">{{ workspace.email }}</p>
          </div>
          <button
            @click="$emit('close')"
            class="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            aria-label="Close modal"
          >
            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Stats Grid -->
        <div class="mb-6 grid grid-cols-3 gap-4">
          <div class="rounded-lg border border-slate-200 p-4">
            <p class="text-sm text-slate-600">Total Users</p>
            <p class="mt-1 text-2xl font-bold text-slate-900">{{ workspace.userCount }}</p>
          </div>
          <div class="rounded-lg border border-slate-200 p-4">
            <p class="text-sm text-slate-600">Active Users</p>
            <p class="mt-1 text-2xl font-bold text-emerald-600">{{ workspace.activeUsers }}</p>
          </div>
          <div class="rounded-lg border border-slate-200 p-4">
            <p class="text-sm text-slate-600">Appointments</p>
            <p class="mt-1 text-2xl font-bold text-slate-900">{{ workspace.appointmentCount }}</p>
          </div>
        </div>

        <!-- Danger Zone -->
        <div class="rounded-lg border-2 border-red-200 bg-red-50 p-4">
          <h3 class="text-lg font-semibold text-red-900">Danger Zone</h3>
          <p class="mt-2 text-sm text-red-700">
            These actions are permanent and cannot be undone.
          </p>

          <div class="mt-4 flex gap-3">
            <button
              v-if="workspace.status === 'active'"
              @click="handleSuspend"
              class="rounded-lg border-2 border-red-600 bg-white px-4 py-2 font-medium text-red-600 transition hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
            >
              Suspend Workspace
            </button>
            <button
              @click="handleDelete"
              class="rounded-lg bg-red-600 px-4 py-2 font-semibold text-white transition hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
            >
              Delete Workspace
            </button>
          </div>
        </div>

        <!-- Close Button -->
        <div class="mt-6 flex justify-end">
          <button
            @click="$emit('close')"
            class="rounded-lg border border-slate-300 px-6 py-2 font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .modal-enter-active,
  .modal-leave-active {
    transition: none !important;
  }
}
</style>
