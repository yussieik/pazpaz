# PazPaz Key Management Procedures

**Last Updated:** 2025-10-19
**Version:** 1.0
**Status:** Production Ready
**Classification:** Internal (Confidential - Authorized Personnel Only)

---

## Table of Contents

1. [Overview](#overview)
2. [Key Inventory](#key-inventory)
3. [Key Generation Procedure](#key-generation-procedure)
4. [Key Rotation Schedule](#key-rotation-schedule)
5. [Key Backup Procedure](#key-backup-procedure)
6. [Key Recovery Procedure](#key-recovery-procedure)
7. [Key Versioning Strategy](#key-versioning-strategy)
8. [Key Strength Requirements](#key-strength-requirements)
9. [Access Control for Keys](#access-control-for-keys)
10. [Compliance & Audit](#compliance--audit)

---

## Overview

This document defines operational procedures for managing cryptographic keys in the PazPaz application. Proper key management is critical for HIPAA compliance and PHI protection.

### Key Management Objectives

1. **Confidentiality**: Prevent unauthorized access to encryption keys
2. **Availability**: Ensure keys are accessible when needed for legitimate operations
3. **Integrity**: Prevent unauthorized modification or corruption of keys
4. **Accountability**: Track all key access and rotation activities

### Compliance Requirements

- **HIPAA §164.312(a)(2)(iv)**: Encryption and decryption mechanisms
- **HIPAA §164.312(e)(2)(ii)**: Encryption key management procedures
- **NIST SP 800-57**: Key management best practices
- **FIPS 140-2**: Cryptographic module standards

### Roles & Responsibilities

| Role | Responsibilities |
|------|------------------|
| **Security Officer** | Approve key rotations, incident response, policy enforcement |
| **Database Administrator** | Execute key rotations, monitor re-encryption, backup validation |
| **DevOps/SRE** | Deploy application updates, manage secrets infrastructure |
| **Backend Developer** | Implement key versioning, test dual-key mode |
| **HIPAA Compliance Officer** | Document key management for audit trail, breach assessment |

---

## Key Inventory

### Active Keys (Production)

| Key Name | Purpose | Algorithm | Key Size | Rotation Frequency | Storage Location |
|----------|---------|-----------|----------|-------------------|------------------|
| **Encryption Master Key** | PHI encryption at rest | AES-256-GCM | 256 bits (32 bytes) | 90 days | AWS Secrets Manager (multi-region) |
| **JWT Signing Secret** | JWT signature (HS256) | HMAC-SHA256 | 256 bits (32 bytes) | 180 days | AWS Secrets Manager |
| **Database Credentials** | PostgreSQL authentication | N/A | N/A | 90 days | AWS Secrets Manager |
| **S3/MinIO Access Key** | File storage access | N/A | N/A | 90 days | IAM Role (no long-lived keys) |
| **Redis Password** | Redis authentication | N/A | N/A | 90 days | Kubernetes Secret |
| **SMTP Credentials** | Email service (SendGrid/MailHog) | N/A | N/A | Manual | AWS Secrets Manager |

### Key Versioning

**Current Production Keys**:
- Encryption Master Key: `v3` (rotated 2025-10-15)
- JWT Secret: `v1` (initial deployment)
- Database Credentials: `v2` (rotated 2025-09-01)

**Archived Keys** (retained for 7 years per HIPAA):
- Encryption Master Key v1 (archived 2025-07-01)
- Encryption Master Key v2 (archived 2025-10-15)

---

## Key Generation Procedure

### Encryption Master Key Generation

**Algorithm**: AES-256-GCM
**Key Size**: 256 bits (32 bytes)
**Entropy Source**: `secrets.token_bytes()` (Python cryptographically secure RNG)

#### Step-by-Step Generation

```bash
# 1. Generate new 256-bit key using cryptographically secure RNG
NEW_KEY=$(python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# 2. Verify key length (must be exactly 32 bytes)
python3 -c "import base64; key = base64.b64decode('$NEW_KEY'); assert len(key) == 32, 'Key length must be 32 bytes'; print(f'✅ Key length verified: {len(key)} bytes')"

# 3. Verify key entropy (should have high entropy)
python3 -c "import base64, math; key = base64.b64decode('$NEW_KEY'); entropy = len(set(key)) / 256.0; assert entropy > 0.8, 'Key entropy too low'; print(f'✅ Key entropy: {entropy:.2%}')"

# 4. Display key (NEVER log this in production!)
echo "Generated Key (v4): $NEW_KEY"

# 5. Store immediately in secrets manager (don't leave in shell history)
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v4 \
  --secret-string "$NEW_KEY" \
  --description "Encryption master key v4 (generated $(date +%Y-%m-%d))" \
  --region us-east-1 \
  --kms-key-id alias/pazpaz-secrets

# 6. Clear shell history to remove plaintext key
history -d $(history 1 | awk '{print $1}')
unset NEW_KEY
```

### JWT Signing Secret Generation

```bash
# Generate 256-bit HMAC secret
JWT_SECRET=$(python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# Store in secrets manager
aws secretsmanager create-secret \
  --name pazpaz/jwt-secret-v2 \
  --secret-string "$JWT_SECRET" \
  --description "JWT signing secret v2 (generated $(date +%Y-%m-%d))" \
  --region us-east-1

unset JWT_SECRET
```

### Database Password Generation

```bash
# Generate strong database password (32 characters, alphanumeric + symbols)
DB_PASSWORD=$(python3 -c "import secrets, string; alphabet = string.ascii_letters + string.digits + '!@#$%^&*()'; print(''.join(secrets.choice(alphabet) for _ in range(32)))")

# Store in secrets manager
aws secretsmanager create-secret \
  --name pazpaz/database-credentials-v3 \
  --secret-string "{\"username\":\"pazpaz\",\"password\":\"$DB_PASSWORD\",\"host\":\"db.pazpaz.internal\",\"port\":5432,\"database\":\"pazpaz\"}" \
  --description "Database credentials v3 (generated $(date +%Y-%m-%d))" \
  --region us-east-1

unset DB_PASSWORD
```

---

## Key Rotation Schedule

### Rotation Frequency

| Key Type | Routine Rotation | Emergency Rotation | Rationale |
|----------|-----------------|-------------------|-----------|
| **Encryption Master Key** | Every 90 days | Within 24 hours | HIPAA best practice, limits exposure window |
| **JWT Signing Secret** | Every 180 days | Within 4 hours | Active tokens remain valid until expiration (7 days) |
| **Database Credentials** | Every 90 days | Within 1 hour | Reduces risk from credential compromise |
| **S3/MinIO Access Key** | Use IAM roles (no rotation) | N/A | Temporary credentials auto-rotate |
| **Redis Password** | Every 90 days | Within 1 hour | Short-lived connections, low impact rotation |

### Rotation Calendar (2025-2026)

**Encryption Master Key (90-day rotation)**:
- ✅ Q4 2024: v1 → v2 (2024-10-15)
- ✅ Q1 2025: v2 → v3 (2025-01-15)
- 🔄 Q2 2025: v3 → v4 (2025-04-15) *Upcoming*
- 📅 Q3 2025: v4 → v5 (2025-07-15)
- 📅 Q4 2025: v5 → v6 (2025-10-15)
- 📅 Q1 2026: v6 → v7 (2026-01-15)

**Rotation Timeline** (Routine 90-day rotation):

```
Week 0: Pre-rotation preparation
  ├─ Generate new key (v4)
  ├─ Backup current key (v3)
  ├─ Test dual-key mode in staging
  └─ Communication to team

Week 1: Deploy dual-key application
  ├─ Store v4 in secrets manager
  ├─ Update Kubernetes secrets (v3 + v4)
  ├─ Deploy application with dual-key support
  └─ Verify new writes use v4, old reads use v3

Week 2-3: Background re-encryption
  ├─ Run re-encryption script (gradual, 100 records/second)
  ├─ Monitor progress daily (v3 → v4 migration)
  ├─ Validate data integrity (spot checks)
  └─ Track error rates

Week 4: Retire old key
  ├─ Verify 100% migration to v4
  ├─ Remove v3 from active secrets
  ├─ Deploy single-key application (v4 only)
  ├─ Archive v3 key (encrypted backup)
  └─ Document rotation completion
```

### Emergency Rotation Triggers

**Immediate rotation required if**:
1. ✅ Encryption key exposed in logs, error messages, or monitoring tools
2. ✅ Unauthorized access to AWS Secrets Manager detected
3. ✅ Security incident affecting application servers or database
4. ✅ Employee with key access leaves organization (termination, resignation)
5. ✅ Third-party vulnerability affecting cryptographic library (OpenSSL, cryptography)
6. ✅ Regulatory requirement or compliance audit finding
7. ✅ Suspected key compromise (forensic analysis)

**Emergency Rotation Timeline**:

```
Hour 0: Incident detection
  └─ Security incident declared

Hour 0-2: Assessment & preparation
  ├─ Assess scope of compromise
  ├─ Generate new key (v_emergency)
  └─ Notify incident response team

Hour 2-4: Deploy emergency key
  ├─ Store new key in secrets manager
  ├─ Update Kubernetes secrets (dual-key)
  ├─ Force application rollout (restart all pods)
  └─ Verify new writes use emergency key

Hour 4-24: Accelerated re-encryption
  ├─ Run re-encryption with increased parallelism (4x workers)
  ├─ Monitor progress hourly
  └─ Estimate completion time

Hour 24-48: Retire compromised key
  ├─ Verify 100% migration complete
  ├─ Remove compromised key from all systems
  ├─ Revoke all access to compromised key
  ├─ Archive compromised key for forensic analysis
  └─ Breach notification assessment (HIPAA 60-day rule)

Hour 48-72: Post-incident review
  ├─ Audit data access logs during compromise window
  ├─ Document incident timeline
  ├─ Determine breach notification requirement
  └─ Implement preventive measures
```

---

## Key Backup Procedure

### Backup Strategy

**Objective**: Ensure encryption keys can be recovered in case of:
- AWS Secrets Manager outage or account lockout
- Accidental key deletion
- Regional disaster (multi-region failover)
- Catastrophic infrastructure failure

**Backup Frequency**:
- **Automated**: Daily backups (3:00 AM UTC)
- **Manual**: After every key rotation
- **Verification**: Quarterly recovery drill

### Automated Daily Backup

**Backup Script**: `/opt/pazpaz/scripts/backup-encryption-keys.sh`

```bash
#!/bin/bash
# Daily encryption key backup script
# Runs via cron: 0 3 * * * /opt/pazpaz/scripts/backup-encryption-keys.sh

set -euo pipefail

BACKUP_DIR="/secure/backups/keys"
S3_BUCKET="s3://pazpaz-key-backups-us-east-1"
GPG_RECIPIENT="security@pazpaz.com"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Fetch current encryption key from AWS Secrets Manager
ENCRYPTION_KEY=$(aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key \
  --region us-east-1 \
  --query SecretString \
  --output text)

# Fetch JWT secret
JWT_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id pazpaz/jwt-secret \
  --region us-east-1 \
  --query SecretString \
  --output text)

# Fetch database credentials
DB_CREDS=$(aws secretsmanager get-secret-value \
  --secret-id pazpaz/database-credentials \
  --region us-east-1 \
  --query SecretString \
  --output text)

# Create JSON backup file
cat > "$BACKUP_DIR/keys-backup-$TIMESTAMP.json" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "encryption_key": "$ENCRYPTION_KEY",
  "jwt_secret": "$JWT_SECRET",
  "database_credentials": $DB_CREDS
}
EOF

# Encrypt backup with GPG (offline master key)
gpg --encrypt --armor --recipient "$GPG_RECIPIENT" \
  --output "$BACKUP_DIR/keys-backup-$TIMESTAMP.json.gpg" \
  "$BACKUP_DIR/keys-backup-$TIMESTAMP.json"

# Remove plaintext backup (keep only encrypted)
shred -u "$BACKUP_DIR/keys-backup-$TIMESTAMP.json"

# Upload encrypted backup to S3 (versioned bucket)
aws s3 cp "$BACKUP_DIR/keys-backup-$TIMESTAMP.json.gpg" \
  "$S3_BUCKET/daily-backups/" \
  --storage-class STANDARD_IA \
  --server-side-encryption AES256

# Upload to secondary region (disaster recovery)
aws s3 cp "$BACKUP_DIR/keys-backup-$TIMESTAMP.json.gpg" \
  "s3://pazpaz-key-backups-us-west-2/daily-backups/" \
  --region us-west-2 \
  --storage-class STANDARD_IA \
  --server-side-encryption AES256

# Cleanup old local backups (keep last 7 days)
find "$BACKUP_DIR" -name "keys-backup-*.json.gpg" -mtime +7 -delete

# Log backup completion
echo "$(date): Key backup completed successfully - $TIMESTAMP" >> /var/log/pazpaz/key-backups.log
```

**Cron Configuration**:

```bash
# /etc/cron.d/pazpaz-key-backup
0 3 * * * pazpaz /opt/pazpaz/scripts/backup-encryption-keys.sh >> /var/log/pazpaz/key-backup.log 2>&1
```

### Manual Backup (After Key Rotation)

```bash
# After rotating to v4, backup immediately
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Fetch new key (v4)
NEW_KEY=$(aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key-v4 \
  --query SecretString \
  --output text)

# Encrypt with GPG
echo "$NEW_KEY" | gpg --encrypt --armor --recipient security@pazpaz.com > \
  /secure/backups/keys/encryption-key-v4-$TIMESTAMP.gpg

# Upload to S3 (multiple regions)
aws s3 cp /secure/backups/keys/encryption-key-v4-$TIMESTAMP.gpg \
  s3://pazpaz-key-backups-us-east-1/rotation-backups/v4/

aws s3 cp /secure/backups/keys/encryption-key-v4-$TIMESTAMP.gpg \
  s3://pazpaz-key-backups-us-west-2/rotation-backups/v4/ \
  --region us-west-2

# Verify backup uploaded successfully
aws s3 ls s3://pazpaz-key-backups-us-east-1/rotation-backups/v4/encryption-key-v4-$TIMESTAMP.gpg
```

### Backup Storage Locations

**Primary**: AWS S3 (us-east-1) - `s3://pazpaz-key-backups-us-east-1/`
- Versioning: Enabled
- Encryption: AES-256 (SSE-S3)
- Lifecycle: Retain for 7 years (HIPAA compliance)
- Access: Restricted to Security Officer + DBA (IAM policy)

**Secondary**: AWS S3 (us-west-2) - `s3://pazpaz-key-backups-us-west-2/`
- Purpose: Disaster recovery (regional failover)
- Replication: Cross-region replication from us-east-1
- Same retention and encryption as primary

**Tertiary**: Offline GPG-encrypted backup
- Location: Secure vault (physical safe, off-site)
- Format: GPG-encrypted USB drives (2 copies)
- Update: After every rotation
- Access: Security Officer only (2-person rule for vault access)

---

## Key Recovery Procedure

### Recovery Scenarios

#### Scenario 1: Key Deleted from AWS Secrets Manager (Accidental)

**Impact**: Application cannot encrypt/decrypt data, service outage

**Recovery Steps**:

```bash
# 1. Identify most recent backup
aws s3 ls s3://pazpaz-key-backups-us-east-1/daily-backups/ | tail -5

# 2. Download encrypted backup
aws s3 cp s3://pazpaz-key-backups-us-east-1/daily-backups/keys-backup-20251019-030000.json.gpg /tmp/

# 3. Decrypt backup with GPG private key
gpg --decrypt /tmp/keys-backup-20251019-030000.json.gpg > /tmp/recovered-keys.json

# 4. Extract encryption key from JSON
ENCRYPTION_KEY=$(jq -r '.encryption_key' /tmp/recovered-keys.json)

# 5. Re-import to AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key \
  --secret-string "$ENCRYPTION_KEY" \
  --description "Recovered from backup $(date +%Y-%m-%d)" \
  --region us-east-1

# 6. Verify recovery
aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key \
  --query SecretString \
  --output text | head -c 20

# 7. Restart application
kubectl rollout restart deployment/pazpaz-api
kubectl rollout status deployment/pazpaz-api --timeout=5m

# 8. Verify application can decrypt data
curl -H "Authorization: Bearer $TOKEN" https://api.pazpaz.com/api/v1/clients | jq '.[0].full_name'

# 9. Cleanup sensitive files
shred -u /tmp/recovered-keys.json /tmp/keys-backup-*.json.gpg
unset ENCRYPTION_KEY

# 10. Document incident
echo "$(date): Key recovered from backup (keys-backup-20251019-030000)" >> /var/log/pazpaz/key-recovery.log
```

**Recovery Time Objective (RTO)**: 30 minutes
**Recovery Point Objective (RPO)**: 24 hours (last daily backup)

#### Scenario 2: AWS Secrets Manager Regional Outage

**Impact**: Cannot access keys in primary region (us-east-1)

**Recovery Steps**:

```bash
# 1. Failover to secondary region (us-west-2)
# Update application configuration
kubectl set env deployment/pazpaz-api AWS_DEFAULT_REGION=us-west-2

# 2. Verify keys accessible in us-west-2
aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key \
  --region us-west-2

# 3. Restart application with new region
kubectl rollout restart deployment/pazpaz-api

# 4. Monitor application logs for errors
kubectl logs -f deployment/pazpaz-api | grep -i "encryption\|decrypt"
```

**RTO**: 15 minutes (automated failover)
**RPO**: 0 (real-time replication)

#### Scenario 3: Catastrophic Key Loss (All Regions, No Backups)

**Impact**: TOTAL DATA LOSS for encrypted fields (cannot decrypt PHI)

**Recovery Steps**:

```
CRITICAL: Without encryption keys, encrypted data is PERMANENTLY UNRECOVERABLE.

Options:
1. Restore from coordinated backup (database + keys from same timestamp)
   - Requires database backup AND key backup from same point in time
   - Data loss: Since last coordinated backup (24 hours max)
   - Procedure: Restore database, import keys, verify decryption

2. If no key backup exists:
   - Encrypted data is LOST (cannot decrypt)
   - Must inform affected patients (HIPAA breach notification)
   - Potential regulatory fines and legal liability
   - Restore database to state BEFORE encryption (if available)

Prevention:
- MANDATORY daily automated backups
- MANDATORY quarterly recovery drills
- Multi-region backup replication
- Offline GPG-encrypted backups (physical vault)
```

### Quarterly Recovery Drill

**Objective**: Verify key backups are functional and recovery procedure works

**Drill Schedule**:
- Q1 (January 15)
- Q2 (April 15)
- Q3 (July 15)
- Q4 (October 15)

**Drill Procedure**:

```bash
# 1. Select random backup from last 30 days
BACKUP_FILE=$(aws s3 ls s3://pazpaz-key-backups-us-east-1/daily-backups/ | tail -30 | shuf -n 1 | awk '{print $4}')

echo "Testing recovery with backup: $BACKUP_FILE"

# 2. Download and decrypt
aws s3 cp "s3://pazpaz-key-backups-us-east-1/daily-backups/$BACKUP_FILE" /tmp/
gpg --decrypt "/tmp/$BACKUP_FILE" > /tmp/recovered-keys.json

# 3. Validate JSON structure
jq -e '.encryption_key, .jwt_secret, .database_credentials' /tmp/recovered-keys.json

# 4. Verify key length (256 bits = 32 bytes)
ENCRYPTION_KEY=$(jq -r '.encryption_key' /tmp/recovered-keys.json)
python3 -c "import base64; key = base64.b64decode('$ENCRYPTION_KEY'); assert len(key) == 32; print('✅ Key length: 32 bytes')"

# 5. Test decryption in staging environment
# Deploy staging with recovered key
kubectl create namespace staging-recovery-drill
kubectl create secret generic pazpaz-secrets \
  --namespace staging-recovery-drill \
  --from-literal=ENCRYPTION_MASTER_KEY="$ENCRYPTION_KEY"

# Deploy staging app
kubectl apply -f k8s/staging-deployment.yaml -n staging-recovery-drill

# Test decryption
STAGING_TOKEN=$(curl -X POST https://staging.pazpaz.com/api/v1/auth/magic-link ...)
curl -H "Authorization: Bearer $STAGING_TOKEN" https://staging.pazpaz.com/api/v1/clients | jq '.[0].full_name'
# Expected: Decrypted client name (not ciphertext)

# 6. Document drill results
cat >> /var/log/pazpaz/recovery-drills.log <<EOF
$(date): Key recovery drill PASSED
  Backup file: $BACKUP_FILE
  Decryption: Successful
  Key length: 32 bytes
  Staging test: Successful
EOF

# 7. Cleanup
kubectl delete namespace staging-recovery-drill
shred -u /tmp/recovered-keys.json "/tmp/$BACKUP_FILE"
unset ENCRYPTION_KEY
```

**Acceptance Criteria**:
- ✅ Backup file downloads successfully
- ✅ GPG decryption succeeds
- ✅ Key length is exactly 32 bytes
- ✅ Staging environment can decrypt data with recovered key
- ✅ Recovery completed within 30 minutes (RTO)

**Drill Documentation**: Results logged to `/var/log/pazpaz/recovery-drills.log` and reviewed in quarterly security meetings.

---

## Key Versioning Strategy

### Version Numbering Scheme

**Format**: `v{number}` (e.g., v1, v2, v3, v4, ...)

**Version Increment**:
- Routine rotation: v1 → v2 → v3 → v4 (incremental)
- Emergency rotation: v3 → v3_emergency → v4 (emergency suffix, then skip to next number)

### Backward Compatibility

**Dual-Key Mode** (during rotation):
- Application supports reading from **old key version** (v3) and writing with **new key version** (v4)
- Encrypted data format includes version prefix: `v4:nonce:ciphertext`
- Decryption logic automatically selects correct key based on version prefix

**Example Encrypted Data**:

```
# Client encrypted with v3
"full_name": "v3:rT8x9kp3Qw==:Uy3pZm9kLTJqeXh0NnY5d3o4YTJj..."

# Client encrypted with v4 (after rotation)
"full_name": "v4:aB7cDeFgHi==:Zx8wQrT6Nm2kYp4jL9vD3xS5hM1c..."
```

**Decryption Logic**:

```python
def decrypt_field_versioned(ciphertext: str) -> str:
    """Decrypt field with automatic key version selection."""
    parts = ciphertext.split(":")
    version = parts[0]  # e.g., "v3" or "v4"
    nonce = base64.b64decode(parts[1])
    encrypted_data = base64.b64decode(parts[2])

    # Select appropriate key
    if version == "v4":
        cipher = AESGCM(settings.encryption_key)  # Current key
    elif version == "v3" and settings.encryption_key_v3:
        cipher = AESGCM(settings.encryption_key_v3)  # Legacy key
    elif version == "v2" and settings.encryption_key_v2:
        cipher = AESGCM(settings.encryption_key_v2)  # Legacy key
    else:
        raise ValueError(f"Unsupported key version: {version}")

    plaintext = cipher.decrypt(nonce, encrypted_data, None)
    return plaintext.decode('utf-8')
```

### Key Retirement

**When to Retire Old Key Version**:
- ✅ 100% of encrypted data migrated to new version (no v3 records remain)
- ✅ Background re-encryption job completed successfully
- ✅ Data integrity validation passed (spot checks)

**Retirement Procedure**:
1. Remove old key from active secrets (AWS Secrets Manager)
2. Deploy application without dual-key support (v4 only)
3. Archive old key in encrypted backup vault (7-year retention)
4. Document retirement in key rotation audit log

**Archived Key Access**: Only Security Officer can retrieve archived keys (for forensic analysis or emergency recovery)

---

## Key Strength Requirements

### Encryption Master Key

**Algorithm**: AES-256-GCM
**Key Length**: 256 bits (32 bytes) - NIST-approved, HIPAA-compliant
**Entropy**: Minimum 250 bits effective entropy (cryptographically secure RNG)
**Format**: Base64-encoded for environment variable storage

**Validation**:

```python
def validate_encryption_key(key_b64: str) -> bool:
    """Validate encryption key meets strength requirements."""
    # Decode base64
    key = base64.b64decode(key_b64)

    # Check length (must be exactly 32 bytes for AES-256)
    if len(key) != 32:
        raise ValueError(f"Invalid key length: {len(key)} bytes (expected 32)")

    # Check entropy (unique bytes / total bytes)
    unique_bytes = len(set(key))
    entropy_ratio = unique_bytes / 256.0

    if entropy_ratio < 0.8:
        raise ValueError(f"Insufficient key entropy: {entropy_ratio:.2%} (expected >80%)")

    # Check not all zeros (common mistake)
    if key == b'\x00' * 32:
        raise ValueError("Key is all zeros (weak key)")

    return True
```

### JWT Signing Secret

**Algorithm**: HMAC-SHA256
**Key Length**: 256 bits (32 bytes) minimum
**Format**: Base64-encoded

### Database Password

**Length**: 32 characters minimum
**Character Set**: Alphanumeric + symbols (`!@#$%^&*()`)
**Complexity**: Must include uppercase, lowercase, digits, and symbols
**Prohibited**: Dictionary words, common patterns, repeated characters

---

## Access Control for Keys

### AWS Secrets Manager IAM Policies

**Production Encryption Key Access**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowApplicationServiceAccountRead",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/pazpaz-api-production"
      },
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:pazpaz/encryption-key-*",
      "Condition": {
        "StringEquals": {
          "aws:PrincipalTag/Environment": "production"
        }
      }
    },
    {
      "Sid": "AllowSecurityOfficerFullAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:user/security-officer"
      },
      "Action": "secretsmanager:*",
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:pazpaz/encryption-key-*",
      "Condition": {
        "Bool": {
          "aws:MultiFactorAuthPresent": "true"
        }
      }
    }
  ]
}
```

### Principle of Least Privilege

| Role | Encryption Key | JWT Secret | Database Creds | S3 Access Key |
|------|---------------|-----------|----------------|---------------|
| **Application (Runtime)** | Read-only | Read-only | Read-only | IAM role (temporary) |
| **Security Officer** | Full access (2FA) | Full access (2FA) | Full access (2FA) | Full access (2FA) |
| **Database Administrator** | Read-only (2FA) | No access | Full access (2FA) | No access |
| **DevOps/SRE** | No direct access | No direct access | Read-only (2FA) | No direct access |
| **Backend Developer** | No access (staging only) | No access (staging only) | No access (staging only) | No access |

### Two-Person Rule

**Key Rotation Approval**:
- Security Officer initiates rotation
- Database Administrator executes rotation
- Both must approve rotation in audit log

**Archived Key Retrieval**:
- Security Officer requests key
- Compliance Officer approves request
- Both document reason for retrieval

---

## Compliance & Audit

### HIPAA Documentation

**Required Documentation**:
1. Key rotation policy (this document)
2. Key rotation schedule (90-day calendar)
3. Key rotation audit log (database table)
4. Key backup verification log (quarterly drills)
5. Key access logs (AWS CloudTrail)
6. Emergency rotation incident reports

### Audit Trail

**Key Rotation Audit Table**:

```sql
CREATE TABLE key_rotation_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rotation_date TIMESTAMP NOT NULL DEFAULT NOW(),
  old_key_version VARCHAR(10) NOT NULL,
  new_key_version VARCHAR(10) NOT NULL,
  rotation_type VARCHAR(20) NOT NULL CHECK (rotation_type IN ('routine', 'emergency')),
  initiated_by VARCHAR(255) NOT NULL,
  approved_by VARCHAR(255) NOT NULL,
  completion_date TIMESTAMP,
  records_reencrypted BIGINT,
  notes TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'failed', 'rolled_back'))
);

-- Example: Log routine rotation from v3 to v4
INSERT INTO key_rotation_audit (
  old_key_version,
  new_key_version,
  rotation_type,
  initiated_by,
  approved_by,
  completion_date,
  records_reencrypted,
  notes,
  status
) VALUES (
  'v3',
  'v4',
  'routine',
  'security-officer@pazpaz.com',
  'dba@pazpaz.com',
  '2025-10-19 18:00:00',
  10543,
  'Routine 90-day rotation completed successfully',
  'completed'
);
```

### Monitoring & Alerting

**CloudWatch Alarms**:

```yaml
# Alert on unauthorized encryption key access
MetricFilter:
  FilterPattern: "{ $.eventName = GetSecretValue && $.requestParameters.secretId = pazpaz/encryption-key && $.errorCode NOT EXISTS }"
  MetricName: EncryptionKeyAccessCount
  Alarm:
    Threshold: 100 per hour
    Action: SNS → security@pazpaz.com
    Description: "Unusual encryption key access detected"

# Alert on key rotation failure
MetricFilter:
  FilterPattern: "[timestamp, level=ERROR, message=\"*key rotation failed*\"]"
  MetricName: KeyRotationFailures
  Alarm:
    Threshold: 1 occurrence
    Action: SNS → security@pazpaz.com + PagerDuty
    Description: "Key rotation failed - immediate attention required"

# Alert on decryption failures
MetricFilter:
  FilterPattern: "[timestamp, level=ERROR, message=\"*Failed to decrypt*\"]"
  MetricName: DecryptionFailures
  Alarm:
    Threshold: 10 per minute
    Action: SNS → oncall@pazpaz.com
    Description: "High rate of decryption failures - possible key issue"
```

---

## References

- [NIST SP 800-57: Key Management Recommendations](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [HIPAA Security Rule §164.312(a)(2)(iv): Encryption and Decryption](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)
- [PazPaz Encryption Architecture](/docs/security/SECURITY_ARCHITECTURE.md)
- [PazPaz Key Rotation Procedure](/docs/security/encryption/KEY_ROTATION_PROCEDURE.md)

---

**Document Owner**: Security Officer + Database Administrator
**Review Schedule**: Quarterly
**Next Review**: 2026-01-19
**Approved By**: Security Officer, HIPAA Compliance Officer, Database Administrator
