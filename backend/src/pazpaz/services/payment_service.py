"""Payment service for manual payment tracking (Phase 1).

This service provides simple payment tracking operations for therapists
who manually track bank transfer payments, cash, Bit, PayBox, etc.

Phase 1 Scope:
    - Mark appointments as paid/unpaid
    - Update payment prices
    - Track payment method and notes
    - No automated payment links or webhooks

Future Phases:
    - Phase 2+: Add automated payment provider support (Bit, PayBox APIs)
    - See docs/payment/PAYMENT_SYSTEM_ARCHITECTURE_V2.md for architecture

Usage:
    from pazpaz.services.payment_service import PaymentService
    from sqlalchemy.ext.asyncio import AsyncSession

    # Initialize service
    service = PaymentService(db_session)

    # Mark appointment as paid
    await service.mark_as_paid(
        appointment=appointment,
        payment_method="bank_transfer",
        notes="Client paid via Bit app, ref: 12345",
    )

    # Update payment price
    await service.update_payment_price(
        appointment=appointment,
        price=Decimal("150.00"),
    )

    # Mark as unpaid (reverse payment)
    await service.mark_as_unpaid(appointment=appointment)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.enums import PaymentStatus

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class PaymentService:
    """Service for manual payment tracking.

    This service handles simple payment tracking operations for therapists
    who manually mark appointments as paid after receiving bank transfers,
    cash, Bit payments, PayBox payments, etc.

    Attributes:
        db: Async SQLAlchemy session for database operations

    Example:
        >>> from pazpaz.services.payment_service import PaymentService
        >>> from decimal import Decimal
        >>>
        >>> service = PaymentService(db_session)
        >>>
        >>> # Mark appointment as paid
        >>> appointment = await service.mark_as_paid(
        ...     appointment=appointment,
        ...     payment_method="bank_transfer",
        ...     notes="Paid via Bit app",
        ... )
        >>> print(appointment.payment_status)
        paid
    """

    def __init__(self, db: AsyncSession):
        """Initialize payment service.

        Args:
            db: Async SQLAlchemy session for database operations
        """
        self.db = db

    async def mark_as_paid(
        self,
        appointment: Appointment,
        payment_method: str,
        notes: str | None = None,
    ) -> Appointment:
        """Mark appointment as paid.

        This method updates the appointment payment status to "paid" and
        records when the payment was received. Use this after the client
        has paid via bank transfer, cash, Bit, PayBox, or any other method.

        Args:
            appointment: Appointment to mark as paid
            payment_method: How client paid ("bank_transfer", "bit", "paybox", "cash", etc.)
            notes: Optional notes (invoice number, reference, etc.)

        Returns:
            Updated appointment with payment_status = "paid"

        Example:
            >>> appointment = await service.mark_as_paid(
            ...     appointment=appointment,
            ...     payment_method="bank_transfer",
            ...     notes="Bank ref: TX123456, Invoice: INV-001",
            ... )
            >>> print(appointment.payment_status)
            paid
            >>> print(appointment.paid_at)
            2025-11-02 14:30:00+00:00
        """
        logger.info(
            "marking_appointment_as_paid",
            appointment_id=str(appointment.id),
            payment_method=payment_method,
            has_notes=notes is not None,
        )

        # Update payment status
        appointment.payment_status = PaymentStatus.PAID
        appointment.paid_at = datetime.now(UTC)
        appointment.payment_method = payment_method

        if notes:
            appointment.payment_notes = notes

        # Commit changes
        await self.db.commit()
        await self.db.refresh(appointment)

        logger.info(
            "appointment_marked_as_paid",
            appointment_id=str(appointment.id),
            payment_method=payment_method,
            paid_at=appointment.paid_at.isoformat(),
        )

        return appointment

    async def mark_as_unpaid(self, appointment: Appointment) -> Appointment:
        """Mark appointment as unpaid (reverse payment).

        This method reverts a payment marking, setting the appointment back
        to "not_paid" status. Use this if a payment was marked incorrectly
        or if a payment failed/bounced.

        Args:
            appointment: Appointment to mark as unpaid

        Returns:
            Updated appointment with payment_status = "not_paid"

        Example:
            >>> appointment = await service.mark_as_unpaid(appointment)
            >>> print(appointment.payment_status)
            not_paid
            >>> print(appointment.paid_at)
            None
        """
        logger.info(
            "marking_appointment_as_unpaid",
            appointment_id=str(appointment.id),
            previous_status=appointment.payment_status.value
            if appointment.payment_status
            else None,
        )

        # Reset payment status
        appointment.payment_status = PaymentStatus.NOT_PAID
        appointment.paid_at = None
        appointment.payment_method = None
        appointment.payment_notes = None

        # Commit changes
        await self.db.commit()
        await self.db.refresh(appointment)

        logger.info(
            "appointment_marked_as_unpaid",
            appointment_id=str(appointment.id),
        )

        return appointment

    async def update_payment_price(
        self, appointment: Appointment, price: Decimal
    ) -> Appointment:
        """Update appointment payment price.

        This method sets or updates the price for an appointment.
        The price can be different from the service default price
        (discounts, sliding scale, promotional pricing, etc.).

        Args:
            appointment: Appointment to update
            price: New payment price (must be non-negative)

        Returns:
            Updated appointment with new payment_price

        Raises:
            ValueError: If price is negative

        Example:
            >>> # Standard price
            >>> appointment = await service.update_payment_price(
            ...     appointment, Decimal("150.00")
            ... )
            >>> print(appointment.payment_price)
            150.00
            >>>
            >>> # Discounted price
            >>> appointment = await service.update_payment_price(
            ...     appointment, Decimal("100.00")
            ... )
            >>> print(appointment.payment_price)
            100.00
        """
        if price < 0:
            raise ValueError(f"Payment price cannot be negative, got {price}")

        logger.info(
            "updating_payment_price",
            appointment_id=str(appointment.id),
            old_price=str(appointment.payment_price)
            if appointment.payment_price
            else None,
            new_price=str(price),
        )

        # Update price
        appointment.payment_price = price

        # Commit changes
        await self.db.commit()
        await self.db.refresh(appointment)

        logger.info(
            "payment_price_updated",
            appointment_id=str(appointment.id),
            payment_price=str(price),
        )

        return appointment

    async def update_payment_details(
        self,
        appointment: Appointment,
        price: Decimal | None = None,
        status: str | None = None,
        method: str | None = None,
        notes: str | None = None,
    ) -> Appointment:
        """Update multiple payment details at once.

        This is a convenience method for updating several payment fields
        in a single operation. Useful for bulk updates or API endpoints
        that accept partial updates.

        Args:
            appointment: Appointment to update
            price: Optional new payment price
            status: Optional new payment status ("paid", "not_paid", "waived")
            method: Optional payment method ("bank_transfer", "cash", etc.)
            notes: Optional payment notes

        Returns:
            Updated appointment

        Raises:
            ValueError: If price is negative or status is invalid

        Example:
            >>> appointment = await service.update_payment_details(
            ...     appointment=appointment,
            ...     price=Decimal("120.00"),
            ...     status="paid",
            ...     method="bank_transfer",
            ...     notes="Paid via Bit, Invoice INV-123",
            ... )
            >>> print(f"{appointment.payment_price} {appointment.payment_status}")
            120.00 paid
        """
        logger.info(
            "updating_payment_details",
            appointment_id=str(appointment.id),
            updating_price=price is not None,
            updating_status=status is not None,
            updating_method=method is not None,
            updating_notes=notes is not None,
        )

        # Update price if provided
        if price is not None:
            if price < 0:
                raise ValueError(f"Payment price cannot be negative, got {price}")
            appointment.payment_price = price

        # Update status if provided
        if status is not None:
            valid_statuses = {"not_paid", "paid", "payment_sent", "waived"}
            if status not in valid_statuses:
                raise ValueError(
                    f"Invalid payment status: {status}. Must be one of {valid_statuses}"
                )

            if status == "paid":
                appointment.payment_status = PaymentStatus.PAID
                appointment.paid_at = datetime.now(UTC)
            elif status == "not_paid":
                appointment.payment_status = PaymentStatus.NOT_PAID
                appointment.paid_at = None
            elif status == "waived":
                appointment.payment_status = PaymentStatus.WAIVED
                appointment.paid_at = datetime.now(UTC)
            # payment_sent status for future use (Phase 2+ automated providers)

        # Update method if provided
        if method is not None:
            appointment.payment_method = method

        # Update notes if provided
        if notes is not None:
            appointment.payment_notes = notes

        # Commit changes
        await self.db.commit()
        await self.db.refresh(appointment)

        logger.info(
            "payment_details_updated",
            appointment_id=str(appointment.id),
            payment_status=appointment.payment_status.value
            if appointment.payment_status
            else None,
        )

        return appointment
