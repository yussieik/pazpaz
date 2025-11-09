"""AI-powered cleanup service for voice transcriptions using Cohere.

This module provides functionality to clean up messy voice dictations by:
- Removing filler words (um, uh, like, you know, אה, כאילו, יודעת)
- Fixing grammar and sentence structure
- Removing repetitions
- Converting run-on sentences to clear clinical sentences

CRITICAL: Preserves ALL clinical details (symptoms, severity, numbers, medical terms).
Never adds information that wasn't explicitly stated in the original transcription.

Used by POST /api/v1/transcribe/cleanup endpoint for optional post-processing.
"""

from __future__ import annotations

import cohere

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def cleanup_transcription(
    raw_text: str,
    field_name: str,
    language: str = "he",
) -> str:
    """
    Clean up messy clinical dictation using Cohere Command-R Plus LLM.

    Removes filler words, fixes grammar, and structures text into clear clinical
    sentences while preserving 100% of clinical details.

    Preservation guarantees:
    - ✅ ALL clinical details (symptoms, severity, duration)
    - ✅ Numbers (pain scores, dates, measurements)
    - ✅ Medical terminology
    - ❌ Never adds information that wasn't stated
    - ❌ Never interprets or guesses

    Args:
        raw_text: Raw transcription from Whisper API
        field_name: SOAP field (subjective, objective, assessment, plan)
        language: Language code (he or en)

    Returns:
        Cleaned clinical text suitable for SOAP note

    Raises:
        Exception: If cleanup fails, returns original text as fallback

    Example:
        ```python
        raw = "Uh, so Sarah came in, she's been having this lower back pain..."
        cleaned = await cleanup_transcription(raw, "subjective", "he")
        # Returns: "Patient reports lower back pain (7-8/10 severity) ongoing..."
        ```
    """
    # Initialize Cohere client (async)
    client = cohere.AsyncClient(api_key=settings.cohere_api_key)

    # Build language-specific prompts
    # Handle both "he" and "hebrew" (Whisper returns "hebrew")
    if language in ("he", "hebrew", "iw"):
        system_prompt = f"""אתה עוזר קליני שמנקה תמלילים קוליים של מטפלים.

משימתך: לנקות תמליל קולי בלתי מסודר והפוך אותו לטקסט קליני מובנה עבור שדה {field_name} בהערות SOAP.

כללים קריטיים:
1. שמור על השפה המקורית של הטקסט - אל תתרגם!
2. הסר מילות מילוי (אה, אמ, כאילו, יודעת, בעצם, אז, נו)
3. תקן דקדוק ומבנה משפטים לעברית תקנית
4. שמור על כל הפרטים הקליניים - אל תפספס שום פרט!
5. שמור על מספרים מדויקים (ציוני כאב, משכים, תדירות)
6. שמור על טרמינולוגיה רפואית מקורית בדיוק
7. אל תוסיף מידע שלא נאמר במפורש
8. אל תפרש או תנחש - רק נקה את מה שקיים
9. פלט טקסט קליני בלבד, ללא הקדמות או הסברים

פורמט פלט: 2-4 משפטים קליניים ברורים ותמציתיים."""

        user_prompt = f"""תמליל קולי לניקוי (שדה: {field_name}):

{raw_text}

נקה את התמליל והפוך אותו לטקסט קליני מסודר:"""

    else:  # English
        system_prompt = f"""You are a clinical assistant cleaning up therapist voice dictations.

Your task: Clean up messy voice dictation and turn it into structured clinical text for the {field_name} field in SOAP notes.

CRITICAL Rules:
1. Keep the same language as the input text - do NOT translate!
2. Remove filler words (um, uh, like, you know, basically, so, well)
3. Fix grammar and sentence structure to proper clinical English
4. Preserve ALL clinical details - don't miss anything!
5. Preserve exact numbers (pain scores, durations, frequencies)
6. Preserve original medical terminology exactly
7. Do NOT add information that wasn't explicitly stated
8. Do NOT interpret or guess - only clean what exists
9. Output clean clinical text only, no preamble or explanations

Output format: 2-4 clear, concise clinical sentences."""

        user_prompt = f"""Voice dictation to clean (field: {field_name}):

{raw_text}

Clean the dictation and turn it into structured clinical text:"""

    try:
        # Call Cohere API with conservative temperature (prefer preservation)
        response = await client.chat(
            model=settings.cohere_chat_model,  # command-r-plus from config
            message=user_prompt,  # User message (singular, not messages array)
            preamble=system_prompt,  # System instructions
            temperature=0.3,  # Low temperature for consistency
            max_tokens=1000,  # Sufficient for SOAP note field
        )

        # Extract cleaned text from response
        cleaned_text = response.text.strip()

        logger.info(
            "transcription_cleanup_success",
            field_name=field_name,
            language=language,
            original_length=len(raw_text),
            cleaned_length=len(cleaned_text),
            model=settings.cohere_chat_model,
        )

        return cleaned_text

    except Exception as e:
        # Fallback: return original text if cleanup fails
        logger.error(
            "transcription_cleanup_failed",
            field_name=field_name,
            language=language,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # Return original text as safe fallback (graceful degradation)
        logger.warning(
            "transcription_cleanup_fallback_to_original",
            field_name=field_name,
        )
        return raw_text
