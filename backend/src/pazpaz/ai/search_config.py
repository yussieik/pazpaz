"""
Search configuration and tuning parameters for semantic retrieval.

This module centralizes all search-related configuration that requires tuning.
These are temporary solutions that will be replaced with hybrid search (BM25 + semantic)
and/or reranking models in future iterations.

TODO: Replace with production-grade search strategy:
  - Option 1: Hybrid search (semantic + BM25 keyword matching)
  - Option 2: Two-stage retrieval with reranking model (Cohere Rerank API)
  - Option 3: Query understanding layer (LLM-based query rewriting)

See: /docs/architecture/search-improvement-plan.md

Technical Debt Tracking:
  - Created: 2025-11-08
  - Reason: Need working search for V1 launch without over-engineering
  - Migration Plan: Post-launch, implement hybrid search (1-2 weeks)
  - Current Performance: ~80% query success rate (4/5 test queries passed)

How to Modify This Configuration:
  1. All tuning parameters are in SearchConfig dataclass below
  2. To adjust thresholds: Modify default_min_similarity, short_query_threshold_reduction
  3. To add query patterns: Extend general_query_patterns list
  4. To add expansion triggers: Extend expansion_trigger_patterns list
  5. Restart API after changes (values loaded at startup)
  6. Test with: docker compose exec api python -c "from pazpaz.ai.search_config import ..."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchConfig:
    """
    Configuration for semantic search behavior.

    These values are tuned based on Cohere Embed v4.0 characteristics
    with input_type differentiation (search_query vs search_document).
    """

    # ============================================================================
    # SIMILARITY THRESHOLDS
    # ============================================================================
    # These thresholds are empirically tuned for Cohere Embed v4.0.
    # Lower thresholds than traditional embeddings because input_type
    # differentiation produces lower but more meaningful similarity scores.

    # Default threshold for most queries
    default_min_similarity: float = 0.3

    # Minimum threshold floor (never go below this)
    absolute_min_similarity: float = 0.15

    # Threshold adjustment for short/general queries
    # Short queries (<6 words) with general patterns get this reduction
    short_query_threshold_reduction: float = 0.10

    # ============================================================================
    # QUERY CLASSIFICATION
    # ============================================================================
    # Patterns used to detect query types for adaptive threshold tuning

    # Word count threshold for "short query" classification
    short_query_word_threshold: int = 6

    # Patterns that indicate general/broad information requests
    # These queries naturally produce lower similarity scores because they
    # lack specific clinical terminology present in detailed documentation
    general_query_patterns: list[str] = None

    # ============================================================================
    # QUERY EXPANSION
    # ============================================================================
    # Clinical terminology mappings for expanding user queries
    # This bridges the gap between lay terminology and clinical documentation

    # Trigger patterns that benefit from expansion
    expansion_trigger_patterns: list[str] = None

    # Patterns that should NOT be expanded (already specific)
    no_expansion_patterns: list[str] = None

    def __post_init__(self):
        """Initialize default values for mutable fields."""
        # Initialize general query patterns
        if self.general_query_patterns is None:
            self.general_query_patterns = [
                # Question words requesting general information
                "what is",
                "what's",
                "what are",
                "where is",
                "where are",
                "where does",
                "how is",
                "how does",
                "how are",
                "tell me",
                "explain",
                "describe",
                # Hebrew equivalents
                "מה זה",
                "איפה",
                "איך",
            ]

        # Initialize expansion trigger patterns
        if self.expansion_trigger_patterns is None:
            self.expansion_trigger_patterns = [
                "treatment",
                "therapy",
                "tried",
                "effective",
                "improve",
                "relief",
                "symptom",
                "complaint",
                "pain",
                "diagnosis",
                "diagnose",
                "diagnosed",
                # Hebrew
                "טיפול",
                "שיפור",
                "כאב",
                "אבחנה",
            ]

        # Initialize no-expansion patterns
        if self.no_expansion_patterns is None:
            self.no_expansion_patterns = [
                "session",
                "date",
                "when",
                "who",
                # Hebrew
                "מתי",
                "פגישה",
            ]


# Global configuration instance
# Override this in tests or for experimentation
_config = SearchConfig()


def get_search_config() -> SearchConfig:
    """
    Get current search configuration.

    Returns:
        Current SearchConfig instance

    Example:
        >>> config = get_search_config()
        >>> print(config.default_min_similarity)
        0.3
    """
    return _config


def set_search_config(config: SearchConfig) -> None:
    """
    Override search configuration (primarily for testing).

    Args:
        config: New SearchConfig instance

    Example:
        >>> test_config = SearchConfig(default_min_similarity=0.1)
        >>> set_search_config(test_config)
    """
    global _config
    _config = config


def compute_adaptive_threshold(
    query: str,
    base_threshold: float,
    config: SearchConfig | None = None,
) -> float:
    """
    Compute adaptive similarity threshold based on query characteristics.

    Short, general queries naturally produce lower similarity scores because
    they lack specific clinical details. This function detects such queries
    and lowers the threshold to avoid false negatives.

    Args:
        query: User query text
        base_threshold: Starting threshold value (usually from API request)
        config: Optional search config (uses global config if not provided)

    Returns:
        Adjusted threshold value (>= absolute_min_similarity)

    Algorithm:
        1. Count words in query
        2. If query is short (<6 words by default):
           a. Check if query matches general information patterns
           b. If yes, reduce threshold by configured amount
        3. Ensure result >= absolute_min_similarity floor

    Examples:
        >>> compute_adaptive_threshold("What is the diagnosis?", 0.3)
        0.2  # Short general query: 0.3 - 0.1 = 0.2

        >>> compute_adaptive_threshold("lower back pain radiation pattern", 0.3)
        0.3  # Specific query: no adjustment

        >>> compute_adaptive_threshold("Where is pain?", 0.15)
        0.15  # Already at floor, no reduction

    TODO: Replace with learned threshold prediction or reranking model
    """
    if config is None:
        config = get_search_config()

    query_word_count = len(query.split())

    # Short query with general pattern → reduce threshold
    if query_word_count < config.short_query_word_threshold:
        query_lower = query.lower()
        if any(pattern in query_lower for pattern in config.general_query_patterns):
            adjusted = base_threshold - config.short_query_threshold_reduction
            return max(config.absolute_min_similarity, adjusted)

    # Default: no adjustment
    return base_threshold


def should_expand_query(query: str, config: SearchConfig | None = None) -> bool:
    """
    Determine if query should be expanded with clinical terminology.

    Some queries benefit from adding related clinical terms (e.g., "treatment"
    → add "therapy", "intervention", "modality"). Others are already specific
    or are metadata queries that shouldn't be expanded.

    Args:
        query: User query text
        config: Optional search config (uses global config if not provided)

    Returns:
        True if query should be expanded, False otherwise

    Examples:
        >>> should_expand_query("What treatments has the patient tried?")
        True  # Contains "treatments" trigger

        >>> should_expand_query("Session notes for June 3rd")
        False  # Contains "session" no-expansion pattern

        >>> should_expand_query("What is the diagnosis?")
        True  # Contains "diagnosis" trigger

    TODO: Replace with neural query rewriting or multi-query generation
    """
    if config is None:
        config = get_search_config()

    query_lower = query.lower()

    # Don't expand if query is asking for specific metadata
    if any(pattern in query_lower for pattern in config.no_expansion_patterns):
        return False

    # Expand if query contains clinical terminology triggers
    return any(trigger in query_lower for trigger in config.expansion_trigger_patterns)
