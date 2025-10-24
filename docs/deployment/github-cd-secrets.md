# GitHub Actions CD Secrets Configuration

This document provides detailed instructions for configuring the required GitHub Secrets and Variables for the PazPaz continuous deployment pipeline.

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

The following secrets **MUST** be configured for the deployment workflow to function properly:

### 1. SSH_PRIVATE_KEY (Required)
**Description**: ED25519 SSH private key for authenticating with the production server.

**How to generate and configure**:
```bash
# 1. Generate a new ED25519 SSH key pair (recommended over RSA for security)
ssh-keygen -t ed25519 -f ~/.ssh/pazpaz-deploy -C "github-actions@pazpaz"

# 2. Copy the public key to the production server
ssh-copy-id -i ~/.ssh/pazpaz-deploy.pub user@your-server.com

# 3. Test the connection
ssh -i ~/.ssh/pazpaz-deploy user@your-server.com "echo 'Connection successful'"

# 4. Add the private key to GitHub Secrets
# Option A: Using GitHub CLI
gh secret set SSH_PRIVATE_KEY < ~/.ssh/pazpaz-deploy

# Option B: Manual via GitHub UI
# - Copy the private key content:
cat ~/.ssh/pazpaz-deploy
# - Go to: Settings > Secrets and variables > Actions
# - Click "New repository secret"
# - Name: SSH_PRIVATE_KEY
# - Value: Paste the entire private key including BEGIN and END lines
```

**Security Notes**:
- Never commit the private key to the repository
- Use a dedicated deployment key, not your personal SSH key
- Consider rotating this key every 90 days
- Store a backup of the key pair in a secure password manager

### 2. SSH_HOST (Required)
**Description**: The hostname or IP address of your production server.

**Examples**:
- IP address: `185.199.108.153`
- Hostname: `pazpaz-prod.example.com`

**How to configure**:
```bash
# Using GitHub CLI
gh secret set SSH_HOST --body "your-server.com"

# Verify the hostname is reachable
ping -c 3 your-server.com
```

### 3. SSH_USER (Required)
**Description**: The username for SSH connection. Should be a non-root user with sudo privileges.

**Setup on server**:
```bash
# Create a dedicated deployment user on the server
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy  # Add to docker group
sudo usermod -aG sudo deploy    # Add sudo privileges (if needed)

# Set up passwordless sudo for specific commands (optional but recommended)
echo "deploy ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker-compose" | sudo tee /etc/sudoers.d/deploy
```

**How to configure**:
```bash
gh secret set SSH_USER --body "deploy"
```

### 4. SSH_PORT (Optional)
**Description**: SSH port if not using the default port 22.

**Default**: `22`

**How to configure** (if using non-standard port):
```bash
gh secret set SSH_PORT --body "2222"
```

### 5. GHCR_TOKEN (Optional)
**Description**: Personal Access Token for GitHub Container Registry. Required if repository is private.

**How to create**:
1. Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name: "PazPaz GHCR Deployment"
4. Select scopes:
   - `read:packages` - Download container images
   - `write:packages` - Upload container images (if needed)
   - `delete:packages` - Delete old images (optional)
5. Set expiration (recommend 90 days with rotation reminders)
6. Generate token and copy immediately (won't be shown again)

**How to configure**:
```bash
gh secret set GHCR_TOKEN --body "ghp_xxxxxxxxxxxxxxxxxxxx"
```

**Note**: If repository is public, you can use `GITHUB_TOKEN` instead, which is automatically available.

### 6. DOMAIN (Required)
**Description**: The production domain name where PazPaz is deployed.

**Examples**:
- `app.pazpaz.com`
- `pazpaz.example.com`
- `therapy.yourdomain.com`

**How to configure**:
```bash
gh secret set DOMAIN --body "app.pazpaz.com"
```

**DNS Setup**:
Ensure your domain points to your server:
```bash
# Verify DNS resolution
nslookup app.pazpaz.com
dig app.pazpaz.com

# Should return your server's IP address
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

After setting up all secrets, verify configuration:

```bash
# List all secrets (names only, not values)
gh secret list

# Test deployment in dry-run mode
gh workflow run "Deploy Production" \
  -f environment=production \
  -f image_tag=latest \
  -f dry_run=true

# Watch the workflow run
gh run watch
```

## Support

For issues with secret configuration:
1. Check the GitHub Actions logs for specific error messages
2. Verify all required secrets are set correctly
3. Test SSH and Docker registry access manually
4. Review server firewall and security group settings
5. Check the deployment scripts have proper permissions

Remember: Never share secret values in issues, logs, or commits!