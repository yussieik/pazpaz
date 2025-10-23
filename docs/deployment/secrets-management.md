# PazPaz Secrets Management Guide

**Last Updated:** 2025-10-23
**Version:** 1.0
**Status:** Production Ready
**Classification:** Internal (Sensitive - DevOps/Security Personnel Only)
**HIPAA Critical:** This document contains procedures for managing PHI encryption keys

---

## Table of Contents

1. [Overview](#overview)
2. [Secrets Inventory](#secrets-inventory)
3. [Generation Instructions](#generation-instructions)
4. [Storage Guidelines](#storage-guidelines)
5. [GitHub Actions Secrets Setup](#github-actions-secrets-setup)
6. [HIPAA Compliance Considerations](#hipaa-compliance-considerations)
7. [Secret Rotation Procedures](#secret-rotation-procedures)
8. [Emergency Procedures](#emergency-procedures)
9. [Validation Checklist](#validation-checklist)
10. [Quick Reference](#quick-reference)

---

## Overview

This document provides comprehensive guidance for generating, managing, and rotating all secrets required for PazPaz production deployment through CI/CD pipelines. Proper secret management is **CRITICAL** for HIPAA compliance and protecting PHI (Protected Health Information).

### Security Principles

- **Never commit secrets to version control** - Use `.env` files locally, AWS Secrets Manager in production
- **Generate cryptographically secure secrets** - Use proper entropy sources (never use weak passwords)
- **Rotate regularly** - 90-day rotation for critical secrets (HIPAA requirement)
- **Audit all access** - Log and monitor secret access patterns
- **Encrypt at rest and in transit** - All secrets must be encrypted
- **Principle of least privilege** - Grant minimum necessary access

### Environments

| Environment | Secret Storage | Access Method | Rotation |
|------------|---------------|---------------|-----------|
| **Local Development** | `.env` files | Environment variables | Manual |
| **CI/CD Pipeline** | GitHub Secrets | `${{ secrets.NAME }}` | 90 days |
| **Staging** | AWS Secrets Manager | IAM role | Automated |
| **Production** | AWS Secrets Manager | IAM role | Automated |

---

## Secrets Inventory

### Critical Secrets (PHI Encryption)

| Secret Name | Purpose | Format | Strength | Rotation | Impact if Lost |
|------------|---------|--------|----------|----------|----------------|
| `ENCRYPTION_MASTER_KEY` | PHI data encryption | Base64 (32 bytes) | 256 bits | 90 days | **DATA LOSS** |
| `POSTGRES_PASSWORD` | Database authentication | Alphanumeric + symbols | 32+ chars | 90 days | Service outage |
| `DATABASE_URL` | PostgreSQL connection | Connection string | N/A | 90 days | Service outage |

### Application Secrets

| Secret Name | Purpose | Format | Strength | Rotation | Impact if Lost |
|------------|---------|--------|----------|----------|----------------|
| `SECRET_KEY` | Session signing | Hex string | 64 chars | 180 days | Session invalidation |
| `JWT_SECRET_KEY` | JWT token signing | Base64 (32 bytes) | 256 bits | 180 days | Auth failure |
| `CSRF_SECRET_KEY` | CSRF protection | Base64 (32 bytes) | 256 bits | 180 days | Security vulnerability |

### External Service Secrets

| Secret Name | Purpose | Format | Strength | Rotation | Impact if Lost |
|------------|---------|--------|----------|----------|----------------|
| `RESEND_API_KEY` | Email service | API key | Provider-specific | 180 days | Email failure |
| `SENTRY_DSN` | Error tracking | URL with auth | N/A | Annual | No monitoring |
| `MINIO_ACCESS_KEY` | Object storage access | Alphanumeric | 16+ chars | 90 days | File upload failure |
| `MINIO_SECRET_KEY` | Object storage secret | Alphanumeric + symbols | 32+ chars | 90 days | File upload failure |
| `REDIS_PASSWORD` | Cache authentication | Alphanumeric + symbols | 32+ chars | 90 days | Cache failure |

### CI/CD Deployment Secrets

| Secret Name | Purpose | Format | Strength | Rotation | Impact if Lost |
|------------|---------|--------|----------|----------|----------------|
| `SSH_PRIVATE_KEY` | Server deployment | RSA/Ed25519 key | 4096 bits | Annual | Cannot deploy |
| `SSH_HOST` | Deployment target | IP/hostname | N/A | As needed | Cannot deploy |
| `SSH_USER` | Deployment user | Username | N/A | Never | Cannot deploy |
| `DOCKER_REGISTRY_PASSWORD` | Registry auth | Token | Provider-specific | 90 days | Cannot push images |

---

## Generation Instructions

### CRITICAL: Encryption Master Key (PHI Protection)

**⚠️ WARNING**: Loss of this key means **PERMANENT DATA LOSS**. No recovery possible.

```bash
# Generate AES-256 encryption key (32 bytes, base64-encoded)
# This key encrypts ALL PHI data (client names, session notes, etc.)

# Method 1: Using OpenSSL (recommended)
openssl rand -base64 32

# Method 2: Using Python cryptography library
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Method 3: Using Python secrets module
python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# Verify key strength (must be exactly 44 characters for Fernet)
KEY="your-generated-key-here"
python3 -c "import base64; k=base64.urlsafe_b64decode('$KEY'+'=='); print(f'✅ Valid: {len(k)==32} bytes')"
```

**Storage Requirements:**
- Store in 3 locations minimum (AWS Secrets Manager, offline backup, secure vault)
- Document key version (v1, v2, v3, etc.)
- Never store in plain text files
- Backup immediately after generation

### Database Credentials

```bash
# Generate PostgreSQL password (32 characters minimum)
# Must include uppercase, lowercase, numbers, and symbols

# Method 1: OpenSSL with character filtering
openssl rand -base64 48 | tr -d '/+=' | cut -c1-32

# Method 2: Python with full character set
python3 -c "
import secrets
import string
alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
password = ''.join(secrets.choice(alphabet) for _ in range(32))
print(password)
"

# Generate complete DATABASE_URL
DB_USER="pazpaz"
DB_PASS="$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-32)"
DB_HOST="db.pazpaz.internal"
DB_PORT="5432"
DB_NAME="pazpaz"

echo "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}?ssl=require"
```

### Application Secret Keys

```bash
# Generate SECRET_KEY for session signing (64-character hex)
openssl rand -hex 32

# Generate JWT_SECRET_KEY (32 bytes, base64)
openssl rand -base64 32

# Generate CSRF protection key (32 bytes, base64)
openssl rand -base64 32

# Generate all application keys at once
cat <<EOF
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -base64 32)
CSRF_SECRET_KEY=$(openssl rand -base64 32)
EOF
```

### MinIO/S3 Credentials

```bash
# Generate MinIO access key (16 characters alphanumeric)
MINIO_ACCESS_KEY=$(openssl rand -base64 16 | tr -d '/+=' | cut -c1-16)

# Generate MinIO secret key (32 characters)
MINIO_SECRET_KEY=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)

# Generate MinIO encryption key for server-side encryption
MINIO_ENCRYPTION_KEY=$(python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

echo "MINIO_ACCESS_KEY=$MINIO_ACCESS_KEY"
echo "MINIO_SECRET_KEY=$MINIO_SECRET_KEY"
echo "MINIO_ENCRYPTION_KEY=$MINIO_ENCRYPTION_KEY"
```

### Redis Password

```bash
# Generate Redis password (32 characters)
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)

# Create Redis URL
echo "REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0"
```

### SSH Deployment Keys

```bash
# Generate Ed25519 SSH key pair for deployment
# Ed25519 is more secure and faster than RSA

# Generate key pair (no passphrase for CI/CD)
ssh-keygen -t ed25519 -C "pazpaz-ci@github.com" -f ~/.ssh/pazpaz-deploy -N ""

# Or generate RSA key (4096 bits) if Ed25519 not supported
ssh-keygen -t rsa -b 4096 -C "pazpaz-ci@github.com" -f ~/.ssh/pazpaz-deploy -N ""

# Display public key (add to server's authorized_keys)
cat ~/.ssh/pazpaz-deploy.pub

# Display private key (add to GitHub Secrets)
cat ~/.ssh/pazpaz-deploy

# IMPORTANT: After adding to GitHub Secrets, delete local copy
shred -u ~/.ssh/pazpaz-deploy*
```

### Complete Secret Generation Script

Create `scripts/generate-secrets.sh`:

```bash
#!/bin/bash
# PazPaz Secret Generation Script
# Generates all required secrets for production deployment

set -euo pipefail

echo "🔐 PazPaz Secret Generator v1.0"
echo "================================"
echo ""
echo "⚠️  SECURITY WARNING:"
echo "- Save these secrets immediately in a password manager"
echo "- Never commit these values to git"
echo "- Delete this output after saving"
echo ""

# Check dependencies
command -v openssl >/dev/null 2>&1 || { echo "❌ openssl required but not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required but not installed."; exit 1; }

# Generate secrets
cat <<EOF
# ============================================
# CRITICAL: PHI ENCRYPTION (HIPAA REQUIRED)
# ============================================
# WARNING: Loss of this key = PERMANENT DATA LOSS
ENCRYPTION_MASTER_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# ============================================
# DATABASE CREDENTIALS
# ============================================
POSTGRES_PASSWORD=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-32)
DATABASE_URL=postgresql+asyncpg://pazpaz:\${POSTGRES_PASSWORD}@db:5432/pazpaz?ssl=require

# ============================================
# APPLICATION SECRETS
# ============================================
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -base64 32)
CSRF_SECRET_KEY=$(openssl rand -base64 32)

# ============================================
# REDIS CACHE
# ============================================
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)
REDIS_URL=redis://:\${REDIS_PASSWORD}@redis:6379/0

# ============================================
# MINIO/S3 OBJECT STORAGE
# ============================================
MINIO_ACCESS_KEY=$(openssl rand -base64 16 | tr -d '/+=' | cut -c1-16)
MINIO_SECRET_KEY=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)
MINIO_ENCRYPTION_KEY=$(python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# ============================================
# EXTERNAL SERVICES (configure as needed)
# ============================================
# RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx  # Get from https://resend.com
# SENTRY_DSN=https://xxxxx@sentry.io/xxxxx  # Get from https://sentry.io

EOF

echo ""
echo "✅ Secrets generated successfully!"
echo ""
echo "NEXT STEPS:"
echo "1. Copy these secrets to a password manager immediately"
echo "2. Add to GitHub Secrets (Settings → Secrets → Actions)"
echo "3. Create production .env file on server"
echo "4. Delete this output (history -c && rm ~/.bash_history)"
echo "5. Test deployment with new secrets"
```

---

## Storage Guidelines

### Development Environment

**Location:** `backend/.env` (never commit!)

```bash
# Create .env from template
cp backend/.env.example backend/.env

# Edit with generated secrets
nano backend/.env

# Verify .env is in .gitignore
grep "^.env$" backend/.gitignore || echo ".env" >> backend/.gitignore
```

### CI/CD Environment (GitHub Actions)

**Location:** GitHub Repository Settings → Secrets and variables → Actions

**Required GitHub Secrets:**

```yaml
# Database
POSTGRES_PASSWORD
DATABASE_URL

# Application
SECRET_KEY
JWT_SECRET_KEY
ENCRYPTION_MASTER_KEY

# External Services
RESEND_API_KEY
SENTRY_DSN
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
REDIS_PASSWORD

# Deployment
SSH_PRIVATE_KEY
SSH_HOST
SSH_USER
DOCKER_REGISTRY_TOKEN
```

### Production Environment

**Primary Storage:** AWS Secrets Manager
**Backup Storage:** Encrypted offline backup

```bash
# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v2 \
  --description "PazPaz PHI encryption master key v2" \
  --secret-string "$ENCRYPTION_MASTER_KEY" \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=HIPAA,Value=critical

# Enable automatic rotation (90 days)
aws secretsmanager rotate-secret \
  --secret-id pazpaz/encryption-key-v2 \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:xxxxx:function:SecretsManagerRotation

# Verify secret stored
aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key-v2 \
  --query SecretString \
  --output text | head -c 10
```

---

## GitHub Actions Secrets Setup

### Step-by-Step Configuration

#### 1. Navigate to Repository Settings

```
https://github.com/[your-org]/pazpaz → Settings → Secrets and variables → Actions
```

#### 2. Add Required Secrets

Click "New repository secret" for each:

**Database Secrets:**
- **Name:** `POSTGRES_PASSWORD`
- **Value:** `[32-character password from generation]`

- **Name:** `DATABASE_URL`
- **Value:** `postgresql+asyncpg://pazpaz:[password]@db:5432/pazpaz?ssl=require`

**Application Secrets:**
- **Name:** `ENCRYPTION_MASTER_KEY`
- **Value:** `[44-character Fernet key - CRITICAL]`

- **Name:** `SECRET_KEY`
- **Value:** `[64-character hex string]`

- **Name:** `JWT_SECRET_KEY`
- **Value:** `[32-byte base64 string]`

**Deployment Secrets:**
- **Name:** `SSH_PRIVATE_KEY`
- **Value:** `[Complete private key including BEGIN/END lines]`
  ```
  -----BEGIN OPENSSH PRIVATE KEY-----
  [key content]
  -----END OPENSSH PRIVATE KEY-----
  ```

- **Name:** `SSH_HOST`
- **Value:** `[Server IP or hostname]`

- **Name:** `SSH_USER`
- **Value:** `deploy` (or your deployment user)

#### 3. Using Secrets in Workflows

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Create .env file
        run: |
          cat <<EOF > .env.production
          DATABASE_URL=${{ secrets.DATABASE_URL }}
          ENCRYPTION_MASTER_KEY=${{ secrets.ENCRYPTION_MASTER_KEY }}
          SECRET_KEY=${{ secrets.SECRET_KEY }}
          JWT_SECRET_KEY=${{ secrets.JWT_SECRET_KEY }}
          REDIS_PASSWORD=${{ secrets.REDIS_PASSWORD }}
          MINIO_ACCESS_KEY=${{ secrets.MINIO_ACCESS_KEY }}
          MINIO_SECRET_KEY=${{ secrets.MINIO_SECRET_KEY }}
          EOF

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/pazpaz
            docker-compose pull
            docker-compose up -d
```

#### 4. GitHub CLI Method (Alternative)

```bash
# Set secrets using GitHub CLI
gh secret set ENCRYPTION_MASTER_KEY < encryption_key.txt
gh secret set POSTGRES_PASSWORD < db_password.txt
gh secret set SSH_PRIVATE_KEY < ~/.ssh/pazpaz-deploy

# List all secrets
gh secret list

# Delete a secret
gh secret delete SECRET_NAME
```

---

## HIPAA Compliance Considerations

### Critical Requirements

1. **Encryption Key Management (§164.312(e)(2)(ii))**
   - `ENCRYPTION_MASTER_KEY` must be 256-bit minimum
   - Rotate every 90 days
   - Store in 3+ locations
   - Document all rotations

2. **Access Control (§164.312(a)(2)(i))**
   - Use IAM roles, not hardcoded credentials
   - Implement 2FA for secret access
   - Log all secret retrievals
   - Regular access reviews

3. **Audit Controls (§164.312(b))**
   - Enable CloudTrail for AWS Secrets Manager
   - Monitor GitHub Actions secret access
   - Alert on unauthorized access attempts
   - Retain logs for 7 years

4. **Transmission Security (§164.312(e)(1))**
   - Use TLS 1.2+ for all secret transfers
   - Database SSL required (`ssl=require`)
   - Encrypted backups only
   - No plaintext email of secrets

### PHI Encryption Architecture

```
Client Data (PHI)
    ↓
ENCRYPTION_MASTER_KEY (AES-256-GCM)
    ↓
Encrypted Data in PostgreSQL
    ↓
Backup Encryption (Additional Layer)
```

**Key Rotation Impact:**
- Requires re-encrypting ALL PHI data
- Plan 4-week migration window
- Keep old key for decryption during transition
- Test recovery procedures quarterly

---

## Secret Rotation Procedures

### Rotation Schedule

| Secret Type | Routine Rotation | Emergency Rotation | Notes |
|------------|-----------------|-------------------|--------|
| **Encryption Keys** | 90 days | 24 hours | Requires data re-encryption |
| **Database Passwords** | 90 days | 1 hour | Update all services |
| **JWT Secrets** | 180 days | 4 hours | Invalidates active sessions |
| **API Keys** | 180 days | 1 hour | Update external services |
| **SSH Keys** | Annual | 24 hours | Update server authorized_keys |

### Encryption Key Rotation Process

**⚠️ CRITICAL: Follow exactly to prevent data loss**

```bash
# 1. Generate new encryption key (v2)
NEW_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Store new key in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v2 \
  --secret-string "$NEW_KEY"

# 3. Update application to support dual keys
# Application reads both v1 (decrypt) and v2 (encrypt)

# 4. Deploy with dual-key support
# New data encrypted with v2
# Old data still readable with v1

# 5. Run re-encryption background job
python scripts/reencrypt_phi_data.py \
  --old-key-secret pazpaz/encryption-key-v1 \
  --new-key-secret pazpaz/encryption-key-v2 \
  --batch-size 1000

# 6. Verify all data re-encrypted
python scripts/verify_encryption.py --key-version v2

# 7. Remove old key access (keep archived)
# Update application to only use v2

# 8. Archive old key (7-year retention)
aws secretsmanager put-secret-value \
  --secret-id pazpaz/archived-keys/v1 \
  --secret-string "$OLD_KEY"
```

### Database Password Rotation

```bash
# 1. Generate new password
NEW_DB_PASS=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-32)

# 2. Update PostgreSQL user password
psql -U postgres -c "ALTER USER pazpaz PASSWORD '$NEW_DB_PASS';"

# 3. Update GitHub Secret
gh secret set POSTGRES_PASSWORD <<< "$NEW_DB_PASS"

# 4. Update AWS Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id pazpaz/database-credentials \
  --secret-string "{\"password\":\"$NEW_DB_PASS\"}"

# 5. Trigger application restart
kubectl rollout restart deployment/pazpaz-api

# 6. Verify connectivity
docker exec pazpaz-api python -c "from pazpaz.database import engine; print('✅ DB connected')"
```

---

## Emergency Procedures

### Scenario: Encryption Key Compromised

**Impact:** All PHI data at risk of exposure

**Immediate Actions (0-2 hours):**

```bash
# 1. Generate emergency key
EMERGENCY_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Store in Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-emergency \
  --secret-string "$EMERGENCY_KEY"

# 3. Update application immediately
export ENCRYPTION_MASTER_KEY=$EMERGENCY_KEY
docker-compose restart api

# 4. Begin re-encryption (high priority)
python scripts/emergency_reencrypt.py --workers 10
```

**Follow-up Actions (2-24 hours):**
1. Audit access logs for compromise window
2. Identify potentially exposed data
3. Begin HIPAA breach assessment
4. Notify security officer
5. Document incident

### Scenario: GitHub Secrets Exposed

**Impact:** CI/CD pipeline compromised

**Immediate Actions:**

```bash
# 1. Rotate ALL GitHub secrets
./scripts/rotate-all-secrets.sh

# 2. Revoke GitHub Actions permissions
gh api -X DELETE /repos/owner/pazpaz/actions/permissions

# 3. Audit workflow runs
gh run list --limit 100 --json conclusion,createdAt,displayTitle

# 4. Re-enable with new secrets
gh secret set --file new-secrets.env
```

### Scenario: Database Credentials Leaked

**Impact:** Direct database access possible

**Immediate Actions:**

```bash
# 1. Change database password immediately
psql -U postgres -c "ALTER USER pazpaz PASSWORD '$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-32)';"

# 2. Kill all existing connections
psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'pazpaz';"

# 3. Review audit logs
psql -U postgres -c "SELECT * FROM audit_events WHERE created_at > NOW() - INTERVAL '24 hours';"

# 4. Update all services with new password
./scripts/update-db-password.sh
```

---

## Validation Checklist

### Pre-Deployment Validation

- [ ] **Encryption Key**
  - [ ] Generated with proper entropy (256 bits)
  - [ ] Stored in AWS Secrets Manager
  - [ ] Backup created and stored securely
  - [ ] Version documented (v1, v2, etc.)

- [ ] **Database Credentials**
  - [ ] Password meets complexity requirements (32+ chars)
  - [ ] SSL mode configured (`ssl=require` minimum)
  - [ ] Connection string tested
  - [ ] Backup access configured

- [ ] **GitHub Secrets**
  - [ ] All required secrets added
  - [ ] SSH key tested with server
  - [ ] Deployment workflow validated
  - [ ] No secrets in workflow logs

- [ ] **Security Measures**
  - [ ] .env files in .gitignore
  - [ ] No secrets in code comments
  - [ ] Audit logging enabled
  - [ ] Rotation calendar created

### Post-Deployment Validation

```bash
# Test encryption is working
curl -X POST https://api.pazpaz.com/api/v1/test/encryption \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"data":"test-phi-data"}'

# Verify database SSL
docker exec pazpaz-api python -c "
from sqlalchemy import create_engine
engine = create_engine('$DATABASE_URL')
with engine.connect() as conn:
    result = conn.execute('SHOW ssl')
    print(f'SSL: {result.fetchone()[0]}')
"

# Check secret accessibility
aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key-v2 \
  --query SecretString \
  --output text | wc -c
# Expected: 44 (Fernet key length)

# Audit GitHub Secret usage
gh api /repos/owner/pazpaz/actions/secrets
```

---

## Quick Reference

### Essential Commands

```bash
# Generate encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate strong password
openssl rand -base64 32 | tr -d '/+='

# Generate hex secret
openssl rand -hex 32

# Add GitHub secret
gh secret set SECRET_NAME < secret_file.txt

# Store in AWS
aws secretsmanager create-secret --name pazpaz/secret --secret-string "value"

# Rotate secret
aws secretsmanager rotate-secret --secret-id pazpaz/secret

# Test database connection
psql "$DATABASE_URL" -c "SELECT 1;"

# Verify encryption working
python -c "from cryptography.fernet import Fernet; f = Fernet(b'$KEY'); print('✅')"
```

### Emergency Contacts

- **Security Officer:** security@pazpaz.com
- **DevOps On-Call:** +1-xxx-xxx-xxxx
- **HIPAA Compliance:** compliance@pazpaz.com
- **AWS Support:** https://console.aws.amazon.com/support

### Related Documentation

- [AWS Secrets Manager Setup](./AWS_SECRETS_MANAGER.md)
- [Key Management Procedures](/docs/security/KEY_MANAGEMENT.md)
- [HIPAA Compliance](/docs/security/SECURITY_ARCHITECTURE.md)
- [CI/CD Implementation Plan](./CI_CD_IMPLEMENTATION_PLAN.md)
- [Incident Response](/docs/security/INCIDENT_RESPONSE.md)

---

**Document Owner:** DevOps Team
**Review Schedule:** Quarterly
**Next Review:** 2026-01-23
**Compliance:** HIPAA §164.312(a)(2)(iv), §164.312(e)