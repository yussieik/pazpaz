#!/usr/bin/env python3
"""
Validate GitHub Secrets configuration for PazPaz deployment.

This script validates that secrets meet security requirements for production deployment.
It can be run locally or in CI/CD pipelines to ensure proper secret configuration.

Usage:
    # Validate secrets from environment variables
    export ENCRYPTION_MASTER_KEY="your-fernet-key-here"
    export SECRET_KEY="your-secret-key-here"
    export JWT_SECRET_KEY="your-jwt-secret-here"
    python validate-secrets.py

    # Run with verbose output
    python validate-secrets.py --verbose

    # Validate specific environment
    python validate-secrets.py --env production

    # Check from file (for testing only, never commit!)
    python validate-secrets.py --from-file .env.test

Exit codes:
    0 - All validations passed
    1 - Critical validation failures
    2 - Non-critical warnings

Security Note:
    This script validates secret FORMAT and STRENGTH only.
    It does NOT store, log, or transmit actual secret values.
"""

import argparse
import base64
import os
import re
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SecretType(Enum):
    """Types of secrets with their validation rules."""
    ENCRYPTION_KEY = "encryption_key"
    APPLICATION_SECRET = "application_secret"
    JWT_SECRET = "jwt_secret"
    DATABASE_PASSWORD = "database_password"
    REDIS_PASSWORD = "redis_password"
    API_KEY = "api_key"
    SSH_KEY = "ssh_key"


@dataclass
class ValidationResult:
    """Result of a secret validation."""
    name: str
    valid: bool
    message: str
    severity: str  # 'critical', 'warning', 'info'


class Colors:
    """Terminal color codes for output formatting."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def disable():
        """Disable colors (for non-TTY output)."""
        Colors.RED = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.BLUE = ''
        Colors.MAGENTA = ''
        Colors.CYAN = ''
        Colors.WHITE = ''
        Colors.RESET = ''
        Colors.BOLD = ''


def print_colored(message: str, color: str = Colors.RESET, bold: bool = False) -> None:
    """Print a colored message to stdout."""
    if bold:
        print(f"{Colors.BOLD}{color}{message}{Colors.RESET}")
    else:
        print(f"{color}{message}{Colors.RESET}")


def validate_encryption_key(key: Optional[str]) -> ValidationResult:
    """
    Validate ENCRYPTION_MASTER_KEY format for Fernet encryption.

    Requirements:
    - Must be base64-encoded
    - Must decode to exactly 32 bytes
    - Must be URL-safe base64
    """
    if not key:
        return ValidationResult(
            name="ENCRYPTION_MASTER_KEY",
            valid=False,
            message="Not set (CRITICAL: Required for PHI encryption)",
            severity="critical"
        )

    try:
        # Check if it's valid base64
        decoded = base64.urlsafe_b64decode(key)

        # Check length (Fernet requires exactly 32 bytes)
        if len(decoded) != 32:
            return ValidationResult(
                name="ENCRYPTION_MASTER_KEY",
                valid=False,
                message=f"Invalid length: {len(decoded)} bytes (must be exactly 32)",
                severity="critical"
            )

        # Additional check: ensure it's not a known test key
        test_keys = [
            'dGVzdF9rZXlfZm9yX2NpX2V4YWN0bHlfMzJfYnl0ZXM=',  # CI fallback
            'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',   # All zeros
        ]
        if key in test_keys:
            return ValidationResult(
                name="ENCRYPTION_MASTER_KEY",
                valid=False,
                message="Using a test/default key (NEVER use in production!)",
                severity="critical"
            )

        return ValidationResult(
            name="ENCRYPTION_MASTER_KEY",
            valid=True,
            message="Valid Fernet key (32 bytes)",
            severity="info"
        )

    except Exception as e:
        return ValidationResult(
            name="ENCRYPTION_MASTER_KEY",
            valid=False,
            message=f"Invalid format: {str(e)}",
            severity="critical"
        )


def validate_secret_key(key: Optional[str], name: str = "SECRET_KEY", min_length: int = 50) -> ValidationResult:
    """
    Validate application secret keys (SECRET_KEY, CSRF_SECRET_KEY).

    Requirements:
    - Minimum length (default 50 characters)
    - Contains mixed character types
    - Not a common/weak pattern
    """
    if not key:
        return ValidationResult(
            name=name,
            valid=False,
            message=f"Not set (Required for {'session management' if 'SECRET' in name else name})",
            severity="critical"
        )

    # Check minimum length
    if len(key) < min_length:
        return ValidationResult(
            name=name,
            valid=False,
            message=f"Too short: {len(key)} chars (minimum {min_length})",
            severity="critical"
        )

    # Check for common weak patterns
    weak_patterns = [
        r'^test',
        r'^secret',
        r'^password',
        r'^12345',
        r'^admin',
        r'^default',
        r'^\w+_only$',
        r'^[a-z]+$',  # All lowercase
        r'^[A-Z]+$',  # All uppercase
        r'^[0-9]+$',  # All numbers
    ]

    for pattern in weak_patterns:
        if re.match(pattern, key.lower()):
            return ValidationResult(
                name=name,
                valid=False,
                message=f"Weak pattern detected (matches {pattern})",
                severity="critical"
            )

    # Check character diversity
    has_lower = any(c.islower() for c in key)
    has_upper = any(c.isupper() for c in key)
    has_digit = any(c.isdigit() for c in key)
    has_special = any(not c.isalnum() for c in key)

    diversity_score = sum([has_lower, has_upper, has_digit, has_special])

    if diversity_score < 3:
        return ValidationResult(
            name=name,
            valid=False,
            message=f"Insufficient character diversity (score: {diversity_score}/4)",
            severity="warning"
        )

    return ValidationResult(
        name=name,
        valid=True,
        message=f"Strong key ({len(key)} chars, diversity: {diversity_score}/4)",
        severity="info"
    )


def validate_jwt_secret(key: Optional[str]) -> ValidationResult:
    """
    Validate JWT_SECRET_KEY.

    Requirements:
    - Minimum 256 bits (32 bytes) for HS256
    - Recommended 50+ characters
    """
    return validate_secret_key(key, "JWT_SECRET_KEY", min_length=50)


def validate_database_password(password: Optional[str]) -> ValidationResult:
    """
    Validate PostgreSQL password.

    Requirements:
    - Minimum 32 characters
    - No spaces or special shell characters
    - Alphanumeric + underscore only (for compatibility)
    """
    if not password:
        return ValidationResult(
            name="DATABASE_PASSWORD",
            valid=False,
            message="Not set (Required for database access)",
            severity="critical"
        )

    if len(password) < 32:
        return ValidationResult(
            name="DATABASE_PASSWORD",
            valid=False,
            message=f"Too short: {len(password)} chars (minimum 32)",
            severity="critical"
        )

    # Check for problematic characters
    if not re.match(r'^[a-zA-Z0-9_]+$', password):
        return ValidationResult(
            name="DATABASE_PASSWORD",
            valid=False,
            message="Contains special characters (use alphanumeric + underscore only)",
            severity="warning"
        )

    return ValidationResult(
        name="DATABASE_PASSWORD",
        valid=True,
        message=f"Valid database password ({len(password)} chars)",
        severity="info"
    )


def validate_redis_password(password: Optional[str]) -> ValidationResult:
    """
    Validate Redis password.

    Requirements:
    - Minimum 32 characters
    - Alphanumeric only (Redis compatibility)
    """
    if not password:
        return ValidationResult(
            name="REDIS_PASSWORD",
            valid=False,
            message="Not set (Required for Redis authentication)",
            severity="critical"
        )

    if len(password) < 32:
        return ValidationResult(
            name="REDIS_PASSWORD",
            valid=False,
            message=f"Too short: {len(password)} chars (minimum 32)",
            severity="critical"
        )

    if not password.isalnum():
        return ValidationResult(
            name="REDIS_PASSWORD",
            valid=False,
            message="Contains non-alphanumeric characters (use alphanumeric only)",
            severity="warning"
        )

    return ValidationResult(
        name="REDIS_PASSWORD",
        valid=True,
        message=f"Valid Redis password ({len(password)} chars)",
        severity="info"
    )


def validate_ssh_key(key: Optional[str]) -> ValidationResult:
    """
    Validate SSH private key format.

    Requirements:
    - Must be in valid OpenSSH or PEM format
    - Must have proper header/footer
    """
    if not key:
        return ValidationResult(
            name="SSH_PRIVATE_KEY",
            valid=False,
            message="Not set (Required for deployment)",
            severity="critical"
        )

    # Check for SSH key headers
    valid_headers = [
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN ENCRYPTED PRIVATE KEY-----",
    ]

    valid_footers = [
        "-----END OPENSSH PRIVATE KEY-----",
        "-----END RSA PRIVATE KEY-----",
        "-----END EC PRIVATE KEY-----",
        "-----END PRIVATE KEY-----",
        "-----END ENCRYPTED PRIVATE KEY-----",
    ]

    has_valid_header = any(header in key for header in valid_headers)
    has_valid_footer = any(footer in key for footer in valid_footers)

    if not has_valid_header:
        return ValidationResult(
            name="SSH_PRIVATE_KEY",
            valid=False,
            message="Invalid format: Missing valid SSH key header",
            severity="critical"
        )

    if not has_valid_footer:
        return ValidationResult(
            name="SSH_PRIVATE_KEY",
            valid=False,
            message="Invalid format: Missing valid SSH key footer",
            severity="critical"
        )

    # Check key type
    if "BEGIN OPENSSH" in key:
        key_type = "OpenSSH"
    elif "BEGIN RSA" in key:
        key_type = "RSA"
    elif "BEGIN EC" in key:
        key_type = "EC/ECDSA"
    else:
        key_type = "Generic"

    return ValidationResult(
        name="SSH_PRIVATE_KEY",
        valid=True,
        message=f"Valid {key_type} private key",
        severity="info"
    )


def validate_database_url(url: Optional[str]) -> ValidationResult:
    """
    Validate DATABASE_URL format.

    Requirements:
    - Must be valid PostgreSQL connection string
    - Must include all required components
    - Should use SSL in production
    """
    if not url:
        return ValidationResult(
            name="DATABASE_URL",
            valid=False,
            message="Not set (Required for database connection)",
            severity="critical"
        )

    # Parse PostgreSQL URL pattern
    pattern = r'^postgresql(?:\+\w+)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)(?:\?(.+))?$'
    match = re.match(pattern, url)

    if not match:
        return ValidationResult(
            name="DATABASE_URL",
            valid=False,
            message="Invalid PostgreSQL URL format",
            severity="critical"
        )

    user, password, host, port, database, params = match.groups()

    # Check for localhost/development values
    if host in ['localhost', '127.0.0.1', 'postgres', 'db']:
        return ValidationResult(
            name="DATABASE_URL",
            valid=False,
            message=f"Using development host: {host} (use production hostname)",
            severity="warning"
        )

    # Check for SSL
    if params and 'sslmode=require' in params:
        ssl_status = "SSL enabled"
    elif params and 'sslmode=disable' in params:
        return ValidationResult(
            name="DATABASE_URL",
            valid=False,
            message="SSL explicitly disabled (HIPAA requires encryption in transit)",
            severity="critical"
        )
    else:
        ssl_status = "SSL not specified (add ?sslmode=require)"

    return ValidationResult(
        name="DATABASE_URL",
        valid=True,
        message=f"Valid PostgreSQL URL ({ssl_status})",
        severity="info"
    )


def load_secrets_from_env() -> Dict[str, Optional[str]]:
    """Load secrets from environment variables."""
    prefix_map = {
        'CI_': 'CI environment',
        'PROD_': 'Production',
        'STAGING_': 'Staging',
        'DEV_': 'Development',
    }

    # Detect environment from prefixes
    env_prefix = ''
    for prefix in prefix_map:
        if os.getenv(f'{prefix}ENCRYPTION_MASTER_KEY'):
            env_prefix = prefix
            break

    # Load secrets with or without prefix
    secrets = {
        'ENCRYPTION_MASTER_KEY': os.getenv(f'{env_prefix}ENCRYPTION_MASTER_KEY') or os.getenv('ENCRYPTION_MASTER_KEY'),
        'SECRET_KEY': os.getenv(f'{env_prefix}SECRET_KEY') or os.getenv('SECRET_KEY'),
        'JWT_SECRET_KEY': os.getenv(f'{env_prefix}JWT_SECRET_KEY') or os.getenv('JWT_SECRET_KEY'),
        'CSRF_SECRET_KEY': os.getenv(f'{env_prefix}CSRF_SECRET_KEY') or os.getenv('CSRF_SECRET_KEY'),
        'DATABASE_URL': os.getenv(f'{env_prefix}DATABASE_URL') or os.getenv('DATABASE_URL'),
        'DATABASE_PASSWORD': os.getenv(f'{env_prefix}POSTGRES_PASSWORD') or os.getenv('POSTGRES_PASSWORD'),
        'REDIS_PASSWORD': os.getenv(f'{env_prefix}REDIS_PASSWORD') or os.getenv('REDIS_PASSWORD'),
        'SSH_PRIVATE_KEY': os.getenv('SSH_PRIVATE_KEY'),
        'MINIO_ACCESS_KEY': os.getenv(f'{env_prefix}MINIO_ACCESS_KEY') or os.getenv('MINIO_ACCESS_KEY'),
        'MINIO_SECRET_KEY': os.getenv(f'{env_prefix}MINIO_SECRET_KEY') or os.getenv('MINIO_SECRET_KEY'),
    }

    return secrets, env_prefix


def load_secrets_from_file(filepath: str) -> Dict[str, Optional[str]]:
    """
    Load secrets from a file (for testing only).

    WARNING: Never use this in production or commit secret files!
    """
    secrets = {}

    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    secrets[key.strip()] = value
    except FileNotFoundError:
        print_colored(f"Error: File '{filepath}' not found", Colors.RED)
        sys.exit(2)
    except Exception as e:
        print_colored(f"Error reading file: {e}", Colors.RED)
        sys.exit(2)

    return secrets, ''


def validate_all_secrets(secrets: Dict[str, Optional[str]], verbose: bool = False) -> Tuple[List[ValidationResult], bool, bool]:
    """
    Validate all secrets and return results.

    Returns:
        Tuple of (results, has_critical_failures, has_warnings)
    """
    results = []

    # Critical secrets (required for HIPAA compliance)
    results.append(validate_encryption_key(secrets.get('ENCRYPTION_MASTER_KEY')))

    # Application secrets
    results.append(validate_secret_key(secrets.get('SECRET_KEY')))
    results.append(validate_jwt_secret(secrets.get('JWT_SECRET_KEY')))

    if secrets.get('CSRF_SECRET_KEY'):
        results.append(validate_secret_key(secrets.get('CSRF_SECRET_KEY'), 'CSRF_SECRET_KEY', min_length=32))

    # Database secrets
    if secrets.get('DATABASE_URL'):
        results.append(validate_database_url(secrets.get('DATABASE_URL')))

    if secrets.get('DATABASE_PASSWORD'):
        results.append(validate_database_password(secrets.get('DATABASE_PASSWORD')))

    # Redis
    if secrets.get('REDIS_PASSWORD'):
        results.append(validate_redis_password(secrets.get('REDIS_PASSWORD')))

    # SSH deployment
    if secrets.get('SSH_PRIVATE_KEY'):
        results.append(validate_ssh_key(secrets.get('SSH_PRIVATE_KEY')))

    # Optional: MinIO/S3
    if secrets.get('MINIO_ACCESS_KEY'):
        results.append(ValidationResult(
            name="MINIO_ACCESS_KEY",
            valid=len(secrets['MINIO_ACCESS_KEY']) >= 20,
            message=f"MinIO access key configured ({len(secrets['MINIO_ACCESS_KEY'])} chars)",
            severity="info" if len(secrets['MINIO_ACCESS_KEY']) >= 20 else "warning"
        ))

    if secrets.get('MINIO_SECRET_KEY'):
        results.append(ValidationResult(
            name="MINIO_SECRET_KEY",
            valid=len(secrets['MINIO_SECRET_KEY']) >= 40,
            message=f"MinIO secret key configured ({len(secrets['MINIO_SECRET_KEY'])} chars)",
            severity="info" if len(secrets['MINIO_SECRET_KEY']) >= 40 else "warning"
        ))

    has_critical = any(r.severity == 'critical' and not r.valid for r in results)
    has_warnings = any(r.severity == 'warning' and not r.valid for r in results)

    return results, has_critical, has_warnings


def print_results(results: List[ValidationResult], env_prefix: str, verbose: bool = False) -> None:
    """Print validation results with color coding."""

    # Header
    print()
    print_colored("=" * 60, Colors.CYAN, bold=True)
    print_colored("  GitHub Secrets Validation Report", Colors.CYAN, bold=True)
    if env_prefix:
        print_colored(f"  Environment: {env_prefix.rstrip('_')}", Colors.CYAN)
    print_colored("=" * 60, Colors.CYAN, bold=True)
    print()

    # Group results by status
    critical_failures = [r for r in results if r.severity == 'critical' and not r.valid]
    warnings = [r for r in results if r.severity == 'warning' and not r.valid]
    successes = [r for r in results if r.valid]

    # Print critical failures
    if critical_failures:
        print_colored("🔴 CRITICAL FAILURES", Colors.RED, bold=True)
        print_colored("-" * 40, Colors.RED)
        for result in critical_failures:
            print_colored(f"  ✗ {result.name}", Colors.RED)
            print_colored(f"    {result.message}", Colors.RED)
        print()

    # Print warnings
    if warnings:
        print_colored("🟡 WARNINGS", Colors.YELLOW, bold=True)
        print_colored("-" * 40, Colors.YELLOW)
        for result in warnings:
            print_colored(f"  ⚠ {result.name}", Colors.YELLOW)
            print_colored(f"    {result.message}", Colors.YELLOW)
        print()

    # Print successes (verbose mode or if no failures)
    if verbose or (not critical_failures and not warnings):
        print_colored("🟢 VALIDATED SECRETS", Colors.GREEN, bold=True)
        print_colored("-" * 40, Colors.GREEN)
        for result in successes:
            print_colored(f"  ✓ {result.name}", Colors.GREEN)
            if verbose:
                print_colored(f"    {result.message}", Colors.GREEN)
        print()

    # Summary
    print_colored("=" * 60, Colors.CYAN)
    print_colored("  SUMMARY", Colors.CYAN, bold=True)
    print_colored("-" * 40, Colors.CYAN)

    total = len(results)
    valid = len(successes)

    if critical_failures:
        status_color = Colors.RED
        status_text = "❌ FAILED - Critical issues found"
    elif warnings:
        status_color = Colors.YELLOW
        status_text = "⚠️  PASSED WITH WARNINGS"
    else:
        status_color = Colors.GREEN
        status_text = "✅ PASSED - All secrets valid"

    print_colored(f"  Status: {status_text}", status_color, bold=True)
    print_colored(f"  Validated: {valid}/{total} secrets", Colors.CYAN)

    if critical_failures:
        print_colored(f"  Critical Issues: {len(critical_failures)}", Colors.RED)
    if warnings:
        print_colored(f"  Warnings: {len(warnings)}", Colors.YELLOW)

    print_colored("=" * 60, Colors.CYAN)
    print()


def main():
    """Main validation routine."""
    parser = argparse.ArgumentParser(
        description='Validate GitHub Secrets for PazPaz deployment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed validation messages'
    )

    parser.add_argument(
        '--env',
        choices=['ci', 'development', 'staging', 'production'],
        help='Specify environment to validate'
    )

    parser.add_argument(
        '--from-file',
        metavar='FILE',
        help='Load secrets from file (TESTING ONLY - never use in production!)'
    )

    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output (exit code only)'
    )

    args = parser.parse_args()

    # Disable colors if requested or not TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    # Load secrets
    if args.from_file:
        print_colored("⚠️  WARNING: Loading secrets from file (NEVER do this in production!)", Colors.YELLOW, bold=True)
        secrets, env_prefix = load_secrets_from_file(args.from_file)
    else:
        secrets, env_prefix = load_secrets_from_env()

    # Override environment if specified
    if args.env:
        env_map = {
            'ci': 'CI_',
            'development': 'DEV_',
            'staging': 'STAGING_',
            'production': 'PROD_'
        }
        env_prefix = env_map[args.env]

    # Validate all secrets
    results, has_critical, has_warnings = validate_all_secrets(secrets, args.verbose)

    # Print results (unless quiet mode)
    if not args.quiet:
        print_results(results, env_prefix, args.verbose)

    # Exit with appropriate code
    if has_critical:
        if not args.quiet:
            print_colored("Action Required: Fix critical issues before deployment", Colors.RED, bold=True)
        sys.exit(1)
    elif has_warnings:
        if not args.quiet:
            print_colored("Recommendation: Review warnings for production deployment", Colors.YELLOW)
        sys.exit(0)  # Don't fail on warnings
    else:
        if not args.quiet:
            print_colored("✅ All secrets validated successfully!", Colors.GREEN, bold=True)
        sys.exit(0)


if __name__ == "__main__":
    main()