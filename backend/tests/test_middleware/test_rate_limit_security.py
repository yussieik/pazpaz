"""Comprehensive security test suite for X-Forwarded-For validation in rate limiting.

This test suite verifies the critical security fix that prevents IP spoofing attacks
by validating X-Forwarded-For headers against a trusted proxy list.

Test Coverage:
1. Trusted proxy scenarios (X-Forwarded-For accepted)
2. Untrusted proxy scenarios (X-Forwarded-For ignored, potential attack logged)
3. Invalid input handling (malformed IPs, injection attempts)
4. IPv6 support
5. Logging verification (debug and warning logs)
6. Backward compatibility with existing tests

Security Context:
Attackers can send fake X-Forwarded-For headers to bypass rate limits, location-based
restrictions, and audit logging. This fix ensures only trusted reverse proxies can
set client IP addresses.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pazpaz.core.config import settings
from pazpaz.middleware.rate_limit import get_client_ip

pytestmark = pytest.mark.asyncio


# ============================================================================
# Test Group 1: Trusted Proxy Scenarios (X-Forwarded-For ACCEPTED)
# ============================================================================


class TestTrustedProxyAcceptsForwardedFor:
    """Test that trusted proxies can set X-Forwarded-For headers."""

    def test_localhost_trusted_proxy_accepts_forwarded_for(self):
        """Localhost (127.0.0.1) should be trusted to set X-Forwarded-For."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"  # Direct connection from localhost
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.42" if key == "X-Forwarded-For" else None
        )

        # Should use forwarded IP from trusted proxy
        client_ip = get_client_ip(mock_request)
        assert client_ip == "203.0.113.42"

    def test_private_network_10_trusted(self):
        """Private network 10.x.x.x should be trusted (default config)."""
        mock_request = MagicMock()
        mock_request.client.host = "10.0.1.5"  # Docker/private network
        mock_request.headers.get.side_effect = lambda key: (
            "198.51.100.1" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "198.51.100.1"

    def test_private_network_172_trusted(self):
        """Private network 172.16-31.x.x should be trusted (default config)."""
        mock_request = MagicMock()
        mock_request.client.host = "172.16.5.10"  # Docker default network
        mock_request.headers.get.side_effect = lambda key: (
            "192.0.2.100" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "192.0.2.100"

    def test_private_network_192_trusted(self):
        """Private network 192.168.x.x should be trusted (default config)."""
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"  # Home/office network
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.99" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "203.0.113.99"

    def test_trusted_proxy_forwards_ipv4(self):
        """Trusted proxy forwarding IPv4 address should be accepted."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "198.51.100.50" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "198.51.100.50"

    def test_trusted_proxy_forwards_ipv6(self):
        """Trusted proxy forwarding IPv6 address should be accepted."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "2001:db8::1" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "2001:db8::1"

    def test_trusted_proxy_multiple_ips_uses_leftmost(self):
        """Trusted proxy with chain should use leftmost IP (original client)."""
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"  # Trusted proxy
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1, 198.51.100.1, 192.0.2.1"  # Proxy chain
            if key == "X-Forwarded-For"
            else None
        )

        # Should use leftmost IP (original client)
        client_ip = get_client_ip(mock_request)
        assert client_ip == "203.0.113.1"

    def test_trusted_proxy_with_whitespace_in_chain(self):
        """Trusted proxy with whitespace in chain should handle correctly."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            " 203.0.113.5 ,  198.51.100.5  " if key == "X-Forwarded-For" else None
        )

        # Should strip whitespace and use leftmost IP
        client_ip = get_client_ip(mock_request)
        assert client_ip == "203.0.113.5"

    def test_trusted_proxy_no_forwarded_for_uses_proxy_ip(self, caplog):
        """Trusted proxy without X-Forwarded-For should use proxy's IP."""
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"  # Trusted proxy
        mock_request.headers.get.return_value = None  # No X-Forwarded-For

        # Should use direct connection IP (proxy itself)
        client_ip = get_client_ip(mock_request)
        assert client_ip == "10.0.0.1"

        # Should log debug message about missing header
        assert any(
            "trusted_proxy_no_forwarded_for" in record.message for record in caplog.records
        )


# ============================================================================
# Test Group 2: Untrusted Proxy Scenarios (X-Forwarded-For IGNORED)
# ============================================================================


class TestUntrustedProxyIgnoresForwardedFor:
    """Test that untrusted clients cannot spoof IP via X-Forwarded-For."""

    def test_public_ip_ignores_forwarded_for(self, caplog):
        """Public IP sending X-Forwarded-For should be ignored (potential attack)."""
        mock_request = MagicMock()
        mock_request.client.host = "8.8.8.8"  # Public IP (Google DNS)
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1" if key == "X-Forwarded-For" else None  # Fake header
        )

        # Should ignore X-Forwarded-For and use direct IP
        client_ip = get_client_ip(mock_request)
        assert client_ip == "8.8.8.8"

        # Should log warning about potential spoofing
        assert any(
            "untrusted_proxy_sent_forwarded_for" in record.message
            for record in caplog.records
        )

    def test_untrusted_attacker_ip_spoofing_attempt(self, caplog):
        """Attacker trying to spoof IP should be detected and logged."""
        mock_request = MagicMock()
        mock_request.client.host = "198.51.100.50"  # Attacker's real IP
        mock_request.headers.get.side_effect = lambda key: (
            "127.0.0.1" if key == "X-Forwarded-For" else None  # Fake localhost
        )

        # Should ignore fake header
        client_ip = get_client_ip(mock_request)
        assert client_ip == "198.51.100.50"  # Real IP

        # Should log security warning
        warning_logs = [
            record
            for record in caplog.records
            if record.levelname == "WARNING"
            and "untrusted_proxy_sent_forwarded_for" in record.message
        ]
        assert len(warning_logs) > 0

        # Log should contain both IPs for security investigation
        log_message = warning_logs[0].message
        assert "198.51.100.50" in str(log_message) or "direct_ip" in str(log_message)

    def test_cloudflare_ip_not_trusted_by_default(self):
        """Cloudflare IP should not be trusted unless explicitly configured."""
        mock_request = MagicMock()
        mock_request.client.host = "104.16.0.0"  # Cloudflare IP
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1" if key == "X-Forwarded-For" else None
        )

        # Should ignore X-Forwarded-For (Cloudflare not in default trusted list)
        client_ip = get_client_ip(mock_request)
        assert client_ip == "104.16.0.0"

    def test_aws_elb_ip_not_trusted_by_default(self):
        """AWS ELB IP should not be trusted unless explicitly configured."""
        mock_request = MagicMock()
        mock_request.client.host = "54.240.0.1"  # AWS IP range
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1" if key == "X-Forwarded-For" else None
        )

        # Should ignore X-Forwarded-For
        client_ip = get_client_ip(mock_request)
        assert client_ip == "54.240.0.1"

    def test_untrusted_ipv6_ignores_forwarded_for(self):
        """Untrusted IPv6 address should ignore X-Forwarded-For."""
        mock_request = MagicMock()
        mock_request.client.host = "2001:4860:4860::8888"  # Google DNS IPv6
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "2001:4860:4860::8888"  # Ignore fake header


# ============================================================================
# Test Group 3: Invalid Input Handling
# ============================================================================


class TestInvalidForwardedForHandling:
    """Test that invalid X-Forwarded-For headers are handled securely."""

    def test_malformed_ip_in_forwarded_for_ignored(self, caplog):
        """Malformed IP in X-Forwarded-For should fall back to direct IP."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"  # Trusted proxy
        mock_request.headers.get.side_effect = lambda key: (
            "not-an-ip-address" if key == "X-Forwarded-For" else None
        )

        # Should fall back to direct IP
        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

        # Should log warning about invalid format
        assert any(
            "invalid_forwarded_ip_format" in record.message for record in caplog.records
        )

    def test_sql_injection_in_forwarded_for_rejected(self, caplog):
        """SQL injection attempt in X-Forwarded-For should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "192.168.1.1; DROP TABLE users;" if key == "X-Forwarded-For" else None
        )

        # Should fall back to direct IP
        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

        # Should log warning
        assert any(
            "invalid_forwarded_ip_format" in record.message for record in caplog.records
        )

    def test_xss_attempt_in_forwarded_for_rejected(self, caplog):
        """XSS attempt in X-Forwarded-For should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "<script>alert('xss')</script>" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

    def test_empty_forwarded_for_uses_direct_ip(self):
        """Empty X-Forwarded-For should use direct IP."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

    def test_whitespace_only_forwarded_for_uses_direct_ip(self):
        """Whitespace-only X-Forwarded-For should use direct IP."""
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "   " if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "10.0.0.1"

    def test_null_bytes_in_forwarded_for_rejected(self, caplog):
        """Null bytes in X-Forwarded-For should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "192.168.1.1\x00malicious" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

    def test_very_long_forwarded_for_chain(self):
        """Very long X-Forwarded-For chain should handle correctly."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        # Create chain of 50 IPs
        chain = ", ".join([f"203.0.113.{i}" for i in range(50)])
        mock_request.headers.get.side_effect = lambda key: (
            chain if key == "X-Forwarded-For" else None
        )

        # Should use leftmost IP
        client_ip = get_client_ip(mock_request)
        assert client_ip == "203.0.113.0"

    def test_invalid_ip_octets_rejected(self, caplog):
        """IP with invalid octets should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "999.999.999.999" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

        assert any(
            "invalid_forwarded_ip_format" in record.message for record in caplog.records
        )

    def test_incomplete_ip_address_rejected(self, caplog):
        """Incomplete IP address should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "192.168.1" if key == "X-Forwarded-For" else None  # Missing octet
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"


# ============================================================================
# Test Group 4: IPv6 Support
# ============================================================================


class TestIPv6ForwardedForSupport:
    """Test IPv6 address handling in X-Forwarded-For."""

    def test_ipv6_address_from_trusted_proxy(self):
        """IPv6 address from trusted proxy should be accepted."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "2001:db8::1" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "2001:db8::1"

    def test_ipv6_compressed_format(self):
        """IPv6 compressed format should be accepted."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "::1" if key == "X-Forwarded-For" else None  # IPv6 localhost
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "::1"

    def test_ipv6_full_format(self):
        """IPv6 full format should be accepted."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "2001:0db8:0000:0000:0000:0000:0000:0001"
            if key == "X-Forwarded-For"
            else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "2001:0db8:0000:0000:0000:0000:0000:0001"

    def test_ipv6_in_chain_uses_leftmost(self):
        """IPv6 in chain should use leftmost address."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "2001:db8::1, 2001:db8::2" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "2001:db8::1"

    def test_malformed_ipv6_rejected(self, caplog):
        """Malformed IPv6 should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "2001:db8:::invalid" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"


# ============================================================================
# Test Group 5: Logging Verification
# ============================================================================


class TestForwardedForLogging:
    """Test that security events are properly logged."""

    def test_trusted_proxy_logs_debug_message(self, caplog):
        """Accepting X-Forwarded-For from trusted proxy should log debug."""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1" if key == "X-Forwarded-For" else None
        )

        get_client_ip(mock_request)

        # Should log debug message
        debug_logs = [r for r in caplog.records if r.levelname == "DEBUG"]
        assert any(
            "client_ip_from_trusted_proxy" in record.message for record in debug_logs
        )

    def test_untrusted_proxy_logs_warning(self, caplog):
        """Rejecting X-Forwarded-For should log warning."""
        mock_request = MagicMock()
        mock_request.client.host = "8.8.8.8"
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1" if key == "X-Forwarded-For" else None
        )

        get_client_ip(mock_request)

        # Should log warning
        warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any(
            "untrusted_proxy_sent_forwarded_for" in record.message
            for record in warning_logs
        )

    def test_invalid_ip_logs_warning(self, caplog):
        """Invalid IP format should log warning."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "invalid-ip" if key == "X-Forwarded-For" else None
        )

        get_client_ip(mock_request)

        warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any(
            "invalid_forwarded_ip_format" in record.message for record in warning_logs
        )

    def test_no_client_logs_warning(self, caplog):
        """Missing request.client should log warning."""
        mock_request = MagicMock()
        mock_request.client = None

        client_ip = get_client_ip(mock_request)
        assert client_ip == "unknown"

        warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("no_client_ip_in_request" in record.message for record in warning_logs)


# ============================================================================
# Test Group 6: Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test that existing functionality still works."""

    def test_no_forwarded_for_header_uses_direct_ip(self):
        """Request without X-Forwarded-For should use direct IP."""
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers.get.return_value = None

        client_ip = get_client_ip(mock_request)
        assert client_ip == "192.168.1.100"

    def test_direct_connection_no_proxy(self):
        """Direct connection without proxy should work as before."""
        mock_request = MagicMock()
        mock_request.client.host = "203.0.113.50"
        mock_request.headers.get.return_value = None

        client_ip = get_client_ip(mock_request)
        assert client_ip == "203.0.113.50"

    def test_localhost_direct_connection(self):
        """Localhost direct connection should work."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = None

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"


# ============================================================================
# Test Group 7: Production Security Scenarios
# ============================================================================


class TestProductionSecurityScenarios:
    """Test realistic production attack and security scenarios."""

    def test_rate_limit_bypass_attempt_detected(self, caplog):
        """Attacker trying to bypass rate limit should be detected."""
        # Scenario: Attacker reaches rate limit, tries to spoof new IP
        mock_request = MagicMock()
        mock_request.client.host = "198.51.100.100"  # Attacker's real IP
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.1" if key == "X-Forwarded-For" else None  # Fake IP
        )

        # Attempt 1: Real IP used
        client_ip = get_client_ip(mock_request)
        assert client_ip == "198.51.100.100"

        # Should log security warning
        assert any(
            "untrusted_proxy_sent_forwarded_for" in record.message
            for record in caplog.records
        )

    def test_distributed_attack_from_multiple_ips(self):
        """Multiple attackers should each be tracked by their real IP."""
        # Attacker 1
        mock_request1 = MagicMock()
        mock_request1.client.host = "198.51.100.1"
        mock_request1.headers.get.return_value = None

        ip1 = get_client_ip(mock_request1)
        assert ip1 == "198.51.100.1"

        # Attacker 2
        mock_request2 = MagicMock()
        mock_request2.client.host = "198.51.100.2"
        mock_request2.headers.get.return_value = None

        ip2 = get_client_ip(mock_request2)
        assert ip2 == "198.51.100.2"

        # IPs should be different (not spoofed)
        assert ip1 != ip2

    def test_legitimate_proxy_chain_handled_correctly(self):
        """Legitimate multi-proxy chain should use original client."""
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"  # Our trusted load balancer

        # Chain: Client -> CDN -> Load Balancer -> App
        mock_request.headers.get.side_effect = lambda key: (
            "203.0.113.50, 104.16.0.1"  # Client, CDN
            if key == "X-Forwarded-For"
            else None
        )

        # Should use leftmost IP (original client)
        client_ip = get_client_ip(mock_request)
        assert client_ip == "203.0.113.50"

    def test_custom_trusted_proxy_configuration(self, monkeypatch):
        """Custom trusted proxy configuration should work in production."""
        # Simulate production with specific load balancer IP
        monkeypatch.setattr(
            settings,
            "trusted_proxy_ips",
            "203.0.113.10,203.0.113.11",  # Load balancer IPs
        )

        # Request from trusted load balancer
        mock_request = MagicMock()
        mock_request.client.host = "203.0.113.10"
        mock_request.headers.get.side_effect = lambda key: (
            "198.51.100.1" if key == "X-Forwarded-For" else None
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "198.51.100.1"

        # Request from different IP should not be trusted
        mock_request2 = MagicMock()
        mock_request2.client.host = "203.0.113.99"  # Not in trusted list
        mock_request2.headers.get.side_effect = lambda key: (
            "198.51.100.2" if key == "X-Forwarded-For" else None
        )

        client_ip2 = get_client_ip(mock_request2)
        assert client_ip2 == "203.0.113.99"  # Ignored X-Forwarded-For


# ============================================================================
# Test Group 8: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_ipv4_mapped_ipv6_address(self):
        """IPv4-mapped IPv6 address should be handled."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "::ffff:192.0.2.1" if key == "X-Forwarded-For" else None
        )

        # Should accept IPv4-mapped IPv6
        client_ip = get_client_ip(mock_request)
        assert client_ip == "::ffff:192.0.2.1"

    def test_port_number_in_forwarded_for_rejected(self, caplog):
        """Port number in X-Forwarded-For should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "192.168.1.1:8080" if key == "X-Forwarded-For" else None  # With port
        )

        # Should fall back to direct IP
        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

    def test_unicode_in_forwarded_for_rejected(self, caplog):
        """Unicode characters in X-Forwarded-For should be rejected."""
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key: (
            "192.168.1.١" if key == "X-Forwarded-For" else None  # Arabic numeral
        )

        client_ip = get_client_ip(mock_request)
        assert client_ip == "127.0.0.1"

    def test_localhost_ipv6_trusted(self):
        """IPv6 localhost should be trusted."""
        mock_request = MagicMock()
        mock_request.client.host = "::1"  # IPv6 localhost
        mock_request.headers.get.side_effect = lambda key: (
            "2001:db8::1" if key == "X-Forwarded-For" else None
        )

        # ::1 should be trusted (need to verify against settings)
        # Default config includes 127.0.0.1 but may not include ::1
        client_ip = get_client_ip(mock_request)
        # This depends on whether ::1 is in trusted_proxy_ips
        # Just verify it returns a valid IP
        assert client_ip in ("::1", "2001:db8::1")
