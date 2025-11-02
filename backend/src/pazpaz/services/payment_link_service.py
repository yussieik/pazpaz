"""
Payment link generation service for Phase 1.5 Smart Payment Links.

This module generates smart payment links (SMS, URLs) without API integration.
It dispatches to type-specific generators based on workspace.payment_link_type.

Supported Payment Link Types:
- bit: SMS fallback with pre-filled Hebrew message (Bit doesn't have public deep link API)
- paybox: URL with amount parameter
- custom: Template-based URL with placeholders ({amount}, {client_name}, {appointment_id})
- bank: Plain text bank details (no link generation)

All functions handle edge cases (None values, empty strings) and return None
when payment links cannot be generated.

Usage:
    from pazpaz.models.workspace import Workspace
    from pazpaz.models.appointment import Appointment
    from pazpaz.services.payment_link_service import generate_payment_link

    link = generate_payment_link(workspace, appointment)
    if link:
        # Send link to client via SMS/email
        send_payment_request(client, link)
"""

from decimal import Decimal
from urllib.parse import parse_qs, urlencode, urlparse

from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.workspace import Workspace

logger = get_logger(__name__)


def generate_payment_link(
    workspace: Workspace,
    appointment: Appointment,
) -> str | None:
    """
    Generate payment link based on workspace configuration.

    Dispatches to type-specific generators based on workspace.payment_link_type.
    Returns None if payment links are disabled or configuration is invalid.

    Args:
        workspace: Workspace with payment link configuration
        appointment: Appointment with payment price

    Returns:
        Payment link string or None if:
        - Payment links disabled (payment_link_type is None)
        - Missing required configuration (payment_link_template is None)
        - No payment price set on appointment
        - Link generation fails

    Examples:
        >>> # Bit SMS link
        >>> workspace.payment_link_type = "bit"
        >>> workspace.payment_link_template = "050-123-4567"
        >>> appointment.payment_price = Decimal("150.00")
        >>> link = generate_payment_link(workspace, appointment)
        >>> link
        'sms:0501234567?&body=%D7%A9%D7%9C%D7%95%D7%9D...'

        >>> # PayBox URL
        >>> workspace.payment_link_type = "paybox"
        >>> workspace.payment_link_template = "https://paybox.co.il/p/yussie"
        >>> link = generate_payment_link(workspace, appointment)
        >>> link
        'https://paybox.co.il/p/yussie?amount=150.00&currency=ILS'

        >>> # Payment links disabled
        >>> workspace.payment_link_type = None
        >>> link = generate_payment_link(workspace, appointment)
        >>> link is None
        True
    """
    # Check if payment links enabled
    if not workspace.payment_link_type or not workspace.payment_link_template:
        logger.debug(
            "payment_links_disabled",
            workspace_id=str(workspace.id),
            payment_link_type=workspace.payment_link_type,
        )
        return None

    # Check if payment price set
    if not appointment.payment_price:
        logger.debug(
            "no_payment_price",
            workspace_id=str(workspace.id),
            appointment_id=str(appointment.id),
        )
        return None

    # Dispatch to type-specific generator
    link_type = workspace.payment_link_type.lower()
    template = workspace.payment_link_template

    try:
        if link_type == "bit":
            return _generate_bit_link(template, appointment.payment_price)
        elif link_type == "paybox":
            return _generate_paybox_link(template, appointment.payment_price)
        elif link_type == "custom":
            return _generate_custom_link(
                template, appointment.payment_price, appointment
            )
        elif link_type == "bank":
            # Bank details are plain text, not a clickable link
            return template
        else:
            logger.warning(
                "unknown_payment_link_type",
                workspace_id=str(workspace.id),
                payment_link_type=link_type,
            )
            return None

    except Exception as e:
        logger.error(
            "payment_link_generation_failed",
            workspace_id=str(workspace.id),
            appointment_id=str(appointment.id),
            payment_link_type=link_type,
            error=str(e),
            exc_info=True,
        )
        return None


def _generate_bit_link(bit_identifier: str, amount: Decimal) -> str:
    """
    Generate Bit payment link - supports both phone numbers (SMS) and web URLs.

    Bit has two modes:
    1. Phone number: Generate SMS link with Hebrew message (for Bit app users)
    2. Web URL: Add amount parameter to Bit Pay URL (for Bit Pay web users)

    Args:
        bit_identifier: Phone number (e.g., "050-123-4567") or Bit Pay URL
                       (e.g., "https://www.bitpay.co.il/app/me/...")
        amount: Payment amount in ILS

    Returns:
        SMS link (if phone) or web URL with amount (if URL)

    Examples:
        >>> # Phone number → SMS link
        >>> link = _generate_bit_link("050-123-4567", Decimal("150.00"))
        >>> link
        'sms:0501234567?&body=%D7%A9%D7%9C%D7%95%D7%9D%2C%20%D7%94%D7%99%D7%99%D7%AA%D7%99%20%D7%A8%D7%95%D7%A6%D7%94%20%D7%9C%D7%A9%D7%9C%D7%9D%20150.00%20%D7%A9%D7%B4%D7%97%20%D7%A2%D7%91%D7%95%D7%A8%20%D7%94%D7%A4%D7%92%D7%99%D7%A9%D7%94.%20%D7%AA%D7%95%D7%93%D7%94%21'

        >>> # Web URL → URL with amount
        >>> link = _generate_bit_link("https://www.bitpay.co.il/app/me/ABC123", Decimal("150.00"))
        >>> link
        'https://www.bitpay.co.il/app/me/ABC123?amount=150.00'
    """
    from urllib.parse import quote

    # Check if it's a URL (Bit Pay web link)
    if bit_identifier.startswith("http://") or bit_identifier.startswith("https://"):
        # Web URL mode: Add amount parameter
        separator = "&" if "?" in bit_identifier else "?"
        return f"{bit_identifier}{separator}amount={amount}"

    # Phone number mode: Generate SMS link
    # Clean phone number (remove dashes, spaces, parentheses)
    clean_phone = (
        bit_identifier.replace("-", "")
        .replace(" ", "")
        .replace("(", "")
        .replace(")", "")
    )

    # Hebrew message: "שלום, הייתי רוצה לשלם {amount} ש״ח עבור הפגישה. תודה!"
    hebrew_message = f"שלום, הייתי רוצה לשלם {amount} ש״ח עבור הפגישה. תודה!"

    # URL-encode the message
    encoded_message = quote(hebrew_message)

    # Return SMS link
    return f"sms:{clean_phone}?&body={encoded_message}"


def _generate_paybox_link(paybox_base_url: str, amount: Decimal) -> str:
    """
    Generate PayBox link with amount parameter.

    PayBox supports amount parameter in URL query string.
    Handles existing query params (use & if ? already in URL).

    Args:
        paybox_base_url: Base PayBox URL (e.g., "https://paybox.co.il/p/yussie")
        amount: Payment amount in ILS

    Returns:
        PayBox URL with amount parameter

    Examples:
        >>> # URL without existing query params
        >>> link = _generate_paybox_link("https://paybox.co.il/p/yussie", Decimal("150.00"))
        >>> link
        'https://paybox.co.il/p/yussie?amount=150.00&currency=ILS'

        >>> # URL with existing query params
        >>> link = _generate_paybox_link("https://paybox.co.il/p/yussie?ref=website", Decimal("75.50"))
        >>> link
        'https://paybox.co.il/p/yussie?ref=website&amount=75.50&currency=ILS'
    """
    # Parse URL to handle existing query params
    parsed = urlparse(paybox_base_url)

    # Get existing query params
    query_params = parse_qs(parsed.query)

    # Add amount and currency params
    query_params["amount"] = [str(amount)]
    query_params["currency"] = ["ILS"]

    # Rebuild query string
    # Convert list values back to single values for encoding
    query_dict = {
        k: v[0] if isinstance(v, list) else v for k, v in query_params.items()
    }
    new_query = urlencode(query_dict)

    # Rebuild URL
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"


def _generate_custom_link(
    template: str, amount: Decimal, appointment: Appointment
) -> str:
    """
    Generate custom payment link from template.

    Supports placeholders:
    - {amount}: Payment amount
    - {client_name}: Client full name (decrypted automatically by SQLAlchemy)
    - {appointment_id}: Appointment UUID

    Client name is URL-encoded to handle special characters.

    Args:
        template: URL template with placeholders
        amount: Payment amount
        appointment: Appointment object (with client relationship loaded)

    Returns:
        URL with placeholders replaced

    Examples:
        >>> # Template with amount placeholder
        >>> template = "https://pay.example.com/invoice?amount={amount}"
        >>> appointment.payment_price = Decimal("150.00")
        >>> link = _generate_custom_link(template, Decimal("150.00"), appointment)
        >>> link
        'https://pay.example.com/invoice?amount=150.00'

        >>> # Template with client name
        >>> template = "https://pay.example.com/client/{client_name}?amount={amount}"
        >>> appointment.client.first_name = "John"
        >>> appointment.client.last_name = "Doe"
        >>> link = _generate_custom_link(template, Decimal("150.00"), appointment)
        >>> link
        'https://pay.example.com/client/John%20Doe?amount=150.00'

        >>> # Template with appointment ID
        >>> template = "https://pay.example.com/appointment/{appointment_id}"
        >>> link = _generate_custom_link(template, Decimal("150.00"), appointment)
        >>> link
        'https://pay.example.com/appointment/...'
    """
    from urllib.parse import quote

    # Get client full name (decrypted automatically by EncryptedString type)
    client_name = ""
    if appointment.client:
        client_name = appointment.client.full_name

    # URL-encode client name to handle special characters
    encoded_client_name = quote(client_name)

    # Replace placeholders
    result = template
    result = result.replace("{amount}", str(amount))
    result = result.replace("{client_name}", encoded_client_name)
    result = result.replace("{appointment_id}", str(appointment.id))

    return result


def get_payment_link_display_text(workspace: Workspace) -> str:
    """
    Get user-friendly display text for payment link type.

    Returns localized labels for UI display.

    Args:
        workspace: Workspace with payment link configuration

    Returns:
        User-friendly label for payment link type

    Examples:
        >>> workspace.payment_link_type = "bit"
        >>> get_payment_link_display_text(workspace)
        'Bit (ביט)'

        >>> workspace.payment_link_type = "paybox"
        >>> get_payment_link_display_text(workspace)
        'PayBox'

        >>> workspace.payment_link_type = "bank"
        >>> get_payment_link_display_text(workspace)
        'Bank Transfer'

        >>> workspace.payment_link_type = None
        >>> get_payment_link_display_text(workspace)
        'Disabled'
    """
    if not workspace.payment_link_type:
        return "Disabled"

    display_map = {
        "bit": "Bit (ביט)",
        "paybox": "PayBox",
        "bank": "Bank Transfer",
        "custom": "Custom Payment Link",
    }

    return display_map.get(workspace.payment_link_type.lower(), "Unknown")
