"""Comprehensive tests for client attachment bulk download endpoint.

Test Coverage:
- Happy path (bulk download 2-3 files successfully)
- Empty attachment_ids list (400)
- Non-existent attachment ID (404)
- Attachment from different client (403/404)
- Attachment from different workspace (404)
- Soft-deleted attachment (404)
- Duplicate filenames handled correctly
- Total size exceeds 100 MB (413)
- More than 50 files (400 via schema validation)
- Audit logging (bulk download events)
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.audit_event import AuditAction, AuditEvent, ResourceType
from pazpaz.models.client import Client
from pazpaz.models.session_attachment import SessionAttachment


# Test file generation helpers
def create_test_image(format: str = "JPEG", size: tuple = (100, 100)) -> bytes:
    """Create a test image in memory."""
    img = Image.new("RGB", size, color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format=format)
    img_bytes.seek(0)
    return img_bytes.read()


def create_test_pdf() -> bytes:
    """Create a minimal valid PDF."""
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"


@pytest.fixture
def mock_s3_client_with_files():
    """Mock S3 client that returns file content for downloads."""
    with patch("pazpaz.api.client_attachments.get_s3_client") as mock_get_client:
        client = MagicMock()

        # Mock file content for each attachment
        # Simulate different file contents for different S3 keys
        def mock_get_object(Bucket, Key):
            # Return mock file content based on key
            if ".jpg" in Key:
                content = create_test_image("JPEG", (200, 200))
            elif ".png" in Key:
                content = create_test_image("PNG", (150, 150))
            elif ".pdf" in Key:
                content = create_test_pdf()
            else:
                content = b"Mock file content"

            # Create a BytesIO object that implements .read()
            body = io.BytesIO(content)
            return {"Body": body}

        client.get_object.side_effect = mock_get_object
        client.put_object.return_value = {"ETag": '"mock-etag-12345"'}
        client.delete_object.return_value = {}
        client.head_bucket.return_value = {}
        client.create_bucket.return_value = {}

        mock_get_client.return_value = client
        yield client


class TestBulkDownload:
    """Tests for POST /api/v1/clients/{client_id}/attachments/download-multiple endpoint."""

    async def test_bulk_download_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        test_workspace,
        test_user,
        mock_s3_client_with_files,
    ):
        """Test successful bulk download of 3 client-level attachments."""
        # Create 3 test attachments for the client
        attachments = []
        for i in range(3):
            attachment = SessionAttachment(
                session_id=None,  # Client-level attachment
                client_id=sample_client_ws1.id,
                workspace_id=test_workspace.id,
                file_name=f"document_{i + 1}.jpg",
                file_type="image/jpeg",
                file_size_bytes=1024 * 100,  # 100 KB each
                s3_key=f"workspaces/{test_workspace.id}/clients/{sample_client_ws1.id}/attachments/{uuid.uuid4()}.jpg",
                uploaded_by_user_id=test_user.id,
            )
            db_session.add(attachment)
            attachments.append(attachment)
        await db_session.commit()

        # Refresh to get IDs
        for att in attachments:
            await db_session.refresh(att)

        # Request bulk download
        attachment_ids = [str(att.id) for att in attachments]
        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers.get("content-disposition", "").lower()
        assert "client-files-" in response.headers.get("content-disposition", "")

        # Verify ZIP file content
        zip_content = response.content
        zip_buffer = io.BytesIO(zip_content)

        with zipfile.ZipFile(zip_buffer, "r") as zip_file:
            # Should have 3 files
            assert len(zip_file.namelist()) == 3

            # Verify filenames match
            for att in attachments:
                assert att.file_name in zip_file.namelist()

    async def test_bulk_download_handles_duplicate_filenames(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        test_workspace,
        test_user,
        mock_s3_client_with_files,
    ):
        """Test duplicate filenames are renamed with counter (e.g., file (2).jpg)."""
        # Create 3 attachments with the same filename
        attachments = []
        for _i in range(3):
            attachment = SessionAttachment(
                session_id=None,
                client_id=sample_client_ws1.id,
                workspace_id=test_workspace.id,
                file_name="document.pdf",  # Same name for all
                file_type="application/pdf",
                file_size_bytes=2048,
                s3_key=f"workspaces/{test_workspace.id}/clients/{sample_client_ws1.id}/attachments/{uuid.uuid4()}.pdf",
                uploaded_by_user_id=test_user.id,
            )
            db_session.add(attachment)
            attachments.append(attachment)
        await db_session.commit()

        for att in attachments:
            await db_session.refresh(att)

        # Request bulk download
        attachment_ids = [str(att.id) for att in attachments]
        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify ZIP contains renamed files
        zip_content = response.content
        zip_buffer = io.BytesIO(zip_content)
        with zipfile.ZipFile(zip_buffer, "r") as zip_file:
            filenames = zip_file.namelist()
            assert len(filenames) == 3

            # Should be: document.pdf, document (2).pdf, document (3).pdf
            assert "document.pdf" in filenames
            assert "document (2).pdf" in filenames
            assert "document (3).pdf" in filenames

    async def test_bulk_download_reject_empty_list(
        self,
        authenticated_client: AsyncClient,
        sample_client_ws1: Client,
    ):
        """Test empty attachment_ids list returns 422 (validation error)."""
        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": []},
        )

        # Pydantic validation error for min_length=1
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_bulk_download_reject_over_50_files(
        self,
        authenticated_client: AsyncClient,
        sample_client_ws1: Client,
    ):
        """Test more than 50 attachment IDs returns 422 (validation error)."""
        # Generate 51 fake UUIDs
        attachment_ids = [str(uuid.uuid4()) for _ in range(51)]

        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        # Pydantic validation error for max_length=50
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_bulk_download_reject_nonexistent_attachment(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        test_workspace,
        test_user,
    ):
        """Test non-existent attachment ID returns 404."""
        # Create 1 valid attachment
        valid_attachment = SessionAttachment(
            session_id=None,
            client_id=sample_client_ws1.id,
            workspace_id=test_workspace.id,
            file_name="valid.jpg",
            file_type="image/jpeg",
            file_size_bytes=1024,
            s3_key=f"workspaces/{test_workspace.id}/clients/{sample_client_ws1.id}/attachments/{uuid.uuid4()}.jpg",
            uploaded_by_user_id=test_user.id,
        )
        db_session.add(valid_attachment)
        await db_session.commit()
        await db_session.refresh(valid_attachment)

        # Request with valid + invalid IDs
        fake_id = uuid.uuid4()
        attachment_ids = [str(valid_attachment.id), str(fake_id)]

        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    async def test_bulk_download_reject_different_client_attachment(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        test_workspace,
        test_user,
    ):
        """Test attachment from different client returns 404."""
        # Create attachment for sample_client_ws1
        attachment_client1 = SessionAttachment(
            session_id=None,
            client_id=sample_client_ws1.id,
            workspace_id=test_workspace.id,
            file_name="client1.jpg",
            file_type="image/jpeg",
            file_size_bytes=1024,
            s3_key=f"workspaces/{test_workspace.id}/clients/{sample_client_ws1.id}/attachments/{uuid.uuid4()}.jpg",
            uploaded_by_user_id=test_user.id,
        )

        # Create a second client
        client2 = Client(
            workspace_id=test_workspace.id,
            first_name="Jane",
            last_name="Smith",
        )
        db_session.add(client2)
        await db_session.commit()
        await db_session.refresh(client2)

        # Create attachment for client2
        attachment_client2 = SessionAttachment(
            session_id=None,
            client_id=client2.id,
            workspace_id=test_workspace.id,
            file_name="client2.jpg",
            file_type="image/jpeg",
            file_size_bytes=2048,
            s3_key=f"workspaces/{test_workspace.id}/clients/{client2.id}/attachments/{uuid.uuid4()}.jpg",
            uploaded_by_user_id=test_user.id,
        )

        db_session.add_all([attachment_client1, attachment_client2])
        await db_session.commit()
        await db_session.refresh(attachment_client1)
        await db_session.refresh(attachment_client2)

        # Try to download client2's attachment via client1's endpoint
        attachment_ids = [str(attachment_client1.id), str(attachment_client2.id)]

        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    async def test_bulk_download_reject_different_workspace_attachment(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        workspace_2,
        test_user_ws2,
    ):
        """Test attachment from different workspace returns 404."""
        # Create client in workspace 2
        client_ws2 = Client(
            workspace_id=workspace_2.id,
            first_name="Bob",
            last_name="Williams",
        )
        db_session.add(client_ws2)
        await db_session.commit()
        await db_session.refresh(client_ws2)

        # Create attachment in workspace 2
        attachment_ws2 = SessionAttachment(
            session_id=None,
            client_id=client_ws2.id,
            workspace_id=workspace_2.id,
            file_name="secret.jpg",
            file_type="image/jpeg",
            file_size_bytes=1024,
            s3_key=f"workspaces/{workspace_2.id}/clients/{client_ws2.id}/attachments/{uuid.uuid4()}.jpg",
            uploaded_by_user_id=test_user_ws2.id,
        )
        db_session.add(attachment_ws2)
        await db_session.commit()
        await db_session.refresh(attachment_ws2)

        # Try to download from workspace 1
        attachment_ids = [str(attachment_ws2.id)]

        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_bulk_download_reject_soft_deleted_attachment(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        test_workspace,
        test_user,
    ):
        """Test soft-deleted attachment returns 404."""
        # Create soft-deleted attachment
        deleted_attachment = SessionAttachment(
            session_id=None,
            client_id=sample_client_ws1.id,
            workspace_id=test_workspace.id,
            file_name="deleted.jpg",
            file_type="image/jpeg",
            file_size_bytes=1024,
            s3_key=f"workspaces/{test_workspace.id}/clients/{sample_client_ws1.id}/attachments/{uuid.uuid4()}.jpg",
            uploaded_by_user_id=test_user.id,
            deleted_at=datetime.now(UTC),
        )
        db_session.add(deleted_attachment)
        await db_session.commit()
        await db_session.refresh(deleted_attachment)

        # Try to download deleted attachment
        attachment_ids = [str(deleted_attachment.id)]

        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_bulk_download_reject_size_over_100mb(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        test_workspace,
        test_user,
    ):
        """Test total size exceeding 100 MB returns 413."""
        # Create 11 attachments of 10 MB each (total: 110 MB)
        attachments = []
        for i in range(11):
            attachment = SessionAttachment(
                session_id=None,
                client_id=sample_client_ws1.id,
                workspace_id=test_workspace.id,
                file_name=f"large_{i + 1}.jpg",
                file_type="image/jpeg",
                file_size_bytes=10 * 1024 * 1024,  # 10 MB each
                s3_key=f"workspaces/{test_workspace.id}/clients/{sample_client_ws1.id}/attachments/{uuid.uuid4()}.jpg",
                uploaded_by_user_id=test_user.id,
            )
            db_session.add(attachment)
            attachments.append(attachment)
        await db_session.commit()

        for att in attachments:
            await db_session.refresh(att)

        # Request all 11 files (110 MB total)
        attachment_ids = [str(att.id) for att in attachments]

        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert (
            "100 mb" in response.json()["detail"].lower()
            or "100mb" in response.json()["detail"].lower()
        )

    async def test_bulk_download_creates_audit_event(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        sample_client_ws1: Client,
        test_workspace,
        test_user,
        mock_s3_client_with_files,
    ):
        """Test bulk download creates audit event with metadata."""
        # Create 2 attachments
        attachments = []
        for i in range(2):
            attachment = SessionAttachment(
                session_id=None,
                client_id=sample_client_ws1.id,
                workspace_id=test_workspace.id,
                file_name=f"file_{i + 1}.pdf",
                file_type="application/pdf",
                file_size_bytes=1024,
                s3_key=f"workspaces/{test_workspace.id}/clients/{sample_client_ws1.id}/attachments/{uuid.uuid4()}.pdf",
                uploaded_by_user_id=test_user.id,
            )
            db_session.add(attachment)
            attachments.append(attachment)
        await db_session.commit()

        for att in attachments:
            await db_session.refresh(att)

        # Request bulk download
        attachment_ids = [str(att.id) for att in attachments]
        response = await authenticated_client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify audit event created
        result = await db_session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.resource_type == ResourceType.SESSION_ATTACHMENT.value,
                AuditEvent.action == AuditAction.READ,
                AuditEvent.workspace_id == test_workspace.id,
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(1)
        )
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.user_id == test_user.id
        assert audit_event.workspace_id == test_workspace.id

        # Verify metadata includes bulk download details
        assert audit_event.event_metadata is not None
        assert "client_id" in audit_event.event_metadata
        assert "attachment_count" in audit_event.event_metadata
        assert audit_event.event_metadata["attachment_count"] == 2
        assert "attachment_ids" in audit_event.event_metadata
        assert "total_size_bytes" in audit_event.event_metadata
        assert "operation" in audit_event.event_metadata
        assert audit_event.event_metadata["operation"] == "bulk_download"

    async def test_bulk_download_requires_authentication(
        self,
        client: AsyncClient,
        sample_client_ws1: Client,
    ):
        """Test unauthenticated request returns 403 (CSRF validation failure)."""
        attachment_ids = [str(uuid.uuid4())]

        response = await client.post(
            f"/api/v1/clients/{sample_client_ws1.id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        # CSRF middleware returns 403 Forbidden before auth middleware runs
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_bulk_download_reject_nonexistent_client(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test non-existent client returns 404."""
        fake_client_id = uuid.uuid4()
        attachment_ids = [str(uuid.uuid4())]

        response = await authenticated_client.post(
            f"/api/v1/clients/{fake_client_id}/attachments/download-multiple",
            json={"attachment_ids": attachment_ids},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
