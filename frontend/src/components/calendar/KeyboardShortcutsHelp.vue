<script setup lang="ts">
interface Props {
  visible: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
}

defineProps<Props>()
const emit = defineEmits<Emits>()

function closeModal() {
  emit('update:visible', false)
}
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
        v-if="visible"
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
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-modal-title"
      >
        <div
          class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-xl"
          @click.stop
        >
          <!-- Header -->
          <div
            class="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4"
          >
            <h2 id="shortcuts-modal-title" class="text-xl font-semibold text-slate-900">
              Keyboard Shortcuts
            </h2>
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

          <!-- Body -->
          <div class="space-y-6 px-6 py-6">
            <!-- Navigation Section -->
            <div>
              <h3
                class="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase"
              >
                Navigation
              </h3>
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Go to today</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >T</kbd
                  >
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Previous period</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >←</kbd
                  >
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Next period</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >→</kbd
                  >
                </div>
              </div>
            </div>

            <!-- Views Section -->
            <div>
              <h3
                class="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase"
              >
                Calendar Views
              </h3>
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Week view</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >W</kbd
                  >
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Day view</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >D</kbd
                  >
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Month view</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >M</kbd
                  >
                </div>
              </div>
            </div>

            <!-- Actions Section -->
            <div>
              <h3
                class="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase"
              >
                Actions
              </h3>
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">New appointment</span>
                  <div class="flex items-center gap-1">
                    <kbd
                      class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                      >⌘</kbd
                    >
                    <span class="text-slate-400">+</span>
                    <kbd
                      class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                      >N</kbd
                    >
                  </div>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Close modal</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >Esc</kbd
                  >
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-slate-700">Show shortcuts</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                    >?</kbd
                  >
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div
            class="border-t border-slate-200 bg-slate-50 px-6 py-4 text-center text-sm text-slate-600"
          >
            Press
            <kbd class="rounded bg-white px-2 py-1 text-sm font-medium text-slate-900"
              >Esc</kbd
            >
            to close
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
