"""
Query expansion for improving semantic search recall.

This module expands user queries with domain-specific synonyms and related terms
to improve retrieval of relevant clinical documentation. Particularly useful for
bridging the gap between lay terminology and clinical terminology.

Architecture:
- Rule-based expansion using clinical domain knowledge
- Maintains original query intent while adding related terms
- Bilingual support (English and Hebrew)

TODO: Replace with neural query rewriting:
  - Use LLM to generate semantically equivalent queries
  - Generate multiple query variations for better recall
  - Consider HyDE (Hypothetical Document Embeddings) approach

See: pazpaz/ai/search_config.py for configuration

Example:
    >>> expand_query("treatments")
    "treatments manual therapy physical therapy exercises medication therapeutic interventions"
"""

from __future__ import annotations

# Clinical terminology mappings for query expansion
TREATMENT_TERMS = [
    "treatment",
    "treatments",
    "therapy",
    "therapies",
    "intervention",
    "interventions",
    "manual therapy",
    "physical therapy",
    "therapeutic",
    "exercises",
    "medication",
    "modality",
    "modalities",
    "rehabilitation",
    "management",
]

PAIN_TERMS = [
    "pain",
    "discomfort",
    "ache",
    "soreness",
    "tenderness",
    "sharp",
    "dull",
    "radiating",
    "referred",
]

IMPROVEMENT_TERMS = [
    "improvement",
    "improved",
    "better",
    "progress",
    "response",
    "effective",
    "effectiveness",
    "relief",
    "reduced",
    "decreased",
]

SYMPTOM_TERMS = [
    "symptom",
    "symptoms",
    "complaint",
    "complaints",
    "issue",
    "issues",
    "problem",
    "problems",
    "condition",
]

DIAGNOSIS_TERMS = [
    "diagnosis",
    "diagnose",
    "diagnosed",
    "assessment",
    "clinical impression",
    "condition",
    "finding",
    "findings",
]

# Hebrew translations for common terms
TREATMENT_TERMS_HE = [
    "טיפול",
    "טיפולים",
    "התערבות",
    "התערבויות",
    "פיזיותרפיה",
    "תרפיה",
    "שיקום",
]

PAIN_TERMS_HE = [
    "כאב",
    "כאבים",
    "אי נוחות",
    "רגישות",
]


def expand_query(query: str, language: str = "en") -> str:
    """
    Expand query with related clinical terminology.

    Adds domain-specific synonyms to improve semantic search recall without
    changing the core intent of the query.

    Args:
        query: Original user query
        language: Language code ("en" or "he")

    Returns:
        Expanded query string with added clinical terms

    Example:
        >>> expand_query("What treatments did the patient try?")
        "What treatments did the patient try? manual therapy physical therapy exercises medication therapeutic interventions"

        >>> expand_query("Has the pain improved?")
        "Has the pain improved? better progress response relief reduced decreased"
    """
    query_lower = query.lower()
    expansions = []

    # Treatment-related expansion
    if any(
        term in query_lower for term in ["treatment", "therapy", "tried", "received"]
    ):
        if language == "he":
            expansions.extend(TREATMENT_TERMS_HE[:3])  # Add top 3 Hebrew terms
        else:
            expansions.extend(
                [
                    "manual therapy",
                    "physical therapy",
                    "exercises",
                    "medication",
                    "therapeutic interventions",
                ]
            )

    # Pain-related expansion
    if any(term in query_lower for term in ["pain", "ache", "hurt", "sore"]):
        if language == "he":
            expansions.extend(PAIN_TERMS_HE[:2])
        else:
            expansions.extend(["discomfort", "soreness", "tenderness"])

    # Improvement/effectiveness expansion
    if any(
        term in query_lower
        for term in [
            "improve",
            "better",
            "effective",
            "help",
            "work",
            "relief",
            "progress",
        ]
    ):
        if language == "he":
            expansions.extend(["התקדמות", "שיפור", "הקלה"])
        else:
            expansions.extend(
                ["progress", "response", "relief", "reduced", "decreased"]
            )

    # Symptom-related expansion
    if any(
        term in query_lower for term in ["symptom", "complaint", "issue", "problem"]
    ):
        if language == "he":
            expansions.extend(["תסמין", "תסמינים", "תלונה"])
        else:
            expansions.extend(["complaint", "issue", "condition"])

    # Diagnosis-related expansion
    if any(
        term in query_lower
        for term in ["diagnosis", "diagnose", "diagnosed", "what is", "condition"]
    ):
        if language == "he":
            expansions.extend(["אבחנה", "מצב קליני", "ממצאים"])
        else:
            # More aggressive expansion for diagnosis queries
            expansions.extend(
                [
                    "assessment",
                    "clinical impression",
                    "finding",
                    "findings",
                    "diagnosis",
                    "diagnose",
                    "diagnosed",
                    "condition",
                    "disorder",
                    "pathology",
                    "etiology",
                    "prognosis",
                    "clinical presentation",
                    "differential diagnosis",
                ]
            )

    # Combine original query with expansions
    if expansions:
        return f"{query} {' '.join(expansions)}"

    return query


# NOTE: should_expand_query() has been moved to pazpaz/ai/search_config.py
# to centralize all search tuning configuration in one place
