#!/bin/bash
# =============================================================================
# Production Environment Validation Script for PazPaz
# =============================================================================
# Validates that all required environment variables are present and properly
# configured for production deployment. This script is HIPAA-compliant and
# ensures all security requirements are met.
#
# Exit codes:
#   0 - All validations passed
#   1 - Missing variables or validation failures
#   2 - Weak secrets detected
#   3 - Example/placeholder values found
# =============================================================================

set -uo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters for issues
MISSING_VARS=0
WEAK_SECRETS=0
EXAMPLE_VALUES=0
FORMAT_ERRORS=0
WARNINGS=0

# Arrays to track issues
declare -a missing_variables=()
declare -a weak_secrets_list=()
declare -a example_values_list=()
declare -a format_errors_list=()
declare -a warnings_list=()

# =============================================================================
# Helper Functions
# =============================================================================

log_error() {
    echo -e "${RED}✗ ERROR:${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}⚠ WARNING:${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if environment file exists
check_env_file() {
    local env_file="${1:-.env.production}"
    if [ ! -f "$env_file" ]; then
        log_error "$env_file file not found!"
        echo ""
        echo "To create a production environment file:"
        echo "  1. Copy the template: cp .env.production.example $env_file"
        echo "  2. Edit $env_file and replace all CHANGE_ME values"
        echo "  3. Generate secure values using the commands in the comments"
        echo "  4. Run this script again to validate"
        exit 1
    fi
    log_success "Found $env_file file"
}

# Load environment variables (without executing them in current shell)
load_env_file() {
    local env_file="${1:-.env.production}"
    # Create a temporary file to store variable names and values
    local temp_file=$(mktemp)

    # Parse environment file, handling comments and empty lines
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue

        # Extract variable name and value
        if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            var_value="${BASH_REMATCH[2]}"

            # Remove quotes if present
            var_value="${var_value%\"}"
            var_value="${var_value#\"}"
            var_value="${var_value%\'}"
            var_value="${var_value#\'}"

            echo "${var_name}=${var_value}" >> "$temp_file"
        fi
    done < "$env_file"

    echo "$temp_file"
}

# Check if a variable exists and has a value
check_required_var() {
    local var_name=$1
    local env_file=$2

    if grep -q "^${var_name}=" "$env_file"; then
        local value=$(grep "^${var_name}=" "$env_file" | cut -d'=' -f2-)
        if [ -z "$value" ] || [ "$value" = '""' ] || [ "$value" = "''" ]; then
            missing_variables+=("$var_name (empty)")
            ((MISSING_VARS++))
            return 1
        fi
        return 0
    else
        missing_variables+=("$var_name (not found)")
        ((MISSING_VARS++))
        return 1
    fi
}

# Get variable value from temp file
get_var_value() {
    local var_name=$1
    local env_file=$2

    if grep -q "^${var_name}=" "$env_file"; then
        grep "^${var_name}=" "$env_file" | cut -d'=' -f2-
    else
        echo ""
    fi
}

# Check if value contains example/placeholder text
check_for_example_value() {
    local var_name=$1
    local value=$2

    local example_patterns=(
        "CHANGE_ME"
        "changeme"
        "your-"
        "your_"
        "example.com"
        "placeholder"
        "PLACEHOLDER"
        "TODO"
        "FIXME"
        "xxx"
        "XXX"
    )

    for pattern in "${example_patterns[@]}"; do
        if [[ "$value" == *"$pattern"* ]]; then
            example_values_list+=("$var_name contains '$pattern'")
            ((EXAMPLE_VALUES++))
            return 1
        fi
    done

    return 0
}

# Validate password strength
check_password_strength() {
    local var_name=$1
    local password=$2
    local min_length=$3

    if [ ${#password} -lt $min_length ]; then
        weak_secrets_list+=("$var_name is only ${#password} characters (minimum: $min_length)")
        ((WEAK_SECRETS++))
        return 1
    fi

    # Check for common weak passwords (only standalone words)
    local weak_patterns=(
        "^password$"
        "^123456"
        "^admin"
        "^secret$"
        "^default"
        "^test"
        "^changeme"
        "^example"
    )

    local lower_password=$(echo "$password" | tr '[:upper:]' '[:lower:]')
    for pattern in "${weak_patterns[@]}"; do
        if [[ "$lower_password" =~ $pattern ]]; then
            weak_secrets_list+=("$var_name matches weak pattern '$pattern'")
            ((WEAK_SECRETS++))
            return 1
        fi
    done

    return 0
}

# Validate base64 encoding
check_base64() {
    local var_name=$1
    local value=$2

    # Check if it's valid base64
    if ! echo "$value" | base64 -d >/dev/null 2>&1; then
        format_errors_list+=("$var_name is not valid base64")
        ((FORMAT_ERRORS++))
        return 1
    fi

    # Check minimum decoded length for encryption keys
    local decoded_length=$(echo "$value" | base64 -d 2>/dev/null | wc -c)
    if [ "$decoded_length" -lt 32 ]; then
        weak_secrets_list+=("$var_name decoded length is $decoded_length bytes (minimum: 32)")
        ((WEAK_SECRETS++))
        return 1
    fi

    return 0
}

# Validate URL format
check_url_format() {
    local var_name=$1
    local url=$2
    local require_https=$3

    # Basic URL regex
    local url_regex='^https?://[a-zA-Z0-9.-]+(:[0-9]+)?(/.*)?$'

    if ! [[ "$url" =~ $url_regex ]]; then
        format_errors_list+=("$var_name is not a valid URL: $url")
        ((FORMAT_ERRORS++))
        return 1
    fi

    # Check for HTTPS in production
    if [ "$require_https" = "true" ] && [[ ! "$url" =~ ^https:// ]]; then
        warnings_list+=("$var_name should use HTTPS in production: $url")
        ((WARNINGS++))
    fi

    return 0
}

# Validate email format
check_email_format() {
    local var_name=$1
    local email=$2

    local email_regex='^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if ! [[ "$email" =~ $email_regex ]]; then
        format_errors_list+=("$var_name is not a valid email: $email")
        ((FORMAT_ERRORS++))
        return 1
    fi

    return 0
}

# Validate domain/host format
check_domain_format() {
    local var_name=$1
    local domains=$2

    # Split comma-separated domains
    IFS=',' read -ra domain_list <<< "$domains"

    local domain_regex='^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    local ip_regex='^([0-9]{1,3}\.){3}[0-9]{1,3}$'

    for domain in "${domain_list[@]}"; do
        # Trim whitespace
        domain=$(echo "$domain" | xargs)

        # Allow localhost and IP addresses for Docker internal communication
        if [[ "$domain" == "localhost" ]] || [[ "$domain" =~ $ip_regex ]]; then
            continue
        fi

        if ! [[ "$domain" =~ $domain_regex ]]; then
            format_errors_list+=("$var_name contains invalid domain: $domain")
            ((FORMAT_ERRORS++))
            return 1
        fi
    done

    return 0
}

# =============================================================================
# Main Validation Logic
# =============================================================================

main() {
    # Accept optional environment file path as first argument
    local env_file="${1:-.env.production}"

    echo "================================================================================"
    echo "                    PazPaz Production Environment Validator"
    echo "================================================================================"
    echo ""

    # Step 1: Check if environment file exists
    check_env_file "$env_file"

    # Step 2: Load environment variables
    log_info "Loading environment variables..."
    ENV_TEMP_FILE=$(load_env_file "$env_file")

    # Step 3: Check all required variables
    echo ""
    echo "Checking Required Variables:"
    echo "----------------------------"

    # GitHub/Docker Registry
    check_required_var "GITHUB_REPOSITORY" "$ENV_TEMP_FILE"
    check_required_var "IMAGE_TAG" "$ENV_TEMP_FILE"
    # VERSION is optional - not critical for deployment
    # check_required_var "VERSION" "$ENV_TEMP_FILE"

    # Database
    check_required_var "POSTGRES_PASSWORD" "$ENV_TEMP_FILE"

    # Redis
    check_required_var "REDIS_PASSWORD" "$ENV_TEMP_FILE"

    # MinIO/S3
    check_required_var "S3_ACCESS_KEY" "$ENV_TEMP_FILE"
    check_required_var "S3_SECRET_KEY" "$ENV_TEMP_FILE"
    check_required_var "S3_BUCKET_NAME" "$ENV_TEMP_FILE"
    check_required_var "S3_REGION" "$ENV_TEMP_FILE"
    check_required_var "MINIO_ENCRYPTION_KEY" "$ENV_TEMP_FILE"

    # Application Security
    check_required_var "SECRET_KEY" "$ENV_TEMP_FILE"
    check_required_var "JWT_SECRET_KEY" "$ENV_TEMP_FILE"
    check_required_var "ENCRYPTION_MASTER_KEY" "$ENV_TEMP_FILE"

    # Application Configuration
    check_required_var "FRONTEND_URL" "$ENV_TEMP_FILE"
    check_required_var "ALLOWED_HOSTS" "$ENV_TEMP_FILE"

    # Email Configuration - OPTIONAL for now (can be configured later for magic link auth)
    log_info "Email (SMTP) configuration is optional and can be set up later for magic link authentication"
    # check_required_var "SMTP_HOST" "$ENV_TEMP_FILE"
    # check_required_var "SMTP_PORT" "$ENV_TEMP_FILE"
    # check_required_var "SMTP_USER" "$ENV_TEMP_FILE"
    # check_required_var "SMTP_PASSWORD" "$ENV_TEMP_FILE"
    # check_required_var "EMAILS_FROM_EMAIL" "$ENV_TEMP_FILE"

    if [ ${MISSING_VARS} -eq 0 ]; then
        log_success "All required variables are present"
    fi

    # Step 4: Validate secret strength
    echo ""
    echo "Validating Secret Strength:"
    echo "---------------------------"

    # Check password strength
    postgres_pass=$(get_var_value "POSTGRES_PASSWORD" "$ENV_TEMP_FILE")
    [ -n "$postgres_pass" ] && check_password_strength "POSTGRES_PASSWORD" "$postgres_pass" 20

    redis_pass=$(get_var_value "REDIS_PASSWORD" "$ENV_TEMP_FILE")
    [ -n "$redis_pass" ] && check_password_strength "REDIS_PASSWORD" "$redis_pass" 20

    s3_access=$(get_var_value "S3_ACCESS_KEY" "$ENV_TEMP_FILE")
    [ -n "$s3_access" ] && check_password_strength "S3_ACCESS_KEY" "$s3_access" 16

    s3_secret=$(get_var_value "S3_SECRET_KEY" "$ENV_TEMP_FILE")
    [ -n "$s3_secret" ] && check_password_strength "S3_SECRET_KEY" "$s3_secret" 32

    secret_key=$(get_var_value "SECRET_KEY" "$ENV_TEMP_FILE")
    [ -n "$secret_key" ] && check_password_strength "SECRET_KEY" "$secret_key" 64

    jwt_secret=$(get_var_value "JWT_SECRET_KEY" "$ENV_TEMP_FILE")
    [ -n "$jwt_secret" ] && check_password_strength "JWT_SECRET_KEY" "$jwt_secret" 32

    smtp_pass=$(get_var_value "SMTP_PASSWORD" "$ENV_TEMP_FILE")
    [ -n "$smtp_pass" ] && check_password_strength "SMTP_PASSWORD" "$smtp_pass" 16

    # Check base64 encoded keys
    minio_key=$(get_var_value "MINIO_ENCRYPTION_KEY" "$ENV_TEMP_FILE")
    [ -n "$minio_key" ] && check_base64 "MINIO_ENCRYPTION_KEY" "$minio_key"

    encryption_key=$(get_var_value "ENCRYPTION_MASTER_KEY" "$ENV_TEMP_FILE")
    [ -n "$encryption_key" ] && check_base64 "ENCRYPTION_MASTER_KEY" "$encryption_key"

    if [ ${WEAK_SECRETS} -eq 0 ]; then
        log_success "All secrets meet strength requirements"
    fi

    # Step 5: Check for example/placeholder values
    echo ""
    echo "Checking for Example Values:"
    echo "----------------------------"

    # Check all variables for example values
    while IFS= read -r line; do
        if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            var_value="${BASH_REMATCH[2]}"
            check_for_example_value "$var_name" "$var_value"
        fi
    done < "$ENV_TEMP_FILE"

    if [ ${EXAMPLE_VALUES} -eq 0 ]; then
        log_success "No example/placeholder values found"
    fi

    # Step 6: Validate formats
    echo ""
    echo "Validating Value Formats:"
    echo "-------------------------"

    # Validate URLs
    frontend_url=$(get_var_value "FRONTEND_URL" "$ENV_TEMP_FILE")
    [ -n "$frontend_url" ] && check_url_format "FRONTEND_URL" "$frontend_url" "true"

    # Validate email
    from_email=$(get_var_value "EMAILS_FROM_EMAIL" "$ENV_TEMP_FILE")
    [ -n "$from_email" ] && check_email_format "EMAILS_FROM_EMAIL" "$from_email"

    smtp_user=$(get_var_value "SMTP_USER" "$ENV_TEMP_FILE")
    if [ -n "$smtp_user" ] && [ "$smtp_user" != "apikey" ] && [ "$smtp_user" != "resend" ]; then
        check_email_format "SMTP_USER" "$smtp_user"
    fi

    # Validate domains
    allowed_hosts=$(get_var_value "ALLOWED_HOSTS" "$ENV_TEMP_FILE")
    [ -n "$allowed_hosts" ] && check_domain_format "ALLOWED_HOSTS" "$allowed_hosts"

    # Validate GitHub repository format
    github_repo=$(get_var_value "GITHUB_REPOSITORY" "$ENV_TEMP_FILE")
    if [ -n "$github_repo" ]; then
        if ! [[ "$github_repo" =~ ^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$ ]]; then
            format_errors_list+=("GITHUB_REPOSITORY should be in format: username/repository")
            ((FORMAT_ERRORS++))
        fi
    fi

    # Validate numeric values
    smtp_port=$(get_var_value "SMTP_PORT" "$ENV_TEMP_FILE")
    if [ -n "$smtp_port" ]; then
        if ! [[ "$smtp_port" =~ ^[0-9]+$ ]]; then
            format_errors_list+=("SMTP_PORT must be a number")
            ((FORMAT_ERRORS++))
        fi
    fi

    if [ ${FORMAT_ERRORS} -eq 0 ]; then
        log_success "All value formats are valid"
    fi

    # Step 7: Security checks
    echo ""
    echo "Security Validation:"
    echo "-------------------"

    # Check that encryption keys are different
    if [ -n "$minio_key" ] && [ -n "$encryption_key" ] && [ "$minio_key" = "$encryption_key" ]; then
        warnings_list+=("MINIO_ENCRYPTION_KEY and ENCRYPTION_MASTER_KEY should be different")
        ((WARNINGS++))
    fi

    # Check that passwords are unique
    if [ -n "$postgres_pass" ] && [ -n "$redis_pass" ] && [ "$postgres_pass" = "$redis_pass" ]; then
        warnings_list+=("POSTGRES_PASSWORD and REDIS_PASSWORD should be different")
        ((WARNINGS++))
    fi

    # Check SSL/TLS settings
    smtp_tls=$(get_var_value "SMTP_USE_TLS" "$ENV_TEMP_FILE")
    if [ "$smtp_tls" != "true" ]; then
        warnings_list+=("SMTP_USE_TLS should be 'true' for production")
        ((WARNINGS++))
    fi

    db_ssl=$(get_var_value "DB_SSL_ENABLED" "$ENV_TEMP_FILE")
    if [ -n "$db_ssl" ] && [ "$db_ssl" != "true" ]; then
        warnings_list+=("DB_SSL_ENABLED should be 'true' for production")
        ((WARNINGS++))
    fi

    if [ ${WARNINGS} -eq 0 ]; then
        log_success "No security warnings"
    else
        log_warning "Found ${WARNINGS} security warnings"
    fi

    # Clean up temp file
    rm -f "$ENV_TEMP_FILE"

    # =============================================================================
    # Summary Report
    # =============================================================================

    echo ""
    echo "================================================================================"
    echo "                              VALIDATION SUMMARY"
    echo "================================================================================"

    # Display detailed issues
    if [ ${#missing_variables[@]} -gt 0 ]; then
        echo ""
        log_error "Missing Variables:"
        for var in "${missing_variables[@]}"; do
            echo "  - $var"
        done
    fi

    if [ ${#weak_secrets_list[@]} -gt 0 ]; then
        echo ""
        log_error "Weak Secrets:"
        for issue in "${weak_secrets_list[@]}"; do
            echo "  - $issue"
        done
    fi

    if [ ${#example_values_list[@]} -gt 0 ]; then
        echo ""
        log_error "Example/Placeholder Values:"
        for issue in "${example_values_list[@]}"; do
            echo "  - $issue"
        done
    fi

    if [ ${#format_errors_list[@]} -gt 0 ]; then
        echo ""
        log_error "Format Errors:"
        for issue in "${format_errors_list[@]}"; do
            echo "  - $issue"
        done
    fi

    if [ ${#warnings_list[@]} -gt 0 ]; then
        echo ""
        log_warning "Security Warnings:"
        for warning in "${warnings_list[@]}"; do
            echo "  - $warning"
        done
    fi

    # Final status
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "Total Issues Found:"
    echo "  Missing Variables:    ${MISSING_VARS}"
    echo "  Weak Secrets:         ${WEAK_SECRETS}"
    echo "  Example Values:       ${EXAMPLE_VALUES}"
    echo "  Format Errors:        ${FORMAT_ERRORS}"
    echo "  Security Warnings:    ${WARNINGS}"
    echo "--------------------------------------------------------------------------------"

    # Determine exit code
    if [ ${MISSING_VARS} -gt 0 ] || [ ${FORMAT_ERRORS} -gt 0 ]; then
        echo ""
        log_error "❌ VALIDATION FAILED: Critical errors found"
        echo ""
        echo "Please fix the issues above and run this script again."
        exit 1
    elif [ ${WEAK_SECRETS} -gt 0 ]; then
        echo ""
        log_error "❌ VALIDATION FAILED: Weak secrets detected"
        echo ""
        echo "Please generate stronger secrets using the commands in .env.production.example"
        exit 2
    elif [ ${EXAMPLE_VALUES} -gt 0 ]; then
        echo ""
        log_error "❌ VALIDATION FAILED: Example/placeholder values found"
        echo ""
        echo "Please replace all CHANGE_ME and example values with real configuration."
        exit 3
    elif [ ${WARNINGS} -gt 0 ]; then
        echo ""
        log_warning "⚠️  VALIDATION PASSED WITH WARNINGS"
        echo ""
        echo "The configuration is valid but has security warnings."
        echo "Consider addressing the warnings above for better security."
        exit 0
    else
        echo ""
        log_success "✅ VALIDATION PASSED: All checks successful!"
        echo ""
        echo "Your .env.production file is ready for deployment."
        exit 0
    fi
}

# Run main function
main "$@"