"""Pydantic schemas for Treatment Recommendation API (ADR 0002)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class TreatmentRecommendationRequest(BaseModel):
    """
    Request schema for treatment recommendation endpoint.

    SECURITY: workspace_id is NOT accepted from client requests.
    It is automatically injected from the authenticated user's session.
    This prevents workspace injection vulnerabilities.

    Attributes:
        subjective: Subjective findings (S in SOAP)
        objective: Objective findings (O in SOAP)
        assessment: Clinical assessment (A in SOAP)
        client_id: Optional client ID for patient-specific context
    """

    subjective: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Subjective findings (S in SOAP)",
    )
    objective: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Objective findings (O in SOAP)",
    )
    assessment: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Clinical assessment (A in SOAP)",
    )
    client_id: uuid.UUID | None = Field(
        None,
        description="Optional: Client ID for patient-specific context",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "subjective": "Patient reports tight upper trapezius and neck pain, 6/10 severity",
                    "objective": "Palpation reveals trigger points in upper trap, limited cervical ROM",
                    "assessment": "Myofascial pain syndrome, upper trapezius",
                    "client_id": "123e4567-e89b-12d3-a456-426614174000",
                },
                {
                    "subjective": "Patient reports anxiety about work presentation",
                    "objective": "Elevated heart rate, tense posture, rapid speech",
                    "assessment": "Situational anxiety, stress management needed",
                },
            ]
        }
    )


class TreatmentRecommendationItem(BaseModel):
    """
    Individual treatment recommendation.

    Attributes:
        recommendation_id: Unique identifier for this recommendation
        title: Brief title summarizing the recommendation (5-10 words)
        description: Detailed treatment recommendation text (2-3 sentences)
        therapy_type: Detected therapy type (massage, physiotherapy, psychotherapy, generic)
        evidence_type: Type of evidence used (workspace_patterns, clinical_guidelines, hybrid)
        similar_cases_count: Number of similar successful cases found (0 if none)
    """

    recommendation_id: uuid.UUID = Field(
        ...,
        description="Unique identifier for this recommendation",
    )
    title: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="Brief title (5-10 words)",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed recommendation (2-3 sentences)",
    )
    therapy_type: str = Field(
        ...,
        pattern="^(massage|physiotherapy|psychotherapy|generic)$",
        description="Detected therapy type",
    )
    evidence_type: str = Field(
        ...,
        pattern="^(workspace_patterns|clinical_guidelines|hybrid)$",
        description="Type of evidence used",
    )
    similar_cases_count: int = Field(
        ...,
        ge=0,
        description="Number of similar successful cases",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recommendation_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Manual Therapy + Home Exercises",
                "description": "Apply manual therapy to upper trapezius trigger points using sustained pressure (30-60 seconds). Prescribe home exercises: gentle neck stretches (3x daily) and postural corrections. Ice for 15 minutes post-treatment.",
                "therapy_type": "massage",
                "evidence_type": "hybrid",
                "similar_cases_count": 5,
            }
        }
    )


class TreatmentRecommendationResponse(BaseModel):
    """
    Response schema for treatment recommendation endpoint.

    Attributes:
        recommendations: List of 1-2 treatment recommendations
        therapy_type: Detected therapy type
        language: Detected language of input (he or en)
        retrieved_count: Number of similar cases retrieved
        processing_time_ms: Total processing time in milliseconds
    """

    recommendations: list[TreatmentRecommendationItem] = Field(
        ...,
        min_length=1,
        max_length=2,
        description="1-2 focused treatment recommendations",
    )
    therapy_type: str = Field(
        ...,
        pattern="^(massage|physiotherapy|psychotherapy|generic)$",
        description="Detected therapy type",
    )
    language: str = Field(
        ...,
        pattern="^(he|en)$",
        description="Detected language (he or en)",
    )
    retrieved_count: int = Field(
        ...,
        ge=0,
        description="Number of similar cases retrieved",
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Processing time in milliseconds",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recommendations": [
                    {
                        "recommendation_id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Manual Therapy + Home Exercises",
                        "description": "Apply manual therapy to upper trapezius trigger points using sustained pressure (30-60 seconds). Prescribe home exercises: gentle neck stretches (3x daily) and postural corrections.",
                        "therapy_type": "massage",
                        "evidence_type": "hybrid",
                        "similar_cases_count": 5,
                    },
                    {
                        "recommendation_id": "660e8400-e29b-41d4-a716-446655440001",
                        "title": "Myofascial Release Technique",
                        "description": "Use myofascial release on cervical paraspinals and scalenes. Apply gentle sustained pressure for 90-120 seconds. Follow with passive stretching.",
                        "therapy_type": "massage",
                        "evidence_type": "clinical_guidelines",
                        "similar_cases_count": 0,
                    },
                ],
                "therapy_type": "massage",
                "language": "en",
                "retrieved_count": 5,
                "processing_time_ms": 1450,
            }
        }
    )
