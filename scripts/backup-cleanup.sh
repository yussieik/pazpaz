#!/bin/bash
# =============================================================================
# PazPaz Backup Cleanup Script - Grandfather-Father-Son Rotation
# =============================================================================
#
# Purpose: Implement backup retention policy and cleanup old backups
# Features:
#   - Grandfather-Father-Son (GFS) rotation scheme
#   - Daily backups kept for 7 days
#   - Weekly backups kept for 4 weeks (Sundays)
#   - Monthly backups kept for 12 months (1st of month)
#   - S3 lifecycle policy configuration
#   - Disk space monitoring and alerts
#   - Backup inventory reporting
#
# Usage:
#   ./backup-cleanup.sh [--dry-run] [--verbose]
#
# Options:
#   --dry-run     Show what would be deleted without making changes
#   --verbose     Show detailed output
#   --force       Force cleanup even if disk space is adequate
#   --report      Generate backup inventory report
#
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# Configuration
# =============================================================================

# Script configuration
SCRIPT_NAME="backup-cleanup.sh"
VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Backup configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/pazpaz}"
DRY_RUN=false
VERBOSE=false
FORCE_CLEANUP=false
GENERATE_REPORT=false

# Retention policy (in days)
DAILY_RETENTION=7          # Keep daily backups for 7 days
WEEKLY_RETENTION=28         # Keep weekly backups for 4 weeks
MONTHLY_RETENTION=365       # Keep monthly backups for 12 months

# S3 configuration
S3_BACKUP_BUCKET="${S3_BACKUP_BUCKET:-pazpaz-backups}"
S3_BACKUP_PREFIX="${S3_BACKUP_PREFIX:-database}"

# Disk space thresholds
DISK_WARNING_THRESHOLD=80  # Warn when disk usage exceeds 80%
DISK_CRITICAL_THRESHOLD=90 # Critical alert at 90%
MIN_FREE_SPACE_GB=10        # Minimum free space required

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

verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        log "🔍 $1" "$NC"
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --force)
                FORCE_CLEANUP=true
                shift
                ;;
            --report)
                GENERATE_REPORT=true
                shift
                ;;
            --help|-h)
                show_usage
                ;;
            *)
                error "Unknown option: $1"
                show_usage
                ;;
        esac
    done
}

# Show usage information
show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Manage backup retention and cleanup old backups

Options:
    --dry-run     Show what would be deleted without making changes
    --verbose     Show detailed output
    --force       Force cleanup even if disk space is adequate
    --report      Generate backup inventory report
    --help        Show this help message

Retention Policy:
    • Daily:   Keep for $DAILY_RETENTION days
    • Weekly:  Keep for $WEEKLY_RETENTION days (4 weeks)
    • Monthly: Keep for $MONTHLY_RETENTION days (12 months)

Examples:
    # Preview cleanup without making changes
    $SCRIPT_NAME --dry-run

    # Run cleanup with detailed output
    $SCRIPT_NAME --verbose

    # Generate backup inventory report
    $SCRIPT_NAME --report

EOF
    exit 0
}

# Convert bytes to human readable format
human_readable_size() {
    local size=$1
    local units=("B" "KB" "MB" "GB" "TB")
    local unit_index=0

    while [[ $size -gt 1024 && $unit_index -lt 4 ]]; do
        size=$((size / 1024))
        ((unit_index++))
    done

    echo "$size ${units[$unit_index]}"
}

# Get disk usage percentage for backup directory
get_disk_usage() {
    df "$BACKUP_DIR" | awk 'NR==2 {print int($5)}'
}

# Get free disk space in GB
get_free_space_gb() {
    df "$BACKUP_DIR" | awk 'NR==2 {print int($4/1024/1024)}'
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
            \"text\": \"$emoji PazPaz Backup Cleanup: $message\",
            \"username\": \"Backup Cleanup Bot\",
            \"icon_emoji\": \":broom:\"
        }" 2>/dev/null || true
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

# Parse arguments
parse_args "$@"

info "Starting PazPaz backup cleanup (v$VERSION)"

if [[ "$DRY_RUN" == "true" ]]; then
    warning "Running in DRY RUN mode - no files will be deleted"
fi

# Check if backup directory exists
if [[ ! -d "$BACKUP_DIR" ]]; then
    error "Backup directory not found: $BACKUP_DIR"
    exit 1
fi

# Check disk usage
DISK_USAGE=$(get_disk_usage)
FREE_SPACE_GB=$(get_free_space_gb)

info "Disk usage: ${DISK_USAGE}% (${FREE_SPACE_GB}GB free)"

if [[ $DISK_USAGE -ge $DISK_CRITICAL_THRESHOLD ]]; then
    error "Critical: Disk usage at ${DISK_USAGE}% (threshold: ${DISK_CRITICAL_THRESHOLD}%)"
    send_slack_notification "⚠️ CRITICAL: Disk usage at ${DISK_USAGE}%!" "error"
    FORCE_CLEANUP=true
elif [[ $DISK_USAGE -ge $DISK_WARNING_THRESHOLD ]]; then
    warning "Disk usage at ${DISK_USAGE}% (threshold: ${DISK_WARNING_THRESHOLD}%)"
    send_slack_notification "Disk usage warning: ${DISK_USAGE}%" "warning"
fi

if [[ $FREE_SPACE_GB -lt $MIN_FREE_SPACE_GB ]]; then
    warning "Low disk space: ${FREE_SPACE_GB}GB free (minimum: ${MIN_FREE_SPACE_GB}GB)"
    FORCE_CLEANUP=true
fi

# =============================================================================
# Backup Inventory
# =============================================================================

info "Analyzing backup inventory..."

# Count backups by type
DAILY_COUNT=$(find "$BACKUP_DIR/daily" -name "*.dump.gpg" 2>/dev/null | wc -l | tr -d ' ')
WEEKLY_COUNT=$(find "$BACKUP_DIR/weekly" -name "*.dump.gpg" 2>/dev/null | wc -l | tr -d ' ')
MONTHLY_COUNT=$(find "$BACKUP_DIR/monthly" -name "*.dump.gpg" 2>/dev/null | wc -l | tr -d ' ')

# Calculate total size
DAILY_SIZE=$(du -sb "$BACKUP_DIR/daily" 2>/dev/null | cut -f1 || echo "0")
WEEKLY_SIZE=$(du -sb "$BACKUP_DIR/weekly" 2>/dev/null | cut -f1 || echo "0")
MONTHLY_SIZE=$(du -sb "$BACKUP_DIR/monthly" 2>/dev/null | cut -f1 || echo "0")
TOTAL_SIZE=$((DAILY_SIZE + WEEKLY_SIZE + MONTHLY_SIZE))

info "Current backup inventory:"
echo "  📅 Daily:   $DAILY_COUNT backups ($(human_readable_size $DAILY_SIZE))"
echo "  📆 Weekly:  $WEEKLY_COUNT backups ($(human_readable_size $WEEKLY_SIZE))"
echo "  📆 Monthly: $MONTHLY_COUNT backups ($(human_readable_size $MONTHLY_SIZE))"
echo "  💾 Total:   $((DAILY_COUNT + WEEKLY_COUNT + MONTHLY_COUNT)) backups ($(human_readable_size $TOTAL_SIZE))"

# =============================================================================
# Local Backup Cleanup
# =============================================================================

info "Cleaning up local backups..."

# Track cleanup statistics
DELETED_COUNT=0
DELETED_SIZE=0

# Clean daily backups older than retention period
info "Cleaning daily backups older than $DAILY_RETENTION days..."
while IFS= read -r backup_file; do
    if [[ -z "$backup_file" ]]; then
        continue
    fi

    FILE_SIZE=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    FILE_AGE=$(( ($(date +%s) - $(stat -f%m "$backup_file" 2>/dev/null || stat -c%Y "$backup_file" 2>/dev/null)) / 86400 ))

    verbose "  Found: $(basename "$backup_file") ($(human_readable_size $FILE_SIZE), $FILE_AGE days old)"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] Would delete: $backup_file"
    else
        rm -f "$backup_file"
        rm -f "${backup_file%.gpg}.meta.json" 2>/dev/null || true
        verbose "  Deleted: $(basename "$backup_file")"
    fi

    ((DELETED_COUNT++))
    DELETED_SIZE=$((DELETED_SIZE + FILE_SIZE))
done < <(find "$BACKUP_DIR/daily" -name "*.dump.gpg" -mtime +$DAILY_RETENTION 2>/dev/null)

# Clean weekly backups older than retention period
info "Cleaning weekly backups older than $WEEKLY_RETENTION days..."
while IFS= read -r backup_file; do
    if [[ -z "$backup_file" ]]; then
        continue
    fi

    FILE_SIZE=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    FILE_AGE=$(( ($(date +%s) - $(stat -f%m "$backup_file" 2>/dev/null || stat -c%Y "$backup_file" 2>/dev/null)) / 86400 ))

    verbose "  Found: $(basename "$backup_file") ($(human_readable_size $FILE_SIZE), $FILE_AGE days old)"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] Would delete: $backup_file"
    else
        rm -f "$backup_file"
        rm -f "${backup_file%.gpg}.meta.json" 2>/dev/null || true
        verbose "  Deleted: $(basename "$backup_file")"
    fi

    ((DELETED_COUNT++))
    DELETED_SIZE=$((DELETED_SIZE + FILE_SIZE))
done < <(find "$BACKUP_DIR/weekly" -name "*.dump.gpg" -mtime +$WEEKLY_RETENTION 2>/dev/null)

# Clean monthly backups older than retention period
info "Cleaning monthly backups older than $MONTHLY_RETENTION days..."
while IFS= read -r backup_file; do
    if [[ -z "$backup_file" ]]; then
        continue
    fi

    FILE_SIZE=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo "0")
    FILE_AGE=$(( ($(date +%s) - $(stat -f%m "$backup_file" 2>/dev/null || stat -c%Y "$backup_file" 2>/dev/null)) / 86400 ))

    verbose "  Found: $(basename "$backup_file") ($(human_readable_size $FILE_SIZE), $FILE_AGE days old)"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] Would delete: $backup_file"
    else
        rm -f "$backup_file"
        rm -f "${backup_file%.gpg}.meta.json" 2>/dev/null || true
        verbose "  Deleted: $(basename "$backup_file")"
    fi

    ((DELETED_COUNT++))
    DELETED_SIZE=$((DELETED_SIZE + FILE_SIZE))
done < <(find "$BACKUP_DIR/monthly" -name "*.dump.gpg" -mtime +$MONTHLY_RETENTION 2>/dev/null)

if [[ $DELETED_COUNT -gt 0 ]]; then
    success "Deleted $DELETED_COUNT old backups (freed $(human_readable_size $DELETED_SIZE))"
else
    info "No old backups to delete"
fi

# =============================================================================
# S3 Lifecycle Policy Configuration
# =============================================================================

if [[ "$DRY_RUN" != "true" ]] && command -v aws >/dev/null 2>&1; then
    info "Configuring S3 lifecycle policies..."

    # Create lifecycle policy JSON
    LIFECYCLE_POLICY=$(cat <<EOF
{
    "Rules": [
        {
            "Id": "daily-backup-retention",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "$S3_BACKUP_PREFIX/daily/"
            },
            "Expiration": {
                "Days": $DAILY_RETENTION
            }
        },
        {
            "Id": "weekly-backup-retention",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "$S3_BACKUP_PREFIX/weekly/"
            },
            "Expiration": {
                "Days": $WEEKLY_RETENTION
            }
        },
        {
            "Id": "monthly-backup-retention",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "$S3_BACKUP_PREFIX/monthly/"
            },
            "Expiration": {
                "Days": $MONTHLY_RETENTION
            }
        },
        {
            "Id": "transition-to-glacier",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "$S3_BACKUP_PREFIX/monthly/"
            },
            "Transitions": [
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ]
        }
    ]
}
EOF
)

    # Apply lifecycle policy to S3 bucket
    if aws s3api put-bucket-lifecycle-configuration \
        --bucket "$S3_BACKUP_BUCKET" \
        --lifecycle-configuration "$LIFECYCLE_POLICY" 2>/dev/null; then
        success "S3 lifecycle policies updated"
    else
        warning "Failed to update S3 lifecycle policies"
    fi
fi

# =============================================================================
# Clean Orphaned Files
# =============================================================================

info "Cleaning orphaned metadata files..."

# Find metadata files without corresponding backup files
ORPHANED_META_COUNT=0
while IFS= read -r meta_file; do
    if [[ -z "$meta_file" ]]; then
        continue
    fi

    BACKUP_FILE="${meta_file%.meta.json}.dump.gpg"
    if [[ ! -f "$BACKUP_FILE" ]]; then
        verbose "  Found orphaned metadata: $(basename "$meta_file")"
        if [[ "$DRY_RUN" == "true" ]]; then
            echo "  [DRY RUN] Would delete: $meta_file"
        else
            rm -f "$meta_file"
        fi
        ((ORPHANED_META_COUNT++))
    fi
done < <(find "$BACKUP_DIR" -name "*.meta.json" 2>/dev/null)

if [[ $ORPHANED_META_COUNT -gt 0 ]]; then
    success "Cleaned $ORPHANED_META_COUNT orphaned metadata files"
fi

# =============================================================================
# Generate Backup Report
# =============================================================================

if [[ "$GENERATE_REPORT" == "true" ]]; then
    info "Generating backup inventory report..."

    REPORT_FILE="$BACKUP_DIR/inventory-$(date +%Y%m%d-%H%M%S).txt"

    {
        echo "PazPaz Backup Inventory Report"
        echo "Generated: $(date)"
        echo "=" | sed 's/./-/g'
        echo ""
        echo "DISK USAGE:"
        echo "  Usage: ${DISK_USAGE}%"
        echo "  Free:  ${FREE_SPACE_GB}GB"
        echo ""
        echo "BACKUP COUNTS:"
        echo "  Daily:   $DAILY_COUNT backups"
        echo "  Weekly:  $WEEKLY_COUNT backups"
        echo "  Monthly: $MONTHLY_COUNT backups"
        echo ""
        echo "STORAGE USAGE:"
        echo "  Daily:   $(human_readable_size $DAILY_SIZE)"
        echo "  Weekly:  $(human_readable_size $WEEKLY_SIZE)"
        echo "  Monthly: $(human_readable_size $MONTHLY_SIZE)"
        echo "  Total:   $(human_readable_size $TOTAL_SIZE)"
        echo ""
        echo "RETENTION POLICY:"
        echo "  Daily:   $DAILY_RETENTION days"
        echo "  Weekly:  $WEEKLY_RETENTION days"
        echo "  Monthly: $MONTHLY_RETENTION days"
        echo ""
        echo "RECENT BACKUPS:"
        echo ""
        echo "Daily (last 3):"
        find "$BACKUP_DIR/daily" -name "*.dump.gpg" -type f -exec ls -lh {} \; 2>/dev/null | tail -3
        echo ""
        echo "Weekly (last 3):"
        find "$BACKUP_DIR/weekly" -name "*.dump.gpg" -type f -exec ls -lh {} \; 2>/dev/null | tail -3
        echo ""
        echo "Monthly (last 3):"
        find "$BACKUP_DIR/monthly" -name "*.dump.gpg" -type f -exec ls -lh {} \; 2>/dev/null | tail -3
    } > "$REPORT_FILE"

    success "Report saved: $REPORT_FILE"
fi

# =============================================================================
# Post-Cleanup Analysis
# =============================================================================

# Check disk usage after cleanup
NEW_DISK_USAGE=$(get_disk_usage)
NEW_FREE_SPACE_GB=$(get_free_space_gb)

if [[ $NEW_DISK_USAGE -lt $DISK_USAGE ]]; then
    success "Disk usage reduced from ${DISK_USAGE}% to ${NEW_DISK_USAGE}%"
fi

# Send notification if significant cleanup occurred
if [[ $DELETED_COUNT -gt 0 ]] && [[ "$DRY_RUN" != "true" ]]; then
    CLEANUP_MESSAGE="Cleanup completed: Deleted $DELETED_COUNT old backups, freed $(human_readable_size $DELETED_SIZE). Disk usage now at ${NEW_DISK_USAGE}%."
    send_slack_notification "$CLEANUP_MESSAGE" "success"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    warning "=== Cleanup Dry Run Complete ==="
    echo "Would delete: $DELETED_COUNT backups"
    echo "Would free:   $(human_readable_size $DELETED_SIZE)"
else
    success "=== Backup Cleanup Complete ==="
    echo "Deleted:     $DELETED_COUNT backups"
    echo "Freed:       $(human_readable_size $DELETED_SIZE)"
fi
echo "Disk usage:  ${NEW_DISK_USAGE}% (${NEW_FREE_SPACE_GB}GB free)"
echo ""

# Log cleanup summary
CLEANUP_LOG="$BACKUP_DIR/cleanup.log"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | Deleted: $DELETED_COUNT | Freed: $(human_readable_size $DELETED_SIZE) | Disk: ${NEW_DISK_USAGE}%" >> "$CLEANUP_LOG"

exit 0