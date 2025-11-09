"""Voice transcription API endpoints for SOAP notes.

This module implements secure voice-to-text transcription for clinical documentation:
- Hebrew and English support via OpenAI Whisper API
- Optional AI cleanup of messy dictations (filler word removal, grammar fixes)
- Rate limiting (60 requests/hour per workspace)
- Workspace isolation and audit logging
- No persistent audio storage (HIPAA compliance)

Endpoints:
- POST /api/v1/transcribe - Transcribe audio file to text
- POST /api/v1/transcribe/cleanup - Clean up messy transcription (optional)
"""

from __future__ import annotations

import redis.asyncio as redis
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.transcription_cleanup import cleanup_transcription
from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.redis import get_redis
from pazpaz.models.user import User
from pazpaz.schemas.transcription import (
    CleanupRequest,
    CleanupResponse,
    TranscriptionResponse,
)

router = APIRouter(tags=["transcription"])
logger = get_logger(__name__)


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    field_name: str = Form(...),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> TranscriptionResponse:
    """
    Transcribe audio file to text for SOAP note field.

    Process:
    1. Rate limit (60 requests/hour per workspace)
    2. Validate audio file (max 10MB, audio/* MIME)
    3. Call OpenAI Whisper API (Hebrew language)
    4. Return transcription text with metadata
    5. Audio never persisted (HIPAA compliance)

    Security:
    - Workspace-scoped rate limiting
    - No persistent audio storage (memory only)
    - Audit logging via middleware (automatic)
    - File validation (MIME type, size)

    Args:
        audio: Audio file (WebM, MP3, WAV, M4A, OGG, FLAC)
        field_name: SOAP field being dictated (subjective, objective, assessment, plan)
        current_user: Authenticated user (from JWT token)
        redis_client: Redis client for rate limiting
        db: Database session (for audit logging context)

    Returns:
        TranscriptionResponse with transcribed text, language, and duration

    Raises:
        HTTPException:
            - 400: Invalid file type or format
            - 429: Rate limit exceeded (60/hour)
            - 500: Transcription failed (OpenAI API error)

    Example:
        ```
        POST /api/v1/transcribe
        Content-Type: multipart/form-data

        audio: <audio file>
        field_name: subjective

        Response 200:
        {
            "text": "Patient reports lower back pain, 7/10 severity",
            "language": "he",
            "duration_seconds": 45.3
        }
        ```
    """
    workspace_id = current_user.workspace_id

    # 1. Rate limit (60 requests/hour per workspace)
    rate_limit_key = f"transcription:{workspace_id}"
    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=rate_limit_key,
        max_requests=60,
        window_seconds=3600,
    ):
        logger.warning(
            "transcription_rate_limit_exceeded",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 60 transcriptions per hour.",
        )

    # 2. Validate audio file MIME type
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        logger.warning(
            "transcription_invalid_mime_type",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            content_type=audio.content_type,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {audio.content_type}. Expected audio/* MIME type.",
        )

    # 3. Validate file size (10 MB max)
    # Read file content for size check and API call
    audio_content = await audio.read()
    file_size_mb = len(audio_content) / (1024 * 1024)

    if len(audio_content) > 10 * 1024 * 1024:  # 10 MB
        logger.warning(
            "transcription_file_too_large",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            file_size_mb=file_size_mb,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {file_size_mb:.1f} MB exceeds maximum of 10 MB.",
        )

    # 4. Call OpenAI Whisper API
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        logger.info(
            "transcription_started",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            field_name=field_name,
            file_size_mb=file_size_mb,
            content_type=audio.content_type,
        )

        # Call Whisper API with automatic language detection
        # Omitting language parameter enables auto-detection (Hebrew/English/etc.)
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(audio.filename, audio_content),
            # language parameter omitted for auto-detection
            response_format="verbose_json",  # Includes duration metadata
        )

        transcription = response.text
        duration = response.duration  # In seconds
        detected_language = response.language or "unknown"

        logger.info(
            "transcription_success",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            field_name=field_name,
            audio_duration=duration,
            transcription_length=len(transcription),
            detected_language=detected_language,
            model="whisper-1",
        )

        return TranscriptionResponse(
            text=transcription,
            language=detected_language,
            duration_seconds=duration,
        )

    except Exception as e:
        logger.error(
            "transcription_failed",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            field_name=field_name,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try again or type manually.",
        ) from e


@router.post("/transcribe/cleanup", response_model=CleanupResponse)
async def cleanup_transcription_text(
    cleanup_request: CleanupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CleanupResponse:
    """
    Clean up messy transcription text using AI.

    Optional post-processing step after transcription. Uses Cohere Command-R Plus
    to remove filler words, fix grammar, and structure text into clear clinical
    sentences while preserving 100% of clinical details.

    User sees before/after comparison and chooses which version to use.

    Args:
        cleanup_request: Contains raw_text, field_name, language
        current_user: Authenticated user (from JWT token)
        db: Database session (for audit logging context)

    Returns:
        CleanupResponse with both cleaned text and original text

    Raises:
        HTTPException:
            - 400: Invalid request (empty text, invalid field_name)
            - 500: Cleanup failed (Cohere API error, returns original text as fallback)

    Example:
        ```
        POST /api/v1/transcribe/cleanup
        Content-Type: application/json

        {
            "raw_text": "Uh, so Sarah came in, she's been having...",
            "field_name": "subjective",
            "language": "he"
        }

        Response 200:
        {
            "cleaned_text": "Patient reports lower back pain (7-8/10)...",
            "original_text": "Uh, so Sarah came in, she's been having..."
        }
        ```
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "transcription_cleanup_requested",
        user_id=str(current_user.id),
        workspace_id=str(workspace_id),
        field_name=cleanup_request.field_name,
        language=cleanup_request.language,
        text_length=len(cleanup_request.raw_text),
    )

    # Call AI cleanup service
    cleaned_text = await cleanup_transcription(
        raw_text=cleanup_request.raw_text,
        field_name=cleanup_request.field_name,
        language=cleanup_request.language,
    )

    return CleanupResponse(
        cleaned_text=cleaned_text,
        original_text=cleanup_request.raw_text,
    )
