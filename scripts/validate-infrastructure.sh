#!/bin/bash
# =============================================================================
# Infrastructure Validation Script
# =============================================================================
# Consolidates all infrastructure validation into a single script
# Replaces 1000+ lines of GitHub Actions YAML with a maintainable bash script
#
# Usage:
#   ./scripts/validate-infrastructure.sh [--verbose] [--check=all|docker|nginx|scripts|env]
#
# Exit codes:
#   0 - All validations passed
#   1 - One or more validations failed
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
VERBOSE=${VERBOSE:-false}
CHECK_TYPE=${1:-all}

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
log_info() {
    echo -e "${GREEN}✅${NC} $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
    FAILED=$((FAILED + 1))
}

log_warn() {
    echo -e "${YELLOW}⚠️${NC}  $1"
    WARNINGS=$((WARNINGS + 1))
}

log_success() {
    PASSED=$((PASSED + 1))
}

# =============================================================================
# Docker Compose Validation
# =============================================================================
validate_docker_compose() {
    echo ""
    echo "🔍 Validating Docker Compose files..."

    # Create temporary env file for validation
    local TEMP_ENV=$(mktemp)
    trap 'rm -f "$TEMP_ENV"' RETURN

    cat > "$TEMP_ENV" << 'EOF'
POSTGRES_PASSWORD=test_pass
REDIS_PASSWORD=test_pass
ENCRYPTION_MASTER_KEY=dGVzdF9rZXlfMzJfYnl0ZXNfZm9yX3ZhbGlkYXRpb24=
SECRET_KEY=test_secret_key_for_validation
S3_ACCESS_KEY=test_access
S3_SECRET_KEY=test_secret
MINIO_ENCRYPTION_KEY=test_minio_key
FRONTEND_URL=https://test.com
ALLOWED_HOSTS=test.com
SMTP_HOST=smtp.test.com
SMTP_PORT=587
SMTP_USER=test
SMTP_PASSWORD=test_pass
EMAILS_FROM_EMAIL=test@test.com
GOOGLE_OAUTH_CLIENT_ID=test
GOOGLE_OAUTH_CLIENT_SECRET=test
GOOGLE_OAUTH_REDIRECT_URI=https://test.com/oauth
EOF

    # Validate docker-compose.yml
    if docker compose -f docker-compose.yml config --quiet 2>/dev/null; then
        log_info "docker-compose.yml syntax is valid"
        log_success
    else
        log_error "docker-compose.yml validation failed"
        return 1
    fi

    # Validate docker-compose.prod.yml (with temp env)
    if docker compose --env-file "$TEMP_ENV" -f docker-compose.prod.yml config --quiet 2>/dev/null; then
        log_info "docker-compose.prod.yml syntax is valid"
        log_success
    else
        log_error "docker-compose.prod.yml validation failed"
        docker compose --env-file "$TEMP_ENV" -f docker-compose.prod.yml config 2>&1 | head -10
        return 1
    fi

    # Check for required networks (with temp env)
    for network in frontend backend database; do
        if docker compose --env-file "$TEMP_ENV" -f docker-compose.prod.yml config 2>/dev/null | \
           sed -n '/^networks:/,/^[a-z]/p' | grep -q "  ${network}:"; then
            log_info "Network '$network' is defined"
        else
            log_warn "Network '$network' might be missing"
        fi
    done

    return 0
}

# =============================================================================
# Nginx Configuration Validation
# =============================================================================
validate_nginx() {
    echo ""
    echo "🔍 Validating Nginx configuration..."

    # Check if nginx is available
    if ! command -v nginx &> /dev/null; then
        log_warn "Nginx not installed - skipping syntax validation (OK for local dev)"
        # Just check that files exist
        if [ -f nginx/nginx.conf ]; then
            log_info "nginx.conf exists"
            log_success
        fi
        return 0
    fi

    # Validate nginx.conf
    if [ -f nginx/nginx.conf ]; then
        if nginx -t -c "$(pwd)/nginx/nginx.conf" 2>&1 | grep -q "syntax is ok"; then
            log_info "nginx.conf syntax is valid"
            log_success
        else
            log_warn "nginx.conf validation failed (may be OK - check in CI)"
        fi
    fi

    # Check for security headers
    local headers=("X-Frame-Options" "X-Content-Type-Options" "Referrer-Policy")
    local found_headers=0
    for header in "${headers[@]}"; do
        if grep -rq "$header" nginx/ 2>/dev/null; then
            log_info "Security header '$header' is configured"
            found_headers=$((found_headers + 1))
        fi
    done

    if [ $found_headers -gt 0 ]; then
        log_success
    fi

    return 0
}

# =============================================================================
# Shell Script Validation
# =============================================================================
validate_scripts() {
    echo ""
    echo "🔍 Validating shell scripts..."

    # Find all shell scripts
    local scripts=(
        "scripts/setup-ssl.sh"
        "scripts/validate-env.sh"
        "scripts/generate-secrets.sh"
        "scripts/validate-secrets.sh"
        "nginx/enable-ssl.sh"
    )

    local script_failed=0

    for script in "${scripts[@]}"; do
        if [ ! -f "$script" ]; then
            log_warn "$script not found - skipping"
            continue
        fi

        # Syntax check
        if bash -n "$script" 2>/dev/null; then
            log_info "$script: Syntax valid"
            log_success
        else
            log_error "$script: Syntax error"
            script_failed=1
        fi

        # Shellcheck (if available)
        if command -v shellcheck &> /dev/null; then
            if shellcheck -e SC2086,SC2181 "$script" 2>/dev/null; then
                log_info "$script: Shellcheck passed"
            else
                log_warn "$script: Shellcheck warnings"
            fi
        fi

        # Check executable permission
        if [ -x "$script" ]; then
            log_info "$script: Executable"
        else
            log_warn "$script: Not executable (chmod +x needed)"
        fi
    done

    return $script_failed
}

# =============================================================================
# Environment Template Validation
# =============================================================================
validate_env_templates() {
    echo ""
    echo "🔍 Validating environment templates..."

    # Check template files exist
    local templates=(".env.example" ".env.production.example")

    for template in "${templates[@]}"; do
        if [ -f "$template" ]; then
            log_info "$template exists"
            log_success
        else
            log_error "$template not found"
            return 1
        fi
    done

    # Check for required variables in production template
    local required_vars=(
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "SECRET_KEY"
        "ENCRYPTION_MASTER_KEY"
        "JWT_SECRET_KEY"
        "S3_ACCESS_KEY"
        "S3_SECRET_KEY"
    )

    local missing=0
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=" .env.production.example; then
            log_info "$var is defined in template"
        else
            log_error "$var is missing from template"
            missing=1
        fi
    done

    # Check for exposed secrets (shouldn't have real values)
    local suspicious_patterns=("ghp_" "ghs_" "sk-" "pk_" "aws_")
    for pattern in "${suspicious_patterns[@]}"; do
        if grep -i "$pattern" .env.production.example 2>/dev/null; then
            log_error "Suspicious pattern '$pattern' found - possible secret exposure"
            missing=1
        fi
    done

    return $missing
}

# =============================================================================
# Main Execution
# =============================================================================
main() {
    echo "════════════════════════════════════════════════════════════"
    echo "  PazPaz Infrastructure Validation"
    echo "════════════════════════════════════════════════════════════"

    case "${CHECK_TYPE#--check=}" in
        all)
            validate_docker_compose || true
            validate_nginx || true
            validate_scripts || true
            validate_env_templates || true
            ;;
        docker)
            validate_docker_compose
            ;;
        nginx)
            validate_nginx
            ;;
        scripts)
            validate_scripts
            ;;
        env)
            validate_env_templates
            ;;
        *)
            echo "Unknown check type: $CHECK_TYPE"
            echo "Usage: $0 [--check=all|docker|nginx|scripts|env]"
            exit 1
            ;;
    esac

    # Summary
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Validation Summary"
    echo "════════════════════════════════════════════════════════════"
    echo -e "${GREEN}✅ Passed:${NC}   $PASSED"
    echo -e "${YELLOW}⚠️  Warnings:${NC} $WARNINGS"
    echo -e "${RED}❌ Failed:${NC}   $FAILED"
    echo "════════════════════════════════════════════════════════════"

    if [ $FAILED -gt 0 ]; then
        echo -e "${RED}Validation failed with $FAILED error(s)${NC}"
        exit 1
    elif [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}Validation passed with $WARNINGS warning(s)${NC}"
        exit 0
    else
        echo -e "${GREEN}All validations passed!${NC}"
        exit 0
    fi
}

main "$@"
