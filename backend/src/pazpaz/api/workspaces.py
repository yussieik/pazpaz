"""Workspace API endpoints for storage management and configuration.

This module provides endpoints for workspace management:
- View current storage usage
- Adjust storage quotas (admin only)
- Update workspace payment and business configuration
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.logging import get_logger
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from pazpaz.utils.encryption import encrypt_field_versioned

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
logger = get_logger(__name__)


class WorkspaceStorageUsageResponse(BaseModel):
    """Response model for workspace storage usage."""

    used_bytes: int = Field(
        ..., description="Total bytes used by all files in workspace"
    )
    quota_bytes: int = Field(
        ..., description="Maximum storage allowed for workspace in bytes"
    )
    remaining_bytes: int = Field(
        ..., description="Bytes remaining (can be negative if quota exceeded)"
    )
    usage_percentage: float = Field(
        ..., description="Percentage of quota used (0-100+)"
    )
    is_quota_exceeded: bool = Field(
        ..., description="True if storage usage exceeds quota"
    )

    # Human-readable convenience fields
    used_mb: float = Field(..., description="Storage used in megabytes")
    quota_mb: float = Field(..., description="Quota in megabytes")
    remaining_mb: float = Field(..., description="Remaining storage in megabytes")

    class Config:
        from_attributes = True


class WorkspaceStorageQuotaUpdateRequest(BaseModel):
    """Request model for updating workspace storage quota."""

    quota_bytes: int = Field(
        ...,
        gt=0,
        description="New storage quota in bytes (must be positive)",
    )


class UpdateWorkspaceRequest(BaseModel):
    """Request model for updating workspace configuration."""

    # Payment configuration
    payment_provider: str | None = Field(
        None,
        description="Payment provider: 'payplus' or null to disable payments",
    )
    payment_provider_config: dict | None = Field(
        None,
        description="Payment provider configuration (API keys, secrets) - will be encrypted",
    )

    # Business details for tax receipts
    business_name: str | None = Field(
        None,
        description="Legal business name",
    )
    business_name_hebrew: str | None = Field(
        None,
        description="Business name in Hebrew (שם העסק בעברית)",
    )
    tax_id: str | None = Field(
        None,
        description="Israeli Tax ID (ת.ז. or ח.פ.)",
    )
    business_license_number: str | None = Field(
        None,
        description="Business license number (מספר רישיון עסק)",
    )
    business_address: str | None = Field(
        None,
        description="Business address for tax receipts",
    )

    # VAT settings
    vat_registered: bool | None = Field(
        None,
        description="Whether workspace is VAT registered (עוסק מורשה)",
    )
    vat_rate: Decimal | None = Field(
        None,
        description="VAT rate percentage (e.g., 17.00 for Israel)",
    )

    # Auto-send settings
    payment_auto_send: bool | None = Field(
        None,
        description="Automatically send payment requests after appointment completion",
    )
    payment_send_timing: str | None = Field(
        None,
        description="When to send: 'immediately' or 'after_session'",
    )


class WorkspaceResponse(BaseModel):
    """Response model for workspace data."""

    id: uuid.UUID = Field(..., description="Workspace UUID")
    name: str = Field(..., description="Workspace name")
    is_active: bool = Field(..., description="Whether workspace is active")

    # Business details
    business_name: str | None = Field(None, description="Legal business name")
    business_name_hebrew: str | None = Field(
        None, description="Business name in Hebrew"
    )
    tax_id: str | None = Field(None, description="Israeli Tax ID")
    business_license_number: str | None = Field(
        None, description="Business license number"
    )
    business_address: str | None = Field(None, description="Business address")

    # VAT configuration
    vat_registered: bool = Field(..., description="Whether VAT registered")
    vat_rate: Decimal = Field(..., description="VAT rate percentage")

    # Payment provider configuration (feature flag)
    payment_provider: str | None = Field(
        None, description="Payment provider: payplus, meshulam, stripe, null"
    )
    payment_auto_send: bool = Field(
        ..., description="Automatically send payment requests"
    )
    payment_send_timing: str = Field(
        ..., description="When to send: immediately, end_of_day, end_of_month, manual"
    )

    # Storage
    storage_used_bytes: int = Field(..., description="Storage used in bytes")
    storage_quota_bytes: int = Field(..., description="Storage quota in bytes")

    # Timezone
    timezone: str | None = Field(None, description="IANA timezone name")

    class Config:
        from_attributes = True


@router.get(
    "/{workspace_id}/storage",
    response_model=WorkspaceStorageUsageResponse,
)
async def get_workspace_storage_usage(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceStorageUsageResponse:
    """
    Get current workspace storage usage statistics.

    Returns detailed storage usage information including:
    - Total bytes used by all files
    - Storage quota (maximum allowed)
    - Remaining storage (can be negative if over quota)
    - Usage percentage
    - Quota exceeded flag

    Args:
        workspace_id: Workspace UUID
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Storage usage statistics

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 403 if workspace_id doesn't match user's workspace
            - 404 if workspace not found

    Example:
        GET /api/v1/workspaces/{uuid}/storage
        Response: {
            "used_bytes": 5368709120,
            "quota_bytes": 10737418240,
            "remaining_bytes": 5368709120,
            "usage_percentage": 50.0,
            "is_quota_exceeded": false,
            "used_mb": 5120.0,
            "quota_mb": 10240.0,
            "remaining_mb": 5120.0
        }
    """
    # Verify user has access to this workspace
    if current_user.workspace_id != workspace_id:
        logger.warning(
            "workspace_storage_access_denied",
            user_id=str(current_user.id),
            user_workspace_id=str(current_user.workspace_id),
            requested_workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace",
        )

    # Fetch workspace with storage info
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    logger.info(
        "workspace_storage_usage_retrieved",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        used_bytes=workspace.storage_used_bytes,
        quota_bytes=workspace.storage_quota_bytes,
        usage_percentage=round(workspace.storage_usage_percentage, 2),
    )

    # Convert bytes to MB for convenience
    used_mb = workspace.storage_used_bytes / (1024 * 1024)
    quota_mb = workspace.storage_quota_bytes / (1024 * 1024)
    remaining_mb = workspace.storage_remaining_bytes / (1024 * 1024)

    return WorkspaceStorageUsageResponse(
        used_bytes=workspace.storage_used_bytes,
        quota_bytes=workspace.storage_quota_bytes,
        remaining_bytes=workspace.storage_remaining_bytes,
        usage_percentage=workspace.storage_usage_percentage,
        is_quota_exceeded=workspace.is_quota_exceeded,
        used_mb=round(used_mb, 2),
        quota_mb=round(quota_mb, 2),
        remaining_mb=round(remaining_mb, 2),
    )


@router.patch(
    "/{workspace_id}/storage/quota",
    response_model=WorkspaceStorageUsageResponse,
)
async def update_workspace_storage_quota(
    workspace_id: uuid.UUID,
    quota_update: WorkspaceStorageQuotaUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceStorageUsageResponse:
    """
    Update workspace storage quota (admin only).

    This endpoint allows administrators to increase or decrease the storage quota
    for a workspace. Useful for:
    - Upgrading workspace to higher tier
    - Temporarily increasing quota for busy practices
    - Reducing quota for inactive workspaces

    IMPORTANT: This does NOT delete files if new quota is lower than current usage.
    Workspace will be over quota until files are deleted.

    Args:
        workspace_id: Workspace UUID
        quota_update: New quota in bytes
        current_user: Authenticated user (must be admin)
        db: Database session

    Returns:
        Updated storage usage statistics

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 403 if not admin or wrong workspace
            - 404 if workspace not found
            - 400 if quota_bytes is invalid (zero or negative)

    Example:
        PATCH /api/v1/workspaces/{uuid}/storage/quota
        {
            "quota_bytes": 21474836480
        }
        Response: (same as GET /storage)
    """
    # Verify user has access to this workspace
    if current_user.workspace_id != workspace_id:
        logger.warning(
            "workspace_quota_update_access_denied",
            user_id=str(current_user.id),
            user_workspace_id=str(current_user.workspace_id),
            requested_workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace",
        )

    # TODO: Add role-based check when User model has role field
    # For now, any authenticated user in workspace can adjust quota
    # In production, add: if not current_user.is_admin: raise 403

    # Fetch workspace
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Store old quota for logging
    old_quota_bytes = workspace.storage_quota_bytes
    old_quota_mb = old_quota_bytes / (1024 * 1024)
    new_quota_mb = quota_update.quota_bytes / (1024 * 1024)

    # Update quota
    workspace.storage_quota_bytes = quota_update.quota_bytes

    await db.commit()
    await db.refresh(workspace)

    logger.info(
        "workspace_storage_quota_updated",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        old_quota_bytes=old_quota_bytes,
        old_quota_mb=round(old_quota_mb, 2),
        new_quota_bytes=quota_update.quota_bytes,
        new_quota_mb=round(new_quota_mb, 2),
        current_usage_bytes=workspace.storage_used_bytes,
        is_now_over_quota=workspace.is_quota_exceeded,
    )

    # Return updated usage stats
    used_mb = workspace.storage_used_bytes / (1024 * 1024)
    quota_mb = workspace.storage_quota_bytes / (1024 * 1024)
    remaining_mb = workspace.storage_remaining_bytes / (1024 * 1024)

    return WorkspaceStorageUsageResponse(
        used_bytes=workspace.storage_used_bytes,
        quota_bytes=workspace.storage_quota_bytes,
        remaining_bytes=workspace.storage_remaining_bytes,
        usage_percentage=workspace.storage_usage_percentage,
        is_quota_exceeded=workspace.is_quota_exceeded,
        used_mb=round(used_mb, 2),
        quota_mb=round(quota_mb, 2),
        remaining_mb=round(remaining_mb, 2),
    )


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def update_workspace(
    workspace_id: uuid.UUID,
    update_data: UpdateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """
    Update workspace configuration (payment settings, business details, VAT).

    This endpoint allows authenticated users to update workspace configuration
    including payment provider settings, business details for receipts, and
    VAT registration status.

    **Workspace Scoping:**
    Users can only update their own workspace (workspace_id must match
    current_user.workspace_id).

    **Payment Provider Encryption:**
    Payment provider configuration (API keys, secrets) is encrypted using
    versioned AES-256-GCM encryption before storing in the database.

    **Partial Updates:**
    Only fields provided in the request body are updated. Omitted fields
    remain unchanged.

    Args:
        workspace_id: UUID of workspace to update
        update_data: Fields to update (only provided fields are changed)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated workspace configuration (without decrypted credentials)

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 403 if workspace_id doesn't match user's workspace
            - 404 if workspace not found

    Security Notes:
        - Payment credentials are encrypted before storage
        - Decrypted credentials are NEVER returned in response
        - Only payment_provider field is returned (not the config)

    Example Request:
        ```json
        PATCH /api/v1/workspaces/{uuid}
        {
            "payment_provider": "payplus",
            "payment_provider_config": {
                "api_key": "pk_live_xxx",
                "payment_page_uid": "abc-123",
                "webhook_secret": "whsec_xxx"
            },
            "business_name": "Example Therapy Clinic",
            "vat_registered": true,
            "vat_rate": 17.00,
            "payment_auto_send": true,
            "payment_send_timing": "immediately"
        }
        ```

    Example Response:
        ```json
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Example Clinic",
            "is_active": true,
            "business_name": "Example Therapy Clinic",
            "business_name_hebrew": null,
            "tax_id": null,
            "business_license_number": null,
            "business_address": null,
            "vat_registered": true,
            "vat_rate": 17.00,
            "payment_provider": "payplus",
            "payment_auto_send": true,
            "payment_send_timing": "immediately",
            "storage_used_bytes": 0,
            "storage_quota_bytes": 10737418240,
            "timezone": "UTC"
        }
        ```
    """
    # Verify user has access to this workspace
    if current_user.workspace_id != workspace_id:
        logger.warning(
            "workspace_update_access_denied",
            user_id=str(current_user.id),
            user_workspace_id=str(current_user.workspace_id),
            requested_workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace",
        )

    # Fetch workspace
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Track what fields are being updated for logging
    updated_fields = []

    # Get only the fields that were actually provided in the request
    # This allows us to distinguish between "field not provided" and "field provided as null"
    provided_fields = update_data.model_dump(exclude_unset=True)

    # Update payment configuration
    # Check if field was provided (not whether it's None) to support explicit null values
    if "payment_provider" in provided_fields:
        workspace.payment_provider = update_data.payment_provider
        updated_fields.append("payment_provider")

    if (
        "payment_provider_config" in provided_fields
        and update_data.payment_provider_config is not None
    ):
        # CRITICAL: Encrypt payment provider config before storing
        # This contains sensitive API keys and secrets
        config_json = json.dumps(update_data.payment_provider_config)
        encrypted_data = encrypt_field_versioned(config_json)

        # Store in versioned format: {"data": "v1:base64_ciphertext"}
        workspace.payment_provider_config = {"data": encrypted_data}
        updated_fields.append("payment_provider_config")

        logger.info(
            "payment_credentials_encrypted",
            workspace_id=str(workspace_id),
            config_keys=list(update_data.payment_provider_config.keys()),
        )

    # Update business details
    if "business_name" in provided_fields:
        workspace.business_name = update_data.business_name
        updated_fields.append("business_name")

    if "business_name_hebrew" in provided_fields:
        workspace.business_name_hebrew = update_data.business_name_hebrew
        updated_fields.append("business_name_hebrew")

    if "tax_id" in provided_fields:
        workspace.tax_id = update_data.tax_id
        updated_fields.append("tax_id")

    if "business_license_number" in provided_fields:
        workspace.business_license = update_data.business_license_number
        updated_fields.append("business_license_number")

    if "business_address" in provided_fields:
        workspace.business_address = update_data.business_address
        updated_fields.append("business_address")

    # Update VAT settings
    if "vat_registered" in provided_fields:
        workspace.vat_registered = update_data.vat_registered
        updated_fields.append("vat_registered")

    if "vat_rate" in provided_fields:
        workspace.vat_rate = update_data.vat_rate
        updated_fields.append("vat_rate")

    # Update auto-send settings
    if "payment_auto_send" in provided_fields:
        workspace.payment_auto_send = update_data.payment_auto_send
        updated_fields.append("payment_auto_send")

    if "payment_send_timing" in provided_fields:
        workspace.payment_send_timing = update_data.payment_send_timing
        updated_fields.append("payment_send_timing")

    # Commit changes to database
    await db.commit()
    await db.refresh(workspace)

    logger.info(
        "workspace_updated",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        updated_fields=updated_fields,
        payment_enabled=workspace.payments_enabled,
    )

    # Return workspace response (WITHOUT decrypted credentials)
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        is_active=workspace.is_active,
        business_name=workspace.business_name,
        business_name_hebrew=workspace.business_name_hebrew,
        tax_id=workspace.tax_id,
        business_license_number=workspace.business_license,
        business_address=workspace.business_address,
        vat_registered=workspace.vat_registered,
        vat_rate=workspace.vat_rate,
        payment_provider=workspace.payment_provider,
        payment_auto_send=workspace.payment_auto_send,
        payment_send_timing=workspace.payment_send_timing,
        storage_used_bytes=workspace.storage_used_bytes,
        storage_quota_bytes=workspace.storage_quota_bytes,
        timezone=workspace.timezone,
    )
