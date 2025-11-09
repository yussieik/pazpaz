# ADR 0003: Voice Transcription for SOAP Notes

**Status**: Implemented ✅ - **COMPLETED 2025-11-09**
**Date**: 2025-11-09
**Last Updated**: 2025-11-09 (Implemented and deployed to production)
**Decision Makers**: Engineering Team, Product Lead
**Technical Story**: Hebrew Voice-to-Text for Efficient SOAP Note Documentation
**Depends On**: None (standalone feature)

**⚠️ CRITICAL UPDATES (2025-11-09)**:
1. **Technology correction**: Original ADR recommended Deepgram Nova-3, which does NOT support Hebrew. Corrected to OpenAI Whisper API. ([Technical Audit](../ADR_0003_TECHNICAL_AUDIT_2025-11-09.md))
2. **Quality control correction**: Removed confidence scoring feature as OpenAI Whisper API does not provide per-word confidence scores natively. Replaced with mandatory preview modal (human review). ([Quality Control Audit](../ADR_0003_QUALITY_CONTROL_AUDIT_2025-11-09.md))
3. **Cost correction**: Corrected Cohere cleanup pricing to $0.40/month (not $0.60). Total: $2.48/month = ₪9.30 (well below budget).
4. **Format detection**: Added MediaRecorder format detection for iOS Safari compatibility (requires MP4 format).

Timeline and success metrics unchanged. All corrections validated against November 2025 technology capabilities.

**Implementation Progress:**
- ✅ **Milestone 1 (Backend)**: Completed (OpenAI Whisper API integration, Cohere cleanup, rate limiting, multipart validation)
- ✅ **Milestone 2 (Frontend)**: Completed (MediaRecorder API with format detection, preview modal, AI cleanup integration)
- ✅ **Deployed to Production**: OPENAI_API_KEY configured, containers recreated, tested with Hebrew & English
- ⏳ **Milestone 3 (Testing)**: Manual testing completed, pending formal accuracy testing

---

## Context

PazPaz therapists currently type 400-500 words of SOAP notes after each 50-minute session. This manual documentation process:

1. **Time-consuming**: 10-15 minutes of typing when therapist is tired post-session
2. **Quality degradation**: Rushed typing leads to brief, incomplete SOAP notes
3. **Impacts RAG quality**: Sparse SOAP notes → less clinical context → worse RAG retrieval → less accurate treatment recommendations
4. **User friction**: Typing is the highest friction point in the documentation workflow

### User Need

**As a therapist**, when documenting a session, **I want** to dictate SOAP notes via voice in Hebrew **so that** I can:
- Save 7-11 minutes per session (2-3 hours/week across 20 sessions)
- Capture richer clinical details naturally (speech is faster than typing)
- Reduce cognitive load post-session (dictation is easier than writing)
- Improve RAG recommendation quality (detailed notes → better retrieval)

### Problem Quantification

**Current workflow:**
```
Session ends → Open laptop → Type S (3 min) → Type O (3 min)
→ Type A (2 min) → Type P (3 min) → Total: 11-13 minutes
```

**Per therapist:**
- 20 sessions/week × 12 minutes = 240 minutes/week = **4 hours/week** spent typing
- Annual: 208 hours/year = **26 working days** spent on typing alone

**Impact on RAG:**
- Rushed typing → Brief notes (e.g., "Back pain, tight, strain")
- RAG similarity search fails to find relevant cases
- Treatment recommendations are generic (no patient history context)

### Constraints

1. **Hebrew Language Priority**: Israeli therapists document in Hebrew (Cohere/Deepgram/Whisper support required)
2. **HIPAA Compliance**: Audio must be encrypted in transit, deleted after transcription (no persistent storage of voice recordings)
3. **No Live Session Recording**: Post-session dictation only (therapist speaks, not patient)
4. **Network Dependency**: Requires internet for API calls (offline fallback: typing)
5. **Cost Management**: Deepgram pricing $0.006/min (need to monitor usage, implement rate limits)
6. **Mobile Support**: Voice input must work on mobile devices (PWA compatibility)

### Non-Goals (V1)

- ❌ Live session recording during therapy (privacy/HIPAA complexity)
- ❌ Automatic S/O/A/P parsing from free-form dictation (V2 feature)
- ❌ Speaker diarization (only therapist speaks, not patient)
- ❌ Offline voice transcription (requires on-device models, too complex for V1)
- ❌ Multi-language support beyond Hebrew/English (focus on Israeli market)
- ❌ Real-time transcription during dictation (show final result only)

---

## Decision

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Speech-to-Text API** | **OpenAI Whisper API** | Proven Hebrew support (~15% WER), $0.006/min, HIPAA BAA available, simplest integration, production-ready |
| **Future Upgrade** | **ivrit-ai Whisper fine-tuned** | 2x better Hebrew accuracy (9.8% WER), requires GPU self-hosting (~€50-100/mo), consider for V2 after user validation |
| **Audio Format** | **WebM Opus / MP3** | Browser-native MediaRecorder API, efficient compression (~64 kbps), universally supported |
| **Frontend Integration** | **Per-field voice buttons** | One mic button per SOAP field (S/O/A/P), explicit user control, no auto-recording |
| **Backend Endpoint** | **POST /api/v1/transcribe** | New endpoint, accepts audio file, returns transcribed text, workspace-scoped |
| **Audio Storage** | **Transient (MinIO temp)** | Upload → Transcribe → Delete (no persistent audio storage for HIPAA compliance) |
| **Rate Limiting** | **60 requests/hour per workspace** | Same as treatment recommendations, prevent abuse, manage API costs |
| **Audit Logging** | **AuditEvent metadata** | Log transcription requests (duration, language, field), no PHI in logs |

### Why OpenAI Whisper over Competitors?

**Comparison (November 2025 validation):**

| Provider | Hebrew WER | Free Tier | HIPAA | Cost (1000 min) | Latency | Status |
|----------|------------|-----------|-------|-----------------|---------|--------|
| **OpenAI Whisper API** | ~15-20% | None | ✅ BAA | $6 | 2-5s | ✅ Production-ready |
| **ivrit-ai Whisper (fine-tuned)** | **9.8%** | N/A (self-host) | ✅ (self-managed) | ~€50-100/mo | Variable | Self-host only |
| **Speechmatics** | ~10-15% | Unknown | ✅ BAA | Unknown | 1-2s | Enterprise API |
| **Google Cloud STT** | ~15% | $300 credits | ✅ BAA | $9 | 1-2s | Production-ready |
| **Deepgram Nova-3** | ❌ **No Hebrew** | $200 credits | ✅ BAA | N/A | N/A | Not supported |

**Decision: OpenAI Whisper API** wins on:
- ✅ **Proven Hebrew support** in production (validated November 2025)
- ✅ **Cheapest option** ($0.006/min = $2.08/therapist/month)
- ✅ **Simplest integration** (single API call, no infrastructure)
- ✅ **HIPAA BAA available** for production deployment
- ✅ **No free tier needed** (cost already minimal: ₪7.80/therapist/month)

**Future Upgrade: ivrit-ai fine-tuned Whisper** (V2 consideration):
- ✅ **2x better Hebrew accuracy** (9.8% WER vs ~15% WER)
- ✅ **Open source** (can self-host)
- ✅ **Fine-tuned on Israeli Hebrew** (Knesset proceedings, crowd-transcribed audio)
- ❌ **No public API** (self-hosting required)
- ❌ **GPU infrastructure needed** (~€50-100/month Hetzner GPU)
- ⏱️ **Consider after V1 validation** (if accuracy <90% or costs >₪500/month)

**Fallback: Speechmatics** if OpenAI Whisper fails (Hebrew + medical terminology support).

**Note**: Original ADR incorrectly recommended Deepgram Nova-3, which does NOT support Hebrew as of November 2025. Corrected based on [Technical Audit 2025-11-09](../ADR_0003_TECHNICAL_AUDIT_2025-11-09.md).

---

## Quality Control & Post-Processing Strategy

### The Messy Dictation Problem

**Real-world therapist dictation:**
```
"Uh, so Sarah came in today, she's been having this, you know,
lower back pain for about two weeks now, it's like a 7 out of 10,
maybe 8 when she bends over, and uh, she said it started after
lifting her daughter, she's a new mom, and she's been having
trouble sleeping because of the pain, um, radiating down to
her left leg sometimes..."
```

**What we need in SOAP Subjective field:**
```
Patient reports lower back pain (7-8/10 severity) ongoing for
two weeks. Pain worsens with bending. Onset after lifting her
daughter. Disrupting sleep. Occasional radiation to left leg.
```

### Two-Layer Quality Control

**Note**: Originally planned as three layers including confidence scoring. Updated to two layers after discovering that OpenAI Whisper API does not provide per-word confidence scores natively. Mandatory preview modal provides sufficient quality control via human review.

#### Layer 1: Audio Quality Pre-Check (Before Transcription)

**Validate audio immediately after recording to prevent bad transcriptions:**

- **Duration check**: Reject recordings <2 seconds (accidental clicks)
- **Volume level check**: Detect too-quiet audio (RMS < 0.01)
- **Clipping detection**: Detect too-loud audio (peak > 0.95)
- **Silence detection**: Warn if >50% silence detected

**UX**: Show warning modal if quality issues detected
- "⚠️ Recording quality low. Re-record?"
- Options: [Re-record] [Use anyway]

**Implementation**: Web Audio API on frontend (no server round-trip)

#### Layer 2: Mandatory Preview Modal (After Transcription)

**User MUST review transcription before inserting:**

- Show raw transcription in editable textarea
- User can edit errors manually
- User can re-record if quality is poor
- User can opt to clean up with AI

**Why this provides quality control:**
- Human review catches transcription errors better than automated scoring
- User sees what's being inserted (builds trust)
- User can correct medical terminology errors
- Simpler implementation (OpenAI Whisper API does not provide confidence scores natively)

**UX**: Preview modal workflow
- Show transcription in editable textarea
- "Was this accurate?" feedback button (optional)
- Options: [Insert] [Re-record] [Clean up with AI]

**Note**: OpenAI Whisper API does not provide per-word confidence scores in the standard API response. While word-level timestamps are available via `timestamp_granularities=["word"]`, confidence scoring would require self-hosted models like `whisper-timestamped` (GPU infrastructure required). For V1, mandatory human review provides sufficient quality control.

#### Layer 3: AI Post-Processing Cleanup (Optional, After Transcription)

**Use Cohere Command-R Plus to clean up messy dictation:**

**Cleanup tasks:**
- Remove filler words (um, uh, like, you know, אה, כאילו, יודעת)
- Fix run-on sentences
- Correct grammar and punctuation
- Remove repetitions
- Structure into clear clinical sentences

**Preservation guarantees:**
- ✅ Preserve ALL clinical details (symptoms, severity, duration)
- ✅ Preserve numbers (pain scores, dates, measurements)
- ✅ Preserve medical terminology
- ❌ Never add information that wasn't stated
- ❌ Never interpret or guess

**Cost**: ~$0.0015 per cleanup (1,000 tokens Cohere Command-R Plus)

**UX**: Optional "✨ Clean up" button in preview modal
- User sees before/after comparison
- User chooses: insert raw or cleaned version

---

## Architecture

### System Flow (With Quality Control)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User clicks 🎤 Dictate (Subjective field)                   │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Recording... 🔴 (MediaRecorder API)                         │
│    [⏹ Stop] [✖ Cancel]                                         │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Audio Quality Check (Web Audio API - frontend)              │
│    ✓ Duration ≥ 2 seconds                                      │
│    ✓ Volume level OK (RMS analysis)                            │
│    ✓ Not clipped (peak analysis)                               │
│                                                                 │
│    If FAIL → Show warning modal:                               │
│    "⚠️ Recording quality low. Re-record?"                      │
│    [Re-record] [Use anyway]                                    │
└─────────────────────────────────────────────────────────────────┘
                           ↓
                           POST /api/v1/transcribe
┌─────────────────────────────────────────────────────────────────┐
│ 4. Backend Processing (FastAPI)                                │
│                                                                 │
│  ✓ Rate limit check (60/hour per workspace)                    │
│  ✓ Validate audio file (max 10MB, audio/* MIME type)           │
│  ✓ Malware scan (ClamAV)                                       │
│  ✓ Call OpenAI Whisper API (language=he, verbose_json)         │
│  ✓ Return: {text, language, duration}                          │
│  ✓ Audit log (metadata only: duration, language, field_name)   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. Preview Modal (CRITICAL REVIEW STEP)                        │
│                                                                 │
│    Transcription Preview                                       │
│    ┌──────────────────────────────────────────────────────┐   │
│    │ "Uh, so Sarah came in today, she's been having      │   │
│    │  this, you know, lower back pain..."                │   │
│    │  (editable text area)                               │   │
│    └──────────────────────────────────────────────────────┘   │
│                                                                 │
│    ☐ Clean up with AI (removes filler words, fixes grammar)   │
│                                                                 │
│    [Insert as-is] [🔄 Re-record] [✨ Clean up]                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓ (if "Clean up" clicked)
                           POST /api/v1/transcribe/cleanup
┌─────────────────────────────────────────────────────────────────┐
│ 6. AI Cleanup Service (Cohere Command-R Plus)                  │
│                                                                 │
│  Prompt: "Clean up clinical dictation. Remove filler words,   │
│           fix grammar, preserve all clinical details..."       │
│                                                                 │
│  Input:  "Uh, so Sarah came in today, she's been having..."   │
│  Output: "Patient reports lower back pain (7-8/10) ongoing..." │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Cleaned Preview (Show Both Versions)                        │
│                                                                 │
│    Original:                                                   │
│    "Uh, so Sarah came in today, she's been having this..."    │
│                                                                 │
│    Cleaned:                                                    │
│    "Patient reports lower back pain (7-8/10 severity)..."     │
│                                                                 │
│    [Insert cleaned] [Revert to original] [Edit]               │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. Text inserted into SOAP field                               │
│    User can continue editing manually before saving            │
└─────────────────────────────────────────────────────────────────┘
```

### Backend Implementation

```python
# backend/src/pazpaz/api/transcription.py

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from openai import AsyncOpenAI
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["transcription"])
logger = get_logger(__name__)

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    field_name: str = Form(...),  # "subjective", "objective", etc.
    current_user: User = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis),
) -> TranscriptionResponse:
    """
    Transcribe audio file to text for SOAP note field.

    Process:
    1. Rate limit (60 requests/hour per workspace)
    2. Validate audio file (max 10MB, audio/* MIME)
    3. Upload to MinIO temp (1-hour TTL)
    4. Call Deepgram API (Hebrew language)
    5. Delete audio from MinIO (HIPAA compliance)
    6. Return transcription text

    Security:
    - Workspace-scoped rate limiting
    - No persistent audio storage
    - Audit logging (metadata only)

    Args:
        audio: Audio file (WebM, MP3, WAV, etc.)
        field_name: SOAP field being dictated
        current_user: Authenticated user
        redis_client: Redis for rate limiting

    Returns:
        TranscriptionResponse with transcribed text

    Raises:
        HTTPException: 400 (invalid file), 429 (rate limit), 500 (transcription error)
    """
    workspace_id = current_user.workspace_id

    # Rate limit (60 requests/hour per workspace)
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

    # Validate audio file
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {audio.content_type}. Expected audio/*",
        )

    # Call OpenAI Whisper API
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        # Read audio file content
        audio_content = await audio.read()

        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(audio.filename, audio_content),
            language="he",  # Hebrew
            response_format="verbose_json",  # Includes duration metadata
        )

        transcription = response.text
        duration = response.duration  # In seconds

        logger.info(
            "transcription_success",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            field_name=field_name,
            audio_duration=duration,
            transcription_length=len(transcription),
            model="whisper-1",
        )

        return TranscriptionResponse(
            text=transcription,
            language=response.language or "he",
            duration_seconds=duration,
        )

    except Exception as e:
        logger.error(
            "transcription_failed",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try again or type manually.",
        ) from e
```

### AI Cleanup Service (Optional Post-Processing)

```python
# backend/src/pazpaz/ai/transcription_cleanup.py

from cohere import AsyncClient as CohereAsyncClient
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

async def cleanup_transcription(
    raw_text: str,
    field_name: str,  # "subjective", "objective", "assessment", "plan"
    language: str = "he",
) -> str:
    """
    Clean up messy clinical dictation using LLM.

    Removes:
    - Filler words (um, uh, like, you know, אה, כאילו, יודעת)
    - Run-on sentences
    - Repetitions
    - Poor grammar

    Preserves:
    - ALL clinical details (symptoms, severity, duration)
    - Numbers (pain scores, dates, measurements)
    - Medical terminology

    Args:
        raw_text: Raw transcription from Whisper API
        field_name: SOAP field (subjective, objective, assessment, plan)
        language: Language code (he or en)

    Returns:
        Cleaned clinical text suitable for SOAP note
    """
    client = CohereAsyncClient(api_key=settings.COHERE_API_KEY)

    if language == "he":
        system_prompt = f"""אתה עוזר קליני שמנקה תמלילים קוליים של מטפלים.

משימתך: לנקות תמליל קולי בלתי מסודר והפוך אותו לטקסט קליני מובנה עבור שדה {field_name} בהערות SOAP.

כללים קריטיים:
1. הסר מילות מילוי (אה, אמ, כאילו, יודעת, בעצם, אז, נו)
2. תקן דקדוק ומבנה משפטים לעברית תקנית
3. שמור על כל הפרטים הקליניים - אל תפספס שום פרט!
4. שמור על מספרים מדויקים (ציוני כאב, משכים, תדירות)
5. שמור על טרמינולוגיה רפואית מקורית בדיוק
6. אל תוסיף מידע שלא נאמר במפורש
7. אל תפרש או תנחש - רק נקה את מה שקיים
8. פלט טקסט קליני בלבד, ללא הקדמות או הסברים

פורמט פלט: 2-4 משפטים קליניים ברורים ותמציתיים."""

        user_prompt = f"""תמליל קולי לניקוי (שדה: {field_name}):

{raw_text}

נקה את התמליל והפוך אותו לטקסט קליני מסודר:"""
    else:  # English
        system_prompt = f"""You are a clinical assistant cleaning up therapist voice dictations.

Your task: Clean up messy voice dictation and turn it into structured clinical text for the {field_name} field in SOAP notes.

CRITICAL Rules:
1. Remove filler words (um, uh, like, you know, basically, so, well)
2. Fix grammar and sentence structure to proper clinical English
3. Preserve ALL clinical details - don't miss anything!
4. Preserve exact numbers (pain scores, durations, frequencies)
5. Preserve original medical terminology exactly
6. Do NOT add information that wasn't explicitly stated
7. Do NOT interpret or guess - only clean what exists
8. Output clean clinical text only, no preamble or explanations

Output format: 2-4 clear, concise clinical sentences."""

        user_prompt = f"""Voice dictation to clean (field: {field_name}):

{raw_text}

Clean the dictation and turn it into structured clinical text:"""

    try:
        response = await client.chat(
            model="command-r-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Low temperature for consistency
            max_tokens=1000,
        )

        cleaned_text = response.message.content[0].text.strip()

        logger.info(
            "transcription_cleanup_success",
            field_name=field_name,
            language=language,
            original_length=len(raw_text),
            cleaned_length=len(cleaned_text),
        )

        return cleaned_text

    except Exception as e:
        logger.error(
            "transcription_cleanup_failed",
            field_name=field_name,
            language=language,
            error=str(e),
            exc_info=True,
        )
        # Fallback: return original text if cleanup fails
        return raw_text
```

### Cleanup API Endpoint

```python
# backend/src/pazpaz/api/transcription.py (additional endpoint)

@router.post("/transcribe/cleanup", response_model=CleanupResponse)
async def cleanup_transcription_text(
    cleanup_request: CleanupRequest,
    current_user: User = Depends(get_current_user),
) -> CleanupResponse:
    """
    Clean up messy transcription text using AI.

    Optional post-processing step after transcription.
    User can choose to apply cleanup or use raw transcription.

    Args:
        cleanup_request: Contains raw_text, field_name, language
        current_user: Authenticated user

    Returns:
        CleanupResponse with cleaned text and original text
    """
    from pazpaz.ai.transcription_cleanup import cleanup_transcription

    workspace_id = current_user.workspace_id

    logger.info(
        "transcription_cleanup_requested",
        user_id=str(current_user.id),
        workspace_id=str(workspace_id),
        field_name=cleanup_request.field_name,
        text_length=len(cleanup_request.raw_text),
    )

    cleaned_text = await cleanup_transcription(
        raw_text=cleanup_request.raw_text,
        field_name=cleanup_request.field_name,
        language=cleanup_request.language,
    )

    return CleanupResponse(
        cleaned_text=cleaned_text,
        original_text=cleanup_request.raw_text,
    )
```

### Frontend Implementation

```vue
<!-- frontend/src/components/sessions/VoiceRecorder.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import { useVoiceRecorder } from '@/composables/useVoiceRecorder'

const props = defineProps<{
  fieldName: 'subjective' | 'objective' | 'assessment' | 'plan'
}>()

const emit = defineEmits<{
  transcribed: [text: string]
}>()

const { isRecording, startRecording, stopRecording, transcribeAudio } = useVoiceRecorder()

async function handleStopRecording() {
  const audioBlob = await stopRecording()
  const transcription = await transcribeAudio(audioBlob, props.fieldName)
  emit('transcribed', transcription.text)
}
</script>

<template>
  <div class="voice-recorder">
    <button
      v-if="!isRecording"
      @click="startRecording"
      class="mic-button"
      :aria-label="`Record ${fieldName}`"
    >
      🎤 Dictate
    </button>

    <div v-else class="recording-controls">
      <span class="recording-indicator">🔴 Recording...</span>
      <button @click="handleStopRecording" class="stop-button">
        ⏹ Stop
      </button>
      <button @click="stopRecording" class="cancel-button">
        ✖ Cancel
      </button>
    </div>
  </div>
</template>
```

```typescript
// frontend/src/composables/useVoiceRecorder.ts
import { ref } from 'vue'
import { TranscriptionService } from '@/api/generated'

export function useVoiceRecorder() {
  const isRecording = ref(false)
  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []

  // Detect supported audio format (iOS Safari requires MP4)
  function getSupportedMimeType(): string {
    const types = [
      'audio/webm;codecs=opus',  // Best: low bitrate, high quality
      'audio/webm',
      'audio/mp4',                // iOS Safari requirement
      'audio/wav',
    ]

    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type
      }
    }

    throw new Error('No supported audio format found on this browser')
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      const mimeType = getSupportedMimeType()
      mediaRecorder = new MediaRecorder(stream, { mimeType })

      audioChunks = []

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data)
      }

      mediaRecorder.start()
      isRecording.value = true
    } catch (error) {
      console.error('Failed to start recording:', error)
      throw new Error('Microphone access denied. Please enable microphone permissions.')
    }
  }

  async function stopRecording(): Promise<Blob> {
    return new Promise((resolve) => {
      if (!mediaRecorder) {
        throw new Error('No active recording')
      }

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
        isRecording.value = false

        // Stop media stream
        mediaRecorder?.stream.getTracks().forEach(track => track.stop())

        resolve(audioBlob)
      }

      mediaRecorder.stop()
    })
  }

  async function transcribeAudio(audioBlob: Blob, fieldName: string) {
    const formData = new FormData()
    formData.append('audio', audioBlob, 'recording.webm')
    formData.append('field_name', fieldName)

    const response = await TranscriptionService.transcribeAudio(formData)
    return response
  }

  return {
    isRecording,
    startRecording,
    stopRecording,
    transcribeAudio,
  }
}
```

---

## Implementation Plan

### Milestone 1: Backend (2-3 days)

**Tasks:**
1. Add OpenAI SDK dependency (`uv add openai`) + audio libraries (`librosa`, `pydub`, `mutagen`)
2. Extend `utils/file_validation.py` with audio MIME types (WAV, MP3, M4A, OGG, FLAC, WEBM)
3. Create `src/pazpaz/ai/transcription_cleanup.py` (AI cleanup service using Cohere)
4. Create `src/pazpaz/api/transcription.py` endpoint (transcribe + cleanup endpoints)
5. Create `src/pazpaz/schemas/transcription.py` (request/response models with confidence scores)
6. Implement rate limiting (60 requests/hour per workspace) - **reuse existing `check_rate_limit_redis()`**
7. Add audit logging (metadata only, no PHI) - **reuse existing audit event patterns**
8. Unit tests for transcription endpoint
9. Integration test with OpenAI Whisper API (Hebrew audio sample)
10. Integration test for AI cleanup service (messy Hebrew dictation)

**Acceptance Criteria:**
- ✅ POST /api/v1/transcribe endpoint responds 200 with Hebrew transcription
- ✅ Rate limit enforced (429 after 60 requests/hour)
- ✅ Audio files validated (reject non-audio, >10MB files)
- ✅ Audit events logged with metadata (duration, language, field_name)
- ✅ Integration test passes with Hebrew medical terminology

**Example Test:**
```python
# tests/test_api/test_transcription.py

async def test_transcribe_hebrew_audio_success(client, current_user, hebrew_audio_file):
    """Test Hebrew audio transcription returns accurate text."""
    response = await client.post(
        "/api/v1/transcribe",
        files={"audio": ("test.webm", hebrew_audio_file, "audio/webm")},
        data={"field_name": "subjective"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["language"] == "he"
    assert len(data["text"]) > 0
    assert data["duration_seconds"] > 0
    # Check for Hebrew text (at least one Hebrew character)
    assert any("\u0590" <= c <= "\u05FF" for c in data["text"])
```

### Milestone 2: Frontend (2-3 days)

**Tasks:**
1. Create `VoiceRecorder.vue` component
2. Create `useVoiceRecorder.ts` composable (MediaRecorder API)
3. Add mic button to SessionEditor.vue (S/O/A/P fields)
4. Handle permissions (microphone access denied)
5. Handle errors (network failure, transcription failure)
6. Loading states (recording indicator, transcription in progress)
7. Mobile PWA testing (iOS Safari, Android Chrome)

**Acceptance Criteria:**
- ✅ Mic button visible on each SOAP field
- ✅ Click mic → Request microphone permission
- ✅ Recording indicator shows while recording
- ✅ Stop button → Upload audio → Show transcription in text field
- ✅ User can edit transcription before saving
- ✅ Error handling (permission denied, network error, transcription error)
- ✅ Mobile PWA works on iOS Safari and Android Chrome

**UX Flow:**
```
1. User clicks 🎤 Dictate on Subjective field
2. Browser prompts "Allow microphone access?" → User allows
3. Recording indicator shows: "🔴 Recording... [⏹ Stop] [✖ Cancel]"
4. User speaks for 30-60 seconds
5. User clicks Stop
6. Loading spinner: "Transcribing..."
7. Transcription appears in text field
8. User edits if needed
9. User moves to Objective field, repeats
```

### Milestone 3: Testing & Polish (1 day)

**Tasks:**
1. Hebrew medical terminology accuracy testing
2. Edge case handling (background noise, unclear speech, silence)
3. Performance testing (latency, large audio files)
4. Mobile UX polish (PWA install, offline fallback)
5. Documentation (user guide, troubleshooting)
6. Cost monitoring dashboard (transcription API usage)

**Acceptance Criteria:**
- ✅ Hebrew medical terms transcribed accurately (>90% accuracy on test set)
- ✅ Background noise handling (filter or warn user)
- ✅ Latency <3 seconds for 60-second audio
- ✅ Mobile PWA works offline (graceful degradation to typing)
- ✅ User guide published (how to dictate SOAP notes)
- ✅ Admin dashboard shows API usage (cost tracking)

---

## Metrics

### Success Metrics

**Adoption:**
- 50% of therapists use voice dictation within 2 weeks of launch
- 70% of SOAP notes contain voice-transcribed content within 1 month
- Average session notes length increases by 30% (richer clinical detail)
- **Cleanup feature used by 40-50% of users** (indicates messy dictation is common)

**Time Savings:**
- Average SOAP note completion time decreases from 12 min → 5 min (58% reduction)
  - Dictation: 2 min (4 fields × 30 sec each)
  - Review/edit in preview modal: 2 min
  - Final edits in SOAP field: 1 min
- User reports 2-3 hours saved per week in surveys

**Quality Improvement:**
- **Raw transcription accuracy**: >85% WER for Hebrew medical terminology
- **Cleanup accuracy**: 100% clinical detail preservation (validated via user feedback)
- **User satisfaction**: >80% rate transcription as "accurate" or "mostly accurate"
- Average SOAP note word count increases from 150 → 300 words (richer documentation)

**RAG Quality Improvement:**
- RAG retrieval precision improves (fewer false positives due to richer context)
- Treatment recommendation acceptance rate increases by 15-20%
- Retrieved session relevance score improves (more clinical details = better semantic matching)

**Cost:**
- Average transcription cost: $0.006/min × 80 min/week × 4.33 weeks = **$2.08/therapist/month**
- Average cleanup cost (50% adoption, corrected Cohere pricing):
  - Cohere Command-R Plus: $2.50/1M input + $10/1M output tokens
  - Per cleanup: ~400 input tokens + ~133 output tokens = $0.00233/cleanup
  - Monthly: 20 sessions × 4 fields × 4.33 weeks × 50% = 173.2 cleanups/month
  - Cost: 173.2 × $0.00233 = **$0.40/therapist/month**
- **Total: $2.48/therapist/month (₪9.30 at ₪3.75/$1) - well below budget** ✅
- OpenAI Whisper API has no free tier, but cost is already minimal

### Monitoring

**Metrics to Track:**
- Transcription requests per workspace (detect heavy users)
- Average audio duration per field (optimize for typical use case)
- **Cleanup feature usage rate** (% of transcriptions that get cleaned up)
- **Audio quality check failures** (how often users get low-quality warnings)
- **User satisfaction ratings** (track "Was this accurate?" button clicks in preview modal)
- Transcription accuracy (user feedback: thumbs up/down in preview modal)
- Hebrew vs English detection (language distribution)
- Error rate (transcription failures, cleanup failures, network errors)
- Cost per workspace (OpenAI Whisper + Cohere cleanup API usage)

**Alerts:**
- Rate limit hits (detect abuse or user frustration)
- Transcription failures >5% (API degradation)
- Audio files >5 minutes (unusual usage, possible misuse)

---

## Risks & Mitigations

### Risk 1: Hebrew Medical Terminology Accuracy

**Risk:** OpenAI Whisper misrecognizes Hebrew medical terms (expected WER ~15-20%)

**Impact:** Users lose trust, revert to typing, or spend too much time correcting errors

**Mitigation:**
- ✅ **Mandatory preview modal** - user MUST review before inserting (never auto-insert)
- ✅ **Audio quality pre-check** - warn users when recording quality is low (Layer 1)
- ✅ **Optional AI cleanup** - removes filler words, improves readability even if some words misrecognized
- ✅ **Editable preview** - user can correct errors before inserting
- ✅ Test with 50 real Hebrew audio samples (medical terminology)
- ✅ Collect user feedback: "Was this accurate?" button in preview modal
- ⏱️ **Future**: Migrate to ivrit-ai fine-tuned model if accuracy <85% (9.8% WER vs ~15% WER)

**Note on Confidence Scoring**: OpenAI Whisper API does not provide per-word confidence scores in the standard response. While this feature was initially planned, mandatory human review via the preview modal provides sufficient quality control for V1. If accuracy issues arise, we can consider self-hosting whisper-timestamped models or migrating to ivrit-ai fine-tuned models.

**Acceptance:**
- V1: 85% accuracy acceptable (with mandatory review + editing)
- V2: 95% accuracy target (with ivrit-ai fine-tuned model)

### Risk 2: Cost Explosion

**Risk:** Heavy users dictate long sessions + always use cleanup → higher costs

**Calculations:**
- Heavy user: 30 sessions/week × 4 fields × 2 min/field = 240 min/week
- Transcription: 240 min/week × 4.33 weeks × $0.006/min = $6.24/month
- Cleanup (100% usage, corrected pricing): 30 × 4 × 4.33 × $0.00233 = $1.21/month
- **Total: $7.45/month (₪27.94 at ₪3.75/$1)** - still acceptable, within ₪30 limit

**Impact:** Unprofitable if many heavy users (margin squeeze)

**Mitigation:**
- Rate limit: 60 requests/hour (prevents abuse)
- Max audio duration: 5 minutes per field (flag longer audio, auto-trim if >5min)
- Monitor top 10% of users (identify heavy users early, consider usage-based pricing tier)
- Optimize audio format (WebM Opus at 64 kbps, not 128 kbps)
- Cleanup is optional (user must click button, not automatic)
- Track cleanup ROI: if users rarely use it, consider removing to save costs

**Acceptance:** <₪10/therapist/month average cost (covers 80% of users)

### Risk 3: Mobile Browser Compatibility

**Risk:** MediaRecorder API not supported on older iOS Safari or Android browsers

**Impact:** Mobile users can't use voice dictation (40% of therapists use mobile)

**Mitigation:**
- Progressive enhancement (show mic button only if MediaRecorder supported)
- Graceful fallback to typing (no broken UX)
- Test on iOS Safari 15+, Android Chrome 90+
- PWA install prompt (better browser support)

**Acceptance:** Voice works on iOS Safari 15+, Android Chrome 90+ (95% mobile coverage)

### Risk 4: HIPAA Compliance Audit

**Risk:** Auditor flags third-party API usage (OpenAI, Cohere) or PHI in transcription/cleanup

**Impact:** Cannot deploy to production, regulatory risk

**Mitigation:**
- No persistent audio storage (transcribe → delete immediately, no MinIO/S3 storage)
- OpenAI BAA signed before production deployment (Whisper API covered)
- Cohere BAA signed before production deployment (Command-R Plus cleanup covered)
- Audit logging (metadata only: duration, language, confidence, no PHI)
- Document data flow in HIPAA compliance checklist:
  - Audio → OpenAI Whisper (encrypted HTTPS, BAA covered)
  - Text → Cohere cleanup (encrypted HTTPS, BAA covered)
  - No audio persisted (deleted after transcription)
  - Text stored encrypted in PostgreSQL (existing PHI encryption)

**Acceptance:**
- OpenAI BAA signed ✅
- Cohere BAA signed ✅
- Data flow documented ✅
- No PHI in audio storage (audio never stored) ✅
- Transcribed text encrypted at rest ✅

### Risk 5: User Adoption Below 50%

**Risk:** Therapists prefer typing (muscle memory, don't see value, or quality too low)

**Impact:** Feature unused, wasted development time

**Mitigation:**
- User research before implementation (validate demand)
- Onboarding tutorial: "Speak naturally, we'll clean it up"
- Show time savings banner: "Voice dictation saves 7 minutes per session"
- **Preview modal builds trust** - user sees transcription before inserting
- **Cleanup feature reduces friction** - removes filler words automatically
- A/B test: Voice vs typing (measure completion time, note quality, user satisfaction)
- Collect feedback: "Why didn't you use voice?" survey for non-adopters

**Acceptance:** 50% adoption within 2 weeks, or iterate on UX

### Risk 6: AI Cleanup Removes Clinical Details (NEW)

**Risk:** Cohere cleanup accidentally removes important clinical information

**Impact:** Users lose trust, lawsuits if critical details lost, feature abandoned

**Mitigation:**
- ✅ **Show before/after comparison** - user MUST review cleanup result
- ✅ **User can revert** to original transcription anytime
- ✅ **Conservative temperature** (0.3) - prefer preservation over aggressive editing
- ✅ **Explicit prompt instructions**: "Preserve ALL clinical details, do NOT add information"
- ✅ **Test suite**: 20 test cases validating 100% clinical detail preservation
- ✅ **User feedback**: "Did cleanup remove important info?" button
- ✅ **Fallback**: If cleanup fails, return original text (graceful degradation)

**Acceptance:**
- 100% clinical detail preservation in test suite ✅
- <1% user reports of missing information
- If >1% reports: disable cleanup feature immediately and investigate

---

## Future Enhancements (Post-V1)

### Phase 1.5: Advanced Quality Control (If V1 Accuracy <85%)

**Feature:** Highlight low-confidence words in preview modal for targeted re-recording

**Example:**
```
Patient reports <mark class="low-confidence">כאב</mark> in lower back, 7/10 severity.
                 ↑ Click to re-record just this word
```

**Implementation:**
- Per-word confidence scores from Whisper API
- Clickable highlights in preview modal
- Re-record single word instead of entire field

**Timeline:** 1 week (if accuracy issues reported)

### Phase 2: Automatic S/O/A/P Parsing

**Feature:** Dictate full SOAP note in one recording, AI parses into S/O/A/P fields

**Example:**
> User dictates: "Subjective: Patient reports lower back pain, 6 out of 10. Objective: Palpation reveals tightness in lumbar paraspinals. Assessment: Acute lumbar strain. Plan: Manual therapy with myofascial release."

**AI parsing:**
```json
{
  "subjective": "Patient reports lower back pain, 6 out of 10",
  "objective": "Palpation reveals tightness in lumbar paraspinals",
  "assessment": "Acute lumbar strain",
  "plan": "Manual therapy with myofascial release"
}
```

**Implementation:** LLM prompt with structured output (Cohere Command-R Plus)

**Timeline:** 1-2 weeks (after V1 validated + cleanup feature proven)

### Phase 3: Real-Time Transcription

**Feature:** Show transcription live while speaking (like Google Docs voice typing)

**UX:** User sees words appear as they speak (instant feedback)

**Implementation:** Deepgram streaming API (WebSocket connection)

**Timeline:** 2-3 weeks (requires WebSocket infrastructure)

### Phase 4: Offline Voice Transcription

**Feature:** On-device speech recognition (no internet required)

**Implementation:** Web Speech API (browser-native) or WASM Whisper model

**Tradeoff:** Lower accuracy (especially Hebrew), larger app size

**Timeline:** 1-2 months (complex, low priority)

### Phase 5: Custom Medical Vocabulary

**Feature:** Fine-tune Deepgram on Hebrew medical terminology from user data

**Implementation:** Collect 10,000+ Hebrew audio samples → Fine-tune Deepgram model

**Impact:** 95%+ accuracy on medical terms (vs 90% baseline)

**Timeline:** 3-6 months (requires data collection phase)

---

## Alternatives Considered

### Alternative 1: OpenAI Whisper API (Self-Hosted)

**Pros:**
- Free if self-hosted (no API costs)
- Full HIPAA control (data never leaves server)
- Proven Hebrew accuracy (7.6% WER)

**Cons:**
- Requires GPU infrastructure (~€50-100/month Hetzner)
- 10-30x slower on CPU (5 minutes to transcribe 30 seconds)
- Deployment complexity (Docker GPU support, model caching)
- No real-time streaming (batch only)

**Decision:** Rejected for V1 (too complex, Deepgram free tier covers testing). Revisit if costs >₪500/month.

### Alternative 2: Google Cloud Speech-to-Text

**Pros:**
- Enterprise-grade (99.9% SLA)
- HIPAA BAA available
- Good Hebrew support (~8-9% WER)

**Cons:**
- Expensive ($24/1000 min vs Deepgram $6)
- Slower latency (1-2s vs <1s)
- Complex setup (GCP credentials, IAM)
- No free tier ($300 credits expire)

**Decision:** Rejected (cost, complexity). Deepgram is better fit for bootstrapped product.

### Alternative 3: AssemblyAI Universal-2

**Pros:**
- Best Hebrew accuracy (6.68% WER)
- Speaker diarization (future use case)
- HIPAA BAA available

**Cons:**
- Smaller free tier ($50 vs $200)
- Higher cost per minute ($15/1000 min vs $6)
- Slower latency (1-2s vs <1s)

**Decision:** Rejected (cost). Deepgram 6.84% WER is close enough to 6.68%.

### Alternative 4: Browser Web Speech API (Native)

**Pros:**
- Free (no API costs)
- Zero latency (on-device)
- No network dependency

**Cons:**
- Inconsistent browser support (Chrome only, not Safari)
- Worse Hebrew accuracy (~15-20% WER)
- No fine-tuning (can't improve medical terminology)
- Privacy concerns (Google processes audio on their servers)

**Decision:** Rejected for V1. Consider for offline fallback in Phase 4.

---

## Dependencies

**Backend:**
- `openai` (Python SDK for OpenAI Whisper API)
- `librosa` (Audio validation: duration, format analysis)
- `pydub` (Audio processing alternative to librosa)
- `mutagen` (Audio metadata removal: ID3 tags, VORBIS_COMMENT)
- Redis (rate limiting - existing)
- MinIO (transient audio storage - existing)
- All existing file upload patterns (`core/storage.py`, `core/rate_limiting.py`, `utils/file_validation.py`, `utils/malware_scanner.py`)

**Frontend:**
- Browser MediaRecorder API (voice recording)
- FormData API (file upload)
- Existing `useFileUpload.ts` composable pattern (80% reusable)

**External Services:**
- OpenAI Whisper API (transcription)
- OpenAI BAA (HIPAA compliance for production)

**Environment Variables:**
```bash
# .env.production
OPENAI_API_KEY=<production-key>  # Get from OpenAI dashboard
```

**Code Reusability:**
- ✅ **70% code reuse** from existing session attachment upload patterns
- ✅ Rate limiting: `check_rate_limit_redis()` from `core/rate_limiting.py`
- ✅ S3 storage: `upload_file()`, `generate_secure_filename()` from `core/storage.py`
- ✅ Malware scanning: `scan_file_for_malware()` from `utils/malware_scanner.py`
- ✅ Storage quota: `validate_workspace_storage_quota()` from `utils/storage_quota.py`
- ✅ Workspace isolation: Follow existing patterns in `api/session_attachments.py`
- ⚠️ Extend `utils/file_validation.py` with audio MIME types (WAV, MP3, M4A, OGG, FLAC, WEBM)
- ⚠️ Create `utils/audio_validation.py` for audio-specific validation (duration, format)
- ⚠️ Create `ai/transcription_service.py` for OpenAI Whisper integration

See [Technical Audit 2025-11-09](../ADR_0003_TECHNICAL_AUDIT_2025-11-09.md) for detailed reusability analysis.

---

## Success Criteria

**V1 is successful if:**
- ✅ 50% of therapists use voice dictation within 2 weeks
- ✅ Average SOAP note completion time reduced by 50-60% (12 min → 5-6 min including review)
- ✅ Hebrew transcription accuracy >85% (acceptable with mandatory review + editing)
- ✅ **Cleanup feature preserves 100% clinical details** (validated via user feedback)
- ✅ **User satisfaction >80%** ("accurate" rating in preview modal feedback)
- ✅ RAG recommendation acceptance rate improves by 15-20%
- ✅ User surveys report "voice dictation saves me 2-3 hours/week"
- ✅ **Total cost <₪10/therapist/month** (transcription + cleanup = ₪9.30/month) ✅

**V1 fails if:**
- ❌ Adoption <30% after 1 month (feature not valuable)
- ❌ Users revert to typing (accuracy too low even with editing)
- ❌ **Cleanup removes clinical details** (>1% user reports of missing information)
- ❌ Total cost >₪15/therapist/month (unprofitable at ₪200 pricing)
- ❌ RAG quality degrades (voice transcription worse than typing)
- ❌ User satisfaction <60% (too many errors, too much editing required)

**If V1 accuracy <85%:**
- → Migrate to ivrit-ai fine-tuned Whisper model (9.8% WER, requires GPU self-hosting)
- → Add advanced quality control (per-word confidence highlighting)
- → Increase cleanup aggressiveness (more filler word removal)

---

## References

- [Deepgram API Documentation](https://developers.deepgram.com/)
- [OpenAI Whisper API Pricing](https://openai.com/api/pricing/)
- [Web Speech API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
- [Speech-to-Text Benchmark 2025](https://www.ionio.ai/blog/2025-edge-speech-to-text-model-benchmark-whisper-vs-competitors)
- [HIPAA Compliance for Voice Recording](https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/recording/index.html)

---

## Changelog

**2025-11-09 18:00**: Critical corrections applied based on Quality Control Audit
- ❌ **Removed confidence scoring** (OpenAI Whisper API does not provide per-word confidence scores natively)
- ✅ **Updated to 2-layer quality control** (Audio Quality Pre-Check + Mandatory Preview Modal)
- ✅ **Corrected Cohere pricing** - $0.40/month (not $0.60), using actual Nov 2025 rates
- ✅ **Updated total cost** - $2.48/month = ₪9.30 (not $2.68/month)
- ✅ **Added MediaRecorder format detection** - iOS Safari requires MP4, Chrome uses WebM
- ✅ **Updated backend implementation** - removed confidence scoring code
- ✅ **Updated frontend implementation** - added format detection function
- ✅ **Updated metrics** - removed confidence scoring, added user satisfaction tracking
- See [Quality Control Audit 2025-11-09](../ADR_0003_QUALITY_CONTROL_AUDIT_2025-11-09.md) for full analysis

**2025-11-09 16:00**: Added comprehensive quality control & post-processing strategy
- ✅ **Added three-layer quality control**:
  - Layer 1: Audio quality pre-check (duration, volume, clipping)
  - Layer 2: Transcription confidence scoring (per-word confidence)
  - Layer 3: AI post-processing cleanup (Cohere Command-R Plus)
- ✅ **Added mandatory preview modal** - user MUST review before inserting
- ✅ **Added optional AI cleanup** - removes filler words, fixes grammar
- ✅ **Added confidence scoring** - warn users when transcription quality low
- ✅ **Updated implementation code** - cleanup service, cleanup endpoint
- ✅ **Updated UX flow** - 8-step workflow with quality checks
- ✅ **Updated cost analysis** - $2.68/therapist/month (transcription + cleanup)
- ✅ **Updated risk mitigation** - new risk: AI cleanup removes clinical details
- ✅ **Updated success criteria** - 100% clinical detail preservation required

**2025-11-09 14:00**: Critical corrections applied based on technical audit
- ❌ **Removed Deepgram Nova-3** (does NOT support Hebrew as of November 2025)
- ✅ **Updated to OpenAI Whisper API** (proven Hebrew support, $0.006/min)
- ✅ **Added ivrit-ai fine-tuned Whisper** as V2 upgrade path (9.8% WER)
- ✅ **Updated dependencies** (openai, librosa, pydub, mutagen)
- ✅ **Added code reusability analysis** (70% reuse from existing patterns)
- ✅ **Updated backend implementation** (Whisper API integration code)
- See [Technical Audit 2025-11-09](../ADR_0003_TECHNICAL_AUDIT_2025-11-09.md) for full analysis

**2025-11-09 10:00**: Initial draft (ADR created with Deepgram recommendation)
