"""Test suite for application configuration settings.

This test suite verifies:
1. Trusted proxy IP validation (critical security control)
2. Configuration validation and error handling
3. is_trusted_proxy() method for IP trust verification
4. IPv4 and IPv6 support
5. CIDR range support
6. Invalid input handling

Security Context:
Trusted proxy configuration is a critical security control for rate limiting.
Misconfigured trusted proxies can allow IP spoofing attacks that bypass
rate limits, location-based restrictions, and audit logging.
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from pazpaz.core.config import Settings

# These are unit tests that don't require async or database fixtures
# Remove asyncio marker to avoid triggering database setup


# ============================================================================
# Test Group 1: Trusted Proxy IP Validation (Configuration)
# ============================================================================


class TestTrustedProxyIPValidation:
    """Test trusted_proxy_ips configuration validation at startup."""

    def test_valid_single_ipv4_address(self):
        """Valid single IPv4 address should be accepted."""
        settings = Settings(trusted_proxy_ips="127.0.0.1")
        assert settings.trusted_proxy_ips == "127.0.0.1"

    def test_valid_multiple_ipv4_addresses(self):
        """Valid multiple IPv4 addresses should be accepted."""
        settings = Settings(trusted_proxy_ips="127.0.0.1,192.168.1.1,10.0.0.1")
        assert settings.trusted_proxy_ips == "127.0.0.1,192.168.1.1,10.0.0.1"

    def test_valid_single_cidr_range(self):
        """Valid CIDR range should be accepted."""
        settings = Settings(trusted_proxy_ips="10.0.0.0/8")
        assert settings.trusted_proxy_ips == "10.0.0.0/8"

    def test_valid_multiple_cidr_ranges(self):
        """Valid multiple CIDR ranges should be accepted."""
        settings = Settings(
            trusted_proxy_ips="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
        )
        assert settings.trusted_proxy_ips == "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

    def test_valid_mixed_ips_and_cidrs(self):
        """Mixed IP addresses and CIDR ranges should be accepted."""
        settings = Settings(trusted_proxy_ips="127.0.0.1,10.0.0.0/8,192.168.1.1")
        assert settings.trusted_proxy_ips == "127.0.0.1,10.0.0.0/8,192.168.1.1"

    def test_valid_ipv6_address(self):
        """Valid IPv6 address should be accepted."""
        settings = Settings(trusted_proxy_ips="::1,2001:db8::1")
        assert settings.trusted_proxy_ips == "::1,2001:db8::1"

    def test_valid_ipv6_cidr(self):
        """Valid IPv6 CIDR range should be accepted."""
        settings = Settings(trusted_proxy_ips="2001:db8::/32")
        assert settings.trusted_proxy_ips == "2001:db8::/32"

    def test_valid_with_whitespace(self):
        """Configuration with whitespace should be accepted and preserved."""
        settings = Settings(trusted_proxy_ips="127.0.0.1, 192.168.1.1 ,10.0.0.0/8")
        # Whitespace is preserved in config (stripped during is_trusted_proxy check)
        assert "127.0.0.1" in settings.trusted_proxy_ips
        assert "192.168.1.1" in settings.trusted_proxy_ips

    def test_default_trusted_proxy_configuration(self):
        """Default configuration should include localhost and private networks (IPv4 + IPv6)."""
        settings = Settings()
        # Default: "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7,fe80::/10"
        # IPv4 localhost and private networks
        assert "127.0.0.1" in settings.trusted_proxy_ips
        assert "10.0.0.0/8" in settings.trusted_proxy_ips
        assert "172.16.0.0/12" in settings.trusted_proxy_ips
        assert "192.168.0.0/16" in settings.trusted_proxy_ips
        # IPv6 localhost and private networks
        assert "::1" in settings.trusted_proxy_ips
        assert "fc00::/7" in settings.trusted_proxy_ips  # IPv6 ULA
        assert "fe80::/10" in settings.trusted_proxy_ips  # IPv6 link-local


class TestTrustedProxyIPValidationErrors:
    """Test that invalid trusted proxy configurations are rejected at startup."""

    def test_invalid_ip_address_rejected(self):
        """Invalid IP address should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips="999.999.999.999")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS contains invalid" in error_message
        assert "999.999.999.999" in error_message

    def test_invalid_cidr_range_rejected(self):
        """Invalid CIDR range should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips="10.0.0.0/999")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS contains invalid" in error_message

    def test_malformed_ip_rejected(self):
        """Malformed IP address should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips="192.168.1")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS contains invalid" in error_message

    def test_empty_configuration_rejected(self):
        """Empty trusted proxy configuration should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips="")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS cannot be empty" in error_message

    def test_whitespace_only_rejected(self):
        """Whitespace-only configuration should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips="   ")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS cannot be empty" in error_message

    def test_comma_only_rejected(self):
        """Comma-only configuration should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips=",,,")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS contains no valid entries" in error_message

    def test_mixed_valid_and_invalid_rejected(self):
        """Mixed valid and invalid IPs should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips="127.0.0.1,999.999.999.999,192.168.1.1")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS contains invalid" in error_message
        assert "999.999.999.999" in error_message

    def test_sql_injection_attempt_rejected(self):
        """SQL injection attempt in configuration should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(trusted_proxy_ips="192.168.1.1; DROP TABLE users;")

        error_message = str(exc_info.value)
        assert "TRUSTED_PROXY_IPS contains invalid" in error_message


# ============================================================================
# Test Group 2: is_trusted_proxy() Method (Runtime Checks)
# ============================================================================


class TestIsTrustedProxyMethod:
    """Test is_trusted_proxy() method for IP trust verification."""

    def test_exact_ip_match_trusted(self):
        """Exact IP match should be trusted."""
        settings = Settings(trusted_proxy_ips="127.0.0.1,192.168.1.100")
        assert settings.is_trusted_proxy("127.0.0.1") is True
        assert settings.is_trusted_proxy("192.168.1.100") is True

    def test_ip_not_in_list_untrusted(self):
        """IP not in trusted list should be untrusted."""
        settings = Settings(trusted_proxy_ips="127.0.0.1")
        assert settings.is_trusted_proxy("8.8.8.8") is False
        assert settings.is_trusted_proxy("192.168.1.1") is False

    def test_cidr_range_match_trusted(self):
        """IP within CIDR range should be trusted."""
        settings = Settings(trusted_proxy_ips="10.0.0.0/8")

        # All 10.x.x.x addresses should be trusted
        assert settings.is_trusted_proxy("10.0.0.1") is True
        assert settings.is_trusted_proxy("10.5.10.20") is True
        assert settings.is_trusted_proxy("10.255.255.254") is True

        # Outside range should be untrusted
        assert settings.is_trusted_proxy("11.0.0.1") is False
        assert settings.is_trusted_proxy("9.255.255.255") is False

    def test_multiple_cidr_ranges(self):
        """IP matching any CIDR range should be trusted."""
        settings = Settings(
            trusted_proxy_ips="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
        )

        # Test each range
        assert settings.is_trusted_proxy("10.1.2.3") is True  # 10.0.0.0/8
        assert settings.is_trusted_proxy("172.16.5.10") is True  # 172.16.0.0/12
        assert settings.is_trusted_proxy("192.168.100.1") is True  # 192.168.0.0/16

        # Outside all ranges
        assert settings.is_trusted_proxy("8.8.8.8") is False

    def test_ipv6_exact_match(self):
        """IPv6 exact match should be trusted."""
        settings = Settings(trusted_proxy_ips="::1,2001:db8::1")

        assert settings.is_trusted_proxy("::1") is True
        assert settings.is_trusted_proxy("2001:db8::1") is True
        assert settings.is_trusted_proxy("2001:db8::2") is False

    def test_ipv6_cidr_range(self):
        """IPv6 within CIDR range should be trusted."""
        settings = Settings(trusted_proxy_ips="2001:db8::/32")

        # Within range
        assert settings.is_trusted_proxy("2001:db8::1") is True
        assert settings.is_trusted_proxy("2001:db8:1::1") is True

        # Outside range
        assert settings.is_trusted_proxy("2001:db9::1") is False

    def test_localhost_variations(self):
        """Various localhost representations should be handled correctly."""
        settings = Settings(trusted_proxy_ips="127.0.0.1,::1")

        # IPv4 localhost
        assert settings.is_trusted_proxy("127.0.0.1") is True

        # IPv6 localhost
        assert settings.is_trusted_proxy("::1") is True

    def test_invalid_ip_format_returns_false(self):
        """Invalid IP format should return False (defensive programming)."""
        settings = Settings(trusted_proxy_ips="127.0.0.1")

        # Invalid formats should return False (not raise exception)
        assert settings.is_trusted_proxy("not-an-ip") is False
        assert settings.is_trusted_proxy("999.999.999.999") is False
        assert settings.is_trusted_proxy("192.168.1") is False
        assert settings.is_trusted_proxy("") is False
        assert settings.is_trusted_proxy("192.168.1.1; DROP TABLE") is False

    def test_case_sensitivity(self):
        """IP addresses should be case-insensitive (IPv6 hex)."""
        settings = Settings(trusted_proxy_ips="2001:DB8::1")

        # Both uppercase and lowercase should work
        assert settings.is_trusted_proxy("2001:db8::1") is True
        assert settings.is_trusted_proxy("2001:DB8::1") is True

    def test_default_configuration_localhost_trusted(self):
        """Default configuration should trust localhost (IPv4 and IPv6)."""
        settings = Settings()

        # IPv4 localhost should be trusted by default
        assert settings.is_trusted_proxy("127.0.0.1") is True

        # IPv6 localhost should be trusted by default
        assert settings.is_trusted_proxy("::1") is True

    def test_default_configuration_private_networks_trusted(self):
        """Default configuration should trust private networks (IPv4 and IPv6)."""
        settings = Settings()

        # IPv4 private networks should be trusted by default
        assert settings.is_trusted_proxy("10.0.0.1") is True
        assert settings.is_trusted_proxy("172.16.0.1") is True
        assert settings.is_trusted_proxy("192.168.1.1") is True

        # IPv6 private networks should be trusted by default
        assert settings.is_trusted_proxy("fc00::1") is True  # IPv6 ULA
        assert settings.is_trusted_proxy("fd00::1") is True  # IPv6 ULA (fd00::/8 subset)
        assert settings.is_trusted_proxy("fe80::1") is True  # IPv6 link-local

    def test_default_configuration_public_ip_untrusted(self):
        """Default configuration should not trust public IPs."""
        settings = Settings()

        # Public IPs should be untrusted by default
        assert settings.is_trusted_proxy("8.8.8.8") is False
        assert settings.is_trusted_proxy("203.0.113.1") is False
        assert settings.is_trusted_proxy("1.1.1.1") is False


# ============================================================================
# Test Group 3: Edge Cases and Security Scenarios
# ============================================================================


class TestTrustedProxyEdgeCases:
    """Test edge cases and security scenarios."""

    def test_single_ip_cidr_32_notation(self):
        """Single IP in CIDR /32 notation should work."""
        settings = Settings(trusted_proxy_ips="192.168.1.100/32")

        # Only exact IP should match
        assert settings.is_trusted_proxy("192.168.1.100") is True
        assert settings.is_trusted_proxy("192.168.1.101") is False

    def test_full_range_cidr_0(self):
        """CIDR /0 (all IPs) should work but is dangerous in production."""
        settings = Settings(trusted_proxy_ips="0.0.0.0/0")

        # All IPv4 addresses should match
        assert settings.is_trusted_proxy("1.2.3.4") is True
        assert settings.is_trusted_proxy("192.168.1.1") is True
        assert settings.is_trusted_proxy("8.8.8.8") is True

    def test_overlapping_ranges(self):
        """Overlapping CIDR ranges should work correctly."""
        settings = Settings(trusted_proxy_ips="10.0.0.0/8,10.0.0.0/16")

        # Should be trusted (matches both ranges)
        assert settings.is_trusted_proxy("10.0.0.1") is True
        assert settings.is_trusted_proxy("10.0.255.255") is True

        # Should be trusted (matches first range only)
        assert settings.is_trusted_proxy("10.1.0.1") is True

    def test_zero_ip_address(self):
        """Zero IP address (0.0.0.0) should be handled."""
        settings = Settings(trusted_proxy_ips="0.0.0.0")
        assert settings.is_trusted_proxy("0.0.0.0") is True
        assert settings.is_trusted_proxy("127.0.0.1") is False

    def test_broadcast_ip_address(self):
        """Broadcast IP address (255.255.255.255) should be handled."""
        settings = Settings(trusted_proxy_ips="255.255.255.255")
        assert settings.is_trusted_proxy("255.255.255.255") is True
        assert settings.is_trusted_proxy("192.168.1.1") is False

    def test_unicode_ip_rejected(self):
        """Unicode characters in IP should return False."""
        settings = Settings(trusted_proxy_ips="127.0.0.1")
        assert settings.is_trusted_proxy("127.0.0.١") is False  # Arabic numeral

    def test_trailing_whitespace_in_check(self):
        """Trailing whitespace in IP check should be handled."""
        settings = Settings(trusted_proxy_ips="127.0.0.1")

        # is_trusted_proxy doesn't strip whitespace - caller should
        # This documents current behavior
        assert settings.is_trusted_proxy("127.0.0.1 ") is False


# ============================================================================
# Test Group 4: Performance and Caching
# ============================================================================


class TestTrustedProxyPerformance:
    """Test performance characteristics of trusted proxy checking."""

    def test_repeated_checks_same_ip(self):
        """Repeated checks of same IP should be consistent."""
        settings = Settings(trusted_proxy_ips="10.0.0.0/8")

        # Multiple checks should return same result
        for _ in range(100):
            assert settings.is_trusted_proxy("10.0.0.1") is True
            assert settings.is_trusted_proxy("8.8.8.8") is False

    def test_large_trusted_proxy_list(self):
        """Large trusted proxy list should work correctly."""
        # Create list of 50 CIDR ranges
        ranges = [f"10.{i}.0.0/16" for i in range(50)]
        settings = Settings(trusted_proxy_ips=",".join(ranges))

        # Should find match in first range
        assert settings.is_trusted_proxy("10.0.0.1") is True

        # Should find match in last range
        assert settings.is_trusted_proxy("10.49.0.1") is True

        # Should not match outside ranges
        assert settings.is_trusted_proxy("10.50.0.1") is False


# ============================================================================
# Test Group 5: Integration with Other Config Settings
# ============================================================================


class TestTrustedProxyConfigIntegration:
    """Test trusted proxy configuration integrates with other settings."""

    def test_trusted_proxy_with_production_environment(self):
        """Trusted proxy should work in production environment."""
        # Production should use specific proxy IPs, not broad ranges
        settings = Settings(
            environment="production",
            trusted_proxy_ips="203.0.113.10,203.0.113.11",  # Load balancer IPs
        )

        # Only specific IPs should be trusted
        assert settings.is_trusted_proxy("203.0.113.10") is True
        assert settings.is_trusted_proxy("203.0.113.11") is True
        assert settings.is_trusted_proxy("203.0.113.12") is False

    def test_trusted_proxy_with_development_environment(self):
        """Trusted proxy should work in development environment."""
        settings = Settings(
            environment="local",
            trusted_proxy_ips="127.0.0.1,10.0.0.0/8",  # Localhost + Docker
        )

        assert settings.is_trusted_proxy("127.0.0.1") is True
        assert settings.is_trusted_proxy("10.0.0.1") is True
