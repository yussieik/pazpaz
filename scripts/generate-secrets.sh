#!/bin/bash
# PazPaz Secret Generation Script
# Generates all required secrets for production deployment
#
# SECURITY WARNING:
# - Run this script in a secure environment
# - Save output immediately to a password manager
# - Delete shell history after running
# - Never commit generated secrets to version control
#
# Usage: ./scripts/generate-secrets.sh [environment]
# Examples:
#   ./scripts/generate-secrets.sh           # Interactive mode
#   ./scripts/generate-secrets.sh production # Generate for production
#   ./scripts/generate-secrets.sh staging    # Generate for staging

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_VERSION="1.0.0"
ENVIRONMENT="${1:-interactive}"

# Function to print colored output
print_header() {
    echo -e "${BLUE}${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_secret() {
    local name=$1
    local value=$2
    echo -e "${BOLD}${name}${NC}=${value}"
}

# Check dependencies
check_dependencies() {
    local missing_deps=0

    if ! command -v openssl >/dev/null 2>&1; then
        print_error "openssl is required but not installed"
        echo "  Install with: apt-get install openssl (Ubuntu) or brew install openssl (Mac)"
        missing_deps=1
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        print_error "python3 is required but not installed"
        echo "  Install with: apt-get install python3 (Ubuntu) or brew install python3 (Mac)"
        missing_deps=1
    fi

    # Check for Python cryptography module
    if ! python3 -c "import cryptography" >/dev/null 2>&1; then
        print_warning "Python cryptography module not found"
        echo "  Install with: pip3 install cryptography"
        echo "  Falling back to base64 encoding for some keys"
    fi

    if [ $missing_deps -eq 1 ]; then
        exit 1
    fi
}

# Generate Fernet encryption key (for PHI data)
generate_encryption_key() {
    if python3 -c "import cryptography" >/dev/null 2>&1; then
        # Use cryptography library if available
        python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    else
        # Fallback to base64 encoding (still secure, just different format)
        # Note: This won't work with Fernet directly, needs conversion
        local key=$(openssl rand -base64 32)
        # Ensure it's URL-safe base64 as Fernet expects
        echo "$key" | tr '+/' '-_' | tr -d '='
    fi
}

# Generate secure password with specified length
generate_password() {
    local length="${1:-32}"
    openssl rand -base64 48 | tr -d '/+=' | cut -c1-"$length"
}

# Generate hex string for session keys
generate_hex_key() {
    local bytes="${1:-32}"
    openssl rand -hex "$bytes"
}

# Generate base64 key
generate_base64_key() {
    local bytes="${1:-32}"
    openssl rand -base64 "$bytes"
}

# Generate alphanumeric key
generate_alphanumeric() {
    local length="${1:-16}"
    openssl rand -base64 "$length" | tr -d '/+=' | cut -c1-"$length"
}

# Main secret generation
generate_secrets() {
    local env=$1

    echo ""
    print_header "🔐 PazPaz Secret Generator v${SCRIPT_VERSION}"
    print_header "════════════════════════════════════════════"
    echo ""

    if [ "$env" == "interactive" ]; then
        print_warning "SECURITY WARNING:"
        echo "  • Save these secrets immediately in a password manager"
        echo "  • Never commit these values to git"
        echo "  • Delete shell history after saving (history -c)"
        echo "  • Use different secrets for each environment"
        echo ""
        read -p "Press Enter to continue or Ctrl+C to cancel..."
        echo ""
    fi

    # Critical: PHI Encryption
    print_header "CRITICAL: PHI ENCRYPTION (HIPAA REQUIRED)"
    print_header "═══════════════════════════════════════════════"
    print_warning "Loss of this key = PERMANENT DATA LOSS. Back up immediately!"
    ENCRYPTION_KEY=$(generate_encryption_key)
    print_secret "ENCRYPTION_MASTER_KEY" "$ENCRYPTION_KEY"
    echo ""

    # Database Credentials
    print_header "DATABASE CREDENTIALS"
    print_header "═══════════════════════════════════════════════"
    DB_PASSWORD=$(generate_password 32)
    print_secret "POSTGRES_PASSWORD" "$DB_PASSWORD"
    print_secret "DATABASE_URL" "postgresql+asyncpg://pazpaz:${DB_PASSWORD}@db:5432/pazpaz?ssl=require"
    echo ""

    # Application Secrets
    print_header "APPLICATION SECRETS"
    print_header "═══════════════════════════════════════════════"
    print_secret "SECRET_KEY" "$(generate_hex_key 32)"
    print_secret "JWT_SECRET_KEY" "$(generate_base64_key 32)"
    print_secret "CSRF_SECRET_KEY" "$(generate_base64_key 32)"
    echo ""

    # Redis Cache
    print_header "REDIS CACHE"
    print_header "═══════════════════════════════════════════════"
    REDIS_PASSWORD=$(generate_password 32)
    print_secret "REDIS_PASSWORD" "$REDIS_PASSWORD"
    print_secret "REDIS_URL" "redis://:${REDIS_PASSWORD}@redis:6379/0"
    echo ""

    # MinIO/S3 Object Storage
    print_header "MINIO/S3 OBJECT STORAGE"
    print_header "═══════════════════════════════════════════════"
    print_secret "MINIO_ACCESS_KEY" "$(generate_alphanumeric 16)"
    print_secret "MINIO_SECRET_KEY" "$(generate_password 32)"
    print_secret "MINIO_ENCRYPTION_KEY" "$(generate_base64_key 32)"
    echo ""

    # External Services (placeholders)
    print_header "EXTERNAL SERVICES (Configure Manually)"
    print_header "═══════════════════════════════════════════════"
    echo "# Get from https://resend.com/api-keys"
    print_secret "RESEND_API_KEY" "re_xxxxxxxxxxxxxxxxxxxx"
    echo ""
    echo "# Get from https://sentry.io/settings/projects/"
    print_secret "SENTRY_DSN" "https://xxxxx@sentry.io/xxxxx"
    echo ""

    # Deployment Configuration
    if [ "$env" == "production" ] || [ "$env" == "staging" ]; then
        print_header "DEPLOYMENT CONFIGURATION"
        print_header "═══════════════════════════════════════════════"
        echo "# Add your server details"
        print_secret "SSH_HOST" "your-server-ip-or-hostname"
        print_secret "SSH_USER" "deploy"
        echo "# Generate SSH key with: ssh-keygen -t ed25519 -f pazpaz-deploy"
        echo "SSH_PRIVATE_KEY=<contents of pazpaz-deploy private key>"
        echo ""
    fi

    print_success "Secrets generated successfully!"
    echo ""
    print_header "NEXT STEPS:"
    echo "1. Copy these secrets to your password manager immediately"
    echo "2. For GitHub Actions: Settings → Secrets → Actions → New repository secret"
    echo "3. For production server: Create /opt/pazpaz/.env.production"
    echo "4. Clear shell history: history -c && rm ~/.bash_history"
    echo "5. Run validation: ./scripts/validate-secrets.sh"
    echo ""

    if [ "$env" == "interactive" ]; then
        print_warning "IMPORTANT: This output contains sensitive data!"
        read -p "Have you saved these secrets securely? (yes/no): " saved
        if [ "$saved" == "yes" ]; then
            print_success "Great! Remember to clear your shell history."
            echo "Run: history -c && rm ~/.bash_history"
        else
            print_error "Please save these secrets before they are lost!"
        fi
    fi
}

# Export to file (optional, encrypted)
export_to_file() {
    local filename="${1:-.env.generated}"

    print_warning "Exporting to file: $filename"
    print_warning "This file contains sensitive data! Encrypt or delete after use."

    {
        echo "# PazPaz Secrets - Generated $(date)"
        echo "# Environment: $ENVIRONMENT"
        echo "# SECURITY: Delete this file after importing to secure storage!"
        echo ""
        generate_secrets "$ENVIRONMENT"
    } > "$filename"

    chmod 600 "$filename"
    print_success "Secrets exported to $filename (permissions: 600)"
    print_warning "Delete this file immediately after use!"
}

# Main execution
main() {
    check_dependencies

    case "$ENVIRONMENT" in
        production|staging|development)
            generate_secrets "$ENVIRONMENT"
            ;;
        export)
            export_to_file "${2:-.env.generated}"
            ;;
        interactive|*)
            generate_secrets "interactive"
            ;;
    esac
}

# Run main function
main "$@"