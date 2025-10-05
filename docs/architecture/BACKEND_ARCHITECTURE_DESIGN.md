# Backend Architecture Design: SOAP Notes, Plan of Care, and Email Reminders

**Project:** PazPaz - Practice Management for Independent Therapists
**Version:** 1.0
**Date:** 2025-10-03
**Target Milestone:** M3-M4

## Table of Contents

1. [Overview](#overview)
2. [Feature 1: Session Documentation (SOAP Notes)](#feature-1-session-documentation-soap-notes)
3. [Feature 2: Plan of Care](#feature-2-plan-of-care)
4. [Feature 3: Email Reminders](#feature-3-email-reminders)
5. [Cross-Cutting Concerns](#cross-cutting-concerns)
6. [Testing Strategy](#testing-strategy)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Overview

This document outlines the backend architecture for three upcoming features:

1. **SOAP Notes** - Session documentation with autosave, file attachments, and offline sync
2. **Plan of Care** - Treatment timeline with goals and milestones
3. **Email Reminders** - Automated appointment notifications

**Critical Requirements:**
- All endpoints MUST enforce workspace scoping
- Performance target: p95 < 150ms for SOAP notes list/get endpoints
- PHI data encryption at rest for session notes and attachments
- Comprehensive audit logging for all data modifications
- Proper error handling with RFC 7807 problem details format

---

## Feature 1: Session Documentation (SOAP Notes)

### 1.1 Data Model

#### Session Model

```python
# backend/src/pazpaz/models/session.py

from __future__ import annotations
import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace
    from pazpaz.models.session_attachment import SessionAttachment


class SessionStatus(str, enum.Enum):
    """Status of a SOAP session note."""
    DRAFT = "draft"           # Autosaved but not finalized
    FINALIZED = "finalized"   # Therapist marked as complete
    ARCHIVED = "archived"     # Soft deleted


class Session(Base):
    """
    Session represents SOAP-based documentation of a therapy session.

    SOAP Structure:
    - Subjective: Client-reported symptoms, feelings, progress
    - Objective: Therapist observations, measurements, assessments
    - Assessment: Clinical impression, diagnosis updates
    - Plan: Treatment plan, next steps, homework

    Critical Privacy Requirements:
    - All text fields contain PHI and MUST be encrypted at rest
    - Audit every create/read/update/delete operation
    - Never log field contents (log IDs only)
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,  # One session per appointment
        comment="Appointment this session documents (1:1 relationship)",
    )

    # SOAP Fields (PHI - encrypt at rest)
    subjective: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Client-reported symptoms and feelings (PHI - encrypt at rest)",
    )
    objective: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Therapist observations and measurements (PHI - encrypt at rest)",
    )
    assessment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Clinical impression and diagnosis (PHI - encrypt at rest)",
    )
    plan: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Treatment plan and next steps (PHI - encrypt at rest)",
    )

    # Metadata
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, native_enum=False, length=50),
        default=SessionStatus.DRAFT,
        nullable=False,
    )
    is_synced: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False if created offline and pending sync",
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When therapist marked session as complete",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="sessions",
    )
    appointment: Mapped[Appointment] = relationship(
        "Appointment",
        back_populates="session",
    )
    attachments: Mapped[list[SessionAttachment]] = relationship(
        "SessionAttachment",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        # Critical index for workspace + appointment queries
        Index(
            "ix_sessions_workspace_appointment",
            "workspace_id",
            "appointment_id",
        ),
        # Index for workspace + status filtering
        Index(
            "ix_sessions_workspace_status",
            "workspace_id",
            "status",
        ),
        # Index for recently updated sessions
        Index(
            "ix_sessions_workspace_updated",
            "workspace_id",
            "updated_at",
        ),
        {
            "comment": (
                "SOAP session notes with PHI - encryption at rest required"
            )
        },
    )

    def __repr__(self) -> str:
        return (
            f"<Session(id={self.id}, appointment_id={self.appointment_id}, "
            f"status={self.status.value})>"
        )
```

#### SessionAttachment Model

```python
# backend/src/pazpaz/models/session_attachment.py

from __future__ import annotations
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.session import Session
    from pazpaz.models.workspace import Workspace


class SessionAttachment(Base):
    """
    SessionAttachment represents files attached to SOAP notes.

    Files are stored in MinIO/S3, not in the database.
    This model stores metadata and references only.

    Critical Security Requirements:
    - Validate file types (images: jpg, png, pdf only)
    - Enforce file size limits (max 10MB per file)
    - Generate presigned URLs for secure access (expire in 15 minutes)
    - Audit all file access operations
    """

    __tablename__ = "session_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File metadata
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename from upload",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes (max 10MB)",
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME type (e.g., image/jpeg, application/pdf)",
    )

    # S3/MinIO storage path
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        comment="S3/MinIO object key (e.g., workspace_id/session_id/uuid_filename)",
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="session_attachments",
    )
    session: Mapped[Session] = relationship(
        "Session",
        back_populates="attachments",
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_session_attachments_workspace_session",
            "workspace_id",
            "session_id",
        ),
        {"comment": "File attachments for SOAP notes"},
    )

    def __repr__(self) -> str:
        return (
            f"<SessionAttachment(id={self.id}, filename={self.filename}, "
            f"session_id={self.session_id})>"
        )
```

### 1.2 API Endpoints

#### Sessions CRUD

```
POST   /api/v1/sessions                      # Create session (draft)
GET    /api/v1/sessions                      # List sessions (paginated, filterable)
GET    /api/v1/sessions/{session_id}         # Get session details
PUT    /api/v1/sessions/{session_id}         # Update session (autosave)
PATCH  /api/v1/sessions/{session_id}/finalize # Finalize session
DELETE /api/v1/sessions/{session_id}         # Delete session (soft delete)
```

#### Attachments

```
POST   /api/v1/sessions/{session_id}/attachments        # Upload attachment
GET    /api/v1/sessions/{session_id}/attachments        # List attachments
GET    /api/v1/sessions/{session_id}/attachments/{id}   # Get presigned URL
DELETE /api/v1/sessions/{session_id}/attachments/{id}   # Delete attachment
```

#### Offline Sync

```
POST   /api/v1/sessions/sync                 # Sync offline sessions
```

### 1.3 Pydantic Schemas

```python
# backend/src/pazpaz/schemas/session.py

from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from pazpaz.models.session import SessionStatus


class SessionBase(BaseModel):
    """Base schema for session fields."""
    appointment_id: uuid.UUID = Field(..., description="Associated appointment")
    subjective: str | None = Field(None, description="Client-reported symptoms")
    objective: str | None = Field(None, description="Therapist observations")
    assessment: str | None = Field(None, description="Clinical impression")
    plan: str | None = Field(None, description="Treatment plan")


class SessionCreate(SessionBase):
    """Schema for creating a session (always starts as draft)."""
    pass


class SessionUpdate(BaseModel):
    """Schema for updating session (autosave - partial updates)."""
    subjective: str | None = None
    objective: str | None = None
    assessment: str | None = None
    plan: str | None = None


class SessionResponse(BaseModel):
    """Schema for session API responses."""
    id: uuid.UUID
    workspace_id: uuid.UUID
    appointment_id: uuid.UUID
    subjective: str | None
    objective: str | None
    assessment: str | None
    plan: str | None
    status: SessionStatus
    is_synced: bool
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    """Schema for paginated session list."""
    items: list[SessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AttachmentUploadResponse(BaseModel):
    """Response schema for attachment upload."""
    id: uuid.UUID
    upload_url: str = Field(..., description="Presigned S3 URL for upload")
    expires_at: datetime = Field(..., description="URL expiration time")


class AttachmentResponse(BaseModel):
    """Schema for attachment metadata."""
    id: uuid.UUID
    session_id: uuid.UUID
    filename: str
    file_size: int
    content_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentDownloadResponse(BaseModel):
    """Response schema for attachment download."""
    download_url: str = Field(..., description="Presigned S3 URL for download")
    expires_at: datetime = Field(..., description="URL expiration time")


class OfflineSessionSync(BaseModel):
    """Schema for syncing offline sessions."""
    client_session_id: str = Field(..., description="Client-generated UUID")
    appointment_id: uuid.UUID
    subjective: str | None = None
    objective: str | None = None
    assessment: str | None = None
    plan: str | None = None
    created_at_client: datetime = Field(..., description="Client timestamp")


class OfflineSyncRequest(BaseModel):
    """Batch sync request for offline sessions."""
    sessions: list[OfflineSessionSync]


class OfflineSyncResponse(BaseModel):
    """Response for offline sync operation."""
    synced_count: int
    failed_count: int
    results: list[dict] = Field(
        ...,
        description="List of {client_session_id, server_session_id, status, error}",
    )
```

### 1.4 Service Layer

```python
# backend/src/pazpaz/services/session_service.py

from __future__ import annotations
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.session import Session, SessionStatus
from pazpaz.models.appointment import Appointment

if TYPE_CHECKING:
    from pazpaz.schemas.session import SessionCreate, SessionUpdate

logger = get_logger(__name__)


class SessionService:
    """Business logic for SOAP session management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        workspace_id: uuid.UUID,
        data: SessionCreate,
    ) -> Session:
        """
        Create a new session (always starts as DRAFT).

        Validates:
        - Appointment exists and belongs to workspace
        - No existing session for this appointment
        """
        # Verify appointment exists in workspace
        query = select(Appointment).where(
            Appointment.id == data.appointment_id,
            Appointment.workspace_id == workspace_id,
        )
        result = await self.db.execute(query)
        appointment = result.scalar_one_or_none()

        if not appointment:
            raise ValueError("Appointment not found or access denied")

        # Check if session already exists for this appointment
        existing_query = select(Session).where(
            Session.appointment_id == data.appointment_id,
        )
        existing_result = await self.db.execute(existing_query)
        existing_session = existing_result.scalar_one_or_none()

        if existing_session:
            raise ValueError("Session already exists for this appointment")

        # Create session
        session = Session(
            workspace_id=workspace_id,
            appointment_id=data.appointment_id,
            subjective=data.subjective,
            objective=data.objective,
            assessment=data.assessment,
            plan=data.plan,
            status=SessionStatus.DRAFT,
            is_synced=True,
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(
            "session_created",
            session_id=str(session.id),
            workspace_id=str(workspace_id),
            appointment_id=str(data.appointment_id),
        )

        return session

    async def update_session(
        self,
        session_id: uuid.UUID,
        workspace_id: uuid.UUID,
        data: SessionUpdate,
    ) -> Session:
        """
        Update session (autosave).

        Only updates provided fields (partial update).
        Cannot update finalized sessions.
        """
        # Fetch session with workspace scoping
        query = select(Session).where(
            Session.id == session_id,
            Session.workspace_id == workspace_id,
        )
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Session not found or access denied")

        if session.status == SessionStatus.FINALIZED:
            raise ValueError("Cannot update finalized session")

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)

        await self.db.commit()
        await self.db.refresh(session)

        logger.debug(
            "session_updated",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )

        return session

    async def finalize_session(
        self,
        session_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Session:
        """
        Finalize session (mark as complete).

        Finalizing prevents further edits and timestamps completion.
        """
        query = select(Session).where(
            Session.id == session_id,
            Session.workspace_id == workspace_id,
        )
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Session not found or access denied")

        if session.status == SessionStatus.FINALIZED:
            raise ValueError("Session is already finalized")

        session.status = SessionStatus.FINALIZED
        session.finalized_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(session)

        logger.info(
            "session_finalized",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )

        return session
```

```python
# backend/src/pazpaz/services/storage_service.py

from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from typing import BinaryIO

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

# Note: Will need to add boto3 to dependencies
# from boto3 import client as boto3_client
# from botocore.exceptions import ClientError

logger = get_logger(__name__)


class StorageService:
    """
    S3/MinIO storage service for file attachments.

    Handles:
    - Presigned URL generation for uploads/downloads
    - File validation (type, size)
    - Object key generation (workspace/session isolation)
    """

    def __init__(self):
        # TODO: Initialize S3/MinIO client
        # self.s3_client = boto3_client(
        #     's3',
        #     endpoint_url=settings.s3_endpoint_url,
        #     aws_access_key_id=settings.s3_access_key,
        #     aws_secret_access_key=settings.s3_secret_key,
        #     region_name=settings.s3_region,
        # )
        self.bucket_name = "pazpaz-attachments"
        self.url_expiration = 900  # 15 minutes

    def generate_storage_key(
        self,
        workspace_id: uuid.UUID,
        session_id: uuid.UUID,
        filename: str,
    ) -> str:
        """
        Generate S3 object key for file.

        Format: {workspace_id}/{session_id}/{uuid}_{filename}

        This ensures:
        - Workspace isolation at storage level
        - No filename collisions
        - Easy cleanup when deleting sessions
        """
        file_uuid = uuid.uuid4()
        return f"{workspace_id}/{session_id}/{file_uuid}_{filename}"

    async def generate_upload_url(
        self,
        storage_key: str,
        content_type: str,
        file_size: int,
    ) -> tuple[str, datetime]:
        """
        Generate presigned URL for file upload.

        Returns:
            (upload_url, expiration_time)
        """
        # TODO: Implement S3 presigned URL generation
        # url = self.s3_client.generate_presigned_url(
        #     'put_object',
        #     Params={
        #         'Bucket': self.bucket_name,
        #         'Key': storage_key,
        #         'ContentType': content_type,
        #         'ContentLength': file_size,
        #     },
        #     ExpiresIn=self.url_expiration,
        # )

        expires_at = datetime.utcnow() + timedelta(seconds=self.url_expiration)

        # Placeholder for now
        url = f"https://minio.pazpaz.local/{self.bucket_name}/{storage_key}"

        logger.info("upload_url_generated", storage_key=storage_key)

        return url, expires_at

    async def generate_download_url(
        self,
        storage_key: str,
    ) -> tuple[str, datetime]:
        """
        Generate presigned URL for file download.

        Returns:
            (download_url, expiration_time)
        """
        # TODO: Implement S3 presigned URL generation
        # url = self.s3_client.generate_presigned_url(
        #     'get_object',
        #     Params={
        #         'Bucket': self.bucket_name,
        #         'Key': storage_key,
        #     },
        #     ExpiresIn=self.url_expiration,
        # )

        expires_at = datetime.utcnow() + timedelta(seconds=self.url_expiration)

        # Placeholder for now
        url = f"https://minio.pazpaz.local/{self.bucket_name}/{storage_key}"

        logger.debug("download_url_generated", storage_key=storage_key)

        return url, expires_at

    async def delete_file(self, storage_key: str) -> None:
        """Delete file from S3/MinIO."""
        # TODO: Implement file deletion
        # self.s3_client.delete_object(
        #     Bucket=self.bucket_name,
        #     Key=storage_key,
        # )

        logger.info("file_deleted", storage_key=storage_key)

    @staticmethod
    def validate_file_type(content_type: str) -> bool:
        """
        Validate file MIME type.

        Allowed types:
        - Images: image/jpeg, image/png
        - Documents: application/pdf
        """
        allowed_types = {
            "image/jpeg",
            "image/png",
            "application/pdf",
        }
        return content_type in allowed_types

    @staticmethod
    def validate_file_size(file_size: int) -> bool:
        """
        Validate file size (max 10MB).

        Args:
            file_size: Size in bytes
        """
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        return file_size <= max_size
```

### 1.5 Performance & Caching

**Query Optimization:**
- Index on `(workspace_id, appointment_id)` for session lookup
- Index on `(workspace_id, status)` for filtering drafts/finalized
- Index on `(workspace_id, updated_at)` for "recent sessions" queries

**Caching Strategy (Redis):**
```python
# Cache session responses for 5 minutes (reduce DB load for frequent edits)
CACHE_KEY_SESSION = "session:{session_id}"
CACHE_TTL_SESSION = 300  # 5 minutes

# Invalidate cache on update/finalize
```

**Target Performance:**
- `GET /api/v1/sessions` (list): p95 < 150ms
- `GET /api/v1/sessions/{id}`: p95 < 50ms
- `PUT /api/v1/sessions/{id}` (autosave): p95 < 100ms

### 1.6 Security & Privacy

**PHI Encryption:**
- Encrypt `subjective`, `objective`, `assessment`, `plan` fields at rest
- Use PostgreSQL `pgcrypto` or application-level encryption (decision pending)

**File Upload Security:**
- Validate file types (whitelist: jpg, png, pdf)
- Enforce size limits (10MB max)
- Presigned URLs expire in 15 minutes
- S3 bucket not publicly accessible (presigned URLs only)

**Audit Logging:**
```python
# Log all session operations to AuditEvent table
AuditEvent(
    workspace_id=workspace_id,
    user_id=user_id,
    action="session.create" | "session.update" | "session.finalize" | "session.delete",
    entity_type="Session",
    entity_id=session_id,
    timestamp=datetime.now(UTC),
    # NEVER log PHI content, only IDs
)
```

---

## Feature 2: Plan of Care

### 2.1 Data Model

#### PlanOfCare Model

```python
# backend/src/pazpaz/models/plan_of_care.py

from __future__ import annotations
import enum
import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.client import Client
    from pazpaz.models.workspace import Workspace
    from pazpaz.models.plan_milestone import PlanMilestone


class PlanStatus(str, enum.Enum):
    """Status of a plan of care."""
    ACTIVE = "active"
    COMPLETED = "completed"
    DISCONTINUED = "discontinued"


class PlanOfCare(Base):
    """
    PlanOfCare represents a structured long-term treatment plan.

    Contains:
    - Overall treatment goals and objectives
    - Expected duration and frequency
    - Associated milestones and progress markers

    Critical Privacy Requirements:
    - diagnosis and goals contain PHI - encrypt at rest
    - Audit all access/modifications
    """

    __tablename__ = "plans_of_care"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Plan details (PHI - encrypt at rest)
    diagnosis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Primary diagnosis or condition being treated (PHI)",
    )
    goals: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Treatment goals and objectives (PHI)",
    )

    # Treatment parameters
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Plan start date",
    )
    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Expected completion date (can be updated)",
    )
    frequency: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Treatment frequency (e.g., '2x per week', 'weekly')",
    )

    # Status
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, native_enum=False, length=50),
        default=PlanStatus.ACTIVE,
        nullable=False,
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="plans_of_care",
    )
    client: Mapped[Client] = relationship(
        "Client",
        back_populates="plans_of_care",
    )
    milestones: Mapped[list[PlanMilestone]] = relationship(
        "PlanMilestone",
        back_populates="plan_of_care",
        cascade="all, delete-orphan",
        order_by="PlanMilestone.target_date",
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_plans_workspace_client",
            "workspace_id",
            "client_id",
        ),
        Index(
            "ix_plans_workspace_status",
            "workspace_id",
            "status",
        ),
        {"comment": "Treatment plans with PHI - encryption at rest required"},
    )

    def __repr__(self) -> str:
        return (
            f"<PlanOfCare(id={self.id}, client_id={self.client_id}, "
            f"status={self.status.value})>"
        )
```

#### PlanMilestone Model

```python
# backend/src/pazpaz/models/plan_milestone.py

from __future__ import annotations
import enum
import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.plan_of_care import PlanOfCare
    from pazpaz.models.workspace import Workspace


class MilestoneStatus(str, enum.Enum):
    """Status of a treatment milestone."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    DISCONTINUED = "discontinued"


class PlanMilestone(Base):
    """
    PlanMilestone represents a specific goal/checkpoint in a treatment plan.

    Examples:
    - "Reduce pain level from 8/10 to 5/10"
    - "Increase range of motion to 90 degrees"
    - "Complete 10 sessions of manual therapy"

    Milestones track progress toward overall plan goals.
    """

    __tablename__ = "plan_milestones"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_of_care_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans_of_care.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Milestone details
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Milestone description and criteria (PHI)",
    )
    target_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Expected achievement date",
    )
    achieved_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Actual achievement date",
    )

    # Ordering and status
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order within plan (0-indexed)",
    )
    status: Mapped[MilestoneStatus] = mapped_column(
        Enum(MilestoneStatus, native_enum=False, length=50),
        default=MilestoneStatus.PENDING,
        nullable=False,
    )

    # Progress notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Progress notes for this milestone (PHI)",
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="plan_milestones",
    )
    plan_of_care: Mapped[PlanOfCare] = relationship(
        "PlanOfCare",
        back_populates="milestones",
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_milestones_workspace_plan",
            "workspace_id",
            "plan_of_care_id",
        ),
        Index(
            "ix_milestones_plan_order",
            "plan_of_care_id",
            "order_index",
        ),
        {"comment": "Treatment milestones with PHI"},
    )

    def __repr__(self) -> str:
        return (
            f"<PlanMilestone(id={self.id}, plan_id={self.plan_of_care_id}, "
            f"status={self.status.value})>"
        )
```

### 2.2 API Endpoints

#### Plans of Care

```
POST   /api/v1/plans                         # Create plan
GET    /api/v1/plans                         # List plans (paginated, filterable)
GET    /api/v1/plans/{plan_id}               # Get plan details
PUT    /api/v1/plans/{plan_id}               # Update plan
PATCH  /api/v1/plans/{plan_id}/status        # Update plan status
DELETE /api/v1/plans/{plan_id}               # Delete plan
```

#### Milestones

```
POST   /api/v1/plans/{plan_id}/milestones                  # Create milestone
GET    /api/v1/plans/{plan_id}/milestones                  # List milestones
GET    /api/v1/plans/{plan_id}/milestones/{milestone_id}   # Get milestone
PUT    /api/v1/plans/{plan_id}/milestones/{milestone_id}   # Update milestone
DELETE /api/v1/plans/{plan_id}/milestones/{milestone_id}   # Delete milestone
```

#### Timeline View

```
GET    /api/v1/clients/{client_id}/timeline  # Chronological treatment events
```

### 2.3 Timeline Endpoint Design

The timeline endpoint aggregates events from multiple sources:
- Appointments (scheduled, completed, cancelled)
- Sessions (SOAP notes)
- Plans of Care (created, updated, completed)
- Milestones (achieved, updated)

```python
# backend/src/pazpaz/schemas/timeline.py

from __future__ import annotations
import enum
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TimelineEventType(str, enum.Enum):
    """Type of timeline event."""
    APPOINTMENT = "appointment"
    SESSION = "session"
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    MILESTONE_ACHIEVED = "milestone_achieved"


class TimelineEvent(BaseModel):
    """
    Generic timeline event.

    Each event represents a clinical activity or milestone.
    Events are sorted chronologically to show treatment progression.
    """
    event_type: TimelineEventType
    event_date: datetime = Field(..., description="When event occurred")
    title: str = Field(..., description="Event title")
    description: str | None = Field(None, description="Event details")

    # Entity references
    appointment_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class ClientTimelineResponse(BaseModel):
    """Response schema for client timeline."""
    client_id: uuid.UUID
    events: list[TimelineEvent] = Field(
        ...,
        description="Chronologically sorted events (newest first)",
    )
    total_events: int
```

**Timeline Endpoint Implementation:**

```python
# backend/src/pazpaz/api/timeline.py

@router.get("/clients/{client_id}/timeline", response_model=ClientTimelineResponse)
async def get_client_timeline(
    client_id: uuid.UUID,
    start_date: date | None = Query(None, description="Filter from date"),
    end_date: date | None = Query(None, description="Filter to date"),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> ClientTimelineResponse:
    """
    Get chronological timeline of all treatment events for a client.

    Aggregates:
    - Appointments (completed sessions)
    - SOAP notes
    - Plan of Care events
    - Milestone achievements

    Events sorted by date descending (most recent first).
    """
    # Verify client belongs to workspace
    client = await get_or_404(db, Client, client_id, workspace_id)

    events = []

    # Fetch appointments
    appointments_query = select(Appointment).where(
        Appointment.client_id == client_id,
        Appointment.workspace_id == workspace_id,
    )
    if start_date:
        appointments_query = appointments_query.where(
            Appointment.scheduled_start >= start_date
        )
    if end_date:
        appointments_query = appointments_query.where(
            Appointment.scheduled_start <= end_date
        )

    appointments_result = await db.execute(appointments_query)
    appointments = appointments_result.scalars().all()

    for appt in appointments:
        events.append(
            TimelineEvent(
                event_type=TimelineEventType.APPOINTMENT,
                event_date=appt.scheduled_start,
                title=f"Appointment - {appt.status.value}",
                description=appt.notes,
                appointment_id=appt.id,
            )
        )

    # Fetch sessions (via appointments)
    # ... similar pattern

    # Fetch plan events
    # ... similar pattern

    # Sort events by date (newest first)
    events.sort(key=lambda e: e.event_date, reverse=True)

    return ClientTimelineResponse(
        client_id=client_id,
        events=events,
        total_events=len(events),
    )
```

### 2.4 Performance & Caching

**Query Optimization:**
- Index on `(workspace_id, client_id)` for plan lookups
- Index on `(plan_of_care_id, order_index)` for milestone ordering

**Timeline Performance:**
- Fetch all entities in parallel (asyncio.gather)
- Limit to last 100 events by default
- Cache timeline response for 10 minutes

**Target Performance:**
- `GET /api/v1/clients/{id}/timeline`: p95 < 200ms

---

## Feature 3: Email Reminders

### 3.1 Data Model

#### ReminderConfiguration Model

```python
# backend/src/pazpaz/models/reminder_configuration.py

from __future__ import annotations
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.workspace import Workspace


class ReminderConfiguration(Base):
    """
    ReminderConfiguration stores workspace-level reminder settings.

    Defines when reminders should be sent relative to appointment time.
    Multiple configurations can be active (e.g., 24h + 1h reminders).
    """

    __tablename__ = "reminder_configurations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reminder timing
    hours_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Send reminder N hours before appointment (e.g., 24, 1)",
    )

    # Enable/disable
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="reminder_configurations",
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_reminder_configs_workspace_active",
            "workspace_id",
            "is_active",
        ),
        {"comment": "Reminder schedule configurations per workspace"},
    )

    def __repr__(self) -> str:
        return (
            f"<ReminderConfiguration(id={self.id}, "
            f"hours_before={self.hours_before})>"
        )
```

#### ReminderLog Model

```python
# backend/src/pazpaz/models/reminder_log.py

from __future__ import annotations
import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class ReminderStatus(str, enum.Enum):
    """Status of reminder delivery."""
    PENDING = "pending"       # Queued but not sent
    SENT = "sent"            # Successfully delivered
    FAILED = "failed"        # Delivery failed
    BOUNCED = "bounced"      # Email bounced
    SKIPPED = "skipped"      # Skipped (e.g., no email address)


class ReminderLog(Base):
    """
    ReminderLog tracks reminder delivery for audit and debugging.

    Records:
    - When reminder was sent
    - Delivery status
    - Failure reasons
    - Email content snapshot
    """

    __tablename__ = "reminder_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Reminder details
    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email address where reminder was sent",
    )
    hours_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Hours before appointment (from configuration)",
    )

    # Delivery tracking
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, native_enum=False, length=50),
        default=ReminderStatus.PENDING,
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When email was sent",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if delivery failed",
    )

    # Email content snapshot (for debugging)
    subject: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Email subject line",
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="reminder_logs",
    )
    appointment: Mapped[Appointment] = relationship(
        "Appointment",
        back_populates="reminder_logs",
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_reminder_logs_workspace_appointment",
            "workspace_id",
            "appointment_id",
        ),
        Index(
            "ix_reminder_logs_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_reminder_logs_created",
            "created_at",
        ),
        {"comment": "Reminder delivery audit logs"},
    )

    def __repr__(self) -> str:
        return (
            f"<ReminderLog(id={self.id}, appointment_id={self.appointment_id}, "
            f"status={self.status.value})>"
        )
```

### 3.2 API Endpoints

#### Reminder Configurations

```
POST   /api/v1/reminders/configurations          # Create reminder config
GET    /api/v1/reminders/configurations          # List configs
PUT    /api/v1/reminders/configurations/{id}     # Update config
DELETE /api/v1/reminders/configurations/{id}     # Delete config
```

#### Reminder Logs

```
GET    /api/v1/reminders/logs                    # List reminder delivery logs
GET    /api/v1/appointments/{id}/reminders       # Get reminders for appointment
```

### 3.3 Background Job Architecture

**Queue System:** Redis + `arq` (async task queue)

#### Task Scheduler Design

```python
# backend/src/pazpaz/workers/reminder_scheduler.py

from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment, AppointmentStatus
from pazpaz.models.reminder_configuration import ReminderConfiguration
from pazpaz.models.reminder_log import ReminderLog, ReminderStatus
from pazpaz.workers.tasks import send_reminder_email

logger = get_logger(__name__)


async def schedule_reminders(db: AsyncSession) -> None:
    """
    Cron job that runs every 5 minutes.

    Checks for appointments needing reminders and queues email tasks.

    Logic:
    1. Fetch active reminder configurations
    2. Calculate time window (now + hours_before ± 5 minutes)
    3. Find appointments in window without sent reminders
    4. Queue email tasks
    """
    logger.info("reminder_scheduler_started")

    # Fetch all active reminder configurations
    config_query = select(ReminderConfiguration).where(
        ReminderConfiguration.is_active == True
    )
    config_result = await db.execute(config_query)
    configs = config_result.scalars().all()

    logger.debug(f"Found {len(configs)} active reminder configurations")

    reminders_queued = 0

    for config in configs:
        # Calculate time window for this configuration
        # Window = [now + hours_before - 5min, now + hours_before + 5min]
        target_time = datetime.utcnow() + timedelta(hours=config.hours_before)
        window_start = target_time - timedelta(minutes=5)
        window_end = target_time + timedelta(minutes=5)

        # Find appointments in window that need reminders
        appointments_query = (
            select(Appointment)
            .where(
                Appointment.workspace_id == config.workspace_id,
                Appointment.scheduled_start >= window_start,
                Appointment.scheduled_start <= window_end,
                Appointment.status == AppointmentStatus.SCHEDULED,
            )
        )

        appointments_result = await db.execute(appointments_query)
        appointments = appointments_result.scalars().all()

        for appointment in appointments:
            # Check if reminder already sent/queued for this config
            log_query = select(ReminderLog).where(
                ReminderLog.appointment_id == appointment.id,
                ReminderLog.hours_before == config.hours_before,
            )
            log_result = await db.execute(log_query)
            existing_log = log_result.scalar_one_or_none()

            if existing_log:
                # Already processed
                continue

            # Get client email (need to join with client)
            # ... fetch client data

            if not client_email:
                # Create log entry for skipped reminder
                log = ReminderLog(
                    workspace_id=appointment.workspace_id,
                    appointment_id=appointment.id,
                    recipient_email="",
                    hours_before=config.hours_before,
                    status=ReminderStatus.SKIPPED,
                    error_message="No email address for client",
                )
                db.add(log)
                continue

            # Create pending log entry
            log = ReminderLog(
                workspace_id=appointment.workspace_id,
                appointment_id=appointment.id,
                recipient_email=client_email,
                hours_before=config.hours_before,
                status=ReminderStatus.PENDING,
            )
            db.add(log)
            await db.commit()
            await db.refresh(log)

            # Queue email task
            await send_reminder_email.delay(
                reminder_log_id=str(log.id),
                appointment_id=str(appointment.id),
                recipient_email=client_email,
            )

            reminders_queued += 1

    await db.commit()

    logger.info(
        "reminder_scheduler_completed",
        reminders_queued=reminders_queued,
    )
```

#### Email Sending Task

```python
# backend/src/pazpaz/workers/tasks.py

import aiosmtplib
from email.message import EmailMessage
from datetime import datetime

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_db
from pazpaz.models.reminder_log import ReminderLog, ReminderStatus

logger = get_logger(__name__)


async def send_reminder_email(
    reminder_log_id: str,
    appointment_id: str,
    recipient_email: str,
) -> None:
    """
    Background task to send reminder email.

    Retries: 3 attempts with exponential backoff
    Timeout: 30 seconds
    """
    logger.info(
        "reminder_email_task_started",
        reminder_log_id=reminder_log_id,
        recipient=recipient_email,
    )

    async with get_db() as db:
        # Fetch reminder log and appointment details
        # ... (omitted for brevity)

        # Generate email content
        subject = f"Appointment Reminder - {appointment.scheduled_start.strftime('%B %d, %Y')}"
        body = f"""
        Hello {client.first_name},

        This is a reminder for your upcoming appointment:

        Date: {appointment.scheduled_start.strftime('%B %d, %Y')}
        Time: {appointment.scheduled_start.strftime('%I:%M %p')}
        Location: {appointment.location_type.value}

        If you need to reschedule, please contact us.

        Thank you,
        {workspace.name}
        """

        # Send email
        try:
            message = EmailMessage()
            message["From"] = settings.emails_from_email
            message["To"] = recipient_email
            message["Subject"] = subject
            message.set_content(body)

            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                timeout=30,
            )

            # Update log
            reminder_log.status = ReminderStatus.SENT
            reminder_log.sent_at = datetime.utcnow()
            reminder_log.subject = subject

            logger.info(
                "reminder_email_sent",
                reminder_log_id=reminder_log_id,
                recipient=recipient_email,
            )

        except Exception as e:
            # Update log with failure
            reminder_log.status = ReminderStatus.FAILED
            reminder_log.error_message = str(e)

            logger.error(
                "reminder_email_failed",
                reminder_log_id=reminder_log_id,
                recipient=recipient_email,
                error=str(e),
            )

            # Re-raise for task retry
            raise

        finally:
            await db.commit()
```

#### Cron Setup (using arq)

```python
# backend/src/pazpaz/workers/worker.py

from arq import create_pool
from arq.connections import RedisSettings

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.workers.reminder_scheduler import schedule_reminders
from pazpaz.workers.tasks import send_reminder_email

logger = get_logger(__name__)


async def startup(ctx):
    """Initialize worker resources."""
    logger.info("worker_started")


async def shutdown(ctx):
    """Cleanup worker resources."""
    logger.info("worker_shutdown")


class WorkerSettings:
    """ARQ worker configuration."""

    # Redis connection
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Task functions
    functions = [
        send_reminder_email,
    ]

    # Cron jobs
    cron_jobs = [
        # Run reminder scheduler every 5 minutes
        {
            "coroutine": schedule_reminders,
            "cron": "*/5 * * * *",  # Every 5 minutes
        },
    ]

    # Worker settings
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    retry_jobs = True
    max_tries = 3
```

### 3.4 Performance & Scalability

**Scheduler Performance:**
- Query optimization: indexes on `(workspace_id, scheduled_start)`
- Batch processing: process up to 1000 appointments per scheduler run
- Idempotency: check `ReminderLog` to avoid duplicate sends

**Email Queue:**
- Async email sending (non-blocking)
- Retry with exponential backoff (3 attempts)
- Rate limiting: max 100 emails/minute per workspace

**Monitoring:**
- Track queue depth (alerts if > 1000 pending)
- Monitor delivery rates (sent/failed/bounced)
- Alert on high failure rates (> 10%)

---

## Cross-Cutting Concerns

### Workspace Scoping Enforcement

**Pattern for all endpoints:**

```python
@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
):
    # ALWAYS use get_or_404 with workspace_id
    session = await get_or_404(db, Session, session_id, workspace_id)
    # ...
```

**Database query pattern:**

```python
# BAD: No workspace scoping
query = select(Session).where(Session.id == session_id)

# GOOD: Workspace scoped
query = select(Session).where(
    Session.id == session_id,
    Session.workspace_id == workspace_id,
)
```

### Audit Logging

**AuditEvent Integration:**

```python
# backend/src/pazpaz/services/audit_service.py

from pazpaz.models.audit_event import AuditEvent, AuditAction

async def log_audit_event(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID,
) -> None:
    """
    Log audit event.

    CRITICAL: Never log PHI content, only entity IDs.
    """
    event = AuditEvent(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,  # "create", "read", "update", "delete"
        entity_type=entity_type,  # "Session", "PlanOfCare", etc.
        entity_id=entity_id,
        timestamp=datetime.now(UTC),
    )
    db.add(event)
    await db.commit()

    logger.info(
        "audit_event_logged",
        workspace_id=str(workspace_id),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
    )
```

**Usage in endpoints:**

```python
@router.post("/sessions")
async def create_session(...):
    session = await session_service.create_session(...)

    # Log audit event
    await log_audit_event(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user_id,
        action="create",
        entity_type="Session",
        entity_id=session.id,
    )

    return session
```

### Error Handling

**RFC 7807 Problem Details Format:**

```python
# backend/src/pazpaz/core/errors.py

from fastapi import HTTPException
from pydantic import BaseModel


class ProblemDetail(BaseModel):
    """RFC 7807 problem details."""
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None


class SessionAlreadyExistsError(HTTPException):
    """Raised when attempting to create duplicate session."""

    def __init__(self, appointment_id: uuid.UUID):
        super().__init__(
            status_code=409,
            detail=ProblemDetail(
                type="https://pazpaz.com/errors/session-already-exists",
                title="Session Already Exists",
                status=409,
                detail=f"A session already exists for appointment {appointment_id}",
            ).model_dump(),
        )


class FileTooLargeError(HTTPException):
    """Raised when file exceeds size limit."""

    def __init__(self, file_size: int, max_size: int):
        super().__init__(
            status_code=413,
            detail=ProblemDetail(
                type="https://pazpaz.com/errors/file-too-large",
                title="File Too Large",
                status=413,
                detail=f"File size {file_size} exceeds maximum {max_size} bytes",
            ).model_dump(),
        )
```

### Rate Limiting

```python
# backend/src/pazpaz/middleware/rate_limit.py

from fastapi import Request, HTTPException
from redis.asyncio import Redis

async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware.

    Limits:
    - 100 requests/minute per workspace for write operations
    - 1000 requests/minute per workspace for read operations
    """
    workspace_id = request.headers.get("X-Workspace-ID")

    if not workspace_id:
        return await call_next(request)

    # Check rate limit in Redis
    key = f"rate_limit:{workspace_id}:{request.method}"
    redis = request.app.state.redis

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)  # 1 minute TTL

    # Set limits based on method
    limit = 100 if request.method in ["POST", "PUT", "PATCH", "DELETE"] else 1000

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))

    return response
```

---

## Testing Strategy

### Unit Tests

**Session Service Tests:**
```python
# backend/tests/test_session_service.py

import pytest
from pazpaz.services.session_service import SessionService
from pazpaz.models.session import SessionStatus

@pytest.mark.asyncio
async def test_create_session(db_session, test_workspace, test_appointment):
    """Test session creation."""
    service = SessionService(db_session)

    session = await service.create_session(
        workspace_id=test_workspace.id,
        data=SessionCreate(
            appointment_id=test_appointment.id,
            subjective="Patient reports pain",
        ),
    )

    assert session.status == SessionStatus.DRAFT
    assert session.subjective == "Patient reports pain"


@pytest.mark.asyncio
async def test_cannot_create_duplicate_session(db_session, test_workspace, test_session):
    """Test duplicate session prevention."""
    service = SessionService(db_session)

    with pytest.raises(ValueError, match="already exists"):
        await service.create_session(
            workspace_id=test_workspace.id,
            data=SessionCreate(appointment_id=test_session.appointment_id),
        )


@pytest.mark.asyncio
async def test_cannot_update_finalized_session(db_session, test_workspace):
    """Test finalized session immutability."""
    # ... create and finalize session

    with pytest.raises(ValueError, match="Cannot update finalized"):
        await service.update_session(...)
```

### Integration Tests

**API Endpoint Tests:**
```python
# backend/tests/test_session_api.py

@pytest.mark.asyncio
async def test_create_session_endpoint(client, test_workspace, test_appointment):
    """Test POST /api/v1/sessions."""
    response = await client.post(
        "/api/v1/sessions",
        headers={"X-Workspace-ID": str(test_workspace.id)},
        json={
            "appointment_id": str(test_appointment.id),
            "subjective": "Test subjective",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_session_autosave(client, test_session):
    """Test autosave functionality."""
    # Update session multiple times rapidly
    for i in range(5):
        response = await client.put(
            f"/api/v1/sessions/{test_session.id}",
            headers={"X-Workspace-ID": str(test_session.workspace_id)},
            json={"subjective": f"Update {i}"},
        )
        assert response.status_code == 200
```

### Workspace Isolation Tests

```python
# backend/tests/test_workspace_isolation.py

@pytest.mark.asyncio
async def test_cannot_access_other_workspace_session(
    client, workspace1, workspace2, session_in_workspace1
):
    """Test workspace scoping prevents cross-workspace access."""
    response = await client.get(
        f"/api/v1/sessions/{session_in_workspace1.id}",
        headers={"X-Workspace-ID": str(workspace2.id)},
    )

    # Should return 404, not 403 (prevent information leakage)
    assert response.status_code == 404
```

### Performance Tests

```python
# backend/tests/test_performance.py

@pytest.mark.performance
@pytest.mark.asyncio
async def test_session_list_performance(client, test_workspace, benchmark):
    """Test session list endpoint meets p95 < 150ms."""
    # Create 100 sessions
    # ...

    def fetch_sessions():
        return client.get(
            "/api/v1/sessions",
            headers={"X-Workspace-ID": str(test_workspace.id)},
        )

    result = benchmark.pedantic(fetch_sessions, iterations=100, rounds=10)

    # Check p95 latency
    p95 = sorted(result.stats['data'])[94]
    assert p95 < 0.150, f"p95 latency {p95}s exceeds 150ms target"
```

---

## Implementation Roadmap

### Phase 1: SOAP Notes Core (M3 - Week 1-2)

**Database:**
- [ ] Create `Session` model with SOAP fields
- [ ] Create `SessionAttachment` model
- [ ] Write Alembic migration
- [ ] Add relationships to `Appointment` and `Workspace`

**Backend:**
- [ ] Implement `SessionService` (create, update, finalize)
- [ ] Create `/api/v1/sessions` CRUD endpoints
- [ ] Add session schemas (request/response)
- [ ] Write unit tests for service layer
- [ ] Write integration tests for API

**Estimated Effort:** 3-4 days

### Phase 2: File Attachments (M3 - Week 2-3)

**Infrastructure:**
- [ ] Set up MinIO in Docker Compose
- [ ] Add `boto3` dependency
- [ ] Configure S3 client in `StorageService`

**Backend:**
- [ ] Implement `StorageService` (presigned URLs)
- [ ] Create `/api/v1/sessions/{id}/attachments` endpoints
- [ ] Add file validation (type, size)
- [ ] Write tests for file upload/download

**Estimated Effort:** 2-3 days

### Phase 3: Autosave & Offline Sync (M3 - Week 3-4)

**Backend:**
- [ ] Add `/api/v1/sessions/sync` endpoint
- [ ] Implement conflict resolution for offline sessions
- [ ] Add `is_synced` flag handling
- [ ] Write tests for sync scenarios

**Estimated Effort:** 2 days

### Phase 4: Plan of Care (M4 - Week 1-2)

**Database:**
- [ ] Create `PlanOfCare` model
- [ ] Create `PlanMilestone` model
- [ ] Write Alembic migration

**Backend:**
- [ ] Implement plan CRUD endpoints
- [ ] Implement milestone CRUD endpoints
- [ ] Add timeline aggregation endpoint
- [ ] Write tests

**Estimated Effort:** 3-4 days

### Phase 5: Email Reminders (M4 - Week 2-4)

**Database:**
- [ ] Create `ReminderConfiguration` model
- [ ] Create `ReminderLog` model
- [ ] Write Alembic migration

**Background Jobs:**
- [ ] Add `arq` dependency
- [ ] Implement `reminder_scheduler` cron job
- [ ] Implement `send_reminder_email` task
- [ ] Set up ARQ worker process

**Backend:**
- [ ] Create reminder configuration endpoints
- [ ] Create reminder log endpoints
- [ ] Write tests for scheduler and tasks

**Estimated Effort:** 4-5 days

### Phase 6: Security & Audit (M5 - Ongoing)

- [ ] Implement PHI encryption (pgcrypto or app-level)
- [ ] Add comprehensive audit logging
- [ ] Security review with `security-auditor` agent
- [ ] Performance testing and optimization

**Estimated Effort:** 3-4 days

---

## Dependencies to Add

```toml
# backend/pyproject.toml

[project.dependencies]
# Existing dependencies...
# Add:
"boto3>=1.28.0",           # S3/MinIO client
"arq>=0.25.0",             # Async task queue
"aiosmtplib>=3.0.0",       # Async SMTP client
```

---

## Configuration Updates

```python
# backend/src/pazpaz/core/config.py

class Settings(BaseSettings):
    # ... existing settings

    # S3/MinIO
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_bucket_name: str = "pazpaz-attachments"

    # File uploads
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: list[str] = ["image/jpeg", "image/png", "application/pdf"]

    # Background jobs (ARQ)
    arq_redis_url: str = "redis://localhost:6379/0"

    # Email reminders
    reminder_scheduler_interval_minutes: int = 5
```

---

## Summary

This architecture provides:

1. **SOAP Notes** - Complete session documentation with autosave, attachments, and offline sync
2. **Plan of Care** - Structured treatment planning with timeline visualization
3. **Email Reminders** - Automated notification system with delivery tracking

**Key Strengths:**
- Workspace scoping enforced at all layers
- Performance optimized with indexes and caching
- PHI protection with encryption and audit logging
- Scalable background job architecture
- Comprehensive error handling
- Thorough testing strategy

**Next Steps:**
1. Review this architecture with `database-architect` for schema optimization
2. Review with `security-auditor` for PHI protection and auth patterns
3. Begin Phase 1 implementation (SOAP Notes Core)
