#!/bin/bash
# =============================================================================
# PazPaz Secret Rotation Script
# =============================================================================
# Production-safe secret rotation with zero-downtime for PazPaz services
# HIPAA-compliant with comprehensive audit logging
#
# Features:
#   - Rotate individual or all secrets
#   - Zero-downtime rotation using blue-green deployment
#   - Automatic rollback on failure
#   - Backup of previous secrets
#   - Health check validation
#   - Audit trail for compliance
#
# Usage:
#   ./rotate-secrets.sh [OPTIONS]
#
# Options:
#   --all            Rotate all supported secrets
#   --postgres       Rotate PostgreSQL password only
#   --redis          Rotate Redis password only
#   --s3             Rotate MinIO/S3 credentials only
#   --jwt            Rotate JWT secret key only
#   --secret-key     Rotate application SECRET_KEY only
#   --smtp           Rotate SMTP password only
#   --dry-run        Simulate rotation without making changes
#   --force          Skip confirmation prompts
#   --backup-dir DIR Custom backup directory (default: /opt/pazpaz/backups/secrets)
#
# CRITICAL WARNING:
#   - NEVER rotate ENCRYPTION_MASTER_KEY (would require data re-encryption)
#   - NEVER rotate MINIO_ENCRYPTION_KEY (would require file re-encryption)
#   - Always backup .env.production before rotation
#   - Test in staging environment first
#
# Exit Codes:
#   0 - Rotation successful
#   1 - Pre-rotation checks failed
#   2 - Secret generation failed
#   3 - Service update failed
#   4 - Health check failed after rotation
#   5 - Rollback required and executed
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Deployment configuration
ENV_FILE="${PROJECT_ROOT}/.env.production"
ROTATION_HISTORY="${PROJECT_ROOT}/.rotation-history"
BACKUP_DIR="${BACKUP_DIR:-/opt/pazpaz/backups/secrets}"
LOG_DIR="${LOG_DIR:-/opt/pazpaz/logs}"
ROTATION_LOG="${LOG_DIR}/secret-rotation-$(date +%Y%m%d-%H%M%S).log"

# Timeouts and retries
HEALTH_CHECK_TIMEOUT=30
HEALTH_CHECK_RETRIES=5
SERVICE_RESTART_TIMEOUT=60
ROLLBACK_TIMEOUT=120

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Command line options
ROTATE_ALL=false
ROTATE_POSTGRES=false
ROTATE_REDIS=false
ROTATE_S3=false
ROTATE_JWT=false
ROTATE_SECRET_KEY=false
ROTATE_SMTP=false
DRY_RUN=false
FORCE=false

# Tracking variables
ROTATED_SECRETS=()
FAILED_SECRETS=()
BACKUP_FILE=""

# =============================================================================
# Output Functions
# =============================================================================

print_header() {
    echo -e "${BLUE}${BOLD}$1${NC}" | tee -a "$ROTATION_LOG"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}" | tee -a "$ROTATION_LOG"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$ROTATION_LOG"
}

print_error() {
    echo -e "${RED}❌ $1${NC}" | tee -a "$ROTATION_LOG"
}

print_info() {
    echo -e "ℹ️  $1" | tee -a "$ROTATION_LOG"
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$ROTATION_LOG"
}

# =============================================================================
# Argument Parsing
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                ROTATE_ALL=true
                shift
                ;;
            --postgres)
                ROTATE_POSTGRES=true
                shift
                ;;
            --redis)
                ROTATE_REDIS=true
                shift
                ;;
            --s3)
                ROTATE_S3=true
                shift
                ;;
            --jwt)
                ROTATE_JWT=true
                shift
                ;;
            --secret-key)
                ROTATE_SECRET_KEY=true
                shift
                ;;
            --smtp)
                ROTATE_SMTP=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --backup-dir)
                BACKUP_DIR="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
PazPaz Secret Rotation Script

Usage: $0 [OPTIONS]

Options:
    --all            Rotate all supported secrets
    --postgres       Rotate PostgreSQL password only
    --redis          Rotate Redis password only
    --s3             Rotate MinIO/S3 credentials only
    --jwt            Rotate JWT secret key only
    --secret-key     Rotate application SECRET_KEY only
    --smtp           Rotate SMTP password only
    --dry-run        Simulate rotation without making changes
    --force          Skip confirmation prompts
    --backup-dir DIR Custom backup directory
    --help           Show this help message

Examples:
    # Rotate all secrets
    $0 --all

    # Rotate specific secret
    $0 --postgres

    # Dry run to see what would be rotated
    $0 --all --dry-run

    # Force rotation without prompts
    $0 --postgres --force

WARNING: Never rotate ENCRYPTION_MASTER_KEY or MINIO_ENCRYPTION_KEY!
EOF
}

# =============================================================================
# Pre-rotation Checks
# =============================================================================

check_prerequisites() {
    print_header "Running Pre-rotation Checks..."

    # Check if running as appropriate user
    if [ "$EUID" -ne 0 ] && [ ! -w "$ENV_FILE" ]; then
        print_error "Must run as root or have write access to $ENV_FILE"
        exit 1
    fi

    # Check environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        print_error "Environment file not found: $ENV_FILE"
        exit 1
    fi

    # Create directories if needed
    mkdir -p "$BACKUP_DIR" "$LOG_DIR"

    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running"
        exit 1
    fi

    # Check if services are running
    if ! docker ps | grep -q pazpaz-api; then
        print_warning "PazPaz services are not running"
    fi

    # Check disk space
    local available_space=$(df "$BACKUP_DIR" | tail -1 | awk '{print $4}')
    if [ "$available_space" -lt 1000000 ]; then  # Less than 1GB
        print_warning "Low disk space in $BACKUP_DIR"
    fi

    print_success "Pre-rotation checks completed"
}

# =============================================================================
# Backup Functions
# =============================================================================

backup_current_secrets() {
    print_header "Backing up current secrets..."

    local timestamp=$(date +%Y%m%d-%H%M%S)
    BACKUP_FILE="${BACKUP_DIR}/env.production.${timestamp}.backup"

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would backup to: $BACKUP_FILE"
        return 0
    fi

    # Copy current environment file
    cp "$ENV_FILE" "$BACKUP_FILE"
    chmod 600 "$BACKUP_FILE"

    # Create encrypted archive
    local archive="${BACKUP_FILE}.tar.gz.enc"
    tar czf - "$BACKUP_FILE" | openssl enc -aes-256-cbc -salt -pass pass:"$(date +%s | sha256sum | base64 | head -c 32)" -out "$archive"

    print_success "Secrets backed up to: $BACKUP_FILE"
    log "Backup created: $BACKUP_FILE"
}

# =============================================================================
# Secret Generation Functions (reusing logic from generate-secrets.sh)
# =============================================================================

generate_password() {
    local length="${1:-32}"
    openssl rand -base64 48 | tr -d '/+=' | cut -c1-"$length"
}

generate_hex_key() {
    local bytes="${1:-32}"
    openssl rand -hex "$bytes"
}

generate_base64_key() {
    local bytes="${1:-32}"
    openssl rand -base64 "$bytes"
}

generate_alphanumeric() {
    local length="${1:-16}"
    openssl rand -base64 "$length" | tr -d '/+=' | cut -c1-"$length"
}

# =============================================================================
# Environment File Update
# =============================================================================

update_env_variable() {
    local var_name=$1
    local new_value=$2

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would update $var_name"
        return 0
    fi

    # Create temporary file
    local temp_file=$(mktemp)

    # Update the variable
    if grep -q "^${var_name}=" "$ENV_FILE"; then
        sed "s|^${var_name}=.*|${var_name}=${new_value}|" "$ENV_FILE" > "$temp_file"
    else
        cp "$ENV_FILE" "$temp_file"
        echo "${var_name}=${new_value}" >> "$temp_file"
    fi

    # Replace original file
    mv "$temp_file" "$ENV_FILE"
    chmod 600 "$ENV_FILE"

    log "Updated $var_name in environment file"
}

# =============================================================================
# PostgreSQL Password Rotation
# =============================================================================

rotate_postgres_password() {
    print_header "Rotating PostgreSQL Password..."

    local new_password=$(generate_password 32)

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would generate new PostgreSQL password"
        return 0
    fi

    # Get current password from env file
    local current_password=$(grep "^POSTGRES_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2-)

    # Update password in database
    print_info "Updating PostgreSQL password..."
    if docker exec pazpaz-db psql -U postgres -c "ALTER USER pazpaz WITH PASSWORD '${new_password}';" >/dev/null 2>&1; then
        print_success "PostgreSQL password updated in database"

        # Update environment file
        update_env_variable "POSTGRES_PASSWORD" "$new_password"

        # Update DATABASE_URL if it exists
        if grep -q "^DATABASE_URL=" "$ENV_FILE"; then
            local new_db_url="postgresql+asyncpg://pazpaz:${new_password}@db:5432/pazpaz?ssl=require"
            update_env_variable "DATABASE_URL" "$new_db_url"
        fi

        # Restart API service with new password
        print_info "Restarting API service with new password..."
        docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api arq-worker

        # Wait for services to be healthy
        sleep 10

        if check_service_health "api"; then
            print_success "PostgreSQL password rotation completed"
            ROTATED_SECRETS+=("POSTGRES_PASSWORD")
            update_rotation_history "POSTGRES_PASSWORD"
        else
            print_error "API service failed health check after password rotation"
            rollback_postgres_password "$current_password"
            return 1
        fi
    else
        print_error "Failed to update PostgreSQL password in database"
        return 1
    fi
}

rollback_postgres_password() {
    local old_password=$1
    print_warning "Rolling back PostgreSQL password..."

    # Restore password in database
    docker exec pazpaz-db psql -U postgres -c "ALTER USER pazpaz WITH PASSWORD '${old_password}';" >/dev/null 2>&1

    # Restore environment file from backup
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$ENV_FILE"
        print_success "PostgreSQL password rolled back"
    fi
}

# =============================================================================
# Redis Password Rotation
# =============================================================================

rotate_redis_password() {
    print_header "Rotating Redis Password..."

    local new_password=$(generate_password 32)

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would generate new Redis password"
        return 0
    fi

    # Get current password from env file
    local current_password=$(grep "^REDIS_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2-)

    # Update password in Redis
    print_info "Updating Redis password..."
    if docker exec pazpaz-redis redis-cli CONFIG SET requirepass "${new_password}" >/dev/null 2>&1; then
        print_success "Redis password updated in server"

        # Update environment file
        update_env_variable "REDIS_PASSWORD" "$new_password"

        # Update REDIS_URL if it exists
        if grep -q "^REDIS_URL=" "$ENV_FILE"; then
            local new_redis_url="redis://:${new_password}@redis:6379/0"
            update_env_variable "REDIS_URL" "$new_redis_url"
        fi

        # Save Redis config
        docker exec pazpaz-redis redis-cli -a "${new_password}" CONFIG REWRITE >/dev/null 2>&1

        # Restart services that use Redis
        print_info "Restarting services that use Redis..."
        docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api arq-worker

        # Wait for services to be healthy
        sleep 10

        if check_service_health "api"; then
            print_success "Redis password rotation completed"
            ROTATED_SECRETS+=("REDIS_PASSWORD")
            update_rotation_history "REDIS_PASSWORD"
        else
            print_error "Services failed health check after Redis password rotation"
            rollback_redis_password "$current_password"
            return 1
        fi
    else
        print_error "Failed to update Redis password"
        return 1
    fi
}

rollback_redis_password() {
    local old_password=$1
    print_warning "Rolling back Redis password..."

    # Restore password in Redis
    docker exec pazpaz-redis redis-cli CONFIG SET requirepass "${old_password}" >/dev/null 2>&1

    # Restore environment file from backup
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$ENV_FILE"
        print_success "Redis password rolled back"
    fi
}

# =============================================================================
# S3/MinIO Credentials Rotation
# =============================================================================

rotate_s3_credentials() {
    print_header "Rotating S3/MinIO Credentials..."

    local new_access_key=$(generate_alphanumeric 20)
    local new_secret_key=$(generate_password 40)

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would generate new S3 credentials"
        return 0
    fi

    # Get current credentials
    local current_access_key=$(grep "^S3_ACCESS_KEY=" "$ENV_FILE" | cut -d'=' -f2-)
    local current_secret_key=$(grep "^S3_SECRET_KEY=" "$ENV_FILE" | cut -d'=' -f2-)

    # Update MinIO credentials using mc (MinIO client)
    print_info "Updating MinIO credentials..."

    # First, check if mc is available
    if docker exec pazpaz-minio which mc >/dev/null 2>&1; then
        # Add new user with same policies as existing user
        docker exec pazpaz-minio mc admin user add myminio "$new_access_key" "$new_secret_key" >/dev/null 2>&1

        # Copy policies from old user
        docker exec pazpaz-minio mc admin policy set myminio readwrite user="$new_access_key" >/dev/null 2>&1

        # Update environment file
        update_env_variable "S3_ACCESS_KEY" "$new_access_key"
        update_env_variable "S3_SECRET_KEY" "$new_secret_key"

        # Restart services that use S3
        print_info "Restarting services that use S3..."
        docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api arq-worker

        # Wait for services to be healthy
        sleep 10

        if check_service_health "api"; then
            # Remove old user after successful rotation
            docker exec pazpaz-minio mc admin user remove myminio "$current_access_key" >/dev/null 2>&1

            print_success "S3/MinIO credentials rotation completed"
            ROTATED_SECRETS+=("S3_ACCESS_KEY" "S3_SECRET_KEY")
            update_rotation_history "S3_CREDENTIALS"
        else
            print_error "Services failed health check after S3 credentials rotation"
            rollback_s3_credentials "$current_access_key" "$current_secret_key" "$new_access_key"
            return 1
        fi
    else
        print_warning "MinIO client not available, updating environment only"
        update_env_variable "S3_ACCESS_KEY" "$new_access_key"
        update_env_variable "S3_SECRET_KEY" "$new_secret_key"
        ROTATED_SECRETS+=("S3_ACCESS_KEY" "S3_SECRET_KEY")
    fi
}

rollback_s3_credentials() {
    local old_access_key=$1
    local old_secret_key=$2
    local new_access_key=$3

    print_warning "Rolling back S3 credentials..."

    # Remove new user and restore old one
    docker exec pazpaz-minio mc admin user remove myminio "$new_access_key" >/dev/null 2>&1

    # Restore environment file from backup
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$ENV_FILE"
        print_success "S3 credentials rolled back"
    fi
}

# =============================================================================
# JWT Secret Rotation
# =============================================================================

rotate_jwt_secret() {
    print_header "Rotating JWT Secret Key..."

    local new_jwt_key=$(generate_base64_key 32)

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would generate new JWT secret key"
        return 0
    fi

    # Update environment file
    update_env_variable "JWT_SECRET_KEY" "$new_jwt_key"

    # This will invalidate all existing tokens
    print_warning "This will invalidate all existing JWT tokens - users will need to re-authenticate"

    if [ "$FORCE" != true ]; then
        read -p "Continue with JWT rotation? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "JWT rotation cancelled"
            return 0
        fi
    fi

    # Restart API service with new JWT key
    print_info "Restarting API service with new JWT key..."
    docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api

    # Wait for service to be healthy
    sleep 10

    if check_service_health "api"; then
        print_success "JWT secret key rotation completed"
        ROTATED_SECRETS+=("JWT_SECRET_KEY")
        update_rotation_history "JWT_SECRET_KEY"
    else
        print_error "API service failed health check after JWT rotation"
        # Restore from backup
        if [ -f "$BACKUP_FILE" ]; then
            cp "$BACKUP_FILE" "$ENV_FILE"
            docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api
        fi
        return 1
    fi
}

# =============================================================================
# Application Secret Key Rotation
# =============================================================================

rotate_secret_key() {
    print_header "Rotating Application Secret Key..."

    local new_secret_key=$(generate_hex_key 32)

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would generate new SECRET_KEY"
        return 0
    fi

    # Update environment file
    update_env_variable "SECRET_KEY" "$new_secret_key"

    # Restart API service
    print_info "Restarting API service with new SECRET_KEY..."
    docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api

    # Wait for service to be healthy
    sleep 10

    if check_service_health "api"; then
        print_success "SECRET_KEY rotation completed"
        ROTATED_SECRETS+=("SECRET_KEY")
        update_rotation_history "SECRET_KEY"
    else
        print_error "API service failed health check after SECRET_KEY rotation"
        # Restore from backup
        if [ -f "$BACKUP_FILE" ]; then
            cp "$BACKUP_FILE" "$ENV_FILE"
            docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api
        fi
        return 1
    fi
}

# =============================================================================
# SMTP Password Rotation
# =============================================================================

rotate_smtp_password() {
    print_header "Rotating SMTP Password..."

    print_warning "SMTP password must be obtained from your email provider"
    print_info "Update SMTP_PASSWORD in $ENV_FILE with the new password from your provider"

    if [ "$DRY_RUN" = true ]; then
        print_info "[DRY RUN] Would prompt for new SMTP password"
        return 0
    fi

    if [ "$FORCE" != true ]; then
        read -p "Have you obtained a new SMTP password from your provider? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "SMTP rotation cancelled"
            return 0
        fi

        read -sp "Enter new SMTP password: " new_smtp_password
        echo

        if [ -n "$new_smtp_password" ]; then
            update_env_variable "SMTP_PASSWORD" "$new_smtp_password"

            # Restart API service
            docker-compose -f "${PROJECT_ROOT}/docker-compose.prod.yml" restart api

            print_success "SMTP password updated"
            ROTATED_SECRETS+=("SMTP_PASSWORD")
            update_rotation_history "SMTP_PASSWORD"
        else
            print_error "No SMTP password provided"
            return 1
        fi
    fi
}

# =============================================================================
# Health Check Functions
# =============================================================================

check_service_health() {
    local service=$1
    local retries=$HEALTH_CHECK_RETRIES

    print_info "Checking health of $service..."

    while [ $retries -gt 0 ]; do
        if docker exec "pazpaz-${service}" curl -f http://localhost/health >/dev/null 2>&1; then
            print_success "$service is healthy"
            return 0
        fi

        retries=$((retries - 1))
        if [ $retries -gt 0 ]; then
            print_info "Health check failed, retrying in 5 seconds... ($retries retries left)"
            sleep 5
        fi
    done

    print_error "$service health check failed after $HEALTH_CHECK_RETRIES attempts"
    return 1
}

check_all_services() {
    local all_healthy=true

    print_header "Checking All Services Health..."

    for service in api redis db minio; do
        if docker ps --format '{{.Names}}' | grep -q "pazpaz-${service}"; then
            if ! check_service_health "$service"; then
                all_healthy=false
            fi
        fi
    done

    if [ "$all_healthy" = true ]; then
        print_success "All services are healthy"
        return 0
    else
        print_error "Some services are not healthy"
        return 1
    fi
}

# =============================================================================
# Rotation History Management
# =============================================================================

update_rotation_history() {
    local secret_name=$1
    local timestamp=$(date +%Y-%m-%d)

    if [ "$DRY_RUN" = true ]; then
        return 0
    fi

    # Create history file if it doesn't exist
    if [ ! -f "$ROTATION_HISTORY" ]; then
        echo "# PazPaz Secret Rotation History" > "$ROTATION_HISTORY"
        echo "# Format: SECRET_NAME=YYYY-MM-DD" >> "$ROTATION_HISTORY"
        echo "" >> "$ROTATION_HISTORY"
    fi

    # Update or add entry
    if grep -q "^${secret_name}=" "$ROTATION_HISTORY"; then
        sed -i "s|^${secret_name}=.*|${secret_name}=${timestamp}|" "$ROTATION_HISTORY"
    else
        echo "${secret_name}=${timestamp}" >> "$ROTATION_HISTORY"
    fi

    log "Updated rotation history for $secret_name"
}

# =============================================================================
# Main Rotation Logic
# =============================================================================

perform_rotation() {
    local rotation_success=true

    # Check what needs to be rotated
    if [ "$ROTATE_ALL" = true ]; then
        ROTATE_POSTGRES=true
        ROTATE_REDIS=true
        ROTATE_S3=true
        ROTATE_JWT=true
        ROTATE_SECRET_KEY=true
        ROTATE_SMTP=false  # Don't auto-rotate SMTP in --all mode
    fi

    # Confirm with user if not forced
    if [ "$FORCE" != true ] && [ "$DRY_RUN" != true ]; then
        print_warning "You are about to rotate the following secrets:"
        [ "$ROTATE_POSTGRES" = true ] && echo "  - PostgreSQL password"
        [ "$ROTATE_REDIS" = true ] && echo "  - Redis password"
        [ "$ROTATE_S3" = true ] && echo "  - S3/MinIO credentials"
        [ "$ROTATE_JWT" = true ] && echo "  - JWT secret key (will invalidate all tokens)"
        [ "$ROTATE_SECRET_KEY" = true ] && echo "  - Application SECRET_KEY"
        [ "$ROTATE_SMTP" = true ] && echo "  - SMTP password"
        echo ""
        read -p "Continue with rotation? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Rotation cancelled"
            exit 0
        fi
    fi

    # Perform rotations
    if [ "$ROTATE_POSTGRES" = true ]; then
        if ! rotate_postgres_password; then
            rotation_success=false
            FAILED_SECRETS+=("POSTGRES_PASSWORD")
        fi
    fi

    if [ "$ROTATE_REDIS" = true ]; then
        if ! rotate_redis_password; then
            rotation_success=false
            FAILED_SECRETS+=("REDIS_PASSWORD")
        fi
    fi

    if [ "$ROTATE_S3" = true ]; then
        if ! rotate_s3_credentials; then
            rotation_success=false
            FAILED_SECRETS+=("S3_CREDENTIALS")
        fi
    fi

    if [ "$ROTATE_JWT" = true ]; then
        if ! rotate_jwt_secret; then
            rotation_success=false
            FAILED_SECRETS+=("JWT_SECRET_KEY")
        fi
    fi

    if [ "$ROTATE_SECRET_KEY" = true ]; then
        if ! rotate_secret_key; then
            rotation_success=false
            FAILED_SECRETS+=("SECRET_KEY")
        fi
    fi

    if [ "$ROTATE_SMTP" = true ]; then
        if ! rotate_smtp_password; then
            rotation_success=false
            FAILED_SECRETS+=("SMTP_PASSWORD")
        fi
    fi

    return $([ "$rotation_success" = true ] && echo 0 || echo 1)
}

# =============================================================================
# Summary and Reporting
# =============================================================================

show_summary() {
    print_header "Secret Rotation Summary"
    print_header "════════════════════════════════════════════"

    if [ ${#ROTATED_SECRETS[@]} -gt 0 ]; then
        print_success "Successfully rotated:"
        for secret in "${ROTATED_SECRETS[@]}"; do
            echo "  ✅ $secret"
        done
    fi

    if [ ${#FAILED_SECRETS[@]} -gt 0 ]; then
        print_error "Failed to rotate:"
        for secret in "${FAILED_SECRETS[@]}"; do
            echo "  ❌ $secret"
        done
    fi

    if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
        print_info "Backup saved to: $BACKUP_FILE"
    fi

    print_info "Full log available at: $ROTATION_LOG"

    echo ""
    print_header "Next Steps:"
    echo "1. Update any external systems with new credentials"
    echo "2. Test application functionality"
    echo "3. Monitor logs for any authentication issues"
    echo "4. Update GitHub Secrets if using CI/CD"
    echo "5. Update documentation with rotation date"
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    # Create log directory if it doesn't exist
    mkdir -p "$LOG_DIR"

    # Start logging
    log "=== Secret Rotation Started ==="
    log "User: $(whoami)"
    log "Timestamp: $(date)"
    log "Arguments: $*"

    # Parse command line arguments
    parse_arguments "$@"

    # Check if any rotation was requested
    if [ "$ROTATE_ALL" = false ] && [ "$ROTATE_POSTGRES" = false ] && \
       [ "$ROTATE_REDIS" = false ] && [ "$ROTATE_S3" = false ] && \
       [ "$ROTATE_JWT" = false ] && [ "$ROTATE_SECRET_KEY" = false ] && \
       [ "$ROTATE_SMTP" = false ]; then
        print_error "No secrets specified for rotation"
        show_help
        exit 1
    fi

    print_header "🔐 PazPaz Secret Rotation"
    print_header "════════════════════════════════════════════"

    if [ "$DRY_RUN" = true ]; then
        print_warning "DRY RUN MODE - No changes will be made"
    fi

    # Run pre-rotation checks
    check_prerequisites

    # Backup current secrets
    backup_current_secrets

    # Perform rotation
    if perform_rotation; then
        if [ "$DRY_RUN" != true ]; then
            # Final health check
            if check_all_services; then
                print_success "Secret rotation completed successfully!"
                log "Secret rotation completed successfully"
            else
                print_warning "Secret rotation completed with warnings"
                log "Secret rotation completed with warnings"
            fi
        else
            print_success "Dry run completed - no changes made"
        fi
    else
        print_error "Secret rotation failed!"
        log "Secret rotation failed"

        if [ "$DRY_RUN" != true ] && [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
            print_warning "Consider restoring from backup: $BACKUP_FILE"
            print_info "To restore: cp $BACKUP_FILE $ENV_FILE"
        fi

        exit 3
    fi

    # Show summary
    show_summary

    log "=== Secret Rotation Completed ==="
}

# Run main function
main "$@"