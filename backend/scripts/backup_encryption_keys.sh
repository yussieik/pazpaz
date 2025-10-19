#!/bin/bash
# scripts/backup_encryption_keys.sh
# Daily automated backup of encryption keys to offline storage
#
# Usage:
#   ./scripts/backup_encryption_keys.sh [--dry-run] [--region REGION]
#
# Requirements:
#   - AWS CLI configured with appropriate credentials
#   - GPG installed with security@pazpaz.com public key imported
#   - Write access to backup directory
#
# HIPAA Compliance: §164.308(a)(7)(ii)(A) - Data Backup Plan

set -euo pipefail

# Configuration
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/secure/backups/encryption-keys}"
AWS_REGION="${AWS_REGION:-us-east-1}"
GPG_RECIPIENT="${GPG_RECIPIENT:-security@pazpaz.com}"
SECRET_PREFIX="pazpaz/encryption-key-"
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --gpg-recipient)
            GPG_RECIPIENT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run              Simulate backup without creating files"
            echo "  --region REGION        AWS region (default: us-east-1)"
            echo "  --backup-dir DIR       Backup directory (default: /secure/backups/encryption-keys)"
            echo "  --gpg-recipient EMAIL  GPG recipient (default: security@pazpaz.com)"
            echo "  -h, --help            Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  BACKUP_DIR            Backup directory path"
            echo "  AWS_REGION            AWS region"
            echo "  GPG_RECIPIENT         GPG recipient email"
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verify prerequisites
verify_prerequisites() {
    log_info "Verifying prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not installed. Install with: pip install awscli"
        exit 1
    fi

    # Check GPG
    if ! command -v gpg &> /dev/null; then
        log_error "GPG not installed. Install with: brew install gnupg (macOS) or apt-get install gnupg (Linux)"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run: aws configure"
        exit 1
    fi

    # Check GPG public key
    if ! gpg --list-keys "$GPG_RECIPIENT" &> /dev/null; then
        log_error "GPG public key for $GPG_RECIPIENT not found."
        log_error "Import key with: gpg --import gpg-public-key.asc"
        exit 1
    fi

    log_success "All prerequisites verified"
}

# Create backup directory
create_backup_directory() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create backup directory: $BACKUP_DIR"
        return
    fi

    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_info "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi

    cd "$BACKUP_DIR"
    log_success "Working directory: $BACKUP_DIR"
}

# Fetch secrets from AWS Secrets Manager
fetch_secrets() {
    log_info "Fetching encryption key secrets from AWS Secrets Manager..."
    log_info "Region: $AWS_REGION"
    log_info "Prefix: $SECRET_PREFIX"

    # List all secrets with prefix
    SECRETS=$(aws secretsmanager list-secrets \
        --region "$AWS_REGION" \
        --filters Key=name,Values="$SECRET_PREFIX" \
        --query 'SecretList[].Name' \
        --output text 2>&1)

    if [[ $? -ne 0 ]]; then
        log_error "Failed to list secrets from AWS Secrets Manager"
        log_error "$SECRETS"
        exit 1
    fi

    if [[ -z "$SECRETS" ]]; then
        log_warning "No encryption key secrets found with prefix: $SECRET_PREFIX"
        exit 0
    fi

    log_success "Found secrets to backup"
}

# Backup single secret
backup_secret() {
    local SECRET_NAME=$1
    local VERSION=$(echo "$SECRET_NAME" | sed "s|$SECRET_PREFIX||")

    log_info "📦 Backing up: $SECRET_NAME (version: $VERSION)"

    # Fetch secret value
    SECRET_VALUE=$(aws secretsmanager get-secret-value \
        --region "$AWS_REGION" \
        --secret-id "$SECRET_NAME" \
        --query SecretString \
        --output text 2>&1)

    if [[ $? -ne 0 ]]; then
        log_error "   Failed to fetch secret: $SECRET_NAME"
        log_error "   $SECRET_VALUE"
        return 1
    fi

    # Create backup filename
    BACKUP_FILE="encryption-key-${VERSION}-backup-${DATE}.json"
    ENCRYPTED_FILE="${BACKUP_FILE}.gpg"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "   [DRY RUN] Would create: $ENCRYPTED_FILE"
        return 0
    fi

    # Save secret to temporary file
    echo "$SECRET_VALUE" > "$BACKUP_FILE"

    # Encrypt with GPG
    gpg --encrypt \
        --recipient "$GPG_RECIPIENT" \
        --armor \
        --trust-model always \
        --output "$ENCRYPTED_FILE" \
        "$BACKUP_FILE" 2>&1

    if [[ $? -ne 0 ]]; then
        log_error "   GPG encryption failed for: $BACKUP_FILE"
        rm -f "$BACKUP_FILE"
        return 1
    fi

    # Securely delete plaintext (10 passes)
    shred -vfz -n 10 "$BACKUP_FILE" 2>&1 | grep -v "shred:"

    log_success "   ✅ Encrypted backup: $ENCRYPTED_FILE"

    return 0
}

# Generate backup manifest
generate_manifest() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would generate backup manifest"
        return
    fi

    local MANIFEST_FILE="BACKUP_MANIFEST_${DATE}.txt"

    cat > "$MANIFEST_FILE" <<EOF
Encryption Key Backup Manifest
Generated: $DATE
Backup Directory: $BACKUP_DIR
AWS Region: $AWS_REGION

Keys Backed Up:
$(ls -lh *.gpg 2>/dev/null || echo "No backup files found")

Storage Instructions:
1. Copy all .gpg files to encrypted USB drive
2. Label USB: "PazPaz Encryption Keys - $DATE"
3. Store in fireproof safe (Location A: Office safe)
4. Maintain 3 most recent backups, archive older backups to Location B (bank vault)

Recovery Contact:
Security Team: security@pazpaz.com

HIPAA Compliance:
- Backup created per §164.308(a)(7)(ii)(A)
- Retention period: 90 days (active), 1 year (archived), 7 years (Glacier)
- Encryption: GPG with 4096-bit RSA key
EOF

    log_success "📄 Manifest created: $MANIFEST_FILE"
}

# Main execution
main() {
    echo ""
    echo "🔐 PazPaz Encryption Key Backup"
    echo "================================"
    echo ""

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "DRY RUN MODE - No files will be created"
        echo ""
    fi

    verify_prerequisites
    create_backup_directory
    fetch_secrets

    echo ""
    log_info "Starting backup process..."
    echo ""

    BACKUP_COUNT=0
    FAILED_COUNT=0

    for SECRET_NAME in $SECRETS; do
        if backup_secret "$SECRET_NAME"; then
            ((BACKUP_COUNT++))
        else
            ((FAILED_COUNT++))
        fi
    done

    echo ""
    echo "================================"
    echo "✅ Backup Complete!"
    echo "================================"
    echo ""
    echo "Summary:"
    echo "  Keys backed up: $BACKUP_COUNT"
    echo "  Failed backups: $FAILED_COUNT"
    echo "  Backup directory: $BACKUP_DIR"
    echo "  AWS region: $AWS_REGION"
    echo "  GPG recipient: $GPG_RECIPIENT"
    echo ""

    if [[ "$DRY_RUN" == "false" ]]; then
        generate_manifest

        echo ""
        echo "📋 Next Steps:"
        echo "  1. Copy encrypted backups to USB drive:"
        echo "     cp $BACKUP_DIR/*.gpg /media/usb/"
        echo ""
        echo "  2. Store USB in fireproof safe (Location A)"
        echo ""
        echo "  3. Update backup log:"
        echo "     echo '$DATE - $BACKUP_COUNT keys backed up' >> /secure/backups/BACKUP_LOG.txt"
        echo ""
        echo "  4. Verify backups (recommended):"
        echo "     ./scripts/verify_backup.sh"
        echo ""
    fi

    # Exit with error if any backups failed
    if [[ $FAILED_COUNT -gt 0 ]]; then
        log_error "Some backups failed. Review errors above."
        exit 1
    fi

    exit 0
}

# Run main function
main
