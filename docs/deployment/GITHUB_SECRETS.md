# GitHub Secrets Configuration Guide

> **Security Notice**: This document contains procedures for managing sensitive credentials. Never commit actual secret values to the repository. All example values shown here are placeholders.

## Table of Contents

1. [Secrets Inventory](#secrets-inventory)
2. [Secret Generation Guide](#secret-generation-guide)
3. [Configuration Instructions](#configuration-instructions)
4. [Security Best Practices](#security-best-practices)
5. [Secret Rotation Procedures](#secret-rotation-procedures)
6. [Validation and Testing](#validation-and-testing)
7. [Emergency Procedures](#emergency-procedures)
8. [Compliance Requirements](#compliance-requirements)

## Secrets Inventory

### CI/CD Secrets (Testing & Development)

| Secret Name | Purpose | Required? | Has Fallback? | Where Used | Rotation Schedule |
|-------------|---------|-----------|---------------|------------|-------------------|
| `CI_ENCRYPTION_KEY` | Test encryption for PHI in CI | No | Yes (hardcoded) | backend-ci.yml:99, :473 | Not required (test only) |
| `CI_SECRET_KEY` | Test app secret for CI | No | Yes (hardcoded) | backend-ci.yml:100, :474 | Not required (test only) |
| `CI_JWT_SECRET_KEY` | Test JWT secret for CI | No | Yes (hardcoded) | backend-ci.yml:101 | Not required (test only) |
| `CODECOV_TOKEN` | Code coverage reporting | No | No | backend-ci.yml:152, frontend-ci.yml | As needed |

### Production Secrets (Required for Deployment)

| Secret Name | Purpose | Required? | Has Fallback? | Where Used | Rotation Schedule |
|-------------|---------|-----------|---------------|------------|-------------------|
| **🔴 CRITICAL - PHI Encryption** | | | | | |
| `PROD_ENCRYPTION_MASTER_KEY` | PHI encryption (HIPAA required) | **YES** | No | Production deployment | Every 90 days |
| **🟠 Database** | | | | | |
| `PROD_DATABASE_URL` | PostgreSQL connection string | **YES** | No | Production deployment | Every 90 days (password) |
| `PROD_POSTGRES_PASSWORD` | PostgreSQL root password | **YES** | No | Production deployment | Every 90 days |
| **🟡 Application Security** | | | | | |
| `PROD_SECRET_KEY` | Django-style secret key | **YES** | No | Production deployment | Every 90 days |
| `PROD_JWT_SECRET_KEY` | JWT token signing | **YES** | No | Production deployment | Every 90 days |
| `PROD_CSRF_SECRET_KEY` | CSRF protection | **YES** | No | Production deployment | Every 90 days |
| `PROD_REDIS_PASSWORD` | Redis authentication | **YES** | No | Production deployment | Every 90 days |
| **🟢 Deployment** | | | | | |
| `SSH_PRIVATE_KEY` | Server deployment access | **YES** | No | Deployment workflows | Annually or on compromise |
| `SSH_HOST` | Target server hostname/IP | **YES** | No | Deployment workflows | As needed |
| `SSH_USER` | SSH username | **YES** | No | Deployment workflows | As needed |
| `SSH_PORT` | SSH port | No | Yes (22) | Deployment workflows | As needed |

### Optional Service Secrets

| Secret Name | Purpose | Required? | Has Fallback? | Where Used | Rotation Schedule |
|-------------|---------|-----------|---------------|------------|-------------------|
| **Storage** | | | | | |
| `PROD_MINIO_ACCESS_KEY` | MinIO/S3 access | Conditional¹ | No | Production (if using S3) | Every 90 days |
| `PROD_MINIO_SECRET_KEY` | MinIO/S3 secret | Conditional¹ | No | Production (if using S3) | Every 90 days |
| **Email Service** | | | | | |
| `PROD_RESEND_API_KEY` | Resend email service | Conditional² | No | Production (if using email) | Per vendor policy |
| **Monitoring** | | | | | |
| `PROD_SENTRY_DSN` | Error tracking | No | Empty string | Production deployment | Per vendor policy |
| `UPTIME_ROBOT_API_KEY` | Uptime monitoring | No | No | Monitoring workflows | Per vendor policy |
| **Container Registry** | | | | | |
| `DOCKER_USERNAME` | Docker Hub access | No | No | Container builds | As needed |
| `DOCKER_PASSWORD` | Docker Hub secret | No | No | Container builds | Every 90 days |

¹ Required if using S3/MinIO for file storage
² Required if email notifications are enabled

## Secret Generation Guide

### 🔴 CRITICAL: PHI Encryption Key (Fernet)

The encryption key is used to encrypt all PHI/PII data at rest. This is a HIPAA requirement.

```bash
# Generate a 32-byte Fernet-compatible encryption key
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# Example output (DO NOT USE THIS):
# dGhpc19pc19hX3NhbXBsZV9rZXlfZG9fbm90X3VzZQ==

# Verify the key is valid (should output "Valid")
python3 -c "
import base64, sys
key = 'your-generated-key-here'
try:
    decoded = base64.urlsafe_b64decode(key)
    print('Valid' if len(decoded) == 32 else 'Invalid length')
except:
    print('Invalid format')
"
```

### 🟡 Application Secrets

These secrets are used for session management, CSRF protection, and JWT signing.

```bash
# Generate SECRET_KEY (64 characters minimum)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Example output (DO NOT USE THIS):
# 7Kj9_mN2pQrStUvWxYzAbCdEfGhIjKlMnOpQrStUvWxYzA1B2C3D4E5F6G7H8

# Generate JWT_SECRET_KEY (64 characters minimum)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Generate CSRF_SECRET_KEY (32 characters minimum)
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 🟠 Database Secrets

```bash
# Generate strong PostgreSQL password (32+ characters)
python3 -c "
import string, secrets
alphabet = string.ascii_letters + string.digits + '_'
password = ''.join(secrets.choice(alphabet) for i in range(40))
print(password)
"

# Example DATABASE_URL format:
# postgresql+asyncpg://pazpaz_user:YOUR_PASSWORD@localhost:5432/pazpaz_prod?sslmode=require

# Generate Redis password (32+ characters, alphanumeric only)
python3 -c "
import string, secrets
alphabet = string.ascii_letters + string.digits
password = ''.join(secrets.choice(alphabet) for i in range(40))
print(password)
"
```

### 🟢 SSH Deployment Keys

```bash
# Generate new ED25519 SSH key pair (recommended)
ssh-keygen -t ed25519 -C "pazpaz-github-actions" -f pazpaz_deploy_key -N ""

# Or RSA if ED25519 not supported (4096 bits minimum)
ssh-keygen -t rsa -b 4096 -C "pazpaz-github-actions" -f pazpaz_deploy_key -N ""

# The private key (pazpaz_deploy_key) goes in SSH_PRIVATE_KEY secret
# The public key (pazpaz_deploy_key.pub) goes on the server's ~/.ssh/authorized_keys
```

### Optional Service Keys

```bash
# MinIO/S3 credentials (20+ characters each)
python3 -c "
import string, secrets
alphabet = string.ascii_uppercase + string.digits
access_key = ''.join(secrets.choice(alphabet) for i in range(20))
print(f'Access Key: {access_key}')

alphabet = string.ascii_letters + string.digits + '+/'
secret_key = ''.join(secrets.choice(alphabet) for i in range(40))
print(f'Secret Key: {secret_key}')
"
```

## Configuration Instructions

### Step 1: Navigate to Repository Settings

1. Go to your GitHub repository: `https://github.com/YOUR_ORG/pazpaz`
2. Click on **Settings** tab
3. In the left sidebar, expand **Secrets and variables**
4. Click on **Actions**

### Step 2: Add Repository Secrets

For each secret:

1. Click **New repository secret**
2. Enter the **Name** exactly as shown in the inventory (case-sensitive)
3. Enter the **Value** (generated using the commands above)
4. Click **Add secret**

### Step 3: Verify Configuration

Run the validation workflow to verify all secrets are properly configured:

```bash
# Trigger the validation workflow manually
gh workflow run validate-secrets.yml

# Or via GitHub UI:
# Actions → Validate GitHub Secrets Configuration → Run workflow
```

### Step 4: Verify in CI Logs

1. Trigger a CI workflow run
2. Check that secrets are being used (they appear as `***` in logs)
3. Verify no fallback warnings appear for production-critical secrets

## Security Best Practices

### ✅ DO's

1. **Generate cryptographically secure random values** using the provided commands
2. **Use different secrets for each environment** (CI, staging, production)
3. **Rotate secrets on schedule** (see rotation procedures)
4. **Use GitHub's secret scanning** to prevent accidental commits
5. **Limit secret access** to required workflows only
6. **Document rotation events** in audit logs
7. **Test secrets after rotation** using validation scripts
8. **Use environment-specific prefixes** (CI_, PROD_, STAGING_)
9. **Enable audit logging** for secret access in GitHub
10. **Use OIDC for cloud providers** when possible (instead of long-lived keys)

### ❌ DON'Ts

1. **Never commit secrets to the repository** (even in "deleted" commits)
2. **Never log secret values** (even partially)
3. **Never use the same secret across environments**
4. **Never share secrets via email, Slack, or chat**
5. **Never store secrets in plain text files**
6. **Never use weak or predictable values**
7. **Never skip rotation schedules**
8. **Never expose secrets in error messages**
9. **Never use production secrets in CI/testing**
10. **Never store secrets in Docker images**

## Secret Rotation Procedures

### Routine Rotation (Every 90 Days)

1. **Generate new secret values** using the generation commands
2. **Update GitHub Secrets** with new values:
   ```bash
   # Using GitHub CLI
   gh secret set PROD_SECRET_KEY < new_secret_value.txt
   ```
3. **Deploy with new secrets** to staging environment first
4. **Verify services start correctly** with new secrets
5. **Deploy to production** during maintenance window
6. **Verify production services** are functioning
7. **Archive old values** (encrypted) for rollback if needed
8. **Update rotation log**:
   ```markdown
   ## Rotation Log
   - Date: 2024-01-15
   - Secrets Rotated: PROD_SECRET_KEY, PROD_JWT_SECRET_KEY
   - Rotated By: @username
   - Verification: All services operational
   - Old Values Archived: vault/archive/2024-01-15/
   ```

### Emergency Rotation (On Compromise)

If a secret is potentially compromised:

1. **IMMEDIATE ACTIONS** (Within 15 minutes):
   ```bash
   # 1. Generate new secret immediately
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"

   # 2. Update GitHub secret
   gh secret set COMPROMISED_SECRET

   # 3. Deploy to production immediately
   ./scripts/emergency-deploy.sh

   # 4. Revoke old secret (if applicable)
   # For API keys, revoke via provider dashboard
   # For database passwords, change immediately
   ```

2. **FOLLOW-UP ACTIONS** (Within 1 hour):
   - Audit all access logs for unauthorized usage
   - Check for data exfiltration
   - Notify security team and stakeholders
   - Document incident in security log

3. **POST-INCIDENT** (Within 24 hours):
   - Complete incident report
   - Review how compromise occurred
   - Update procedures to prevent recurrence
   - Rotate related secrets as precaution

### Rotation Schedule

| Secret Type | Routine Rotation | Emergency Triggers |
|-------------|------------------|-------------------|
| Encryption Keys | 90 days | Suspected compromise, key exposure |
| Database Passwords | 90 days | Unauthorized access, employee departure |
| API Secrets | 90 days | Failed validation, suspicious activity |
| JWT Secrets | 90 days | Token compromise, algorithm change |
| SSH Keys | 365 days | Server compromise, key exposure |
| Service API Keys | Per vendor | Rate limit abuse, billing anomaly |

## Validation and Testing

### Using the Validation Script

```bash
# Run the validation script locally
cd scripts/
python3 validate-secrets.py

# Or with uv
uv run python scripts/validate-secrets.py

# Test with environment variables
export ENCRYPTION_MASTER_KEY="your-key-here"
export SECRET_KEY="your-secret-here"
export JWT_SECRET_KEY="your-jwt-secret-here"
uv run python scripts/validate-secrets.py

# Run in verbose mode
uv run python scripts/validate-secrets.py --verbose
```

### Validation Checklist

Before marking secrets as configured:

- [ ] All required secrets have been generated
- [ ] Secrets meet minimum length requirements
- [ ] Secrets use cryptographically secure randomness
- [ ] No secrets are committed to the repository
- [ ] Validation script passes all checks
- [ ] CI workflows can access secrets (check logs)
- [ ] Production deployment tested with new secrets
- [ ] Rotation schedule documented
- [ ] Emergency procedures tested
- [ ] Team members trained on procedures

## Emergency Procedures

### Secret Exposure Response

If a secret is accidentally exposed (e.g., in logs, commits, screenshots):

1. **Minute 0-5: Immediate Containment**
   - Rotate the exposed secret immediately
   - Remove/redact the exposure if possible
   - Deploy new secret to production

2. **Minute 5-30: Assessment**
   - Determine exposure duration and scope
   - Check access logs for unauthorized use
   - Identify all systems using the secret

3. **Minute 30-60: Remediation**
   - Complete rotation across all environments
   - Verify all services are operational
   - Begin incident documentation

4. **Hour 1-24: Follow-up**
   - Complete incident report
   - Notify affected parties if required
   - Review and update procedures

### Lost Access Recovery

If GitHub Secrets are inaccessible:

1. **Use backup credentials** (stored in secure vault)
2. **Access via GitHub API** with admin token
3. **Contact GitHub Support** if organization-wide issue
4. **Implement from backup** configuration if needed

## Compliance Requirements

### HIPAA Technical Safeguards

Per HIPAA Security Rule (45 CFR §164.312):

1. **Access Control (§164.312(a))**
   - Unique user identification via SECRET_KEY
   - Automatic logoff via JWT expiration
   - Encryption via ENCRYPTION_MASTER_KEY

2. **Audit Controls (§164.312(b))**
   - Secret access logged in GitHub audit log
   - Rotation events documented
   - Access reviews quarterly

3. **Integrity (§164.312(c))**
   - Secrets transmitted over TLS only
   - Verification via validation script
   - Tamper detection via GitHub's audit log

4. **Transmission Security (§164.312(e))**
   - All secrets encrypted in transit (TLS)
   - No secrets in URLs or logs
   - Secure storage in GitHub Secrets

### Audit Trail Requirements

Maintain records of:
- Secret creation dates
- Rotation history
- Access logs (via GitHub audit)
- Validation test results
- Incident reports
- Training completion

### Quarterly Security Review

Every 3 months:
- [ ] Review all secret access logs
- [ ] Verify rotation schedule compliance
- [ ] Test emergency procedures
- [ ] Update documentation
- [ ] Train new team members
- [ ] Review and update this guide

---

**Last Updated**: 2024-10-23
**Next Review**: 2024-01-23
**Document Owner**: DevOps Team
**Compliance Officer**: [Designated HIPAA Officer]

For questions or concerns about secret management, contact the DevOps team or security officer immediately.