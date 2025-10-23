#!/bin/bash
# PazPaz Secrets Validation Script
# Validates that all required secrets are present and meet security requirements
#
# Usage: ./scripts/validate-secrets.sh [env-file]
# Examples:
#   ./scripts/validate-secrets.sh                    # Check current environment
#   ./scripts/validate-secrets.sh .env.production    # Check specific file
#   ./scripts/validate-secrets.sh --github           # Check GitHub secrets

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
ENV_FILE="${1:-.env}"
CHECK_MODE="file"
ERRORS=0
WARNINGS=0

# Parse arguments
if [ "$#" -gt 0 ]; then
    case "$1" in
        --github)
            CHECK_MODE="github"
            ;;
        --help|-h)
            echo "Usage: $0 [env-file|--github|--help]"
            echo ""
            echo "Options:"
            echo "  env-file     Path to .env file to validate (default: .env)"
            echo "  --github     Check GitHub Actions secrets"
            echo "  --help       Show this help message"
            exit 0
            ;;
    esac
fi

# Output functions
print_header() {
    echo -e "${BLUE}${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}  ✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}  ⚠️  $1${NC}"
    ((WARNINGS++))
}

print_error() {
    echo -e "${RED}  ❌ $1${NC}"
    ((ERRORS++))
}

print_info() {
    echo -e "  ℹ️  $1"
}

# Check if a variable exists and is not empty
check_var_exists() {
    local var_name=$1
    local var_value="${2:-}"

    if [ -z "$var_value" ]; then
        print_error "$var_name is not set or empty"
        return 1
    else
        return 0
    fi
}

# Check if a variable meets minimum length
check_var_length() {
    local var_name=$1
    local var_value="${2:-}"
    local min_length=$3

    if [ ${#var_value} -lt "$min_length" ]; then
        print_error "$var_name is too short (${#var_value} chars, minimum: $min_length)"
        return 1
    else
        print_success "$var_name length OK (${#var_value} chars)"
        return 0
    fi
}

# Check if a string is base64 encoded
check_base64() {
    local var_name=$1
    local var_value="${2:-}"

    if echo "$var_value" | base64 -d >/dev/null 2>&1; then
        print_success "$var_name is valid base64"
        return 0
    else
        print_error "$var_name is not valid base64"
        return 1
    fi
}

# Check if a string is hex encoded
check_hex() {
    local var_name=$1
    local var_value="${2:-}"

    if [[ "$var_value" =~ ^[a-fA-F0-9]+$ ]]; then
        print_success "$var_name is valid hex"
        return 0
    else
        print_error "$var_name is not valid hex"
        return 1
    fi
}

# Check Fernet key format
check_fernet_key() {
    local var_name=$1
    local var_value="${2:-}"

    # Fernet keys are 44 characters (32 bytes base64 encoded with padding)
    if [ ${#var_value} -eq 44 ]; then
        if echo "$var_value" | base64 -d >/dev/null 2>&1; then
            print_success "$var_name is valid Fernet key"
            return 0
        else
            print_error "$var_name is not a valid Fernet key (invalid base64)"
            return 1
        fi
    else
        print_error "$var_name is not a valid Fernet key (wrong length: ${#var_value}, expected: 44)"
        return 1
    fi
}

# Check PostgreSQL connection URL
check_database_url() {
    local var_name=$1
    local var_value="${2:-}"

    if [[ "$var_value" =~ ^postgresql(\+asyncpg)?://[^:]+:[^@]+@[^/]+/[^?]+(\?.*)?$ ]]; then
        # Check for SSL requirement
        if [[ "$var_value" =~ ssl=(require|verify-ca|verify-full) ]]; then
            print_success "$var_name format OK with SSL"
        else
            print_warning "$var_name missing SSL parameter (add ?ssl=require for production)"
        fi
        return 0
    else
        print_error "$var_name is not a valid PostgreSQL URL"
        return 1
    fi
}

# Check Redis URL
check_redis_url() {
    local var_name=$1
    local var_value="${2:-}"

    if [[ "$var_value" =~ ^redis://(:.*)?@[^/]+/[0-9]+$ ]]; then
        print_success "$var_name format OK"
        return 0
    else
        print_error "$var_name is not a valid Redis URL"
        return 1
    fi
}

# Load environment file
load_env_file() {
    local file=$1

    if [ ! -f "$file" ]; then
        print_error "File not found: $file"
        exit 1
    fi

    # Source the file (be careful with this in production!)
    set -a
    source "$file"
    set +a

    print_info "Loaded environment from: $file"
}

# Validate file-based secrets
validate_file_secrets() {
    print_header "🔒 PazPaz Secrets Validator"
    print_header "════════════════════════════════════════"
    echo ""

    if [ "$ENV_FILE" != "current" ]; then
        load_env_file "$ENV_FILE"
    fi

    # Critical: PHI Encryption
    print_header "CRITICAL: PHI Encryption Key"
    if check_var_exists "ENCRYPTION_MASTER_KEY" "$ENCRYPTION_MASTER_KEY"; then
        check_fernet_key "ENCRYPTION_MASTER_KEY" "$ENCRYPTION_MASTER_KEY"
    fi
    echo ""

    # Database
    print_header "Database Credentials"
    if check_var_exists "DATABASE_URL" "${DATABASE_URL:-}"; then
        check_database_url "DATABASE_URL" "$DATABASE_URL"
    fi
    if check_var_exists "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD:-}"; then
        check_var_length "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD" 20
    fi
    echo ""

    # Application Secrets
    print_header "Application Secrets"
    if check_var_exists "SECRET_KEY" "${SECRET_KEY:-}"; then
        check_var_length "SECRET_KEY" "$SECRET_KEY" 64
        check_hex "SECRET_KEY" "$SECRET_KEY"
    fi
    if check_var_exists "JWT_SECRET_KEY" "${JWT_SECRET_KEY:-}"; then
        check_var_length "JWT_SECRET_KEY" "$JWT_SECRET_KEY" 32
        check_base64 "JWT_SECRET_KEY" "$JWT_SECRET_KEY"
    fi
    echo ""

    # Redis
    print_header "Redis Configuration"
    if check_var_exists "REDIS_URL" "${REDIS_URL:-}"; then
        check_redis_url "REDIS_URL" "$REDIS_URL"
    fi
    if check_var_exists "REDIS_PASSWORD" "${REDIS_PASSWORD:-}"; then
        check_var_length "REDIS_PASSWORD" "$REDIS_PASSWORD" 20
    fi
    echo ""

    # MinIO/S3
    print_header "MinIO/S3 Storage"
    if check_var_exists "MINIO_ACCESS_KEY" "${MINIO_ACCESS_KEY:-}"; then
        check_var_length "MINIO_ACCESS_KEY" "$MINIO_ACCESS_KEY" 12
    fi
    if check_var_exists "MINIO_SECRET_KEY" "${MINIO_SECRET_KEY:-}"; then
        check_var_length "MINIO_SECRET_KEY" "$MINIO_SECRET_KEY" 20
    fi
    if check_var_exists "MINIO_ENCRYPTION_KEY" "${MINIO_ENCRYPTION_KEY:-}"; then
        check_base64 "MINIO_ENCRYPTION_KEY" "$MINIO_ENCRYPTION_KEY"
    fi
    echo ""

    # Optional External Services
    print_header "External Services (Optional)"
    if [ -n "${RESEND_API_KEY:-}" ]; then
        if [[ "$RESEND_API_KEY" =~ ^re_[a-zA-Z0-9]+ ]]; then
            print_success "RESEND_API_KEY format OK"
        else
            print_warning "RESEND_API_KEY might be placeholder"
        fi
    else
        print_info "RESEND_API_KEY not configured (optional)"
    fi

    if [ -n "${SENTRY_DSN:-}" ]; then
        if [[ "$SENTRY_DSN" =~ ^https://[a-f0-9]+@[^/]+/[0-9]+$ ]]; then
            print_success "SENTRY_DSN format OK"
        else
            print_warning "SENTRY_DSN might be placeholder"
        fi
    else
        print_info "SENTRY_DSN not configured (optional)"
    fi
    echo ""
}

# Validate GitHub secrets
validate_github_secrets() {
    print_header "🔒 GitHub Actions Secrets Validator"
    print_header "════════════════════════════════════════"
    echo ""

    # Check if gh CLI is installed
    if ! command -v gh >/dev/null 2>&1; then
        print_error "GitHub CLI (gh) is not installed"
        print_info "Install with: brew install gh (Mac) or see https://cli.github.com"
        exit 1
    fi

    # Check if authenticated
    if ! gh auth status >/dev/null 2>&1; then
        print_error "Not authenticated with GitHub"
        print_info "Run: gh auth login"
        exit 1
    fi

    print_info "Checking GitHub repository secrets..."
    echo ""

    # Get list of secrets
    SECRETS=$(gh secret list --json name --jq '.[].name' 2>/dev/null || echo "")

    if [ -z "$SECRETS" ]; then
        print_error "No secrets found or unable to access repository"
        print_info "Make sure you're in the repository directory"
        exit 1
    fi

    # Required secrets for CI/CD
    REQUIRED_SECRETS=(
        "ENCRYPTION_MASTER_KEY"
        "DATABASE_URL"
        "POSTGRES_PASSWORD"
        "SECRET_KEY"
        "JWT_SECRET_KEY"
        "REDIS_PASSWORD"
        "MINIO_ACCESS_KEY"
        "MINIO_SECRET_KEY"
        "SSH_HOST"
        "SSH_USER"
        "SSH_PRIVATE_KEY"
    )

    # Optional secrets
    OPTIONAL_SECRETS=(
        "RESEND_API_KEY"
        "SENTRY_DSN"
        "DOCKER_REGISTRY_TOKEN"
    )

    print_header "Required Secrets"
    for secret in "${REQUIRED_SECRETS[@]}"; do
        if echo "$SECRETS" | grep -q "^$secret$"; then
            print_success "$secret is configured"
        else
            print_error "$secret is missing"
        fi
    done
    echo ""

    print_header "Optional Secrets"
    for secret in "${OPTIONAL_SECRETS[@]}"; do
        if echo "$SECRETS" | grep -q "^$secret$"; then
            print_success "$secret is configured"
        else
            print_info "$secret not configured (optional)"
        fi
    done
    echo ""
}

# Security checks
run_security_checks() {
    print_header "Security Checks"

    # Check if .env is in .gitignore
    if [ -f .gitignore ]; then
        if grep -q "^\.env$" .gitignore; then
            print_success ".env is in .gitignore"
        else
            print_error ".env is NOT in .gitignore - secrets could be committed!"
        fi
    else
        print_warning ".gitignore not found"
    fi

    # Check for hardcoded secrets in common files
    print_info "Scanning for potential hardcoded secrets..."

    suspicious_patterns=(
        "ENCRYPTION_MASTER_KEY=.+"
        "SECRET_KEY=[a-f0-9]{64}"
        "password\s*=\s*['\"][^'\"]{8,}"
        "api[_-]key\s*=\s*['\"][^'\"]{10,}"
    )

    for pattern in "${suspicious_patterns[@]}"; do
        if grep -r -E "$pattern" --include="*.py" --include="*.js" --include="*.ts" --exclude-dir=".git" --exclude-dir="node_modules" --exclude-dir=".venv" . 2>/dev/null | grep -v ".env.example"; then
            print_warning "Found potential hardcoded secret (pattern: $pattern)"
        fi
    done

    echo ""
}

# Main validation
main() {
    case "$CHECK_MODE" in
        file)
            validate_file_secrets
            run_security_checks
            ;;
        github)
            validate_github_secrets
            ;;
    esac

    # Summary
    print_header "Validation Summary"
    print_header "════════════════════════════════════════"

    if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        print_success "All checks passed! Your secrets are properly configured."
    elif [ $ERRORS -eq 0 ]; then
        print_warning "Validation completed with $WARNINGS warning(s)"
        echo "Review warnings above and fix if needed for production."
    else
        print_error "Validation failed with $ERRORS error(s) and $WARNINGS warning(s)"
        echo "Fix the errors above before deploying to production."
        exit 1
    fi
}

# Run main function
main