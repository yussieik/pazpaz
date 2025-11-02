"""Payment-related enumerations.

This module defines enums for payment tracking in appointments.
These enums provide type safety and validation for payment-related fields.

Usage:
    from pazpaz.models.enums import PaymentStatus, PaymentMethod

    # In Pydantic schemas
    class AppointmentCreate(BaseModel):
        payment_status: PaymentStatus = PaymentStatus.NOT_PAID
        payment_method: PaymentMethod | None = None

    # In SQLAlchemy models
    payment_status: Mapped[str] = mapped_column(
        nullable=False,
        default=PaymentStatus.NOT_PAID.value
    )
"""

from enum import Enum


class PaymentStatus(str, Enum):
    """Appointment payment status.

    Tracks the current payment state for an appointment. This is independent
    of appointment or session status - clients may pay before, during, or after
    their appointment.

    Attributes:
        NOT_PAID: Payment has not been received (default)
        PAID: Payment has been received and confirmed
        PAYMENT_SENT: Payment link or invoice sent to client
        WAIVED: Payment waived (pro bono, scholarship, etc.)
    """

    NOT_PAID = "not_paid"
    PAID = "paid"
    PAYMENT_SENT = "payment_sent"
    WAIVED = "waived"


class PaymentMethod(str, Enum):
    """Payment collection method.

    Indicates how the payment was collected or will be collected.
    This helps therapists track payment sources and reconcile accounts.

    Attributes:
        CASH: Cash payment
        CARD: Credit/debit card payment (in-person or via terminal)
        BANK_TRANSFER: Direct bank transfer or wire
        BIT: Payment via Bit app (Israeli mobile payment)
        PAYBOX: Payment via PayBox (Israeli payment service)
        OTHER: Other payment method (specify in notes)
    """

    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    BIT = "bit"
    PAYBOX = "paybox"
    OTHER = "other"
