"""Prometheus metrics for AI agent monitoring."""

from prometheus_client import Counter, Histogram

# Query metrics
ai_agent_queries_total = Counter(
    "ai_agent_queries_total",
    "Total AI agent queries processed",
    ["workspace_id", "language", "status"],
)

ai_agent_query_duration_seconds = Histogram(
    "ai_agent_query_duration_seconds",
    "Time spent processing AI agent queries end-to-end",
    ["language"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0],
)

# Embedding metrics
ai_agent_embedding_duration_seconds = Histogram(
    "ai_agent_embedding_duration_seconds",
    "Time spent generating embeddings for queries",
    ["model"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

ai_agent_embedding_errors_total = Counter(
    "ai_agent_embedding_errors_total",
    "Total embedding generation errors",
    ["error_type", "model"],
)

# Retrieval metrics
ai_agent_retrieval_duration_seconds = Histogram(
    "ai_agent_retrieval_duration_seconds",
    "Time spent retrieving relevant sessions from vector store",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

ai_agent_sources_retrieved = Histogram(
    "ai_agent_sources_retrieved",
    "Number of source sessions retrieved per query",
    buckets=[0, 1, 2, 3, 4, 5, 7, 10, 15, 20],
)

# LLM metrics
ai_agent_llm_duration_seconds = Histogram(
    "ai_agent_llm_duration_seconds",
    "Time spent calling Cohere LLM for synthesis",
    ["model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)

ai_agent_llm_errors_total = Counter(
    "ai_agent_llm_errors_total",
    "Total LLM API errors",
    ["error_type", "model"],
)

ai_agent_llm_tokens_total = Counter(
    "ai_agent_llm_tokens_total",
    "Total tokens consumed by LLM calls",
    ["model", "token_type"],  # token_type: input, output
)

# Rate limiting metrics
ai_agent_rate_limit_hits_total = Counter(
    "ai_agent_rate_limit_hits_total",
    "Total rate limit hits (queries blocked)",
    ["workspace_id"],
)

# Citation metrics
ai_agent_citations_returned = Histogram(
    "ai_agent_citations_returned",
    "Number of citations returned per query",
    buckets=[0, 1, 2, 3, 4, 5, 7, 10],
)

# Retry metrics
ai_retries_total = Counter(
    "ai_retries_total",
    "Total retry attempts across all AI operations",
    ["operation", "attempt", "circuit_breaker"],
)

ai_circuit_breaker_state_changes_total = Counter(
    "ai_circuit_breaker_state_changes_total",
    "Total circuit breaker state transitions",
    ["circuit_breaker", "from_state", "to_state"],
)

ai_circuit_breaker_open_duration_seconds = Histogram(
    "ai_circuit_breaker_open_duration_seconds",
    "Duration circuit breaker remains in open state",
    ["circuit_breaker"],
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

# Cache metrics
ai_agent_cache_hits_total = Counter(
    "ai_agent_cache_hits_total",
    "Total cache hits for AI agent",
    ["workspace_id", "cache_layer"],  # cache_layer: query_result, embedding
)

ai_agent_cache_misses_total = Counter(
    "ai_agent_cache_misses_total",
    "Total cache misses for AI agent",
    ["workspace_id", "cache_layer"],
)

ai_agent_cache_invalidations_total = Counter(
    "ai_agent_cache_invalidations_total",
    "Total cache invalidations",
    ["workspace_id", "reason"],  # reason: session_created, session_updated, etc.
)

__all__ = [
    "ai_agent_queries_total",
    "ai_agent_query_duration_seconds",
    "ai_agent_embedding_duration_seconds",
    "ai_agent_embedding_errors_total",
    "ai_agent_retrieval_duration_seconds",
    "ai_agent_sources_retrieved",
    "ai_agent_llm_duration_seconds",
    "ai_agent_llm_errors_total",
    "ai_agent_llm_tokens_total",
    "ai_agent_rate_limit_hits_total",
    "ai_agent_citations_returned",
    "ai_retries_total",
    "ai_circuit_breaker_state_changes_total",
    "ai_circuit_breaker_open_duration_seconds",
    "ai_agent_cache_hits_total",
    "ai_agent_cache_misses_total",
    "ai_agent_cache_invalidations_total",
]
