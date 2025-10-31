"""Payment service for orchestrating payment operations.

This service layer provides business logic for payment processing, including:
- Creating payment requests with VAT calculation
- Processing payment webhooks with idempotency checks
- Updating appointment payment status based on transaction state

Architecture:
    - Uses PaymentProvider abstraction for multi-provider support
    - Integrates with Redis for webhook idempotency
    - Manages PaymentTransaction lifecycle in database
    - Coordinates with Appointment model for payment status

Security:
    - Webhook signature verification via PaymentProvider
    - Idempotency checks prevent duplicate processing
    - All database operations scoped to workspace_id
    - Never logs credentials or PII

Performance:
    - Redis used for fast idempotency checks (O(1) lookup)
    - Database queries use selectinload for relationship efficiency
    - Transactions ensure data consistency

Usage:
    from pazpaz.services.payment_service import PaymentService
    from sqlalchemy.ext.asyncio import AsyncSession

    # Create payment request
    service = PaymentService(db_session)
    transaction = await service.create_payment_request(
        workspace=workspace,
        appointment=appointment,
        customer_email="client@example.com",
    )

    # Process webhook
    transaction = await service.process_webhook(
        workspace=workspace,
        payload=webhook_body,
        headers=request.headers,
    )
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.enums import PaymentStatus
from pazpaz.models.payment_transaction import PaymentTransaction
from pazpaz.payments.base import PaymentLinkRequest
from pazpaz.payments.exceptions import (
    InvalidCredentialsError,
    PaymentProviderError,
    WebhookVerificationError,
)
from pazpaz.payments.factory import get_payment_provider
from pazpaz.services.email_service import send_payment_request_email

if TYPE_CHECKING:
    from pazpaz.models.workspace import Workspace
    from pazpaz.payments.base import PaymentLinkResponse, WebhookPaymentData

logger = get_logger(__name__)

# Redis idempotency configuration
WEBHOOK_IDEMPOTENCY_TTL_SECONDS = 86400  # 24 hours


def get_redis_url() -> str:
    """Get Redis connection URL from settings.

    Returns:
        Redis connection URL

    Example:
        >>> url = get_redis_url()
        >>> print(url)
        redis://:password@localhost:6379/0
    """
    return settings.redis_url


class PaymentService:
    """Service for orchestrating payment operations.

    This service coordinates payment link creation, webhook processing,
    and payment transaction management. It acts as the business logic
    layer between the API endpoints and the payment provider abstraction.

    Attributes:
        db: Async SQLAlchemy session for database operations

    Example:
        >>> from pazpaz.services.payment_service import PaymentService
        >>> from sqlalchemy.ext.asyncio import AsyncSession
        >>>
        >>> # Initialize service
        >>> service = PaymentService(db_session)
        >>>
        >>> # Create payment request
        >>> transaction = await service.create_payment_request(
        ...     workspace=workspace,
        ...     appointment=appointment,
        ...     customer_email="client@example.com",
        ... )
        >>>
        >>> # Process webhook
        >>> transaction = await service.process_webhook(
        ...     workspace=workspace,
        ...     payload=webhook_body,
        ...     headers=request.headers,
        ... )
    """

    def __init__(self, db: AsyncSession):
        """Initialize payment service.

        Args:
            db: Async SQLAlchemy session for database operations
        """
        self.db = db

    @staticmethod
    def calculate_vat(
        total_amount: Decimal,
        vat_rate: Decimal,
        vat_registered: bool,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate VAT breakdown from total amount.

        This method splits a total amount into base amount and VAT amount
        based on workspace VAT registration status. Israeli tax law requires
        VAT-registered businesses to separate VAT from the base price.

        VAT Calculation Logic:
            - If VAT registered: Split total into base + VAT
              Formula: base = total / (1 + vat_rate/100)
              Formula: vat = total - base
            - If NOT VAT registered: No VAT separation
              base = total, vat = 0

        Args:
            total_amount: Total amount to split (ILS)
            vat_rate: VAT rate percentage (e.g., 17.00 for 17%)
            vat_registered: Whether workspace is VAT registered

        Returns:
            Tuple of (base_amount, vat_amount, total_amount)
            All amounts rounded to 2 decimal places

        Raises:
            ValueError: If total_amount is negative or zero
            ValueError: If vat_rate is negative

        Example:
            >>> # VAT registered with 17% rate
            >>> base, vat, total = PaymentService.calculate_vat(
            ...     Decimal("117.00"),
            ...     Decimal("17.00"),
            ...     True
            ... )
            >>> print(f"Base: {base}, VAT: {vat}, Total: {total}")
            Base: 100.00, VAT: 17.00, Total: 117.00

            >>> # Not VAT registered
            >>> base, vat, total = PaymentService.calculate_vat(
            ...     Decimal("100.00"),
            ...     Decimal("17.00"),
            ...     False
            ... )
            >>> print(f"Base: {base}, VAT: {vat}, Total: {total}")
            Base: 100.00, VAT: 0.00, Total: 100.00
        """
        # Validate inputs
        if total_amount <= 0:
            raise ValueError(f"Total amount must be positive, got {total_amount}")

        if vat_rate < 0:
            raise ValueError(f"VAT rate cannot be negative, got {vat_rate}")

        # Round total to 2 decimal places
        total = total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if vat_registered:
            # Calculate base amount: base = total / (1 + vat_rate/100)
            vat_multiplier = 1 + (vat_rate / 100)
            base = (total / vat_multiplier).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Calculate VAT amount: vat = total - base
            vat = (total - base).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            # Not VAT registered: no VAT separation
            base = total
            vat = Decimal("0.00")

        return (base, vat, total)

    async def create_payment_request(
        self,
        workspace: Workspace,
        appointment: Appointment,
        customer_email: str,
    ) -> PaymentTransaction:
        """Create payment request and generate payment link.

        This method orchestrates the payment link creation flow:
        1. Get payment provider for workspace
        2. Calculate VAT breakdown
        3. Create payment link via provider API
        4. Create PaymentTransaction record
        5. Update appointment payment status to "pending"

        Args:
            workspace: Workspace with payment provider configured
            appointment: Appointment to create payment for
            customer_email: Customer email for payment receipt

        Returns:
            Created PaymentTransaction with payment link

        Raises:
            InvalidCredentialsError: If provider credentials invalid
            PaymentProviderError: If provider API call fails
            ValueError: If appointment has no price set

        Example:
            >>> service = PaymentService(db_session)
            >>> transaction = await service.create_payment_request(
            ...     workspace=workspace,
            ...     appointment=appointment,
            ...     customer_email="client@example.com",
            ... )
            >>> print(transaction.provider_payment_link)
            https://payplus.co.il/pay/abc123
            >>> print(transaction.status)
            pending
        """
        # Validate appointment has price
        if appointment.payment_price is None or appointment.payment_price <= 0:
            raise ValueError(
                f"Appointment {appointment.id} has no price set. "
                "Set appointment.payment_price before creating payment request."
            )

        logger.info(
            "creating_payment_request",
            workspace_id=str(workspace.id),
            appointment_id=str(appointment.id),
            amount=str(appointment.payment_price),
        )

        try:
            # Get payment provider
            provider = get_payment_provider(workspace)

            # Calculate VAT breakdown
            base_amount, vat_amount, total_amount = self.calculate_vat(
                total_amount=appointment.payment_price,
                vat_rate=workspace.vat_rate,
                vat_registered=workspace.vat_registered,
            )

            logger.info(
                "vat_calculation_complete",
                workspace_id=str(workspace.id),
                appointment_id=str(appointment.id),
                base_amount=str(base_amount),
                vat_amount=str(vat_amount),
                total_amount=str(total_amount),
                vat_registered=workspace.vat_registered,
            )

            # Load client relationship if not already loaded
            if not appointment.client:
                await self.db.refresh(appointment, attribute_names=["client"])

            # Create payment link request
            link_request = PaymentLinkRequest(
                amount=total_amount,
                currency="ILS",
                description=(
                    f"Appointment payment - "
                    f"{appointment.client.full_name if appointment.client else 'Client'} - "
                    f"{appointment.scheduled_start.strftime('%Y-%m-%d %H:%M')}"
                ),
                customer_email=customer_email,
                customer_name=appointment.client.full_name
                if appointment.client
                else None,
                metadata={
                    "workspace_id": str(workspace.id),
                    "appointment_id": str(appointment.id),
                },
            )

            # Call provider API to create payment link
            link_response: PaymentLinkResponse = await provider.create_payment_link(
                link_request
            )

            logger.info(
                "payment_link_created",
                workspace_id=str(workspace.id),
                appointment_id=str(appointment.id),
                provider=workspace.payment_provider,
                provider_transaction_id=link_response.provider_transaction_id,
            )

            # Create payment transaction record
            transaction = PaymentTransaction(
                workspace_id=workspace.id,
                appointment_id=appointment.id,
                base_amount=base_amount,
                vat_amount=vat_amount,
                total_amount=total_amount,
                currency="ILS",
                payment_method="online_card",
                status="pending",
                provider=workspace.payment_provider,
                provider_transaction_id=link_response.provider_transaction_id,
                provider_payment_link=link_response.payment_link_url,
            )

            self.db.add(transaction)

            # Update appointment payment status to payment_sent (link sent to client)
            appointment.payment_status = PaymentStatus.PAYMENT_SENT.value

            # Commit transaction
            await self.db.commit()
            await self.db.refresh(transaction)

            logger.info(
                "payment_request_created",
                workspace_id=str(workspace.id),
                appointment_id=str(appointment.id),
                transaction_id=str(transaction.id),
                payment_link=link_response.payment_link_url,
            )

            # Send payment request email to client
            # Email failure should NOT fail payment creation
            try:
                email_sent = await send_payment_request_email(
                    customer_email=customer_email,
                    customer_name=appointment.client.full_name
                    if appointment.client
                    else "Valued Client",
                    therapist_name=workspace.name,
                    appointment_date=appointment.scheduled_start,
                    amount=transaction.total_amount,
                    currency=transaction.currency,
                    payment_link=transaction.provider_payment_link,
                )

                if email_sent:
                    logger.info(
                        "payment_request_email_sent",
                        transaction_id=str(transaction.id),
                        workspace_id=str(workspace.id),
                    )
                else:
                    logger.warning(
                        "payment_request_email_failed",
                        transaction_id=str(transaction.id),
                        workspace_id=str(workspace.id),
                        message="Email send returned False",
                    )

            except Exception as e:
                # Don't fail payment creation if email fails
                logger.error(
                    "payment_request_email_error",
                    error=str(e),
                    transaction_id=str(transaction.id),
                    workspace_id=str(workspace.id),
                    exc_info=True,
                )

            return transaction

        except InvalidCredentialsError as e:
            logger.error(
                "invalid_payment_credentials",
                workspace_id=str(workspace.id),
                provider=workspace.payment_provider,
                error=str(e),
            )

            # Create failed transaction record
            transaction = PaymentTransaction(
                workspace_id=workspace.id,
                appointment_id=appointment.id,
                base_amount=Decimal("0.00"),
                vat_amount=Decimal("0.00"),
                total_amount=appointment.payment_price or Decimal("0.00"),
                currency="ILS",
                payment_method="online_card",
                status="failed",
                provider=workspace.payment_provider,
                failed_at=datetime.now(UTC),
                failure_reason=f"Invalid payment provider credentials: {e.message}",
            )

            self.db.add(transaction)
            await self.db.commit()
            await self.db.refresh(transaction)

            # Re-raise exception
            raise

        except PaymentProviderError as e:
            logger.error(
                "payment_provider_error",
                workspace_id=str(workspace.id),
                appointment_id=str(appointment.id),
                provider=workspace.payment_provider,
                error=str(e),
                exc_info=True,
            )

            # Create failed transaction record
            transaction = PaymentTransaction(
                workspace_id=workspace.id,
                appointment_id=appointment.id,
                base_amount=Decimal("0.00"),
                vat_amount=Decimal("0.00"),
                total_amount=appointment.payment_price or Decimal("0.00"),
                currency="ILS",
                payment_method="online_card",
                status="failed",
                provider=workspace.payment_provider,
                failed_at=datetime.now(UTC),
                failure_reason=f"Payment provider error: {e.message}",
            )

            self.db.add(transaction)
            await self.db.commit()
            await self.db.refresh(transaction)

            # Re-raise exception
            raise

    async def process_webhook(
        self,
        workspace: Workspace,
        payload: str,
        headers: dict[str, str],
    ) -> PaymentTransaction:
        """Process payment webhook and update transaction status.

        This method handles incoming webhooks from payment providers:
        1. Get payment provider for workspace
        2. Verify webhook signature for security
        3. Check idempotency (prevent duplicate processing)
        4. Parse webhook payload
        5. Find transaction by provider_transaction_id
        6. Update transaction status
        7. Update appointment payment status

        Idempotency:
            Uses Redis to track processed webhook IDs with 24-hour TTL.
            If webhook already processed, returns existing transaction
            without re-processing.

        Args:
            workspace: Workspace with payment provider configured
            payload: Raw webhook body as string
            headers: HTTP headers including signature

        Returns:
            Updated PaymentTransaction

        Raises:
            WebhookVerificationError: If signature verification fails
            PaymentProviderError: If webhook parsing fails
            ValueError: If transaction not found

        Example:
            >>> service = PaymentService(db_session)
            >>> transaction = await service.process_webhook(
            ...     workspace=workspace,
            ...     payload=request.body,
            ...     headers=dict(request.headers),
            ... )
            >>> print(transaction.status)
            completed
        """
        logger.info(
            "processing_payment_webhook",
            workspace_id=str(workspace.id),
            provider=workspace.payment_provider,
        )

        # Get payment provider
        provider = get_payment_provider(workspace)

        # Verify webhook signature
        is_valid = await provider.verify_webhook(payload.encode(), headers)
        if not is_valid:
            logger.warning(
                "webhook_verification_failed",
                workspace_id=str(workspace.id),
                provider=workspace.payment_provider,
            )
            raise WebhookVerificationError(
                "Webhook signature verification failed",
                provider=workspace.payment_provider,
            )

        logger.info(
            "webhook_signature_verified",
            workspace_id=str(workspace.id),
            provider=workspace.payment_provider,
        )

        # Parse webhook payload
        payload_dict = json.loads(payload)
        webhook_data: WebhookPaymentData = await provider.parse_webhook_payment(
            payload_dict
        )

        logger.info(
            "webhook_parsed",
            workspace_id=str(workspace.id),
            provider=workspace.payment_provider,
            provider_transaction_id=webhook_data.provider_transaction_id,
            status=webhook_data.status,
        )

        # Check idempotency using Redis
        redis_client = await redis.from_url(get_redis_url())
        try:
            idempotency_key = f"webhook:{webhook_data.provider_transaction_id}"

            # Check if already processed
            if await redis_client.get(idempotency_key):
                logger.info(
                    "webhook_already_processed",
                    workspace_id=str(workspace.id),
                    provider_transaction_id=webhook_data.provider_transaction_id,
                    message="Webhook already processed, returning existing transaction",
                )

                # Find and return existing transaction
                stmt = (
                    select(PaymentTransaction)
                    .options(selectinload(PaymentTransaction.appointment))
                    .where(
                        PaymentTransaction.workspace_id == workspace.id,
                        PaymentTransaction.provider_transaction_id
                        == webhook_data.provider_transaction_id,
                    )
                )
                result = await self.db.execute(stmt)
                transaction = result.scalar_one()

                return transaction

            # Mark as processed (24h TTL)
            await redis_client.setex(
                idempotency_key, WEBHOOK_IDEMPOTENCY_TTL_SECONDS, "1"
            )

            logger.info(
                "webhook_idempotency_key_set",
                workspace_id=str(workspace.id),
                provider_transaction_id=webhook_data.provider_transaction_id,
                ttl_seconds=WEBHOOK_IDEMPOTENCY_TTL_SECONDS,
            )

        finally:
            await redis_client.aclose()

        # Find transaction by provider_transaction_id and workspace_id
        stmt = (
            select(PaymentTransaction)
            .options(selectinload(PaymentTransaction.appointment))
            .where(
                PaymentTransaction.workspace_id == workspace.id,
                PaymentTransaction.provider_transaction_id
                == webhook_data.provider_transaction_id,
            )
        )
        result = await self.db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            logger.error(
                "transaction_not_found",
                workspace_id=str(workspace.id),
                provider_transaction_id=webhook_data.provider_transaction_id,
            )
            raise ValueError(
                f"Transaction not found for provider_transaction_id: "
                f"{webhook_data.provider_transaction_id}"
            )

        # Update transaction status based on webhook data
        transaction.status = webhook_data.status

        if webhook_data.status == "completed":
            transaction.completed_at = webhook_data.completed_at or datetime.now(UTC)

            # Update appointment payment status and paid_at timestamp
            if transaction.appointment:
                transaction.appointment.payment_status = PaymentStatus.PAID.value
                transaction.appointment.paid_at = datetime.now(UTC)

            logger.info(
                "payment_completed",
                workspace_id=str(workspace.id),
                transaction_id=str(transaction.id),
                appointment_id=str(transaction.appointment_id)
                if transaction.appointment_id
                else None,
                amount=str(transaction.total_amount),
            )

        elif webhook_data.status == "failed":
            transaction.failed_at = datetime.now(UTC)
            transaction.failure_reason = webhook_data.failure_reason

            # Update appointment payment status back to not_paid (payment failed)
            if transaction.appointment:
                transaction.appointment.payment_status = PaymentStatus.NOT_PAID.value
                transaction.appointment.paid_at = None

            logger.warning(
                "payment_failed",
                workspace_id=str(workspace.id),
                transaction_id=str(transaction.id),
                appointment_id=str(transaction.appointment_id)
                if transaction.appointment_id
                else None,
                failure_reason=webhook_data.failure_reason,
            )

        elif webhook_data.status == "refunded":
            transaction.refunded_at = datetime.now(UTC)

            # Update appointment payment status to not_paid (refunded = effectively unpaid)
            if transaction.appointment:
                transaction.appointment.payment_status = PaymentStatus.NOT_PAID.value
                transaction.appointment.paid_at = None

            logger.info(
                "payment_refunded",
                workspace_id=str(workspace.id),
                transaction_id=str(transaction.id),
                appointment_id=str(transaction.appointment_id)
                if transaction.appointment_id
                else None,
            )

        # Update provider metadata if present
        if webhook_data.metadata:
            transaction.provider_metadata = webhook_data.metadata

        # Commit transaction
        await self.db.commit()
        await self.db.refresh(transaction)

        logger.info(
            "webhook_processed",
            workspace_id=str(workspace.id),
            transaction_id=str(transaction.id),
            status=transaction.status,
        )

        return transaction
