"""Payment feature flag detection utilities.

This module provides utility classes for checking payment feature availability
in the PazPaz application. These utilities are part of Phase 0 payment infrastructure
and only implement feature flag detection - no actual payment processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class PaymentFeatureChecker:
    """Utility class for checking payment feature availability.

    This class provides static methods to determine if payment features are enabled
    and whether payment requests can be sent for appointments. All methods are
    stateless and can be called without instantiation.

    Phase 0 Implementation:
        This is part of the foundational payment infrastructure. These methods
        only check feature flags and validate conditions - they do not trigger
        any actual payment processing.

    Example:
        >>> from pazpaz.models import Workspace, Appointment
        >>> from pazpaz.utils.payment_features import PaymentFeatureChecker
        >>>
        >>> # Check if payments enabled for workspace
        >>> workspace = Workspace(payment_provider="payplus")
        >>> PaymentFeatureChecker.is_enabled(workspace)
        True
        >>>
        >>> # Check if payment request can be sent
        >>> appointment = Appointment(
        ...     workspace=workspace,
        ...     payment_price=Decimal("100.00"),
        ...     status="attended",
        ...     payment_status="unpaid"
        ... )
        >>> can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)
        >>> print(f"Can send: {can_send}, Reason: {reason}")
        Can send: True, Reason: Can send payment request
    """

    @staticmethod
    def is_enabled(workspace: Workspace) -> bool:
        """Check if payment processing is enabled for workspace.

        A workspace has payments enabled if it has a payment provider configured.
        The payment_provider field acts as the feature flag:
        - None/NULL: Payments disabled
        - "payplus"/"meshulam"/"stripe": Payments enabled

        Args:
            workspace: The workspace to check

        Returns:
            True if payment_provider is configured (not None), False otherwise

        Example:
            >>> workspace = Workspace(payment_provider="payplus")
            >>> PaymentFeatureChecker.is_enabled(workspace)
            True
            >>>
            >>> workspace = Workspace(payment_provider=None)
            >>> PaymentFeatureChecker.is_enabled(workspace)
            False
        """
        return workspace.payment_provider is not None

    @staticmethod
    def can_send_payment_request(appointment: Appointment) -> tuple[bool, str]:
        """Check if payment request can be sent for appointment.

        Validates all conditions required to send a payment request to a client:
        1. Payments must be enabled for the workspace
        2. Appointment must have a price set
        3. Appointment must be completed (status = "attended")
        4. Payment must not already be paid
        5. Payment must not already be pending

        This method does NOT send payment requests - it only validates whether
        sending would be allowed. Actual payment request creation happens in Phase 1.

        Args:
            appointment: The appointment to check (must have workspace relationship loaded)

        Returns:
            Tuple of (can_send: bool, reason: str)
            - If can_send is True, reason is "Can send payment request"
            - If can_send is False, reason explains which validation failed

        Example:
            >>> # Valid case - all checks pass
            >>> appointment = Appointment(
            ...     workspace=Workspace(payment_provider="payplus"),
            ...     payment_price=Decimal("150.00"),
            ...     status="attended",
            ...     payment_status="unpaid"
            ... )
            >>> can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)
            >>> can_send
            True
            >>> reason
            'Can send payment request'
            >>>
            >>> # Invalid case - no price set
            >>> appointment = Appointment(
            ...     workspace=Workspace(payment_provider="payplus"),
            ...     payment_price=None,
            ...     status="attended",
            ...     payment_status="unpaid"
            ... )
            >>> can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)
            >>> can_send
            False
            >>> reason
            'No price set for appointment'
            >>>
            >>> # Invalid case - not completed yet
            >>> appointment = Appointment(
            ...     workspace=Workspace(payment_provider="payplus"),
            ...     payment_price=Decimal("150.00"),
            ...     status="scheduled",
            ...     payment_status="unpaid"
            ... )
            >>> can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)
            >>> can_send
            False
            >>> reason
            'Appointment not completed yet'
            >>>
            >>> # Invalid case - already paid
            >>> appointment = Appointment(
            ...     workspace=Workspace(payment_provider="payplus"),
            ...     payment_price=Decimal("150.00"),
            ...     status="attended",
            ...     payment_status="paid"
            ... )
            >>> can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)
            >>> can_send
            False
            >>> reason
            'Already paid'
        """
        workspace = appointment.workspace

        # Check 1: Payments enabled for workspace
        if not PaymentFeatureChecker.is_enabled(workspace):
            return False, "Payments not enabled for workspace"

        # Check 2: Appointment has price set
        if appointment.payment_price is None:
            return False, "No price set for appointment"

        # Check 3: Appointment is completed (status = "attended")
        # Note: In PazPaz, "attended" is the status for completed appointments
        if appointment.status.value != "attended":
            return False, "Appointment not completed yet"

        # Check 4: Not already paid
        if appointment.payment_status == "paid":
            return False, "Already paid"

        # Check 5: Not already pending
        if appointment.payment_status == "pending":
            return False, "Payment request already sent"

        # All checks passed
        return True, "Can send payment request"
