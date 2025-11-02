"""Payment API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.logging import get_logger
from pazpaz.models.user import User

router = APIRouter(prefix="/payments", tags=["payments"])
logger = get_logger(__name__)


class PaymentConfigResponse(BaseModel):
    """
    Payment configuration for a workspace.

    Phase 1: Manual payment tracking with bank account details.
    Phase 1.5: Smart payment links (Bit, PayBox, custom URLs).
    Phase 2+: Automated payment provider integrations.
    """

    payment_mode: str | None = Field(
        None,
        description="Current payment mode: 'manual', 'smart_link', 'automated', or null (disabled)",
    )
    bank_account_details: str | None = Field(
        None,
        description="Bank account details for manual payment tracking (free-text)",
    )
    payment_link_type: str | None = Field(
        None,
        description="Payment link type: 'bit', 'paybox', 'custom', or null (disabled)",
    )
    payment_link_template: str | None = Field(
        None,
        description="Payment link template: phone number (Bit), URL (PayBox/custom), or null",
    )
    payment_provider: str | None = Field(
        None,
        description="Payment provider name (manual, or future automated providers), or null (disabled)",
    )

    model_config = ConfigDict(from_attributes=True)


class UpdatePaymentConfigRequest(BaseModel):
    """Request to update payment configuration."""

    bank_account_details: str | None = Field(
        None,
        description="Bank account details for manual payment tracking (free-text)",
        examples=["Bank Leumi, Account: 12345, Branch: 678"],
    )
    payment_link_type: str | None = Field(
        None,
        description="Payment link type: 'bit', 'paybox', 'custom', or null to disable",
        examples=["bit", "paybox", "custom"],
    )
    payment_link_template: str | None = Field(
        None,
        description="Payment link template: phone number for Bit (050-XXXXXXX), URL for PayBox/custom",
        examples=["050-1234567", "https://paybox.co.il/p/username"],
    )

    @field_validator("payment_link_template")
    @classmethod
    def validate_payment_link_template(cls, v: str | None, info) -> str | None:
        """Validate payment link template based on payment_link_type."""
        if v is None:
            return v

        # Get payment_link_type from the same request
        payment_link_type = info.data.get("payment_link_type")

        if not payment_link_type:
            # If payment_link_template provided without payment_link_type, reject
            raise ValueError(
                "payment_link_type must be provided when setting payment_link_template"
            )

        if payment_link_type == "bit":
            # Bit supports two modes: phone number (SMS) or Bit Pay web URL
            # Check if it's a URL first
            if v.startswith(("http://", "https://")):
                # URL mode - valid Bit Pay web URL
                pass  # No additional validation needed
            else:
                # Phone number mode - validate Israeli mobile format
                # Clean phone (remove dashes, spaces, parentheses)
                clean_phone = (
                    v.replace("-", "")
                    .replace(" ", "")
                    .replace("(", "")
                    .replace(")", "")
                )

                # Must start with 05 and be 10 digits
                if not clean_phone.startswith("05") or len(clean_phone) != 10:
                    raise ValueError(
                        "Bit must be Israeli mobile format (05X-XXXXXXX) or Bit Pay URL (https://...)"
                    )

                # Check all characters are digits
                if not clean_phone.isdigit():
                    raise ValueError(
                        "Bit phone number must contain only digits (and optional dashes/spaces)"
                    )

        elif payment_link_type in ("paybox", "custom"):
            # Validate URL format
            if not v.startswith(("http://", "https://")):
                raise ValueError(
                    f"{payment_link_type.capitalize()} template must be a valid URL starting with http:// or https://"
                )

        return v


@router.get("/config", response_model=PaymentConfigResponse)
async def get_payment_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentConfigResponse:
    """
    Get payment configuration for authenticated user's workspace.

    **Phase 1 Behavior:**
    - Returns bank account details for manual payment tracking

    **Phase 1.5 Behavior:**
    - Returns payment_mode (manual, smart_link, automated, or null)
    - Returns payment_link_type and payment_link_template for smart links

    **Phase 2+ Behavior:**
    - payment_provider field for future automated integrations

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - workspace_id derived from JWT token (server-side, trusted)

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        PaymentConfigResponse with payment configuration

    Raises:
        HTTPException: 401 if not authenticated

    Example Response (Phase 1.5 - Smart Links):
        ```json
        {
            "payment_mode": "smart_link",
            "bank_account_details": null,
            "payment_link_type": "bit",
            "payment_link_template": "050-1234567",
            "payment_provider": null
        }
        ```

    Example Response (Phase 1 - Manual):
        ```json
        {
            "payment_mode": "manual",
            "bank_account_details": "Bank Leumi, Account: 12345, Branch: 678",
            "payment_link_type": null,
            "payment_link_template": null,
            "payment_provider": null
        }
        ```
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "payment_config_requested",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
    )

    # Access workspace via relationship (already loaded by get_current_user)
    workspace = current_user.workspace

    config = PaymentConfigResponse(
        payment_mode=workspace.payment_mode,
        bank_account_details=workspace.bank_account_details,
        payment_link_type=workspace.payment_link_type,
        payment_link_template=workspace.payment_link_template,
        payment_provider=workspace.payment_provider,
    )

    logger.info(
        "payment_config_returned",
        workspace_id=str(workspace_id),
        payment_mode=config.payment_mode,
        has_bank_details=config.bank_account_details is not None,
        payment_link_type=config.payment_link_type,
        provider=config.payment_provider,
    )

    return config


@router.put("/config", response_model=PaymentConfigResponse)
async def update_payment_config(
    request_data: UpdatePaymentConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentConfigResponse:
    """
    Update payment configuration for authenticated user's workspace.

    **Phase 1 Behavior:**
    - Updates bank account details for manual payment tracking

    **Phase 1.5 Behavior:**
    - Updates payment_link_type and payment_link_template for smart links
    - Validates phone format for Bit links
    - Validates URL format for PayBox/custom links

    **Phase 2+ Behavior:**
    - payment_provider field not updatable via this endpoint (reserved for future)

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - workspace_id derived from JWT token (server-side, trusted)

    **Validation:**
    - Bit: Israeli mobile phone format (05X-XXXXXXX or 05XXXXXXXX)
    - PayBox/Custom: Valid URL starting with http:// or https://

    Args:
        request_data: Payment configuration updates
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        PaymentConfigResponse with updated payment configuration

    Raises:
        HTTPException: 401 if not authenticated
        HTTPException: 400 if validation fails

    Example Request (Phase 1 - Manual):
        ```json
        {
            "bank_account_details": "Bank Leumi, Account: 12345, Branch: 678"
        }
        ```

    Example Request (Phase 1.5 - Bit):
        ```json
        {
            "payment_link_type": "bit",
            "payment_link_template": "050-1234567"
        }
        ```

    Example Request (Phase 1.5 - PayBox):
        ```json
        {
            "payment_link_type": "paybox",
            "payment_link_template": "https://paybox.co.il/p/username"
        }
        ```

    Example Response:
        ```json
        {
            "payment_mode": "smart_link",
            "bank_account_details": null,
            "payment_link_type": "bit",
            "payment_link_template": "050-1234567",
            "payment_provider": null
        }
        ```
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "payment_config_update_requested",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        has_bank_details=request_data.bank_account_details is not None,
        payment_link_type=request_data.payment_link_type,
    )

    # Access workspace via relationship (already loaded by get_current_user)
    workspace = current_user.workspace

    # Track what changed for audit logging
    changes = {}

    # Get dict of fields that were explicitly set in request
    request_dict = request_data.model_dump(exclude_unset=True)

    # Update bank account details (Phase 1)
    if "bank_account_details" in request_dict:
        workspace.bank_account_details = request_data.bank_account_details
        changes["bank_account_details"] = request_data.bank_account_details is not None

    # Update payment link configuration (Phase 1.5)
    if "payment_link_type" in request_dict:
        workspace.payment_link_type = request_data.payment_link_type
        changes["payment_link_type"] = request_data.payment_link_type

    if "payment_link_template" in request_dict:
        workspace.payment_link_template = request_data.payment_link_template
        changes["payment_link_template"] = "***"  # Don't log phone/URL

    # Commit changes
    await db.commit()
    await db.refresh(workspace)

    config = PaymentConfigResponse(
        payment_mode=workspace.payment_mode,
        bank_account_details=workspace.bank_account_details,
        payment_link_type=workspace.payment_link_type,
        payment_link_template=workspace.payment_link_template,
        payment_provider=workspace.payment_provider,
    )

    logger.info(
        "payment_config_updated",
        workspace_id=str(workspace_id),
        payment_mode=config.payment_mode,
        changes=changes,
    )

    return config
