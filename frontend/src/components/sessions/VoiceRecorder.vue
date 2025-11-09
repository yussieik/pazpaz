<script setup lang="ts">
/**
 * VoiceRecorder Component
 *
 * Voice-to-text transcription for SOAP note fields with preview modal.
 *
 * Features:
 * - Record button → Recording indicator → Stop/Cancel
 * - Transcription preview modal (mandatory review before inserting)
 * - Editable transcription text
 * - Optional AI cleanup (removes filler words, fixes grammar)
 * - Before/after comparison for cleanup
 * - Error handling (permissions, network, API failures)
 * - Mobile-friendly (iOS Safari, Android Chrome)
 *
 * Usage:
 *   <VoiceRecorder
 *     :field-name="subjective"
 *     @transcribed="handleTranscribed"
 *   />
 */

import { ref, computed } from 'vue'
import { useVoiceRecorder } from '@/composables/useVoiceRecorder'
import type {
  TranscriptionResponse,
  CleanupResponse,
} from '@/composables/useVoiceRecorder'

interface Props {
  /** SOAP field name (subjective, objective, assessment, plan) */
  fieldName: 'subjective' | 'objective' | 'assessment' | 'plan'
  /** Language for AI cleanup (he or en) */
  language?: string
}

interface Emits {
  /** Emitted when user confirms transcription text */
  (e: 'transcribed', text: string): void
}

const props = withDefaults(defineProps<Props>(), {
  language: 'he',
})

const emit = defineEmits<Emits>()

// Voice recorder composable
const {
  isRecording,
  isTranscribing,
  error,
  permissionDenied,
  startRecording,
  stopRecording,
  cancelRecording,
  transcribeAudio,
  cleanupTranscription,
  clearError,
} = useVoiceRecorder()

// Preview modal state
const showPreviewModal = ref(false)
const transcriptionText = ref('')
const originalText = ref('') // For cleanup comparison
const detectedLanguage = ref('en') // Language detected by Whisper
const isCleaningUp = ref(false)
const showCleanupComparison = ref(false)

// Recording duration timer (for UX feedback)
const recordingDuration = ref(0)
let recordingTimer: number | null = null

/**
 * Handle mic button click - start recording
 */
async function handleStartRecording() {
  try {
    clearError()
    await startRecording()

    // Start duration timer
    recordingDuration.value = 0
    recordingTimer = window.setInterval(() => {
      recordingDuration.value++
    }, 1000)
  } catch (err) {
    // Error handled by composable (permissionDenied, error)
    console.error('Failed to start recording:', err)
  }
}

/**
 * Handle stop button click - stop recording and transcribe
 */
async function handleStopRecording() {
  try {
    // Stop timer
    if (recordingTimer) {
      clearInterval(recordingTimer)
      recordingTimer = null
    }

    // Stop recording and get audio blob
    const audioBlob = await stopRecording()

    // Transcribe audio
    const result: TranscriptionResponse = await transcribeAudio(
      audioBlob,
      props.fieldName
    )

    // Show preview modal with transcription
    transcriptionText.value = result.text
    originalText.value = result.text // Save original for comparison
    detectedLanguage.value = result.language || 'en' // Use detected language
    showPreviewModal.value = true
    showCleanupComparison.value = false
  } catch (err) {
    // Error handled by composable
    console.error('Failed to stop/transcribe recording:', err)
  }
}

/**
 * Handle cancel button click - discard recording
 */
function handleCancelRecording() {
  // Stop timer
  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }

  recordingDuration.value = 0
  cancelRecording()
}

/**
 * Handle "Clean up with AI" button click
 */
async function handleCleanup() {
  try {
    isCleaningUp.value = true

    const result: CleanupResponse = await cleanupTranscription(
      transcriptionText.value,
      props.fieldName,
      detectedLanguage.value // Use detected language from Whisper
    )

    // Update transcription with cleaned text
    transcriptionText.value = result.cleaned_text
    originalText.value = result.original_text

    // Show comparison
    showCleanupComparison.value = true
  } catch (err) {
    console.error('Cleanup failed:', err)
    // Composable handles fallback to original text
  } finally {
    isCleaningUp.value = false
  }
}

/**
 * Revert to original (un-cleaned) text
 */
function revertToOriginal() {
  transcriptionText.value = originalText.value
  showCleanupComparison.value = false
}

/**
 * Insert transcription into SOAP field
 */
function insertTranscription() {
  emit('transcribed', transcriptionText.value)
  closePreviewModal()
}

/**
 * Close preview modal and reset state
 */
function closePreviewModal() {
  showPreviewModal.value = false
  transcriptionText.value = ''
  originalText.value = ''
  detectedLanguage.value = 'en' // Reset to default
  showCleanupComparison.value = false
  clearError()
}

/**
 * Formatted duration (MM:SS)
 */
const formattedDuration = computed(() => {
  const minutes = Math.floor(recordingDuration.value / 60)
  const seconds = recordingDuration.value % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})
</script>

<template>
  <div class="voice-recorder">
    <!-- Mic Button (Not Recording) -->
    <button
      v-if="!isRecording && !isTranscribing"
      type="button"
      @click="handleStartRecording"
      class="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none"
      :disabled="permissionDenied"
      :class="{ 'cursor-not-allowed opacity-50': permissionDenied }"
      :aria-label="`Record ${fieldName} field`"
    >
      <!-- Mic Icon -->
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
        />
      </svg>
      <span>Dictate</span>
    </button>

    <!-- Recording Controls (While Recording) -->
    <div
      v-if="isRecording"
      class="inline-flex items-center gap-2 rounded-md bg-red-50 px-3 py-1.5"
    >
      <!-- Recording Indicator -->
      <div class="flex items-center gap-1.5">
        <span class="relative flex h-3 w-3">
          <span
            class="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75"
          ></span>
          <span class="relative inline-flex h-3 w-3 rounded-full bg-red-500"></span>
        </span>
        <span class="text-sm font-medium text-red-700"
          >Recording {{ formattedDuration }}</span
        >
      </div>

      <!-- Stop Button -->
      <button
        type="button"
        @click="handleStopRecording"
        class="inline-flex items-center gap-1 rounded bg-red-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-red-700 focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:outline-none"
      >
        <svg class="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
          <rect x="6" y="6" width="8" height="8" rx="1" />
        </svg>
        Stop
      </button>

      <!-- Cancel Button -->
      <button
        type="button"
        @click="handleCancelRecording"
        class="text-xs text-red-700 underline hover:text-red-800 focus:outline-none"
      >
        Cancel
      </button>
    </div>

    <!-- Transcribing Indicator -->
    <div
      v-if="isTranscribing"
      class="inline-flex items-center gap-2 rounded-md bg-blue-50 px-3 py-1.5"
    >
      <!-- Spinner -->
      <svg class="h-4 w-4 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
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
      <span class="text-sm font-medium text-blue-700">Transcribing...</span>
    </div>

    <!-- Error Banner -->
    <div v-if="error" class="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
      <div class="flex items-start gap-2">
        <svg
          class="mt-0.5 h-4 w-4 flex-shrink-0 text-red-600"
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
          <p>{{ error }}</p>
          <button
            v-if="permissionDenied"
            type="button"
            @click="clearError"
            class="mt-1 text-xs font-medium text-red-700 underline hover:text-red-800"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>

    <!-- Preview Modal (Mandatory Review Before Inserting) -->
    <Teleport to="body">
      <div
        v-if="showPreviewModal"
        class="fixed inset-0 z-50 overflow-y-auto"
        aria-labelledby="preview-modal-title"
        role="dialog"
        aria-modal="true"
      >
        <!-- Background overlay -->
        <div
          class="bg-opacity-50 fixed inset-0 bg-slate-900 transition-opacity"
          @click="closePreviewModal"
        ></div>

        <!-- Modal content -->
        <div
          class="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0"
        >
          <div
            class="relative w-full transform overflow-hidden rounded-lg bg-white px-4 pt-5 pb-4 text-left shadow-xl transition-all sm:my-8 sm:max-w-2xl sm:p-6"
            @click.stop
          >
            <!-- Header -->
            <div class="mb-4">
              <h3
                id="preview-modal-title"
                class="text-lg leading-6 font-semibold text-slate-900"
              >
                Transcription Preview
              </h3>
              <p class="mt-1 text-sm text-slate-600">
                Review and edit the transcription before inserting into
                {{ fieldName }} field.
              </p>
            </div>

            <!-- Transcription Text (Editable) -->
            <div class="mb-4">
              <label
                for="transcription-text"
                class="block text-sm font-medium text-slate-700"
              >
                Transcribed Text
              </label>
              <textarea
                id="transcription-text"
                v-model="transcriptionText"
                rows="8"
                class="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                placeholder="Transcription will appear here..."
              ></textarea>
              <p class="mt-1 text-xs text-slate-500">
                {{ transcriptionText.length }} characters
              </p>
            </div>

            <!-- Cleanup Comparison (if AI cleanup was used) -->
            <div v-if="showCleanupComparison" class="mb-4 rounded-md bg-blue-50 p-3">
              <div class="mb-2 flex items-center justify-between">
                <p class="text-sm font-medium text-blue-900">AI Cleanup Applied</p>
                <button
                  type="button"
                  @click="revertToOriginal"
                  class="text-xs font-medium text-blue-700 underline hover:text-blue-800"
                >
                  Revert to original
                </button>
              </div>
              <details class="text-sm text-blue-800">
                <summary class="cursor-pointer font-medium">Show original text</summary>
                <p class="mt-2 rounded bg-white p-2 whitespace-pre-wrap text-slate-700">
                  {{ originalText }}
                </p>
              </details>
            </div>

            <!-- Action Buttons -->
            <div
              class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <!-- Left: Cleanup Button -->
              <button
                v-if="!showCleanupComparison"
                type="button"
                @click="handleCleanup"
                :disabled="isCleaningUp"
                class="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
              >
                <svg
                  v-if="!isCleaningUp"
                  class="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                  />
                </svg>
                <svg
                  v-else
                  class="h-4 w-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
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
                <span>{{ isCleaningUp ? 'Cleaning...' : 'Clean up with AI' }}</span>
              </button>
              <div v-else></div>

              <!-- Right: Insert / Re-record Buttons -->
              <div class="flex gap-2">
                <button
                  type="button"
                  @click="closePreviewModal"
                  class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none"
                >
                  Re-record
                </button>
                <button
                  type="button"
                  @click="insertTranscription"
                  class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none"
                >
                  Insert
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
