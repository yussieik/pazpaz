"""Pydantic schemas for AI Agent API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionCitationResponse(BaseModel):
    """
    Citation reference to a specific session in AI agent response.

    Attributes:
        type: Citation type discriminator ("session")
        session_id: UUID of the cited session
        client_id: UUID of the client (for navigation to client detail page)
        client_name: Name of the client (for display in UI)
        session_date: Date of the session
        similarity: Cosine similarity score (0.0 to 1.0, higher = more relevant)
        field_name: SOAP field that matched (subjective, objective, assessment, plan)
    """

    type: str = Field(default="session", description="Citation type discriminator")
    session_id: uuid.UUID = Field(..., description="Session ID")
    client_id: uuid.UUID = Field(..., description="Client ID for navigation")
    client_name: str = Field(..., description="Client name for display")
    session_date: datetime = Field(..., description="Session date")
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0-1.0)",
    )
    field_name: str = Field(..., description="SOAP field that matched")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "session",
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "client_id": "987e6543-e21b-12d3-a456-426614174111",
                "client_name": "John Doe",
                "session_date": "2025-11-01T10:30:00Z",
                "similarity": 0.85,
                "field_name": "subjective",
            }
        }
    )


class ClientCitationResponse(BaseModel):
    """
    Citation reference to a client profile in AI agent response.

    Used when the AI agent cites information from client profile fields
    (medical history, notes) rather than session notes.

    Attributes:
        type: Citation type discriminator ("client")
        client_id: UUID of the cited client
        client_name: Name of the client (for display in UI)
        similarity: Cosine similarity score (0.0 to 1.0, higher = more relevant)
        field_name: Client field that matched (medical_history, notes)
    """

    type: str = Field(default="client", description="Citation type discriminator")
    client_id: uuid.UUID = Field(..., description="Client ID")
    client_name: str = Field(..., description="Client name for display")
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0-1.0)",
    )
    field_name: str = Field(..., description="Client field that matched")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "client",
                "client_id": "123e4567-e89b-12d3-a456-426614174000",
                "client_name": "Jane Smith",
                "similarity": 0.88,
                "field_name": "medical_history",
            }
        }
    )


class AgentChatRequest(BaseModel):
    """
    Request schema for AI agent chat endpoint.

    SECURITY: workspace_id is NOT accepted from client requests.
    It is automatically injected from the authenticated user's session.
    This prevents workspace injection vulnerabilities.

    Attributes:
        query: Natural language question (Hebrew or English)
        client_id: Optional client ID to scope retrieval to specific patient
        max_results: Maximum number of sessions to retrieve (1-10)
        min_similarity: Minimum similarity threshold (0.0-1.0)
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language question (Hebrew or English)",
    )
    client_id: uuid.UUID | None = Field(
        None,
        description="Optional: Scope to specific client's history",
    )
    max_results: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum sessions to retrieve (1-10)",
    )
    min_similarity: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold (0.0-1.0, default: 0.3 for search)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "What was the patient's back pain history?",
                    "client_id": "123e4567-e89b-12d3-a456-426614174000",
                    "max_results": 5,
                    "min_similarity": 0.7,
                },
                {
                    "query": "מה היה הטיפול בכאבי גב?",
                    "max_results": 3,
                    "min_similarity": 0.8,
                },
            ]
        }
    )


class AgentChatResponse(BaseModel):
    """
    Response schema for AI agent chat endpoint.

    Attributes:
        answer: The synthesized answer text (Hebrew or English)
        citations: List of citations (session or client) referenced in the answer
        language: Detected language of the query ("he" or "en")
        retrieved_count: Number of records retrieved from vector store
        processing_time_ms: Total processing time in milliseconds
    """

    answer: str = Field(..., description="Synthesized answer")
    citations: list[SessionCitationResponse | ClientCitationResponse] = Field(
        default_factory=list,
        description="Citations (session notes or client profiles)",
    )
    language: str = Field(
        ...,
        pattern="^(he|en)$",
        description="Detected language (he or en)",
    )
    retrieved_count: int = Field(
        ...,
        ge=0,
        description="Number of records retrieved (sessions + clients)",
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Processing time in milliseconds",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Based on session notes, the patient reported lower back pain...",
                "citations": [
                    {
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "client_id": "987e6543-e21b-12d3-a456-426614174111",
                        "client_name": "John Doe",
                        "session_date": "2025-11-01T10:30:00Z",
                        "similarity": 0.85,
                        "field_name": "subjective",
                    }
                ],
                "language": "en",
                "retrieved_count": 3,
                "processing_time_ms": 1250,
            }
        }
    )
