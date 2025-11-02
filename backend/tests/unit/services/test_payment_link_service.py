"""Unit tests for payment link service."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from pazpaz.services.payment_link_service import (
    _generate_bit_link,
    _generate_custom_link,
    _generate_paybox_link,
    generate_payment_link,
    get_payment_link_display_text,
)


class TestGenerateBitLink:
    """Test Bit link generation."""

    def test_bit_link_with_dashes(self):
        """Test Bit link generation with phone number containing dashes."""
        # Arrange
        phone = "050-123-4567"
        amount = Decimal("150.00")

        # Act
        result = _generate_bit_link(phone, amount)

        # Assert
        assert result.startswith("sms:0501234567?&body=")
        assert "150.00" in result
        # Verify Hebrew message is URL-encoded (check for %D7 which is Hebrew)
        assert "%D7" in result

    def test_bit_link_with_spaces(self):
        """Test Bit link generation with phone number containing spaces."""
        # Arrange
        phone = "050 123 4567"
        amount = Decimal("75.50")

        # Act
        result = _generate_bit_link(phone, amount)

        # Assert
        assert result.startswith("sms:0501234567?&body=")
        assert "75.50" in result
        assert "%D7" in result

    def test_bit_link_hebrew_message_encoded(self):
        """Test Bit link Hebrew message is properly URL-encoded."""
        # Arrange
        phone = "0501234567"
        amount = Decimal("200.00")

        # Act
        result = _generate_bit_link(phone, amount)

        # Assert
        # Hebrew characters should be URL-encoded
        assert "%D7%A9%D7%9C%D7%95%D7%9D" in result  # שלום encoded
        # Amount should appear in the message
        assert "200.00" in result

    def test_bit_link_amount_appears_in_link(self):
        """Test amount appears correctly in Bit SMS link."""
        # Arrange
        phone = "050-123-4567"
        amount = Decimal("99.99")

        # Act
        result = _generate_bit_link(phone, amount)

        # Assert
        assert "99.99" in result

    def test_bit_link_with_parentheses(self):
        """Test Bit link with phone number containing parentheses."""
        # Arrange
        phone = "(050)123-4567"
        amount = Decimal("50.00")

        # Act
        result = _generate_bit_link(phone, amount)

        # Assert
        assert result.startswith("sms:0501234567?&body=")
        assert "50.00" in result

    def test_bit_link_with_web_url(self):
        """Test Bit link with Bit Pay web URL (instead of phone number)."""
        # Arrange
        bit_pay_url = "https://www.bitpay.co.il/app/me/ABC123"
        amount = Decimal("150.00")

        # Act
        result = _generate_bit_link(bit_pay_url, amount)

        # Assert
        assert result == "https://www.bitpay.co.il/app/me/ABC123?amount=150.00"
        assert result.startswith("https://")
        assert "amount=150.00" in result

    def test_bit_link_with_web_url_existing_params(self):
        """Test Bit link with Bit Pay URL that already has query parameters."""
        # Arrange
        bit_pay_url = "https://www.bitpay.co.il/app/me/ABC123?lang=he"
        amount = Decimal("200.00")

        # Act
        result = _generate_bit_link(bit_pay_url, amount)

        # Assert
        assert result == "https://www.bitpay.co.il/app/me/ABC123?lang=he&amount=200.00"
        assert "lang=he" in result
        assert "&amount=200.00" in result

    def test_bit_link_with_http_url(self):
        """Test Bit link with HTTP URL (non-HTTPS)."""
        # Arrange
        bit_url = "http://bitpay.co.il/app/me/ABC123"
        amount = Decimal("100.00")

        # Act
        result = _generate_bit_link(bit_url, amount)

        # Assert
        assert result == "http://bitpay.co.il/app/me/ABC123?amount=100.00"
        assert "amount=100.00" in result


class TestGeneratePayBoxLink:
    """Test PayBox link generation."""

    def test_paybox_url_without_existing_query_params(self):
        """Test PayBox link when base URL has no query params."""
        # Arrange
        base_url = "https://paybox.co.il/p/yussie"
        amount = Decimal("150.00")

        # Act
        result = _generate_paybox_link(base_url, amount)

        # Assert
        assert result.startswith("https://paybox.co.il/p/yussie?")
        assert "amount=150.00" in result or "amount=150.0" in result
        assert "currency=ILS" in result

    def test_paybox_url_with_existing_query_params(self):
        """Test PayBox link when base URL already has query params."""
        # Arrange
        base_url = "https://paybox.co.il/p/yussie?ref=website"
        amount = Decimal("75.50")

        # Act
        result = _generate_paybox_link(base_url, amount)

        # Assert
        assert result.startswith("https://paybox.co.il/p/yussie?")
        assert "ref=website" in result
        assert "amount=75.5" in result or "amount=75.50" in result
        assert "currency=ILS" in result

    def test_paybox_preserves_scheme_and_host(self):
        """Test PayBox link preserves scheme and host."""
        # Arrange
        base_url = "https://custom.paybox.example.com/payment/user123"
        amount = Decimal("100.00")

        # Act
        result = _generate_paybox_link(base_url, amount)

        # Assert
        assert result.startswith("https://custom.paybox.example.com/payment/user123?")
        assert "amount=100" in result
        assert "currency=ILS" in result


class TestGenerateCustomLink:
    """Test custom link generation."""

    def test_custom_link_amount_placeholder(self):
        """Test custom link replaces {amount} placeholder."""
        # Arrange
        template = "https://pay.example.com/invoice?amount={amount}"
        amount = Decimal("150.00")

        # Create mock appointment
        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.client = None

        # Act
        result = _generate_custom_link(template, amount, appointment)

        # Assert
        assert "amount=150.00" in result or "amount=150.0" in result
        assert "{amount}" not in result

    def test_custom_link_client_name_placeholder(self):
        """Test custom link replaces {client_name} placeholder with URL encoding."""
        # Arrange
        template = "https://pay.example.com/client/{client_name}?amount={amount}"
        amount = Decimal("150.00")

        # Create mock appointment with client
        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.client = MagicMock()
        appointment.client.full_name = "John Doe"

        # Act
        result = _generate_custom_link(template, amount, appointment)

        # Assert
        assert "John%20Doe" in result  # URL-encoded space
        assert "{client_name}" not in result

    def test_custom_link_appointment_id_placeholder(self):
        """Test custom link replaces {appointment_id} placeholder."""
        # Arrange
        template = "https://pay.example.com/appointment/{appointment_id}"
        amount = Decimal("100.00")
        appointment_id = uuid.uuid4()

        # Create mock appointment
        appointment = MagicMock()
        appointment.id = appointment_id
        appointment.client = None

        # Act
        result = _generate_custom_link(template, amount, appointment)

        # Assert
        assert str(appointment_id) in result
        assert "{appointment_id}" not in result

    def test_custom_link_all_placeholders(self):
        """Test custom link with all placeholders."""
        # Arrange
        template = (
            "https://pay.example.com/{appointment_id}/{client_name}?amount={amount}"
        )
        amount = Decimal("250.00")
        appointment_id = uuid.uuid4()

        # Create mock appointment with client
        appointment = MagicMock()
        appointment.id = appointment_id
        appointment.client = MagicMock()
        appointment.client.full_name = "Jane Smith"

        # Act
        result = _generate_custom_link(template, amount, appointment)

        # Assert
        assert str(appointment_id) in result
        assert "Jane%20Smith" in result
        assert "amount=250" in result
        assert "{appointment_id}" not in result
        assert "{client_name}" not in result
        assert "{amount}" not in result

    def test_custom_link_special_characters_in_client_name(self):
        """Test custom link URL-encodes special characters in client name."""
        # Arrange
        template = "https://pay.example.com/client/{client_name}"
        amount = Decimal("100.00")

        # Create mock appointment with client having special characters
        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.client = MagicMock()
        appointment.client.full_name = "José García"

        # Act
        result = _generate_custom_link(template, amount, appointment)

        # Assert
        # Special characters should be URL-encoded
        assert "Jos%C3%A9" in result  # é encoded
        assert "Garc%C3%ADa" in result  # í encoded

    def test_custom_link_no_client(self):
        """Test custom link when appointment has no client (client_name should be empty)."""
        # Arrange
        template = "https://pay.example.com/client/{client_name}/pay?amount={amount}"
        amount = Decimal("50.00")

        # Create mock appointment without client
        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.client = None

        # Act
        result = _generate_custom_link(template, amount, appointment)

        # Assert
        # Empty client name should result in empty string (not error)
        assert "https://pay.example.com/client//pay" in result
        assert "amount=50" in result


class TestGeneratePaymentLink:
    """Test main payment link generation function."""

    def test_bit_type_returns_sms_link(self):
        """Test payment link generation for Bit type."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "bit"
        workspace.payment_link_template = "050-123-4567"

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("150.00")

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is not None
        assert result.startswith("sms:")
        assert "0501234567" in result

    def test_paybox_type_returns_url_with_amount(self):
        """Test payment link generation for PayBox type."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "paybox"
        workspace.payment_link_template = "https://paybox.co.il/p/yussie"

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("200.00")

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is not None
        assert result.startswith("https://paybox.co.il/p/yussie?")
        assert "amount=200" in result
        assert "currency=ILS" in result

    def test_bank_type_returns_template(self):
        """Test payment link generation for bank transfer type."""
        # Arrange
        bank_details = "Bank: Example Bank\nAccount: 123456\nBranch: 789"
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "bank"
        workspace.payment_link_template = bank_details

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("100.00")

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result == bank_details

    def test_custom_type_returns_custom_url(self):
        """Test payment link generation for custom type."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "custom"
        workspace.payment_link_template = "https://pay.example.com?amount={amount}"

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("300.00")
        appointment.client = None

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is not None
        assert "https://pay.example.com?amount=300" in result

    def test_returns_none_when_payment_link_type_is_none(self):
        """Test returns None when payment links are disabled (type is None)."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = None
        workspace.payment_link_template = "some-template"

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("150.00")

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is None

    def test_returns_none_when_template_is_none(self):
        """Test returns None when payment_link_template is None."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "bit"
        workspace.payment_link_template = None

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("150.00")

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is None

    def test_returns_none_when_payment_price_is_none(self):
        """Test returns None when appointment has no payment price."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "bit"
        workspace.payment_link_template = "050-123-4567"

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = None

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is None

    def test_unknown_payment_link_type_returns_none(self):
        """Test returns None for unknown payment link type."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "unknown_type"
        workspace.payment_link_template = "some-template"

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("150.00")

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is None

    def test_case_insensitive_payment_link_type(self):
        """Test payment link type is case-insensitive."""
        # Arrange
        workspace = MagicMock()
        workspace.id = uuid.uuid4()
        workspace.payment_link_type = "BIT"  # Uppercase
        workspace.payment_link_template = "050-123-4567"

        appointment = MagicMock()
        appointment.id = uuid.uuid4()
        appointment.payment_price = Decimal("150.00")

        # Act
        result = generate_payment_link(workspace, appointment)

        # Assert
        assert result is not None
        assert result.startswith("sms:")


class TestGetPaymentLinkDisplayText:
    """Test display text helper."""

    def test_bit_display_text(self):
        """Test display text for Bit type."""
        # Arrange
        workspace = MagicMock()
        workspace.payment_link_type = "bit"

        # Act
        result = get_payment_link_display_text(workspace)

        # Assert
        assert result == "Bit (ביט)"

    def test_paybox_display_text(self):
        """Test display text for PayBox type."""
        # Arrange
        workspace = MagicMock()
        workspace.payment_link_type = "paybox"

        # Act
        result = get_payment_link_display_text(workspace)

        # Assert
        assert result == "PayBox"

    def test_bank_display_text(self):
        """Test display text for bank transfer type."""
        # Arrange
        workspace = MagicMock()
        workspace.payment_link_type = "bank"

        # Act
        result = get_payment_link_display_text(workspace)

        # Assert
        assert result == "Bank Transfer"

    def test_custom_display_text(self):
        """Test display text for custom type."""
        # Arrange
        workspace = MagicMock()
        workspace.payment_link_type = "custom"

        # Act
        result = get_payment_link_display_text(workspace)

        # Assert
        assert result == "Custom Payment Link"

    def test_disabled_display_text(self):
        """Test display text when payment links are disabled."""
        # Arrange
        workspace = MagicMock()
        workspace.payment_link_type = None

        # Act
        result = get_payment_link_display_text(workspace)

        # Assert
        assert result == "Disabled"

    def test_unknown_type_display_text(self):
        """Test display text for unknown type."""
        # Arrange
        workspace = MagicMock()
        workspace.payment_link_type = "unknown_type"

        # Act
        result = get_payment_link_display_text(workspace)

        # Assert
        assert result == "Unknown"

    def test_case_insensitive_display_text(self):
        """Test display text is case-insensitive."""
        # Arrange
        workspace = MagicMock()
        workspace.payment_link_type = "BIT"  # Uppercase

        # Act
        result = get_payment_link_display_text(workspace)

        # Assert
        assert result == "Bit (ביט)"
