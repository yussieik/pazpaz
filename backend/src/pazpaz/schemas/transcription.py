"""Pydantic schemas for voice transcription API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    """
    Response schema for audio transcription.

    Returns transcribed text from OpenAI Whisper API along with
    metadata about the transcription (language, duration).

    Used by POST /api/v1/transcribe endpoint.
    """

    text: str = Field(
        description="Transcribed text from audio",
        examples=["Patient reports lower back pain, 7/10 severity"],
    )
    language: str = Field(
        description="Detected language code (ISO 639-1, e.g., 'he', 'en')",
        examples=["he", "en"],
    )
    duration_seconds: float = Field(
        description="Audio duration in seconds",
        examples=[45.3],
    )


class CleanupRequest(BaseModel):
    """
    Request schema for AI cleanup of messy transcription text.

    Optional post-processing step after transcription. User can choose
    to clean up filler words and improve grammar while preserving all
    clinical details.

    Used by POST /api/v1/transcribe/cleanup endpoint.

    Validation:
    - raw_text: 1-10000 characters (reasonable SOAP note length)
    - field_name: Must be valid SOAP field
    - language: ISO 639-1 language code
    """

    raw_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Raw transcription text to clean up",
        examples=[
            "Uh, so Sarah came in today, she's been having this, you know, "
            "lower back pain for about two weeks now..."
        ],
    )
    field_name: str = Field(
        ...,
        description="SOAP field name (subjective, objective, assessment, plan)",
        examples=["subjective", "objective", "assessment", "plan"],
    )
    language: str = Field(
        default="he",
        description="Language code for cleanup prompts (he, en)",
        examples=["he", "en"],
    )


class CleanupResponse(BaseModel):
    """
    Response schema for AI cleanup service.

    Returns both cleaned text and original text so user can compare
    and choose which version to use.

    Used by POST /api/v1/transcribe/cleanup endpoint.
    """

    cleaned_text: str = Field(
        description="AI-cleaned transcription (filler words removed, grammar fixed)",
        examples=[
            "Patient reports lower back pain (7-8/10 severity) ongoing for two weeks. "
            "Pain worsens with bending. Onset after lifting her daughter."
        ],
    )
    original_text: str = Field(
        description="Original raw transcription (for comparison)",
        examples=[
            "Uh, so Sarah came in today, she's been having this, you know, "
            "lower back pain for about two weeks now..."
        ],
    )
