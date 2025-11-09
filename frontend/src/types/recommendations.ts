/**
 * Treatment Recommendation type definitions for PazPaz
 *
 * Provides TypeScript interfaces for AI-powered treatment plan recommendations
 * (ADR 0002 - Treatment Recommendation Engine, Milestone 2)
 *
 * Features:
 * - Therapy-specific recommendations (massage, physiotherapy, psychotherapy)
 * - Evidence-based suggestions with patient context
 * - Bilingual support (Hebrew/English)
 * - Rate limited (60 requests/hour per workspace)
 *
 * HIPAA Compliance:
 * - SOAP note inputs not stored (ephemeral processing)
 * - Workspace isolation enforced
 * - Audit logging (metadata only, no PHI)
 */

/**
 * Treatment recommendation request (mirrors backend TreatmentRecommendationRequest)
 */
export interface TreatmentRecommendationRequest {
  subjective: string
  objective: string
  assessment: string
  client_id?: string
}

/**
 * Individual treatment recommendation item (mirrors backend TreatmentRecommendationItem)
 */
export interface TreatmentRecommendationItem {
  recommendation_id: string
  title: string
  description: string
  therapy_type: 'massage' | 'physiotherapy' | 'psychotherapy' | 'generic'
  evidence_type: 'workspace_patterns' | 'clinical_guidelines' | 'hybrid'
  similar_cases_count: number
}

/**
 * Treatment recommendation response (mirrors backend TreatmentRecommendationResponse)
 */
export interface TreatmentRecommendationResponse {
  recommendations: TreatmentRecommendationItem[]
  therapy_type: 'massage' | 'physiotherapy' | 'psychotherapy' | 'generic'
  language: 'he' | 'en'
  retrieved_count: number
  processing_time_ms: number
}

/**
 * UI state for treatment recommendations
 */
export interface TreatmentRecommendationState {
  recommendations: TreatmentRecommendationItem[]
  isLoading: boolean
  error: string | null
  therapy_type: 'massage' | 'physiotherapy' | 'psychotherapy' | 'generic' | null
  language: 'he' | 'en' | null
  retrieved_count: number
  processing_time_ms: number
}

/**
 * Feedback type for user interaction with recommendations
 * (Deferred to Phase 2 - Milestone 3)
 */
export interface TreatmentRecommendationFeedback {
  recommendation_id: string
  feedback_type: 'thumbs_up' | 'thumbs_down' | 'used'
  session_id?: string
}
