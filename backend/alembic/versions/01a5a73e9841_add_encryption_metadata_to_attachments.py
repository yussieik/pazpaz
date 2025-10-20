"""add_encryption_metadata_to_attachments

Revision ID: 01a5a73e9841
Revises: 01b9ba5f6818
Create Date: 2025-10-20 13:35:38.668946

This migration adds encryption_metadata JSONB column to session_attachments table
to store S3/MinIO server-side encryption (SSE) verification metadata for HIPAA compliance.

Encryption metadata includes:
- algorithm: Encryption algorithm used (e.g., "AES256")
- verified_at: ISO timestamp when encryption was verified
- s3_sse: ServerSideEncryption value from S3 response
- etag: S3 ETag for object integrity verification

HIPAA Requirement: §164.312(a)(2)(iv) - Encryption at rest verification
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '01a5a73e9841'
down_revision: str | Sequence[str] | None = '01b9ba5f6818'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add encryption_metadata JSONB column to session_attachments.

    This column stores S3 server-side encryption verification metadata
    to ensure PHI file attachments are encrypted at rest.
    """
    op.add_column(
        'session_attachments',
        sa.Column(
            'encryption_metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='S3 server-side encryption metadata for HIPAA compliance verification'
        )
    )


def downgrade() -> None:
    """Remove encryption_metadata column from session_attachments."""
    op.drop_column('session_attachments', 'encryption_metadata')
