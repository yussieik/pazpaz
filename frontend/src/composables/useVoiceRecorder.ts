/**
 * Voice Recorder Composable
 *
 * Provides voice recording and transcription functionality for SOAP notes.
 *
 * Features:
 * - MediaRecorder API for browser-native audio recording
 * - Format detection for iOS Safari compatibility (requires MP4)
 * - Audio quality pre-check (duration, volume level)
 * - OpenAI Whisper API transcription (Hebrew/English)
 * - Optional AI cleanup (Cohere - removes filler words)
 * - Preview modal with before/after comparison
 * - Error handling (permissions, network, API failures)
 * - Rate limiting (60 requests/hour per workspace)
 *
 * Usage:
 *   const { startRecording, stopRecording, transcribeAudio } = useVoiceRecorder()
 *   await startRecording()
 *   const audioBlob = await stopRecording()
 *   const result = await transcribeAudio(audioBlob, 'subjective')
 */

import { ref, type Ref } from 'vue'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'

/**
 * Transcription response from backend
 */
export interface TranscriptionResponse {
  text: string
  language: string
  duration_seconds: number
}

/**
 * Cleanup response from backend (optional post-processing)
 */
export interface CleanupResponse {
  cleaned_text: string
  original_text: string
}

/**
 * Recording state
 */
export interface RecordingState {
  isRecording: boolean
  isTranscribing: boolean
  error: string | null
  permissionDenied: boolean
  audioBlob: Blob | null
  duration: number // Recording duration in seconds
}

export function useVoiceRecorder() {
  const isRecording: Ref<boolean> = ref(false)
  const isTranscribing: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const permissionDenied: Ref<boolean> = ref(false)

  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []
  let stream: MediaStream | null = null
  let recordingStartTime: number = 0

  /**
   * Detect supported audio format (iOS Safari requires MP4)
   *
   * Priority order:
   * 1. audio/webm;codecs=opus (Best: low bitrate, high quality)
   * 2. audio/webm
   * 3. audio/mp4 (iOS Safari requirement)
   * 4. audio/wav (Fallback)
   */
  function getSupportedMimeType(): string {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/wav']

    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        console.debug(`[VoiceRecorder] Using audio format: ${type}`)
        return type
      }
    }

    throw new Error(
      'No supported audio format found. Please use a modern browser (Chrome 49+, Safari 14.1+, Firefox 25+).'
    )
  }

  /**
   * Start recording audio from microphone
   *
   * Requests microphone permission if needed.
   * Starts MediaRecorder with best supported format.
   *
   * @throws Error if microphone access denied or MediaRecorder not supported
   */
  async function startRecording(): Promise<void> {
    try {
      error.value = null
      permissionDenied.value = false

      // Request microphone access
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Detect best supported MIME type
      const mimeType = getSupportedMimeType()

      // Create MediaRecorder
      mediaRecorder = new MediaRecorder(stream, { mimeType })
      audioChunks = []
      recordingStartTime = Date.now()

      // Collect audio data
      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data)
        }
      }

      // Start recording
      mediaRecorder.start()
      isRecording.value = true

      console.debug('[VoiceRecorder] Recording started')
    } catch (err) {
      console.error('[VoiceRecorder] Failed to start recording:', err)

      // Handle permission denied
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          permissionDenied.value = true
          error.value =
            'Microphone access denied. Please enable microphone permissions in your browser settings.'
        } else if (err.name === 'NotFoundError') {
          error.value =
            'No microphone found. Please connect a microphone and try again.'
        } else {
          error.value = `Failed to start recording: ${err.message}`
        }
      } else {
        error.value = 'Failed to start recording. Please try again.'
      }

      throw err
    }
  }

  /**
   * Stop recording and return audio blob
   *
   * Stops MediaRecorder and releases microphone stream.
   * Returns audio blob for upload to transcription API.
   *
   * @returns Promise that resolves to audio blob
   * @throws Error if no active recording
   */
  async function stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!mediaRecorder) {
        const err = new Error('No active recording to stop')
        error.value = err.message
        reject(err)
        return
      }

      mediaRecorder.onstop = () => {
        // Create audio blob from chunks
        const audioBlob = new Blob(audioChunks, { type: mediaRecorder!.mimeType })

        // Calculate recording duration
        const duration = (Date.now() - recordingStartTime) / 1000 // seconds

        // Stop media stream (release microphone)
        stream?.getTracks().forEach((track) => track.stop())
        stream = null

        // Reset state
        isRecording.value = false
        mediaRecorder = null

        console.debug(
          `[VoiceRecorder] Recording stopped. Duration: ${duration.toFixed(1)}s, Size: ${(audioBlob.size / 1024).toFixed(1)} KB`
        )

        // Validate duration (2-300 seconds per ADR)
        if (duration < 2) {
          const err = new Error(
            'Recording too short (minimum 2 seconds). Please try again.'
          )
          error.value = err.message
          reject(err)
          return
        }

        if (duration > 300) {
          const err = new Error(
            'Recording too long (maximum 5 minutes). Please re-record.'
          )
          error.value = err.message
          reject(err)
          return
        }

        resolve(audioBlob)
      }

      mediaRecorder.stop()
    })
  }

  /**
   * Cancel recording without saving
   *
   * Stops recording and discards audio data.
   */
  function cancelRecording(): void {
    if (mediaRecorder && isRecording.value) {
      mediaRecorder.stop()
      stream?.getTracks().forEach((track) => track.stop())
      stream = null
      isRecording.value = false
      mediaRecorder = null
      audioChunks = []
      console.debug('[VoiceRecorder] Recording canceled')
    }
  }

  /**
   * Transcribe audio file using OpenAI Whisper API
   *
   * Uploads audio to backend /api/v1/transcribe endpoint.
   * Backend handles OpenAI Whisper API call with Hebrew language support.
   *
   * @param audioBlob - Audio file to transcribe
   * @param fieldName - SOAP field name (subjective, objective, assessment, plan)
   * @returns Transcription response with text, language, and duration
   * @throws Error if API call fails or rate limit exceeded
   */
  async function transcribeAudio(
    audioBlob: Blob,
    fieldName: string
  ): Promise<TranscriptionResponse> {
    try {
      error.value = null
      isTranscribing.value = true

      // Create FormData for multipart/form-data upload
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')
      formData.append('field_name', fieldName)

      console.debug(
        `[VoiceRecorder] Transcribing audio for field: ${fieldName}, size: ${(audioBlob.size / 1024).toFixed(1)} KB`
      )

      // Call backend transcription endpoint
      const response = await apiClient.post<TranscriptionResponse>(
        '/transcribe',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 60000, // 60 seconds (Whisper API can take time)
        }
      )

      console.debug('[VoiceRecorder] Transcription successful:', response.data)

      return response.data
    } catch (err) {
      console.error('[VoiceRecorder] Transcription failed:', err)

      // Handle specific error cases
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as AxiosError<{ detail: string }>

        if (axiosError.response?.status === 429) {
          error.value =
            'Rate limit exceeded (60 transcriptions/hour). Please try again later.'
        } else if (axiosError.response?.status === 400) {
          error.value =
            axiosError.response.data?.detail || 'Invalid audio file. Please re-record.'
        } else if (axiosError.response?.status === 500) {
          error.value =
            'Transcription service temporarily unavailable. Please try again or type manually.'
        } else {
          error.value =
            'Transcription failed. Please check your network connection and try again.'
        }
      } else {
        error.value = 'Transcription failed. Please try again or type manually.'
      }

      throw err
    } finally {
      isTranscribing.value = false
    }
  }

  /**
   * Clean up messy transcription using AI (optional)
   *
   * Removes filler words (um, uh, like, אה, כאילו) and fixes grammar
   * while preserving 100% of clinical details.
   *
   * @param rawText - Raw transcription text
   * @param fieldName - SOAP field name
   * @param language - Language code (he or en)
   * @returns Cleanup response with cleaned and original text
   */
  async function cleanupTranscription(
    rawText: string,
    fieldName: string,
    language: string = 'he'
  ): Promise<CleanupResponse> {
    try {
      console.debug(
        `[VoiceRecorder] Cleaning up transcription for field: ${fieldName}, language: ${language}`
      )

      const response = await apiClient.post<CleanupResponse>('/transcribe/cleanup', {
        raw_text: rawText,
        field_name: fieldName,
        language,
      })

      console.debug('[VoiceRecorder] Cleanup successful')

      return response.data
    } catch (err) {
      console.error('[VoiceRecorder] Cleanup failed:', err)

      // Return original text as fallback (graceful degradation)
      console.warn('[VoiceRecorder] Falling back to original text')
      return {
        cleaned_text: rawText,
        original_text: rawText,
      }
    }
  }

  /**
   * Reset error state
   */
  function clearError(): void {
    error.value = null
    permissionDenied.value = false
  }

  return {
    // State
    isRecording,
    isTranscribing,
    error,
    permissionDenied,

    // Methods
    startRecording,
    stopRecording,
    cancelRecording,
    transcribeAudio,
    cleanupTranscription,
    clearError,
  }
}
