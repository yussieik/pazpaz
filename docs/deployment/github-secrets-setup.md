# GitHub Secrets Setup Guide for PazPaz CI/CD

**Last Updated:** 2025-10-23
**Version:** 1.0
**Status:** Production Ready
**Owner:** DevOps Team
**Repository:** https://github.com/yussieik/pazpaz
**Classification:** Internal - DevOps/Security Personnel Only

---

## Table of Contents

1. [Overview](#overview)
2. [GitHub Secrets Inventory](#github-secrets-inventory)
3. [Setup Instructions](#setup-instructions)
4. [Secret Naming Conventions](#secret-naming-conventions)
5. [Security Best Practices](#security-best-practices)
6. [Integration with CI/CD Workflows](#integration-with-cicd-workflows)
7. [Environment-Specific Secrets](#environment-specific-secrets)
8. [Testing and Validation](#testing-and-validation)
9. [Troubleshooting](#troubleshooting)
10. [Secret Rotation](#secret-rotation)
11. [Emergency Procedures](#emergency-procedures)
12. [Quick Reference](#quick-reference)

---

## Overview

This guide provides comprehensive instructions for setting up GitHub Secrets required for the PazPaz CI/CD pipeline. GitHub Secrets are encrypted environment variables used to store sensitive information needed during automated build and deployment processes.

### Why GitHub Secrets?

- **Security**: Encrypted at rest and in transit
- **Auditability**: All access is logged
- **Integration**: Native support in GitHub Actions
- **Separation**: Keeps secrets out of code and config files
- **Access Control**: Repository-level permissions

### Security Architecture

```
GitHub Secrets (Encrypted)
    ↓
GitHub Actions Runtime (Ephemeral)
    ↓
Deployment Scripts (SSH/Docker)
    ↓
Production Environment (.env files)
```

---

## GitHub Secrets Inventory

### 🔴 Critical Secrets (HIPAA-Required)

| Secret Name | Purpose | Format | Rotation | Priority |
|------------|---------|--------|----------|----------|
| `PROD_ENCRYPTION_MASTER_KEY` | PHI data encryption | Base64 (44 chars) | 90 days | **CRITICAL** |
| `PROD_DATABASE_URL` | PostgreSQL connection | Connection string | 90 days | **CRITICAL** |
| `PROD_POSTGRES_PASSWORD` | Database authentication | 32+ chars | 90 days | **CRITICAL** |

### 🟡 Deployment Secrets (Required for CI/CD)

| Secret Name | Purpose | Format | Rotation | Priority |
|------------|---------|--------|----------|----------|
| `SSH_PRIVATE_KEY` | Server deployment access | Ed25519/RSA key | Annual | HIGH |
| `SSH_HOST` | Production server IP/hostname | IP or domain | As needed | HIGH |
| `SSH_USER` | Deployment username | Username | Never | MEDIUM |
| `SSH_PORT` | SSH port (if not 22) | Number | As needed | LOW |

### 🟢 Application Secrets

| Secret Name | Purpose | Format | Rotation | Priority |
|------------|---------|--------|----------|----------|
| `PROD_SECRET_KEY` | Session signing | Hex (64 chars) | 180 days | HIGH |
| `PROD_JWT_SECRET_KEY` | JWT token signing | Base64 (32 bytes) | 180 days | HIGH |
| `PROD_CSRF_SECRET_KEY` | CSRF protection | Base64 (32 bytes) | 180 days | MEDIUM |
| `PROD_REDIS_PASSWORD` | Redis authentication | 32+ chars | 90 days | MEDIUM |

### 🔵 External Service Secrets

| Secret Name | Purpose | Format | Rotation | Priority |
|------------|---------|--------|----------|----------|
| `PROD_RESEND_API_KEY` | Email service | API key | 180 days | MEDIUM |
| `PROD_SENTRY_DSN` | Error tracking | URL | Annual | LOW |
| `PROD_MINIO_ACCESS_KEY` | Object storage | 16+ chars | 90 days | MEDIUM |
| `PROD_MINIO_SECRET_KEY` | Object storage | 32+ chars | 90 days | MEDIUM |

### ⚪ Container Registry Secrets

| Secret Name | Purpose | Format | Default | Priority |
|------------|---------|--------|---------|----------|
| `GHCR_TOKEN` | GitHub Container Registry | PAT or `GITHUB_TOKEN` | Built-in | MEDIUM |
| `DOCKER_USERNAME` | Docker Hub (optional) | Username | N/A | LOW |
| `DOCKER_PASSWORD` | Docker Hub (optional) | Password/Token | N/A | LOW |

### 🟣 Monitoring Secrets (Optional)

| Secret Name | Purpose | Format | Rotation | Priority |
|------------|---------|--------|----------|----------|
| `SENTRY_AUTH_TOKEN` | Sentry release tracking | Token | Annual | LOW |
| `UPTIME_ROBOT_API_KEY` | Uptime monitoring | API key | Annual | LOW |
| `SLACK_WEBHOOK_URL` | Deployment notifications | Webhook URL | Never | LOW |

---

## Setup Instructions

### Method 1: GitHub Web UI (Recommended for Initial Setup)

#### Step 1: Navigate to Repository Settings

1. Go to https://github.com/yussieik/pazpaz
2. Click on **Settings** tab
3. In left sidebar, expand **Secrets and variables**
4. Click on **Actions**

#### Step 2: Add Each Secret

For each secret in the inventory:

1. Click **New repository secret**
2. Enter the secret **Name** (exactly as listed above)
3. Enter the secret **Value**
4. Click **Add secret**

#### Step 3: Critical Secrets Setup

##### PROD_ENCRYPTION_MASTER_KEY (Most Critical)
```bash
# Generate if not already created (see secrets-management.md)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
- **Name:** `PROD_ENCRYPTION_MASTER_KEY`
- **Value:** [44-character Fernet key]
- **Warning:** Loss = permanent data loss. Back up immediately!

##### SSH_PRIVATE_KEY (For Deployment)
```bash
# If not already generated
ssh-keygen -t ed25519 -C "pazpaz-github-actions" -f pazpaz-deploy -N ""
cat pazpaz-deploy
```
- **Name:** `SSH_PRIVATE_KEY`
- **Value:** Complete private key including BEGIN/END lines:
```
-----BEGIN OPENSSH PRIVATE KEY-----
[key content here]
-----END OPENSSH PRIVATE KEY-----
```

##### Database Secrets
```bash
# Generate strong password
openssl rand -base64 32 | tr -d '/+=' | cut -c1-32
```
- **Name:** `PROD_POSTGRES_PASSWORD`
- **Value:** [32-character password]

- **Name:** `PROD_DATABASE_URL`
- **Value:** `postgresql+asyncpg://pazpaz:[password]@localhost:5432/pazpaz?ssl=require`

### Method 2: GitHub CLI (Recommended for Automation)

#### Install and Authenticate

```bash
# macOS
brew install gh

# Linux (Debian/Ubuntu)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh

# Authenticate (choose HTTPS and browser authentication)
gh auth login
```

#### Add Secrets via CLI

```bash
# Add single-line secrets
gh secret set PROD_SECRET_KEY --body "$(openssl rand -hex 32)"
gh secret set SSH_HOST --body "your-server-ip-or-domain"
gh secret set SSH_USER --body "deploy"
gh secret set SSH_PORT --body "22"

# Add multi-line secrets from file
gh secret set SSH_PRIVATE_KEY < ~/.ssh/pazpaz-deploy
gh secret set PROD_ENCRYPTION_MASTER_KEY < encryption-key.txt

# Add from environment variable
export DB_PASS=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)
gh secret set PROD_POSTGRES_PASSWORD --body "$DB_PASS"

# List all secrets (names only, values are hidden)
gh secret list
```

### Method 3: Bulk Import (Using Script)

See the automation script at `/scripts/setup-github-secrets.sh` (created below).

---

## Secret Naming Conventions

### Naming Rules

1. **UPPERCASE_WITH_UNDERSCORES** - All secrets must use uppercase
2. **Environment Prefix** - Use environment prefixes:
   - `PROD_*` - Production secrets
   - `STAGING_*` - Staging secrets (future)
   - `DEV_*` - Development secrets (rarely needed)
3. **Descriptive Names** - Clear indication of purpose
4. **No Special Characters** - Only A-Z, 0-9, and underscore

### Examples

✅ **Good Names:**
- `PROD_DATABASE_URL`
- `PROD_ENCRYPTION_MASTER_KEY`
- `SSH_PRIVATE_KEY`
- `PROD_REDIS_PASSWORD`

❌ **Bad Names:**
- `database-url` (lowercase, hyphens)
- `PROD_DB` (too abbreviated)
- `PASSWORD` (no context)
- `prod.database.url` (dots not allowed)

### Grouping Convention

Group related secrets with common prefixes:
- `SSH_*` - All SSH-related secrets
- `DOCKER_*` - Container registry secrets
- `PROD_*` - Production environment secrets
- `MONITORING_*` - Monitoring service secrets

---

## Security Best Practices

### 1. SSH Key Generation and Management

```bash
# Generate deployment-specific SSH key
ssh-keygen -t ed25519 -C "github-actions@pazpaz-$(date +%Y%m%d)" -f deploy_key -N ""

# Restrict key on server (authorized_keys)
# Add command restriction to limit what the key can do
echo 'command="/opt/pazpaz/scripts/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding' $(cat deploy_key.pub) >> ~/.ssh/authorized_keys

# Set proper permissions
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh

# After adding to GitHub, securely delete local copy
shred -vfz -n 3 deploy_key
rm deploy_key.pub
```

### 2. Secret Access Control

```yaml
# Repository Settings → Actions → General
# Set "Actions permissions" to:
- ✅ Allow owner, and select non-owner, actions and reusable workflows
- ✅ Allow actions created by GitHub
- ❌ Allow all actions (too permissive)

# Workflow permissions:
- ✅ Read repository contents
- ✅ Write packages (for container registry)
- ❌ Write security events (unless using CodeQL)
```

### 3. Secret Masking in Logs

GitHub automatically masks secrets in logs, but follow these practices:

```yaml
# Good: Secret is masked
- name: Deploy
  run: echo "Deploying with key ${{ secrets.SSH_PRIVATE_KEY }}"
  # Output: Deploying with key ***

# Bad: Can expose partial secrets
- name: Debug
  run: |
    echo "Key starts with: ${KEY:0:10}"  # Don't do this!

# Good: Never echo secrets, even for debugging
- name: Validate secret exists
  run: |
    if [ -z "${{ secrets.PROD_SECRET_KEY }}" ]; then
      echo "ERROR: PROD_SECRET_KEY not set"
      exit 1
    fi
    echo "✅ Secret validated (not shown)"
```

### 4. Repository Security Settings

Enable these GitHub security features:

```bash
# Using GitHub CLI
gh api repos/yussieik/pazpaz -X PATCH \
  -F security_and_analysis='{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}'

# Or via Web UI:
# Settings → Code security and analysis
# ✅ Enable Dependabot alerts
# ✅ Enable Dependabot security updates
# ✅ Enable secret scanning
# ✅ Enable push protection for secrets
```

### 5. Audit Secret Access

```bash
# View audit log (requires appropriate permissions)
gh api /repos/yussieik/pazpaz/actions/secrets/SECRET_NAME

# Monitor secret usage in workflows
gh run list --json name,conclusion,createdAt | jq '.[] | select(.createdAt > "2024-01-01")'
```

---

## Integration with CI/CD Workflows

### Basic Usage in GitHub Actions

```yaml
name: Deploy to Production
on:
  push:
    branches: [main]
  workflow_dispatch:  # Manual trigger

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production  # Optional: use environments for additional protection

    steps:
      - uses: actions/checkout@v4

      # Using secrets in environment variables
      - name: Set up environment
        env:
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
          ENCRYPTION_KEY: ${{ secrets.PROD_ENCRYPTION_MASTER_KEY }}
        run: |
          echo "DATABASE_URL=$DATABASE_URL" >> .env.production
          echo "ENCRYPTION_MASTER_KEY=$ENCRYPTION_KEY" >> .env.production

      # Using secrets for authentication
      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # Using SSH key for deployment
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          port: ${{ secrets.SSH_PORT }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/pazpaz
            ./scripts/deploy.sh
```

### Advanced: Using GitHub Environments

```yaml
# Create environments for additional protection
name: Deploy with Environments

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to Staging
        env:
          DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
        run: echo "Deploying to staging..."

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://pazpaz.com
    steps:
      - name: Deploy to Production
        env:
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
        run: echo "Deploying to production..."
```

### Creating Deployment Environments

```bash
# Via GitHub UI:
# Settings → Environments → New environment

# Configure environment protection rules:
# ✅ Required reviewers (1-2 people)
# ✅ Wait timer (5-30 minutes)
# ✅ Restrict deployment branches (main only)
# ✅ Environment secrets (override repository secrets)
```

---

## Environment-Specific Secrets

### Development Environment

Development typically doesn't use GitHub Secrets. Use local `.env` files:

```bash
# backend/.env (local development)
DATABASE_URL=postgresql+asyncpg://pazpaz:localpass@localhost:5432/pazpaz_dev
ENCRYPTION_MASTER_KEY=dev-key-only-for-local-testing
SECRET_KEY=dev-secret-key-not-for-production
```

### Staging Environment (Future)

When adding staging environment:

```bash
# Add staging-specific secrets
gh secret set STAGING_DATABASE_URL --body "postgresql://staging-connection"
gh secret set STAGING_ENCRYPTION_KEY --body "staging-encryption-key"
gh secret set STAGING_SSH_HOST --body "staging.pazpaz.com"
```

### Production Environment

Production secrets use `PROD_` prefix as documented above.

### Secret Precedence

```yaml
# GitHub Actions secret precedence (highest to lowest):
1. Environment secrets (if using environments)
2. Repository secrets
3. Organization secrets (if applicable)

# Example: Environment secret overrides repository secret
jobs:
  deploy:
    environment: production  # Uses production-specific secrets
    steps:
      - run: echo ${{ secrets.DATABASE_URL }}
        # Uses production environment's DATABASE_URL, not repository's
```

---

## Testing and Validation

### 1. Validate All Secrets Are Set

Create `.github/workflows/validate-secrets.yml`:

```yaml
name: Validate Secrets
on:
  workflow_dispatch:
  schedule:
    - cron: '0 9 * * 1'  # Weekly on Mondays

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - name: Check Critical Secrets
        run: |
          MISSING_SECRETS=""

          # Critical secrets that must exist
          REQUIRED_SECRETS=(
            "PROD_ENCRYPTION_MASTER_KEY"
            "PROD_DATABASE_URL"
            "PROD_POSTGRES_PASSWORD"
            "SSH_PRIVATE_KEY"
            "SSH_HOST"
            "SSH_USER"
            "PROD_SECRET_KEY"
            "PROD_JWT_SECRET_KEY"
          )

          for SECRET in "${REQUIRED_SECRETS[@]}"; do
            if [ -z "${!SECRET}" ]; then
              MISSING_SECRETS="$MISSING_SECRETS $SECRET"
            fi
          done

          if [ -n "$MISSING_SECRETS" ]; then
            echo "❌ Missing secrets:$MISSING_SECRETS"
            exit 1
          fi

          echo "✅ All required secrets are configured"
        env:
          PROD_ENCRYPTION_MASTER_KEY: ${{ secrets.PROD_ENCRYPTION_MASTER_KEY }}
          PROD_DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
          PROD_POSTGRES_PASSWORD: ${{ secrets.PROD_POSTGRES_PASSWORD }}
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
          SSH_HOST: ${{ secrets.SSH_HOST }}
          SSH_USER: ${{ secrets.SSH_USER }}
          PROD_SECRET_KEY: ${{ secrets.PROD_SECRET_KEY }}
          PROD_JWT_SECRET_KEY: ${{ secrets.PROD_JWT_SECRET_KEY }}

      - name: Test SSH Connection
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          port: ${{ secrets.SSH_PORT || 22 }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            echo "✅ SSH connection successful"
            echo "Hostname: $(hostname)"
            echo "User: $(whoami)"
            echo "Path: $(pwd)"
```

### 2. Test Secret Format Validation

```bash
# Local validation script before adding to GitHub
#!/bin/bash

# Test encryption key format (must be valid Fernet key)
validate_encryption_key() {
  local key="$1"
  python3 -c "
from cryptography.fernet import Fernet
try:
    Fernet(b'$key')
    print('✅ Valid encryption key')
except Exception as e:
    print(f'❌ Invalid encryption key: {e}')
    exit(1)
"
}

# Test database URL format
validate_database_url() {
  local url="$1"
  if [[ $url =~ ^postgresql\+asyncpg://[^:]+:[^@]+@[^:]+:[0-9]+/[^?]+(\?.*)?$ ]]; then
    echo "✅ Valid database URL format"
  else
    echo "❌ Invalid database URL format"
    exit 1
  fi
}

# Test SSH key format
validate_ssh_key() {
  local key="$1"
  if echo "$key" | ssh-keygen -l -f - &>/dev/null; then
    echo "✅ Valid SSH key"
  else
    echo "❌ Invalid SSH key format"
    exit 1
  fi
}
```

### 3. Manual Testing Checklist

- [ ] All secrets added to GitHub repository
- [ ] SSH connection test passes
- [ ] Container registry login works
- [ ] No secrets visible in workflow logs
- [ ] Secret rotation calendar created
- [ ] Backup of critical secrets stored securely
- [ ] Team members aware of secret locations

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Secret not found" in workflow

**Symptom:**
```
Error: Input required and not supplied: key
```

**Solutions:**
1. Verify secret name matches exactly (case-sensitive)
2. Check if secret exists: `gh secret list`
3. Ensure workflow has access to secrets
4. Check if using environments (environment secrets override repository secrets)

#### Issue: SSH key authentication fails

**Symptom:**
```
Permission denied (publickey)
```

**Solutions:**
1. Verify key format includes BEGIN/END lines
2. Check server's `authorized_keys` has correct public key
3. Ensure no extra whitespace in secret value
4. Test locally: `ssh -i key_file user@host`

#### Issue: Multiline secret not working

**Symptom:**
```
Error: Unexpected token in JSON
```

**Solution for multiline secrets:**
```yaml
# Wrong - breaks on newlines
- run: echo "${{ secrets.SSH_PRIVATE_KEY }}" > key.pem

# Correct - preserves formatting
- run: |
    cat <<'EOF' > key.pem
    ${{ secrets.SSH_PRIVATE_KEY }}
    EOF
    chmod 600 key.pem
```

#### Issue: Secret visible in logs

**Symptom:**
Secret value appears in workflow logs

**Solutions:**
1. Never use `set -x` in bash when secrets are present
2. Don't use `echo` with secrets
3. Avoid string manipulation on secrets
4. Use `::add-mask::` for dynamic secrets:
```yaml
- run: |
    TOKEN=$(generate_token)
    echo "::add-mask::$TOKEN"
    # Now TOKEN is masked in logs
```

#### Issue: Container registry authentication fails

**Symptom:**
```
Error: unauthorized: authentication required
```

**Solutions:**
```yaml
# For GitHub Container Registry
- uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}  # Built-in token

# For Docker Hub
- uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKER_USERNAME }}
    password: ${{ secrets.DOCKER_PASSWORD }}
```

---

## Secret Rotation

### Rotation Schedule

| Secret Type | Routine | Emergency | Automation |
|------------|---------|-----------|------------|
| Encryption keys | 90 days | 1 hour | Script + manual |
| Database passwords | 90 days | 1 hour | Script |
| API tokens | 180 days | 24 hours | Provider-dependent |
| SSH keys | Annual | 24 hours | Manual |

### Rotation Process

#### 1. Database Password Rotation

```bash
#!/bin/bash
# Rotate database password

# Generate new password
NEW_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)

# Update in GitHub
gh secret set PROD_POSTGRES_PASSWORD --body "$NEW_PASSWORD"

# Update database (via SSH to production)
ssh user@production <<EOF
  psql -U postgres -c "ALTER USER pazpaz PASSWORD '$NEW_PASSWORD';"
  docker-compose restart api worker
EOF

# Verify
gh workflow run validate-secrets.yml
```

#### 2. SSH Key Rotation

```bash
#!/bin/bash
# Rotate SSH deployment key

# Generate new key
ssh-keygen -t ed25519 -C "pazpaz-github-$(date +%Y%m%d)" -f new_deploy_key -N ""

# Add to server
ssh user@production "echo '$(cat new_deploy_key.pub)' >> ~/.ssh/authorized_keys"

# Update GitHub secret
gh secret set SSH_PRIVATE_KEY < new_deploy_key

# Test new key
ssh -i new_deploy_key user@production echo "✅ New key works"

# Remove old key from server
ssh user@production "sed -i '/pazpaz-github-20[0-9][0-9]/d' ~/.ssh/authorized_keys"

# Clean up
shred -vfz new_deploy_key*
```

#### 3. Bulk Secret Rotation

```bash
#!/bin/bash
# Rotate all application secrets

echo "🔄 Rotating PazPaz application secrets..."

# Application secrets
gh secret set PROD_SECRET_KEY --body "$(openssl rand -hex 32)"
gh secret set PROD_JWT_SECRET_KEY --body "$(openssl rand -base64 32)"
gh secret set PROD_CSRF_SECRET_KEY --body "$(openssl rand -base64 32)"

# Redis password
NEW_REDIS_PASS=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)
gh secret set PROD_REDIS_PASSWORD --body "$NEW_REDIS_PASS"

# MinIO credentials
gh secret set PROD_MINIO_ACCESS_KEY --body "$(openssl rand -base64 16 | tr -d '/+=' | cut -c1-16)"
gh secret set PROD_MINIO_SECRET_KEY --body "$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)"

echo "✅ Secrets rotated. Remember to:"
echo "1. Update production environment"
echo "2. Restart services"
echo "3. Test application"
echo "4. Update documentation"
```

---

## Emergency Procedures

### Scenario 1: GitHub Account Compromised

**Immediate Actions:**

```bash
# 1. Revoke all GitHub tokens
gh auth logout

# 2. Rotate ALL secrets immediately
./scripts/emergency-rotate-all-secrets.sh

# 3. Disable GitHub Actions temporarily
gh api repos/yussieik/pazpaz/actions -X PUT -F enabled=false

# 4. Audit recent workflow runs
gh run list --limit 50 --json conclusion,createdAt,headSha | jq '.'

# 5. Re-enable with new credentials
gh auth login
gh api repos/yussieik/pazpaz/actions -X PUT -F enabled=true
```

### Scenario 2: Production Server Compromised

```bash
# 1. Rotate SSH keys immediately
ssh-keygen -t ed25519 -f emergency_key -N ""
# Manually update server's authorized_keys via console/KVM

# 2. Update GitHub secret
gh secret set SSH_PRIVATE_KEY < emergency_key

# 3. Rotate all production secrets
gh secret set PROD_DATABASE_URL --body "new-connection-string"
gh secret set PROD_ENCRYPTION_MASTER_KEY --body "new-encryption-key"
# ... rotate all others

# 4. Rebuild and redeploy
gh workflow run deploy-production.yml
```

### Scenario 3: Secret Exposed in Logs

```bash
# 1. Delete workflow run logs immediately
gh run delete RUN_ID

# 2. Rotate exposed secret
gh secret set EXPOSED_SECRET --body "new-value"

# 3. Audit access logs
gh api /repos/yussieik/pazpaz/actions/runs/RUN_ID/logs

# 4. Update deployment
gh workflow run deploy-production.yml
```

---

## Quick Reference

### Essential Commands

```bash
# Add secret
gh secret set SECRET_NAME --body "value"

# Add from file
gh secret set SECRET_NAME < file.txt

# List secrets
gh secret list

# Delete secret
gh secret delete SECRET_NAME

# View secret metadata (not value)
gh api /repos/yussieik/pazpaz/actions/secrets/SECRET_NAME

# Test SSH connection
ssh -i key_file user@host echo "Connected"

# Validate GitHub token
gh auth status

# Trigger validation workflow
gh workflow run validate-secrets.yml

# View recent workflow runs
gh run list --limit 10

# Check secret in workflow
echo "Secret exists: $([[ -n '${{ secrets.SECRET_NAME }}' ]] && echo 'Yes' || echo 'No')"
```

### Secret Generation Cheat Sheet

```bash
# Encryption key (Fernet)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Strong password (32 chars)
openssl rand -base64 32 | tr -d '/+=' | cut -c1-32

# Hex secret (64 chars)
openssl rand -hex 32

# JWT secret (base64)
openssl rand -base64 32

# SSH key (Ed25519)
ssh-keygen -t ed25519 -C "description" -f keyname -N ""

# Database URL
echo "postgresql+asyncpg://user:$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)@host:5432/db?ssl=require"
```

### Repository Settings Checklist

- [ ] Secret scanning enabled
- [ ] Push protection enabled
- [ ] Dependabot enabled
- [ ] Branch protection on main
- [ ] Required status checks
- [ ] Environments configured (if using)
- [ ] Audit log retention set
- [ ] 2FA required for organization

---

## Related Documentation

- [Secrets Management Guide](./secrets-management.md) - Comprehensive secret generation
- [CI/CD Implementation Plan](./CI_CD_IMPLEMENTATION_PLAN.md) - Overall pipeline design
- [Docker Compose Production](./docker-compose-production.md) - Production configuration
- [HIPAA Compliance](/docs/security/SECURITY_ARCHITECTURE.md) - Security requirements
- [GitHub Actions Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

---

## Automation Script

The automation script for setting up GitHub Secrets is available at:
- `/scripts/setup-github-secrets.sh`

This script provides interactive setup and validation of all required secrets.

---

**Document Maintenance:**
- **Owner:** DevOps Team
- **Review Frequency:** Quarterly
- **Last Review:** 2025-10-23
- **Next Review:** 2026-01-23
- **Version Control:** Git
- **Change Log:** See git history