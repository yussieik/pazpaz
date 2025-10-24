#!/bin/bash
# =============================================================================
# Example: Integration of Migration Script with Deployment
# =============================================================================
# This script demonstrates how to integrate database migrations into the
# deployment workflow using both migrate.sh and deploy.sh scripts.
#
# Usage:
#   ./deploy-with-migrations.sh [--skip-migration] [--force]
#
# This is an example integration script. In production, you would typically
# add migration calls directly to deploy.sh.
# =============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Options
SKIP_MIGRATION=false
FORCE_MIGRATION=false
DEPLOYMENT_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-migration)
            SKIP_MIGRATION=true
            shift
            ;;
        --force)
            FORCE_MIGRATION=true
            shift
            ;;
        *)
            DEPLOYMENT_ARGS="$DEPLOYMENT_ARGS $1"
            shift
            ;;
    esac
done

echo -e "${BLUE}[INFO]${NC} Starting deployment with migrations"

# Step 1: Run database migrations
if [ "$SKIP_MIGRATION" = false ]; then
    echo -e "${BLUE}[INFO]${NC} Running database migrations..."

    MIGRATION_ARGS=""
    if [ "$FORCE_MIGRATION" = true ]; then
        MIGRATION_ARGS="--force"
    fi

    if "${SCRIPT_DIR}/migrate.sh" $MIGRATION_ARGS upgrade; then
        echo -e "${GREEN}[SUCCESS]${NC} Database migrations completed"
    else
        echo -e "${RED}[ERROR]${NC} Database migrations failed"
        echo -e "${YELLOW}[WARNING]${NC} Deployment aborted due to migration failure"
        exit 1
    fi
else
    echo -e "${YELLOW}[WARNING]${NC} Skipping database migrations"
fi

# Step 2: Run deployment
echo -e "${BLUE}[INFO]${NC} Running deployment..."

if "${SCRIPT_DIR}/deploy.sh" $DEPLOYMENT_ARGS; then
    echo -e "${GREEN}[SUCCESS]${NC} Deployment completed"
else
    echo -e "${RED}[ERROR]${NC} Deployment failed"

    # Optional: Rollback migrations on deployment failure
    if [ "$SKIP_MIGRATION" = false ]; then
        echo -e "${YELLOW}[WARNING]${NC} Rolling back database migrations..."
        if "${SCRIPT_DIR}/migrate.sh" downgrade -1; then
            echo -e "${GREEN}[SUCCESS]${NC} Database rolled back"
        else
            echo -e "${RED}[ERROR]${NC} Database rollback failed - manual intervention required"
        fi
    fi

    exit 2
fi

# Step 3: Validate deployment
echo -e "${BLUE}[INFO]${NC} Validating deployment..."

# Validate database
if "${SCRIPT_DIR}/migrate.sh" validate; then
    echo -e "${GREEN}[SUCCESS]${NC} Database validation passed"
else
    echo -e "${YELLOW}[WARNING]${NC} Database validation failed - please investigate"
fi

echo -e "${GREEN}[SUCCESS]${NC} Deployment with migrations completed successfully"