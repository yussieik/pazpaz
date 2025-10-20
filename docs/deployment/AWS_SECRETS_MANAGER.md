# AWS Secrets Manager - Comprehensive Guide

**Last Updated:** 2025-10-20
**Status:** Production-Ready
**HIPAA Compliance:** Required

---

## Table of Contents

1. [Overview](#overview)
2. [Security Benefits](#security-benefits)
3. [Prerequisites](#prerequisites)
4. [Secrets Reference](#secrets-reference)
5. [Setup Instructions](#setup-instructions)
6. [IAM Permissions](#iam-permissions)
7. [Multi-Region Replication](#multi-region-replication)
8. [Automatic Rotation](#automatic-rotation)
9. [Application Integration](#application-integration)
10. [Monitoring & Alerts](#monitoring--alerts)
11. [Troubleshooting](#troubleshooting)
12. [HIPAA Compliance](#hipaa-compliance)

---

## Overview

PazPaz uses AWS Secrets Manager to securely store and retrieve sensitive credentials in production and staging environments. This eliminates storing plaintext passwords in `.env` files, which is a **CRITICAL** HIPAA compliance requirement.

### Why AWS Secrets Manager?

**Security Problem:**
- Encryption keys stored in `.env` files can be exposed via git history, backups, logs, or stolen laptops
- Impact: HIPAA violation §164.308(a)(4)(ii)(A) - Access Authorization
- Solution: Centralized secret management with AWS Secrets Manager

**Security Benefits:**
1. **Centralized Management** - All secrets in one auditable location
2. **Access Control** - IAM policies restrict who can fetch secrets
3. **Audit Trail** - CloudTrail logs all `GetSecretValue` API calls
4. **Encryption at Rest** - Secrets encrypted with AWS KMS
5. **Automatic Rotation** - 90-day key rotation (HIPAA requirement)
6. **Multi-Region Replication** - Disaster recovery with failover
7. **No Plaintext Storage** - Keys never written to disk unencrypted

---

## Security Benefits

| Feature | Benefit |
|---------|---------|
| **Centralized Secret Management** | All secrets in one auditable location |
| **IAM Access Control** | Fine-grained permissions via IAM policies |
| **CloudTrail Audit Logs** | Complete record of all secret access |
| **KMS Encryption at Rest** | Secrets encrypted with AES-256 |
| **Automatic Rotation** | 90-day rotation for HIPAA compliance |
| **Multi-Region Replication** | Failover to `us-west-2` for disaster recovery |
| **No Plaintext in Code** | Keys never hardcoded or committed to git |

---

## Prerequisites

Before running these commands:

- [ ] AWS CLI installed and configured (`aws --version`)
- [ ] Admin IAM credentials or sufficient permissions:
  - `secretsmanager:CreateSecret`
  - `secretsmanager:PutSecretValue`
  - `secretsmanager:TagResource`
  - `secretsmanager:ReplicateSecretToRegions`
  - `secretsmanager:RotateSecret`
- [ ] Determine AWS account ID: `aws sts get-caller-identity --query Account --output text`
- [ ] IAM roles created (see [AWS_IAM_ROLES.md](./AWS_IAM_ROLES.md))

---

## Secrets Reference

### Production Secrets Inventory

| Secret Name | Purpose | Format | Rotation | Priority |
|-------------|---------|--------|----------|----------|
| `pazpaz/encryption-key-v2` | PHI encryption master key | Fernet key (44 chars) | Versioned (not rotated) | CRITICAL |
| `pazpaz/encryption-key-v1` | Legacy PHI decryption | Fernet key (44 chars) | Retained until migration | HIGH |
| `pazpaz/jwt-secret` | JWT token signing | Random string (64+ chars) | 90 days | HIGH |
| `pazpaz/database-credentials` | PostgreSQL connection | JSON object | 90 days | CRITICAL |
| `pazpaz/redis-url` | Redis connection | Connection URL | 180 days | MEDIUM |
| `pazpaz/email-credentials` | SMTP email sending | JSON object | 180 days | LOW |

### Secret Naming Convention

**Format:** `pazpaz/{environment}/{secret-type}`

**Examples:**
- Production: `pazpaz/encryption-key-v2`
- Staging: `pazpaz/staging/encryption-key-v2`
- Development: Use `.env` files (not Secrets Manager)

---

## Setup Instructions

### 1. Encryption Master Key (v2)

**Purpose:** AES-256-GCM encryption key for PHI data in database

**CRITICAL:** This key encrypts client names, contact information, session notes, and attachments. Loss of this key = permanent data loss.

```bash
# Generate new encryption key (44-character base64-encoded Fernet key)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v2 \
  --description "PazPaz AES-256-GCM encryption key (version 2)" \
  --secret-string "$ENCRYPTION_KEY" \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Compliance,Value=HIPAA Key=Application,Value=PazPaz

# Verify secret created
aws secretsmanager describe-secret --secret-id pazpaz/encryption-key-v2 --region us-east-1
```

**Migration Note:** If you have existing data encrypted with `pazpaz/encryption-key-v1`, you MUST:
1. Keep `pazpaz/encryption-key-v1` secret active for decryption
2. Update application configuration to use `pazpaz/encryption-key-v2` for NEW encryptions
3. See [Key Rotation Procedure](/docs/security/encryption/KEY_ROTATION_PROCEDURE.md) for full migration steps

**DO NOT** delete `pazpaz/encryption-key-v1` until all historical data has been re-encrypted with v2.

---

### 2. JWT Secret

**Purpose:** Signing key for JWT access tokens (authentication)

```bash
# Generate strong JWT secret (64-byte base64-encoded random key)
JWT_SECRET=$(openssl rand -base64 64)

# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/jwt-secret \
  --description "PazPaz JWT signing key" \
  --secret-string "$JWT_SECRET" \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Compliance,Value=HIPAA Key=Application,Value=PazPaz

# Verify secret created
aws secretsmanager describe-secret --secret-id pazpaz/jwt-secret --region us-east-1
```

**Security Note:** Changing this secret will invalidate all active JWT tokens. Users will need to re-authenticate after rotation.

---

### 3. Database Credentials

**Purpose:** PostgreSQL connection string for RDS instance

**Format:** JSON with connection parameters for structured credential management

```bash
# Generate strong database password (64-character random password)
DB_PASSWORD=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-64)

# Create JSON payload
cat > /tmp/db-credentials.json <<EOF
{
  "username": "pazpaz",
  "password": "$DB_PASSWORD",
  "host": "pazpaz-prod.REPLACE_ME.us-east-1.rds.amazonaws.com",
  "port": 5432,
  "database": "pazpaz",
  "ssl_cert_path": "/etc/ssl/certs/rds-ca-2019-root.pem"
}
EOF

# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/database-credentials \
  --description "PazPaz PostgreSQL connection credentials" \
  --secret-string file:///tmp/db-credentials.json \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Compliance,Value=HIPAA Key=Application,Value=PazPaz

# Clean up temporary file (never commit to git!)
rm /tmp/db-credentials.json

# Verify secret created
aws secretsmanager describe-secret --secret-id pazpaz/database-credentials --region us-east-1
```

**Alternative Format (Connection URL):**

If you prefer a single connection URL instead of JSON:

```bash
# Generate database password
DB_PASSWORD=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-64)

# Create connection URL
DATABASE_URL="postgresql+asyncpg://pazpaz:$DB_PASSWORD@pazpaz-prod.REPLACE_ME.us-east-1.rds.amazonaws.com:5432/pazpaz?ssl=require"

# Create secret
aws secretsmanager create-secret \
  --name pazpaz/database-url \
  --description "PazPaz PostgreSQL connection URL" \
  --secret-string "$DATABASE_URL" \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Compliance,Value=HIPAA Key=Application,Value=PazPaz
```

**Note:** The application supports both formats. JSON format is recommended for structured credential management and easier rotation.

---

### 4. Redis Credentials

**Purpose:** Redis connection string for session cache and rate limiting

```bash
# Generate strong Redis password (64-character random password)
REDIS_PASSWORD=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-64)

# Create Redis URL
# Replace HOST with your ElastiCache endpoint (e.g., "pazpaz-redis.abc123.cache.amazonaws.com")
REDIS_URL="redis://:$REDIS_PASSWORD@pazpaz-redis.REPLACE_ME.cache.amazonaws.com:6379/0"

# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/redis-url \
  --description "PazPaz Redis connection URL with authentication" \
  --secret-string "$REDIS_URL" \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Compliance,Value=HIPAA Key=Application,Value=PazPaz

# Verify secret created
aws secretsmanager describe-secret --secret-id pazpaz/redis-url --region us-east-1
```

---

### 5. S3/Storage Credentials

**Purpose:** S3 access credentials for file attachments (session photos, PDFs)

**IMPORTANT:** For production, use **IAM roles** instead of access keys when possible (see [AWS_IAM_ROLES.md](./AWS_IAM_ROLES.md)).

If IAM roles are not available (e.g., on-premises deployment):

```bash
# Create IAM user for S3 access
aws iam create-user --user-name pazpaz-s3-prod

# Create access key
aws iam create-access-key --user-name pazpaz-s3-prod
# Save output: AccessKeyId and SecretAccessKey

# Store credentials in Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/s3-credentials \
  --description "S3 credentials for PazPaz production attachments" \
  --secret-string '{
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }' \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Application,Value=PazPaz
```

**Best Practice:** Use IAM roles attached to EC2/ECS instead. See [AWS_IAM_ROLES.md](./AWS_IAM_ROLES.md) for configuration.

---

### 6. Email Credentials (Optional)

**Purpose:** SMTP credentials for sending email notifications

```bash
# Create email credentials secret (if using SMTP)
aws secretsmanager create-secret \
  --name pazpaz/email-credentials \
  --description "SMTP credentials for PazPaz email notifications" \
  --secret-string '{
    "username": "smtp-username",
    "password": "smtp-password",
    "smtp_host": "smtp.example.com",
    "smtp_port": 587
  }' \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Application,Value=PazPaz
```

---

## IAM Permissions

### Application Task Role Policy

The application running in ECS needs permission to read secrets. Add this policy to the `pazpaz-backend-task-role` IAM role.

**IAM Policy:** `pazpaz-backend-secrets-access`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/encryption-key-v2-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/encryption-key-v1-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/jwt-secret-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/database-credentials-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/database-url-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/redis-url-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/s3-credentials-*",
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/email-credentials-*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    }
  ]
}
```

**Apply IAM Policy:**

```bash
# Get your AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create policy document with account ID replaced
cat > /tmp/secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/encryption-key-v2-*",
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/encryption-key-v1-*",
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/jwt-secret-*",
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/database-credentials-*",
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/database-url-*",
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/redis-url-*",
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/s3-credentials-*",
        "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT_ID}:secret:pazpaz/email-credentials-*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    }
  ]
}
EOF

# Attach policy to task role
aws iam put-role-policy \
  --role-name pazpaz-backend-task-role \
  --policy-name pazpaz-backend-secrets-access \
  --policy-document file:///tmp/secrets-policy.json

# Clean up
rm /tmp/secrets-policy.json

# Verify policy attached
aws iam get-role-policy \
  --role-name pazpaz-backend-task-role \
  --policy-name pazpaz-backend-secrets-access
```

**Security Features:**
- **Least Privilege:** Only grants access to `pazpaz/*` secrets (wildcards allowed for version suffixes)
- **Region Restriction:** Secrets Manager access limited to `us-east-1`
- **Explicit Deny for Write:** No `PutSecretValue` or `DeleteSecret` permissions (application cannot modify secrets)
- **Audit Trail:** All `GetSecretValue` calls logged to CloudTrail

---

## Multi-Region Replication

Enable cross-region replication for disaster recovery. If `us-east-1` fails, the application can failover to `us-west-2`.

### Replicate All Secrets

```bash
# Replicate all PazPaz secrets to us-west-2
for secret in \
  pazpaz/encryption-key-v2 \
  pazpaz/encryption-key-v1 \
  pazpaz/jwt-secret \
  pazpaz/database-credentials \
  pazpaz/redis-url \
  pazpaz/s3-credentials; do

  echo "Replicating $secret to us-west-2..."

  aws secretsmanager replicate-secret-to-regions \
    --secret-id "$secret" \
    --add-replica-regions Region=us-west-2 \
    --region us-east-1

  # Wait for replication to complete
  sleep 2
done

echo "Replication complete. Verify replication status:"
aws secretsmanager describe-secret \
  --secret-id pazpaz/encryption-key-v2 \
  --region us-east-1 \
  --query 'ReplicationStatus'
```

**Replication Lag:** Typically <1 minute. Replication is asynchronous.

### Disaster Recovery Test

```bash
# Fetch secret from replica region (simulates failover)
aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key-v2 \
  --region us-west-2 \
  --query 'SecretString' \
  --output text
```

### Failover Configuration

Update application configuration to support multi-region failover:

```python
# backend/src/pazpaz/core/config.py
aws_region: str = Field(default="us-east-1", description="Primary AWS region")
aws_region_failover: str = Field(default="us-west-2", description="Failover AWS region")
```

---

## Automatic Rotation

### Encryption Key Rotation

**IMPORTANT:** Encryption keys use **versioning**, not rotation. Do NOT enable automatic rotation for encryption keys.

**Why Versioning Instead of Rotation:**
- Rotating encryption keys breaks decryption of historical data
- Versioned keys allow:
  - New data encrypted with v2
  - Old data decrypted with v1
  - Gradual migration without downtime

**Create New Version Manually:**

```bash
# Generate new encryption key version (v3)
NEW_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create new version as separate secret
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v3 \
  --description "PazPaz AES-256-GCM encryption key (version 3)" \
  --secret-string "$NEW_KEY" \
  --region us-east-1 \
  --tags Key=Environment,Value=production Key=Compliance,Value=HIPAA Key=Application,Value=PazPaz

# Update application to use v3 for NEW encryptions (see KEY_ROTATION_PROCEDURE.md)
```

---

### JWT Secret Rotation

Enable automatic rotation for JWT secrets (90-day HIPAA requirement).

**Prerequisite:** Create Lambda function for JWT secret rotation (see [AWS Lambda Rotation Functions](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets-lambda-function.html))

**Enable Rotation:**

```bash
# Enable automatic rotation (90 days)
aws secretsmanager rotate-secret \
  --secret-id pazpaz/jwt-secret \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:ACCOUNT_ID:function:pazpaz-jwt-rotation \
  --rotation-rules AutomaticallyAfterDays=90 \
  --region us-east-1

# Verify rotation enabled
aws secretsmanager describe-secret \
  --secret-id pazpaz/jwt-secret \
  --region us-east-1 \
  --query 'RotationEnabled'
```

**Rotation Impact:**
- All active JWT tokens invalidated
- Users must re-authenticate
- Schedule rotation during low-traffic periods (e.g., 3 AM Sunday)

---

### Database Password Rotation

Enable automatic rotation for database credentials (90-day HIPAA requirement).

**Prerequisite:** RDS must support IAM database authentication OR use AWS-managed rotation Lambda

**Enable Rotation (RDS PostgreSQL):**

```bash
# Enable automatic rotation (90 days)
aws secretsmanager rotate-secret \
  --secret-id pazpaz/database-credentials \
  --rotation-lambda-arn arn:aws:serverlessrepo:us-east-1:297356227924:applications/SecretsManagerRDSPostgreSQLRotationSingleUser \
  --rotation-rules AutomaticallyAfterDays=90 \
  --region us-east-1

# Verify rotation enabled
aws secretsmanager describe-secret \
  --secret-id pazpaz/database-credentials \
  --region us-east-1 \
  --query 'RotationEnabled'
```

**Rotation Process:**
1. Lambda creates new password
2. Lambda updates RDS user password
3. Lambda updates secret in Secrets Manager
4. Application uses new password on next connection (automatic reconnect)

**No Downtime:** Connection pooling handles rotation transparently.

---

## Application Integration

The PazPaz backend already has AWS Secrets Manager integration implemented in `backend/src/pazpaz/utils/secrets_manager.py`.

**No Code Changes Required** — The application automatically fetches secrets from AWS Secrets Manager in production.

### Environment Configuration

Set these environment variables in ECS task definition:

```bash
ENVIRONMENT=production        # Triggers AWS Secrets Manager usage
AWS_REGION=us-east-1          # Primary region
USE_AWS_SECRETS=true          # Optional: Explicitly enable Secrets Manager (already default in production)
```

### Secret Naming Configuration

If you want to customize secret names (e.g., for staging vs. production):

```bash
# Override default secret names in ECS task definition
SECRETS_MANAGER_KEY_NAME=pazpaz/encryption-key-v2         # Encryption key secret name
DB_SECRETS_MANAGER_KEY_NAME=pazpaz/database-credentials   # Database credentials secret name
```

### Application Startup Verification

The application verifies Secrets Manager integration at startup:

```python
# backend/src/pazpaz/main.py - Startup Event Handler
@app.on_event("startup")
async def verify_secrets_manager():
    """Verify AWS Secrets Manager integration in production."""
    if settings.environment in ("production", "staging"):
        logger.info(
            "encryption_key_source",
            source="aws_secrets_manager",
            secret_name=settings.secrets_manager_key_name,
            region=settings.aws_region,
        )

        # Test fetch encryption key (cached for subsequent calls)
        try:
            key = settings.encryption_key
            logger.info("encryption_key_loaded_successfully", key_length=len(key))
        except Exception as e:
            logger.error("encryption_key_load_failed", error=str(e))
            raise RuntimeError(
                "Failed to load encryption key from AWS Secrets Manager. "
                "Verify IAM permissions and secret exists."
            )
```

**Expected Startup Logs (Production):**

```json
{
  "event": "encryption_key_source",
  "source": "aws_secrets_manager",
  "secret_name": "pazpaz/encryption-key-v2",
  "region": "us-east-1"
}
{
  "event": "encryption_key_loaded_successfully",
  "key_length": 32
}
```

---

## Monitoring & Alerts

### CloudWatch Alarms for Rotation Failures

Monitor secret rotation failures to ensure HIPAA compliance.

```bash
# Create CloudWatch alarm for rotation failures
aws cloudwatch put-metric-alarm \
  --alarm-name pazpaz-secrets-rotation-failure \
  --alarm-description "Alert when secret rotation fails (HIPAA compliance risk)" \
  --metric-name RotationFailed \
  --namespace AWS/SecretsManager \
  --statistic Sum \
  --period 3600 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:pazpaz-critical-alerts
```

---

### CloudTrail Monitoring for Unauthorized Access

Enable CloudTrail logging for Secrets Manager API calls.

```bash
# Create CloudTrail trail (if not exists)
aws cloudtrail create-trail \
  --name pazpaz-secrets-audit \
  --s3-bucket-name pazpaz-cloudtrail-logs-ACCOUNT_ID \
  --is-multi-region-trail \
  --enable-log-file-validation

# Start logging
aws cloudtrail start-logging --name pazpaz-secrets-audit

# Create CloudWatch log group for CloudTrail events
aws logs create-log-group --log-group-name /aws/cloudtrail/pazpaz-secrets

# Create metric filter for unauthorized GetSecretValue attempts
aws logs put-metric-filter \
  --log-group-name /aws/cloudtrail/pazpaz-secrets \
  --filter-name UnauthorizedSecretsAccess \
  --filter-pattern '{ ($.errorCode = "AccessDenied") && ($.eventName = "GetSecretValue") }' \
  --metric-transformations \
    metricName=UnauthorizedSecretsAccess,metricNamespace=PazPaz/Security,metricValue=1

# Create alarm for unauthorized access attempts
aws cloudwatch put-metric-alarm \
  --alarm-name pazpaz-unauthorized-secrets-access \
  --alarm-description "Alert on unauthorized Secrets Manager access attempts" \
  --metric-name UnauthorizedSecretsAccess \
  --namespace PazPaz/Security \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 3 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:pazpaz-security-alerts
```

---

## Troubleshooting

### Error: "ResourceNotFoundException: Secrets Manager can't find the specified secret"

**Cause:** Secret does not exist in Secrets Manager or wrong secret name.

**Solution:**
1. Verify secret exists:
   ```bash
   aws secretsmanager describe-secret --secret-id pazpaz/encryption-key-v2 --region us-east-1
   ```
2. Check application configuration:
   ```bash
   # Verify SECRETS_MANAGER_KEY_NAME matches actual secret name
   echo $SECRETS_MANAGER_KEY_NAME
   ```
3. Verify region matches:
   ```bash
   # Secret must be in same region as application
   echo $AWS_REGION
   ```

---

### Error: "AccessDeniedException: User is not authorized to perform: secretsmanager:GetSecretValue"

**Cause:** IAM role lacks permission to read secret.

**Solution:**
1. Verify IAM role has Secrets Manager policy:
   ```bash
   aws iam get-role-policy \
     --role-name pazpaz-backend-task-role \
     --policy-name pazpaz-backend-secrets-access
   ```
2. Check resource ARN includes wildcard suffix:
   ```json
   "Resource": [
     "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/encryption-key-v2-*"
   ]
   ```
   **Note:** The `-*` suffix is required because Secrets Manager appends a random string to ARNs.

3. Verify IAM role is attached to ECS task:
   ```bash
   aws ecs describe-task-definition \
     --task-definition pazpaz-backend \
     --query 'taskDefinition.taskRoleArn'
   ```

---

### Error: "InvalidRequestException: You can't perform this operation on the secret because it is currently being rotated"

**Cause:** Rotation in progress; secret temporarily unavailable.

**Solution:**
- Wait 1-2 minutes for rotation to complete
- Application automatically retries failed secret fetches
- No manual intervention required

---

### Error: Application falls back to environment variable in production

**Symptom:** Logs show `aws_unavailable_using_env_fallback` in production.

**Cause:** AWS Secrets Manager unavailable or IAM permissions issue.

**Solution:**
1. Check application logs for specific AWS error:
   ```bash
   aws logs tail /ecs/pazpaz-backend --follow | grep secret
   ```
2. Verify IAM role attached to ECS task
3. Test secret access manually:
   ```bash
   aws secretsmanager get-secret-value --secret-id pazpaz/encryption-key-v2 --region us-east-1
   ```

---

## HIPAA Compliance

| HIPAA Requirement | How AWS Secrets Manager Helps |
|-------------------|-------------------------------|
| §164.308(a)(4)(ii)(A) - Access Authorization | IAM policies enforce least privilege access to secrets |
| §164.312(a)(2)(iv) - Encryption at Rest | Secrets encrypted with AWS KMS (AES-256) |
| §164.312(e)(1) - Transmission Security | Secrets fetched via HTTPS (TLS 1.2+) |
| §164.312(b) - Audit Controls | CloudTrail logs all secret access events |
| §164.308(a)(3)(ii)(A) - Authorization/Supervision | IAM role-based access control |
| §164.308(a)(4)(ii)(B) - Access Modification | Centralized IAM policy updates |

**Compliance Benefits:**
- ✅ Centralized secret management (single audit point)
- ✅ Automatic rotation (90-day HIPAA requirement)
- ✅ Comprehensive audit trail (who accessed what, when)
- ✅ No secrets in version control (eliminates git history exposure)
- ✅ Encryption at rest (AWS KMS AES-256)
- ✅ Encryption in transit (TLS 1.2+ for API calls)

---

## References

### AWS Documentation
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [AWS Secrets Manager Rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [IAM Policies for Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/auth-and-access.html)

### PazPaz Documentation
- [AWS IAM Roles Guide](./AWS_IAM_ROLES.md)
- [Production Deployment Checklist](./PRODUCTION_DEPLOYMENT_CHECKLIST.md)
- [Infrastructure Security Checklist](./INFRASTRUCTURE_SECURITY_CHECKLIST.md)

---

**Last Updated:** 2025-10-20
**Status:** Production-Ready
**HIPAA Compliance:** ✅ Required
