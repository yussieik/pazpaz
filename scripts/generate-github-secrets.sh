#!/bin/bash
# =============================================================================
# GitHub Secrets Generator for PazPaz CI/CD
# =============================================================================
# This script generates secure values for GitHub Secrets
# and provides instructions on how to add them to your repository.
#
# Usage:
#   ./scripts/generate-github-secrets.sh
#
# Output:
#   - Generates secure random values for secrets
#   - Prints instructions for adding to GitHub
#   - Optionally uses GitHub CLI to set secrets automatically
# =============================================================================

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "════════════════════════════════════════════════════════════"
echo "  GitHub Secrets Generator for PazPaz"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if GitHub CLI is available
HAS_GH_CLI=false
if command -v gh &> /dev/null; then
    HAS_GH_CLI=true
    echo -e "${GREEN}✓${NC} GitHub CLI detected - can auto-configure secrets"
else
    echo -e "${YELLOW}!${NC} GitHub CLI not found - will generate values only"
    echo -e "  Install: ${BLUE}brew install gh${NC} (macOS) or visit https://cli.github.com"
fi
echo ""

# Check existing secrets from environment or prompt
echo "Checking existing configuration..."
echo ""

# Production SSH credentials
if [ -n "${PRODUCTION_SSH_HOST:-}" ]; then
    SSH_HOST="$PRODUCTION_SSH_HOST"
    echo -e "${GREEN}✓${NC} Using existing PRODUCTION_SSH_HOST from environment"
else
    echo -e "${BLUE}Production SSH Configuration${NC}"
    echo -n "Enter production server IP/hostname (or press Enter to skip): "
    read -r SSH_HOST
fi

if [ -n "${PRODUCTION_SSH_USER:-}" ]; then
    SSH_USER="$PRODUCTION_SSH_USER"
    echo -e "${GREEN}✓${NC} Using existing PRODUCTION_SSH_USER from environment"
else
    if [ -n "$SSH_HOST" ]; then
        echo -n "Enter SSH username (default: root): "
        read -r SSH_USER
        SSH_USER=${SSH_USER:-root}
    fi
fi

if [ -n "${PRODUCTION_SSH_PORT:-}" ]; then
    SSH_PORT="$PRODUCTION_SSH_PORT"
    echo -e "${GREEN}✓${NC} Using existing PRODUCTION_SSH_PORT from environment"
else
    if [ -n "$SSH_HOST" ]; then
        echo -n "Enter SSH port (default: 22): "
        read -r SSH_PORT
        SSH_PORT=${SSH_PORT:-22}
    fi
fi

# Check for existing SSH key
SSH_KEY=""
if [ -f ~/.ssh/id_ed25519 ]; then
    echo -e "${YELLOW}?${NC} Found SSH key at ~/.ssh/id_ed25519"
    echo -n "Use this key? (y/n): "
    read -r use_key
    if [[ "$use_key" =~ ^[Yy]$ ]]; then
        SSH_KEY=$(cat ~/.ssh/id_ed25519)
    fi
elif [ -f ~/.ssh/id_rsa ]; then
    echo -e "${YELLOW}?${NC} Found SSH key at ~/.ssh/id_rsa"
    echo -n "Use this key? (y/n): "
    read -r use_key
    if [[ "$use_key" =~ ^[Yy]$ ]]; then
        SSH_KEY=$(cat ~/.ssh/id_rsa)
    fi
fi

# If no key found or user declined, offer to generate
if [ -z "$SSH_KEY" ] && [ -n "$SSH_HOST" ]; then
    echo -e "${YELLOW}!${NC} No SSH key selected"
    echo -n "Generate new ED25519 SSH key? (y/n): "
    read -r gen_key
    if [[ "$gen_key" =~ ^[Yy]$ ]]; then
        KEY_PATH="/tmp/pazpaz_deploy_key"
        ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "pazpaz-github-actions"
        SSH_KEY=$(cat "$KEY_PATH")
        echo ""
        echo -e "${GREEN}✓${NC} Generated new SSH key at $KEY_PATH"
        echo -e "${YELLOW}!${NC} IMPORTANT: Add public key to server authorized_keys:"
        echo ""
        echo -e "${BLUE}On your server, run:${NC}"
        echo "  ssh $SSH_USER@$SSH_HOST"
        echo "  mkdir -p ~/.ssh"
        echo "  echo '$(cat ${KEY_PATH}.pub)' >> ~/.ssh/authorized_keys"
        echo "  chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
        echo ""
    fi
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Generated Secret Values"
echo "════════════════════════════════════════════════════════════"
echo ""

# Create a temporary file to store secrets
SECRETS_FILE=$(mktemp)
trap 'rm -f "$SECRETS_FILE"' EXIT

# Production SSH Secrets
if [ -n "$SSH_HOST" ]; then
    echo "# Production SSH Configuration" >> "$SECRETS_FILE"
    echo "PRODUCTION_SSH_HOST=$SSH_HOST" >> "$SECRETS_FILE"
    echo "PRODUCTION_SSH_USER=${SSH_USER:-root}" >> "$SECRETS_FILE"
    echo "PRODUCTION_SSH_PORT=${SSH_PORT:-22}" >> "$SECRETS_FILE"

    if [ -n "$SSH_KEY" ]; then
        echo "PRODUCTION_SSH_KEY<<EOF" >> "$SECRETS_FILE"
        echo "$SSH_KEY" >> "$SECRETS_FILE"
        echo "EOF" >> "$SECRETS_FILE"
    fi
    echo "" >> "$SECRETS_FILE"
fi

# CI Environment Secrets (for testing)
echo "# CI Test Secrets (not production)" >> "$SECRETS_FILE"
echo "CI_ENCRYPTION_KEY=$(openssl rand -base64 32)" >> "$SECRETS_FILE"
echo "CI_SECRET_KEY=$(openssl rand -base64 64)" >> "$SECRETS_FILE"
echo "CI_JWT_SECRET_KEY=$(openssl rand -base64 32)" >> "$SECRETS_FILE"
echo "" >> "$SECRETS_FILE"

# Optional: Codecov
echo "# Optional: Code Coverage (get from https://codecov.io)" >> "$SECRETS_FILE"
echo "# CODECOV_TOKEN=<get-from-codecov.io>" >> "$SECRETS_FILE"
echo "" >> "$SECRETS_FILE"

# Display the secrets
cat "$SECRETS_FILE"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  How to Add Secrets to GitHub"
echo "════════════════════════════════════════════════════════════"
echo ""

if [ "$HAS_GH_CLI" = true ]; then
    echo -e "${GREEN}Option 1: Automatic (using GitHub CLI)${NC}"
    echo ""
    echo "Run these commands:"
    echo ""

    if [ -n "$SSH_HOST" ]; then
        echo -e "${BLUE}# Production SSH${NC}"
        echo "gh secret set PRODUCTION_SSH_HOST --body '$SSH_HOST'"
        echo "gh secret set PRODUCTION_SSH_USER --body '${SSH_USER:-root}'"
        echo "gh secret set PRODUCTION_SSH_PORT --body '${SSH_PORT:-22}'"
        if [ -n "$SSH_KEY" ]; then
            echo "gh secret set PRODUCTION_SSH_KEY < /path/to/private_key"
        fi
        echo ""
    fi

    echo -e "${BLUE}# CI Test Secrets${NC}"
    echo "gh secret set CI_ENCRYPTION_KEY --body '$(grep CI_ENCRYPTION_KEY "$SECRETS_FILE" | cut -d= -f2)'"
    echo "gh secret set CI_SECRET_KEY --body '$(grep CI_SECRET_KEY "$SECRETS_FILE" | cut -d= -f2)'"
    echo "gh secret set CI_JWT_SECRET_KEY --body '$(grep CI_JWT_SECRET_KEY "$SECRETS_FILE" | cut -d= -f2)'"
    echo ""

    echo -n "Would you like to set these secrets now? (y/n): "
    read -r auto_set

    if [[ "$auto_set" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Setting secrets via GitHub CLI..."

        if [ -n "$SSH_HOST" ]; then
            gh secret set PRODUCTION_SSH_HOST --body "$SSH_HOST" && echo "✓ PRODUCTION_SSH_HOST set"
            gh secret set PRODUCTION_SSH_USER --body "${SSH_USER:-root}" && echo "✓ PRODUCTION_SSH_USER set"
            gh secret set PRODUCTION_SSH_PORT --body "${SSH_PORT:-22}" && echo "✓ PRODUCTION_SSH_PORT set"

            if [ -n "$SSH_KEY" ]; then
                echo "$SSH_KEY" | gh secret set PRODUCTION_SSH_KEY && echo "✓ PRODUCTION_SSH_KEY set"
            fi
        fi

        grep CI_ENCRYPTION_KEY "$SECRETS_FILE" | cut -d= -f2 | gh secret set CI_ENCRYPTION_KEY && echo "✓ CI_ENCRYPTION_KEY set"
        grep CI_SECRET_KEY "$SECRETS_FILE" | cut -d= -f2 | gh secret set CI_SECRET_KEY && echo "✓ CI_SECRET_KEY set"
        grep CI_JWT_SECRET_KEY "$SECRETS_FILE" | cut -d= -f2 | gh secret set CI_JWT_SECRET_KEY && echo "✓ CI_JWT_SECRET_KEY set"

        echo ""
        echo -e "${GREEN}✓${NC} Secrets configured successfully!"
        echo ""
        echo "Verify at: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/settings/secrets/actions"
    fi
    echo ""
fi

echo -e "${GREEN}Option $([ "$HAS_GH_CLI" = true ] && echo "2" || echo "1"): Manual (via GitHub Web UI)${NC}"
echo ""
echo "1. Go to: https://github.com/YOUR_USERNAME/pazpaz/settings/secrets/actions"
echo "2. Click 'New repository secret'"
echo "3. Add each secret from the output above:"
echo ""

if [ -n "$SSH_HOST" ]; then
    echo -e "   ${BLUE}Name:${NC} PRODUCTION_SSH_HOST"
    echo -e "   ${BLUE}Value:${NC} $SSH_HOST"
    echo ""
    echo -e "   ${BLUE}Name:${NC} PRODUCTION_SSH_USER"
    echo -e "   ${BLUE}Value:${NC} ${SSH_USER:-root}"
    echo ""
    echo -e "   ${BLUE}Name:${NC} PRODUCTION_SSH_PORT"
    echo -e "   ${BLUE}Value:${NC} ${SSH_PORT:-22}"
    echo ""

    if [ -n "$SSH_KEY" ]; then
        echo -e "   ${BLUE}Name:${NC} PRODUCTION_SSH_KEY"
        echo -e "   ${BLUE}Value:${NC} (paste the entire private key, including BEGIN/END lines)"
        echo ""
    fi
fi

echo "   Plus the CI secrets from the output above (CI_ENCRYPTION_KEY, etc.)"
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  Next Steps"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "1. ✓ Add secrets to GitHub (see instructions above)"
echo "2. Test SSH connection to production server"
echo "3. Run: ./scripts/validate-infrastructure.sh --check=all"
echo "4. Create a test PR to verify CI works"
echo ""

# Save secrets to a file for reference (excluding SSH key)
SAVE_FILE="github-secrets-$(date +%Y%m%d-%H%M%S).txt"
cp "$SECRETS_FILE" "$SAVE_FILE"
echo -e "${GREEN}✓${NC} Secrets saved to: $SAVE_FILE"
echo -e "${RED}!${NC} IMPORTANT: Keep this file secure and delete after use!"
echo ""
