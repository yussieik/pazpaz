#!/usr/bin/env python3
"""
S3/MinIO Credential Validation Script

This script validates S3/MinIO credentials to ensure they meet security requirements
before deployment. It checks for:

1. Default credentials (minioadmin/minioadmin123) in production
2. Password strength requirements (length, complexity)
3. Environment-specific security configurations
4. Credential age and rotation warnings

Usage:
    python scripts/validate_s3_credentials.py
    python scripts/validate_s3_credentials.py --environment production
    python scripts/validate_s3_credentials.py --strict

Exit codes:
    0 - All validations passed
    1 - Validation errors found (see output)
    2 - Fatal configuration error

See: backend/docs/storage/S3_CREDENTIAL_MANAGEMENT.md
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# ANSI color codes for output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(message: str):
    """Print formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(message: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_warning(message: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ WARNING: {message}{Colors.ENDC}")


def print_error(message: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ ERROR: {message}{Colors.ENDC}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {message}{Colors.ENDC}")


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse key=value
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value

    return env_vars


def get_credentials() -> Tuple[str, str, str]:
    """
    Get S3/MinIO credentials from environment or .env file.

    Returns:
        Tuple[access_key, secret_key, environment]
    """
    # Try environment variables first
    access_key = os.getenv("S3_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER")
    secret_key = os.getenv("S3_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD")
    environment = os.getenv("ENVIRONMENT", "development")

    # If not in environment, try .env file
    if not access_key or not secret_key:
        env_file = Path(__file__).parent.parent / ".env"
        env_vars = load_env_file(env_file)
        access_key = access_key or env_vars.get("S3_ACCESS_KEY")
        secret_key = secret_key or env_vars.get("S3_SECRET_KEY")
        environment = environment or env_vars.get("ENVIRONMENT", "development")

    return access_key or "", secret_key or "", environment.lower()


def validate_default_credentials(
    access_key: str, secret_key: str, environment: str
) -> List[str]:
    """
    Validate that default credentials are not used in production.

    Args:
        access_key: S3 access key / MinIO root user
        secret_key: S3 secret key / MinIO root password
        environment: Deployment environment (development, staging, production)

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check for default credentials
    is_default_user = access_key in ["minioadmin", "admin", "root"]
    is_default_pass = secret_key in ["minioadmin123", "password", "admin"]

    if environment in ["production", "prod"]:
        if is_default_user:
            errors.append(
                f"Default username '{access_key}' detected in PRODUCTION environment. "
                "This is a CRITICAL security risk!"
            )
        if is_default_pass:
            errors.append(
                "Default password detected in PRODUCTION environment. "
                "This is a CRITICAL security risk!"
            )
    elif environment in ["staging", "stage"]:
        if is_default_user or is_default_pass:
            errors.append(
                f"Default credentials detected in STAGING environment. "
                "Change credentials before deployment."
            )

    return errors


def validate_password_strength(secret_key: str, strict: bool = False) -> List[str]:
    """
    Validate password meets strength requirements.

    Requirements:
        - Minimum 20 characters (32 recommended)
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 digit
        - At least 1 special character
        - No common dictionary words
        - No sequential characters (abc, 123)

    Args:
        secret_key: Password to validate
        strict: If True, enforce stricter requirements (32 chars minimum)

    Returns:
        List of error/warning messages (empty if valid)
    """
    errors = []
    warnings = []

    # Check length
    min_length = 32 if strict else 20
    if len(secret_key) < min_length:
        errors.append(
            f"Password too short: {len(secret_key)} characters "
            f"(minimum: {min_length})"
        )
    elif len(secret_key) < 32 and not strict:
        warnings.append(
            f"Password length is {len(secret_key)} characters. "
            "Consider using 32+ characters for better security."
        )

    # Check character variety
    has_upper = bool(re.search(r"[A-Z]", secret_key))
    has_lower = bool(re.search(r"[a-z]", secret_key))
    has_digit = bool(re.search(r"[0-9]", secret_key))
    has_special = bool(re.search(r"[^A-Za-z0-9]", secret_key))

    if not has_upper:
        errors.append("Password missing uppercase letters")
    if not has_lower:
        errors.append("Password missing lowercase letters")
    if not has_digit:
        errors.append("Password missing digits")
    if not has_special:
        warnings.append(
            "Password missing special characters. "
            "Consider adding symbols for better security."
        )

    # Check for common patterns
    sequential_patterns = [
        "abc",
        "bcd",
        "cde",
        "123",
        "234",
        "345",
        "456",
        "567",
        "678",
        "789",
    ]
    for pattern in sequential_patterns:
        if pattern in secret_key.lower():
            warnings.append(
                f"Password contains sequential characters: '{pattern}'. "
                "Avoid predictable patterns."
            )
            break

    # Check for repeated characters (more than 2 consecutive)
    if re.search(r"(.)\1{2,}", secret_key):
        warnings.append(
            "Password contains 3+ repeated characters (e.g., 'aaa'). "
            "Avoid repetition."
        )

    # Check for common dictionary words
    common_words = [
        "password",
        "admin",
        "user",
        "root",
        "test",
        "development",
        "staging",
        "production",
        "secret",
        "key",
        "minio",
        "pazpaz",
    ]
    for word in common_words:
        if word in secret_key.lower():
            errors.append(
                f"Password contains common word: '{word}'. "
                "Use randomly generated passwords."
            )
            break

    # Combine errors and warnings
    all_messages = []
    all_messages.extend(errors)
    if not strict:
        # In non-strict mode, warnings don't fail validation
        for warning in warnings:
            all_messages.append(f"WARNING: {warning}")
    else:
        # In strict mode, warnings are treated as errors
        all_messages.extend(warnings)

    return all_messages


def validate_username(access_key: str) -> List[str]:
    """
    Validate username meets requirements.

    Requirements:
        - Minimum 8 characters
        - Maximum 32 characters
        - Alphanumeric, hyphens, underscores only
        - Not a default/common username

    Args:
        access_key: Username to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check length
    if len(access_key) < 8:
        errors.append(f"Username too short: {len(access_key)} characters (minimum: 8)")
    elif len(access_key) > 32:
        errors.append(
            f"Username too long: {len(access_key)} characters (maximum: 32)"
        )

    # Check allowed characters
    if not re.match(r"^[A-Za-z0-9_-]+$", access_key):
        errors.append(
            "Username contains invalid characters. "
            "Allowed: alphanumeric, hyphens, underscores"
        )

    # Check for default/common usernames
    common_usernames = [
        "minioadmin",
        "admin",
        "root",
        "user",
        "test",
        "dev",
        "administrator",
    ]
    if access_key.lower() in common_usernames:
        errors.append(
            f"Username '{access_key}' is too common. "
            "Use a unique, non-guessable username."
        )

    return errors


def check_credential_rotation(environment: str) -> List[str]:
    """
    Check if credentials need rotation based on environment.

    Rotation schedules:
        - Development: 180 days (6 months)
        - Staging: 90 days (3 months)
        - Production: 90 days (3 months)

    Args:
        environment: Deployment environment

    Returns:
        List of warning messages
    """
    warnings = []

    # This is a placeholder - in a real implementation, you'd track last rotation date
    # in a separate file or database. For now, just provide guidance.

    rotation_schedule = {
        "development": 180,
        "staging": 90,
        "production": 90,
    }

    days = rotation_schedule.get(environment, 90)

    warnings.append(
        f"REMINDER: Rotate credentials every {days} days in {environment} environment. "
        f"See docs/storage/S3_CREDENTIAL_MANAGEMENT.md for rotation procedures."
    )

    return warnings


def validate_environment_config(environment: str, access_key: str) -> List[str]:
    """
    Validate environment-specific configurations.

    Args:
        environment: Deployment environment
        access_key: S3 access key (to check if IAM role should be used)

    Returns:
        List of warning/info messages
    """
    messages = []

    if environment in ["production", "prod"]:
        if access_key:
            messages.append(
                "INFO: Production environment detected with access key. "
                "Consider using AWS IAM roles instead of access keys for better security. "
                "See docs/storage/S3_CREDENTIAL_MANAGEMENT.md (Production Setup)."
            )
        else:
            messages.append(
                "INFO: Production environment with no access key (likely using IAM role). "
                "This is the recommended configuration."
            )

    elif environment in ["staging", "stage"]:
        messages.append(
            "INFO: Staging environment detected. "
            "Ensure credentials are stored in AWS Secrets Manager. "
            "See docs/storage/S3_CREDENTIAL_MANAGEMENT.md (Staging Setup)."
        )

    elif environment in ["development", "dev", "local"]:
        messages.append(
            "INFO: Development environment detected. "
            "Ensure MinIO is bound to localhost only (127.0.0.1) and not exposed to network."
        )

    return messages


def main():
    """Main validation logic."""
    parser = argparse.ArgumentParser(
        description="Validate S3/MinIO credentials for security compliance"
    )
    parser.add_argument(
        "--environment",
        "-e",
        choices=["development", "staging", "production"],
        help="Override detected environment",
    )
    parser.add_argument(
        "--strict",
        "-s",
        action="store_true",
        help="Enable strict validation (treat warnings as errors)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress informational messages",
    )

    args = parser.parse_args()

    # Print header
    if not args.quiet:
        print_header("S3/MinIO Credential Security Validation")

    # Get credentials
    access_key, secret_key, environment = get_credentials()

    # Override environment if specified
    if args.environment:
        environment = args.environment

    if not args.quiet:
        print_info(f"Environment: {environment}")
        print_info(f"Access Key: {access_key[:4]}{'*' * 8} (length: {len(access_key)})")
        print_info(f"Secret Key: {'*' * 12} (length: {len(secret_key)})")
        print()

    # Check if credentials exist
    if not access_key or not secret_key:
        print_error(
            "Credentials not found in environment or .env file. "
            "Set S3_ACCESS_KEY and S3_SECRET_KEY."
        )
        return 2

    # Run validations
    errors = []
    warnings = []

    # 1. Check for default credentials
    if not args.quiet:
        print("1. Checking for default credentials...")
    default_errors = validate_default_credentials(access_key, secret_key, environment)
    if default_errors:
        errors.extend(default_errors)
        for error in default_errors:
            print_error(error)
    else:
        if not args.quiet:
            print_success("No default credentials detected")

    # 2. Validate username
    if not args.quiet:
        print("\n2. Validating username...")
    username_errors = validate_username(access_key)
    if username_errors:
        errors.extend(username_errors)
        for error in username_errors:
            print_error(error)
    else:
        if not args.quiet:
            print_success("Username meets requirements")

    # 3. Validate password strength
    if not args.quiet:
        print("\n3. Validating password strength...")
    password_messages = validate_password_strength(secret_key, strict=args.strict)
    if password_messages:
        for message in password_messages:
            if message.startswith("WARNING:"):
                warning_text = message.replace("WARNING: ", "")
                warnings.append(warning_text)
                if not args.strict:
                    print_warning(warning_text)
                else:
                    print_error(warning_text)
                    errors.append(warning_text)
            else:
                errors.append(message)
                print_error(message)
    else:
        if not args.quiet:
            print_success("Password meets all strength requirements")

    # 4. Check credential rotation reminders
    if not args.quiet:
        print("\n4. Checking credential rotation schedule...")
    rotation_warnings = check_credential_rotation(environment)
    for warning in rotation_warnings:
        if not args.quiet:
            print_warning(warning)

    # 5. Validate environment-specific config
    if not args.quiet:
        print("\n5. Validating environment configuration...")
    env_messages = validate_environment_config(environment, access_key)
    for message in env_messages:
        if not args.quiet:
            print_info(message)

    # Print summary
    if not args.quiet:
        print_header("Validation Summary")

    if errors:
        print_error(f"Found {len(errors)} error(s)")
        for error in errors:
            print(f"  - {error}")
        print()
        print_error("Validation FAILED. Fix errors before deployment.")
        return 1
    elif warnings and not args.strict:
        print_warning(f"Found {len(warnings)} warning(s)")
        for warning in warnings:
            print(f"  - {warning}")
        print()
        print_success("Validation PASSED (with warnings)")
        if not args.quiet:
            print_info("Consider addressing warnings for improved security.")
        return 0
    else:
        print_success("All validations PASSED")
        if not args.quiet:
            print()
            print_info("Credentials meet security requirements.")
            print_info(
                "Remember to rotate credentials according to schedule:"
            )
            print_info("  - Development: Every 180 days")
            print_info("  - Staging: Every 90 days")
            print_info("  - Production: Every 90 days")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nValidation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(2)
