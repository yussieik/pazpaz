import { ref } from 'vue'
import apiClient from '@/api/client'
import type {
  TreatmentRecommendationRequest,
  TreatmentRecommendationResponse,
  TreatmentRecommendationItem,
  TreatmentRecommendationFeedback,
} from '@/types/recommendations'
import { stripMarkdown } from '@/utils/markdown'

/**
 * Treatment Recommendations Composable
 *
 * Provides AI-powered treatment plan recommendation functionality with:
 * - Therapy-specific recommendations (massage, physiotherapy, psychotherapy)
 * - Evidence-based suggestions from workspace patterns + clinical guidelines
 * - Rate limiting (60 requests/hour per workspace)
 * - Workspace-scoped queries
 * - Bilingual support (Hebrew/English)
 *
 * HIPAA Compliance:
 * - SOAP note inputs not stored (ephemeral processing)
 * - PHI auto-decrypted only for authorized workspace
 * - All requests logged with metadata (not SOAP contents)
 *
 * Architecture:
 * - Reuses ADR 0001 infrastructure (ClinicalAgent, RAG pipeline)
 * - LLM-primary with optional patient context (hybrid approach)
 * - Workspace isolation enforced at API level
 */

const recommendations = ref<TreatmentRecommendationItem[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const therapyType = ref<string | null>(null)
const language = ref<'he' | 'en' | null>(null)
const retrievedCount = ref(0)
const processingTimeMs = ref(0)

export function useTreatmentRecommendations() {
  /**
   * Get treatment recommendations based on SOAP note inputs
   *
   * @param request - SOAP note fields (S, O, A) and optional client_id
   * @returns Treatment recommendations with evidence and metadata
   *
   * Example:
   * ```ts
   * const { getRecommendations } = useTreatmentRecommendations()
   *
   * const response = await getRecommendations({
   *   subjective: 'Patient reports upper trapezius tension, 7/10 pain',
   *   objective: 'Palpation reveals trigger points in upper trap',
   *   assessment: 'Myofascial pain syndrome',
   *   client_id: 'uuid' // optional
   * })
   * ```
   */
  async function getRecommendations(
    request: TreatmentRecommendationRequest
  ): Promise<TreatmentRecommendationResponse> {
    isLoading.value = true
    error.value = null

    try {
      // Validate inputs before sending
      if (
        !request.subjective?.trim() ||
        !request.objective?.trim() ||
        !request.assessment?.trim()
      ) {
        throw new Error('Subjective, Objective, and Assessment fields are required')
      }

      // Send request to backend
      const response = await apiClient.post<TreatmentRecommendationResponse>(
        '/ai/treatment-recommendations/',
        request
      )

      // Update state with response
      recommendations.value = response.data.recommendations
      therapyType.value = response.data.therapy_type
      language.value = response.data.language
      retrievedCount.value = response.data.retrieved_count
      processingTimeMs.value = response.data.processing_time_ms

      return response.data
    } catch (err: unknown) {
      const axiosError = err as {
        response?: { status?: number; data?: { detail?: string } }
        message?: string
      }

      // Handle rate limiting (60 req/hour)
      if (axiosError.response?.status === 429) {
        error.value =
          'Rate limit exceeded. Maximum 60 recommendation requests per hour per workspace.'
      }
      // Handle authentication errors
      else if (axiosError.response?.status === 401) {
        error.value = 'Authentication required. Please log in.'
      }
      // Handle validation errors (empty SOAP fields, prompt injection)
      else if (axiosError.response?.status === 400) {
        error.value =
          axiosError.response?.data?.detail ||
          'Invalid input. Please check your SOAP note fields.'
      }
      // Handle server errors
      else if (axiosError.response?.status === 500) {
        error.value = 'Failed to generate recommendations. Please try again later.'
      }
      // Handle other errors
      else {
        error.value =
          axiosError.message ||
          axiosError.response?.data?.detail ||
          'Failed to get recommendations. Please try again.'
      }

      // Clear recommendations on error
      recommendations.value = []
      therapyType.value = null
      language.value = null
      retrievedCount.value = 0
      processingTimeMs.value = 0

      throw new Error(error.value)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Insert recommendation into Plan field
   *
   * @param recommendation - Recommendation to insert
   * @returns Formatted text for Plan field (with markdown stripped)
   *
   * Example:
   * ```ts
   * const { insertRecommendation } = useTreatmentRecommendations()
   * const planText = insertRecommendation(recommendation)
   * // Returns: "Manual Therapy + Home Exercises\n\nApply manual therapy..."
   * ```
   *
   * Note: Markdown formatting is stripped since the Plan field is a plain textarea.
   */
  function insertRecommendation(recommendation: TreatmentRecommendationItem): string {
    // Strip markdown formatting from description (Plan field is plain textarea)
    const plainDescription = stripMarkdown(recommendation.description)

    // Format: Title\n\nDescription (plain text)
    return `${recommendation.title}\n\n${plainDescription}`
  }

  /**
   * Submit feedback for a recommendation (deferred to Phase 2)
   *
   * @param feedback - User feedback (thumbs up/down, used)
   *
   * Note: This is a placeholder for Milestone 3.
   * Feedback will be stored in audit_events.metadata for analytics.
   */
  async function submitFeedback(
    feedback: TreatmentRecommendationFeedback
  ): Promise<void> {
    // Placeholder for Phase 2 - Milestone 3
    // TODO: Implement feedback API in Milestone 3
    // await apiClient.post('/ai/treatment-recommendations/feedback', feedback)
    void feedback // Suppress unused parameter warning
  }

  /**
   * Clear current recommendations and state
   */
  function clearRecommendations(): void {
    recommendations.value = []
    error.value = null
    therapyType.value = null
    language.value = null
    retrievedCount.value = 0
    processingTimeMs.value = 0
  }

  /**
   * Get evidence badge text for display
   *
   * @param recommendation - Recommendation item
   * @returns Localized evidence badge text
   *
   * Example:
   * ```ts
   * getEvidenceBadge(rec) // "Based on 5 similar cases"
   * getEvidenceBadge(rec) // "Clinical guidelines"
   * getEvidenceBadge(rec) // "Hybrid (3 cases + guidelines)"
   * ```
   */
  function getEvidenceBadge(recommendation: TreatmentRecommendationItem): string {
    const { evidence_type, similar_cases_count } = recommendation

    if (evidence_type === 'workspace_patterns') {
      const casesText = similar_cases_count === 1 ? 'case' : 'cases'
      return `Based on ${similar_cases_count} similar ${casesText}`
    } else if (evidence_type === 'clinical_guidelines') {
      return 'Clinical guidelines'
    } else if (evidence_type === 'hybrid') {
      const casesText = similar_cases_count === 1 ? 'case' : 'cases'
      return `Hybrid (${similar_cases_count} ${casesText} + guidelines)`
    }

    return 'Evidence-based'
  }

  return {
    // State
    recommendations,
    isLoading,
    error,
    therapyType,
    language,
    retrievedCount,
    processingTimeMs,

    // Methods
    getRecommendations,
    insertRecommendation,
    submitFeedback,
    clearRecommendations,
    getEvidenceBadge,
  }
}
