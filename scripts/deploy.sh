#!/bin/bash
# =============================================================================
# Production Deployment Script for PazPaz
# =============================================================================
# Straightforward Docker Compose deployment with health checks and logging.
# No complex blue-green logic - Docker Compose handles zero-downtime updates.
#
# Usage:
#   ./deploy.sh [OPTIONS]
#
# Options:
#   --tag <tag>           Specify image tag (default: latest)
#   --skip-backup         Skip database backup
#   --skip-health-checks  Skip health checks (not recommended)
#   --dry-run            Show what would be deployed without deploying
#
# Environment Variables:
#   IMAGE_TAG            Docker image tag (overrides --tag)
#
# Exit Codes:
#   0 - Deployment successful
#   1 - Pre-deployment checks failed
#   2 - Deployment failed
#   3 - Health checks failed
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_DIR="${DEPLOYMENT_DIR:-/opt/pazpaz}"
BACKUP_DIR="${DEPLOYMENT_DIR}/backups"
LOG_DIR="${DEPLOYMENT_DIR}/logs"

# Default settings
IMAGE_TAG="${IMAGE_TAG:-latest}"
SKIP_BACKUP=false
SKIP_HEALTH_CHECKS=false
DRY_RUN=false

# Docker Compose files
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"

# Health check settings
HEALTH_CHECK_TIMEOUT=120
HEALTH_CHECK_INTERVAL=5

# =============================================================================
# Logging
# =============================================================================

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_DIR}/deployment.log"
}

log_info() {
    log "${BLUE}[INFO]${NC} $*"
}

log_success() {
    log "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    log "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    log "${RED}[ERROR]${NC} $*"
}

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --skip-health-checks)
            SKIP_HEALTH_CHECKS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Pre-deployment Checks
# =============================================================================

pre_deployment_checks() {
    log_info "Running pre-deployment checks..."

    # Check if running in correct directory
    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_error "docker-compose.prod.yml not found. Are you in the deployment directory?"
        return 1
    fi

    # Check if .env.production exists
    if [ ! -f "${ENV_FILE}" ]; then
        log_error ".env.production not found"
        return 1
    fi

    # Check Docker is running
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running"
        return 1
    fi

    # Check Docker Compose is available
    if ! docker compose version > /dev/null 2>&1; then
        log_error "Docker Compose is not available"
        return 1
    fi

    # Check disk space (require at least 10GB free)
    AVAILABLE_SPACE=$(df -BG "${DEPLOYMENT_DIR}" | awk 'NR==2 {gsub("G",""); print $4}')
    if [ "$AVAILABLE_SPACE" -lt 10 ]; then
        log_warning "Low disk space: ${AVAILABLE_SPACE}GB available"
    fi

    # Create required directories
    mkdir -p "${BACKUP_DIR}" "${LOG_DIR}"

    log_success "Pre-deployment checks passed"
}

# =============================================================================
# Backup Database
# =============================================================================

backup_database() {
    if [ "$SKIP_BACKUP" = true ]; then
        log_warning "Skipping database backup (--skip-backup flag)"
        return 0
    fi

    log_info "Creating database backup..."

    BACKUP_FILE="${BACKUP_DIR}/pre-deployment-$(date +%Y%m%d-%H%M%S).sql"

    if docker exec pazpaz-db pg_dump -U pazpaz -d pazpaz > "${BACKUP_FILE}"; then
        log_success "Database backup created: ${BACKUP_FILE}"

        # Keep only last 10 backups
        ls -t "${BACKUP_DIR}"/pre-deployment-*.sql | tail -n +11 | xargs -r rm
    else
        log_error "Database backup failed"
        return 1
    fi
}

# =============================================================================
# Update Configuration
# =============================================================================

update_configuration() {
    log_info "Updating configuration for image tag: ${IMAGE_TAG}"

    # Backup current docker-compose.prod.yml
    cp "${COMPOSE_FILE}" "${COMPOSE_FILE}.backup-$(date +%Y%m%d-%H%M%S)"

    # Update image tags in docker-compose.prod.yml
    sed -i "s|image: ghcr.io/yussieik/pazpaz-backend:.*|image: ghcr.io/yussieik/pazpaz-backend:${IMAGE_TAG}|g" "${COMPOSE_FILE}"
    sed -i "s|image: ghcr.io/yussieik/pazpaz-frontend:.*|image: ghcr.io/yussieik/pazpaz-frontend:${IMAGE_TAG}|g" "${COMPOSE_FILE}"

    log_success "Configuration updated"
}

# =============================================================================
# Deploy Application
# =============================================================================

deploy_application() {
    log_info "Starting deployment..."

    if [ "$DRY_RUN" = true ]; then
        log_info "DRY RUN - Validating configuration..."
        docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config
        log_success "Configuration is valid (dry run)"
        return 0
    fi

    # Pull latest images
    log_info "Pulling Docker images..."
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" pull api frontend

    # Deploy with Docker Compose (handles zero-downtime updates)
    log_info "Starting/restarting services..."
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --no-build

    log_success "Services started"
}

# =============================================================================
# Health Checks
# =============================================================================

check_health() {
    if [ "$SKIP_HEALTH_CHECKS" = true ]; then
        log_warning "Skipping health checks (--skip-health-checks flag)"
        return 0
    fi

    log_info "Running health checks..."

    local elapsed=0
    while [ $elapsed -lt $HEALTH_CHECK_TIMEOUT ]; do
        # Get unhealthy service count
        UNHEALTHY=$(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps --format json | \
            jq -r 'select(.Service == "api" or .Service == "frontend" or .Service == "nginx") | select(.Health != "healthy") | .Service' | wc -l)

        if [ "$UNHEALTHY" -eq 0 ]; then
            log_success "All services are healthy"
            return 0
        fi

        log_info "Waiting for services to become healthy... (${elapsed}/${HEALTH_CHECK_TIMEOUT}s)"
        sleep $HEALTH_CHECK_INTERVAL
        elapsed=$((elapsed + HEALTH_CHECK_INTERVAL))
    done

    log_error "Health check timeout - services did not become healthy"

    # Show container status
    log_info "Container status:"
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps

    # Show recent logs
    log_info "Recent logs:"
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs --tail=30

    return 1
}

# =============================================================================
# Main Deployment Flow
# =============================================================================

main() {
    log_info "=========================================="
    log_info "PazPaz Deployment Started"
    log_info "=========================================="
    log_info "Image Tag: ${IMAGE_TAG}"
    log_info "Deployment Directory: ${DEPLOYMENT_DIR}"
    log_info "Dry Run: ${DRY_RUN}"
    log_info "=========================================="

    # Change to deployment directory
    cd "${DEPLOYMENT_DIR}"

    # Run pre-deployment checks
    if ! pre_deployment_checks; then
        log_error "Pre-deployment checks failed"
        exit 1
    fi

    # Backup database
    if [ "$DRY_RUN" = false ]; then
        if ! backup_database; then
            log_error "Database backup failed"
            exit 1
        fi
    fi

    # Update configuration
    if ! update_configuration; then
        log_error "Configuration update failed"
        exit 1
    fi

    # Deploy application
    if ! deploy_application; then
        log_error "Deployment failed"
        exit 2
    fi

    # Health checks
    if [ "$DRY_RUN" = false ]; then
        if ! check_health; then
            log_error "Health checks failed"
            log_warning "Consider running: docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} logs"
            exit 3
        fi
    fi

    log_info "=========================================="
    log_success "Deployment Completed Successfully!"
    log_info "=========================================="
    log_info "View logs: docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} logs -f"
    log_info "Check status: docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} ps"
}

# Run main function
main
