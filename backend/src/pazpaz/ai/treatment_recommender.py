"""
Treatment plan recommendation engine.

Extends ClinicalAgent with AI-powered treatment recommendations
based on SOAP notes and patient history (ADR 0002).

This module provides therapy-specific treatment recommendations using:
1. Therapy type detection (massage, physiotherapy, psychotherapy)
2. RAG-based patient context retrieval
3. LLM-powered recommendation generation with markdown formatting
4. Structured parsing and validation

Reuses 85% of existing ClinicalAgent infrastructure for RAG retrieval.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass

from pazpaz.ai.prompts import detect_language, get_treatment_prompt
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TreatmentRecommendation:
    """
    A single treatment recommendation from the AI agent.

    Attributes:
        recommendation_id: Unique identifier for this recommendation
        title: Brief title summarizing the recommendation
        description: Detailed treatment recommendation text
        therapy_type: Detected therapy type (massage, physiotherapy, psychotherapy, generic)
        evidence_type: Type of evidence used (workspace_patterns, clinical_guidelines, hybrid)
        similar_cases_count: Number of similar successful cases found (0 if none)
    """

    recommendation_id: uuid.UUID
    title: str
    description: str
    therapy_type: str
    evidence_type: str
    similar_cases_count: int


@dataclass
class RecommendationResponse:
    """
    Structured response from treatment recommendation generation.

    Attributes:
        recommendations: List of 1-2 treatment recommendations
        therapy_type: Detected therapy type
        language: Detected language of input
        retrieved_count: Number of similar cases retrieved
        processing_time_ms: Total processing time in milliseconds
    """

    recommendations: list[TreatmentRecommendation]
    therapy_type: str
    language: str
    retrieved_count: int
    processing_time_ms: int


class AgentError(Exception):
    """Exception raised when agent operations fail."""

    pass


class TreatmentRecommender:
    """
    Treatment plan recommender using LLM + patient context.

    Provides therapy-specific recommendations (massage, physiotherapy, psychotherapy)
    with markdown formatting and evidence-based sourcing.
    """

    def __init__(self, clinical_agent):
        """
        Initialize with a reference to the main ClinicalAgent.

        Args:
            clinical_agent: ClinicalAgent instance for querying patient context
        """
        self.agent = clinical_agent
        self.logger = get_logger(__name__)

    async def recommend_treatment_plan(
        self,
        workspace_id: uuid.UUID,
        subjective: str,
        objective: str,
        assessment: str,
        client_id: uuid.UUID | None = None,
    ) -> RecommendationResponse:
        """
        Generate treatment plan recommendations using LLM + patient context.

        This method extends the ClinicalAgent with treatment recommendation capabilities
        as specified in ADR 0002. It reuses the existing RAG infrastructure (85% code reuse)
        while adding therapy-specific recommendation generation.

        Process:
        1. Detect therapy type from SOAP terminology
        2. Get patient context (reuses existing query() method)
        3. Generate recommendations using therapy-specific LLM prompt
        4. Parse and structure recommendations

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            subjective: Subjective findings (S in SOAP)
            objective: Objective findings (O in SOAP)
            assessment: Clinical assessment (A in SOAP)
            client_id: Optional client ID for patient-specific context

        Returns:
            RecommendationResponse with 1-2 treatment recommendations

        Raises:
            AgentError: If recommendation generation fails
            ValueError: If parameters are invalid

        Example:
            >>> response = await agent.recommend_treatment_plan(
            ...     workspace_id=workspace_id,
            ...     subjective="Patient reports tight upper trapezius...",
            ...     objective="Palpation reveals trigger points...",
            ...     assessment="Myofascial pain syndrome...",
            ...     client_id=client_id,
            ... )
            >>> print(response.recommendations[0].description)
        """
        start_time = time.time()

        self.logger.info(
            "treatment_recommendation_started",
            workspace_id=str(workspace_id),
            client_id=str(client_id) if client_id else None,
            soa_length=len(subjective) + len(objective) + len(assessment),
        )

        try:
            # Step 1: Detect language from SOA
            combined_soa = f"{subjective} {objective} {assessment}"
            language = detect_language(combined_soa)

            # Step 2: Detect therapy type (simple keyword matching for MVP)
            therapy_type = self._detect_therapy_type_simple(
                subjective, objective, assessment
            )

            self.logger.debug(
                "therapy_type_detected",
                workspace_id=str(workspace_id),
                therapy_type=therapy_type,
                language=language,
            )

            # Step 3: Get patient context using existing RAG agent
            # Use actual SOA content as query to find semantically similar past sessions
            # This ensures we retrieve sessions with similar clinical presentations
            patient_context_query = (
                combined_soa  # Already contains "{subjective} {objective} {assessment}"
            )

            patient_context_response = await self.agent.query(
                workspace_id=workspace_id,
                query=patient_context_query,
                client_id=client_id,
                max_results=3,  # Limit to recent sessions
                min_similarity=0.3,  # Lower threshold to retrieve more context (same as AI Agent chat)
            )

            self.logger.debug(
                "patient_context_retrieved",
                workspace_id=str(workspace_id),
                context_length=len(patient_context_response.answer),
                sources_count=patient_context_response.retrieved_count,
            )

            # Step 4: Build recommendation prompt (language-aware)
            treatment_prompt = get_treatment_prompt(therapy_type)

            # Build user prompt in detected language
            if language == "he":
                # Hebrew prompt
                user_prompt = f"""**ממצאי המפגש הנוכחי (S/O/A):**

סובייקטיבי: {subjective}
אובייקטיבי: {objective}
הערכה: {assessment}

**היסטוריה קלינית של המטופל:**
{patient_context_response.answer if patient_context_response.retrieved_count > 0 else "לא קיימת היסטוריית מפגשים קודמים."}

**משימה:**
על סמך ממצאי המפגש הנוכחי והיסטוריית המטופל, ספק 1-2 המלצות טיפול ממוקדות לקטע התכנית (Plan).

**קריטי - פורמט תגובה (חובה לעקוב בדיוק):**
חובה להשתמש בפורמט המדויק הזה עם תוויות "כותרת:" ו"תיאור:":

המלצה 1:
כותרת: טיפול ידני להגבלת תנועה בגב התחתון
תיאור: **פרוטוקול טיפולי:** יישם **שחרור מיופשיאלי** לשרירים הפארה-ספינליים המותניים (L3-L5) עם לחץ מתמשך למשך 2-3 דקות. המשך עם **טיפול בנקודות טריגר** בנקודות רגישות מזוהות. **מעקב:** הערך מחדש ROM לאחר 3 מפגשים.

המלצה 2:
כותרת: תוכנית תרגילי בית
תיאור: **חינוך המטופל:** למד **תרגילי ייצוב ליבה** (plank, bird-dog) לביצוע יומי. התחל עם החזקות של 10 שניות, התקדם ל-30 שניות. **אזהרה:** עצור אם הכאב גובר מעבר לרמת הבסיס.

(הערה: בדוגמאות לעיל, כל סימני ה-**מודגש** נמצאים באותה שורה עם הטקסט - זה נדרש לעיבוד markdown נכון)

**הנחיות עיצוב Markdown לתיאור:**
- השתמש ב**מודגש** (כוכביות כפולות) למונחים קליניים מרכזיים - קריטי: כוכביות חייבות להיות באותה שורה עם הטקסט
  - נכון: **פרוטוקול טיפולי:** או **שחרור מיופשיאלי**
  - לא נכון: **\nפרוטוקול טיפולי\n** (אל תשים כוכביות בשורות נפרדות)
- השתמש ברשימות תבליטים (- או *) לפרוטוקולים רב-שלביים או רצפי טיפול
- השתמש בכותרות מדורים כמו **פרוטוקול טיפולי:**, **מעקב:**, **אזהרה:**
- שמור על תיאורים תמציתיים (2-3 משפטים)
- ללא מעברי שורה בין כוכביות פתיחה וסגירה

**התגובה שלך (עקוב אחר הפורמט לעיל בדיוק עם תוויות "כותרת:" ו"תיאור:"):**

המלצה 1:
כותרת: [הכותרת שלך כאן - טקסט פשוט, 5-10 מילים]
תיאור: [התיאור שלך בעיצוב markdown כאן עם מונחים **מודגשים**]

המלצה 2:
כותרת: [הכותרת שלך כאן - טקסט פשוט, 5-10 מילים]
תיאור: [התיאור שלך בעיצוב markdown כאן עם מונחים **מודגשים**]
"""
            else:
                # English prompt (default)
                user_prompt = f"""**Current Session S/O/A:**

Subjective: {subjective}
Objective: {objective}
Assessment: {assessment}

**Patient Clinical History:**
{patient_context_response.answer if patient_context_response.retrieved_count > 0 else "No previous session history available."}

**Task:**
Based on the current session findings and patient history, provide 1-2 focused treatment recommendations for the Plan section.

**CRITICAL - Response Format (MUST FOLLOW EXACTLY):**
You MUST use this EXACT format with "Title:" and "Description:" labels:

Recommendation 1:
Title: Manual Therapy for Lumbar Restriction
Description: **Treatment Protocol:** Apply **myofascial release** to lumbar paraspinals (L3-L5) using sustained pressure for 2-3 minutes. Follow with **trigger point therapy** at identified tender points. **Follow-up:** Reassess ROM after 3 sessions.

Recommendation 2:
Title: Home Exercise Program
Description: **Patient Education:** Teach **core stabilization exercises** (plank, bird-dog) to perform daily. Start with 10-second holds, progress to 30 seconds. **Caution:** Stop if pain increases beyond baseline level.

(NOTE: In the examples above, all **bold** markers are on the same line as the text - this is required for proper markdown rendering)

**Markdown Formatting Guidelines for Description:**
- Use **bold** (double asterisks) for key clinical terms - CRITICAL: asterisks MUST be on the SAME LINE as the text
  - CORRECT: **Treatment Protocol:** or **myofascial release**
  - WRONG: **\nTreatment Protocol\n** (do NOT put asterisks on separate lines)
- Use bullet lists (- or *) for multi-step protocols or treatment sequences
- Use section headers like **Treatment Protocol:**, **Follow-up:**, **Caution:**
- Keep descriptions concise (2-3 sentences)
- NO line breaks between opening and closing asterisks

**YOUR RESPONSE (follow format above EXACTLY with "Title:" and "Description:" labels):**

Recommendation 1:
Title: [your title here - plain text, 5-10 words]
Description: [your markdown-formatted description here with **bold** terms]

Recommendation 2:
Title: [your title here - plain text, 5-10 words]
Description: [your markdown-formatted description here with **bold** terms]
"""

            # Step 5: Generate recommendations using LLM
            self.logger.debug(
                "llm_generation_started",
                workspace_id=str(workspace_id),
                therapy_type=therapy_type,
            )

            (
                answer,
                tokens_used,
                llm_duration,
            ) = await self.agent._synthesize_answer_with_retry(
                system_prompt=treatment_prompt,
                user_prompt=user_prompt,
            )

            # Step 6: Parse LLM response into structured recommendations
            recommendations = self._parse_recommendations(
                answer,
                therapy_type=therapy_type,
                evidence_type=(
                    "hybrid"
                    if patient_context_response.retrieved_count > 0
                    else "clinical_guidelines"
                ),
                similar_cases_count=patient_context_response.retrieved_count,
            )

            processing_time = int((time.time() - start_time) * 1000)

            self.logger.info(
                "treatment_recommendation_completed",
                workspace_id=str(workspace_id),
                therapy_type=therapy_type,
                recommendations_count=len(recommendations),
                processing_time_ms=processing_time,
                tokens_used=tokens_used,
            )

            return RecommendationResponse(
                recommendations=recommendations,
                therapy_type=therapy_type,
                language=language,
                retrieved_count=patient_context_response.retrieved_count,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)

            self.logger.error(
                "treatment_recommendation_failed",
                workspace_id=str(workspace_id),
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time,
                exc_info=True,
            )

            raise AgentError(
                f"Failed to generate treatment recommendations: {e}"
            ) from e

    def _detect_therapy_type_simple(
        self, subjective: str, objective: str, assessment: str
    ) -> str:
        """
        Detect therapy type using simple keyword matching (MVP approach).

        This is a simplified detection method that uses keyword matching.
        Phase 2 can upgrade to LLM-based classification for better accuracy.

        Args:
            subjective: Subjective findings
            objective: Objective findings
            assessment: Clinical assessment

        Returns:
            Therapy type: "massage", "physiotherapy", "psychotherapy", or "generic"
        """
        combined_text = f"{subjective} {objective} {assessment}".lower()

        # Massage therapy keywords
        massage_keywords = [
            "massage",
            "trigger point",
            "myofascial",
            "deep tissue",
            "swedish",
            "pressure",
            "muscle tension",
            "כאבי שרירים",
            "עיסוי",
            "נקודות טריגר",
        ]

        # Physiotherapy keywords
        physio_keywords = [
            "rom",
            "range of motion",
            "exercise",
            "strength",
            "gait",
            "mobilization",
            "rehab",
            "טווח תנועה",
            "תרגילים",
            "שיקום",
            "כוח",
        ]

        # Psychotherapy keywords
        psycho_keywords = [
            "mood",
            "anxiety",
            "depression",
            "cbt",
            "dbt",
            "thoughts",
            "feelings",
            "coping",
            "חרדה",
            "דיכאון",
            "מצב רוח",
            "רגשות",
        ]

        # Count keyword matches
        massage_count = sum(1 for kw in massage_keywords if kw in combined_text)
        physio_count = sum(1 for kw in physio_keywords if kw in combined_text)
        psycho_count = sum(1 for kw in psycho_keywords if kw in combined_text)

        # Determine therapy type (highest count wins)
        max_count = max(massage_count, physio_count, psycho_count)

        if max_count == 0:
            return "generic"  # No clear match

        if massage_count == max_count:
            return "massage"
        elif physio_count == max_count:
            return "physiotherapy"
        elif psycho_count == max_count:
            return "psychotherapy"
        else:
            return "generic"

    def _parse_recommendations(
        self,
        llm_response: str,
        therapy_type: str,
        evidence_type: str,
        similar_cases_count: int,
    ) -> list[TreatmentRecommendation]:
        """
        Parse LLM response into structured treatment recommendations.

        Expects format:
        Recommendation 1:
        Title: [title]
        Description: [description]

        Args:
            llm_response: Raw LLM response text
            therapy_type: Detected therapy type
            evidence_type: Type of evidence used
            similar_cases_count: Number of similar cases retrieved

        Returns:
            List of TreatmentRecommendation objects (1-2 recommendations)
        """
        recommendations = []

        # Split by "Recommendation" or "המלצה" markers (bilingual support)
        sections = re.split(
            r"(?:^|\n)(?:Recommendation|המלצה)\s+\d+:\s*\n",
            llm_response,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        for section in sections[1:]:  # Skip first empty section
            section = section.strip()
            if not section:
                continue

            # Try to extract title and description with explicit labels (bilingual)
            # Match both "Title:" and "כותרת:"
            title_match = re.search(
                r"(?:Title|כותרת):\s*(.+?)(?:\n|$)", section, re.IGNORECASE
            )
            # Match both "Description:" and "תיאור:"
            desc_match = re.search(
                r"(?:Description|תיאור):\s*(.+?)(?:\n\n(?:Recommendation|המלצה)|\Z)",
                section,
                re.IGNORECASE | re.DOTALL,
            )

            if title_match and desc_match:
                title = title_match.group(1).strip()
                description = desc_match.group(1).strip()

                self.logger.debug(
                    "recommendation_parsed",
                    title=title,
                    description_length=len(description),
                )

                recommendations.append(
                    TreatmentRecommendation(
                        recommendation_id=uuid.uuid4(),
                        title=title,
                        description=description,
                        therapy_type=therapy_type,
                        evidence_type=evidence_type,
                        similar_cases_count=similar_cases_count,
                    )
                )
            else:
                # Fallback: Try to parse without explicit labels
                # Assume first line is title, rest is description
                lines = section.split("\n", 1)
                if len(lines) >= 2:
                    title = lines[0].strip()
                    # Remove "Title:" prefix if present
                    title = re.sub(r"^Title:\s*", "", title, flags=re.IGNORECASE)

                    description = lines[1].strip()
                    # Remove "Description:" prefix if present
                    description = re.sub(
                        r"^Description:\s*", "", description, flags=re.IGNORECASE
                    )

                    self.logger.warning(
                        "recommendation_parsed_fallback",
                        title=title,
                        description_length=len(description),
                        message="LLM did not use Title:/Description: format, using fallback parser",
                    )

                    recommendations.append(
                        TreatmentRecommendation(
                            recommendation_id=uuid.uuid4(),
                            title=title,
                            description=description,
                            therapy_type=therapy_type,
                            evidence_type=evidence_type,
                            similar_cases_count=similar_cases_count,
                        )
                    )

        # Final fallback: If parsing completely failed, log error but don't return malformed data
        if not recommendations:
            self.logger.error(
                "recommendation_parsing_failed",
                response_length=len(llm_response),
                response_preview=llm_response[:200],
            )
            # Return a single recommendation with the full response
            recommendations.append(
                TreatmentRecommendation(
                    recommendation_id=uuid.uuid4(),
                    title="Treatment Plan Recommendation",
                    description=llm_response.strip(),
                    therapy_type=therapy_type,
                    evidence_type=evidence_type,
                    similar_cases_count=similar_cases_count,
                )
            )

        # Clean up markdown formatting in descriptions
        for rec in recommendations:
            rec.description = self._clean_markdown(rec.description)

        # Limit to 2 recommendations
        return recommendations[:2]

    def _clean_markdown(self, text: str) -> str:
        """
        Clean up malformed markdown formatting.

        Fixes common issues like asterisks on separate lines.

        Args:
            text: Raw markdown text

        Returns:
            Cleaned markdown text
        """
        # Fix: ** on separate lines (e.g., "**\ntext\n**" -> "**text**")
        # Pattern: ** followed by newline, then text, then newline, then **
        text = re.sub(
            r"\*\*\s*\n\s*(.+?)\s*\n\s*\*\*", r"**\1**", text, flags=re.DOTALL
        )

        # Fix: ** at start of line with text continuing on same line, then ** on next line
        # Pattern: "**text\n**" -> "**text**"
        text = re.sub(r"\*\*([^\n*]+?)\s*\n\s*\*\*", r"**\1**", text)

        # Fix: ** at end of previous line, then text on new line, then **
        # Pattern: "**\ntext**" -> "**text**"
        text = re.sub(r"\*\*\s*\n\s*([^\n*]+?)\*\*", r"**\1**", text)

        return text.strip()
