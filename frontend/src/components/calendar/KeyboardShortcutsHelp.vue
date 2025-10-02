<script setup lang="ts">
import { computed } from 'vue'
import { KEYBOARD_SHORTCUTS, type ShortcutConfig } from '@/config/keyboardShortcuts'

interface Props {
  visible: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
}

defineProps<Props>()
const emit = defineEmits<Emits>()

// Group shortcuts by category
const navigationShortcuts = computed<ShortcutConfig[]>(() =>
  KEYBOARD_SHORTCUTS.filter((s) => s.category === 'navigation')
)

const calendarShortcuts = computed<ShortcutConfig[]>(() =>
  KEYBOARD_SHORTCUTS.filter((s) => s.category === 'calendar')
)

const clientShortcuts = computed<ShortcutConfig[]>(() =>
  KEYBOARD_SHORTCUTS.filter((s) => s.category === 'client')
)

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
            <div v-if="navigationShortcuts.length > 0">
              <h3
                class="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase"
              >
                Navigation
              </h3>
              <div class="space-y-2">
                <div
                  v-for="shortcut in navigationShortcuts"
                  :key="shortcut.keys"
                  class="flex items-center justify-between"
                >
                  <span class="text-slate-700">{{ shortcut.description }}</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                  >
                    {{ shortcut.keys }}
                  </kbd>
                </div>
              </div>
            </div>

            <!-- Calendar Section -->
            <div v-if="calendarShortcuts.length > 0">
              <h3
                class="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase"
              >
                Calendar
              </h3>
              <div class="space-y-2">
                <div
                  v-for="shortcut in calendarShortcuts"
                  :key="shortcut.keys"
                  class="flex items-center justify-between"
                >
                  <span class="text-slate-700">{{ shortcut.description }}</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                  >
                    {{ shortcut.keys }}
                  </kbd>
                </div>
              </div>
            </div>

            <!-- Client Section -->
            <div v-if="clientShortcuts.length > 0">
              <h3
                class="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase"
              >
                Client Detail
              </h3>
              <div class="space-y-2">
                <div
                  v-for="shortcut in clientShortcuts"
                  :key="shortcut.keys"
                  class="flex items-center justify-between"
                >
                  <span class="text-slate-700">{{ shortcut.description }}</span>
                  <kbd
                    class="rounded bg-slate-100 px-2 py-1 text-sm font-medium text-slate-900"
                  >
                    {{ shortcut.keys }}
                  </kbd>
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
