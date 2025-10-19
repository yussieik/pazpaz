# Credential Rotation Checklist

**HIPAA Compliance:** §164.308(a)(4)(i) - Information Access Management

This document outlines the credential rotation process for PazPaz infrastructure secrets.

## Rotation Schedule

| Credential Type | Development | Production | Notes |
|----------------|-------------|------------|-------|
| Database Passwords | 180 days | 90 days | Rotate immediately if compromised |
| S3/MinIO Access Keys | 180 days | 90 days | Rotate immediately if exposed |
| Encryption Master Keys | 365 days | 180 days | Requires data re-encryption |
| JWT Secrets | 180 days | 90 days | Invalidates all sessions |
| Redis Passwords | 180 days | 90 days | Low impact rotation |

## Critical Security Notice

**⚠️ NEVER commit .env files to git**

All `.env` files contain sensitive credentials and are gitignored. If you accidentally commit secrets:

1. **Stop immediately** - Do not push to remote
2. **Rotate all exposed credentials** (see procedures below)
3. **Clean git history** (see Git History Cleanup section)
4. **Update .gitignore** to prevent future accidents
5. **Document the incident** in security audit log

## Credentials to Rotate

### 1. PostgreSQL Database Password

**Environment Variable:** `POSTGRES_PASSWORD`

**Impact:** Database access disruption during rotation

**Procedure:**
```bash
# 1. Generate new password
export NEW_POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)

# 2. Connect to database and update password
docker exec -it pazpaz-db psql -U pazpaz -d pazpaz -c "ALTER USER pazpaz WITH PASSWORD '$NEW_POSTGRES_PASSWORD';"

# 3. Update .env file
echo "POSTGRES_PASSWORD=$NEW_POSTGRES_PASSWORD" >> .env

# 4. Restart API service to pick up new credentials
docker-compose restart api

# 5. Verify connection
docker-compose exec api python -c "from app.db.session import SessionLocal; SessionLocal().execute('SELECT 1')"
```

**Verification:**
- [ ] Database connection successful
- [ ] API health check passes
- [ ] No authentication errors in logs

---

### 2. S3/MinIO Access Credentials

**Environment Variables:** `S3_ACCESS_KEY`, `S3_SECRET_KEY`

**Impact:** File upload/download failures during rotation

**Procedure:**
```bash
# 1. Generate new credentials
export S3_ACCESS_KEY=$(openssl rand -base64 16 | tr -d '/+=' | cut -c1-16)
export S3_SECRET_KEY=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)

# 2. Update MinIO root credentials
# IMPORTANT: This requires MinIO restart
docker-compose down minio

# 3. Update .env file
echo "S3_ACCESS_KEY=$S3_ACCESS_KEY" >> .env
echo "S3_SECRET_KEY=$S3_SECRET_KEY" >> .env

# 4. Restart MinIO with new credentials
docker-compose up -d minio

# 5. Verify access
docker-compose exec api python -c "from app.storage.s3 import s3_client; s3_client.list_buckets()"
```

**Verification:**
- [ ] MinIO console login works with new credentials
- [ ] API can list S3 buckets
- [ ] File upload/download functional
- [ ] No authentication errors in logs

---

### 3. Encryption Master Key

**Environment Variable:** `ENCRYPTION_MASTER_KEY`

**Impact:** HIGH - Requires data re-encryption

**⚠️ WARNING:** This is a destructive operation requiring data migration

**Procedure:**
```bash
# 1. Generate new master key
export NEW_MASTER_KEY=$(python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# 2. Run key rotation migration script
docker-compose exec api python scripts/rotate_master_key.py \
  --old-key "$ENCRYPTION_MASTER_KEY" \
  --new-key "$NEW_MASTER_KEY" \
  --dry-run

# 3. Review migration plan, then execute
docker-compose exec api python scripts/rotate_master_key.py \
  --old-key "$ENCRYPTION_MASTER_KEY" \
  --new-key "$NEW_MASTER_KEY"

# 4. Update .env file
echo "ENCRYPTION_MASTER_KEY=$NEW_MASTER_KEY" >> .env

# 5. Restart API
docker-compose restart api
```

**Verification:**
- [ ] All PHI data decrypts successfully
- [ ] No data corruption detected
- [ ] Audit log shows successful rotation
- [ ] Backup created before rotation

**Rollback Plan:**
```bash
# If rotation fails, restore from backup
docker-compose exec db psql -U pazpaz -d pazpaz -f /backups/pre-rotation-backup.sql
# Revert ENCRYPTION_MASTER_KEY in .env to old value
docker-compose restart api
```

---

### 4. JWT Secret

**Environment Variable:** `JWT_SECRET`

**Impact:** All user sessions invalidated

**Procedure:**
```bash
# 1. Generate new JWT secret
export JWT_SECRET=$(openssl rand -base64 64 | tr -d '\n')

# 2. Update .env file
echo "JWT_SECRET=$JWT_SECRET" >> .env

# 3. Restart API (invalidates all sessions)
docker-compose restart api

# 4. Notify users of forced logout
# - Send email notification
# - Display banner in UI
```

**Verification:**
- [ ] New logins generate valid tokens
- [ ] Old tokens rejected with 401 Unauthorized
- [ ] Token refresh flow works
- [ ] Magic link authentication functional

---

### 5. Redis Password

**Environment Variable:** `REDIS_PASSWORD`

**Impact:** Session and cache invalidation

**Procedure:**
```bash
# 1. Generate new password
export REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)

# 2. Update .env file
echo "REDIS_PASSWORD=$REDIS_PASSWORD" >> .env

# 3. Restart Redis with new password
docker-compose restart redis

# 4. Restart API to reconnect with new password
docker-compose restart api
```

**Verification:**
- [ ] Redis connection successful
- [ ] API can read/write to Redis
- [ ] Background tasks processing
- [ ] No authentication errors

---

### 6. MinIO Encryption Key

**Environment Variable:** `MINIO_ENCRYPTION_KEY`

**Impact:** S3 server-side encryption key rotation

**Procedure:**
```bash
# 1. Generate new encryption key
export MINIO_ENCRYPTION_KEY=$(python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# 2. Update .env file
echo "MINIO_ENCRYPTION_KEY=$MINIO_ENCRYPTION_KEY" >> .env

# 3. Restart MinIO
docker-compose restart minio

# 4. Re-encrypt existing objects (if needed)
# MinIO supports multiple KMS keys; old objects remain accessible
```

**Verification:**
- [ ] MinIO starts successfully
- [ ] Existing files remain accessible
- [ ] New uploads encrypted with new key

---

## Git History Cleanup (If Secrets Committed)

**⚠️ CRITICAL:** If .env files were committed to git, follow these steps **immediately**:

### Option 1: BFG Repo-Cleaner (Recommended)

```bash
# 1. Install BFG Repo-Cleaner
brew install bfg  # macOS
# OR download from: https://reclaimtheweb.org/library/bfg.jar

# 2. Clone a fresh mirror of the repository
git clone --mirror https://github.com/your-org/pazpaz.git pazpaz-mirror.git
cd pazpaz-mirror.git

# 3. Remove .env files from history
bfg --delete-files '.env' --no-blob-protection .

# 4. Clean and garbage collect
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 5. Force push (WARNING: Destructive operation)
git push --force --all
git push --force --tags

# 6. Notify all team members to re-clone repository
echo "All team members must delete and re-clone the repository"
```

### Option 2: git-filter-repo

```bash
# 1. Install git-filter-repo
brew install git-filter-repo  # macOS
# OR: pip install git-filter-repo

# 2. Backup repository
cp -r /Users/yussieik/Desktop/projects/pazpaz /Users/yussieik/Desktop/projects/pazpaz-backup

# 3. Remove .env files from history
cd /Users/yussieik/Desktop/projects/pazpaz
git filter-repo --path .env --path backend/.env --path frontend/.env --invert-paths

# 4. Force push (WARNING: Destructive operation)
git push origin --force --all
git push origin --force --tags

# 5. Notify team to re-clone
```

### Post-Cleanup Verification

```bash
# Verify .env files removed from history
git log --all --full-history -- "*/.env" "**/.env" ".env"
# Output should be empty

# Check git objects
git rev-list --all --objects | grep -E '\.env$|\.env\.'
# Output should only show .env.example files

# Verify current .env files are ignored
git check-ignore -v .env backend/.env
# Should show .gitignore rules matching these files
```

---

## Post-Rotation Checklist

After rotating any credentials:

- [ ] Update .env files on all environments (dev, staging, production)
- [ ] Update CI/CD secrets (GitHub Actions, CircleCI, etc.)
- [ ] Update documentation if procedures changed
- [ ] Test full application functionality
- [ ] Monitor logs for authentication errors
- [ ] Document rotation in security audit log
- [ ] Verify backups contain no plaintext secrets
- [ ] Update password manager entries
- [ ] Notify security team of rotation completion

---

## Emergency Rotation (Compromised Credentials)

**If credentials are compromised (exposed in git, leaked, etc.):**

1. **IMMEDIATE:** Rotate affected credentials (follow procedures above)
2. **URGENT:** Review access logs for unauthorized access
3. **URGENT:** Lock down affected services temporarily if needed
4. **HIGH:** Clean git history if secrets were committed
5. **HIGH:** Notify security team and stakeholders
6. **MEDIUM:** Conduct incident post-mortem
7. **MEDIUM:** Update security training materials

**Incident Response Timeline:**
- 0-15 minutes: Identify scope of compromise
- 15-60 minutes: Rotate all exposed credentials
- 1-4 hours: Clean git history, verify no unauthorized access
- 4-24 hours: Complete incident report, update procedures

---

## Automation (Future Enhancement)

**Recommended:** Implement automated credential rotation:

1. Use HashiCorp Vault for dynamic secrets
2. AWS Secrets Manager for automatic rotation
3. Kubernetes External Secrets Operator
4. Automated rotation scripts with zero-downtime
5. Monitoring and alerting for rotation failures

---

## References

- [NIST SP 800-53 IA-5: Authenticator Management](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- [HIPAA §164.308(a)(4) - Information Access Management](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [BFG Repo-Cleaner Documentation](https://reclaimtheweb.org/library/bfg.jar)
- [git-filter-repo Documentation](https://github.com/newren/git-filter-repo)

---

**Last Updated:** 2025-10-19
**Next Review:** 2026-01-19 (90 days)
