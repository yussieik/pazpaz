# PazPaz Secret Rotation Schedule

## Overview

This document defines the secret rotation schedule and procedures for PazPaz production environment. Regular secret rotation is a critical security practice required for HIPAA compliance and defense against credential compromise.

**Last Updated:** 2025-10-24

## Rotation Schedule

### Summary Table

| Secret Type | Rotation Frequency | Risk Level | Last Rotated | Next Rotation | Automated |
|------------|-------------------|------------|--------------|---------------|-----------|
| **Database Credentials** | 90 days | High | - | - | ✅ |
| **Redis Password** | 90 days | Medium | - | - | ✅ |
| **S3/MinIO Credentials** | 180 days | Medium | - | - | ✅ |
| **JWT Secret Key** | 90 days | High | - | - | ✅ |
| **Application SECRET_KEY** | 90 days | High | - | - | ✅ |
| **SMTP Password** | 180 days | Low | - | - | ⚠️ Manual |
| **CSRF Secret Key** | 90 days | Medium | - | - | ✅ |
| **Encryption Master Key** | **NEVER** | Critical | N/A | N/A | ❌ |
| **MinIO Encryption Key** | **NEVER** | Critical | N/A | N/A | ❌ |

### Detailed Rotation Requirements

#### 1. Database Credentials (90 days)
- **Secret Names:** `POSTGRES_PASSWORD`, `DATABASE_URL`
- **Rotation Command:** `./scripts/rotate-secrets.sh --postgres`
- **Impact:** Brief connection pool reset, no downtime
- **Rollback:** Automatic if health checks fail
- **Verification Steps:**
  1. Check API health endpoint: `curl https://api.pazpaz.com/health`
  2. Verify database connectivity in logs
  3. Test a database query through the API

#### 2. Redis Password (90 days)
- **Secret Names:** `REDIS_PASSWORD`, `REDIS_URL`
- **Rotation Command:** `./scripts/rotate-secrets.sh --redis`
- **Impact:** Brief cache reset, sessions remain valid
- **Rollback:** Automatic if health checks fail
- **Verification Steps:**
  1. Check Redis connectivity: `docker exec pazpaz-redis redis-cli ping`
  2. Verify background jobs are processing
  3. Check session functionality

#### 3. S3/MinIO Credentials (180 days)
- **Secret Names:** `S3_ACCESS_KEY`, `S3_SECRET_KEY`
- **Rotation Command:** `./scripts/rotate-secrets.sh --s3`
- **Impact:** No downtime, seamless transition
- **Rollback:** Automatic if health checks fail
- **Verification Steps:**
  1. Test file upload functionality
  2. Verify existing files are accessible
  3. Check MinIO admin panel

#### 4. JWT Secret Key (90 days)
- **Secret Names:** `JWT_SECRET_KEY`
- **Rotation Command:** `./scripts/rotate-secrets.sh --jwt`
- **Impact:** **All users must re-authenticate**
- **Rollback:** Manual restore from backup
- **Pre-rotation Checklist:**
  - [ ] Notify users 24 hours in advance
  - [ ] Schedule during low-traffic period
  - [ ] Prepare support team for login issues
- **Verification Steps:**
  1. Test login with new credentials
  2. Verify JWT token generation
  3. Monitor authentication error rates

#### 5. Application Secret Key (90 days)
- **Secret Names:** `SECRET_KEY`
- **Rotation Command:** `./scripts/rotate-secrets.sh --secret-key`
- **Impact:** Session invalidation, CSRF tokens reset
- **Rollback:** Automatic if health checks fail
- **Verification Steps:**
  1. Test form submissions
  2. Verify CSRF protection is working
  3. Check session functionality

#### 6. SMTP Password (180 days)
- **Secret Names:** `SMTP_PASSWORD`
- **Rotation Command:** `./scripts/rotate-secrets.sh --smtp`
- **Impact:** Email sending temporarily unavailable
- **Rollback:** Manual restore from backup
- **Special Instructions:**
  1. Obtain new SMTP credentials from email provider
  2. Update in environment file
  3. Test email sending functionality

#### 7. CSRF Secret Key (90 days)
- **Secret Names:** `CSRF_SECRET_KEY`
- **Rotation Command:** Included in `--secret-key` rotation
- **Impact:** Active CSRF tokens invalidated
- **Rollback:** Automatic if health checks fail

## Secrets That Must NEVER Be Rotated

### ❌ ENCRYPTION_MASTER_KEY
- **Reason:** Used to encrypt PHI data at rest
- **Impact if rotated:** **PERMANENT DATA LOSS** - All encrypted PHI becomes unrecoverable
- **Migration required:** Would need to decrypt and re-encrypt all data with new key
- **Security:** Store in hardware security module (HSM) or secure key vault

### ❌ MINIO_ENCRYPTION_KEY
- **Reason:** Used to encrypt files stored in MinIO/S3
- **Impact if rotated:** All stored files become unreadable
- **Migration required:** Would need to re-encrypt all stored files
- **Security:** Backup securely and never expose

## Rotation Procedures

### Standard Rotation Process

1. **Pre-rotation (Day Before)**
   ```bash
   # Check secret age
   ./scripts/check-secret-age.sh

   # Verify backup system is working
   ls -la /opt/pazpaz/backups/secrets/

   # Notify team of upcoming rotation
   ```

2. **Rotation Day**
   ```bash
   # Full backup of current environment
   cp .env.production .env.production.backup-$(date +%Y%m%d)

   # Perform rotation (example for all secrets)
   ./scripts/rotate-secrets.sh --all

   # Verify services are healthy
   docker-compose -f docker-compose.prod.yml ps
   ```

3. **Post-rotation**
   ```bash
   # Update GitHub Secrets (if using CI/CD)
   gh secret set POSTGRES_PASSWORD < new_password.txt

   # Update monitoring alerts
   # Update documentation
   ```

### Emergency Rotation (Suspected Compromise)

If you suspect a secret has been compromised:

1. **Immediate Actions**
   ```bash
   # Rotate the compromised secret immediately
   ./scripts/rotate-secrets.sh --postgres --force

   # Check audit logs for unauthorized access
   docker logs pazpaz-api | grep -i auth
   ```

2. **Investigation**
   - Review access logs for unusual patterns
   - Check Git history for accidental commits
   - Audit user access and permissions
   - Review recent deployments and changes

3. **Remediation**
   - Rotate all related secrets
   - Review and update access controls
   - Implement additional monitoring
   - Document incident for compliance

### Rollback Procedures

If rotation fails or causes issues:

1. **Automatic Rollback** (built into rotation script)
   - Health checks fail → automatic restore
   - Service won't start → automatic restore

2. **Manual Rollback**
   ```bash
   # Stop affected services
   docker-compose -f docker-compose.prod.yml stop api

   # Restore from backup
   cp /opt/pazpaz/backups/secrets/env.production.20241024.backup .env.production

   # Restart services
   docker-compose -f docker-compose.prod.yml up -d api

   # Verify functionality
   curl https://api.pazpaz.com/health
   ```

## Compliance Requirements (HIPAA)

### NIST 800-66 Guidelines
- Regular password changes (90-180 days)
- Strong password requirements (32+ characters, high entropy)
- Audit trail for all rotations
- Secure storage of credentials
- Access logging and monitoring

### Audit Trail Requirements
All secret rotations must be logged with:
- Timestamp of rotation
- User who performed rotation
- Secrets that were rotated
- Success/failure status
- Any errors or warnings

Logs are stored in: `/opt/pazpaz/logs/secret-rotation-*.log`

### Documentation Requirements
- Maintain this schedule document
- Update `.rotation-history` file after each rotation
- Document any deviations from schedule
- Keep incident reports for emergency rotations

## Automation Setup

### GitHub Actions Reminder (Monthly Check)

Create `.github/workflows/secret-rotation-reminder.yml`:

```yaml
name: Secret Rotation Reminder

on:
  schedule:
    # Run on the 1st of every month at 9 AM UTC
    - cron: '0 9 1 * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  check-rotation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Check Secret Age
        run: |
          ./scripts/check-secret-age.sh

      - name: Create Issue if Rotation Needed
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '🔐 Secret Rotation Required',
              body: 'Secrets are due for rotation. Check the workflow logs for details.',
              labels: ['security', 'operations']
            })
```

### Cron Job Setup (On Production Server)

```bash
# Add to crontab (crontab -e)
# Check secret age weekly on Mondays at 9 AM
0 9 * * 1 /opt/pazpaz/scripts/check-secret-age.sh >> /opt/pazpaz/logs/secret-age-check.log 2>&1

# Send email alert if secrets need rotation
0 9 * * 1 /opt/pazpaz/scripts/check-secret-age.sh | grep -E "WARNING|OVERDUE" && echo "Secrets need rotation" | mail -s "PazPaz Secret Rotation Alert" ops@pazpaz.com
```

## Testing Rotation

### Test in Staging First
Always test secret rotation in staging environment:

```bash
# Staging rotation
ENV_FILE=.env.staging ./scripts/rotate-secrets.sh --all --dry-run

# If dry run successful, perform actual rotation
ENV_FILE=.env.staging ./scripts/rotate-secrets.sh --all
```

### Rotation Validation Checklist

- [ ] All services restart successfully
- [ ] Health checks pass for all services
- [ ] Database connectivity verified
- [ ] Redis connectivity verified
- [ ] S3/MinIO file operations work
- [ ] Authentication works (if JWT rotated)
- [ ] Email sending works (if SMTP rotated)
- [ ] No errors in application logs
- [ ] Monitoring alerts are normal
- [ ] Performance metrics unchanged

## Secret Storage Best Practices

### Production Server
- Store in `/opt/pazpaz/.env.production`
- File permissions: `600` (read/write by owner only)
- Owner: `deploy` user or `root`
- Encrypted filesystem recommended
- Regular encrypted backups

### GitHub Secrets (for CI/CD)
- Use repository secrets, not organization secrets
- Limit access to deployment workflows only
- Regular audit of secret access
- Use OIDC for cloud provider auth when possible

### Development
- Never use production secrets in development
- Use `.env.example` as template
- Generate development-specific secrets
- Add `.env*` to `.gitignore`

## Monitoring and Alerts

### Key Metrics to Monitor
- Authentication failure rate
- Database connection errors
- Redis connection errors
- S3/MinIO access errors
- API health check status

### Alert Thresholds
- Auth failures > 5% → Immediate investigation
- Database connection errors > 0 → Check rotation
- Any service unhealthy > 5 minutes → Rollback consideration

## Contact Information

### Rotation Responsibilities
- **Primary:** DevOps Team
- **Backup:** Senior Backend Developer
- **Approval Required:** CTO or Security Officer

### Emergency Contacts
- **On-call Engineer:** (defined in PagerDuty)
- **Security Team:** security@pazpaz.com
- **CTO:** cto@pazpaz.com

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2024-10-24 | 1.0.0 | Initial rotation schedule | DevOps |

---

**Remember:** Secret rotation is not optional - it's a critical security requirement. When in doubt, rotate. It's better to deal with minor disruption than a security breach.