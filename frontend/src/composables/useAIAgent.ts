import { ref, computed } from 'vue'
import apiClient from '@/api/client'

/**
 * AI Agent Composable
 *
 * Provides AI clinical documentation assistant functionality with:
 * - Natural language queries (Hebrew/English)
 * - Session citation references
 * - Rate limiting (30 queries/hour per workspace)
 * - Workspace-scoped queries
 *
 * HIPAA Compliance:
 * - No query text stored (ephemeral processing)
 * - PHI auto-decrypted only for authorized workspace
 * - All queries logged with metadata (not query text)
 */

export interface SessionCitation {
  type: 'session'
  session_id: string
  client_id: string
  client_name: string
  session_date: string
  similarity: number
  field_name: string
}

export interface ClientCitation {
  type: 'client'
  client_id: string
  client_name: string
  similarity: number
  field_name: string
}

export type Citation = SessionCitation | ClientCitation

export interface AgentChatRequest {
  query: string
  client_id?: string
  max_results?: number
  min_similarity?: number
}

export interface AgentChatResponse {
  answer: string
  citations: Citation[]
  language: 'he' | 'en'
  retrieved_count: number
  processing_time_ms: number
}

export interface AgentMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  timestamp: Date
  language?: 'he' | 'en'
  processing_time_ms?: number
}

const messages = ref<AgentMessage[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

export function useAIAgent() {
  /**
   * Send query to AI agent
   *
   * @param request - Chat request with query and optional filters
   * @returns Agent response with answer and citations
   */
  async function sendQuery(request: AgentChatRequest): Promise<AgentChatResponse> {
    isLoading.value = true
    error.value = null

    try {
      // Add user message to chat
      const userMessage: AgentMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: request.query,
        timestamp: new Date(),
      }
      messages.value.push(userMessage)

      // Send query to backend
      const response = await apiClient.post<AgentChatResponse>(
        '/ai/agent/chat',
        request
      )

      // Add assistant response to chat
      const assistantMessage: AgentMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.data.answer,
        citations: response.data.citations,
        timestamp: new Date(),
        language: response.data.language,
        processing_time_ms: response.data.processing_time_ms,
      }
      messages.value.push(assistantMessage)

      return response.data
    } catch (err: unknown) {
      const axiosError = err as {
        response?: { status?: number; data?: { detail?: string } }
      }

      // Handle rate limiting
      if (axiosError.response?.status === 429) {
        error.value = 'Rate limit exceeded. Maximum 30 queries per hour.'
      }
      // Handle authentication errors
      else if (axiosError.response?.status === 401) {
        error.value = 'Authentication required. Please log in.'
      }
      // Handle other errors
      else {
        error.value =
          axiosError.response?.data?.detail ||
          'Failed to process query. Please try again.'
      }

      // Add error message to chat
      const errorMessage: AgentMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: error.value,
        timestamp: new Date(),
      }
      messages.value.push(errorMessage)

      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Clear chat history
   */
  function clearMessages() {
    messages.value = []
    error.value = null
  }

  /**
   * Get last N messages
   */
  function getRecentMessages(count: number = 10): AgentMessage[] {
    return messages.value.slice(-count)
  }

  // Computed property for checking if there are any messages
  const hasMessages = computed(() => messages.value.length > 0)

  // Computed property for getting the last message
  const lastMessage = computed(() =>
    messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  )

  return {
    // State
    messages,
    isLoading,
    error,
    hasMessages,
    lastMessage,

    // Actions
    sendQuery,
    clearMessages,
    getRecentMessages,
  }
}
