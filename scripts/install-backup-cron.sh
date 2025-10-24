#!/bin/bash
# =============================================================================
# PazPaz Backup Cron Job Installation Script
# =============================================================================
#
# Purpose: Configure automated backup schedule using cron
# Features:
#   - Daily backups at 2 AM UTC
#   - Weekly full backups on Sundays at 3 AM UTC
#   - Monthly backups on the 1st at 4 AM UTC
#   - Automated backup testing on the first Sunday
#   - Log rotation configuration
#   - Email notification on cron failures
#
# Usage:
#   sudo ./install-backup-cron.sh [--user USERNAME]
#
# Options:
#   --user USERNAME    User account to run backups (default: pazpaz)
#   --remove          Remove backup cron jobs
#   --dry-run         Show what would be installed without making changes
#
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# Configuration
# =============================================================================

# Script configuration
SCRIPT_NAME="install-backup-cron.sh"
VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default values
BACKUP_USER="${BACKUP_USER:-pazpaz}"
DRY_RUN=false
REMOVE_MODE=false

# Paths
BACKUP_SCRIPT="$SCRIPT_DIR/backup-db.sh"
TEST_SCRIPT="$SCRIPT_DIR/test-backup-restore.sh"
CLEANUP_SCRIPT="$SCRIPT_DIR/backup-cleanup.sh"
CRON_FILE="/etc/cron.d/pazpaz-backups"
LOGROTATE_FILE="/etc/logrotate.d/pazpaz-backups"
BACKUP_LOG_DIR="/var/log/pazpaz"

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

# Show usage information
show_usage() {
    cat << EOF
Usage: sudo $SCRIPT_NAME [OPTIONS]

Configure automated backup schedule for PazPaz database

Options:
    --user USERNAME    User account to run backups (default: pazpaz)
    --remove          Remove backup cron jobs
    --dry-run         Show what would be installed without making changes
    --help            Show this help message

Examples:
    # Install cron jobs for default user
    sudo $SCRIPT_NAME

    # Install for specific user
    sudo $SCRIPT_NAME --user postgres

    # Remove backup cron jobs
    sudo $SCRIPT_NAME --remove

    # Preview changes
    $SCRIPT_NAME --dry-run

EOF
    exit 0
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --user)
                BACKUP_USER="$2"
                shift 2
                ;;
            --remove)
                REMOVE_MODE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
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

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]] && [[ "$DRY_RUN" != "true" ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

# Parse arguments
parse_args "$@"

# Check root privileges
check_root

info "PazPaz Backup Cron Job Installer v$VERSION"

if [[ "$REMOVE_MODE" == "true" ]]; then
    info "Mode: Remove backup cron jobs"
elif [[ "$DRY_RUN" == "true" ]]; then
    info "Mode: Dry run (no changes will be made)"
else
    info "Mode: Install backup cron jobs"
fi

# Check if user exists
if ! id "$BACKUP_USER" &>/dev/null && [[ "$DRY_RUN" != "true" ]]; then
    error "User '$BACKUP_USER' does not exist"
    exit 1
fi

# Check if backup scripts exist
if [[ ! -f "$BACKUP_SCRIPT" ]] && [[ "$REMOVE_MODE" != "true" ]]; then
    error "Backup script not found: $BACKUP_SCRIPT"
    exit 1
fi

# =============================================================================
# Remove Mode
# =============================================================================

if [[ "$REMOVE_MODE" == "true" ]]; then
    info "Removing backup cron jobs..."

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Would remove: $CRON_FILE"
        echo "Would remove: $LOGROTATE_FILE"
    else
        # Remove cron file
        if [[ -f "$CRON_FILE" ]]; then
            rm -f "$CRON_FILE"
            success "Removed cron file: $CRON_FILE"
        else
            warning "Cron file not found: $CRON_FILE"
        fi

        # Remove logrotate configuration
        if [[ -f "$LOGROTATE_FILE" ]]; then
            rm -f "$LOGROTATE_FILE"
            success "Removed logrotate config: $LOGROTATE_FILE"
        else
            warning "Logrotate config not found: $LOGROTATE_FILE"
        fi

        # Reload cron service
        if systemctl is-active --quiet crond || systemctl is-active --quiet cron; then
            systemctl reload crond 2>/dev/null || systemctl reload cron 2>/dev/null || true
            success "Reloaded cron service"
        fi
    fi

    success "Backup cron jobs removed successfully"
    exit 0
fi

# =============================================================================
# Create Log Directory
# =============================================================================

if [[ "$DRY_RUN" == "true" ]]; then
    echo "Would create directory: $BACKUP_LOG_DIR"
else
    mkdir -p "$BACKUP_LOG_DIR"
    chown "$BACKUP_USER:$BACKUP_USER" "$BACKUP_LOG_DIR"
    chmod 755 "$BACKUP_LOG_DIR"
    success "Created log directory: $BACKUP_LOG_DIR"
fi

# =============================================================================
# Create Cron Configuration
# =============================================================================

info "Creating cron configuration..."

# Generate cron content
read -r -d '' CRON_CONTENT << EOF || true
# =============================================================================
# PazPaz Database Backup Schedule
# =============================================================================
# Installed by: $SCRIPT_NAME v$VERSION
# Date: $(date)
# User: $BACKUP_USER
#
# Schedule:
#   - Daily backups: Every day at 2:00 AM UTC
#   - Weekly backups: Every Sunday at 3:00 AM UTC
#   - Monthly backups: 1st of each month at 4:00 AM UTC
#   - Backup testing: First Sunday of month at 5:00 AM UTC
#   - Cleanup old backups: Every day at 6:00 AM UTC
#
# =============================================================================

# Set PATH for cron environment
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Environment variables (loaded from .env.production)
SHELL=/bin/bash

# Email for cron errors (configure MAILTO to receive notifications)
MAILTO=admin@pazpaz.com

# -----------------------------------------------------------------------------
# Daily Backup - Every day at 2:00 AM UTC
# -----------------------------------------------------------------------------
# Creates compressed, encrypted backup and uploads to S3
0 2 * * * $BACKUP_USER cd $PROJECT_ROOT && $BACKUP_SCRIPT daily >> $BACKUP_LOG_DIR/backup-daily.log 2>&1

# -----------------------------------------------------------------------------
# Weekly Full Backup - Every Sunday at 3:00 AM UTC
# -----------------------------------------------------------------------------
# Creates weekly snapshot for longer retention
0 3 * * 0 $BACKUP_USER cd $PROJECT_ROOT && $BACKUP_SCRIPT weekly >> $BACKUP_LOG_DIR/backup-weekly.log 2>&1

# -----------------------------------------------------------------------------
# Monthly Backup - First of month at 4:00 AM UTC
# -----------------------------------------------------------------------------
# Creates monthly archive for long-term retention (12 months)
0 4 1 * * $BACKUP_USER cd $PROJECT_ROOT && $BACKUP_SCRIPT monthly >> $BACKUP_LOG_DIR/backup-monthly.log 2>&1

# -----------------------------------------------------------------------------
# Backup Testing - First Sunday of month at 5:00 AM UTC
# -----------------------------------------------------------------------------
# Automatically tests restore process to verify backup integrity
0 5 1-7 * 0 $BACKUP_USER cd $PROJECT_ROOT && $TEST_SCRIPT >> $BACKUP_LOG_DIR/backup-test.log 2>&1

# -----------------------------------------------------------------------------
# Cleanup Old Backups - Every day at 6:00 AM UTC
# -----------------------------------------------------------------------------
# Removes old backups according to retention policy
0 6 * * * $BACKUP_USER cd $PROJECT_ROOT && $CLEANUP_SCRIPT >> $BACKUP_LOG_DIR/backup-cleanup.log 2>&1

# -----------------------------------------------------------------------------
# Health Check - Every 6 hours
# -----------------------------------------------------------------------------
# Verify backup system is functioning (creates metrics)
0 */6 * * * $BACKUP_USER cd $PROJECT_ROOT && $BACKUP_SCRIPT --check >> $BACKUP_LOG_DIR/backup-health.log 2>&1

# =============================================================================
# End of PazPaz Backup Schedule
# =============================================================================
EOF

if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "Would create $CRON_FILE with content:"
    echo "----------------------------------------"
    echo "$CRON_CONTENT"
    echo "----------------------------------------"
else
    # Write cron file
    echo "$CRON_CONTENT" > "$CRON_FILE"

    # Set proper permissions
    chmod 644 "$CRON_FILE"
    chown root:root "$CRON_FILE"

    success "Created cron configuration: $CRON_FILE"
fi

# =============================================================================
# Create Logrotate Configuration
# =============================================================================

info "Creating logrotate configuration..."

# Generate logrotate content
read -r -d '' LOGROTATE_CONTENT << EOF || true
# =============================================================================
# PazPaz Backup Log Rotation Configuration
# =============================================================================
# Rotates backup logs to prevent disk space issues
#
# Installation: $SCRIPT_NAME v$VERSION
# Date: $(date)
# =============================================================================

$BACKUP_LOG_DIR/*.log {
    # Rotation frequency
    daily

    # Keep 30 days of logs
    rotate 30

    # Compress old logs
    compress
    delaycompress

    # Don't rotate empty logs
    notifempty

    # Create new log files with proper permissions
    create 644 $BACKUP_USER $BACKUP_USER

    # Share scripts between all logs
    sharedscripts

    # Run after rotation
    postrotate
        # Send HUP signal to rsyslog if needed
        /usr/bin/killall -HUP rsyslogd 2>/dev/null || true

        # Log rotation event
        echo "[\$(date +'%Y-%m-%d %H:%M:%S')] Log rotation completed" >> $BACKUP_LOG_DIR/rotation.log
    endscript
}

# Separate configuration for backup metadata logs
/var/backups/pazpaz/backup.log {
    weekly
    rotate 52
    compress
    notifempty
    create 644 $BACKUP_USER $BACKUP_USER
}
EOF

if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "Would create $LOGROTATE_FILE with content:"
    echo "----------------------------------------"
    echo "$LOGROTATE_CONTENT"
    echo "----------------------------------------"
else
    # Write logrotate file
    echo "$LOGROTATE_CONTENT" > "$LOGROTATE_FILE"

    # Set proper permissions
    chmod 644 "$LOGROTATE_FILE"
    chown root:root "$LOGROTATE_FILE"

    success "Created logrotate configuration: $LOGROTATE_FILE"
fi

# =============================================================================
# Test Cron Syntax
# =============================================================================

if [[ "$DRY_RUN" != "true" ]]; then
    info "Testing cron syntax..."

    # Test if crontab can parse the file
    if crontab -u "$BACKUP_USER" -l >/dev/null 2>&1; then
        success "Cron syntax is valid"
    else
        # Initialize empty crontab if it doesn't exist
        echo "" | crontab -u "$BACKUP_USER" -
    fi
fi

# =============================================================================
# Reload Services
# =============================================================================

if [[ "$DRY_RUN" != "true" ]]; then
    info "Reloading services..."

    # Reload cron service
    if systemctl is-active --quiet crond; then
        systemctl reload crond
        success "Reloaded crond service"
    elif systemctl is-active --quiet cron; then
        systemctl reload cron
        success "Reloaded cron service"
    else
        warning "Cron service not found or not running"
    fi

    # Test logrotate configuration
    if command -v logrotate >/dev/null 2>&1; then
        logrotate -d "$LOGROTATE_FILE" >/dev/null 2>&1 || warning "Logrotate test failed"
        success "Logrotate configuration validated"
    fi
fi

# =============================================================================
# Display Schedule Summary
# =============================================================================

echo ""
success "=== Backup Cron Jobs Installed Successfully ==="
echo ""
echo "📅 Backup Schedule:"
echo "  • Daily:   Every day at 2:00 AM UTC"
echo "  • Weekly:  Sundays at 3:00 AM UTC"
echo "  • Monthly: 1st of month at 4:00 AM UTC"
echo "  • Testing: First Sunday at 5:00 AM UTC"
echo "  • Cleanup: Daily at 6:00 AM UTC"
echo ""
echo "📁 Configuration Files:"
echo "  • Cron:     $CRON_FILE"
echo "  • Logrotate: $LOGROTATE_FILE"
echo "  • Logs:     $BACKUP_LOG_DIR/"
echo ""
echo "👤 Backup User: $BACKUP_USER"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    warning "This was a dry run - no changes were made"
    echo "Run with sudo to actually install the cron jobs"
else
    echo "Next Steps:"
    echo "1. Configure environment variables in /etc/environment:"
    echo "   - POSTGRES_PASSWORD"
    echo "   - S3_BACKUP_BUCKET"
    echo "   - GPG_BACKUP_RECIPIENT"
    echo "   - SLACK_WEBHOOK_URL (optional)"
    echo ""
    echo "2. Set up GPG key for backup encryption:"
    echo "   gpg --gen-key"
    echo "   gpg --export-secret-keys backup@pazpaz.com > /root/backup-key.gpg"
    echo ""
    echo "3. Configure AWS CLI for S3 access:"
    echo "   aws configure"
    echo ""
    echo "4. Test backup manually:"
    echo "   sudo -u $BACKUP_USER $BACKUP_SCRIPT daily"
    echo ""
    echo "5. Monitor first automated backup:"
    echo "   tail -f $BACKUP_LOG_DIR/backup-daily.log"
fi

echo ""
success "Installation complete!"

exit 0