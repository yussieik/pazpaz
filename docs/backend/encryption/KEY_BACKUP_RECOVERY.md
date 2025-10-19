# Encryption Key Backup & Recovery Procedures

**Version:** 1.0
**Date:** 2025-10-19
**Status:** ✅ Implemented
**HIPAA Compliance:** Key backup and disaster recovery (§164.308(a)(7)(ii)(A))

---

## Table of Contents

1. [Overview](#overview)
2. [Multi-Region Replication](#multi-region-replication)
3. [Offline Backup Procedure](#offline-backup-procedure)
4. [Recovery Procedures](#recovery-procedures)
5. [Quarterly Recovery Drills](#quarterly-recovery-drills)
6. [Disaster Scenarios](#disaster-scenarios)
7. [Troubleshooting](#troubleshooting)
8. [HIPAA Compliance Notes](#hipaa-compliance-notes)

---

## Overview

### Purpose

This document describes the encryption key backup and recovery procedures for PazPaz. The system implements a **defense-in-depth** strategy with three layers of key backup:

1. **Primary Storage**: AWS Secrets Manager (us-east-1)
2. **Multi-Region Replication**: AWS Secrets Manager replicas (us-west-2, eu-west-1)
3. **Offline Backup**: GPG-encrypted backups in secure physical locations

### Critical Requirements

**WITHOUT ENCRYPTION KEYS, ALL PHI DATA IS PERMANENTLY INACCESSIBLE.**

- **RTO (Recovery Time Objective)**: 1 hour - maximum time to restore key access
- **RPO (Recovery Point Objective)**: 24 hours - maximum data loss (daily backups)
- **HIPAA Requirement**: §164.308(a)(7)(ii)(A) - Data backup and disaster recovery plan

### Key Backup Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                   Key Backup Strategy (3 Layers)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: AWS Secrets Manager Primary (us-east-1)               │
│           - Production encryption keys (v1, v2, v3, ...)        │
│           - Automatic backups within region                      │
│           - High availability, low latency                       │
│                                                                  │
│  Layer 2: Multi-Region Replication (us-west-2, eu-west-1)      │
│           - Automatic asynchronous replication                   │
│           - Regional failover capability                         │
│           - Protects against single-region outage                │
│                                                                  │
│  Layer 3: Offline GPG-Encrypted Backup                          │
│           - Daily encrypted backups to offline storage           │
│           - Fireproof safe / Safety deposit box                  │
│           - Protects against total AWS outage or account loss    │
│           - Manual recovery (requires GPG private key)           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-Region Replication

### Architecture

**Primary Region**: `us-east-1` (US East - N. Virginia)
**Replica Regions**:
- `us-west-2` (US West - Oregon)
- `eu-west-1` (EU - Ireland)

**Replication Lag**: Typically <1 second (asynchronous)

### Setup Procedure

#### 1. Enable Multi-Region Replication

For each encryption key version (v1, v2, v3, ...), enable replication to backup regions:

```bash
#!/bin/bash
# scripts/setup_multi_region_replication.sh

# Configuration
PRIMARY_REGION="us-east-1"
REPLICA_REGIONS=("us-west-2" "eu-west-1")
SECRET_PREFIX="pazpaz/encryption-key-"

# Get all encryption key secrets
SECRETS=$(aws secretsmanager list-secrets \
    --region $PRIMARY_REGION \
    --filters Key=name,Values=$SECRET_PREFIX \
    --query 'SecretList[].Name' \
    --output text)

# Enable replication for each secret
for SECRET_NAME in $SECRETS; do
    echo "Enabling replication for: $SECRET_NAME"

    # Build replica region arguments
    REPLICA_ARGS=""
    for REGION in "${REPLICA_REGIONS[@]}"; do
        REPLICA_ARGS="$REPLICA_ARGS --add-replica-regions Region=$REGION"
    done

    # Replicate secret
    aws secretsmanager replicate-secret-to-regions \
        --region $PRIMARY_REGION \
        --secret-id $SECRET_NAME \
        $REPLICA_ARGS

    echo "✅ Replication enabled for $SECRET_NAME"
done

echo ""
echo "✅ Multi-region replication setup complete!"
echo "   Primary region: $PRIMARY_REGION"
echo "   Replica regions: ${REPLICA_REGIONS[@]}"
```

#### 2. Verify Replication Status

```bash
#!/bin/bash
# Verify replication is working

SECRET_NAME="pazpaz/encryption-key-v1"
PRIMARY_REGION="us-east-1"

# Describe secret to see replication status
aws secretsmanager describe-secret \
    --region $PRIMARY_REGION \
    --secret-id $SECRET_NAME \
    --query 'ReplicationStatus[].{Region:Region,Status:Status,LastAccessedDate:LastAccessedDate}' \
    --output table

# Expected output:
# -----------------------------------------------------------
# |                    DescribeSecret                       |
# +---------------+------------------+----------------------+
# |    Region     |     Status       | LastAccessedDate     |
# +---------------+------------------+----------------------+
# |  us-west-2    |  InSync          |  2025-10-19T10:00:00Z|
# |  eu-west-1    |  InSync          |  2025-10-19T10:00:00Z|
# +---------------+------------------+----------------------+
```

#### 3. Monitor Replication Lag

Create CloudWatch alarm to detect replication issues:

```bash
# CloudWatch alarm for replication lag
aws cloudwatch put-metric-alarm \
    --alarm-name "PazPaz-Encryption-Key-Replication-Lag" \
    --alarm-description "Alert if encryption key replication lag exceeds 60 seconds" \
    --metric-name ReplicationLatency \
    --namespace AWS/SecretsManager \
    --statistic Maximum \
    --period 300 \
    --threshold 60 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:security-alerts
```

### Failover Procedure

If primary region (us-east-1) is unavailable, switch to replica region:

```python
# pazpaz/utils/secrets_manager.py

def get_encryption_key_version(
    version: str,
    region: str = None,
    retry_regions: list[str] = None,
) -> bytes:
    """
    Fetch encryption key with automatic regional failover.

    Args:
        version: Key version (e.g., "v1", "v2")
        region: Primary region (default: us-east-1)
        retry_regions: Fallback regions (default: [us-west-2, eu-west-1])

    Returns:
        32-byte encryption key

    Raises:
        KeyRecoveryError: If key cannot be fetched from any region
    """
    if region is None:
        region = settings.aws_region or "us-east-1"

    if retry_regions is None:
        retry_regions = ["us-west-2", "eu-west-1"]

    secret_name = f"pazpaz/encryption-key-{version}"
    regions_to_try = [region] + retry_regions

    for current_region in regions_to_try:
        try:
            logger.info(
                "fetching_encryption_key",
                version=version,
                region=current_region,
            )

            client = boto3.client("secretsmanager", region_name=current_region)
            response = client.get_secret_value(SecretId=secret_name)

            secret_value = json.loads(response["SecretString"])
            key = base64.b64decode(secret_value["encryption_key"])

            logger.info(
                "encryption_key_fetched",
                version=version,
                region=current_region,
                failover=current_region != region,
            )

            return key

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.warning(
                "encryption_key_fetch_failed",
                version=version,
                region=current_region,
                error_code=error_code,
            )

            # Try next region
            continue

    # All regions failed
    raise KeyRecoveryError(
        f"Failed to fetch encryption key {version} from all regions: {regions_to_try}"
    )
```

---

## Offline Backup Procedure

### GPG Key Setup

#### 1. Generate GPG Key Pair (One-Time Setup)

```bash
#!/bin/bash
# Generate GPG key pair for encryption key backups

# Interactive key generation
gpg --full-generate-key

# Select options:
# - Key type: (1) RSA and RSA (default)
# - Key size: 4096 bits
# - Expiration: 0 (does not expire) or 5 years
# - Real name: PazPaz Security Team
# - Email: security@pazpaz.com
# - Passphrase: STRONG_PASSPHRASE (store in 1Password/Keeper)

# Verify key created
gpg --list-keys security@pazpaz.com

# Output:
# pub   rsa4096 2025-10-19 [SC]
#       ABCD1234567890ABCDEF1234567890ABCDEF12
# uid           [ultimate] PazPaz Security Team <security@pazpaz.com>
# sub   rsa4096 2025-10-19 [E]
```

#### 2. Export and Secure GPG Private Key

```bash
#!/bin/bash
# Export GPG private key for disaster recovery

# Export private key (keep VERY secure!)
gpg --export-secret-keys --armor security@pazpaz.com > gpg-private-key.asc

# Encrypt private key with additional passphrase
gpg --symmetric --cipher-algo AES256 gpg-private-key.asc

# Result: gpg-private-key.asc.gpg

# Store in 3 locations:
# 1. Company password manager (1Password/Keeper vault)
# 2. Printed copy in fireproof safe (physical security)
# 3. USB drive in bank safety deposit box

# Securely delete plaintext private key
shred -vfz -n 10 gpg-private-key.asc
```

#### 3. Distribute GPG Public Key

```bash
#!/bin/bash
# Export and distribute GPG public key

# Export public key
gpg --export --armor security@pazpaz.com > gpg-public-key.asc

# Distribute to team members who need to create backups
# Store in repository (safe to commit):
cp gpg-public-key.asc /Users/yussieik/Desktop/projects/pazpaz/backend/keys/gpg-public-key.asc

# Import on backup server
gpg --import gpg-public-key.asc
```

### Daily Backup Script

```bash
#!/bin/bash
# scripts/backup_encryption_keys.sh
# Daily automated backup of encryption keys to offline storage

set -euo pipefail

# Configuration
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/secure/backups/encryption-keys"
AWS_REGION="us-east-1"
GPG_RECIPIENT="security@pazpaz.com"
SECRET_PREFIX="pazpaz/encryption-key-"

# Create backup directory
mkdir -p "$BACKUP_DIR"
cd "$BACKUP_DIR"

echo "🔐 Starting encryption key backup: $DATE"
echo ""

# Fetch all key versions from AWS Secrets Manager
SECRETS=$(aws secretsmanager list-secrets \
    --region $AWS_REGION \
    --filters Key=name,Values=$SECRET_PREFIX \
    --query 'SecretList[].Name' \
    --output text)

BACKUP_COUNT=0

for SECRET_NAME in $SECRETS; do
    VERSION=$(echo $SECRET_NAME | sed "s|$SECRET_PREFIX||")

    echo "📦 Backing up: $SECRET_NAME (version: $VERSION)"

    # Fetch secret value
    SECRET_VALUE=$(aws secretsmanager get-secret-value \
        --region $AWS_REGION \
        --secret-id $SECRET_NAME \
        --query SecretString \
        --output text)

    # Create backup filename
    BACKUP_FILE="encryption-key-${VERSION}-backup-${DATE}.json"
    ENCRYPTED_FILE="${BACKUP_FILE}.gpg"

    # Save secret to temporary file
    echo "$SECRET_VALUE" > "$BACKUP_FILE"

    # Encrypt with GPG
    gpg --encrypt \
        --recipient $GPG_RECIPIENT \
        --armor \
        --output "$ENCRYPTED_FILE" \
        "$BACKUP_FILE"

    # Securely delete plaintext
    shred -vfz -n 10 "$BACKUP_FILE"

    echo "   ✅ Encrypted backup: $ENCRYPTED_FILE"

    ((BACKUP_COUNT++))
done

echo ""
echo "✅ Backup complete!"
echo "   Keys backed up: $BACKUP_COUNT"
echo "   Backup directory: $BACKUP_DIR"
echo ""
echo "📋 Next steps:"
echo "   1. Copy encrypted backups to USB drive"
echo "   2. Store USB in fireproof safe (Location A)"
echo "   3. Update backup log: /secure/backups/BACKUP_LOG.md"
echo "   4. Verify backups with: scripts/verify_backup.sh"

# Create backup manifest
cat > "BACKUP_MANIFEST_${DATE}.txt" <<EOF
Encryption Key Backup Manifest
Generated: $DATE
Backup Directory: $BACKUP_DIR
AWS Region: $AWS_REGION

Keys Backed Up:
$(ls -lh *.gpg)

Storage Instructions:
1. Copy all .gpg files to encrypted USB drive
2. Label USB: "PazPaz Encryption Keys - $DATE"
3. Store in fireproof safe (Location A: Office safe)
4. Maintain 3 most recent backups, archive older backups to Location B (bank vault)

Recovery Contact:
Security Team: security@pazpaz.com
EOF

echo ""
echo "📄 Manifest created: BACKUP_MANIFEST_${DATE}.txt"
```

### Backup Storage Locations

**Location A (Primary)**: Office fireproof safe
- **Access**: CTO + Security Lead
- **Retention**: 3 most recent daily backups
- **Verification**: Weekly visual inspection

**Location B (Secondary)**: Bank safety deposit box
- **Access**: CEO + CTO
- **Retention**: Monthly backups for 1 year
- **Verification**: Quarterly drill

**Location C (Tertiary)**: Encrypted cloud storage (AWS S3 Glacier Deep Archive)
- **Access**: Security team (IAM roles)
- **Retention**: All backups, 7-year retention
- **Verification**: Annual drill

### Backup Rotation Schedule

```
Daily:    Create encrypted backup → Store in Location A
Weekly:   Verify backups in Location A readable
Monthly:  Archive to Location B (bank vault)
Annually: Archive to Location C (Glacier Deep Archive)
```

---

## Recovery Procedures

### Recovery Scenario 1: Primary Region Outage

**Trigger**: AWS us-east-1 region unavailable
**RTO**: 5 minutes (automatic failover)
**RPO**: 0 (real-time replication)

**Procedure**:

```python
# Application automatically fails over to replica region
# pazpaz/utils/secrets_manager.py handles this via retry_regions

# Manual verification:
from pazpaz.utils.secrets_manager import get_encryption_key_version

# This will automatically try us-west-2, then eu-west-1
key = get_encryption_key_version("v1")

# Verify decryption works
from pazpaz.utils.encryption import decrypt_field

test_ciphertext = b"v1:..." # Load from database
plaintext = decrypt_field(test_ciphertext, key)

assert plaintext == "expected value"
```

**No manual intervention required** - application handles failover automatically.

### Recovery Scenario 2: Total AWS Outage (All Regions)

**Trigger**: All AWS regions unavailable or account compromised
**RTO**: 1 hour (manual recovery)
**RPO**: 24 hours (daily backups)

**Procedure**:

#### Step 1: Retrieve Offline Backup

```bash
# 1. Retrieve USB drive from fireproof safe (Location A)
# 2. Insert USB into secure air-gapped machine
# 3. Copy encrypted backup files

cd /secure/recovery
cp /media/usb/encryption-key-*.gpg .

# Verify files copied
ls -lh encryption-key-*.gpg

# encryption-key-v1-backup-20251019_100000.json.gpg
# encryption-key-v2-backup-20251019_100000.json.gpg
# encryption-key-v3-backup-20251019_100000.json.gpg
```

#### Step 2: Decrypt GPG Backup

```bash
#!/bin/bash
# scripts/restore_encryption_keys.sh

set -euo pipefail

# Configuration
BACKUP_DIR="/secure/recovery"
RESTORE_DIR="/secure/restored-keys"
GPG_KEY="security@pazpaz.com"

mkdir -p "$RESTORE_DIR"
cd "$BACKUP_DIR"

echo "🔓 Decrypting encryption key backups..."
echo ""

for ENCRYPTED_FILE in encryption-key-*.gpg; do
    echo "📂 Decrypting: $ENCRYPTED_FILE"

    # Extract base filename (remove .gpg)
    DECRYPTED_FILE="${ENCRYPTED_FILE%.gpg}"

    # Decrypt with GPG (prompts for passphrase)
    gpg --decrypt \
        --output "$RESTORE_DIR/$DECRYPTED_FILE" \
        "$ENCRYPTED_FILE"

    echo "   ✅ Decrypted: $RESTORE_DIR/$DECRYPTED_FILE"
done

echo ""
echo "✅ Decryption complete!"
echo "   Restored keys: $RESTORE_DIR"
echo ""
echo "📋 Next steps:"
echo "   1. Verify key integrity: scripts/verify_restored_keys.sh"
echo "   2. Re-upload to AWS Secrets Manager (if recovered)"
echo "   3. Or load directly into application environment variables"
```

#### Step 3: Verify Key Integrity

```python
# scripts/verify_restored_keys.py

import json
import base64
from pathlib import Path

def verify_restored_keys(restore_dir: Path):
    """Verify restored encryption keys are valid."""

    print("🔍 Verifying restored encryption keys...")
    print()

    for key_file in restore_dir.glob("encryption-key-*.json"):
        print(f"📄 Verifying: {key_file.name}")

        # Load key metadata
        with open(key_file, "r") as f:
            secret_value = json.load(f)

        # Verify required fields
        assert "encryption_key" in secret_value, "Missing encryption_key"
        assert "version" in secret_value, "Missing version"
        assert "created_at" in secret_value, "Missing created_at"
        assert "expires_at" in secret_value, "Missing expires_at"

        # Verify key format
        key_bytes = base64.b64decode(secret_value["encryption_key"])
        assert len(key_bytes) == 32, f"Invalid key size: {len(key_bytes)} bytes (expected 32)"

        # Verify version format
        version = secret_value["version"]
        assert version.startswith("v"), f"Invalid version format: {version}"

        print(f"   ✅ Valid: {version}, created {secret_value['created_at']}")

    print()
    print("✅ All keys verified successfully!")

if __name__ == "__main__":
    restore_dir = Path("/secure/restored-keys")
    verify_restored_keys(restore_dir)
```

#### Step 4: Restore Keys to AWS (If Available)

```bash
#!/bin/bash
# Re-upload restored keys to AWS Secrets Manager

RESTORE_DIR="/secure/restored-keys"
AWS_REGION="us-east-1"

cd "$RESTORE_DIR"

for KEY_FILE in encryption-key-*.json; do
    VERSION=$(echo $KEY_FILE | sed 's/encryption-key-//' | sed 's/-backup.*//')
    SECRET_NAME="pazpaz/encryption-key-${VERSION}"

    echo "📤 Uploading: $SECRET_NAME"

    # Check if secret exists
    if aws secretsmanager describe-secret \
        --region $AWS_REGION \
        --secret-id $SECRET_NAME &> /dev/null; then

        # Update existing secret
        aws secretsmanager put-secret-value \
            --region $AWS_REGION \
            --secret-id $SECRET_NAME \
            --secret-string file://$KEY_FILE

        echo "   ✅ Updated: $SECRET_NAME"
    else
        # Create new secret
        aws secretsmanager create-secret \
            --region $AWS_REGION \
            --name $SECRET_NAME \
            --secret-string file://$KEY_FILE

        echo "   ✅ Created: $SECRET_NAME"
    fi
done

echo ""
echo "✅ Keys restored to AWS Secrets Manager!"
echo "   Region: $AWS_REGION"
```

#### Step 5: Test Decryption with Restored Keys

```python
# tests/test_restored_keys.py

import base64
import json
from pathlib import Path
from pazpaz.utils.encryption import decrypt_field

async def test_decrypt_with_restored_keys():
    """Test that restored keys can decrypt production PHI data."""

    # 1. Load restored keys
    restore_dir = Path("/secure/restored-keys")

    for key_file in restore_dir.glob("encryption-key-*.json"):
        with open(key_file, "r") as f:
            secret_value = json.load(f)

        version = secret_value["version"]
        key = base64.b64decode(secret_value["encryption_key"])

        print(f"🔍 Testing decryption with {version}...")

        # 2. Fetch test ciphertext from database
        # (encrypted with this key version)
        test_ciphertext = await fetch_test_ciphertext(version)

        # 3. Decrypt
        plaintext = decrypt_field(test_ciphertext, key)

        # 4. Verify matches expected value
        expected = await fetch_expected_plaintext(version)
        assert plaintext == expected, f"Decryption mismatch for {version}"

        print(f"   ✅ {version} decryption successful")

    print()
    print("✅ All restored keys verified with production data!")
```

### Recovery Scenario 3: Lost AWS Account Access

**Trigger**: AWS account credentials lost/compromised
**RTO**: 4 hours (manual recovery + AWS support)
**RPO**: 24 hours (daily backups)

**Procedure**:

1. **Contact AWS Support** (Critical Priority)
   - Account recovery process
   - Provide account ID, ownership verification
   - Expected response: 2-4 hours

2. **While Waiting for AWS**:
   - Retrieve offline backups (Location A or B)
   - Decrypt keys using GPG private key
   - Load keys into application via environment variables
   - Application continues operating with local keys

3. **After AWS Access Restored**:
   - Re-upload keys to AWS Secrets Manager
   - Re-enable multi-region replication
   - Verify application switched back to AWS key fetching

### Recovery Scenario 4: Lost GPG Private Key

**Trigger**: GPG private key lost or compromised
**RTO**: N/A (prevented through redundancy)
**RPO**: N/A

**Prevention**:

1. **3 Copies of GPG Private Key**:
   - Copy 1: Password manager (1Password/Keeper)
   - Copy 2: Printed paper in fireproof safe
   - Copy 3: Encrypted USB in bank vault

2. **Compromise Procedure**:
   - If GPG key compromised, immediately:
     1. Generate new GPG key pair
     2. Re-encrypt all offline backups with new key
     3. Update backup procedures to use new key
     4. Revoke old GPG key
     5. Audit who had access to compromised key

---

## Quarterly Recovery Drills

### Purpose

**HIPAA Requirement**: §164.308(a)(7)(ii)(E) - Testing and revision procedures

Quarterly drills ensure:
1. Backup and recovery procedures actually work
2. Team members are trained and capable
3. RTO/RPO targets are achievable
4. Documentation is accurate and up-to-date

### Drill Schedule

- **Q1 (January)**: Multi-region failover drill
- **Q2 (April)**: Offline backup recovery drill
- **Q3 (July)**: Total AWS outage simulation
- **Q4 (October)**: Lost account access simulation

### Drill Checklist

#### Pre-Drill Preparation (1 week before)

- [ ] Schedule 2-hour maintenance window (non-production hours)
- [ ] Notify team members of drill (CTO, Security Lead, DevOps)
- [ ] Prepare test PHI data encrypted with all key versions
- [ ] Verify backup storage locations accessible (safe keys available)
- [ ] Review recovery procedures documentation

#### Drill Execution

**Quarterly Drill 1: Multi-Region Failover**

```python
# tests/quarterly/test_q1_multi_region_failover.py

import pytest
from pazpaz.utils.secrets_manager import get_encryption_key_version
from pazpaz.utils.encryption import decrypt_field

@pytest.mark.quarterly_drill
async def test_multi_region_failover_drill():
    """
    Q1 Drill: Test automatic failover to replica regions.

    Scenario: Primary region (us-east-1) becomes unavailable
    Expected: Application automatically fails over to us-west-2
    RTO Target: <5 minutes
    """
    print("\n" + "="*70)
    print("Q1 QUARTERLY DRILL: Multi-Region Failover")
    print("="*70)

    # 1. Verify primary region works
    print("\n1️⃣ Verifying primary region (us-east-1)...")
    key_v1 = get_encryption_key_version("v1", region="us-east-1")
    assert len(key_v1) == 32
    print("   ✅ Primary region operational")

    # 2. Simulate primary region failure (mock AWS failure)
    print("\n2️⃣ Simulating us-east-1 outage...")
    with mock_aws_region_failure("us-east-1"):

        # 3. Fetch key (should failover to us-west-2)
        print("\n3️⃣ Testing automatic failover...")
        start_time = time.time()

        key_v1_failover = get_encryption_key_version(
            "v1",
            region="us-east-1",
            retry_regions=["us-west-2", "eu-west-1"]
        )

        failover_time = time.time() - start_time

        assert len(key_v1_failover) == 32
        assert failover_time < 5.0, f"Failover took {failover_time}s (target: <5s)"

        print(f"   ✅ Failover successful in {failover_time:.2f}s")

    # 4. Verify keys are identical
    print("\n4️⃣ Verifying key consistency...")
    assert key_v1 == key_v1_failover
    print("   ✅ Keys match (replication working)")

    # 5. Test decryption with failover key
    print("\n5️⃣ Testing decryption with failover key...")
    test_ciphertext = load_test_ciphertext("v1")
    plaintext = decrypt_field(test_ciphertext, key_v1_failover)

    assert plaintext == EXPECTED_PLAINTEXT
    print("   ✅ Decryption successful")

    print("\n" + "="*70)
    print("✅ Q1 DRILL PASSED - Multi-region failover operational")
    print(f"   Failover time: {failover_time:.2f}s (target: <5s)")
    print("="*70)
```

**Quarterly Drill 2: Offline Backup Recovery**

```python
# tests/quarterly/test_q2_offline_backup_recovery.py

@pytest.mark.quarterly_drill
async def test_offline_backup_recovery_drill():
    """
    Q2 Drill: Test recovery from offline GPG-encrypted backups.

    Scenario: Total AWS outage, must recover from offline backup
    Expected: Keys recovered and PHI decryptable within 1 hour
    RTO Target: <1 hour
    """
    print("\n" + "="*70)
    print("Q2 QUARTERLY DRILL: Offline Backup Recovery")
    print("="*70)

    # 1. Retrieve backup from "safe" (simulated)
    print("\n1️⃣ Retrieving backup from secure storage...")
    backup_dir = Path("/secure/recovery/simulated")
    assert backup_dir.exists(), "Backup storage not accessible"
    print("   ✅ Backup storage accessible")

    # 2. Decrypt GPG backup
    print("\n2️⃣ Decrypting GPG-encrypted backup...")
    start_time = time.time()

    subprocess.run([
        "gpg", "--decrypt",
        "--output", "encryption-key-v1-restored.json",
        str(backup_dir / "encryption-key-v1-backup-20251019.json.gpg")
    ], check=True)

    decrypt_time = time.time() - start_time
    print(f"   ✅ Decrypted in {decrypt_time:.2f}s")

    # 3. Load and verify key
    print("\n3️⃣ Loading restored key...")
    with open("encryption-key-v1-restored.json", "r") as f:
        secret_value = json.load(f)

    key = base64.b64decode(secret_value["encryption_key"])
    assert len(key) == 32
    print("   ✅ Key loaded and validated")

    # 4. Test decryption with restored key
    print("\n4️⃣ Testing decryption with restored key...")
    test_ciphertext = load_test_ciphertext("v1")
    plaintext = decrypt_field(test_ciphertext, key)

    assert plaintext == EXPECTED_PLAINTEXT
    print("   ✅ Decryption successful")

    # 5. Verify all key versions
    print("\n5️⃣ Verifying all key versions...")
    for version in ["v1", "v2", "v3"]:
        # ... (repeat steps 2-4 for each version)
        pass

    total_time = time.time() - start_time

    print("\n" + "="*70)
    print("✅ Q2 DRILL PASSED - Offline backup recovery operational")
    print(f"   Total recovery time: {total_time:.2f}s (target: <3600s)")
    print("="*70)

    # Cleanup
    os.remove("encryption-key-v1-restored.json")
```

**Quarterly Drill 3: Total AWS Outage Simulation**

```python
# tests/quarterly/test_q3_total_aws_outage.py

@pytest.mark.quarterly_drill
async def test_total_aws_outage_simulation():
    """
    Q3 Drill: Simulate complete AWS outage (all regions down).

    Scenario: AWS unavailable, switch to offline backup recovery
    Expected: Application continues with environment variable keys
    RTO Target: <1 hour
    """
    print("\n" + "="*70)
    print("Q3 QUARTERLY DRILL: Total AWS Outage Simulation")
    print("="*70)

    # 1. Simulate AWS outage
    print("\n1️⃣ Simulating total AWS outage...")
    with mock_aws_outage():

        # 2. Verify AWS is unreachable
        print("\n2️⃣ Verifying AWS unavailable...")
        with pytest.raises(ClientError):
            get_encryption_key_version("v1", region="us-east-1")

        print("   ✅ AWS confirmed unavailable")

        # 3. Recover from offline backup
        print("\n3️⃣ Recovering from offline backup...")
        recovered_keys = recover_from_offline_backup()

        # 4. Load keys into environment
        print("\n4️⃣ Loading keys into application...")
        for version, key in recovered_keys.items():
            os.environ[f"ENCRYPTION_KEY_{version.upper()}"] = base64.b64encode(key).decode()

        # 5. Test application with env var keys
        print("\n5️⃣ Testing application with recovered keys...")
        # ... (test CRUD operations with PHI)

        print("   ✅ Application operational with offline keys")

    print("\n" + "="*70)
    print("✅ Q3 DRILL PASSED - Total outage recovery operational")
    print("="*70)
```

**Quarterly Drill 4: Lost Account Access Simulation**

```python
# tests/quarterly/test_q4_lost_account_access.py

@pytest.mark.quarterly_drill
async def test_lost_account_access_simulation():
    """
    Q4 Drill: Simulate lost AWS account access.

    Scenario: AWS credentials invalid, account locked
    Expected: Recover from offline backup, restore to new account
    RTO Target: <4 hours
    """
    print("\n" + "="*70)
    print("Q4 QUARTERLY DRILL: Lost Account Access Simulation")
    print("="*70)

    # 1. Invalidate AWS credentials
    print("\n1️⃣ Simulating lost AWS access...")
    with mock_invalid_aws_credentials():

        # 2. Attempt AWS access (should fail)
        print("\n2️⃣ Verifying AWS access denied...")
        with pytest.raises(ClientError, match="InvalidAccessKeyId"):
            get_encryption_key_version("v1")

        print("   ✅ AWS access confirmed lost")

        # 3. Recover from offline backup
        print("\n3️⃣ Recovering from offline backup...")
        recovered_keys = recover_from_offline_backup()

        # 4. Restore to "new" AWS account
        print("\n4️⃣ Restoring to new AWS account...")
        restore_keys_to_aws(recovered_keys, account_id="NEW_ACCOUNT")

        # 5. Verify restoration
        print("\n5️⃣ Verifying restoration...")
        # ... (test key fetch from new account)

        print("   ✅ Keys restored to new AWS account")

    print("\n" + "="*70)
    print("✅ Q4 DRILL PASSED - Account recovery operational")
    print("="*70)
```

#### Post-Drill Review

- [ ] Document actual RTO/RPO achieved
- [ ] Identify issues or gaps discovered
- [ ] Update procedures based on lessons learned
- [ ] Schedule follow-up actions for issues
- [ ] Generate drill report
- [ ] Schedule next quarter's drill

### Drill Report Template

```markdown
# Quarterly Key Recovery Drill Report

**Quarter**: Q1 2025
**Date**: 2025-01-15
**Drill Type**: Multi-Region Failover
**Participants**: Alice (CTO), Bob (Security Lead), Charlie (DevOps)

## Objectives

- Test automatic failover to replica region (us-west-2)
- Verify RTO <5 minutes
- Validate decryption with failover keys

## Results

✅ **PASS** - All objectives met

- Failover time: 3.2 seconds (target: <5 minutes)
- Decryption successful: 100% (45/45 test records)
- No data loss or corruption

## Issues Discovered

1. **Minor**: CloudWatch alarm didn't trigger (configuration error)
   - Action: Update alarm threshold
   - Owner: Charlie (DevOps)
   - Due: 2025-01-20

## Lessons Learned

- Failover faster than expected (3.2s vs 5min target)
- Documentation accurate and easy to follow
- Team well-trained, no confusion during drill

## Recommendations

1. Add automated failover testing to CI/CD
2. Update RTO target to <10 seconds (currently overprovisioned)
3. Schedule extra drill in Q2 for new team members

## Next Drill

**Date**: 2025-04-15
**Type**: Q2 - Offline Backup Recovery

---

**Report by**: Bob (Security Lead)
**Reviewed by**: Alice (CTO)
**Date**: 2025-01-16
```

---

## Disaster Scenarios

### Scenario Matrix

| Scenario | Likelihood | Impact | RTO | RPO | Recovery Method |
|----------|-----------|--------|-----|-----|----------------|
| Primary region outage | Medium | Low | <5 min | 0 | Multi-region failover |
| Multi-region outage | Low | Medium | <1 hour | 24 hours | Offline backup |
| AWS account loss | Very Low | High | <4 hours | 24 hours | Offline backup + AWS support |
| GPG key loss | Very Low | Critical | N/A | N/A | Prevented (3 copies) |
| Physical safe breach | Very Low | Medium | <1 hour | 24 hours | Bank vault backup |
| All backups destroyed | Extremely Low | Critical | Data loss | N/A | Prevented (3 locations) |

### Communication Plan

**During Recovery Event**:

1. **Incident Commander**: CTO or Security Lead
2. **Communication Channels**:
   - Internal: Slack #security-incidents (priority 1)
   - External: Email to stakeholders (if >1 hour outage)
   - HIPAA Reporting: If PHI at risk of breach

3. **Stakeholder Notifications**:
   - **<15 min**: Internal team only
   - **15-60 min**: Notify leadership, prepare customer communication
   - **>60 min**: Notify affected customers, prepare HIPAA report if required

4. **Status Updates**:
   - Every 30 minutes during active recovery
   - Final all-clear notification

### HIPAA Breach Notification

If encryption keys are compromised or PHI exposed:

**Timeline**:
- **Immediate**: Contain breach, revoke compromised keys
- **Within 60 days**: Notify affected individuals (45 CFR §164.404)
- **Within 60 days**: Notify HHS Office for Civil Rights
- **Without unreasonable delay**: Notify media (if >500 individuals affected)

**Documentation Required**:
- Timeline of events
- Root cause analysis
- PHI affected (which patients, what data)
- Remediation steps taken
- Prevention measures implemented

---

## Troubleshooting

### Issue 1: Multi-Region Replication Not Working

**Symptoms**:
- Replication status shows "Failed" or "Pending"
- Replica regions out of sync

**Diagnosis**:
```bash
# Check replication status
aws secretsmanager describe-secret \
    --region us-east-1 \
    --secret-id pazpaz/encryption-key-v1 \
    --query 'ReplicationStatus'

# Output:
# [
#   {
#     "Region": "us-west-2",
#     "Status": "Failed",
#     "StatusMessage": "Access denied"
#   }
# ]
```

**Solution**:
```bash
# 1. Verify IAM permissions in replica region
aws iam get-role-policy \
    --role-name SecretsManagerReplicationRole \
    --policy-name ReplicationPolicy \
    --region us-west-2

# 2. Re-enable replication
aws secretsmanager remove-regions-from-replication \
    --secret-id pazpaz/encryption-key-v1 \
    --remove-replica-regions us-west-2

aws secretsmanager replicate-secret-to-regions \
    --secret-id pazpaz/encryption-key-v1 \
    --add-replica-regions Region=us-west-2

# 3. Verify replication recovered
aws secretsmanager describe-secret \
    --secret-id pazpaz/encryption-key-v1 \
    --query 'ReplicationStatus[?Region==`us-west-2`]'
```

### Issue 2: GPG Decryption Fails

**Symptoms**:
- `gpg --decrypt` prompts for passphrase, then fails
- Error: "decryption failed: No secret key"

**Diagnosis**:
```bash
# Check if GPG private key is imported
gpg --list-secret-keys security@pazpaz.com

# If empty, private key not imported
```

**Solution**:
```bash
# 1. Retrieve GPG private key from password manager or safe
# 2. Import private key
gpg --import gpg-private-key.asc

# 3. Trust the key
gpg --edit-key security@pazpaz.com
# In GPG prompt:
# gpg> trust
# Your decision? 5 (ultimate trust)
# gpg> quit

# 4. Retry decryption
gpg --decrypt encryption-key-v1-backup.json.gpg
```

### Issue 3: Offline Backup USB Drive Unreadable

**Symptoms**:
- USB drive not mounting
- Filesystem errors

**Solution**:
```bash
# 1. Try different computer/port
# 2. Check filesystem
sudo fsck /dev/disk2s1

# 3. If corrupted, use bank vault backup (Location B)
# 4. Update backup procedures to use higher-quality USB drives
# 5. Consider replacing USB with encrypted SSD for better durability
```

### Issue 4: Restored Keys Don't Decrypt Production Data

**Symptoms**:
- Key restored successfully
- Decryption fails with "Authentication tag mismatch"

**Diagnosis**:
```python
# Verify key matches expected hash
import hashlib
import base64

key_hash = hashlib.sha256(key).hexdigest()
print(f"Restored key hash: {key_hash}")

# Compare with expected hash (stored separately)
expected_hash = "abc123..."  # From secure documentation
assert key_hash == expected_hash
```

**Possible Causes**:
1. **Wrong backup version**: Using v1 backup to decrypt v2 data
2. **Corrupted backup**: Backup file damaged during storage
3. **Wrong GPG key**: Decrypted with wrong GPG private key

**Solution**:
```bash
# 1. Verify backup version matches data
SELECT version FROM sessions WHERE id = 'test-id';
# Result: v2

# Use v2 backup, not v1

# 2. Try backup from different location (Location B)

# 3. Verify GPG key fingerprint
gpg --list-keys security@pazpaz.com
# Compare fingerprint with documented value
```

---

## HIPAA Compliance Notes

### Relevant Requirements

**§164.308(a)(7)(ii)(A) - Data Backup Plan**
- ✅ Daily automated backups of encryption keys
- ✅ Offline backups in secure physical locations
- ✅ Multi-region cloud backups (AWS Secrets Manager)

**§164.308(a)(7)(ii)(B) - Disaster Recovery Plan**
- ✅ Documented recovery procedures for multiple scenarios
- ✅ RTO/RPO targets defined and tested
- ✅ Quarterly recovery drills

**§164.308(a)(7)(ii)(C) - Emergency Mode Operation Plan**
- ✅ Application can operate with offline keys (environment variables)
- ✅ Failover procedures documented and tested

**§164.308(a)(7)(ii)(E) - Testing and Revision Procedures**
- ✅ Quarterly recovery drills
- ✅ Drill reports documenting results and lessons learned
- ✅ Procedures updated based on drill findings

### Audit Trail

All key backup and recovery operations must be logged:

```python
# Audit log format
{
    "event_type": "encryption_key_backup",
    "timestamp": "2025-10-19T10:00:00Z",
    "user_id": "security-team",
    "action": "backup_created",
    "key_version": "v1",
    "backup_location": "fireproof_safe_location_a",
    "backup_hash": "sha256:abc123...",
    "retention_period": "90_days"
}

{
    "event_type": "encryption_key_recovery",
    "timestamp": "2025-10-19T12:00:00Z",
    "user_id": "alice@pazpaz.com",
    "action": "key_restored_from_backup",
    "key_version": "v1",
    "backup_source": "offline_gpg_backup",
    "recovery_reason": "quarterly_drill_q2",
    "recovery_time_seconds": 45
}
```

### Retention Policy

**Encryption Keys**: Retain for 7 years after rotation (HIPAA minimum)
- Active keys: Stored in AWS Secrets Manager + offline backups
- Rotated keys: Archived to AWS S3 Glacier Deep Archive
- Deletion: Secure deletion only after 7-year retention + no dependent PHI

**Backup Files**: Retain for 1 year, then archive
- Daily backups: Keep 30 days in Location A
- Monthly backups: Keep 1 year in Location B
- Annual backups: Keep 7 years in Location C (Glacier)

**Drill Reports**: Retain indefinitely for compliance audit trail

---

## Summary

✅ **Backup Strategy (3 Layers)**:
1. AWS Secrets Manager primary (us-east-1) - automatic backups
2. Multi-region replication (us-west-2, eu-west-1) - <1 second lag
3. Offline GPG-encrypted backups - daily, 3 physical locations

✅ **Recovery Procedures**:
- Multi-region failover: <5 minutes, automatic
- Offline backup recovery: <1 hour, manual
- Total AWS outage: <1 hour, manual
- Lost account access: <4 hours, AWS support + manual

✅ **Quarterly Drills**:
- Q1: Multi-region failover
- Q2: Offline backup recovery
- Q3: Total AWS outage simulation
- Q4: Lost account access simulation

✅ **HIPAA Compliance**:
- Daily backups (§164.308(a)(7)(ii)(A))
- Disaster recovery plan (§164.308(a)(7)(ii)(B))
- Emergency mode operation (§164.308(a)(7)(ii)(C))
- Testing and revision (§164.308(a)(7)(ii)(E))

✅ **Documentation**:
- Comprehensive recovery procedures
- Troubleshooting guides
- Drill checklists and report templates
- Audit trail requirements

---

**Last Updated:** 2025-10-19
**Next Review:** After Q1 2025 drill
**Owner:** Security Team + DevOps
**Emergency Contact:** security@pazpaz.com
