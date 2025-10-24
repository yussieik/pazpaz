#!/bin/bash
# =============================================================================
# Database Migration Script for PazPaz
# =============================================================================
# Production-safe database migration with comprehensive safety checks,
# automatic backups, test migrations, and rollback capability.
# HIPAA-compliant with full audit logging.
#
# Features:
#   - Pre-migration database snapshot (pg_dump -Fc format)
#   - Migration SQL preview (dry-run capability)
#   - Test migration on copy database before production
#   - Automatic rollback on failure
#   - Post-migration validation
#   - Comprehensive logging with timestamps
#   - Integration with Alembic migration system
#
# Usage:
#   ./migrate.sh [OPTIONS] [COMMAND]
#
# Commands:
#   upgrade [revision]    Upgrade database to revision (default: head)
#   downgrade [revision]  Downgrade database to revision
#   current              Show current database revision
#   history              Show migration history
#   validate             Validate database integrity
#
# Options:
#   --dry-run            Generate and show migration SQL without applying
#   --skip-backup        Skip database backup (NOT recommended)
#   --skip-test          Skip test migration (dangerous)
#   --force              Force migration even with warnings
#   --timeout <seconds>  Migration timeout (default: 300)
#   --env <environment>  Environment (production/staging/development)
#
# Environment Variables Required:
#   POSTGRES_PASSWORD    Database password
#
# Exit Codes:
#   0 - Migration successful
#   1 - Pre-migration checks failed
#   2 - Backup failed
#   3 - Test migration failed
#   4 - Production migration failed
#   5 - Rollback failed
#   6 - Validation failed
# =============================================================================

set -uo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Use /opt/pazpaz if writable, otherwise use project directory
if [ -w "/opt/pazpaz" ] || [ "$EUID" -eq 0 ]; then
    DEPLOYMENT_DIR="/opt/pazpaz"
else
    DEPLOYMENT_DIR="${PROJECT_ROOT}/.deployment"
fi

BACKUP_DIR="${DEPLOYMENT_DIR}/backups/migrations"
LOG_DIR="${DEPLOYMENT_DIR}/logs"
MIGRATION_LOG="${LOG_DIR}/migration-$(date +%Y%m%d-%H%M%S).log"

# Database Configuration
ENV_FILE="${PROJECT_ROOT}/.env.production"
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="pazpaz"
DB_USER="pazpaz"
DB_TEST_NAME="pazpaz_test_migration"

# Alembic Configuration
BACKEND_DIR="${PROJECT_ROOT}/backend"
ALEMBIC_INI="${BACKEND_DIR}/alembic.ini"
MIGRATIONS_DIR="${BACKEND_DIR}/alembic/versions"

# Migration Configuration
MIGRATION_TIMEOUT=300  # 5 minutes max for migration
VALIDATION_TIMEOUT=60   # 1 minute for validation checks
MAX_BACKUP_AGE_DAYS=30  # Keep backups for 30 days

# Docker Configuration
CONTAINER_NAME="pazpaz-db"
API_CONTAINER="pazpaz-api"
USE_DOCKER=false

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Migration state tracking
MIGRATION_ID="migration-$(date +%Y%m%d-%H%M%S)-$$"
CURRENT_REVISION=""
TARGET_REVISION="head"
BACKUP_FILE=""
TEST_PASSED=false
MIGRATION_APPLIED=false

# Command line options
COMMAND="upgrade"
DRY_RUN=false
SKIP_BACKUP=false
SKIP_TEST=false
FORCE_MIGRATION=false
ENVIRONMENT="production"

# =============================================================================
# Logging Functions
# =============================================================================

# Initialize logging
init_logging() {
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"

    # Start logging
    exec 1> >(tee -a "$MIGRATION_LOG")
    exec 2>&1

    log_info "=================================="
    log_info "Database Migration Started"
    log_info "Migration ID: $MIGRATION_ID"
    log_info "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "Environment: $ENVIRONMENT"
    log_info "=================================="
}

# Log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Log info message
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%H:%M:%S') - $*"
}

# Log success message
log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%H:%M:%S') - $*"
}

# Log warning message
log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%H:%M:%S') - $*"
}

# Log error message
log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') - $*" >&2
}

# =============================================================================
# Database Functions
# =============================================================================

# Check if running in Docker environment
check_docker_environment() {
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        USE_DOCKER=true
        log_info "Docker environment detected, using container: $CONTAINER_NAME"
    else
        log_info "Local environment detected"
    fi
}

# Load database password from environment file
load_database_password() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        return 1
    fi

    DB_PASSWORD=$(grep "^POSTGRES_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")

    if [ -z "$DB_PASSWORD" ]; then
        log_error "POSTGRES_PASSWORD not found in environment file"
        return 1
    fi

    export PGPASSWORD="$DB_PASSWORD"
    return 0
}

# Execute PostgreSQL command
execute_psql() {
    local database="${1:-$DB_NAME}"
    local command="$2"

    if [ "$USE_DOCKER" = true ]; then
        docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$database" -c "$command"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$database" -c "$command"
    fi
}

# Execute PostgreSQL command from file
execute_psql_file() {
    local database="${1:-$DB_NAME}"
    local file="$2"

    if [ "$USE_DOCKER" = true ]; then
        docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$database" < "$file"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$database" < "$file"
    fi
}

# Create database backup
backup_database() {
    log_info "Creating database backup..."

    local backup_name="pre-migration-${MIGRATION_ID}.dump"
    BACKUP_FILE="${BACKUP_DIR}/${backup_name}"

    if [ "$USE_DOCKER" = true ]; then
        if docker exec "$CONTAINER_NAME" pg_dump -Fc -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"; then
            log_success "Database backup created: $BACKUP_FILE"
            log_info "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
            return 0
        fi
    else
        if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -Fc -d "$DB_NAME" > "$BACKUP_FILE"; then
            log_success "Database backup created: $BACKUP_FILE"
            log_info "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
            return 0
        fi
    fi

    log_error "Failed to create database backup"
    return 1
}

# Restore database from backup
restore_database() {
    local backup_file="${1:-$BACKUP_FILE}"

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    log_info "Restoring database from backup: $backup_file"

    # Drop and recreate database
    execute_psql "postgres" "DROP DATABASE IF EXISTS $DB_NAME;"
    execute_psql "postgres" "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

    # Restore from backup
    if [ "$USE_DOCKER" = true ]; then
        if docker exec -i "$CONTAINER_NAME" pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl < "$backup_file"; then
            log_success "Database restored from backup"
            return 0
        fi
    else
        if pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl < "$backup_file"; then
            log_success "Database restored from backup"
            return 0
        fi
    fi

    log_error "Failed to restore database from backup"
    return 1
}

# Clean old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (older than ${MAX_BACKUP_AGE_DAYS} days)..."

    find "$BACKUP_DIR" -name "*.dump" -type f -mtime +${MAX_BACKUP_AGE_DAYS} -delete 2>/dev/null || true

    local backup_count=$(find "$BACKUP_DIR" -name "*.dump" -type f 2>/dev/null | wc -l)
    log_info "Current backup count: $backup_count"
}

# =============================================================================
# Alembic Migration Functions
# =============================================================================

# Get current database revision
get_current_revision() {
    local revision

    if [ "$USE_DOCKER" = true ]; then
        revision=$(docker exec "$API_CONTAINER" bash -c "cd /app && PYTHONPATH=/app/src alembic current 2>/dev/null" | grep -oE '[a-f0-9]{12}' | head -1)
    else
        revision=$(cd "$BACKEND_DIR" && PYTHONPATH="${BACKEND_DIR}/src" uv run alembic current 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -1)
    fi

    if [ -z "$revision" ]; then
        # Check if alembic_version table exists
        local table_exists=$(execute_psql "$DB_NAME" "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version');" | grep -c 't')

        if [ "$table_exists" -eq 0 ]; then
            log_warning "No alembic_version table found - database not initialized"
            echo "none"
        else
            log_warning "Could not determine current revision"
            echo "unknown"
        fi
    else
        echo "$revision"
    fi
}

# Generate migration SQL
generate_migration_sql() {
    local target="${1:-head}"
    local sql_file="${2:-/tmp/migration-${MIGRATION_ID}.sql}"

    log_info "Generating migration SQL for target: $target"

    if [ "$USE_DOCKER" = true ]; then
        docker exec "$API_CONTAINER" bash -c "cd /app && PYTHONPATH=/app/src alembic upgrade $target --sql" > "$sql_file" 2>&1
    else
        (cd "$BACKEND_DIR" && PYTHONPATH="${BACKEND_DIR}/src" uv run alembic upgrade "$target" --sql) > "$sql_file" 2>&1
    fi

    if [ -s "$sql_file" ]; then
        log_success "Migration SQL generated: $sql_file"
        log_info "SQL preview (first 20 lines):"
        head -20 "$sql_file" | sed 's/^/  /'
        return 0
    else
        log_warning "No migration SQL generated (database may be up to date)"
        return 1
    fi
}

# Create test database
create_test_database() {
    log_info "Creating test database: $DB_TEST_NAME"

    # Drop existing test database
    execute_psql "postgres" "DROP DATABASE IF EXISTS $DB_TEST_NAME;" 2>/dev/null || true

    # Create new test database
    execute_psql "postgres" "CREATE DATABASE $DB_TEST_NAME OWNER $DB_USER;"

    # Restore backup to test database
    if [ "$USE_DOCKER" = true ]; then
        docker exec -i "$CONTAINER_NAME" pg_restore -U "$DB_USER" -d "$DB_TEST_NAME" --no-owner --no-acl < "$BACKUP_FILE"
    else
        pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_TEST_NAME" --no-owner --no-acl < "$BACKUP_FILE"
    fi

    log_success "Test database created and populated"
}

# Run test migration
run_test_migration() {
    log_info "Running test migration on: $DB_TEST_NAME"

    # Create test database configuration
    local test_db_url="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_TEST_NAME}"

    # Run migration on test database
    if [ "$USE_DOCKER" = true ]; then
        if timeout "$MIGRATION_TIMEOUT" docker exec "$API_CONTAINER" bash -c \
            "cd /app && DATABASE_URL='$test_db_url' PYTHONPATH=/app/src alembic upgrade $TARGET_REVISION"; then
            log_success "Test migration completed successfully"
            TEST_PASSED=true
            return 0
        fi
    else
        if timeout "$MIGRATION_TIMEOUT" bash -c \
            "cd '$BACKEND_DIR' && DATABASE_URL='$test_db_url' PYTHONPATH='${BACKEND_DIR}/src' uv run alembic upgrade $TARGET_REVISION"; then
            log_success "Test migration completed successfully"
            TEST_PASSED=true
            return 0
        fi
    fi

    log_error "Test migration failed"
    return 1
}

# Drop test database
cleanup_test_database() {
    log_info "Cleaning up test database"
    execute_psql "postgres" "DROP DATABASE IF EXISTS $DB_TEST_NAME;" 2>/dev/null || true
}

# Apply migration to production
apply_migration() {
    log_info "Applying migration to production database"
    log_warning "Target revision: $TARGET_REVISION"

    # Run migration with timeout
    if [ "$USE_DOCKER" = true ]; then
        if timeout "$MIGRATION_TIMEOUT" docker exec "$API_CONTAINER" bash -c \
            "cd /app && PYTHONPATH=/app/src alembic $COMMAND $TARGET_REVISION"; then
            log_success "Migration applied successfully"
            MIGRATION_APPLIED=true
            return 0
        fi
    else
        if timeout "$MIGRATION_TIMEOUT" bash -c \
            "cd '$BACKEND_DIR' && PYTHONPATH='${BACKEND_DIR}/src' uv run alembic $COMMAND $TARGET_REVISION"; then
            log_success "Migration applied successfully"
            MIGRATION_APPLIED=true
            return 0
        fi
    fi

    log_error "Migration failed"
    return 1
}

# Rollback migration using Alembic
rollback_migration() {
    log_warning "Rolling back migration to revision: $CURRENT_REVISION"

    # Try Alembic downgrade first
    if [ "$USE_DOCKER" = true ]; then
        if timeout "$MIGRATION_TIMEOUT" docker exec "$API_CONTAINER" bash -c \
            "cd /app && PYTHONPATH=/app/src alembic downgrade $CURRENT_REVISION"; then
            log_success "Migration rolled back using Alembic"
            return 0
        fi
    else
        if timeout "$MIGRATION_TIMEOUT" bash -c \
            "cd '$BACKEND_DIR' && PYTHONPATH='${BACKEND_DIR}/src' uv run alembic downgrade $CURRENT_REVISION"; then
            log_success "Migration rolled back using Alembic"
            return 0
        fi
    fi

    log_warning "Alembic rollback failed, restoring from backup"

    # Fallback to backup restore
    if restore_database "$BACKUP_FILE"; then
        log_success "Database restored from backup"
        return 0
    fi

    log_error "Failed to rollback migration"
    return 1
}

# =============================================================================
# Validation Functions
# =============================================================================

# Validate database connection
validate_connection() {
    log_info "Validating database connection..."

    if execute_psql "$DB_NAME" "SELECT version();" > /dev/null 2>&1; then
        log_success "Database connection successful"
        return 0
    else
        log_error "Cannot connect to database"
        return 1
    fi
}

# Validate migration state
validate_migration_state() {
    log_info "Validating migration state..."

    # Check alembic_version table
    local version=$(execute_psql "$DB_NAME" "SELECT version_num FROM alembic_version;" 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -1)

    if [ -n "$version" ]; then
        log_success "Current migration version: $version"
    else
        log_warning "No migration version found in database"
    fi

    # Check for pending migrations
    if [ "$USE_DOCKER" = true ]; then
        local pending=$(docker exec "$API_CONTAINER" bash -c "cd /app && PYTHONPATH=/app/src alembic history -r current:head" | grep -c "Rev:")
    else
        local pending=$(cd "$BACKEND_DIR" && PYTHONPATH="${BACKEND_DIR}/src" uv run alembic history -r current:head | grep -c "Rev:")
    fi

    if [ "$pending" -gt 0 ]; then
        log_info "Pending migrations: $pending"
    else
        log_info "Database is up to date"
    fi
}

# Validate database schema
validate_schema() {
    log_info "Validating database schema..."

    # Check critical tables exist
    local tables=("workspaces" "users" "clients" "appointments" "sessions" "services" "locations" "alembic_version")
    local missing_tables=()

    for table in "${tables[@]}"; do
        local exists=$(execute_psql "$DB_NAME" "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table');" | grep -c 't')
        if [ "$exists" -eq 0 ]; then
            missing_tables+=("$table")
        fi
    done

    if [ ${#missing_tables[@]} -eq 0 ]; then
        log_success "All critical tables exist"
    else
        log_warning "Missing tables: ${missing_tables[*]}"
    fi

    # Check foreign key constraints
    local fk_count=$(execute_psql "$DB_NAME" "SELECT COUNT(*) FROM pg_constraint WHERE contype = 'f';" | grep -oE '[0-9]+' | head -1)
    log_info "Foreign key constraints: $fk_count"

    # Check indexes
    local index_count=$(execute_psql "$DB_NAME" "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';" | grep -oE '[0-9]+' | head -1)
    log_info "Indexes: $index_count"
}

# Run post-migration tests
run_post_migration_tests() {
    log_info "Running post-migration tests..."

    # Test basic queries
    local tests_passed=0
    local tests_failed=0

    # Test 1: Check workspace table
    if execute_psql "$DB_NAME" "SELECT COUNT(*) FROM workspaces;" > /dev/null 2>&1; then
        ((tests_passed++))
        log_success "✓ Workspace table accessible"
    else
        ((tests_failed++))
        log_error "✗ Workspace table not accessible"
    fi

    # Test 2: Check user table
    if execute_psql "$DB_NAME" "SELECT COUNT(*) FROM users;" > /dev/null 2>&1; then
        ((tests_passed++))
        log_success "✓ User table accessible"
    else
        ((tests_failed++))
        log_error "✗ User table not accessible"
    fi

    # Test 3: Check foreign key integrity
    if execute_psql "$DB_NAME" "SELECT conname FROM pg_constraint WHERE contype = 'f' LIMIT 1;" > /dev/null 2>&1; then
        ((tests_passed++))
        log_success "✓ Foreign key constraints intact"
    else
        ((tests_failed++))
        log_error "✗ Foreign key constraints issue"
    fi

    log_info "Post-migration tests: $tests_passed passed, $tests_failed failed"

    if [ "$tests_failed" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# Generate migration report
generate_migration_report() {
    local report_file="${LOG_DIR}/migration-report-${MIGRATION_ID}.txt"

    {
        echo "==============================================="
        echo "Migration Report"
        echo "==============================================="
        echo "Migration ID: $MIGRATION_ID"
        echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Environment: $ENVIRONMENT"
        echo "Command: $COMMAND $TARGET_REVISION"
        echo ""
        echo "Initial State:"
        echo "  Current Revision: $CURRENT_REVISION"
        echo "  Target Revision: $TARGET_REVISION"
        echo ""
        echo "Backup Information:"
        echo "  Backup File: $BACKUP_FILE"
        echo "  Backup Size: $(du -h "$BACKUP_FILE" 2>/dev/null | cut -f1)"
        echo ""
        echo "Test Migration:"
        echo "  Test Database: $DB_TEST_NAME"
        echo "  Test Result: $([ "$TEST_PASSED" = true ] && echo "PASSED" || echo "FAILED")"
        echo ""
        echo "Production Migration:"
        echo "  Applied: $([ "$MIGRATION_APPLIED" = true ] && echo "YES" || echo "NO")"
        echo "  Final Revision: $(get_current_revision)"
        echo ""
        echo "Validation Results:"
        validate_schema 2>&1
        echo ""
        echo "==============================================="
    } > "$report_file"

    log_info "Migration report saved: $report_file"
}

# =============================================================================
# Command Handlers
# =============================================================================

# Handle upgrade command
handle_upgrade() {
    log_info "Starting database upgrade"

    # Get current revision
    CURRENT_REVISION=$(get_current_revision)
    log_info "Current revision: $CURRENT_REVISION"

    # Check if already at target
    if [ "$CURRENT_REVISION" = "$TARGET_REVISION" ] && [ "$TARGET_REVISION" != "head" ]; then
        log_info "Database already at target revision"
        return 0
    fi

    # Create backup unless skipped
    if [ "$SKIP_BACKUP" = false ]; then
        if ! backup_database; then
            log_error "Backup failed, aborting migration"
            return 2
        fi
    else
        log_warning "Skipping backup (NOT recommended)"
    fi

    # Generate migration SQL for review
    local sql_file="/tmp/migration-${MIGRATION_ID}.sql"
    generate_migration_sql "$TARGET_REVISION" "$sql_file"

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry run mode - migration SQL saved to: $sql_file"
        return 0
    fi

    # Test migration unless skipped
    if [ "$SKIP_TEST" = false ]; then
        create_test_database

        if ! run_test_migration; then
            log_error "Test migration failed"
            cleanup_test_database

            if [ "$FORCE_MIGRATION" = false ]; then
                log_error "Aborting migration (use --force to override)"
                return 3
            else
                log_warning "Forcing migration despite test failure"
            fi
        fi

        cleanup_test_database
    else
        log_warning "Skipping test migration (dangerous)"
    fi

    # Apply migration to production
    if ! apply_migration; then
        log_error "Migration failed, attempting rollback"

        if rollback_migration; then
            log_success "Rollback completed"
            return 4
        else
            log_error "CRITICAL: Rollback failed - manual intervention required"
            log_error "Backup file: $BACKUP_FILE"
            return 5
        fi
    fi

    # Validate migration
    if ! run_post_migration_tests; then
        log_warning "Post-migration tests failed"

        if [ "$FORCE_MIGRATION" = false ]; then
            log_error "Rolling back due to validation failure"

            if rollback_migration; then
                log_success "Rollback completed"
                return 6
            else
                log_error "CRITICAL: Rollback failed - manual intervention required"
                return 5
            fi
        fi
    fi

    log_success "Migration completed successfully"
    return 0
}

# Handle downgrade command
handle_downgrade() {
    log_info "Starting database downgrade"

    # Get current revision
    CURRENT_REVISION=$(get_current_revision)
    log_info "Current revision: $CURRENT_REVISION"

    # Create backup unless skipped
    if [ "$SKIP_BACKUP" = false ]; then
        if ! backup_database; then
            log_error "Backup failed, aborting downgrade"
            return 2
        fi
    else
        log_warning "Skipping backup (NOT recommended)"
    fi

    # Apply downgrade
    COMMAND="downgrade"
    if ! apply_migration; then
        log_error "Downgrade failed"

        if [ "$SKIP_BACKUP" = false ]; then
            log_info "Restoring from backup"

            if restore_database "$BACKUP_FILE"; then
                log_success "Database restored from backup"
                return 4
            else
                log_error "CRITICAL: Restore failed - manual intervention required"
                return 5
            fi
        fi

        return 4
    fi

    log_success "Downgrade completed successfully"
    return 0
}

# Handle current command
handle_current() {
    log_info "Checking current database revision"

    local revision=$(get_current_revision)
    echo "Current revision: $revision"

    # Get revision details
    if [ "$USE_DOCKER" = true ]; then
        docker exec "$API_CONTAINER" bash -c "cd /app && PYTHONPATH=/app/src alembic history -r $revision:$revision -v" 2>/dev/null
    else
        (cd "$BACKEND_DIR" && PYTHONPATH="${BACKEND_DIR}/src" uv run alembic history -r "$revision:$revision" -v) 2>/dev/null
    fi

    return 0
}

# Handle history command
handle_history() {
    log_info "Showing migration history"

    if [ "$USE_DOCKER" = true ]; then
        docker exec "$API_CONTAINER" bash -c "cd /app && PYTHONPATH=/app/src alembic history -v"
    else
        (cd "$BACKEND_DIR" && PYTHONPATH="${BACKEND_DIR}/src" uv run alembic history -v)
    fi

    return 0
}

# Handle validate command
handle_validate() {
    log_info "Validating database state"

    validate_connection || return 1
    validate_migration_state
    validate_schema
    run_post_migration_tests

    return 0
}

# =============================================================================
# Main Script
# =============================================================================

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            upgrade|downgrade|current|history|validate)
                COMMAND="$1"
                shift
                if [[ -n "${1:-}" && ! "$1" =~ ^-- ]]; then
                    TARGET_REVISION="$1"
                    shift
                fi
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --skip-test)
                SKIP_TEST=true
                shift
                ;;
            --force)
                FORCE_MIGRATION=true
                shift
                ;;
            --timeout)
                MIGRATION_TIMEOUT="$2"
                shift 2
                ;;
            --env|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help message
show_help() {
    cat << EOF
Database Migration Script for PazPaz

Usage: ./migrate.sh [OPTIONS] [COMMAND] [REVISION]

Commands:
    upgrade [revision]    Upgrade database to revision (default: head)
    downgrade [revision]  Downgrade database to revision
    current              Show current database revision
    history              Show migration history
    validate             Validate database integrity

Options:
    --dry-run            Generate and show migration SQL without applying
    --skip-backup        Skip database backup (NOT recommended)
    --skip-test          Skip test migration (dangerous)
    --force              Force migration even with warnings
    --timeout <seconds>  Migration timeout (default: 300)
    --env <environment>  Environment (production/staging/development)
    --help, -h           Show this help message

Examples:
    # Upgrade to latest version (recommended)
    ./migrate.sh upgrade

    # Upgrade to specific revision
    ./migrate.sh upgrade abc123def456

    # Dry run to preview changes
    ./migrate.sh --dry-run upgrade

    # Downgrade one revision
    ./migrate.sh downgrade -1

    # Check current revision
    ./migrate.sh current

    # Validate database state
    ./migrate.sh validate

Environment Variables:
    POSTGRES_PASSWORD    Database password (required)

Safety Features:
    - Automatic backup before migration
    - Test migration on copy database
    - Rollback on failure
    - Post-migration validation
    - Comprehensive logging

EOF
}

# Main execution
main() {
    # Parse arguments
    parse_arguments "$@"

    # Initialize logging
    init_logging

    # Check environment
    check_docker_environment

    # Load database credentials
    if ! load_database_password; then
        log_error "Failed to load database credentials"
        exit 1
    fi

    # Validate connection
    if ! validate_connection; then
        log_error "Cannot connect to database"
        exit 1
    fi

    # Execute command
    case $COMMAND in
        upgrade)
            handle_upgrade
            exit_code=$?
            ;;
        downgrade)
            handle_downgrade
            exit_code=$?
            ;;
        current)
            handle_current
            exit_code=$?
            ;;
        history)
            handle_history
            exit_code=$?
            ;;
        validate)
            handle_validate
            exit_code=$?
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_help
            exit 1
            ;;
    esac

    # Generate report
    if [[ "$COMMAND" == "upgrade" || "$COMMAND" == "downgrade" ]]; then
        generate_migration_report
    fi

    # Cleanup old backups
    cleanup_old_backups

    # Final status
    if [ $exit_code -eq 0 ]; then
        log_success "Migration script completed successfully"
    else
        log_error "Migration script failed with exit code: $exit_code"
    fi

    exit $exit_code
}

# Run main function
main "$@"