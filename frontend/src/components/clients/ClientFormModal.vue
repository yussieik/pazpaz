<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from '@/composables/useI18n'
import type { ClientCreate, Client } from '@/types/client'
import IconClose from '@/components/icons/IconClose.vue'

const { t } = useI18n()

interface Props {
  visible: boolean
  mode: 'create' | 'edit'
  client?: Client | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'submit', data: ClientCreate): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Form state
const formData = ref<ClientCreate>({
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  date_of_birth: '',
  address: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  medical_history: '',
  notes: '',
  google_calendar_consent: true, // Default to true (opt-out model)
})

// UI state
const isAdditionalDetailsExpanded = ref(false)
const isSubmitting = ref(false)

// Template refs for auto-focus
const firstNameInputRef = ref<HTMLInputElement>()
const dateOfBirthInputRef = ref<HTMLInputElement>()

// Validation
const errors = ref<Record<string, string>>({})

// Platform detection for keyboard shortcuts
const isMac = computed(() => navigator.userAgent.toUpperCase().indexOf('MAC') >= 0)
const modifierKey = computed(() => (isMac.value ? '⌘' : 'Ctrl'))

// Computed properties
const modalTitle = computed(() =>
  props.mode === 'create' ? t('clients.formModal.createTitle') : t('clients.formModal.editTitle')
)

const submitButtonText = computed(() =>
  props.mode === 'create' ? t('clients.formModal.addButton') : t('clients.formModal.saveButton')
)

// Check if email is provided for calendar consent
const hasEmail = computed(() => {
  return (formData.value.email?.trim().length ?? 0) > 0
})

// Date formatting helper
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString()
}

// Watch for modal visibility and pre-fill data in edit mode
watch(
  () => [props.visible, props.mode, props.client] as const,
  ([isVisible, mode, client]) => {
    if (!isVisible) {
      resetForm()
      return
    }

    if (mode === 'edit' && client && typeof client === 'object') {
      // Pre-fill all fields from client
      formData.value = {
        first_name: client.first_name,
        last_name: client.last_name,
        phone: client.phone || '',
        email: client.email || '',
        date_of_birth: client.date_of_birth || '',
        address: client.address || '',
        emergency_contact_name: client.emergency_contact_name || '',
        emergency_contact_phone: client.emergency_contact_phone || '',
        medical_history: client.medical_history || '',
        notes: client.notes || '',
        google_calendar_consent: client.google_calendar_consent ?? null,
      }

      // Auto-expand "Add More Details" if client has optional data
      const hasOptionalData = Boolean(
        client.date_of_birth ||
          client.address ||
          client.emergency_contact_name ||
          client.emergency_contact_phone ||
          client.medical_history ||
          client.notes
      )
      isAdditionalDetailsExpanded.value = hasOptionalData

      // Auto-focus first name field
      nextTick(() => {
        firstNameInputRef.value?.focus()
      })
    } else if (mode === 'create') {
      // Reset form for create mode
      resetForm()
      // Auto-focus first name field on modal open
      nextTick(() => {
        firstNameInputRef.value?.focus()
      })
    }
  },
  { deep: true }
)

// Watch email changes to auto-disable consent if email is removed
watch(
  () => formData.value.email,
  (newEmail) => {
    // If email is removed, disable calendar consent
    if (!newEmail?.trim() && formData.value.google_calendar_consent) {
      formData.value.google_calendar_consent = false
    }
    // If email is added back and consent was disabled, re-enable it (opt-out model)
    if (newEmail?.trim() && !formData.value.google_calendar_consent) {
      formData.value.google_calendar_consent = true
    }
  }
)

function resetForm() {
  formData.value = {
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    date_of_birth: '',
    address: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    medical_history: '',
    notes: '',
    google_calendar_consent: true, // Default to true for new clients (opt-out model)
  }
  errors.value = {}
  isAdditionalDetailsExpanded.value = false
  isSubmitting.value = false
}

function validate(): boolean {
  errors.value = {}

  // Only first name and last name are required
  if (!formData.value.first_name?.trim()) {
    errors.value.first_name = t('clients.formModal.fields.firstName.required')
  }
  if (!formData.value.last_name?.trim()) {
    errors.value.last_name = t('clients.formModal.fields.lastName.required')
  }

  // Email format validation (only if provided)
  const hasEmail = formData.value.email?.trim()
  if (hasEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.value.email || '')) {
    errors.value.email = t('clients.formModal.fields.email.invalid')
  }

  return Object.keys(errors.value).length === 0
}

function handleBlur(field: 'first_name' | 'last_name') {
  // Real-time validation on blur
  if (field === 'first_name' && !formData.value.first_name?.trim()) {
    errors.value.first_name = t('clients.formModal.fields.firstName.required')
  } else if (field === 'first_name') {
    delete errors.value.first_name
  }

  if (field === 'last_name' && !formData.value.last_name?.trim()) {
    errors.value.last_name = t('clients.formModal.fields.lastName.required')
  } else if (field === 'last_name') {
    delete errors.value.last_name
  }
}

function handleSubmit() {
  if (!validate()) {
    // Focus first error field
    if (errors.value.first_name) {
      firstNameInputRef.value?.focus()
    }
    return
  }

  isSubmitting.value = true

  // Clean up form data: remove empty optional fields
  const cleanedData: ClientCreate = {
    first_name: formData.value.first_name.trim(),
    last_name: formData.value.last_name.trim(),
    phone: formData.value.phone?.trim() || null,
    email: formData.value.email?.trim() || null,
    date_of_birth: formData.value.date_of_birth?.trim() || null,
    address: formData.value.address?.trim() || null,
    emergency_contact_name: formData.value.emergency_contact_name?.trim() || null,
    emergency_contact_phone: formData.value.emergency_contact_phone?.trim() || null,
    medical_history: formData.value.medical_history?.trim() || null,
    notes: formData.value.notes?.trim() || null,
    google_calendar_consent: formData.value.google_calendar_consent,
  }

  emit('submit', cleanedData)
  // Note: Parent component (ClientsView) handles closing the modal
  // This prevents race conditions and allows parent to show errors if needed
}

function closeModal() {
  emit('update:visible', false)
}

function toggleAdditionalDetails() {
  isAdditionalDetailsExpanded.value = !isAdditionalDetailsExpanded.value

  // Focus first additional field when expanding
  if (isAdditionalDetailsExpanded.value) {
    nextTick(() => {
      dateOfBirthInputRef.value?.focus()
    })
  }
}

function handleKeydown(e: KeyboardEvent) {
  // Check for ⌘Enter (macOS) or Ctrl+Enter (Windows/Linux) to submit form
  const isSubmitShortcut = (e.metaKey || e.ctrlKey) && e.key === 'Enter'

  if (isSubmitShortcut && props.visible) {
    e.preventDefault()
    handleSubmit()
    return
  }

  // Escape to close modal
  if (e.key === 'Escape' && props.visible) {
    e.preventDefault()
    closeModal()
  }
}

// Mount global keyboard handler for modal
onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
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
        :aria-labelledby="`client-form-modal-title`"
      >
        <div
          class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-xl"
          @click.stop
        >
          <!-- Header -->
          <div
            class="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 sm:px-6"
          >
            <h2
              id="client-form-modal-title"
              class="text-lg font-semibold text-slate-900 sm:text-xl"
            >
              {{ modalTitle }}
            </h2>
            <button
              @click="closeModal"
              class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 sm:min-h-0 sm:min-w-0 sm:p-2"
              :aria-label="t('clients.formModal.closeDialogAriaLabel')"
            >
              <IconClose class="h-6 w-6 sm:h-5 sm:w-5" />
            </button>
          </div>

          <!-- Form -->
          <form
            @submit.prevent="handleSubmit"
            class="space-y-6 px-5 pt-6 pb-6 sm:space-y-6 sm:px-6"
          >
            <!-- Phase 1: Essential Fields (Always Visible) -->
            <div class="space-y-6">
              <!-- First Name -->
              <div>
                <label
                  for="first-name"
                  class="mb-1.5 block text-sm font-medium text-slate-900"
                >
                  {{ t('clients.formModal.fields.firstName.label') }}
                  <span class="ms-0.5 text-red-500" aria-label="required">*</span>
                </label>
                <input
                  id="first-name"
                  ref="firstNameInputRef"
                  v-model="formData.first_name"
                  v-rtl
                  type="text"
                  autocomplete="given-name"
                  aria-required="true"
                  :aria-invalid="!!errors.first_name"
                  :aria-describedby="errors.first_name ? 'first-name-error' : undefined"
                  @blur="handleBlur('first_name')"
                  :class="[
                    'mt-1 block min-h-[44px] w-full rounded-lg border px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:ring-2 focus:outline-none sm:text-sm',
                    errors.first_name
                      ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                      : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-500',
                  ]"
                />
                <span
                  v-if="errors.first_name"
                  id="first-name-error"
                  role="alert"
                  class="mt-1 block text-sm text-red-600"
                >
                  {{ errors.first_name }}
                </span>
              </div>

              <!-- Last Name -->
              <div>
                <label
                  for="last-name"
                  class="mb-1.5 block text-sm font-medium text-slate-900"
                >
                  {{ t('clients.formModal.fields.lastName.label') }}
                  <span class="ms-0.5 text-red-500" aria-label="required">*</span>
                </label>
                <input
                  id="last-name"
                  v-model="formData.last_name"
                  v-rtl
                  type="text"
                  autocomplete="family-name"
                  aria-required="true"
                  :aria-invalid="!!errors.last_name"
                  :aria-describedby="errors.last_name ? 'last-name-error' : undefined"
                  @blur="handleBlur('last_name')"
                  :class="[
                    'mt-1 block min-h-[44px] w-full rounded-lg border px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:ring-2 focus:outline-none sm:text-sm',
                    errors.last_name
                      ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                      : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-500',
                  ]"
                />
                <span
                  v-if="errors.last_name"
                  id="last-name-error"
                  role="alert"
                  class="mt-1 block text-sm text-red-600"
                >
                  {{ errors.last_name }}
                </span>
              </div>

              <!-- Phone (optional) -->
              <div>
                <label
                  for="phone"
                  class="mb-1.5 block text-sm font-medium text-slate-900"
                >
                  {{ t('clients.formModal.fields.phone.label') }}
                </label>
                <input
                  id="phone"
                  v-model="formData.phone"
                  type="tel"
                  autocomplete="tel"
                  :placeholder="t('clients.formModal.fields.phone.placeholder')"
                  aria-required="false"
                  class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
                />
              </div>

              <!-- Email (optional) -->
              <div>
                <label
                  for="email"
                  class="mb-1.5 block text-sm font-medium text-slate-900"
                >
                  {{ t('clients.formModal.fields.email.label') }}
                </label>
                <input
                  id="email"
                  v-model="formData.email"
                  type="email"
                  autocomplete="email"
                  :placeholder="t('clients.formModal.fields.email.placeholder')"
                  aria-required="false"
                  :aria-invalid="!!errors.email"
                  :aria-describedby="errors.email ? 'email-error' : undefined"
                  :class="[
                    'mt-1 block min-h-[44px] w-full rounded-lg border px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:ring-2 focus:outline-none sm:text-sm',
                    errors.email
                      ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                      : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-500',
                  ]"
                />
                <span
                  v-if="errors.email"
                  id="email-error"
                  role="alert"
                  class="mt-1 block text-sm text-red-600"
                >
                  {{ errors.email }}
                </span>
              </div>

              <!-- Google Calendar Consent (only shown if email exists) -->
              <div v-if="hasEmail" class="flex items-start gap-3">
                <input
                  id="google-calendar-consent"
                  v-model="formData.google_calendar_consent"
                  type="checkbox"
                  class="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                />
                <div class="flex-1">
                  <label
                    for="google-calendar-consent"
                    class="cursor-pointer text-sm font-medium text-slate-700"
                  >
                    {{ t('clients.formModal.fields.calendarConsent.label') }}
                  </label>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ t('clients.formModal.fields.calendarConsent.description') }}
                  </p>
                  <p
                    v-if="
                      props.mode === 'edit' &&
                      props.client?.google_calendar_consent_date
                    "
                    class="mt-1 text-xs text-slate-400"
                  >
                    {{ t('clients.formModal.fields.calendarConsent.consentGrantedLabel') }}
                    {{ formatDate(props.client.google_calendar_consent_date) }}
                  </p>
                </div>
              </div>

              <!-- Warning if no email -->
              <div
                v-if="!hasEmail && formData.google_calendar_consent"
                class="rounded-md border border-amber-200 bg-amber-50 p-3"
              >
                <p class="flex items-center gap-2 text-xs text-amber-700">
                  <svg
                    class="h-4 w-4 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <span>{{ t('clients.formModal.fields.calendarConsent.emailRequiredWarning') }}</span>
                </p>
              </div>
            </div>

            <!-- "Add More Details" Button -->
            <button
              type="button"
              @click="toggleAdditionalDetails"
              :aria-expanded="isAdditionalDetailsExpanded"
              aria-controls="additional-details"
              class="flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            >
              <span>
                {{ isAdditionalDetailsExpanded ? t('clients.formModal.fields.toggleDetails.hide') : t('clients.formModal.fields.toggleDetails.addMore') }}
                <span class="text-slate-500">{{ t('clients.formModal.fields.toggleDetails.optional') }}</span>
              </span>
              <svg
                :class="[
                  'h-5 w-5 text-slate-400 transition-transform',
                  isAdditionalDetailsExpanded ? 'rotate-180' : '',
                ]"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            <!-- Phase 2: Additional Details (Collapsible) -->
            <Transition
              enter-active-class="transition-all duration-200 ease-out"
              leave-active-class="transition-all duration-200 ease-in"
              enter-from-class="opacity-0 max-h-0"
              enter-to-class="opacity-100 max-h-[2000px]"
              leave-from-class="opacity-100 max-h-[2000px]"
              leave-to-class="opacity-0 max-h-0"
            >
              <div
                v-if="isAdditionalDetailsExpanded"
                id="additional-details"
                :aria-hidden="!isAdditionalDetailsExpanded"
                class="space-y-6 overflow-hidden"
              >
                <!-- Date of Birth -->
                <div>
                  <label
                    for="date-of-birth"
                    class="mb-1.5 block text-sm font-medium text-slate-900"
                  >
                    {{ t('clients.formModal.fields.dateOfBirth.label') }}
                  </label>
                  <input
                    id="date-of-birth"
                    ref="dateOfBirthInputRef"
                    v-model="formData.date_of_birth"
                    type="date"
                    class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
                  />
                </div>

                <!-- Address -->
                <div>
                  <label
                    for="address"
                    class="mb-1.5 block text-sm font-medium text-slate-900"
                  >
                    {{ t('clients.formModal.fields.address.label') }}
                  </label>
                  <input
                    id="address"
                    v-model="formData.address"
                    v-rtl
                    type="text"
                    autocomplete="street-address"
                    :placeholder="t('clients.formModal.fields.address.placeholder')"
                    class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
                  />
                </div>

                <!-- Emergency Contact Name -->
                <div>
                  <label
                    for="emergency-contact-name"
                    class="mb-1.5 block text-sm font-medium text-slate-900"
                  >
                    {{ t('clients.formModal.fields.emergencyContactName.label') }}
                  </label>
                  <input
                    id="emergency-contact-name"
                    v-model="formData.emergency_contact_name"
                    v-rtl
                    type="text"
                    :placeholder="t('clients.formModal.fields.emergencyContactName.placeholder')"
                    class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
                  />
                </div>

                <!-- Emergency Contact Phone -->
                <div>
                  <label
                    for="emergency-contact-phone"
                    class="mb-1.5 block text-sm font-medium text-slate-900"
                  >
                    {{ t('clients.formModal.fields.emergencyContactPhone.label') }}
                  </label>
                  <input
                    id="emergency-contact-phone"
                    v-model="formData.emergency_contact_phone"
                    type="tel"
                    :placeholder="t('clients.formModal.fields.emergencyContactPhone.placeholder')"
                    class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
                  />
                </div>

                <!-- Medical History -->
                <div>
                  <label
                    for="medical-history"
                    class="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-slate-900"
                  >
                    <span>{{ t('clients.formModal.fields.medicalHistory.label') }}</span>
                    <span
                      class="text-xs text-slate-500"
                      aria-label="Encrypted and private"
                      >{{ t('clients.formModal.fields.medicalHistory.encryptedNote') }}</span
                    >
                  </label>
                  <textarea
                    id="medical-history"
                    v-model="formData.medical_history"
                    v-rtl
                    rows="4"
                    :placeholder="t('clients.formModal.fields.medicalHistory.placeholder')"
                    class="mt-1 block min-h-[100px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
                  ></textarea>
                </div>

                <!-- Intake Notes -->
                <div>
                  <label
                    for="notes"
                    class="mb-1.5 block text-sm font-medium text-slate-900"
                  >
                    {{ t('clients.formModal.fields.intakeNotes.label') }}
                  </label>
                  <textarea
                    id="notes"
                    v-model="formData.notes"
                    v-rtl
                    rows="4"
                    :placeholder="t('clients.formModal.fields.intakeNotes.placeholder')"
                    class="mt-1 block min-h-[100px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
                  ></textarea>
                </div>
              </div>
            </Transition>
          </form>

          <!-- Footer -->
          <div
            class="sticky bottom-0 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-6"
          >
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
              <button
                @click="closeModal"
                type="button"
                :disabled="isSubmitting"
                class="order-2 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 sm:order-1 sm:w-auto"
              >
                {{ t('clients.formModal.cancelButton') }}
              </button>
              <button
                @click="handleSubmit"
                type="submit"
                :disabled="isSubmitting"
                class="order-1 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300 sm:order-2 sm:w-auto"
              >
                <span v-if="isSubmitting" class="flex items-center gap-2">
                  <svg
                    class="h-4 w-4 animate-spin"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
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
                  {{ mode === 'edit' ? t('clients.formModal.savingStatus') : t('clients.formModal.addingStatus') }}
                </span>
                <span v-else>{{ submitButtonText }}</span>
              </button>
            </div>
            <p class="mt-3 hidden text-center text-xs text-slate-500 sm:block">
              {{ t('clients.formModal.keyboardHint') }}
              <kbd
                class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700"
                >{{ modifierKey }}Enter</kbd
              >
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .transition-all,
  .transition-opacity,
  .transition-transform {
    transition: none !important;
  }
}
</style>
