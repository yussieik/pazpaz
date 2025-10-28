<script setup lang="ts">
import { ref, nextTick } from 'vue'
import type { ClientCreate } from '@/types/client'

interface Emits {
  (e: 'submit', data: ClientCreate): void
  (e: 'cancel'): void
}

const emit = defineEmits<Emits>()

// Form state
const formData = ref<ClientCreate>({
  first_name: '',
  last_name: '',
  phone: '',
})

// Validation errors
const errors = ref<Record<string, string>>({})

// Refs for focus management
const firstNameInput = ref<HTMLInputElement>()

/**
 * Focus the first input when component is mounted
 */
defineExpose({
  focus: () => {
    nextTick(() => {
      firstNameInput.value?.focus()
    })
  },
})

/**
 * Validate form data
 */
function validate(): boolean {
  errors.value = {}

  if (!formData.value.first_name.trim()) {
    errors.value.first_name = 'First name is required'
  }

  if (!formData.value.last_name.trim()) {
    errors.value.last_name = 'Last name is required'
  }

  return Object.keys(errors.value).length === 0
}

/**
 * Handle form submission
 */
function handleSubmit() {
  if (!validate()) return

  emit('submit', {
    first_name: formData.value.first_name.trim(),
    last_name: formData.value.last_name.trim(),
    phone: formData.value.phone?.trim() || null,
  })

  // Reset form
  formData.value = {
    first_name: '',
    last_name: '',
    phone: '',
  }
  errors.value = {}
}

/**
 * Handle cancel action
 */
function handleCancel() {
  emit('cancel')
  formData.value = {
    first_name: '',
    last_name: '',
    phone: '',
  }
  errors.value = {}
}

/**
 * Handle Enter key on inputs (submit form)
 */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    handleSubmit()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    handleCancel()
  }
}
</script>

<template>
  <div class="border-t border-slate-200 bg-slate-50 p-4">
    <div class="mb-3 flex items-center gap-2">
      <svg
        class="h-5 w-5 text-emerald-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 4v16m8-8H4"
        />
      </svg>
      <h3 class="text-sm font-semibold text-slate-900">Add New Client</h3>
    </div>

    <form @submit.prevent="handleSubmit" class="space-y-3">
      <!-- First Name -->
      <div>
        <label for="quick-add-first-name" class="sr-only">First Name</label>
        <input
          id="quick-add-first-name"
          ref="firstNameInput"
          v-model="formData.first_name"
          v-rtl
          type="text"
          placeholder="First Name *"
          autocomplete="given-name"
          @keydown="handleKeydown"
          :class="[
            'block w-full rounded-lg border px-3 py-2 text-sm placeholder-slate-400 transition-colors',
            'focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none',
            errors.first_name ? 'border-red-500' : 'border-slate-300',
          ]"
          aria-required="true"
          :aria-invalid="!!errors.first_name"
        />
        <p v-if="errors.first_name" class="mt-1 text-xs text-red-600" role="alert">
          {{ errors.first_name }}
        </p>
      </div>

      <!-- Last Name -->
      <div>
        <label for="quick-add-last-name" class="sr-only">Last Name</label>
        <input
          id="quick-add-last-name"
          v-model="formData.last_name"
          v-rtl
          type="text"
          placeholder="Last Name *"
          autocomplete="family-name"
          @keydown="handleKeydown"
          :class="[
            'block w-full rounded-lg border px-3 py-2 text-sm placeholder-slate-400 transition-colors',
            'focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none',
            errors.last_name ? 'border-red-500' : 'border-slate-300',
          ]"
          aria-required="true"
          :aria-invalid="!!errors.last_name"
        />
        <p v-if="errors.last_name" class="mt-1 text-xs text-red-600" role="alert">
          {{ errors.last_name }}
        </p>
      </div>

      <!-- Phone (Optional) -->
      <div>
        <label for="quick-add-phone" class="sr-only">Phone (optional)</label>
        <input
          id="quick-add-phone"
          v-model="formData.phone"
          type="tel"
          placeholder="Phone (for reminders, optional)"
          autocomplete="tel"
          @keydown="handleKeydown"
          class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm placeholder-slate-400 transition-colors focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
        />
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center gap-2">
        <button
          type="submit"
          class="flex-1 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
        >
          Add Client
        </button>
        <button
          type="button"
          @click="handleCancel"
          class="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2"
        >
          Cancel
        </button>
      </div>
    </form>

    <p class="mt-2 text-xs text-slate-500">Press Enter to add, Escape to cancel</p>
  </div>
</template>
