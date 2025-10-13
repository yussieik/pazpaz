# AWS Secrets Manager Migration Guide

**Version:** 1.0
**Date:** 2025-10-12
**Audience:** DevOps, SRE, Database Administrators
**Purpose:** Migrate encryption key from environment variables to AWS Secrets Manager

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Migration Checklist](#pre-migration-checklist)
3. [Migration Procedure](#migration-procedure)
4. [Validation and Testing](#validation-and-testing)
5. [Rollback Plan](#rollback-plan)
6. [Post-Migration](#post-migration)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Migration Goals

This guide covers migrating from environment variable-based encryption key storage to AWS Secrets Manager for production deployments.

**Before Migration:**
```
┌─────────────────┐
│  ECS Task       │
│                 │
│  Environment:   │
│  ENCRYPTION_    │
│  MASTER_KEY=... │
│  (Plaintext)    │
└─────────────────┘
```

**After Migration:**
```
┌─────────────────┐         ┌──────────────────────┐
│  ECS Task       │         │ AWS Secrets Manager  │
│                 │         │                      │
│  (IAM Role) ────┼────────▶│ pazpaz/encryption-   │
│                 │         │ key-v1               │
│                 │         │ (KMS Encrypted)      │
└─────────────────┘         └──────────────────────┘
```

### Benefits of Migration

1. **Enhanced Security**
   - Keys encrypted at rest with AWS KMS
   - No plaintext keys in environment variables
   - Fine-grained access control via IAM

2. **Audit Trail**
   - CloudTrail logs all key access
   - Track who accessed keys and when
   - Compliance reporting for HIPAA

3. **Key Rotation**
   - Automated key rotation capability
   - Versioned secrets with rollback
   - Zero-downtime rotation support

4. **Availability**
   - Multi-AZ replication (99.99% SLA)
   - Automatic failover
   - Graceful fallback to environment variable

### Migration Timeline

**Zero-Downtime Migration** (recommended):
```
Day 0:  Pre-migration preparation and testing
Day 1:  Deploy dual-mode application (AWS + env var fallback)
Day 2:  Validate AWS Secrets Manager access
Day 3:  Remove environment variable (production only)
```

**Estimated Duration**: 3 days (with 1 day buffer for issues)
**Downtime**: None (graceful fallback ensures availability)

---

## Pre-Migration Checklist

### 1. Inventory Current Encryption Keys

**Step 1**: Identify all environments using encryption keys:

```bash
# List all ECS task definitions
aws ecs list-task-definitions --family-prefix pazpaz

# Extract encryption keys from each environment
for env in production staging; do
  echo "=== $env ==="
  aws ecs describe-task-definition \
    --task-definition pazpaz-api-$env \
    --query 'taskDefinition.containerDefinitions[0].environment[?name==`ENCRYPTION_MASTER_KEY`].value' \
    --output text
done
```

**Step 2**: Backup current encryption keys:

```bash
# Export current production key
CURRENT_KEY=$(aws ecs describe-task-definition \
  --task-definition pazpaz-api-production \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`ENCRYPTION_MASTER_KEY`].value' \
  --output text)

# Encrypt and store securely
echo "$CURRENT_KEY" | gpg --encrypt --recipient security@pazpaz.com > \
  /secure/backups/encryption-key-production-$(date +%Y%m%d).gpg

# Verify backup
gpg --decrypt /secure/backups/encryption-key-production-*.gpg
```

### 2. Verify AWS Secrets Manager Setup

**Prerequisites** (from [AWS_SECRETS_MANAGER_SETUP.md](AWS_SECRETS_MANAGER_SETUP.md)):

- [ ] AWS Secrets Manager secret created: `pazpaz/encryption-key-v1`
- [ ] KMS key created (optional): `alias/pazpaz-secrets`
- [ ] IAM policy created: `PazPazSecretsReadOnly`
- [ ] IAM policy attached to ECS task role
- [ ] CloudWatch alarms configured for monitoring

**Verification:**

```bash
# Verify secret exists
aws secretsmanager describe-secret \
  --secret-id pazpaz/encryption-key-v1 \
  --region us-east-1

# Verify IAM policy attached
aws iam list-attached-role-policies \
  --role-name PazPazECSTaskRole | grep PazPazSecretsReadOnly
```

### 3. Test in Staging Environment

**CRITICAL**: Always test in staging before production migration.

```bash
# Step 1: Deploy staging with AWS Secrets Manager
# (Keep environment variable as fallback)

# Step 2: Verify staging application can access AWS secret
aws ecs run-task \
  --cluster pazpaz-staging \
  --task-definition pazpaz-api-staging \
  --count 1 \
  --launch-type FARGATE

# Step 3: Check logs for successful key fetch
aws logs tail /aws/ecs/pazpaz-api-staging --follow | grep "encryption_key"

# Expected log:
# {"event": "encryption_key_fetched_from_aws", "secret_id": "pazpaz/encryption-key-v1"}
```

### 4. Communication Plan

**Notify stakeholders 3 days before migration:**

```
Subject: Production Migration - AWS Secrets Manager (Zero Downtime)

Team,

We will migrate encryption key storage from environment variables to AWS Secrets
Manager on [DATE]. This is a zero-downtime operation with automatic fallback.

Timeline:
- [DATE 9:00 AM]: Deploy dual-mode application (AWS + env var fallback)
- [DATE 10:00 AM]: Validate AWS access and monitoring
- [DATE 11:00 AM]: Remove environment variable (if validation passes)

Expected impact: None (application maintains fallback to environment variable)

Rollback plan: Instant rollback available by reverting ECS task definition

Point of contact: [Name], [Email], [Phone]
```

---

## Migration Procedure

### Phase 1: Create Secret in AWS Secrets Manager

**Step 1**: Migrate production encryption key to AWS Secrets Manager

```bash
# Export current production key
CURRENT_PROD_KEY=$(aws ecs describe-task-definition \
  --task-definition pazpaz-api-production \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`ENCRYPTION_MASTER_KEY`].value' \
  --output text)

# Verify key is valid (32 bytes)
python -c "import base64; key = base64.b64decode('$CURRENT_PROD_KEY'); print(f'Key length: {len(key)} bytes')"
# Expected: Key length: 32 bytes

# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v1 \
  --description "PazPaz production encryption key (migrated from env var)" \
  --secret-string "$CURRENT_PROD_KEY" \
  --kms-key-id alias/pazpaz-secrets \
  --tags Key=Environment,Value=Production Key=MigratedFrom,Value=EnvironmentVariable \
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

**Step 2**: Verify secret matches current environment variable

```bash
# Fetch from AWS Secrets Manager
AWS_KEY=$(aws secretsmanager get-secret-value \
  --secret-id pazpaz/encryption-key-v1 \
  --region us-east-1 \
  --query SecretString \
  --output text)

# Compare with current environment variable
if [ "$CURRENT_PROD_KEY" = "$AWS_KEY" ]; then
  echo "✅ Keys match - migration safe to proceed"
else
  echo "❌ Keys DO NOT match - DO NOT PROCEED"
  exit 1
fi
```

### Phase 2: Deploy Dual-Mode Application

**Step 1**: Update ECS task definition (keep environment variable as fallback)

```json
{
  "family": "pazpaz-api-production",
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
        },
        {
          "name": "ENCRYPTION_MASTER_KEY",
          "value": "your-current-key-here"
        }
      ]
    }
  ]
}
```

**IMPORTANT**: Keep `ENCRYPTION_MASTER_KEY` during initial deployment for fallback.

**Step 2**: Register new task definition

```bash
# Create updated task definition
aws ecs register-task-definition \
  --cli-input-json file://pazpaz-api-production-dual-mode.json

# Note the new revision number
NEW_REVISION=123
```

**Step 3**: Update ECS service (zero-downtime deployment)

```bash
# Update service to use new task definition
aws ecs update-service \
  --cluster pazpaz-production \
  --service pazpaz-api \
  --task-definition pazpaz-api-production:$NEW_REVISION \
  --force-new-deployment

# Monitor deployment
aws ecs wait services-stable \
  --cluster pazpaz-production \
  --services pazpaz-api

# Check rollout status
aws ecs describe-services \
  --cluster pazpaz-production \
  --services pazpaz-api \
  --query 'services[0].deployments'
```

**Expected Output** (successful deployment):

```json
[
  {
    "status": "PRIMARY",
    "taskDefinition": "pazpaz-api-production:123",
    "desiredCount": 2,
    "runningCount": 2
  }
]
```

### Phase 3: Validate AWS Secrets Manager Access

**Step 1**: Check application logs for successful AWS fetch

```bash
# Tail application logs
aws logs tail /aws/ecs/pazpaz-api-production --follow | grep "encryption_key"

# Expected log entries:
# {"event": "encryption_key_fetched_from_aws", "secret_id": "pazpaz/encryption-key-v1", "version_id": "..."}
```

**Step 2**: Verify CloudTrail logs

```bash
# Check CloudTrail for GetSecretValue events
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
  --region us-east-1 \
  --max-results 10

# Filter for pazpaz secret
# Should show recent GetSecretValue calls from ECS task role
```

**Step 3**: Test end-to-end encryption

```bash
# Create a test client via API
curl -X POST https://api.pazpaz.com/api/v1/clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "MigrationTest",
    "last_name": "User",
    "email": "test@example.com",
    "consent_status": true
  }'

# Verify encrypted data in database
psql -h db-host -U pazpaz -c \
  "SELECT first_name FROM clients WHERE last_name = 'User';"

# Expected: Binary/encrypted data (not plaintext "MigrationTest")

# Retrieve via API (should decrypt correctly)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.pazpaz.com/api/v1/clients/$CLIENT_ID

# Expected: {"first_name": "MigrationTest", ...}
```

**Step 4**: Monitor for 24 hours

```bash
# Monitor error rates
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=pazpaz-api \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average

# Check for any fallback to environment variable
aws logs filter-pattern /aws/ecs/pazpaz-api-production \
  --filter-pattern "aws_unavailable_using_env_fallback" \
  --start-time -24h

# Expected: No results (AWS should be working)
```

### Phase 4: Remove Environment Variable (Production Only)

**ONLY proceed if validation passes (no errors for 24+ hours)**

**Step 1**: Create new task definition without environment variable

```json
{
  "family": "pazpaz-api-production",
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

**Note**: `ENCRYPTION_MASTER_KEY` is now removed.

**Step 2**: Deploy updated task definition

```bash
# Register new task definition
aws ecs register-task-definition \
  --cli-input-json file://pazpaz-api-production-aws-only.json

FINAL_REVISION=124

# Update service
aws ecs update-service \
  --cluster pazpaz-production \
  --service pazpaz-api \
  --task-definition pazpaz-api-production:$FINAL_REVISION \
  --force-new-deployment

# Monitor deployment
aws ecs wait services-stable \
  --cluster pazpaz-production \
  --services pazpaz-api
```

**Step 3**: Final validation

```bash
# Verify application still works
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.pazpaz.com/api/v1/health

# Expected: {"status": "healthy"}

# Check logs for AWS access only (no fallback)
aws logs tail /aws/ecs/pazpaz-api-production --follow | grep "encryption_key"

# Expected: Only "encryption_key_fetched_from_aws" (no "env_fallback")
```

---

## Validation and Testing

### Functional Tests

**Test 1**: Create encrypted record

```bash
# Create client with encrypted PII
curl -X POST https://api.pazpaz.com/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name":"EncryptTest","last_name":"User","consent_status":true}'

# Expected: 201 Created
```

**Test 2**: Read encrypted record

```bash
# Read client (triggers decryption)
curl -H "Authorization: Bearer $TOKEN" \
  https://api.pazpaz.com/api/v1/clients/$CLIENT_ID

# Expected: {"first_name": "EncryptTest", ...}
```

**Test 3**: Update encrypted record

```bash
# Update client
curl -X PATCH https://api.pazpaz.com/api/v1/clients/$CLIENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name":"UpdatedName"}'

# Expected: 200 OK
```

### Performance Tests

**Benchmark key fetch latency:**

```bash
# Measure AWS Secrets Manager latency
time curl -H "Authorization: Bearer $TOKEN" \
  https://api.pazpaz.com/api/v1/health

# Expected: <150ms (p95 target)
# Note: First request may be slower (key fetch), subsequent requests cached
```

### Security Tests

**Test 1**: Verify CloudTrail audit logs

```bash
# Check for GetSecretValue events
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
  --region us-east-1

# Verify events include:
# - eventTime (when)
# - userIdentity.principalId (who - ECS task role)
# - requestParameters.secretId (which secret)
```

**Test 2**: Verify IAM permissions

```bash
# Attempt to modify secret (should fail with application role)
aws secretsmanager update-secret \
  --secret-id pazpaz/encryption-key-v1 \
  --secret-string "invalid-key"

# Expected: AccessDeniedException (application can only READ, not UPDATE)
```

---

## Rollback Plan

### Scenario 1: AWS Secrets Manager Unavailable

**Symptom**: Application logs show `aws_unavailable_using_env_fallback`

**Action**: No rollback needed - graceful fallback is working as designed.

**Monitor**: Investigate root cause (IAM permissions, network, AWS service issue)

### Scenario 2: Application Cannot Start

**Symptom**: ECS tasks fail health checks, container exits with error

**Rollback Steps**:

```bash
# Step 1: Revert to previous task definition
PREVIOUS_REVISION=122  # Before migration

aws ecs update-service \
  --cluster pazpaz-production \
  --service pazpaz-api \
  --task-definition pazpaz-api-production:$PREVIOUS_REVISION \
  --force-new-deployment

# Step 2: Wait for rollback
aws ecs wait services-stable \
  --cluster pazpaz-production \
  --services pazpaz-api

# Step 3: Verify service health
curl https://api.pazpaz.com/api/v1/health
```

**Estimated Rollback Time**: 5-10 minutes (ECS rolling update)

### Scenario 3: Data Corruption Detected

**Symptom**: Decryption errors, corrupted client data

**CRITICAL Rollback**:

```bash
# Step 1: Immediate service stop
aws ecs update-service \
  --cluster pazpaz-production \
  --service pazpaz-api \
  --desired-count 0

# Step 2: Restore from database backup
pg_restore -h db-host -U pazpaz -d pazpaz \
  /backups/pazpaz-backup-$(date +%Y%m%d).dump

# Step 3: Revert to previous task definition
aws ecs update-service \
  --cluster pazpaz-production \
  --service pazpaz-api \
  --task-definition pazpaz-api-production:$PREVIOUS_REVISION \
  --desired-count 2

# Step 4: Investigate root cause before retrying migration
```

---

## Post-Migration

### 1. Update Documentation

**Update internal runbooks:**

- [ ] Remove references to environment variable key storage
- [ ] Update disaster recovery procedures
- [ ] Document AWS Secrets Manager access for on-call

**Update compliance docs:**

- [ ] HIPAA compliance report (encryption key management)
- [ ] Security audit documentation
- [ ] Key rotation schedule

### 2. Clean Up Old Keys

**Staging/Development** (keep environment variable for local development):

```bash
# Staging can keep env var as fallback
# Development always uses env var (no AWS required)
```

**Production** (remove environment variable after 7 days):

```bash
# After 7 days of stable operation, remove env var completely
# This is already done in Phase 4 above
```

### 3. Schedule Key Rotation

**Set up annual key rotation** (see [KEY_ROTATION_PROCEDURE.md](KEY_ROTATION_PROCEDURE.md)):

```bash
# Create calendar event
# Subject: Annual Encryption Key Rotation
# Date: [1 year from migration date]
# Description: Rotate pazpaz/encryption-key-v1 to v2 per HIPAA compliance
```

### 4. Document Migration in Audit Log

**Record migration event:**

```sql
-- Insert migration record
INSERT INTO key_rotation_audit (
  rotation_date,
  old_key_version,
  new_key_version,
  rotation_type,
  initiated_by,
  notes
) VALUES (
  NOW(),
  'env-var',
  'aws-secrets-manager-v1',
  'migration',
  'devops@pazpaz.com',
  'Migrated from environment variable to AWS Secrets Manager'
);
```

---

## Troubleshooting

### Issue 1: "Access Denied" During Migration

**Error:**

```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException)
```

**Solution:**

```bash
# Verify IAM policy attached
aws iam list-attached-role-policies --role-name PazPazECSTaskRole

# Attach policy if missing
aws iam attach-role-policy \
  --role-name PazPazECSTaskRole \
  --policy-arn arn:aws:iam::123456789012:policy/PazPazSecretsReadOnly
```

### Issue 2: Keys Don't Match

**Error:**

```
❌ Keys DO NOT match - DO NOT PROCEED
```

**Cause**: Typo in secret creation or copy-paste error.

**Solution:**

```bash
# Delete incorrect secret
aws secretsmanager delete-secret \
  --secret-id pazpaz/encryption-key-v1 \
  --force-delete-without-recovery

# Recreate with correct key
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v1 \
  --secret-string "$CURRENT_PROD_KEY"

# Re-verify match
```

### Issue 3: Fallback Loop (Constantly Using Env Var)

**Symptom**: Logs show repeated `aws_unavailable_using_env_fallback`

**Causes**:

1. IAM role not attached to ECS task
2. Network connectivity issue
3. Wrong AWS region

**Diagnosis:**

```bash
# Check ECS task role
aws ecs describe-task-definition \
  --task-definition pazpaz-api-production \
  --query 'taskDefinition.taskRoleArn'

# Test network from container
aws ecs execute-command \
  --cluster pazpaz-production \
  --task <task-id> \
  --container pazpaz-api \
  --interactive \
  --command "/bin/sh"

# Inside container:
curl https://secretsmanager.us-east-1.amazonaws.com
```

---

## Next Steps

- **Monitor AWS Costs**: AWS Secrets Manager pricing (~$0.40/secret/month)
- **Set Up Key Rotation**: See [KEY_ROTATION_PROCEDURE.md](KEY_ROTATION_PROCEDURE.md)
- **Configure CloudWatch Dashboards**: Monitor key access patterns

---

**Document Version:** 1.0
**Last Updated:** 2025-10-12
**Owner:** DevOps Team
**Reviewers:** Security Team, Backend Team
