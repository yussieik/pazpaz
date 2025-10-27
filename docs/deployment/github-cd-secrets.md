# GitHub Actions CD Secrets Configuration

This document provides detailed instructions for configuring the required GitHub Secrets and Variables for the PazPaz continuous deployment pipeline.

**Status:** ✅ Automated CD is **live in production** as of October 27, 2025

**Production Environment:**
- URL: https://pazpaz.health
- Server: 5.161.241.81 (Hetzner Cloud CPX41)
- Deployment Method: Automated via GitHub Actions on push to main

## Repository Variables

These are non-secret configuration values that control workflow features. Set these in **Settings → Secrets and variables → Actions → Variables**.

### Optional Feature Toggles

- **`ENABLE_SLACK_NOTIFICATIONS`** (default: unset/false)
  - Set to `true` to enable Slack notifications for deployments
  - Only set this if you have configured `SLACK_WEBHOOK_URL` secret
  - Without this variable, Slack notification step will be skipped

- **`ENABLE_SENTRY_RELEASES`** (default: unset/false)
  - Set to `true` to enable Sentry release tracking
  - Only set this if you have configured `SENTRY_AUTH_TOKEN` secret
  - Without this variable, Sentry release step will be skipped

**How to set variables:**
```bash
# Using GitHub CLI
gh variable set ENABLE_SLACK_NOTIFICATIONS --body "true"
gh variable set ENABLE_SENTRY_RELEASES --body "true"

# Or via GitHub UI:
# Settings → Secrets and variables → Actions → Variables tab → New repository variable
```

## Required Secrets

The following secrets are configured for the production deployment pipeline:

### 1. PRODUCTION_SSH_KEY (Required) ✅
**Description**: ED25519 SSH private key for authenticating with the production server.

**Current Configuration:**
- ✅ Configured and working
- Format: ED25519 private key
- Access: `root@5.161.241.81`
- Usage: Both frontend and backend workflows

**How to generate and configure** (for reference/rotation):
```bash
# 1. Generate a new ED25519 SSH key pair (recommended over RSA for security)
ssh-keygen -t ed25519 -f ~/.ssh/pazpaz-deploy -C "github-actions@pazpaz"

# 2. Copy the public key to the production server
ssh-copy-id -i ~/.ssh/pazpaz-deploy.pub root@5.161.241.81

# 3. Test the connection
ssh -i ~/.ssh/pazpaz-deploy root@5.161.241.81 "echo 'Connection successful'"

# 4. Add the private key to GitHub Secrets
gh secret set PRODUCTION_SSH_KEY < ~/.ssh/pazpaz-deploy
```

**Security Notes**:
- Never commit the private key to the repository
- Use a dedicated deployment key, not your personal SSH key
- Consider rotating this key every 90 days
- Store a backup of the key pair in a secure password manager

### 2. PROD_ENCRYPTION_MASTER_KEY (Required) ✅
**Description**: Master encryption key for HIPAA-compliant PHI encryption.

**Current Configuration:**
- ✅ Configured and working
- Validated weekly by `.github/workflows/validate-secrets.yml`
- Critical for HIPAA compliance

**How to configure**:
```bash
# Generate a secure 32-byte key (base64 encoded)
openssl rand -base64 32

# Add to GitHub Secrets
gh secret set PROD_ENCRYPTION_MASTER_KEY --body "your-base64-key-here"
```

**Important:** This key is critical for PHI encryption. Loss of this key means loss of access to encrypted patient data.

### 3. SSH Host, User, and Port (Hardcoded)

**Important:** These values are **NOT configured as secrets**. They are hardcoded directly in the workflow files for simplicity.

**Current Configuration:**
- SSH Host: `5.161.241.81` (hardcoded in workflows)
- SSH User: `root` (hardcoded in workflows)
- SSH Port: `22` (default, not specified)

**Location in workflows:**
- Backend: `.github/workflows/backend-ci.yml` (line 678)
- Frontend: `.github/workflows/frontend-ci.yml` (line 511)

**Example from workflow:**
```yaml
- name: Deploy backend to production
  run: |
    ssh root@5.161.241.81 << 'ENDSSH'
      # deployment commands
    ENDSSH
```

**Note:** If you need to change these values, edit the workflow files directly rather than using secrets.

### 4. Production Domain (Hardcoded)

**Current Configuration:**
- Domain: `pazpaz.health` (hardcoded in health checks)
- No GitHub secret required

**Location in workflows:**
- Backend health check: `.github/workflows/backend-ci.yml` (line 726)
- Frontend health check: `.github/workflows/frontend-ci.yml` (line 553)

**Example from workflow:**
```yaml
- name: Verify deployment health
  run: |
    if curl -f -s -o /dev/null -w "%{http_code}" https://pazpaz.health/ | grep -q "200"; then
      echo "✅ Production site is accessible"
    fi
```

### 5. GITHUB_TOKEN (Automatic)
**Description**: Automatically provided by GitHub Actions for authenticating with GitHub Container Registry.

**Current Configuration:**
- ✅ Automatically available in all workflows
- Used for: Pushing/pulling Docker images from ghcr.io
- No manual configuration needed

**Usage in workflows:**
```yaml
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

## Optional Secrets

### 7. SLACK_WEBHOOK_URL (Optional)
**Description**: Webhook URL for Slack deployment notifications.

**How to create**:
1. Go to https://api.slack.com/apps
2. Create a new app or select existing
3. Enable "Incoming Webhooks"
4. Add new webhook to workspace
5. Select channel for notifications
6. Copy webhook URL

**How to configure**:
```bash
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/YOUR_WORKSPACE_ID/YOUR_CHANNEL_ID/YOUR_WEBHOOK_TOKEN"
```

**Test webhook**:
```bash
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test deployment notification"}' \
  YOUR_WEBHOOK_URL
```

### 8. SENTRY_AUTH_TOKEN (Optional)
**Description**: Authentication token for Sentry release tracking and error monitoring.

**How to create**:
1. Go to Sentry Settings > Account > API > Auth Tokens
2. Create new token with scopes:
   - `project:releases` - Create and manage releases
   - `org:read` - Read organization details
3. Copy token

**How to configure**:
```bash
gh secret set SENTRY_AUTH_TOKEN --body "your-sentry-token"
gh secret set SENTRY_ORG --body "your-org-slug"
gh secret set SENTRY_PROJECT --body "pazpaz"
```

### 9. DISCORD_WEBHOOK_URL (Optional)
**Description**: Alternative to Slack for deployment notifications.

**How to create**:
1. Open Discord server settings
2. Go to Integrations > Webhooks
3. Create new webhook
4. Copy webhook URL

### 10. CODECOV_TOKEN (Optional)
**Description**: Token for uploading coverage reports to Codecov.

**How to get**:
1. Sign up at https://codecov.io
2. Add repository
3. Copy the upload token

## Environment-Specific Secrets

For staging/production separation, prefix secrets with environment:

- `PRODUCTION_SSH_HOST`
- `STAGING_SSH_HOST`
- `PRODUCTION_DOMAIN`
- `STAGING_DOMAIN`

## Security Best Practices

### 1. Secret Rotation Schedule
Implement regular rotation for sensitive secrets:
- SSH keys: Every 90 days
- PAT tokens: Every 90 days
- Webhook URLs: Annually or when personnel change

### 2. Access Control
- Limit who can view/edit secrets (Repository Settings > Manage access)
- Use environment protection rules for production deployments
- Require approval for production deployments

### 3. Audit Trail
- GitHub automatically logs secret access
- Review audit logs regularly: Settings > Security > Audit log

### 4. Secret Scanning
GitHub automatically scans for exposed secrets. Additional measures:
- Enable push protection
- Use `.gitignore` for `.env` files
- Never log secret values in workflows

## Troubleshooting

### SSH Connection Issues
```bash
# Test from GitHub Actions
- name: Debug SSH
  run: |
    ssh -vvv production "echo 'test'"

# Common issues:
# 1. Permission denied: Check SSH key and authorized_keys
# 2. Connection timeout: Check firewall/security groups
# 3. Host key verification: Add to known_hosts or use StrictHostKeyChecking=no
```

### GHCR Authentication Issues
```bash
# Test authentication locally
echo $GHCR_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull test
docker pull ghcr.io/your-org/pazpaz/backend:latest
```

### Missing Secrets Error
If deployment fails with "Missing required secrets":
1. Check all required secrets are set
2. Verify secret names match exactly (case-sensitive)
3. Ensure no extra spaces in secret values
4. Check repository has access to organization secrets (if used)

## Quick Setup Script

For quick setup, save and run this script:

```bash
#!/bin/bash
# setup-cd-secrets.sh

echo "PazPaz CD Secrets Setup"
echo "======================"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI not installed. Install from: https://cli.github.com/"
    exit 1
fi

# Authenticate if needed
gh auth status || gh auth login

# Prompt for required values
read -p "Enter SSH Host (IP or domain): " SSH_HOST
read -p "Enter SSH User [deploy]: " SSH_USER
SSH_USER=${SSH_USER:-deploy}
read -p "Enter SSH Port [22]: " SSH_PORT
SSH_PORT=${SSH_PORT:-22}
read -p "Enter Production Domain: " DOMAIN

# Generate SSH key if it doesn't exist
SSH_KEY_PATH="$HOME/.ssh/pazpaz-deploy"
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "Generating SSH key..."
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -C "github-actions@pazpaz" -N ""
    echo "Public key generated. Add this to your server's authorized_keys:"
    cat "${SSH_KEY_PATH}.pub"
    read -p "Press enter once you've added the public key to the server..."
fi

# Set secrets
echo "Setting GitHub Secrets..."
gh secret set SSH_HOST --body "$SSH_HOST"
gh secret set SSH_USER --body "$SSH_USER"
gh secret set SSH_PORT --body "$SSH_PORT"
gh secret set DOMAIN --body "$DOMAIN"
gh secret set SSH_PRIVATE_KEY < "$SSH_KEY_PATH"

echo ""
echo "Required secrets configured! ✅"
echo ""
echo "Optional: Add these secrets manually if needed:"
echo "  - GHCR_TOKEN (for private registries)"
echo "  - SLACK_WEBHOOK_URL (for notifications)"
echo "  - SENTRY_AUTH_TOKEN (for error tracking)"
echo ""
echo "Test deployment with:"
echo "  gh workflow run 'Deploy Production' -f environment=production -f image_tag=latest -f dry_run=true"
```

Make executable and run:
```bash
chmod +x setup-cd-secrets.sh
./setup-cd-secrets.sh
```

## Verification

**Current Status:** ✅ All required secrets are configured and validated

### Verify Secrets Configuration

```bash
# List all secrets (names only, not values)
gh secret list

# Should show at minimum:
# - PRODUCTION_SSH_KEY
# - PROD_ENCRYPTION_MASTER_KEY
```

### Test Automated Deployment

**Option 1: Trigger validation workflow**
```bash
# Run secrets validation workflow
gh workflow run "Validate GitHub Secrets Configuration"

# Watch the run
gh run watch

# This will:
# - Validate PROD_ENCRYPTION_MASTER_KEY exists
# - Test SSH connectivity to 5.161.241.81
# - Check container health patterns
```

**Option 2: Trigger full deployment**
```bash
# Trigger backend deployment (will also deploy if you push to main)
gh workflow run "Backend CI" --ref main

# Trigger frontend deployment
gh workflow run "Frontend CI" --ref main

# Watch the runs
gh run watch
```

**Option 3: Push to main (automatic deployment)**
```bash
# Make any change and push to main
git add .
git commit -m "test: trigger automated deployment"
git push origin main

# Deployment will automatically trigger
gh run watch
```

### Verify Production Deployment

After deployment completes, verify production is working:

```bash
# Check API health
curl https://pazpaz.health/api/v1/health
# Should return: {"status":"ok"}

# Check frontend
curl -I https://pazpaz.health/
# Should return: HTTP/2 200

# SSH to server and check containers
ssh root@5.161.241.81 "cd /opt/pazpaz && docker compose -f docker-compose.prod.yml ps"
```

## Current Workflow Configuration Summary

### Backend CI/CD (`.github/workflows/backend-ci.yml`)

**Triggers:**
- Push to main (paths: `backend/**`, `.github/workflows/backend-ci.yml`, `pyproject.toml`)
- Pull requests to main
- Manual workflow dispatch

**Jobs:**
1. **Test & Quality Checks** - pytest with 90% pass rate requirement
2. **Security Scanning** - Trivy, CodeQL, dependency checks
3. **OpenAPI Validation** - API spec validation
4. **Docker Build** - Build and push to ghcr.io/yussieik/pazpaz-backend
5. **Deploy to Production** - SSH deploy to 5.161.241.81 (only on main push)

**Deployment Steps:**
1. Pull latest backend images (api, arq-worker)
2. Run Alembic migrations: `alembic upgrade head`
3. Recreate containers: `docker compose up -d --force-recreate api arq-worker`
4. Verify container health: `docker ps | grep "Up.*pazpaz-api"`
5. Verify API health: `curl https://pazpaz.health/api/v1/health`

### Frontend CI/CD (`.github/workflows/frontend-ci.yml`)

**Triggers:**
- Push to main (paths: `frontend/**`, `.github/workflows/frontend-ci.yml`, `package.json`)
- Pull requests to main
- Manual workflow dispatch

**Jobs:**
1. **Test & Quality Checks** - ESLint, Prettier, TypeScript, Vitest
2. **Security Scanning** - npm audit, Trivy
3. **License Compliance** - License checker
4. **Bundle Size Analysis** - Size comparison (PRs only)
5. **Docker Build** - Build and push to ghcr.io/yussieik/pazpaz-frontend
6. **Deploy to Production** - SSH deploy to 5.161.241.81 (only on main push)

**Deployment Steps:**
1. Pull latest frontend image
2. Recreate containers: `docker compose up -d --force-recreate frontend nginx`
3. Verify container health: `docker ps | grep "Up.*pazpaz-frontend"`
4. Verify site accessibility: `curl https://pazpaz.health/`

### Secrets Validation (`.github/workflows/validate-secrets.yml`)

**Triggers:**
- Weekly schedule (Mondays at 9 AM UTC)
- Manual workflow dispatch

**Checks:**
1. **Critical Secrets** - PROD_ENCRYPTION_MASTER_KEY (fails if missing)
2. **Database Secrets** - PROD_DATABASE_URL, PROD_POSTGRES_PASSWORD
3. **SSH Secrets** - SSH_PRIVATE_KEY (hardcoded host/user)
4. **Application Secrets** - PROD_SECRET_KEY, PROD_JWT_SECRET_KEY, etc.
5. **SSH Connection Test** - Live test to 5.161.241.81
6. **Server Health Check** - Docker installation, /opt/pazpaz directory

### Key Differences from Documentation Template

The actual implementation differs from the generic template in these ways:

1. **SSH credentials are hardcoded** - Not using SSH_HOST, SSH_USER, SSH_PORT secrets
2. **Domain is hardcoded** - Not using DOMAIN secret (uses pazpaz.health directly)
3. **Simplified secret management** - Only 2 critical secrets: PRODUCTION_SSH_KEY and PROD_ENCRYPTION_MASTER_KEY
4. **Direct root access** - Uses root@5.161.241.81 instead of dedicated deploy user
5. **Container health checks** - Uses pattern matching: `docker ps | grep "Up.*container-name"`

## Support

For issues with secret configuration:
1. Check the GitHub Actions logs for specific error messages
2. Verify all required secrets are set correctly
3. Test SSH and Docker registry access manually
4. Review server firewall and security group settings
5. Check the deployment scripts have proper permissions

**Production Support:**
- SSH: `ssh root@5.161.241.81`
- Logs: `cd /opt/pazpaz && docker compose -f docker-compose.prod.yml logs -f`
- Workflow logs: `gh run list --limit 5`

Remember: Never share secret values in issues, logs, or commits!

---

**Last Updated:** October 27, 2025
**Status:** Production (Automated CD Live)