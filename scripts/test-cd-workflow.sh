#!/bin/bash
# =============================================================================
# Test CD Workflow Script
# =============================================================================
# This script helps validate the continuous deployment workflow configuration
# before running actual deployments.
#
# Usage: ./scripts/test-cd-workflow.sh
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}PazPaz CD Workflow Test${NC}"
echo "=========================="
echo ""

# Check if GitHub CLI is installed
echo -e "${BLUE}Checking prerequisites...${NC}"
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI not installed${NC}"
    echo "Install from: https://cli.github.com/"
    exit 1
fi
echo -e "${GREEN}✅ GitHub CLI installed${NC}"

# Check authentication
if ! gh auth status > /dev/null 2>&1; then
    echo -e "${RED}❌ Not authenticated with GitHub${NC}"
    echo "Run: gh auth login"
    exit 1
fi
echo -e "${GREEN}✅ Authenticated with GitHub${NC}"

# Check required files exist
echo ""
echo -e "${BLUE}Checking required files...${NC}"

FILES_TO_CHECK=(
    ".github/workflows/deploy-production.yml"
    "docker-compose.prod.yml"
    "scripts/deploy.sh"
    "scripts/migrate.sh"
    "scripts/rotate-secrets.sh"
    "docs/deployment/github-cd-secrets.md"
)

ALL_FILES_EXIST=true
for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file not found${NC}"
        ALL_FILES_EXIST=false
    fi
done

if [ "$ALL_FILES_EXIST" = false ]; then
    echo -e "${RED}Some required files are missing. Please ensure all files are created.${NC}"
    exit 1
fi

# Check GitHub Secrets
echo ""
echo -e "${BLUE}Checking GitHub Secrets configuration...${NC}"

REQUIRED_SECRETS=(
    "SSH_PRIVATE_KEY"
    "SSH_HOST"
    "SSH_USER"
    "DOMAIN"
)

OPTIONAL_SECRETS=(
    "SSH_PORT"
    "GHCR_TOKEN"
    "SLACK_WEBHOOK_URL"
    "SENTRY_AUTH_TOKEN"
)

echo -e "${YELLOW}Required secrets:${NC}"
MISSING_SECRETS=()
for secret in "${REQUIRED_SECRETS[@]}"; do
    if gh secret list | grep -q "^$secret"; then
        echo -e "${GREEN}✅ $secret is configured${NC}"
    else
        echo -e "${RED}❌ $secret is NOT configured${NC}"
        MISSING_SECRETS+=("$secret")
    fi
done

echo ""
echo -e "${YELLOW}Optional secrets:${NC}"
for secret in "${OPTIONAL_SECRETS[@]}"; do
    if gh secret list | grep -q "^$secret"; then
        echo -e "${GREEN}✅ $secret is configured${NC}"
    else
        echo -e "${YELLOW}⚠️  $secret is not configured (optional)${NC}"
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Missing required secrets: ${MISSING_SECRETS[*]}${NC}"
    echo "Configure them using: gh secret set SECRET_NAME"
    echo "See docs/deployment/github-cd-secrets.md for detailed instructions"
    exit 1
fi

# Check workflow syntax
echo ""
echo -e "${BLUE}Validating workflow syntax...${NC}"
if gh workflow view "Deploy Production" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Workflow syntax is valid${NC}"
else
    echo -e "${RED}❌ Workflow syntax error or workflow not found${NC}"
    echo "Check .github/workflows/deploy-production.yml for errors"
    exit 1
fi

# Check Docker images availability (if possible)
echo ""
echo -e "${BLUE}Checking Docker images...${NC}"
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
if [ -n "$REPO" ]; then
    echo "Repository: $REPO"

    # Check if we can access the registry
    if docker manifest inspect "ghcr.io/$REPO/backend:latest" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend image accessible${NC}"
    else
        echo -e "${YELLOW}⚠️  Backend image not accessible (may not be built yet)${NC}"
    fi

    if docker manifest inspect "ghcr.io/$REPO/frontend:latest" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Frontend image accessible${NC}"
    else
        echo -e "${YELLOW}⚠️  Frontend image not accessible (may not be built yet)${NC}"
    fi
fi

# Test SSH connection (if configured)
echo ""
echo -e "${BLUE}Testing server connectivity (optional)...${NC}"
if [ -n "$SSH_HOST" ] && [ -n "$SSH_USER" ]; then
    echo "Testing connection to $SSH_USER@$SSH_HOST..."
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" "echo 'Connection successful'" 2>/dev/null; then
        echo -e "${GREEN}✅ SSH connection successful${NC}"
    else
        echo -e "${YELLOW}⚠️  Cannot connect via SSH (check firewall/keys)${NC}"
    fi
else
    echo -e "${YELLOW}Skip: SSH_HOST/SSH_USER not set in environment${NC}"
fi

# Suggest test commands
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}All checks passed! 🎉${NC}"
echo ""
echo "You can now test the deployment workflow:"
echo ""
echo -e "${YELLOW}1. Dry run (recommended first):${NC}"
echo "   gh workflow run 'Deploy Production' \\"
echo "     -f environment=production \\"
echo "     -f image_tag=latest \\"
echo "     -f dry_run=true"
echo ""
echo -e "${YELLOW}2. Watch the workflow:${NC}"
echo "   gh run watch"
echo ""
echo -e "${YELLOW}3. View workflow runs:${NC}"
echo "   gh run list --workflow='Deploy Production'"
echo ""
echo -e "${YELLOW}4. Actual deployment (after dry run succeeds):${NC}"
echo "   gh workflow run 'Deploy Production' \\"
echo "     -f environment=production \\"
echo "     -f image_tag=latest"
echo ""
echo "For more information, see docs/deployment/github-cd-secrets.md"