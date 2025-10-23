#!/bin/bash

# PazPaz GitHub Secrets Setup Script
# Automates the configuration of GitHub Secrets for CI/CD pipeline
#
# Requirements:
# - GitHub CLI (gh) installed and authenticated
# - Python 3 with cryptography library
# - OpenSSL
# - SSH client
#
# Usage: ./scripts/setup-github-secrets.sh [--production | --staging | --all]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SECRETS_FILE="${PROJECT_ROOT}/.github-secrets.env"  # Temporary file for secrets
REPO_OWNER="yussieik"
REPO_NAME="pazpaz"

# Logging
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

# Header
print_header() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           PazPaz GitHub Secrets Setup Wizard                ║"
    echo "║                    Version 1.0.0                            ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing_tools=()

    # Check gh CLI
    if ! command -v gh &> /dev/null; then
        missing_tools+=("gh (GitHub CLI)")
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    fi

    # Check OpenSSL
    if ! command -v openssl &> /dev/null; then
        missing_tools+=("openssl")
    fi

    # Check SSH
    if ! command -v ssh-keygen &> /dev/null; then
        missing_tools+=("ssh-keygen")
    fi

    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        echo ""
        echo "Installation instructions:"
        echo "  macOS:    brew install gh python3 openssl openssh"
        echo "  Ubuntu:   apt-get install gh python3 openssl openssh-client"
        echo ""
        exit 1
    fi

    # Check Python cryptography library
    if ! python3 -c "import cryptography" 2>/dev/null; then
        log_warning "Python cryptography library not installed"
        read -p "Install cryptography library? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            pip3 install cryptography || {
                log_error "Failed to install cryptography library"
                exit 1
            }
        else
            log_error "cryptography library is required for encryption key generation"
            exit 1
        fi
    fi

    # Check gh authentication
    if ! gh auth status &>/dev/null; then
        log_warning "GitHub CLI not authenticated"
        log_info "Running: gh auth login"
        gh auth login
    fi

    # Verify repository access
    if ! gh api "repos/${REPO_OWNER}/${REPO_NAME}" &>/dev/null; then
        log_error "Cannot access repository ${REPO_OWNER}/${REPO_NAME}"
        log_info "Make sure you have admin access to the repository"
        exit 1
    fi

    log_success "All prerequisites met"
}

# Generate encryption key
generate_encryption_key() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

# Generate secure password
generate_password() {
    local length="${1:-32}"
    openssl rand -base64 48 | tr -d '/+=' | cut -c1-"${length}"
}

# Generate hex key
generate_hex_key() {
    local bytes="${1:-32}"
    openssl rand -hex "${bytes}"
}

# Generate base64 key
generate_base64_key() {
    local bytes="${1:-32}"
    openssl rand -base64 "${bytes}"
}

# Check if secret exists
secret_exists() {
    local secret_name="$1"
    gh secret list | grep -q "^${secret_name}" 2>/dev/null
}

# Add or update secret
add_secret() {
    local name="$1"
    local value="$2"
    local description="${3:-}"

    if [ -z "$value" ]; then
        log_warning "Skipping ${name} (no value provided)"
        return
    fi

    if secret_exists "$name"; then
        log_info "Updating existing secret: ${name}"
    else
        log_info "Adding new secret: ${name}"
    fi

    if [ -n "$description" ]; then
        echo "  Description: ${description}"
    fi

    echo "$value" | gh secret set "$name" 2>/dev/null && {
        log_success "Secret ${name} configured"
    } || {
        log_error "Failed to set secret ${name}"
        return 1
    }
}

# Generate SSH deployment key
generate_ssh_key() {
    local key_file="${1:-pazpaz-deploy}"
    local key_comment="pazpaz-github-actions-$(date +%Y%m%d)"

    log_info "Generating SSH deployment key..."

    # Generate key
    ssh-keygen -t ed25519 -C "${key_comment}" -f "${key_file}" -N "" -q

    log_success "SSH key generated: ${key_file}"

    # Display public key
    echo ""
    echo "Public key (add to server's ~/.ssh/authorized_keys):"
    echo "────────────────────────────────────────────────────"
    cat "${key_file}.pub"
    echo "────────────────────────────────────────────────────"
    echo ""

    # Return private key content
    cat "${key_file}"
}

# Interactive mode: Collect required information
collect_secrets_interactive() {
    log_info "Starting interactive setup..."
    echo ""

    local secrets_env=""

    # Critical: Encryption key
    echo "═══════════════════════════════════════════════════════"
    echo "CRITICAL: PHI Encryption Key (HIPAA Required)"
    echo "═══════════════════════════════════════════════════════"
    log_warning "This key encrypts ALL patient data. Loss = permanent data loss!"
    echo ""
    read -p "Generate new encryption key? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ENCRYPTION_KEY=$(generate_encryption_key)
        secrets_env+="PROD_ENCRYPTION_MASTER_KEY=${ENCRYPTION_KEY}"$'\n'
        log_success "Encryption key generated"
        log_warning "SAVE THIS KEY IMMEDIATELY in a password manager!"
        echo "Key: ${ENCRYPTION_KEY}"
        read -p "Press Enter after you've saved the key..."
    else
        read -p "Enter existing encryption key: " ENCRYPTION_KEY
        secrets_env+="PROD_ENCRYPTION_MASTER_KEY=${ENCRYPTION_KEY}"$'\n'
    fi
    echo ""

    # Database credentials
    echo "═══════════════════════════════════════════════════════"
    echo "Database Configuration"
    echo "═══════════════════════════════════════════════════════"
    read -p "Generate new database password? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        DB_PASSWORD=$(generate_password)
        secrets_env+="PROD_POSTGRES_PASSWORD=${DB_PASSWORD}"$'\n'
        log_success "Database password generated"
    else
        read -sp "Enter database password: " DB_PASSWORD
        echo
        secrets_env+="PROD_POSTGRES_PASSWORD=${DB_PASSWORD}"$'\n'
    fi

    read -p "Database host [localhost]: " DB_HOST
    DB_HOST="${DB_HOST:-localhost}"

    read -p "Database port [5432]: " DB_PORT
    DB_PORT="${DB_PORT:-5432}"

    read -p "Database name [pazpaz]: " DB_NAME
    DB_NAME="${DB_NAME:-pazpaz}"

    DATABASE_URL="postgresql+asyncpg://pazpaz:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?ssl=require"
    secrets_env+="PROD_DATABASE_URL=${DATABASE_URL}"$'\n'
    echo ""

    # SSH deployment configuration
    echo "═══════════════════════════════════════════════════════"
    echo "SSH Deployment Configuration"
    echo "═══════════════════════════════════════════════════════"
    read -p "Production server IP or hostname: " SSH_HOST
    secrets_env+="SSH_HOST=${SSH_HOST}"$'\n'

    read -p "SSH username [deploy]: " SSH_USER
    SSH_USER="${SSH_USER:-deploy}"
    secrets_env+="SSH_USER=${SSH_USER}"$'\n'

    read -p "SSH port [22]: " SSH_PORT
    SSH_PORT="${SSH_PORT:-22}"
    secrets_env+="SSH_PORT=${SSH_PORT}"$'\n'

    read -p "Generate new SSH key? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SSH_KEY=$(generate_ssh_key "temp-deploy-key")
        secrets_env+="SSH_PRIVATE_KEY=${SSH_KEY}"$'\n'

        # Test SSH connection
        log_info "Testing SSH connection..."
        if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
           -i "temp-deploy-key" -p "${SSH_PORT}" \
           "${SSH_USER}@${SSH_HOST}" "echo 'SSH test successful'" 2>/dev/null; then
            log_success "SSH connection successful"
        else
            log_warning "SSH connection failed. Make sure to add the public key to the server"
        fi

        # Clean up temp key
        shred -vfz "temp-deploy-key" 2>/dev/null || rm -f "temp-deploy-key"
        rm -f "temp-deploy-key.pub"
    else
        echo "Paste the SSH private key (press Ctrl+D when done):"
        SSH_KEY=$(cat)
        secrets_env+="SSH_PRIVATE_KEY=${SSH_KEY}"$'\n'
    fi
    echo ""

    # Application secrets
    echo "═══════════════════════════════════════════════════════"
    echo "Application Secrets"
    echo "═══════════════════════════════════════════════════════"
    log_info "Generating application secrets..."

    secrets_env+="PROD_SECRET_KEY=$(generate_hex_key)"$'\n'
    secrets_env+="PROD_JWT_SECRET_KEY=$(generate_base64_key)"$'\n'
    secrets_env+="PROD_CSRF_SECRET_KEY=$(generate_base64_key)"$'\n'
    secrets_env+="PROD_REDIS_PASSWORD=$(generate_password)"$'\n'

    log_success "Application secrets generated"
    echo ""

    # MinIO/S3 configuration
    echo "═══════════════════════════════════════════════════════"
    echo "MinIO/S3 Object Storage"
    echo "═══════════════════════════════════════════════════════"
    read -p "Configure MinIO/S3 storage? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        secrets_env+="PROD_MINIO_ACCESS_KEY=$(generate_password 16)"$'\n'
        secrets_env+="PROD_MINIO_SECRET_KEY=$(generate_password 32)"$'\n'
        log_success "MinIO credentials generated"
    fi
    echo ""

    # External services
    echo "═══════════════════════════════════════════════════════"
    echo "External Services (Optional)"
    echo "═══════════════════════════════════════════════════════"

    read -p "Configure Resend email service? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter Resend API key: " RESEND_KEY
        if [ -n "$RESEND_KEY" ]; then
            secrets_env+="PROD_RESEND_API_KEY=${RESEND_KEY}"$'\n'
        fi
    fi

    read -p "Configure Sentry error tracking? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter Sentry DSN: " SENTRY_DSN
        if [ -n "$SENTRY_DSN" ]; then
            secrets_env+="PROD_SENTRY_DSN=${SENTRY_DSN}"$'\n'
        fi
    fi
    echo ""

    # Save to temporary file
    echo "$secrets_env" > "$SECRETS_FILE"
    log_success "Secrets collected and saved to temporary file"
}

# Upload secrets to GitHub
upload_secrets() {
    log_info "Uploading secrets to GitHub..."
    echo ""

    if [ ! -f "$SECRETS_FILE" ]; then
        log_error "Secrets file not found: $SECRETS_FILE"
        return 1
    fi

    local total=0
    local success=0
    local failed=0

    # Parse secrets file and upload
    while IFS='=' read -r name value; do
        if [ -n "$name" ] && [ -n "$value" ]; then
            ((total++))
            if add_secret "$name" "$value"; then
                ((success++))
            else
                ((failed++))
            fi
        fi
    done < "$SECRETS_FILE"

    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "Upload Summary:"
    echo "  Total:      ${total}"
    echo "  Success:    ${success}"
    echo "  Failed:     ${failed}"
    echo "═══════════════════════════════════════════════════════"

    if [ $failed -eq 0 ]; then
        log_success "All secrets uploaded successfully!"
    else
        log_warning "Some secrets failed to upload. Please check and retry."
    fi
}

# Validate secrets
validate_secrets() {
    log_info "Validating configured secrets..."
    echo ""

    local required_secrets=(
        "PROD_ENCRYPTION_MASTER_KEY"
        "PROD_DATABASE_URL"
        "PROD_POSTGRES_PASSWORD"
        "SSH_PRIVATE_KEY"
        "SSH_HOST"
        "SSH_USER"
        "PROD_SECRET_KEY"
        "PROD_JWT_SECRET_KEY"
    )

    local missing=()

    for secret in "${required_secrets[@]}"; do
        if secret_exists "$secret"; then
            echo "  ✅ ${secret}"
        else
            echo "  ❌ ${secret} (missing)"
            missing+=("$secret")
        fi
    done

    echo ""
    if [ ${#missing[@]} -eq 0 ]; then
        log_success "All required secrets are configured!"
    else
        log_error "Missing required secrets: ${missing[*]}"
        return 1
    fi
}

# Test SSH connection
test_ssh_connection() {
    log_info "Testing SSH connection..."

    # Create temporary workflow for testing
    local workflow_file=".github/workflows/test-ssh.yml"

    cat > "$workflow_file" <<'EOF'
name: Test SSH Connection
on: workflow_dispatch

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Test SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          port: ${{ secrets.SSH_PORT }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            echo "✅ SSH connection successful"
            echo "Hostname: $(hostname)"
            echo "User: $(whoami)"
EOF

    # Trigger workflow
    if gh workflow run test-ssh.yml; then
        log_success "SSH test workflow triggered. Check GitHub Actions for results."
    else
        log_error "Failed to trigger SSH test workflow"
    fi

    # Clean up
    rm -f "$workflow_file"
}

# Clean up sensitive files
cleanup() {
    log_info "Cleaning up sensitive files..."

    if [ -f "$SECRETS_FILE" ]; then
        shred -vfz "$SECRETS_FILE" 2>/dev/null || rm -f "$SECRETS_FILE"
        log_success "Temporary secrets file removed"
    fi

    # Clear bash history
    history -c 2>/dev/null || true
}

# Main menu
main_menu() {
    echo "Select an option:"
    echo ""
    echo "  1) Complete setup (interactive)"
    echo "  2) Validate existing secrets"
    echo "  3) Test SSH connection"
    echo "  4) Upload secrets from file"
    echo "  5) Generate secrets only (no upload)"
    echo "  6) Exit"
    echo ""
    read -p "Enter choice [1-6]: " choice

    case $choice in
        1)
            collect_secrets_interactive
            upload_secrets
            validate_secrets
            cleanup
            ;;
        2)
            validate_secrets
            ;;
        3)
            test_ssh_connection
            ;;
        4)
            read -p "Enter secrets file path: " secrets_file
            SECRETS_FILE="$secrets_file"
            upload_secrets
            ;;
        5)
            collect_secrets_interactive
            log_info "Secrets saved to: $SECRETS_FILE"
            log_warning "Remember to upload them to GitHub and then delete the file!"
            ;;
        6)
            echo "Exiting..."
            cleanup
            exit 0
            ;;
        *)
            log_error "Invalid choice"
            main_menu
            ;;
    esac
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# Main execution
main() {
    print_header
    check_prerequisites

    # Check command line arguments
    case "${1:-}" in
        --validate)
            validate_secrets
            ;;
        --test-ssh)
            test_ssh_connection
            ;;
        --help)
            echo "Usage: $0 [--validate|--test-ssh|--help]"
            echo ""
            echo "Options:"
            echo "  --validate    Validate existing secrets"
            echo "  --test-ssh    Test SSH connection"
            echo "  --help        Show this help message"
            echo ""
            echo "Without options, runs interactive setup wizard."
            ;;
        *)
            main_menu
            ;;
    esac

    echo ""
    log_info "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Verify secrets in GitHub: https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/secrets/actions"
    echo "  2. Test deployment workflow: gh workflow run deploy-production.yml"
    echo "  3. Document secret rotation schedule"
    echo "  4. Set up secret backup in password manager"
    echo ""
}

# Run main function
main "$@"