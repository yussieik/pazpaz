#!/bin/bash
# scripts/restore_encryption_keys.sh
# Recover encryption keys from GPG-encrypted offline backups
#
# Usage:
#   ./scripts/restore_encryption_keys.sh [--dry-run] [--backup-dir DIR] [--restore-to-aws]
#
# Requirements:
#   - GPG installed with security@pazpaz.com private key imported
#   - GPG private key passphrase (prompted during decryption)
#   - AWS CLI configured (if --restore-to-aws flag used)
#
# HIPAA Compliance: §164.308(a)(7)(ii)(B) - Disaster Recovery Plan

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/secure/backups/encryption-keys}"
RESTORE_DIR="${RESTORE_DIR:-/secure/restored-keys}"
AWS_REGION="${AWS_REGION:-us-east-1}"
DRY_RUN=false
RESTORE_TO_AWS=false
VERIFY_INTEGRITY=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --restore-dir)
            RESTORE_DIR="$2"
            shift 2
            ;;
        --restore-to-aws)
            RESTORE_TO_AWS=true
            shift
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --no-verify)
            VERIFY_INTEGRITY=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run              Simulate restore without creating files"
            echo "  --backup-dir DIR       Backup directory (default: /secure/backups/encryption-keys)"
            echo "  --restore-dir DIR      Restore directory (default: /secure/restored-keys)"
            echo "  --restore-to-aws       Upload restored keys to AWS Secrets Manager"
            echo "  --region REGION        AWS region for upload (default: us-east-1)"
            echo "  --no-verify            Skip integrity verification"
            echo "  -h, --help            Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  BACKUP_DIR            Backup directory path"
            echo "  RESTORE_DIR           Restore directory path"
            echo "  AWS_REGION            AWS region"
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

log_step() {
    echo -e "${CYAN}$1${NC}"
}

# Verify prerequisites
verify_prerequisites() {
    log_info "Verifying prerequisites..."

    # Check GPG
    if ! command -v gpg &> /dev/null; then
        log_error "GPG not installed. Install with: brew install gnupg (macOS) or apt-get install gnupg (Linux)"
        exit 1
    fi

    # Check GPG private key
    if ! gpg --list-secret-keys security@pazpaz.com &> /dev/null; then
        log_error "GPG private key for security@pazpaz.com not found."
        log_error ""
        log_error "Import private key with:"
        log_error "  1. Retrieve gpg-private-key.asc from password manager or secure storage"
        log_error "  2. gpg --import gpg-private-key.asc"
        log_error "  3. gpg --edit-key security@pazpaz.com"
        log_error "     gpg> trust"
        log_error "     Your decision? 5 (ultimate trust)"
        log_error "     gpg> quit"
        exit 1
    fi

    # Check AWS CLI if --restore-to-aws
    if [[ "$RESTORE_TO_AWS" == "true" ]]; then
        if ! command -v aws &> /dev/null; then
            log_error "AWS CLI not installed (required for --restore-to-aws)"
            exit 1
        fi

        if ! aws sts get-caller-identity &> /dev/null; then
            log_error "AWS credentials not configured. Run: aws configure"
            exit 1
        fi
    fi

    # Check backup directory
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_error "Backup directory does not exist: $BACKUP_DIR"
        exit 1
    fi

    # Check for encrypted backup files
    if ! ls "$BACKUP_DIR"/encryption-key-*.gpg &> /dev/null; then
        log_error "No encrypted backup files found in: $BACKUP_DIR"
        log_error "Expected files: encryption-key-*.gpg"
        exit 1
    fi

    log_success "All prerequisites verified"
}

# Create restore directory
create_restore_directory() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create restore directory: $RESTORE_DIR"
        return
    fi

    if [[ ! -d "$RESTORE_DIR" ]]; then
        log_info "Creating restore directory: $RESTORE_DIR"
        mkdir -p "$RESTORE_DIR"
    fi

    log_success "Restore directory ready: $RESTORE_DIR"
}

# Decrypt single backup file
decrypt_backup() {
    local ENCRYPTED_FILE=$1
    local FILENAME=$(basename "$ENCRYPTED_FILE")

    # Extract base filename (remove .gpg)
    local DECRYPTED_FILE="${FILENAME%.gpg}"

    log_info "📂 Decrypting: $FILENAME"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "   [DRY RUN] Would decrypt to: $RESTORE_DIR/$DECRYPTED_FILE"
        return 0
    fi

    # Decrypt with GPG (prompts for passphrase if needed)
    if ! gpg --decrypt \
        --quiet \
        --output "$RESTORE_DIR/$DECRYPTED_FILE" \
        "$ENCRYPTED_FILE" 2>&1; then
        log_error "   Failed to decrypt: $FILENAME"
        log_error "   Possible causes:"
        log_error "     - Incorrect passphrase"
        log_error "     - GPG private key not imported"
        log_error "     - Corrupted backup file"
        return 1
    fi

    log_success "   ✅ Decrypted: $DECRYPTED_FILE"
    return 0
}

# Verify key integrity
verify_key_integrity() {
    local KEY_FILE=$1
    local FILENAME=$(basename "$KEY_FILE")

    log_info "🔍 Verifying: $FILENAME"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "   [DRY RUN] Would verify integrity"
        return 0
    fi

    # Parse JSON
    if ! python3 -c "import json; json.load(open('$KEY_FILE'))" 2>&1; then
        log_error "   Invalid JSON format"
        return 1
    fi

    # Verify required fields
    local MISSING_FIELDS=""

    if ! python3 -c "import json; assert 'encryption_key' in json.load(open('$KEY_FILE'))" 2>&1; then
        MISSING_FIELDS="$MISSING_FIELDS encryption_key"
    fi

    if ! python3 -c "import json; assert 'version' in json.load(open('$KEY_FILE'))" 2>&1; then
        MISSING_FIELDS="$MISSING_FIELDS version"
    fi

    if ! python3 -c "import json; assert 'created_at' in json.load(open('$KEY_FILE'))" 2>&1; then
        MISSING_FIELDS="$MISSING_FIELDS created_at"
    fi

    if ! python3 -c "import json; assert 'expires_at' in json.load(open('$KEY_FILE'))" 2>&1; then
        MISSING_FIELDS="$MISSING_FIELDS expires_at"
    fi

    if [[ -n "$MISSING_FIELDS" ]]; then
        log_error "   Missing fields:$MISSING_FIELDS"
        return 1
    fi

    # Verify key size (32 bytes = 44 chars base64)
    local KEY_LENGTH=$(python3 -c "import json, base64; print(len(base64.b64decode(json.load(open('$KEY_FILE'))['encryption_key'])))")

    if [[ "$KEY_LENGTH" -ne 32 ]]; then
        log_error "   Invalid key size: $KEY_LENGTH bytes (expected 32)"
        return 1
    fi

    # Extract version for logging
    local VERSION=$(python3 -c "import json; print(json.load(open('$KEY_FILE'))['version'])")

    log_success "   ✅ Valid: $VERSION, key size: 32 bytes"
    return 0
}

# Restore key to AWS Secrets Manager
restore_to_aws() {
    local KEY_FILE=$1
    local FILENAME=$(basename "$KEY_FILE")

    # Extract version from filename
    local VERSION=$(echo "$FILENAME" | sed 's/encryption-key-//' | sed 's/-backup.*//')
    local SECRET_NAME="pazpaz/encryption-key-${VERSION}"

    log_info "📤 Uploading to AWS: $SECRET_NAME"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "   [DRY RUN] Would upload to: $SECRET_NAME (region: $AWS_REGION)"
        return 0
    fi

    # Check if secret exists
    if aws secretsmanager describe-secret \
        --region "$AWS_REGION" \
        --secret-id "$SECRET_NAME" &> /dev/null; then

        log_warning "   Secret already exists. Updating value..."

        # Update existing secret
        aws secretsmanager put-secret-value \
            --region "$AWS_REGION" \
            --secret-id "$SECRET_NAME" \
            --secret-string file://"$KEY_FILE" &> /dev/null

        if [[ $? -eq 0 ]]; then
            log_success "   ✅ Updated: $SECRET_NAME"
        else
            log_error "   Failed to update: $SECRET_NAME"
            return 1
        fi
    else
        log_info "   Creating new secret: $SECRET_NAME"

        # Create new secret
        aws secretsmanager create-secret \
            --region "$AWS_REGION" \
            --name "$SECRET_NAME" \
            --secret-string file://"$KEY_FILE" &> /dev/null

        if [[ $? -eq 0 ]]; then
            log_success "   ✅ Created: $SECRET_NAME"
        else
            log_error "   Failed to create: $SECRET_NAME"
            return 1
        fi
    fi

    return 0
}

# Generate recovery report
generate_recovery_report() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would generate recovery report"
        return
    fi

    local REPORT_FILE="$RESTORE_DIR/RECOVERY_REPORT_$(date +%Y%m%d_%H%M%S).txt"

    cat > "$REPORT_FILE" <<EOF
Encryption Key Recovery Report
Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Backup Directory: $BACKUP_DIR
Restore Directory: $RESTORE_DIR
AWS Region: $AWS_REGION

Recovery Summary:
  Keys restored: $RESTORE_COUNT
  Failed restorations: $FAILED_COUNT
  Integrity checks passed: $VERIFY_COUNT
  Uploaded to AWS: $(if [[ "$RESTORE_TO_AWS" == "true" ]]; then echo "$AWS_UPLOAD_COUNT"; else echo "N/A (--restore-to-aws not used)"; fi)

Restored Keys:
$(ls -lh "$RESTORE_DIR"/encryption-key-*.json 2>/dev/null || echo "No keys restored")

Recovery Procedure:
1. Retrieved encrypted backups from: $BACKUP_DIR
2. Decrypted using GPG private key: security@pazpaz.com
3. Verified key integrity (JSON format, required fields, key size)
$(if [[ "$RESTORE_TO_AWS" == "true" ]]; then echo "4. Uploaded to AWS Secrets Manager (region: $AWS_REGION)"; fi)

Next Steps:
1. Verify keys can decrypt production PHI:
   python3 backend/tests/test_key_recovery.py

2. If AWS not restored, load keys into environment variables:
   export ENCRYPTION_KEY_V1=\$(cat $RESTORE_DIR/encryption-key-v1-*.json | jq -r .encryption_key)
   export ENCRYPTION_KEY_V2=\$(cat $RESTORE_DIR/encryption-key-v2-*.json | jq -r .encryption_key)

3. Restart application to load restored keys

4. Update incident log:
   echo "$(date -u +"%Y-%m-%d %H:%M:%S") - Key recovery successful" >> /secure/incidents/INCIDENT_LOG.txt

HIPAA Compliance:
- Recovery performed per §164.308(a)(7)(ii)(B)
- Incident logged for audit trail
- Keys securely deleted after verification (recommended)

Recovery Contact:
Security Team: security@pazpaz.com
EOF

    log_success "📄 Recovery report created: $REPORT_FILE"
}

# Main execution
main() {
    echo ""
    echo "🔓 PazPaz Encryption Key Recovery"
    echo "=================================="
    echo ""

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "DRY RUN MODE - No files will be created"
        echo ""
    fi

    verify_prerequisites
    create_restore_directory

    echo ""
    log_step "Step 1: Decrypting GPG-encrypted backups"
    log_step "==========================================="
    echo ""

    RESTORE_COUNT=0
    FAILED_COUNT=0

    for ENCRYPTED_FILE in "$BACKUP_DIR"/encryption-key-*.gpg; do
        if decrypt_backup "$ENCRYPTED_FILE"; then
            ((RESTORE_COUNT++))
        else
            ((FAILED_COUNT++))
        fi
    done

    echo ""
    echo "Decryption Summary:"
    echo "  Restored: $RESTORE_COUNT"
    echo "  Failed: $FAILED_COUNT"
    echo ""

    if [[ "$VERIFY_INTEGRITY" == "true" && "$DRY_RUN" == "false" ]]; then
        log_step "Step 2: Verifying key integrity"
        log_step "================================"
        echo ""

        VERIFY_COUNT=0
        VERIFY_FAILED=0

        for KEY_FILE in "$RESTORE_DIR"/encryption-key-*.json; do
            if [[ -f "$KEY_FILE" ]]; then
                if verify_key_integrity "$KEY_FILE"; then
                    ((VERIFY_COUNT++))
                else
                    ((VERIFY_FAILED++))
                fi
            fi
        done

        echo ""
        echo "Verification Summary:"
        echo "  Passed: $VERIFY_COUNT"
        echo "  Failed: $VERIFY_FAILED"
        echo ""

        if [[ $VERIFY_FAILED -gt 0 ]]; then
            log_error "Some keys failed integrity verification. Review errors above."
            exit 1
        fi
    else
        VERIFY_COUNT=0
    fi

    if [[ "$RESTORE_TO_AWS" == "true" && "$DRY_RUN" == "false" ]]; then
        log_step "Step 3: Uploading to AWS Secrets Manager"
        log_step "=========================================="
        echo ""

        AWS_UPLOAD_COUNT=0
        AWS_UPLOAD_FAILED=0

        for KEY_FILE in "$RESTORE_DIR"/encryption-key-*.json; do
            if [[ -f "$KEY_FILE" ]]; then
                if restore_to_aws "$KEY_FILE"; then
                    ((AWS_UPLOAD_COUNT++))
                else
                    ((AWS_UPLOAD_FAILED++))
                fi
            fi
        done

        echo ""
        echo "AWS Upload Summary:"
        echo "  Uploaded: $AWS_UPLOAD_COUNT"
        echo "  Failed: $AWS_UPLOAD_FAILED"
        echo ""

        if [[ $AWS_UPLOAD_FAILED -gt 0 ]]; then
            log_warning "Some AWS uploads failed. Keys are still available in: $RESTORE_DIR"
        fi
    else
        AWS_UPLOAD_COUNT=0
    fi

    if [[ "$DRY_RUN" == "false" ]]; then
        generate_recovery_report
    fi

    echo ""
    echo "=================================="
    echo "✅ Recovery Complete!"
    echo "=================================="
    echo ""
    echo "Summary:"
    echo "  Keys restored: $RESTORE_COUNT"
    echo "  Failed restorations: $FAILED_COUNT"
    echo "  Integrity checks passed: $VERIFY_COUNT"
    if [[ "$RESTORE_TO_AWS" == "true" ]]; then
        echo "  Uploaded to AWS: $AWS_UPLOAD_COUNT"
    fi
    echo "  Restore directory: $RESTORE_DIR"
    echo ""

    if [[ "$DRY_RUN" == "false" ]]; then
        echo "📋 Next Steps:"
        echo ""
        echo "  1. Verify keys can decrypt production PHI:"
        echo "     python3 backend/tests/test_key_recovery.py"
        echo ""

        if [[ "$RESTORE_TO_AWS" == "false" ]]; then
            echo "  2. Load keys into environment variables:"
            echo "     export ENCRYPTION_KEY_V1=\$(cat $RESTORE_DIR/encryption-key-v1-*.json | jq -r .encryption_key)"
            echo "     export ENCRYPTION_KEY_V2=\$(cat $RESTORE_DIR/encryption-key-v2-*.json | jq -r .encryption_key)"
            echo ""
            echo "  3. Or upload to AWS Secrets Manager:"
            echo "     ./scripts/restore_encryption_keys.sh --restore-to-aws"
            echo ""
        fi

        echo "  $(if [[ "$RESTORE_TO_AWS" == "true" ]]; then echo "2"; else echo "4"; fi). Restart application to load restored keys"
        echo ""
        echo "  $(if [[ "$RESTORE_TO_AWS" == "true" ]]; then echo "3"; else echo "5"; fi). Securely delete restored plaintext keys (after verification):"
        echo "     shred -vfz -n 10 $RESTORE_DIR/encryption-key-*.json"
        echo ""
        echo "  $(if [[ "$RESTORE_TO_AWS" == "true" ]]; then echo "4"; else echo "6"; fi). Update incident log:"
        echo "     echo \"\$(date -u +\"%Y-%m-%d %H:%M:%S\") - Key recovery successful\" >> /secure/incidents/INCIDENT_LOG.txt"
        echo ""
    fi

    # Exit with error if any restorations failed
    if [[ $FAILED_COUNT -gt 0 ]]; then
        log_error "Some restorations failed. Review errors above."
        exit 1
    fi

    exit 0
}

# Run main function
main
