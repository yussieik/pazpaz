# Encryption Key Rotation Procedure
**Version:** 1.0
**Date:** 2025-10-03
**For:** DevOps, SRE, Database Administrators
**Criticality:** HIGH - Follow procedure exactly to avoid data loss

---

## Table of Contents

1. [Overview](#1-overview)
2. [Key Rotation Schedule](#2-key-rotation-schedule)
3. [Pre-Rotation Checklist](#3-pre-rotation-checklist)
4. [Routine Rotation Procedure](#4-routine-rotation-procedure)
5. [Emergency Rotation Procedure](#5-emergency-rotation-procedure)
6. [Validation and Rollback](#6-validation-and-rollback)
7. [Disaster Recovery](#7-disaster-recovery)
8. [Key Management Best Practices](#8-key-management-best-practices)

---

## 1. Overview

### 1.1 Purpose

This document defines the operational procedures for rotating encryption keys used to protect PHI/PII in the PazPaz application. Key rotation is a critical security practice that:

- Limits the exposure window if a key is compromised
- Meets HIPAA compliance requirements
- Reduces cryptographic risk from long-term key use

### 1.2 Key Rotation Strategy

**Zero-Downtime Rotation:**
- Application supports dual-key mode (v1 and v2 simultaneously)
- New writes use v2 key
- Old data remains readable with v1 key
- Background job re-encrypts all data to v2
- v1 key retired after full re-encryption

**Rotation Frequency:**
- **Routine rotation:** Every 12 months
- **Emergency rotation:** Within 24 hours of security incident

### 1.3 Roles and Responsibilities

| Role | Responsibility |
|------|---------------|
| Security Officer | Authorize key rotation, review security incidents |
| Database Administrator | Execute rotation procedure, monitor re-encryption |
| DevOps/SRE | Deploy application updates, manage secrets |
| Backend Developer | Verify application behavior, test dual-key mode |
| HIPAA Compliance Officer | Document rotation for audit trail |

---

## 2. Key Rotation Schedule

### 2.1 Routine Rotation Calendar

**Annual Schedule:**
- Q1 (January): Review key rotation procedure
- Q2 (April): Generate new key (v2), deploy dual-key application
- Q3 (July): Re-encrypt all data, retire old key (v1)
- Q4 (October): Audit rotation completion, update documentation

**Timeline for Routine Rotation:**
```
Week 1: Pre-rotation preparation and testing
Week 2: Deploy dual-key application (v1 + v2)
Week 3-6: Background re-encryption (gradual)
Week 7: Validation and old key retirement
Week 8: Post-rotation audit and documentation
```

### 2.2 Emergency Rotation Triggers

**Immediate rotation required if:**
- ✅ Encryption key exposed in version control, logs, or error messages
- ✅ Unauthorized access to secrets manager or environment variables
- ✅ Security incident affecting application servers
- ✅ Employee with key access leaves organization under suspicious circumstances
- ✅ Third-party security advisory affects encryption library

**Rotation timeline:**
- 0-4 hours: Incident detection and assessment
- 4-8 hours: Generate new key, deploy dual-key application
- 8-24 hours: Emergency re-encryption (accelerated)
- 24-48 hours: Retire compromised key, audit impact

---

## 3. Pre-Rotation Checklist

### 3.1 Preparation (1 Week Before)

**1. Verify Current Key Configuration**

```bash
# Check current key version in production
kubectl exec -it pazpaz-api-pod -- env | grep ENCRYPTION
# Expected output:
# ENCRYPTION_MASTER_KEY=<base64-key>
# ENCRYPTION_MASTER_KEY_V2=  (empty or not set)

# Verify key length
python -c "import os, base64; key = base64.b64decode(os.environ['ENCRYPTION_MASTER_KEY']); print(f'Key length: {len(key)} bytes')"
# Expected: Key length: 32 bytes
```

**2. Backup Current Key**

```bash
# Export current key to secure offline storage
kubectl get secret pazpaz-secrets -o jsonpath='{.data.ENCRYPTION_MASTER_KEY}' | base64 -d > /secure/backup/encryption-key-v1-$(date +%Y%m%d).bin

# Verify backup
ls -lh /secure/backup/encryption-key-v1-*.bin

# Encrypt backup with GPG (offline master key)
gpg --encrypt --recipient security@pazpaz.com /secure/backup/encryption-key-v1-$(date +%Y%m%d).bin

# Store encrypted backup in secure vault (offline, multiple locations)
```

**3. Review Data Inventory**

```sql
-- Count encrypted records per table
SELECT 'clients' AS table_name, COUNT(*) AS total_records
FROM clients
WHERE medical_history IS NOT NULL;

-- Estimate re-encryption time (assume 100 records/second)
-- Total time = total_records / 100 seconds
```

**4. Test Dual-Key Mode in Staging**

```bash
# Deploy staging environment with dual-key support
# Update staging secrets
kubectl create secret generic pazpaz-secrets-staging \
  --from-literal=ENCRYPTION_MASTER_KEY="$OLD_KEY" \
  --from-literal=ENCRYPTION_MASTER_KEY_V2="$NEW_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart staging pods
kubectl rollout restart deployment/pazpaz-api-staging

# Verify staging works with both keys
curl https://staging.pazpaz.com/api/v1/health
```

**5. Communication Plan**

```
Subject: Scheduled Encryption Key Rotation - [Date]

Team,

We will be performing a routine encryption key rotation on [DATE] as part of our HIPAA compliance procedures. This is a zero-downtime operation.

Timeline:
- [DATE 9:00 AM]: Deploy dual-key application update
- [DATE 9:00 AM - 5:00 PM]: Background re-encryption (gradual)
- [DATE 6:00 PM]: Validation and old key retirement

Expected impact: None (zero downtime)

Actions required:
- Monitor error rates during rotation window
- Report any authentication or data access issues immediately

Point of contact: [Name], [Email]
```

---

## 4. Routine Rotation Procedure

### 4.1 Phase 1: Generate New Key (Day 1, 9:00 AM)

**Step 1: Generate v2 Key**

```bash
# Generate new 256-bit encryption key
NEW_KEY=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

echo "New key (v2): $NEW_KEY"

# Verify key length
python -c "import base64; key = base64.b64decode('$NEW_KEY'); print(f'Length: {len(key)} bytes')"
# Expected: Length: 32 bytes
```

**Step 2: Store v2 Key in Secrets Manager**

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v2 \
  --secret-string "$NEW_KEY" \
  --description "Encryption key v2 (rotated $(date +%Y-%m-%d))" \
  --region us-east-1

# Or update existing secret
aws secretsmanager update-secret \
  --secret-id pazpaz/encryption-key \
  --secret-string "{\"v1\":\"$OLD_KEY\",\"v2\":\"$NEW_KEY\"}" \
  --region us-east-1
```

**Step 3: Update Environment Variables (Dual-Key Mode)**

```bash
# Kubernetes Secret (Production)
kubectl create secret generic pazpaz-secrets \
  --from-literal=ENCRYPTION_MASTER_KEY="$OLD_KEY" \
  --from-literal=ENCRYPTION_MASTER_KEY_V2="$NEW_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify secret
kubectl get secret pazpaz-secrets -o jsonpath='{.data.ENCRYPTION_MASTER_KEY_V2}' | base64 -d
```

### 4.2 Phase 2: Deploy Dual-Key Application (Day 1, 10:00 AM)

**Step 1: Update Application Code (Already Implemented)**

```python
# src/pazpaz/core/config.py

class Settings(BaseSettings):
    encryption_master_key: str = Field(..., env="ENCRYPTION_MASTER_KEY")
    encryption_master_key_v2: str | None = Field(None, env="ENCRYPTION_MASTER_KEY_V2")

    @property
    def encryption_key(self) -> bytes:
        """Primary encryption key (used for new writes)."""
        # Use v2 if available (during rotation)
        if self.encryption_master_key_v2:
            return base64.b64decode(self.encryption_master_key_v2)
        return base64.b64decode(self.encryption_master_key)

    @property
    def encryption_key_v1(self) -> bytes:
        """Legacy encryption key (for reading old data)."""
        return base64.b64decode(self.encryption_master_key)
```

```python
# src/pazpaz/db/encrypted_types.py

class EncryptedType(TypeDecorator):
    def __init__(self, key: bytes, key_v1: bytes | None = None, ...):
        self.key = key  # v2 (for writes)
        self.key_v1 = key_v1  # v1 (for reads during rotation)
        self.cipher = AESGCM(key)
        self.cipher_v1 = AESGCM(key_v1) if key_v1 else None

    def process_bind_param(self, value, dialect):
        """Encrypt with v2 key."""
        # Always use v2 for new writes
        nonce = secrets.token_bytes(12)
        ciphertext = self.cipher.encrypt(nonce, value.encode('utf-8'), None)
        return f"v2:{base64.b64encode(nonce).decode()}:{base64.b64encode(ciphertext).decode()}"

    def process_result_value(self, value, dialect):
        """Decrypt with appropriate key version."""
        parts = value.split(":")
        key_version = parts[0]

        if key_version == "v2":
            cipher = self.cipher  # v2 key
        elif key_version == "v1" and self.cipher_v1:
            cipher = self.cipher_v1  # v1 key
        else:
            raise ValueError(f"Unsupported key version: {key_version}")

        nonce = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        plaintext = cipher.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
```

**Step 2: Deploy Application Update**

```bash
# Build new Docker image with dual-key support
docker build -t pazpaz-api:v2.1.0 .

# Push to registry
docker push pazpaz-api:v2.1.0

# Update Kubernetes deployment
kubectl set image deployment/pazpaz-api pazpaz-api=pazpaz-api:v2.1.0

# Monitor rollout
kubectl rollout status deployment/pazpaz-api

# Verify pods are healthy
kubectl get pods -l app=pazpaz-api
```

**Step 3: Verify Dual-Key Mode Active**

```bash
# Check application logs for key version
kubectl logs -l app=pazpaz-api --tail=50 | grep -i "encryption"

# Test write (should use v2)
curl -X POST https://api.pazpaz.com/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Test","last_name":"User","consent_status":true}'

# Verify encrypted data uses v2
psql -h db-host -U pazpaz -c "SELECT first_name FROM clients WHERE last_name LIKE 'User%' LIMIT 1;"
# Expected: v2:rT8x9kp3Qw==:...
```

### 4.3 Phase 3: Re-Encrypt All Data (Day 1-7)

**Step 1: Run Re-Encryption Script**

```python
# src/pazpaz/scripts/reencrypt_clients.py

import asyncio
from sqlalchemy import select, update
from pazpaz.db.session import async_session
from pazpaz.models.client import Client

async def reencrypt_all_clients():
    """Re-encrypt all client data from v1 to v2."""
    batch_size = 100
    total_reencrypted = 0

    async with async_session() as db:
        # Count total records
        result = await db.execute(select(func.count(Client.id)))
        total = result.scalar_one()
        print(f"Total clients to re-encrypt: {total}")

        while True:
            # Find clients with v1 encrypted data
            # (We detect by checking if first_name starts with "v1:")
            result = await db.execute(
                text("SELECT id FROM clients WHERE first_name LIKE 'v1:%' LIMIT :limit"),
                {"limit": batch_size}
            )
            client_ids = [row[0] for row in result.fetchall()]

            if not client_ids:
                break  # All done

            # Load clients (ORM decrypts with v1 key)
            result = await db.execute(
                select(Client).where(Client.id.in_(client_ids))
            )
            clients = result.scalars().all()

            # Update each client (triggers re-encryption with v2 key)
            for client in clients:
                # Simply accessing and setting triggers re-encryption
                client.first_name = client.first_name  # Decrypt v1, encrypt v2
                client.last_name = client.last_name
                client.email = client.email
                client.medical_history = client.medical_history
                # ... other encrypted fields

            await db.commit()
            total_reencrypted += len(clients)

            print(f"Re-encrypted {total_reencrypted}/{total} clients ({total_reencrypted/total*100:.1f}%)")

            # Rate limiting (don't overload database)
            await asyncio.sleep(0.5)  # 200 records/second

    print(f"Re-encryption complete! Total: {total_reencrypted}")

if __name__ == "__main__":
    asyncio.run(reencrypt_all_clients())
```

**Step 2: Run Script in Background**

```bash
# Run on production server (in tmux/screen session)
kubectl exec -it pazpaz-api-pod -- uv run python -m pazpaz.scripts.reencrypt_clients

# Or run as Kubernetes Job
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: reencrypt-clients
spec:
  template:
    spec:
      containers:
      - name: reencrypt
        image: pazpaz-api:v2.1.0
        command: ["uv", "run", "python", "-m", "pazpaz.scripts.reencrypt_clients"]
        env:
        - name: ENCRYPTION_MASTER_KEY
          valueFrom:
            secretKeyRef:
              name: pazpaz-secrets
              key: ENCRYPTION_MASTER_KEY
        - name: ENCRYPTION_MASTER_KEY_V2
          valueFrom:
            secretKeyRef:
              name: pazpaz-secrets
              key: ENCRYPTION_MASTER_KEY_V2
      restartPolicy: OnFailure
EOF
```

**Step 3: Monitor Progress**

```bash
# Check job logs
kubectl logs -f job/reencrypt-clients

# Check database (count v1 vs v2 records)
psql -h db-host -U pazpaz -c "
SELECT
  SUM(CASE WHEN first_name LIKE 'v1:%' THEN 1 ELSE 0 END) AS v1_count,
  SUM(CASE WHEN first_name LIKE 'v2:%' THEN 1 ELSE 0 END) AS v2_count,
  COUNT(*) AS total
FROM clients;
"

# Expected output (progress over days):
# Day 1:  v1_count: 8000, v2_count: 2000, total: 10000
# Day 2:  v1_count: 5000, v2_count: 5000, total: 10000
# Day 7:  v1_count: 0,    v2_count: 10000, total: 10000
```

### 4.4 Phase 4: Retire Old Key (Day 8)

**Step 1: Verify Re-Encryption Complete**

```sql
-- Verify NO v1 records remain
SELECT COUNT(*) FROM clients WHERE first_name LIKE 'v1:%';
-- Expected: 0

SELECT COUNT(*) FROM clients WHERE medical_history LIKE 'v1:%';
-- Expected: 0

-- Verify ALL records use v2
SELECT COUNT(*) FROM clients WHERE first_name LIKE 'v2:%';
-- Expected: <total_clients>
```

**Step 2: Remove v1 Key from Application**

```bash
# Update secrets (remove ENCRYPTION_MASTER_KEY, keep only v2)
kubectl create secret generic pazpaz-secrets \
  --from-literal=ENCRYPTION_MASTER_KEY="$NEW_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Note: v2 becomes the new "v1" (primary key)
```

**Step 3: Deploy Single-Key Application**

```bash
# Application now only supports v2 key
# Update code to remove v1 support

# Deploy
kubectl set image deployment/pazpaz-api pazpaz-api=pazpaz-api:v2.2.0
kubectl rollout status deployment/pazpaz-api
```

**Step 4: Archive Old Key**

```bash
# Move old key to secure archive (DO NOT DELETE)
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v1-archived-$(date +%Y%m%d) \
  --secret-string "$OLD_KEY" \
  --description "Archived key v1 (rotated $(date +%Y-%m-%d))" \
  --region us-east-1

# Tag as archived
aws secretsmanager tag-resource \
  --secret-id pazpaz/encryption-key-v1-archived-$(date +%Y%m%d) \
  --tags Key=Status,Value=Archived Key=RotationDate,Value=$(date +%Y-%m-%d)
```

---

## 5. Emergency Rotation Procedure

### 5.1 Immediate Actions (0-4 Hours)

**Step 1: Incident Assessment**

```
INCIDENT REPORT TEMPLATE

Date/Time: [TIMESTAMP]
Reported By: [NAME]
Incident Type: [Key Exposure / Unauthorized Access / Other]

Description:
[How was the key exposed? Logs, version control, unauthorized access, etc.]

Scope:
[ ] Encryption key exposed in logs
[ ] Encryption key committed to version control
[ ] Unauthorized access to secrets manager
[ ] Suspicious employee activity
[ ] Third-party breach

Impact Assessment:
[ ] Low: Key exposure limited, no evidence of access
[ ] Medium: Key exposure public, no evidence of decryption
[ ] High: Key exposure confirmed, potential data decryption

Actions Taken:
1. [Revoke access to compromised systems]
2. [Rotate credentials]
3. [Initiate emergency key rotation]
```

**Step 2: Generate Emergency Key Immediately**

```bash
# Generate new key (v2)
EMERGENCY_KEY=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# Store in secrets manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v2-emergency \
  --secret-string "$EMERGENCY_KEY" \
  --description "Emergency rotation key (incident $(date +%Y%m%d))" \
  --region us-east-1
```

**Step 3: Deploy Dual-Key Application (Expedited)**

```bash
# Update secrets (emergency)
kubectl create secret generic pazpaz-secrets \
  --from-literal=ENCRYPTION_MASTER_KEY="$OLD_KEY" \
  --from-literal=ENCRYPTION_MASTER_KEY_V2="$EMERGENCY_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Force rollout (immediate)
kubectl rollout restart deployment/pazpaz-api
kubectl rollout status deployment/pazpaz-api --timeout=5m
```

### 5.2 Accelerated Re-Encryption (4-24 Hours)

**Step 1: Run Re-Encryption in Parallel**

```bash
# Increase batch size and parallelism
# Run 4 parallel jobs (split by client ID ranges)

kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: reencrypt-clients-emergency-1
spec:
  parallelism: 4  # 4 parallel workers
  template:
    spec:
      containers:
      - name: reencrypt
        image: pazpaz-api:v2.1.0
        command: ["uv", "run", "python", "-m", "pazpaz.scripts.reencrypt_clients", "--batch-size", "500", "--parallel", "4"]
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
      restartPolicy: OnFailure
EOF
```

**Step 2: Monitor Aggressively**

```bash
# Check progress every 10 minutes
watch -n 600 "psql -h db-host -U pazpaz -c \"
SELECT
  SUM(CASE WHEN first_name LIKE 'v1:%' THEN 1 ELSE 0 END) AS v1_remaining,
  SUM(CASE WHEN first_name LIKE 'v2:%' THEN 1 ELSE 0 END) AS v2_encrypted,
  COUNT(*) AS total
FROM clients;
\""
```

**Step 3: Retire Compromised Key Within 24 Hours**

```bash
# As soon as re-encryption completes, retire old key
# Follow Phase 4 procedure (expedited)

# Verify completion
SELECT COUNT(*) FROM clients WHERE first_name LIKE 'v1:%';
# Must be 0 before retiring key

# Remove compromised key
kubectl delete secret pazpaz-secrets
kubectl create secret generic pazpaz-secrets \
  --from-literal=ENCRYPTION_MASTER_KEY="$EMERGENCY_KEY"

# Deploy single-key application
kubectl set image deployment/pazpaz-api pazpaz-api=pazpaz-api:v2.2.0
```

### 5.3 Post-Incident Actions

**Step 1: Audit Data Access Logs**

```sql
-- Check if compromised key was used to access data
SELECT
  event_type,
  resource_type,
  user_id,
  ip_address,
  created_at
FROM audit_events
WHERE created_at BETWEEN '[INCIDENT_START]' AND '[INCIDENT_END]'
  AND action = 'READ'
  AND resource_type IN ('Client', 'Session', 'PlanOfCare')
ORDER BY created_at DESC;
```

**Step 2: Determine Breach Notification Requirement**

```
HIPAA BREACH NOTIFICATION DECISION TREE

Was the encryption key compromised?
  └─ YES
      └─ Was encrypted data accessed by unauthorized party?
          ├─ YES → BREACH NOTIFICATION REQUIRED
          │   └─ Actions:
          │       1. Notify affected individuals within 60 days
          │       2. Notify HHS Secretary
          │       3. Notify media (if >500 individuals affected)
          │
          └─ NO or UNKNOWN → Review encryption safe harbor
              └─ Was encryption key stored separately from data?
                  ├─ YES → SAFE HARBOR (no notification required)
                  └─ NO → Consult legal counsel
```

**Step 3: Document Incident**

```
INCIDENT REPORT (Post-Resolution)

Incident ID: INC-2025-001
Date: 2025-10-03
Severity: HIGH

Summary:
Encryption key exposed in application logs due to error handling bug.

Timeline:
- 09:00 AM: Key exposure discovered in CloudWatch logs
- 09:15 AM: Incident declared, emergency rotation initiated
- 10:00 AM: New key deployed (dual-key mode)
- 10:00 AM - 08:00 PM: Emergency re-encryption (10 hours)
- 08:30 PM: Old key retired, incident resolved

Impact:
- No evidence of unauthorized data access
- All data re-encrypted with new key
- HIPAA safe harbor applies (no breach notification required)

Root Cause:
Error handling code logged decrypted values in exception messages.

Remediation:
1. Updated error handling to never log sensitive data
2. Added code review checklist for sensitive data logging
3. Implemented automated log scanning for PII/PHI

Lessons Learned:
- Emergency rotation procedure worked as designed
- Re-encryption completed in 10 hours (faster than planned)
- Need better secrets detection in CI/CD pipeline
```

---

## 6. Validation and Rollback

### 6.1 Validation Checklist

**After Dual-Key Deployment:**

```bash
# 1. Verify application can read old data (v1 key)
curl -H "Authorization: Bearer $TOKEN" https://api.pazpaz.com/api/v1/clients/$CLIENT_ID
# Should return decrypted data (no errors)

# 2. Verify new writes use v2 key
curl -X POST https://api.pazpaz.com/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name":"TestV2","last_name":"User","consent_status":true}'

# Check database
psql -h db-host -U pazpaz -c "SELECT first_name FROM clients WHERE last_name = 'User';"
# Expected: v2:rT8x9kp3Qw==:...

# 3. Verify no errors in application logs
kubectl logs -l app=pazpaz-api --tail=100 | grep -i "decrypt"
# Should be no decryption errors
```

**After Re-Encryption:**

```bash
# 1. Verify all records migrated to v2
psql -h db-host -U pazpaz -c "
SELECT
  'clients' AS table_name,
  SUM(CASE WHEN first_name LIKE 'v1:%' THEN 1 ELSE 0 END) AS v1_count,
  SUM(CASE WHEN first_name LIKE 'v2:%' THEN 1 ELSE 0 END) AS v2_count
FROM clients
UNION ALL
SELECT
  'appointments',
  SUM(CASE WHEN notes LIKE 'v1:%' THEN 1 ELSE 0 END),
  SUM(CASE WHEN notes LIKE 'v2:%' THEN 1 ELSE 0 END)
FROM appointments;
"

# Expected: v1_count = 0, v2_count > 0

# 2. Spot-check decrypted data integrity
# (Compare before/after screenshots or exported data)
```

### 6.2 Rollback Procedure

**Scenario: Re-encryption fails or corrupts data**

**Step 1: Stop Re-Encryption Job**

```bash
kubectl delete job reencrypt-clients
```

**Step 2: Revert to Single-Key Application (v1 only)**

```bash
# Remove v2 key
kubectl create secret generic pazpaz-secrets \
  --from-literal=ENCRYPTION_MASTER_KEY="$OLD_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Rollback deployment
kubectl rollout undo deployment/pazpaz-api
kubectl rollout status deployment/pazpaz-api
```

**Step 3: Restore from Backup (if data corrupted)**

```bash
# Restore database from backup taken before rotation
pg_restore -h db-host -U pazpaz -d pazpaz /backups/pazpaz-backup-$(date +%Y%m%d).dump

# Verify data integrity
psql -h db-host -U pazpaz -c "SELECT COUNT(*) FROM clients;"
```

**Step 4: Post-Mortem**

```
ROLLBACK POST-MORTEM

Date: [DATE]
Reason for rollback: [Re-encryption failure / data corruption / etc.]

What went wrong:
[Detailed description]

Data loss:
[None / Partial / Full]

Recovery actions:
1. [Stopped re-encryption job]
2. [Reverted to v1 key]
3. [Restored from backup]

Prevention measures:
1. [Additional testing in staging]
2. [Smaller batch sizes]
3. [Better error handling]
```

---

## 7. Disaster Recovery

### 7.1 Key Loss Scenarios

**Scenario 1: Encryption key deleted from secrets manager**

**Recovery:**
```bash
# Restore from backup
gpg --decrypt /secure/backup/encryption-key-v1-20251003.bin.gpg > /tmp/encryption-key-v1.bin

# Re-import to secrets manager
KEY_B64=$(base64 < /tmp/encryption-key-v1.bin)

aws secretsmanager create-secret \
  --name pazpaz/encryption-key \
  --secret-string "$KEY_B64" \
  --region us-east-1

# Verify recovery
aws secretsmanager get-secret-value --secret-id pazpaz/encryption-key --query SecretString --output text

# Redeploy application
kubectl rollout restart deployment/pazpaz-api
```

**Scenario 2: All keys lost (catastrophic failure)**

**Recovery:**
```
CRITICAL: Without encryption keys, encrypted data is UNRECOVERABLE.

Options:
1. Restore from database backup + key backup (taken at same time)
   - Requires coordinated backups (database + keys)
   - Some data loss (since last backup)

2. If no key backup exists:
   - Data is permanently lost (cannot decrypt)
   - Must restore from database backup to state BEFORE encryption
   - Or accept total data loss for encrypted fields

Prevention:
- Backup keys alongside database backups (same timestamp)
- Store key backups in multiple secure locations
- Test key recovery quarterly
```

### 7.2 Key Backup Procedure

**Daily Automated Backup:**

```bash
#!/bin/bash
# /opt/pazpaz/scripts/backup-encryption-keys.sh

# Fetch current key from secrets manager
CURRENT_KEY=$(aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key \
  --query SecretString \
  --output text)

# Save to local encrypted backup
echo "$CURRENT_KEY" | gpg --encrypt --recipient security@pazpaz.com > \
  /secure/backups/encryption-key-$(date +%Y%m%d-%H%M%S).bin.gpg

# Upload to S3 (versioned bucket)
aws s3 cp /secure/backups/encryption-key-$(date +%Y%m%d-%H%M%S).bin.gpg \
  s3://pazpaz-key-backups/encryption-keys/ \
  --storage-class STANDARD_IA

# Cleanup old local backups (keep last 7 days)
find /secure/backups -name "encryption-key-*.bin.gpg" -mtime +7 -delete
```

**Cron Job:**
```bash
# Run daily at 3:00 AM
0 3 * * * /opt/pazpaz/scripts/backup-encryption-keys.sh >> /var/log/pazpaz/key-backup.log 2>&1
```

### 7.3 Key Recovery Testing

**Quarterly Test (Every 3 Months):**

```bash
# 1. Fetch key backup from S3
aws s3 cp s3://pazpaz-key-backups/encryption-keys/encryption-key-20251003-030000.bin.gpg /tmp/

# 2. Decrypt backup
gpg --decrypt /tmp/encryption-key-20251003-030000.bin.gpg > /tmp/recovered-key.txt

# 3. Verify key integrity
python -c "import base64; key = base64.b64decode(open('/tmp/recovered-key.txt').read().strip()); print(f'Key length: {len(key)} bytes')"
# Expected: Key length: 32 bytes

# 4. Test decryption with recovered key (in staging)
# Deploy staging with recovered key, verify data accessible

# 5. Document test results
echo "Key recovery test passed: $(date)" >> /var/log/pazpaz/key-recovery-tests.log

# 6. Cleanup
rm /tmp/recovered-key.txt /tmp/encryption-key-*.bin.gpg
```

---

## 8. Key Management Best Practices

### 8.1 Security Principles

**1. Separation of Duties:**
- Encryption keys managed by Security Officer + DBA (2-person rule)
- No single person can rotate keys without approval
- Require 2FA for secrets manager access

**2. Principle of Least Privilege:**
- Only application service account can access keys at runtime
- Developers cannot access production keys (only staging)
- DevOps can rotate keys but cannot view plaintext keys

**3. Defense in Depth:**
- Keys stored in secrets manager (encrypted at rest)
- Secrets manager access requires IAM role + 2FA
- Keys backed up in separate location (encrypted with GPG)
- Application code never logs keys (audit logs monitor for leaks)

### 8.2 Monitoring and Alerting

**CloudWatch Alarms:**

```yaml
# Alert on encryption key access
MetricFilter:
  FilterPattern: "{ $.eventName = GetSecretValue && $.requestParameters.secretId = pazpaz/encryption-key }"
  MetricName: EncryptionKeyAccess
  Alarm:
    Threshold: 100 per hour  # Alert if excessive access
    Action: SNS topic (security team)

# Alert on decryption failures
MetricFilter:
  FilterPattern: "[timestamp, request_id, level=ERROR, message=\"*Failed to decrypt field*\"]"
  MetricName: DecryptionFailures
  Alarm:
    Threshold: 10 per minute
    Action: SNS topic (on-call engineer)
```

**Audit Trail:**

```sql
-- Log all encryption key rotations
CREATE TABLE key_rotation_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rotation_date TIMESTAMP NOT NULL DEFAULT NOW(),
  old_key_version VARCHAR(10) NOT NULL,
  new_key_version VARCHAR(10) NOT NULL,
  rotation_type VARCHAR(20) NOT NULL, -- 'routine' or 'emergency'
  initiated_by VARCHAR(255) NOT NULL,
  completion_date TIMESTAMP,
  records_reencrypted BIGINT,
  notes TEXT
);

-- Insert after each rotation
INSERT INTO key_rotation_audit (old_key_version, new_key_version, rotation_type, initiated_by, notes)
VALUES ('v1', 'v2', 'routine', 'security-officer@pazpaz.com', 'Annual routine rotation');
```

### 8.3 Compliance Documentation

**For HIPAA Audits:**

1. **Key Rotation Policy**
   - Documented rotation schedule (annual)
   - Emergency rotation triggers
   - Approval workflow

2. **Key Access Logs**
   - AWS CloudTrail logs (GetSecretValue events)
   - Key rotation audit table

3. **Encryption Standards**
   - Algorithm: AES-256-GCM (NIST-approved)
   - Key length: 256 bits
   - Key derivation: Secure random generation

4. **Disaster Recovery**
   - Key backup procedures
   - Recovery test results (quarterly)
   - RTO/RPO metrics

---

## Appendix A: Key Rotation Checklist

**Pre-Rotation (1 Week Before):**
- [ ] Backup current encryption key (encrypted with GPG)
- [ ] Test dual-key mode in staging environment
- [ ] Estimate re-encryption time (record count / throughput)
- [ ] Communicate rotation schedule to team
- [ ] Verify database backups are current

**Day 1: Deploy Dual-Key Application**
- [ ] Generate new encryption key (v2)
- [ ] Store v2 key in secrets manager
- [ ] Update Kubernetes secrets with both keys
- [ ] Deploy dual-key application
- [ ] Verify new writes use v2 key
- [ ] Verify old reads use v1 key (no errors)

**Day 1-7: Re-Encrypt Data**
- [ ] Run re-encryption script (background job)
- [ ] Monitor progress daily (v1 vs v2 counts)
- [ ] Check for errors in application logs
- [ ] Verify data integrity (spot checks)

**Day 8: Retire Old Key**
- [ ] Verify 100% of data migrated to v2
- [ ] Remove v1 key from secrets manager
- [ ] Deploy single-key application (v2 only)
- [ ] Archive old key in secure vault
- [ ] Document rotation completion

**Post-Rotation:**
- [ ] Update key rotation audit table
- [ ] Generate compliance report for HIPAA
- [ ] Backup new key (v2)
- [ ] Update runbooks and documentation
- [ ] Schedule next rotation (12 months)

---

## Appendix B: Emergency Contact List

| Role | Name | Email | Phone |
|------|------|-------|-------|
| Security Officer | [Name] | security@pazpaz.com | [Phone] |
| Database Administrator | [Name] | dba@pazpaz.com | [Phone] |
| DevOps Lead | [Name] | devops@pazpaz.com | [Phone] |
| HIPAA Compliance Officer | [Name] | compliance@pazpaz.com | [Phone] |
| On-Call Engineer | [Rotation] | oncall@pazpaz.com | [PagerDuty] |

**Emergency Escalation:**
1. On-Call Engineer (immediate)
2. DevOps Lead (within 30 minutes)
3. Security Officer (within 1 hour)
4. HIPAA Compliance Officer (for breach assessment)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-03
**Next Review:** 2026-01-01
**Owner:** Security Officer + Database Administrator
