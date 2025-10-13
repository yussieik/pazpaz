# AWS Secrets Manager Setup Guide

**Version:** 1.0
**Date:** 2025-10-12
**Audience:** DevOps, SRE, System Administrators
**Purpose:** Configure AWS Secrets Manager for PazPaz encryption key management

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [AWS Secrets Manager Setup](#aws-secrets-manager-setup)
4. [IAM Policies and Permissions](#iam-policies-and-permissions)
5. [Application Configuration](#application-configuration)
6. [Testing and Validation](#testing-and-validation)
7. [Monitoring and Alerts](#monitoring-and-alerts)
8. [Troubleshooting](#troubleshooting)

---

## Overview

### Why AWS Secrets Manager?

PazPaz uses AWS Secrets Manager for encryption key management in production because it provides:

- **Automatic Key Rotation**: Built-in support for automated key rotation
- **Audit Trail**: AWS CloudTrail logs all secret access
- **Access Control**: Fine-grained IAM policies for who can access keys
- **Secrets Versioning**: Automatic versioning with rollback capability
- **Encryption at Rest**: Keys encrypted with AWS KMS
- **High Availability**: Multi-AZ replication and 99.99% SLA

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Production Environment                  │
│                                                             │
│  ┌───────────────┐         ┌──────────────────────┐       │
│  │   ECS Task    │         │  AWS Secrets Manager  │       │
│  │               │         │                       │       │
│  │  PazPaz API   │────────▶│  pazpaz/encryption-   │       │
│  │               │  IAM    │  key-v1               │       │
│  │  (IAM Role)   │  Role   │                       │       │
│  └───────────────┘         │  (KMS Encrypted)      │       │
│                            └──────────────────────┘       │
│                                     │                       │
│                                     ▼                       │
│                            ┌──────────────────────┐       │
│                            │   AWS CloudTrail     │       │
│                            │   (Audit Logs)       │       │
│                            └──────────────────────┘       │
└─────────────────────────────────────────────────────────────┘

Development Environment:
┌────────────────────────────┐
│  Local Development         │
│                            │
│  .env file                 │
│  ENCRYPTION_MASTER_KEY=... │
│  (Environment Variable)    │
└────────────────────────────┘
```

### Deployment Strategy

| Environment | Key Storage | Fallback |
|-------------|-------------|----------|
| **Local** | Environment variable (`ENCRYPTION_MASTER_KEY`) | N/A |
| **Staging** | AWS Secrets Manager | Environment variable |
| **Production** | AWS Secrets Manager | Environment variable |

**Graceful Fallback**: If AWS Secrets Manager is unavailable (network issue, IAM error), the application falls back to `ENCRYPTION_MASTER_KEY` environment variable to maintain availability.

---

## Prerequisites

### 1. AWS Account Setup

- AWS account with administrative access
- AWS CLI installed and configured
- AWS region selected (default: `us-east-1`)

```bash
# Verify AWS CLI
aws --version
# Expected: aws-cli/2.x.x

# Verify credentials
aws sts get-caller-identity
# Should show your account ID and user/role
```

### 2. Required Permissions

Your AWS user/role needs these permissions to set up Secrets Manager:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:TagResource",
        "kms:CreateKey",
        "kms:DescribeKey",
        "kms:TagResource",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PutRolePolicy"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. Generate Encryption Key

Generate a secure 32-byte (256-bit) encryption key:

```bash
# Method 1: Python (recommended)
python -c 'import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())'

# Method 2: OpenSSL
openssl rand -base64 32

# Expected output (example):
# rT8x9kp3QwE7yLmN2oA5vK1uG4hJ6fD9cB8sZ0tX3iY=
```

**IMPORTANT**: Save this key securely. You'll need it for the next steps.

---

## AWS Secrets Manager Setup

### Step 1: Create KMS Key (Optional but Recommended)

Create a dedicated KMS key for encrypting secrets:

```bash
# Create KMS key
aws kms create-key \
  --description "PazPaz Secrets Manager encryption key" \
  --tags TagKey=Project,TagValue=PazPaz TagKey=Purpose,TagValue=SecretsEncryption \
  --region us-east-1

# Note the KeyId from output (e.g., "12345678-1234-1234-1234-123456789012")
KMS_KEY_ID="your-kms-key-id"

# Create key alias for easy reference
aws kms create-alias \
  --alias-name alias/pazpaz-secrets \
  --target-key-id $KMS_KEY_ID \
  --region us-east-1
```

### Step 2: Create Secret in AWS Secrets Manager

```bash
# Set your encryption key (generated in Prerequisites step 3)
ENCRYPTION_KEY="rT8x9kp3QwE7yLmN2oA5vK1uG4hJ6fD9cB8sZ0tX3iY="

# Create secret
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v1 \
  --description "PazPaz encryption key v1 for PHI/PII data" \
  --secret-string "$ENCRYPTION_KEY" \
  --kms-key-id alias/pazpaz-secrets \
  --tags Key=Project,Value=PazPaz Key=Environment,Value=Production Key=Version,Value=v1 \
  --region us-east-1
```

**Expected Output:**

```json
{
    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:pazpaz/encryption-key-v1-AbCdEf",
    "Name": "pazpaz/encryption-key-v1",
    "VersionId": "12345678-1234-1234-1234-123456789012"
}
```

### Step 3: Verify Secret

```bash
# Retrieve secret to verify
aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key-v1 \
  --region us-east-1 \
  --query SecretString \
  --output text

# Should output your encryption key (base64)
```

### Step 4: Configure Secret Rotation (Optional)

**Note**: Automatic rotation requires a Lambda function. For manual rotation, see [KEY_ROTATION_PROCEDURE.md](KEY_ROTATION_PROCEDURE.md).

```bash
# Enable automatic rotation (requires Lambda function)
aws secretsmanager rotate-secret \
  --secret-id pazpaz/encryption-key-v1 \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789012:function:PazPazKeyRotation \
  --rotation-rules AutomaticallyAfterDays=365 \
  --region us-east-1
```

---

## IAM Policies and Permissions

### Application IAM Role (ECS Task Role)

The PazPaz application needs permission to **read** secrets (but not modify them).

#### Step 1: Create IAM Policy

```bash
# Create policy document
cat > pazpaz-secrets-readonly-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadEncryptionKey",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/encryption-key-*"
      ]
    },
    {
      "Sid": "DecryptWithKMS",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:DescribeKey"
      ],
      "Resource": [
        "arn:aws:kms:us-east-1:*:key/*"
      ],
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "secretsmanager.us-east-1.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create IAM policy
aws iam create-policy \
  --policy-name PazPazSecretsReadOnly \
  --policy-document file://pazpaz-secrets-readonly-policy.json \
  --description "Allow PazPaz application to read encryption keys from Secrets Manager"
```

#### Step 2: Attach Policy to ECS Task Role

```bash
# Attach to existing ECS task role
aws iam attach-role-policy \
  --role-name PazPazECSTaskRole \
  --policy-arn arn:aws:iam::123456789012:policy/PazPazSecretsReadOnly

# Verify attachment
aws iam list-attached-role-policies \
  --role-name PazPazECSTaskRole
```

### DevOps/Admin IAM Policy (Full Access)

For administrators who manage secrets:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:*"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:*:alias/pazpaz-secrets"
    }
  ]
}
```

---

## Application Configuration

### Environment Variables

Update your application environment variables:

#### Production (ECS Task Definition)

```json
{
  "containerDefinitions": [
    {
      "name": "pazpaz-api",
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "AWS_REGION",
          "value": "us-east-1"
        },
        {
          "name": "SECRETS_MANAGER_KEY_NAME",
          "value": "pazpaz/encryption-key-v1"
        }
      ]
    }
  ]
}
```

**IMPORTANT**: Do **NOT** set `ENCRYPTION_MASTER_KEY` in production. The application will fetch the key from AWS Secrets Manager.

#### Staging (Optional Environment Variable Fallback)

```bash
# .env.staging
ENVIRONMENT=staging
AWS_REGION=us-east-1
SECRETS_MANAGER_KEY_NAME=pazpaz/encryption-key-v1

# Optional: Fallback if AWS unavailable
ENCRYPTION_MASTER_KEY=your-fallback-key-here
```

#### Local Development

```bash
# .env
ENVIRONMENT=local

# Use environment variable (no AWS required)
ENCRYPTION_MASTER_KEY=rT8x9kp3QwE7yLmN2oA5vK1uG4hJ6fD9cB8sZ0tX3iY=

# Optional: Test AWS integration locally
# AWS_REGION=us-east-1
# SECRETS_MANAGER_KEY_NAME=pazpaz/encryption-key-v1
```

### Application Code (Already Configured)

The application automatically uses AWS Secrets Manager in `pazpaz.core.config.Settings`:

```python
from pazpaz.core.config import settings

# Automatically fetches from AWS Secrets Manager in production
# Falls back to ENCRYPTION_MASTER_KEY environment variable if AWS unavailable
encryption_key = settings.encryption_key
```

---

## Testing and Validation

### Test 1: Verify IAM Role Permissions

```bash
# Assume the ECS task role (for testing)
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/PazPazECSTaskRole \
  --role-session-name test-session

# Export temporary credentials (from assume-role output)
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."

# Test secret access
aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key-v1 \
  --region us-east-1

# Should succeed and return secret
```

### Test 2: Local Application Test

```bash
# Test application can fetch key from AWS
cd /path/to/pazpaz/backend

# Set environment for AWS testing
export ENVIRONMENT=staging
export AWS_REGION=us-east-1
export SECRETS_MANAGER_KEY_NAME=pazpaz/encryption-key-v1

# Run Python test
python -c "
from pazpaz.core.config import settings
key = settings.encryption_key
print(f'✅ Successfully fetched key: {len(key)} bytes')
"

# Expected output:
# ✅ Successfully fetched key: 32 bytes
```

### Test 3: Fallback to Environment Variable

```bash
# Simulate AWS unavailable (wrong secret name)
export ENVIRONMENT=staging
export SECRETS_MANAGER_KEY_NAME=pazpaz/nonexistent-key
export ENCRYPTION_MASTER_KEY=rT8x9kp3QwE7yLmN2oA5vK1uG4hJ6fD9cB8sZ0tX3iY=

# Run Python test
python -c "
from pazpaz.core.config import settings
key = settings.encryption_key
print(f'✅ Fallback successful: {len(key)} bytes')
"

# Should fall back to environment variable
# Check logs for: "aws_unavailable_using_env_fallback"
```

### Test 4: End-to-End Encryption Test

```bash
# Test encrypt/decrypt with AWS-fetched key
python -c "
from pazpaz.core.config import settings
from pazpaz.utils.encryption import encrypt_field, decrypt_field

key = settings.encryption_key
plaintext = 'Patient has diabetes'

# Encrypt
ciphertext = encrypt_field(plaintext, key)
print(f'✅ Encrypted: {len(ciphertext)} bytes')

# Decrypt
decrypted = decrypt_field(ciphertext, key)
assert decrypted == plaintext, 'Decryption failed!'
print(f'✅ Decrypted: {decrypted}')
"

# Expected:
# ✅ Encrypted: 49 bytes
# ✅ Decrypted: Patient has diabetes
```

---

## Monitoring and Alerts

### CloudWatch Alarms

#### 1. Secret Access Monitoring

Monitor excessive secret access (potential attack):

```bash
# Create CloudWatch metric filter
aws logs put-metric-filter \
  --log-group-name /aws/secretsmanager \
  --filter-name PazPazSecretAccess \
  --filter-pattern '{ $.eventName = "GetSecretValue" && $.requestParameters.secretId = "pazpaz/encryption-key-v1" }' \
  --metric-transformations \
    metricName=EncryptionKeyAccess,metricNamespace=PazPaz/Security,metricValue=1

# Create alarm for excessive access
aws cloudwatch put-metric-alarm \
  --alarm-name PazPazExcessiveKeyAccess \
  --alarm-description "Alert when encryption key accessed >100 times/hour" \
  --metric-name EncryptionKeyAccess \
  --namespace PazPaz/Security \
  --statistic Sum \
  --period 3600 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:security-alerts
```

#### 2. Failed Access Attempts

Alert on unauthorized secret access:

```bash
aws logs put-metric-filter \
  --log-group-name /aws/secretsmanager \
  --filter-name PazPazSecretAccessDenied \
  --filter-pattern '{ $.errorCode = "AccessDeniedException" && $.requestParameters.secretId = "pazpaz/encryption-key-v1" }' \
  --metric-transformations \
    metricName=EncryptionKeyAccessDenied,metricNamespace=PazPaz/Security,metricValue=1

aws cloudwatch put-metric-alarm \
  --alarm-name PazPazUnauthorizedKeyAccess \
  --alarm-description "Alert on any unauthorized key access attempt" \
  --metric-name EncryptionKeyAccessDenied \
  --namespace PazPaz/Security \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:security-alerts
```

### Application Logging

The application logs all encryption key access:

```json
{
  "timestamp": "2025-10-12T10:30:00Z",
  "level": "INFO",
  "event": "encryption_key_fetched_from_aws",
  "secret_id": "pazpaz/encryption-key-v1",
  "version_id": "12345678-1234-1234-1234-123456789012",
  "environment": "production"
}
```

**Log Queries** (CloudWatch Insights):

```sql
-- Count key access by hour
fields @timestamp, event
| filter event = "encryption_key_fetched_from_aws"
| stats count() by bin(@timestamp, 1h)

-- Find fallback usage (AWS unavailable)
fields @timestamp, event, secret_id
| filter event = "aws_unavailable_using_env_fallback"
| sort @timestamp desc
```

---

## Troubleshooting

### Issue 1: "Access Denied" Error

**Error:**

```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling
the GetSecretValue operation: User is not authorized to perform: secretsmanager:GetSecretValue
```

**Cause**: IAM role lacks `secretsmanager:GetSecretValue` permission.

**Solution:**

```bash
# Verify IAM policy attached to role
aws iam list-attached-role-policies --role-name PazPazECSTaskRole

# Attach missing policy
aws iam attach-role-policy \
  --role-name PazPazECSTaskRole \
  --policy-arn arn:aws:iam::123456789012:policy/PazPazSecretsReadOnly
```

### Issue 2: "Secret Not Found"

**Error:**

```
botocore.exceptions.ClientError: An error occurred (ResourceNotFoundException) when calling
the GetSecretValue operation: Secrets Manager can't find the specified secret.
```

**Cause**: Secret name mismatch or wrong region.

**Solution:**

```bash
# List all secrets in region
aws secretsmanager list-secrets --region us-east-1

# Verify secret name matches SECRETS_MANAGER_KEY_NAME env var
echo $SECRETS_MANAGER_KEY_NAME
# Should be: pazpaz/encryption-key-v1

# Create secret if missing (see Step 2)
```

### Issue 3: "KMS Decrypt Error"

**Error:**

```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling
the Decrypt operation: User is not authorized to perform: kms:Decrypt
```

**Cause**: IAM role lacks KMS decrypt permission.

**Solution:**

```bash
# Update IAM policy to include KMS permissions (see IAM Policies section)
# Or use default AWS-managed KMS key for Secrets Manager
```

### Issue 4: Application Falls Back to Environment Variable

**Symptom**: Application logs show `aws_unavailable_using_env_fallback`.

**Causes**:

1. **Network issue**: Application cannot reach AWS Secrets Manager
2. **IAM role not attached**: ECS task missing IAM role
3. **Wrong region**: Secret exists in different region

**Diagnosis:**

```bash
# Check application logs
kubectl logs -l app=pazpaz-api | grep "aws_unavailable"

# Verify ECS task has IAM role
aws ecs describe-task-definition \
  --task-definition pazpaz-api \
  --query 'taskDefinition.taskRoleArn'

# Test network connectivity from container
kubectl exec -it pazpaz-api-pod -- curl https://secretsmanager.us-east-1.amazonaws.com
```

**Solution:**

- Ensure ECS task role is attached
- Verify security group allows outbound HTTPS (443)
- Check VPC endpoint for Secrets Manager (if using private subnets)

### Issue 5: "Key Length Invalid"

**Error:**

```
ValueError: Encryption key from AWS Secrets Manager must be 32 bytes, got 24 bytes
```

**Cause**: Secret contains invalid base64 or wrong key size.

**Solution:**

```bash
# Regenerate valid key
NEW_KEY=$(python -c 'import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())')

# Update secret
aws secretsmanager update-secret \
  --secret-id pazpaz/encryption-key-v1 \
  --secret-string "$NEW_KEY" \
  --region us-east-1
```

---

## Next Steps

- **Key Rotation**: See [KEY_ROTATION_PROCEDURE.md](KEY_ROTATION_PROCEDURE.md)
- **Migration**: See [AWS_SECRETS_MANAGER_MIGRATION.md](AWS_SECRETS_MANAGER_MIGRATION.md)
- **Encryption Usage**: See [ENCRYPTION_USAGE_GUIDE.md](ENCRYPTION_USAGE_GUIDE.md)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-12
**Owner:** DevOps Team
**Reviewers:** Security Team, Backend Team
