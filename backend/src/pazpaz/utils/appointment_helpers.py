"""Helper utilities for appointment API operations."""

from __future__ import annotations

from pazpaz.models.appointment import Appointment
from pazpaz.schemas.appointment import AppointmentResponse, ClientSummary


def build_appointment_response_with_client(
    appointment: Appointment,
) -> AppointmentResponse:
    """
    Build an AppointmentResponse with populated ClientSummary.

    Converts an Appointment model instance (with eagerly loaded client relationship)
    into an AppointmentResponse schema, populating the client field with a
    ClientSummary if the client relationship exists.

    This helper eliminates duplicate client summary construction logic across
    appointment API endpoints (create, list, get, update).

    Args:
        appointment: Appointment instance with client relationship loaded
            (use selectinload(Appointment.client) in query)

    Returns:
        AppointmentResponse with client field populated if client exists

    Example:
        >>> from sqlalchemy import select
        >>> from sqlalchemy.orm import selectinload
        >>> query = (
        ...     select(Appointment)
        ...     .where(Appointment.id == appointment_id)
        ...     .options(selectinload(Appointment.client))
        ... )
        >>> result = await db.execute(query)
        >>> appointment = result.scalar_one()
        >>> response = build_appointment_response_with_client(appointment)
    """
    response_data = AppointmentResponse.model_validate(appointment)

    if appointment.client:
        response_data.client = ClientSummary(
            id=appointment.client.id,
            first_name=appointment.client.first_name,
            last_name=appointment.client.last_name,
            full_name=appointment.client.full_name,
        )

    return response_data
