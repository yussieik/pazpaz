#!/bin/bash
# =============================================================================
# PazPaz Database Backup Script - HIPAA Compliant
# =============================================================================
#
# Purpose: Automated PostgreSQL backups with encryption and off-site storage
# Features:
#   - Compressed PostgreSQL custom format backups (pg_dump -Fc)
#   - GPG encryption for HIPAA compliance
#   - S3/DigitalOcean Spaces upload for off-site storage
#   - Backup integrity verification
#   - Automated cleanup of old backups
#   - Notifications on failure (Slack/Email)
#   - Performance metrics and logging
#
# Usage:
#   ./backup-db.sh [daily|weekly|monthly]
#
# Environment Requirements:
#   - PostgreSQL client tools installed
#   - AWS CLI configured for S3 access
#   - GPG configured with backup encryption key
#   - Docker running with pazpaz-db container
#
# Required Environment Variables:
#   - POSTGRES_PASSWORD: Database password
#   - S3_BACKUP_BUCKET: S3 bucket for backup storage
#   - GPG_BACKUP_RECIPIENT: GPG recipient for encryption
#   - SLACK_WEBHOOK_URL: Slack webhook for notifications (optional)
#   - SMTP_RECIPIENT: Email recipient for notifications (optional)
#
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# Configuration
# =============================================================================

# Script configuration
SCRIPT_NAME="backup-db.sh"
VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Backup configuration
BACKUP_TYPE="${1:-daily}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/pazpaz}"
BACKUP_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DATE="$(date +%Y%m%d)"
BACKUP_WEEK="$(date +%Y-W%U)"
BACKUP_MONTH="$(date +%Y%m)"

# Database configuration
DB_CONTAINER="pazpaz-db"
DB_NAME="pazpaz"
DB_USER="pazpaz"
DB_HOST="localhost"
DB_PORT="5432"

# S3 configuration
S3_BACKUP_BUCKET="${S3_BACKUP_BUCKET:-pazpaz-backups}"
S3_BACKUP_PREFIX="${S3_BACKUP_PREFIX:-database}"
S3_STORAGE_CLASS="${S3_STORAGE_CLASS:-STANDARD_IA}"  # Use Infrequent Access for cost savings

# GPG configuration
GPG_BACKUP_RECIPIENT="${GPG_BACKUP_RECIPIENT:-backup@pazpaz.com}"
GPG_KEY_FINGERPRINT="${GPG_KEY_FINGERPRINT:-}"

# Retention configuration (days)
DAILY_RETENTION=7
WEEKLY_RETENTION=28  # 4 weeks
MONTHLY_RETENTION=365  # 12 months

# Notification configuration
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
SMTP_RECIPIENT="${SMTP_RECIPIENT:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

# Print colored output
log() {
    echo -e "${2:-$NC}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

info() {
    log "ℹ️  $1" "$BLUE"
}

success() {
    log "✅ $1" "$GREEN"
}

warning() {
    log "⚠️  $1" "$YELLOW"
}

error() {
    log "❌ $1" "$RED"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Send Slack notification
send_slack_notification() {
    local message="$1"
    local status="${2:-info}"

    if [[ -z "$SLACK_WEBHOOK_URL" ]]; then
        return 0
    fi

    local emoji="ℹ️"
    case "$status" in
        success) emoji="✅" ;;
        warning) emoji="⚠️" ;;
        error) emoji="❌" ;;
    esac

    curl -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \"$emoji PazPaz Backup: $message\",
            \"username\": \"Backup Bot\",
            \"icon_emoji\": \":floppy_disk:\"
        }" 2>/dev/null || true
}

# Send email notification
send_email_notification() {
    local subject="$1"
    local body="$2"

    if [[ -z "$SMTP_RECIPIENT" ]]; then
        return 0
    fi

    echo "$body" | mail -s "$subject" "$SMTP_RECIPIENT" 2>/dev/null || true
}

# Cleanup on exit
cleanup() {
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        error "Backup failed with exit code $exit_code"
        send_slack_notification "Database backup failed! Check logs for details." "error"
        send_email_notification "PazPaz Backup Failed" "Database backup failed at $(date). Please check the logs."
    fi

    # Clean up temporary files
    if [[ -n "${TEMP_BACKUP_FILE:-}" ]] && [[ -f "$TEMP_BACKUP_FILE" ]]; then
        rm -f "$TEMP_BACKUP_FILE"
    fi
}

trap cleanup EXIT

# =============================================================================
# Pre-flight Checks
# =============================================================================

info "Starting PazPaz database backup ($BACKUP_TYPE)"
info "Backup timestamp: $BACKUP_TIMESTAMP"

# Check required commands
REQUIRED_COMMANDS=("docker" "pg_dump" "gpg" "aws")
for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command_exists "$cmd"; then
        error "Required command not found: $cmd"
        exit 1
    fi
done

# Create backup directory structure
mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly,temp}

# Check if database container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    error "Database container '$DB_CONTAINER' is not running"
    exit 1
fi

# Get database password
if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
    if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
        source "$PROJECT_ROOT/.env.production"
    else
        error "POSTGRES_PASSWORD not set and .env.production not found"
        exit 1
    fi
fi

# Verify GPG key exists
if [[ -n "$GPG_KEY_FINGERPRINT" ]]; then
    if ! gpg --list-keys "$GPG_KEY_FINGERPRINT" >/dev/null 2>&1; then
        error "GPG key with fingerprint $GPG_KEY_FINGERPRINT not found"
        exit 1
    fi
elif ! gpg --list-keys "$GPG_BACKUP_RECIPIENT" >/dev/null 2>&1; then
    warning "GPG key for $GPG_BACKUP_RECIPIENT not found, attempting to import..."
    # Try to import from keyserver
    gpg --keyserver hkps://keys.openpgp.org --recv-keys "$GPG_BACKUP_RECIPIENT" || {
        error "Failed to import GPG key for $GPG_BACKUP_RECIPIENT"
        exit 1
    }
fi

# Check S3 bucket access
if ! aws s3 ls "s3://$S3_BACKUP_BUCKET" >/dev/null 2>&1; then
    error "Cannot access S3 bucket: $S3_BACKUP_BUCKET"
    exit 1
fi

# =============================================================================
# Backup Process
# =============================================================================

# Determine backup file paths
case "$BACKUP_TYPE" in
    daily)
        BACKUP_SUBDIR="daily"
        BACKUP_NAME="pazpaz-daily-${BACKUP_DATE}-${BACKUP_TIMESTAMP}"
        S3_PATH="$S3_BACKUP_PREFIX/daily/${BACKUP_DATE}/"
        ;;
    weekly)
        BACKUP_SUBDIR="weekly"
        BACKUP_NAME="pazpaz-weekly-${BACKUP_WEEK}-${BACKUP_TIMESTAMP}"
        S3_PATH="$S3_BACKUP_PREFIX/weekly/${BACKUP_WEEK}/"
        ;;
    monthly)
        BACKUP_SUBDIR="monthly"
        BACKUP_NAME="pazpaz-monthly-${BACKUP_MONTH}-${BACKUP_TIMESTAMP}"
        S3_PATH="$S3_BACKUP_PREFIX/monthly/${BACKUP_MONTH}/"
        ;;
    *)
        error "Invalid backup type: $BACKUP_TYPE. Use daily, weekly, or monthly"
        exit 1
        ;;
esac

BACKUP_FILE="$BACKUP_DIR/$BACKUP_SUBDIR/${BACKUP_NAME}.dump"
ENCRYPTED_FILE="${BACKUP_FILE}.gpg"
METADATA_FILE="${BACKUP_FILE}.meta.json"
TEMP_BACKUP_FILE="$BACKUP_DIR/temp/${BACKUP_NAME}.dump"

info "Creating $BACKUP_TYPE backup: $BACKUP_NAME"

# Step 1: Create database backup
info "Performing database dump..."
START_TIME=$(date +%s)

# Use docker exec to run pg_dump inside the container
docker exec "$DB_CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -Fc \
    -v \
    --no-password \
    --quote-all-identifiers \
    --serializable-deferrable \
    --no-synchronized-snapshots \
    --lock-wait-timeout=60000 \
> "$TEMP_BACKUP_FILE" 2>/dev/null

DUMP_SIZE=$(du -h "$TEMP_BACKUP_FILE" | cut -f1)
END_TIME=$(date +%s)
DUMP_DURATION=$((END_TIME - START_TIME))

success "Database dump completed: $DUMP_SIZE in ${DUMP_DURATION}s"

# Step 2: Verify backup integrity
info "Verifying backup integrity..."
if ! pg_restore --list "$TEMP_BACKUP_FILE" >/dev/null 2>&1; then
    error "Backup verification failed - corrupt backup file"
    exit 1
fi

# Get backup statistics
TABLE_COUNT=$(pg_restore --list "$TEMP_BACKUP_FILE" 2>/dev/null | grep -c "TABLE DATA" || true)
success "Backup verified: $TABLE_COUNT tables"

# Step 3: Encrypt backup
info "Encrypting backup with GPG..."
START_TIME=$(date +%s)

gpg --trust-model always \
    --encrypt \
    --recipient "$GPG_BACKUP_RECIPIENT" \
    --cipher-algo AES256 \
    --compress-algo zlib \
    --compress-level 9 \
    --output "$ENCRYPTED_FILE" \
    "$TEMP_BACKUP_FILE"

ENCRYPTED_SIZE=$(du -h "$ENCRYPTED_FILE" | cut -f1)
END_TIME=$(date +%s)
ENCRYPT_DURATION=$((END_TIME - START_TIME))

success "Backup encrypted: $ENCRYPTED_SIZE in ${ENCRYPT_DURATION}s"

# Step 4: Create metadata file
info "Creating backup metadata..."
cat > "$METADATA_FILE" <<EOF
{
    "backup_name": "$BACKUP_NAME",
    "backup_type": "$BACKUP_TYPE",
    "backup_timestamp": "$BACKUP_TIMESTAMP",
    "database_name": "$DB_NAME",
    "original_size": "$DUMP_SIZE",
    "encrypted_size": "$ENCRYPTED_SIZE",
    "table_count": $TABLE_COUNT,
    "dump_duration": $DUMP_DURATION,
    "encrypt_duration": $ENCRYPT_DURATION,
    "postgres_version": "$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c 'SELECT version()' | head -1)",
    "gpg_recipient": "$GPG_BACKUP_RECIPIENT",
    "hostname": "$(hostname)",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Step 5: Upload to S3
info "Uploading backup to S3..."
START_TIME=$(date +%s)

# Upload encrypted backup
aws s3 cp "$ENCRYPTED_FILE" \
    "s3://$S3_BACKUP_BUCKET/$S3_PATH${BACKUP_NAME}.dump.gpg" \
    --storage-class "$S3_STORAGE_CLASS" \
    --metadata "backup-type=$BACKUP_TYPE,created=$BACKUP_TIMESTAMP" \
    --server-side-encryption AES256

# Upload metadata
aws s3 cp "$METADATA_FILE" \
    "s3://$S3_BACKUP_BUCKET/$S3_PATH${BACKUP_NAME}.meta.json" \
    --storage-class "$S3_STORAGE_CLASS" \
    --server-side-encryption AES256

END_TIME=$(date +%s)
UPLOAD_DURATION=$((END_TIME - START_TIME))

success "Backup uploaded to S3 in ${UPLOAD_DURATION}s"

# Step 6: Create "latest" symlink for easy restore
if [[ "$BACKUP_TYPE" == "daily" ]]; then
    ln -sf "$ENCRYPTED_FILE" "$BACKUP_DIR/latest.dump.gpg"
    ln -sf "$METADATA_FILE" "$BACKUP_DIR/latest.meta.json"

    # Upload latest markers to S3
    aws s3 cp "$ENCRYPTED_FILE" \
        "s3://$S3_BACKUP_BUCKET/$S3_BACKUP_PREFIX/latest.dump.gpg" \
        --storage-class STANDARD \
        --metadata "backup-type=latest,created=$BACKUP_TIMESTAMP" \
        --server-side-encryption AES256
fi

# Step 7: Clean up temporary files
rm -f "$TEMP_BACKUP_FILE"
mv "$ENCRYPTED_FILE" "$BACKUP_FILE.gpg"  # Keep encrypted version only

# =============================================================================
# Cleanup Old Backups
# =============================================================================

info "Cleaning up old backups..."

# Clean up local backups
case "$BACKUP_TYPE" in
    daily)
        find "$BACKUP_DIR/daily" -name "*.dump.gpg" -mtime +$DAILY_RETENTION -delete
        find "$BACKUP_DIR/daily" -name "*.meta.json" -mtime +$DAILY_RETENTION -delete
        ;;
    weekly)
        find "$BACKUP_DIR/weekly" -name "*.dump.gpg" -mtime +$WEEKLY_RETENTION -delete
        find "$BACKUP_DIR/weekly" -name "*.meta.json" -mtime +$WEEKLY_RETENTION -delete
        ;;
    monthly)
        find "$BACKUP_DIR/monthly" -name "*.dump.gpg" -mtime +$MONTHLY_RETENTION -delete
        find "$BACKUP_DIR/monthly" -name "*.meta.json" -mtime +$MONTHLY_RETENTION -delete
        ;;
esac

# Note: S3 lifecycle policies should handle remote cleanup
# This is configured separately via AWS Console or Terraform

success "Old backups cleaned up"

# =============================================================================
# Logging and Notifications
# =============================================================================

# Log backup completion
BACKUP_LOG="$BACKUP_DIR/backup.log"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $BACKUP_TYPE | $BACKUP_NAME | $DUMP_SIZE | $ENCRYPTED_SIZE | SUCCESS" >> "$BACKUP_LOG"

# Send success notification
TOTAL_DURATION=$(($(date +%s) - $(date +%s --date="$BACKUP_TIMESTAMP")))
SUCCESS_MESSAGE="✅ $BACKUP_TYPE backup completed successfully
• Name: $BACKUP_NAME
• Size: $DUMP_SIZE → $ENCRYPTED_SIZE (encrypted)
• Tables: $TABLE_COUNT
• Duration: ${TOTAL_DURATION}s
• Location: s3://$S3_BACKUP_BUCKET/$S3_PATH"

send_slack_notification "$SUCCESS_MESSAGE" "success"

# Print summary
echo ""
success "=== Backup Completed Successfully ==="
echo "Backup Name:     $BACKUP_NAME"
echo "Backup Type:     $BACKUP_TYPE"
echo "Original Size:   $DUMP_SIZE"
echo "Encrypted Size:  $ENCRYPTED_SIZE"
echo "Table Count:     $TABLE_COUNT"
echo "Total Duration:  ${TOTAL_DURATION}s"
echo "S3 Location:     s3://$S3_BACKUP_BUCKET/$S3_PATH"
echo ""

# =============================================================================
# Performance Metrics (Optional)
# =============================================================================

# Send metrics to monitoring system if configured
if [[ -n "${METRICS_ENDPOINT:-}" ]]; then
    curl -X POST "$METRICS_ENDPOINT" \
        -H "Content-Type: application/json" \
        -d "{
            \"metric\": \"backup.database\",
            \"value\": 1,
            \"tags\": {
                \"type\": \"$BACKUP_TYPE\",
                \"duration\": $TOTAL_DURATION,
                \"size_bytes\": $(stat -f%z "$BACKUP_FILE.gpg" 2>/dev/null || stat -c%s "$BACKUP_FILE.gpg"),
                \"table_count\": $TABLE_COUNT
            }
        }" 2>/dev/null || true
fi

exit 0