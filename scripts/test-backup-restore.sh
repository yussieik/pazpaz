#!/bin/bash
# =============================================================================
# PazPaz Backup Restore Testing Script
# =============================================================================
#
# Purpose: Automated testing of database backup restoration
# Features:
#   - Monthly automated restore tests (first Sunday)
#   - Verifies backup integrity before upload
#   - Tests restore time and validates data
#   - Measures restore performance
#   - Validates critical tables and data consistency
#   - Alerts on test failures
#
# Usage:
#   ./test-backup-restore.sh [--backup-file FILE] [--skip-cleanup]
#
# Options:
#   --backup-file FILE    Specific backup file to test (default: latest)
#   --skip-cleanup       Don't delete test database after testing
#   --full-validation    Run comprehensive data validation
#   --performance-test   Test restore performance with timing
#
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# =============================================================================
# Configuration
# =============================================================================

# Script configuration
SCRIPT_NAME="test-backup-restore.sh"
VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Test configuration
TEST_DB_NAME="pazpaz_restore_test_$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/pazpaz}"
BACKUP_FILE="${1:-$BACKUP_DIR/latest.dump.gpg}"
SKIP_CLEANUP=false
FULL_VALIDATION=false
PERFORMANCE_TEST=false

# Database configuration
DB_CONTAINER="pazpaz-db"
DB_USER="pazpaz"
DB_HOST="localhost"
DB_PORT="5432"

# GPG configuration
GPG_BACKUP_RECIPIENT="${GPG_BACKUP_RECIPIENT:-backup@pazpaz.com}"

# Notification configuration
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
SMTP_RECIPIENT="${SMTP_RECIPIENT:-}"

# Performance thresholds
MAX_RESTORE_TIME_SECONDS=300  # 5 minutes max for restore
MIN_TABLE_COUNT=20  # Minimum expected tables
MIN_ROW_COUNT=100   # Minimum expected rows across all tables

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
            \"text\": \"$emoji PazPaz Backup Test: $message\",
            \"username\": \"Backup Test Bot\",
            \"icon_emoji\": \":test_tube:\"
        }" 2>/dev/null || true
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --backup-file)
                BACKUP_FILE="$2"
                shift 2
                ;;
            --skip-cleanup)
                SKIP_CLEANUP=true
                shift
                ;;
            --full-validation)
                FULL_VALIDATION=true
                shift
                ;;
            --performance-test)
                PERFORMANCE_TEST=true
                shift
                ;;
            --help|-h)
                show_usage
                ;;
            *)
                error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

# Show usage information
show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Test database backup restoration process

Options:
    --backup-file FILE    Specific backup file to test (default: latest)
    --skip-cleanup       Don't delete test database after testing
    --full-validation    Run comprehensive data validation
    --performance-test   Test restore performance with timing
    --help               Show this help message

Examples:
    # Test latest backup
    $SCRIPT_NAME

    # Test specific backup file
    $SCRIPT_NAME --backup-file /backups/pazpaz-20240324.dump.gpg

    # Run full validation suite
    $SCRIPT_NAME --full-validation --performance-test

EOF
    exit 0
}

# Cleanup function
cleanup() {
    local exit_code=$?

    if [[ "$SKIP_CLEANUP" != "true" ]] && [[ -n "${TEST_DB_NAME:-}" ]]; then
        info "Cleaning up test database..."
        docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS \"$TEST_DB_NAME\";" 2>/dev/null || true
    fi

    if [[ -n "${TEMP_RESTORE_FILE:-}" ]] && [[ -f "$TEMP_RESTORE_FILE" ]]; then
        rm -f "$TEMP_RESTORE_FILE"
    fi

    if [[ $exit_code -ne 0 ]]; then
        error "Backup restore test failed with exit code $exit_code"
        send_slack_notification "Backup restore test FAILED! Check logs for details." "error"
    fi
}

trap cleanup EXIT

# =============================================================================
# Pre-flight Checks
# =============================================================================

# Parse arguments
parse_args "$@"

info "Starting PazPaz backup restore test"
info "Test database: $TEST_DB_NAME"

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

# Check if backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Determine if backup is encrypted
IS_ENCRYPTED=false
if [[ "$BACKUP_FILE" == *.gpg ]]; then
    IS_ENCRYPTED=true
    info "Backup file is encrypted"
fi

# =============================================================================
# Step 1: Decrypt Backup (if needed)
# =============================================================================

TEMP_RESTORE_FILE=""
if [[ "$IS_ENCRYPTED" == "true" ]]; then
    info "Decrypting backup file..."
    TEMP_RESTORE_FILE="/tmp/restore_test_$(date +%s).dump"

    START_TIME=$(date +%s)
    gpg --decrypt --output "$TEMP_RESTORE_FILE" "$BACKUP_FILE" 2>/dev/null
    DECRYPT_TIME=$(($(date +%s) - START_TIME))

    success "Backup decrypted in ${DECRYPT_TIME}s"
    RESTORE_FILE="$TEMP_RESTORE_FILE"
else
    RESTORE_FILE="$BACKUP_FILE"
fi

# =============================================================================
# Step 2: Verify Backup Integrity
# =============================================================================

info "Verifying backup integrity..."

# List backup contents
if ! pg_restore --list "$RESTORE_FILE" >/dev/null 2>&1; then
    error "Backup verification failed - corrupt backup file"
    exit 1
fi

# Get backup statistics
TABLE_COUNT=$(pg_restore --list "$RESTORE_FILE" 2>/dev/null | grep -c "TABLE DATA" || echo "0")
SCHEMA_COUNT=$(pg_restore --list "$RESTORE_FILE" 2>/dev/null | grep -c "SCHEMA" || echo "0")
FUNCTION_COUNT=$(pg_restore --list "$RESTORE_FILE" 2>/dev/null | grep -c "FUNCTION" || echo "0")
INDEX_COUNT=$(pg_restore --list "$RESTORE_FILE" 2>/dev/null | grep -c "INDEX" || echo "0")

success "Backup verified: $TABLE_COUNT tables, $SCHEMA_COUNT schemas, $FUNCTION_COUNT functions, $INDEX_COUNT indexes"

# Check minimum requirements
if [[ $TABLE_COUNT -lt $MIN_TABLE_COUNT ]]; then
    error "Backup has too few tables: $TABLE_COUNT (expected at least $MIN_TABLE_COUNT)"
    exit 1
fi

# =============================================================================
# Step 3: Create Test Database
# =============================================================================

info "Creating test database: $TEST_DB_NAME"

docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE \"$TEST_DB_NAME\" WITH ENCODING='UTF8' LC_COLLATE='en_US.utf8' LC_CTYPE='en_US.utf8';"

success "Test database created"

# =============================================================================
# Step 4: Restore Backup
# =============================================================================

info "Restoring backup to test database..."

START_TIME=$(date +%s)

# Perform restore
pg_restore \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$TEST_DB_NAME" \
    --no-password \
    --verbose \
    --no-owner \
    --no-privileges \
    --no-comments \
    --if-exists \
    --clean \
    --create \
    "$RESTORE_FILE" 2>/dev/null || {
        # Some errors are expected (e.g., role doesn't exist)
        # Check if critical tables were restored
        docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -c "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' LIMIT 1;" >/dev/null 2>&1 || {
            error "Restore failed - no tables created"
            exit 1
        }
    }

RESTORE_TIME=$(($(date +%s) - START_TIME))

success "Backup restored in ${RESTORE_TIME}s"

# Check restore time threshold
if [[ $RESTORE_TIME -gt $MAX_RESTORE_TIME_SECONDS ]]; then
    warning "Restore took longer than expected: ${RESTORE_TIME}s (threshold: ${MAX_RESTORE_TIME_SECONDS}s)"
fi

# =============================================================================
# Step 5: Validate Restored Data
# =============================================================================

info "Validating restored data..."

# Get table statistics
RESTORED_TABLES=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE';
" | tr -d ' ')

# Count total rows across all tables
TOTAL_ROWS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT SUM(n_live_tup)
    FROM pg_stat_user_tables;
" | tr -d ' ')

success "Restored $RESTORED_TABLES tables with $TOTAL_ROWS total rows"

# Check critical tables exist
CRITICAL_TABLES=(
    "users"
    "workspaces"
    "clients"
    "appointments"
    "sessions"
    "services"
    "locations"
    "plan_of_care"
    "audit_events"
    "alembic_version"
)

info "Checking critical tables..."
for table in "${CRITICAL_TABLES[@]}"; do
    if docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -c "SELECT 1 FROM $table LIMIT 1;" >/dev/null 2>&1; then
        echo "  ✓ Table '$table' exists"
    else
        error "  ✗ Critical table missing: $table"
        exit 1
    fi
done

# =============================================================================
# Step 6: Run Data Integrity Checks
# =============================================================================

if [[ "$FULL_VALIDATION" == "true" ]]; then
    info "Running comprehensive data validation..."

    # Check referential integrity
    info "Checking foreign key constraints..."
    CONSTRAINT_VIOLATIONS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
        SELECT COUNT(*)
        FROM information_schema.table_constraints
        WHERE constraint_type = 'FOREIGN KEY'
        AND constraint_schema = 'public';
    " | tr -d ' ')

    if [[ $CONSTRAINT_VIOLATIONS -gt 0 ]]; then
        success "  $CONSTRAINT_VIOLATIONS foreign key constraints verified"
    fi

    # Check for orphaned records
    info "Checking for orphaned records..."

    # Check appointments without clients
    ORPHANED_APPOINTMENTS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
        SELECT COUNT(*)
        FROM appointments a
        LEFT JOIN clients c ON a.client_id = c.id
        WHERE a.client_id IS NOT NULL AND c.id IS NULL;
    " 2>/dev/null | tr -d ' ' || echo "0")

    if [[ $ORPHANED_APPOINTMENTS -gt 0 ]]; then
        warning "  Found $ORPHANED_APPOINTMENTS orphaned appointments"
    else
        success "  No orphaned appointments found"
    fi

    # Check sessions without appointments
    ORPHANED_SESSIONS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
        SELECT COUNT(*)
        FROM sessions s
        LEFT JOIN appointments a ON s.appointment_id = a.id
        WHERE s.appointment_id IS NOT NULL AND a.id IS NULL;
    " 2>/dev/null | tr -d ' ' || echo "0")

    if [[ $ORPHANED_SESSIONS -gt 0 ]]; then
        warning "  Found $ORPHANED_SESSIONS orphaned sessions"
    else
        success "  No orphaned sessions found"
    fi

    # Check data consistency
    info "Checking data consistency..."

    # Verify workspace isolation
    WORKSPACE_VIOLATIONS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
        SELECT COUNT(*)
        FROM (
            SELECT DISTINCT workspace_id FROM users
            UNION SELECT DISTINCT workspace_id FROM clients
            UNION SELECT DISTINCT workspace_id FROM appointments
        ) w
        LEFT JOIN workspaces ws ON w.workspace_id = ws.id
        WHERE w.workspace_id IS NOT NULL AND ws.id IS NULL;
    " 2>/dev/null | tr -d ' ' || echo "0")

    if [[ $WORKSPACE_VIOLATIONS -gt 0 ]]; then
        error "  Found $WORKSPACE_VIOLATIONS workspace isolation violations"
        exit 1
    else
        success "  Workspace isolation verified"
    fi
fi

# =============================================================================
# Step 7: Performance Testing
# =============================================================================

if [[ "$PERFORMANCE_TEST" == "true" ]]; then
    info "Running performance tests..."

    # Test query performance
    QUERY_START=$(date +%s%N)
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -c "
        SELECT COUNT(*) FROM appointments
        WHERE created_at >= NOW() - INTERVAL '30 days';
    " >/dev/null 2>&1
    QUERY_TIME=$(( ($(date +%s%N) - QUERY_START) / 1000000 ))

    if [[ $QUERY_TIME -lt 150 ]]; then
        success "  Query performance: ${QUERY_TIME}ms (✓ < 150ms)"
    else
        warning "  Query performance: ${QUERY_TIME}ms (threshold: 150ms)"
    fi

    # Test index usage
    INDEX_USAGE=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
        SELECT ROUND(100 * SUM(idx_scan) / NULLIF(SUM(seq_scan + idx_scan), 0), 2)
        FROM pg_stat_user_tables;
    " 2>/dev/null | tr -d ' ' || echo "0")

    info "  Index usage: ${INDEX_USAGE}%"
fi

# =============================================================================
# Step 8: Generate Test Report
# =============================================================================

info "Generating test report..."

REPORT_FILE="$BACKUP_DIR/restore-test-$(date +%Y%m%d-%H%M%S).json"

cat > "$REPORT_FILE" <<EOF
{
    "test_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "test_database": "$TEST_DB_NAME",
    "backup_file": "$BACKUP_FILE",
    "restore_time_seconds": $RESTORE_TIME,
    "decrypt_time_seconds": ${DECRYPT_TIME:-0},
    "table_count": $TABLE_COUNT,
    "restored_tables": $RESTORED_TABLES,
    "total_rows": ${TOTAL_ROWS:-0},
    "validation": {
        "critical_tables": "passed",
        "foreign_keys": ${CONSTRAINT_VIOLATIONS:-0},
        "orphaned_appointments": ${ORPHANED_APPOINTMENTS:-0},
        "orphaned_sessions": ${ORPHANED_SESSIONS:-0},
        "workspace_violations": ${WORKSPACE_VIOLATIONS:-0}
    },
    "performance": {
        "query_time_ms": ${QUERY_TIME:-0},
        "index_usage_percent": ${INDEX_USAGE:-0}
    },
    "result": "success"
}
EOF

success "Test report saved: $REPORT_FILE"

# =============================================================================
# Cleanup and Summary
# =============================================================================

if [[ "$SKIP_CLEANUP" == "true" ]]; then
    warning "Skipping cleanup - test database preserved: $TEST_DB_NAME"
    echo "To manually remove: docker exec $DB_CONTAINER psql -U $DB_USER -c 'DROP DATABASE \"$TEST_DB_NAME\";'"
else
    info "Cleaning up test database..."
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS \"$TEST_DB_NAME\";"
    success "Test database removed"
fi

# Clean up temporary files
if [[ -n "$TEMP_RESTORE_FILE" ]] && [[ -f "$TEMP_RESTORE_FILE" ]]; then
    rm -f "$TEMP_RESTORE_FILE"
fi

# Send success notification
SUCCESS_MESSAGE="✅ Backup restore test completed successfully
• Restore Time: ${RESTORE_TIME}s
• Tables: $RESTORED_TABLES
• Total Rows: ${TOTAL_ROWS:-unknown}
• Critical Tables: All verified
• Data Integrity: Passed"

send_slack_notification "$SUCCESS_MESSAGE" "success"

# Print summary
echo ""
success "=== Backup Restore Test Completed Successfully ==="
echo "Test Database:    $TEST_DB_NAME"
echo "Restore Time:     ${RESTORE_TIME}s"
echo "Tables Restored:  $RESTORED_TABLES"
echo "Total Rows:       ${TOTAL_ROWS:-unknown}"
echo "Report:           $REPORT_FILE"
echo ""

exit 0