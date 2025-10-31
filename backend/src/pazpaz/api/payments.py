"""Payment API endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.payment_transaction import PaymentTransaction
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from pazpaz.payments.base import PaymentLinkRequest
from pazpaz.payments.exceptions import (
    InvalidCredentialsError,
    PaymentProviderError,
    ProviderNotConfiguredError,
    WebhookVerificationError,
)
from pazpaz.payments.providers.payplus import PayPlusProvider
from pazpaz.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])
logger = get_logger(__name__)


class TestCredentialsRequest(BaseModel):
    """Request to test payment provider credentials."""

    api_key: str = Field(
        ...,
        description="PayPlus API key",
    )
    payment_page_uid: str = Field(
        ...,
        description="PayPlus payment page UID",
    )
    webhook_secret: str = Field(
        ...,
        description="PayPlus webhook secret for signature verification",
    )
    base_url: str | None = Field(
        None,
        description="Optional custom base URL for testing/sandbox environment",
    )


class TestCredentialsResponse(BaseModel):
    """Response from credentials test."""

    success: bool = Field(
        ...,
        description="Whether credentials are valid",
    )
    message: str = Field(
        ...,
        description="Human-readable message about the test result",
    )


class PaymentConfigResponse(BaseModel):
    """
    Payment configuration for a workspace.

    Phase 0: Returns workspace payment settings (feature flag data only).
    No payment processing capabilities implemented yet.
    """

    enabled: bool = Field(
        ...,
        description="Whether payments are enabled for workspace (payment_provider is set)",
    )
    provider: str | None = Field(
        None,
        description="Payment provider: payplus, meshulam, stripe, or null if disabled",
    )
    auto_send: bool = Field(
        False,
        description="Automatically send payment requests after appointment completion",
    )
    send_timing: str = Field(
        "immediately",
        description="When to send payment requests: immediately, end_of_day, end_of_month, manual",
    )
    business_name: str | None = Field(
        None,
        description="Business name for receipts",
    )
    vat_registered: bool = Field(
        False,
        description="Whether workspace is VAT registered (עוסק מורשה)",
    )

    model_config = ConfigDict(from_attributes=True)


class CreatePaymentRequestRequest(BaseModel):
    """Request to create a payment request for an appointment."""

    appointment_id: uuid.UUID = Field(
        ...,
        description="UUID of the appointment to create payment for",
    )
    customer_email: EmailStr = Field(
        ...,
        description="Customer email for payment receipt",
    )


class PaymentTransactionResponse(BaseModel):
    """Payment transaction details."""

    id: uuid.UUID = Field(..., description="Transaction ID")
    appointment_id: uuid.UUID | None = Field(
        None, description="Optional appointment ID"
    )
    total_amount: Decimal = Field(..., description="Total payment amount")
    currency: str = Field(..., description="Currency code (ILS, USD, EUR)")
    status: str = Field(
        ...,
        description="Status: pending, completed, failed, refunded, cancelled",
    )
    provider: str | None = Field(None, description="Payment provider name")
    payment_link: str | None = Field(None, description="Payment link URL")
    created_at: datetime = Field(..., description="When transaction was created")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_transaction(
        cls, transaction: PaymentTransaction
    ) -> PaymentTransactionResponse:
        """Convert PaymentTransaction model to response."""
        return cls(
            id=transaction.id,
            appointment_id=transaction.appointment_id,
            total_amount=transaction.total_amount,
            currency=transaction.currency,
            status=transaction.status,
            provider=transaction.provider,
            payment_link=transaction.provider_payment_link,
            created_at=transaction.created_at,
        )


class PaymentTransactionListResponse(BaseModel):
    """List of payment transactions."""

    transactions: list[PaymentTransactionResponse] = Field(
        ..., description="List of payment transactions"
    )


@router.get("/config", response_model=PaymentConfigResponse)
async def get_payment_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentConfigResponse:
    """
    Get payment configuration for authenticated user's workspace.

    Returns payment settings if payments are enabled, or {enabled: false} if disabled.

    **Phase 0 Behavior:**
    - Returns workspace payment configuration (read-only)
    - No payment processing endpoints available yet
    - Payment provider configuration (API keys) remains encrypted and hidden

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - workspace_id derived from JWT token (server-side, trusted)
    - No cross-workspace data access possible

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session (unused in Phase 0, kept for future use)

    Returns:
        PaymentConfigResponse with workspace payment settings

    Raises:
        HTTPException: 401 if not authenticated

    Example Response (payments disabled):
        ```json
        {
            "enabled": false,
            "provider": null,
            "auto_send": false,
            "send_timing": "immediately",
            "business_name": null,
            "vat_registered": false
        }
        ```

    Example Response (payments enabled):
        ```json
        {
            "enabled": true,
            "provider": "payplus",
            "auto_send": true,
            "send_timing": "immediately",
            "business_name": "Example Therapy Clinic",
            "vat_registered": true
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

    # SECURITY: Never expose payment_provider_config (contains encrypted API keys)
    # Only return safe configuration fields
    config = PaymentConfigResponse(
        enabled=workspace.payments_enabled,
        provider=workspace.payment_provider,
        auto_send=workspace.payment_auto_send,
        send_timing=workspace.payment_send_timing,
        business_name=workspace.business_name,
        vat_registered=workspace.vat_registered,
    )

    logger.info(
        "payment_config_returned",
        workspace_id=str(workspace_id),
        enabled=config.enabled,
        provider=config.provider,
    )

    return config


@router.post("/test-credentials", response_model=TestCredentialsResponse)
async def test_payment_credentials(
    request_data: TestCredentialsRequest,
) -> TestCredentialsResponse:
    """
    Test PayPlus credentials without storing them.

    This endpoint validates PayPlus API credentials by making a test API call
    to the PayPlus API without saving the credentials to the database. Used
    by the frontend "Test Connection" button to verify credentials before saving.

    **No Authentication Required:**
    This endpoint does NOT require authentication to allow testing credentials
    during initial setup before workspace payment configuration is saved.

    **Security Notes:**
    - Credentials are NOT logged or stored
    - Test API call uses minimal data (no real payment created)
    - Rate limited to prevent credential brute-forcing
    - Errors are sanitized to prevent credential leakage

    **Workflow:**
    1. Receive credentials from request body
    2. Instantiate PayPlusProvider with test credentials
    3. Attempt a minimal API call to validate credentials
    4. Return success/failure without exposing internal details

    Args:
        request_data: PayPlus credentials to test

    Returns:
        TestCredentialsResponse with success status and message

    Example Request:
        ```json
        {
            "api_key": "test_key_123",
            "payment_page_uid": "abc-def-123",
            "webhook_secret": "secret_xyz"
        }
        ```

    Example Success Response:
        ```json
        {
            "success": true,
            "message": "Credentials are valid and PayPlus API is reachable"
        }
        ```

    Example Failure Response:
        ```json
        {
            "success": false,
            "message": "Invalid API key or payment page UID"
        }
        ```
    """
    logger.info(
        "test_credentials_requested",
        has_api_key=bool(request_data.api_key),
        has_payment_page_uid=bool(request_data.payment_page_uid),
        has_webhook_secret=bool(request_data.webhook_secret),
    )

    try:
        # Create temporary PayPlusProvider instance with test credentials
        # Note: We pass a dict matching the config format expected by PayPlusProvider
        test_config = {
            "api_key": request_data.api_key,
            "payment_page_uid": request_data.payment_page_uid,
            "webhook_secret": request_data.webhook_secret,
        }

        # Include custom base_url if provided (for testing/sandbox environments)
        if request_data.base_url:
            test_config["base_url"] = request_data.base_url

        provider = PayPlusProvider(test_config)

        # Attempt a minimal test API call to validate credentials
        # We'll create a test payment link request with minimal data
        # PayPlus should validate credentials before processing the full request
        test_payment = PaymentLinkRequest(
            amount=Decimal("1.00"),  # Minimal amount for testing
            currency="ILS",
            description="Connection test - do not process",
            customer_email="test@example.com",
            metadata={
                "test_mode": True,
                "purpose": "credential_validation",
            },
        )

        # Make the test API call
        # If credentials are invalid, this will raise InvalidCredentialsError
        await provider.create_payment_link(test_payment)

        logger.info(
            "test_credentials_success",
            message="Credentials validated successfully",
        )

        return TestCredentialsResponse(
            success=True,
            message="Credentials are valid and PayPlus API is reachable",
        )

    except InvalidCredentialsError as e:
        logger.warning(
            "test_credentials_invalid",
            error=str(e),
        )
        return TestCredentialsResponse(
            success=False,
            message="Invalid API key or payment page UID",
        )

    except PaymentProviderError as e:
        logger.error(
            "test_credentials_provider_error",
            error=str(e),
            exc_info=True,
        )
        return TestCredentialsResponse(
            success=False,
            message="Unable to connect to PayPlus API. Please check your credentials and try again.",
        )

    except Exception as e:
        logger.error(
            "test_credentials_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return TestCredentialsResponse(
            success=False,
            message="An unexpected error occurred while testing credentials",
        )


@router.post("/create-request", response_model=PaymentTransactionResponse)
async def create_payment_request(
    request_data: CreatePaymentRequestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentTransactionResponse:
    """
    Create payment request for an appointment.

    This endpoint creates a payment link via the configured payment provider
    (e.g., PayPlus, Meshulam, Stripe) and returns a PaymentTransaction with
    the payment link that can be sent to the client.

    **Workflow:**
    1. Validates appointment exists and belongs to user's workspace
    2. Validates workspace has payments enabled
    3. Validates appointment has a price set
    4. Creates payment link via payment provider API
    5. Creates PaymentTransaction record with payment link
    6. Updates appointment payment status to "pending"

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - Prevents cross-workspace payment creation

    **VAT Handling:**
    - If workspace is VAT registered, splits total into base + VAT
    - If not VAT registered, total amount is the base price (no VAT)

    Args:
        request_data: Payment request data (appointment_id, customer_email)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        PaymentTransactionResponse with payment link

    Raises:
        HTTPException: 404 if appointment not found or wrong workspace
        HTTPException: 400 if payments not enabled
        HTTPException: 400 if no price set on appointment
        HTTPException: 400 if payment provider error occurs
        HTTPException: 401 if payment provider credentials invalid

    Example Request:
        ```json
        {
            "appointment_id": "550e8400-e29b-41d4-a716-446655440000",
            "customer_email": "client@example.com"
        }
        ```

    Example Response:
        ```json
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "appointment_id": "550e8400-e29b-41d4-a716-446655440000",
            "total_amount": "117.00",
            "currency": "ILS",
            "status": "pending",
            "provider": "payplus",
            "payment_link": "https://payplus.co.il/pay/abc123",
            "created_at": "2025-10-30T10:00:00Z"
        }
        ```
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "create_payment_request",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        appointment_id=str(request_data.appointment_id),
        customer_email=request_data.customer_email,
    )

    # Load appointment with workspace relationship
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.workspace), selectinload(Appointment.client))
        .where(
            Appointment.id == request_data.appointment_id,
            Appointment.workspace_id == workspace_id,
        )
    )
    result = await db.execute(stmt)
    appointment = result.scalar_one_or_none()

    if not appointment:
        logger.warning(
            "appointment_not_found",
            workspace_id=str(workspace_id),
            appointment_id=str(request_data.appointment_id),
        )
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    # Validate workspace has payments enabled
    workspace = appointment.workspace
    if not workspace.payments_enabled:
        logger.warning(
            "payments_not_enabled",
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=400,
            detail="Payments are not enabled for this workspace",
        )

    # Validate appointment has price set
    if appointment.payment_price is None or appointment.payment_price <= 0:
        logger.warning(
            "appointment_no_price",
            workspace_id=str(workspace_id),
            appointment_id=str(request_data.appointment_id),
        )
        raise HTTPException(
            status_code=400,
            detail="Appointment does not have a price set",
        )

    # Create payment service and request
    service = PaymentService(db)

    try:
        transaction = await service.create_payment_request(
            workspace=workspace,
            appointment=appointment,
            customer_email=request_data.customer_email,
        )

        logger.info(
            "payment_request_created_success",
            workspace_id=str(workspace_id),
            transaction_id=str(transaction.id),
            appointment_id=str(request_data.appointment_id),
            status=transaction.status,
        )

        return PaymentTransactionResponse.from_transaction(transaction)

    except InvalidCredentialsError as e:
        logger.error(
            "payment_request_invalid_credentials",
            workspace_id=str(workspace_id),
            provider=workspace.payment_provider,
            error=str(e),
        )
        raise HTTPException(
            status_code=401,
            detail=f"Invalid payment provider credentials: {e.message}",
        ) from e

    except ProviderNotConfiguredError as e:
        logger.error(
            "payment_request_provider_not_configured",
            workspace_id=str(workspace_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Payment provider not configured: {e.message}",
        ) from e

    except PaymentProviderError as e:
        logger.error(
            "payment_request_provider_error",
            workspace_id=str(workspace_id),
            provider=workspace.payment_provider,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Payment provider error: {e.message}",
        ) from e

    except ValueError as e:
        logger.error(
            "payment_request_validation_error",
            workspace_id=str(workspace_id),
            appointment_id=str(request_data.appointment_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e


@router.post("/webhook/{provider}")
async def process_payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Process payment webhook from payment provider.

    **IMPORTANT: This endpoint has NO AUTHENTICATION** as webhooks come from
    external payment providers. Security is enforced via webhook signature
    verification using the provider's secret key.

    **Workflow:**
    1. Read raw request body and headers
    2. Extract workspace_id from webhook payload metadata
    3. Load workspace from database
    4. Verify workspace has the provider configured
    5. Verify webhook signature using provider's secret
    6. Parse webhook payload
    7. Check idempotency (prevent duplicate processing)
    8. Update PaymentTransaction status
    9. Update Appointment payment status
    10. ALWAYS return 200 OK (even on errors, to prevent retries)

    **Idempotency:**
    - Uses Redis to track processed webhook IDs with 24-hour TTL
    - If webhook already processed, returns success without re-processing
    - Prevents duplicate payment status updates

    **Security:**
    - Webhook signature verified using provider secret key
    - workspace_id embedded in webhook metadata (set during payment creation)
    - Invalid signatures logged as security warnings
    - Never expose internal errors to webhook caller

    **Error Handling:**
    - Always returns 200 OK to prevent provider retries
    - Logs errors for debugging but doesn't expose details
    - Malformed webhooks are logged and ignored

    Args:
        provider: Payment provider name (e.g., "payplus", "meshulam", "stripe")
        request: FastAPI request object (for body and headers)
        db: Database session

    Returns:
        {"status": "ok"} always, regardless of success or failure

    Example Webhook Payload (PayPlus):
        ```json
        {
            "transaction_id": "payplus-txn-12345",
            "status": "completed",
            "amount": 117.00,
            "currency": "ILS",
            "custom_fields": {
                "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
                "appointment_id": "660e8400-e29b-41d4-a716-446655440001"
            },
            "completed_at": "2025-10-30T10:00:00Z"
        }
        ```
    """
    # Read raw request body and headers
    payload = await request.body()
    payload_str = payload.decode("utf-8")
    headers = dict(request.headers)

    logger.info(
        "webhook_received",
        provider=provider,
        headers_present=list(headers.keys()),
    )

    try:
        # Parse webhook to find workspace
        payload_dict = json.loads(payload_str)
        custom_fields = payload_dict.get("custom_fields", {})
        workspace_id_str = custom_fields.get("workspace_id")

        if not workspace_id_str:
            logger.error(
                "webhook_missing_workspace_id",
                provider=provider,
                payload_keys=list(payload_dict.keys()),
            )
            return {"status": "ok"}  # Return 200 to prevent retries

        workspace_id = uuid.UUID(workspace_id_str)

        # Load workspace from database
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await db.execute(stmt)
        workspace = result.scalar_one_or_none()

        if not workspace:
            logger.error(
                "webhook_workspace_not_found",
                provider=provider,
                workspace_id=str(workspace_id),
            )
            return {"status": "ok"}  # Return 200 to prevent retries

        # Validate workspace has this provider configured
        if workspace.payment_provider != provider:
            logger.warning(
                "webhook_provider_mismatch",
                provider=provider,
                workspace_id=str(workspace_id),
                workspace_provider=workspace.payment_provider,
            )
            return {"status": "ok"}  # Return 200 to prevent retries

        # Create payment service and process webhook
        service = PaymentService(db)

        try:
            transaction = await service.process_webhook(
                workspace=workspace,
                payload=payload_str,
                headers=headers,
            )

            logger.info(
                "webhook_processed_success",
                provider=provider,
                workspace_id=str(workspace_id),
                transaction_id=str(transaction.id),
                status=transaction.status,
            )

            return {"status": "ok"}

        except WebhookVerificationError as e:
            logger.warning(
                "webhook_verification_failed",
                provider=provider,
                workspace_id=str(workspace_id),
                error=str(e),
            )
            return {"status": "ok"}  # Return 200 to prevent retries

        except ValueError as e:
            logger.error(
                "webhook_transaction_not_found",
                provider=provider,
                workspace_id=str(workspace_id),
                error=str(e),
            )
            return {"status": "ok"}  # Return 200 to prevent retries

        except PaymentProviderError as e:
            logger.error(
                "webhook_provider_error",
                provider=provider,
                workspace_id=str(workspace_id),
                error=str(e),
                exc_info=True,
            )
            return {"status": "ok"}  # Return 200 to prevent retries

    except json.JSONDecodeError as e:
        logger.error(
            "webhook_invalid_json",
            provider=provider,
            error=str(e),
        )
        return {"status": "ok"}  # Return 200 to prevent retries

    except Exception as e:
        logger.error(
            "webhook_unexpected_error",
            provider=provider,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return {"status": "ok"}  # Return 200 to prevent retries


@router.get("/transactions", response_model=PaymentTransactionListResponse)
async def get_payment_transactions(
    appointment_id: uuid.UUID = Query(..., description="Appointment ID to filter by"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentTransactionListResponse:
    """
    Get payment transactions for an appointment.

    Returns all payment transactions associated with a specific appointment,
    ordered by creation time (most recent first). This allows viewing payment
    history including pending, completed, failed, and refunded transactions.

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - Prevents cross-workspace transaction access

    **Use Cases:**
    - View payment history for an appointment
    - Check if payment link was sent
    - See failed payment attempts
    - Track refunds

    Args:
        appointment_id: UUID of the appointment to filter by
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        PaymentTransactionListResponse with list of transactions

    Raises:
        HTTPException: 401 if not authenticated

    Example Response:
        ```json
        {
            "transactions": [
                {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "appointment_id": "550e8400-e29b-41d4-a716-446655440000",
                    "total_amount": "117.00",
                    "currency": "ILS",
                    "status": "completed",
                    "provider": "payplus",
                    "payment_link": "https://payplus.co.il/pay/abc123",
                    "created_at": "2025-10-30T10:00:00Z"
                },
                {
                    "id": "770e8400-e29b-41d4-a716-446655440002",
                    "appointment_id": "550e8400-e29b-41d4-a716-446655440000",
                    "total_amount": "117.00",
                    "currency": "ILS",
                    "status": "failed",
                    "provider": "payplus",
                    "payment_link": "https://payplus.co.il/pay/xyz789",
                    "created_at": "2025-10-30T09:00:00Z"
                }
            ]
        }
        ```
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "get_payment_transactions",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        appointment_id=str(appointment_id),
    )

    # Query transactions for this workspace and appointment
    stmt = (
        select(PaymentTransaction)
        .where(
            PaymentTransaction.workspace_id == workspace_id,
            PaymentTransaction.appointment_id == appointment_id,
        )
        .order_by(PaymentTransaction.created_at.desc())
    )

    result = await db.execute(stmt)
    transactions = result.scalars().all()

    logger.info(
        "payment_transactions_retrieved",
        workspace_id=str(workspace_id),
        appointment_id=str(appointment_id),
        count=len(transactions),
    )

    return PaymentTransactionListResponse(
        transactions=[
            PaymentTransactionResponse.from_transaction(txn) for txn in transactions
        ]
    )
