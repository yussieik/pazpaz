# AWS Secrets Manager for Database Credentials

**Status:** ✅ Implemented (Task 2.1 - Security Remediation Plan)
**Last Updated:** 2025-10-19
**HIPAA Compliance:** ✅ Required for production

---

## Overview

PazPaz uses AWS Secrets Manager to securely store and retrieve database credentials in production and staging environments. This eliminates the need to store plaintext passwords in environment files, which is a **HIPAA compliance requirement**.

### Security Benefits

- **No plaintext credentials** in configuration files or code
- **Automatic encryption at rest** using AWS KMS
- **Audit trail** via AWS CloudTrail for all secret access
- **Automatic rotation support** (90-day rotation required for HIPAA)
- **Fine-grained IAM permissions** control who/what can access secrets
- **Graceful fallback** to environment variables for development

### Architecture

```
Environment Detection
       │
       ├─ Local Development ──────► DATABASE_URL environment variable (.env file)
       │
       ├─ Staging ─────────────────► AWS Secrets Manager (primary)
       │                              └─ Fallback: DATABASE_URL env var
       │
       └─ Production ──────────────► AWS Secrets Manager (primary)
                                      └─ Fallback: DATABASE_URL env var
```

---

## AWS Secret Format

The database credentials are stored as a JSON object in AWS Secrets Manager:

```json
{
  "username": "pazpaz",
  "password": "GENERATED_STRONG_PASSWORD_HERE",
  "host": "prod-db.internal",
  "port": 5432,
  "database": "pazpaz",
  "ssl_cert_path": "/etc/ssl/certs/rds-ca-2019-root.pem"
}
```

### Field Descriptions

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `username` | Yes | PostgreSQL username | `pazpaz` |
| `password` | Yes | PostgreSQL password (min 32 chars) | `Generated via openssl` |
| `host` | Yes | Database hostname/IP | `prod-db.internal` or `db.example.com` |
| `port` | Yes | PostgreSQL port | `5432` |
| `database` | Yes | Database name | `pazpaz` |
| `ssl_cert_path` | No | Path to SSL CA certificate on server | `/etc/ssl/certs/rds-ca-2019-root.pem` |

**Notes:**
- `ssl_cert_path` is optional and defaults to `/etc/ssl/certs/ca-certificates.crt`
- SSL configuration (mode, verification) is handled separately in `/backend/src/pazpaz/db/base.py`

---

## Setup Instructions

### Step 1: Generate Strong Password

Generate a cryptographically secure password (minimum 32 characters, recommend 64):

```bash
# Generate 64-character password
openssl rand -base64 48 | tr -d '/+=' | cut -c1-64
```

**Password Requirements (HIPAA):**
- Minimum 32 characters (64 recommended)
- Include uppercase, lowercase, numbers, symbols
- No dictionary words or sequential patterns
- Must be rotated every 90 days

### Step 2: Create Secret in AWS Secrets Manager

Create a JSON file with your database credentials:

```bash
# Create db-credentials.json (DO NOT commit to git!)
cat > db-credentials.json <<EOF
{
  "username": "pazpaz",
  "password": "YOUR_GENERATED_PASSWORD_HERE",
  "host": "prod-db.internal",
  "port": 5432,
  "database": "pazpaz",
  "ssl_cert_path": "/etc/ssl/certs/rds-ca-2019-root.pem"
}
EOF
```

Create the secret using AWS CLI:

```bash
# Create secret
aws secretsmanager create-secret \
    --name pazpaz/database-credentials \
    --description "PazPaz production database credentials" \
    --secret-string file://db-credentials.json \
    --region us-east-1

# Securely delete the credentials file
shred -u db-credentials.json  # Linux
# or
rm -P db-credentials.json      # macOS
```

### Step 3: Configure IAM Permissions

Your application needs IAM permissions to read the secret. Create an IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/database-credentials-*"
    }
  ]
}
```

Attach this policy to:
- Your ECS task role (if using ECS)
- Your EC2 instance profile (if using EC2)
- Your Lambda execution role (if using Lambda)

### Step 4: Configure Application Environment

Set the following environment variables in your production environment:

```bash
# Required
ENVIRONMENT=production  # or staging
AWS_REGION=us-east-1

# Optional (override default secret name)
DB_SECRETS_MANAGER_KEY_NAME=pazpaz/database-credentials
```

**Do NOT set `DATABASE_URL` in production** - it will be fetched from AWS Secrets Manager automatically.

### Step 5: Verify Setup

Test that your application can fetch the credentials:

```python
# Test script: test_db_connection.py
from pazpaz.utils.secrets_manager import get_database_credentials

# Should fetch from AWS Secrets Manager in production
db_url = get_database_credentials(
    environment="production",
    secret_name="pazpaz/database-credentials",
    region="us-east-1"
)

print("✅ Successfully fetched database credentials from AWS Secrets Manager")
print(f"Host: {db_url.split('@')[1].split(':')[0]}")
```

Run the test:

```bash
AWS_PROFILE=production ENVIRONMENT=production uv run python test_db_connection.py
```

---

## Local Development Setup

For local development, **do not use AWS Secrets Manager**. Instead, use a `.env` file:

```bash
# .env (local development only)
ENVIRONMENT=local
DATABASE_URL=postgresql+asyncpg://pazpaz:YOUR_LOCAL_PASSWORD@localhost:5432/pazpaz
```

The application will automatically detect `ENVIRONMENT=local` and use the `DATABASE_URL` environment variable instead of AWS Secrets Manager.

---

## Credential Rotation (HIPAA Requirement)

Database passwords must be rotated every **90 days** for HIPAA compliance.

### Rotation Procedure

1. **Generate new password:**
   ```bash
   openssl rand -base64 48 | tr -d '/+=' | cut -c1-64
   ```

2. **Update database password:**
   ```sql
   -- Connect to PostgreSQL as superuser
   ALTER USER pazpaz WITH PASSWORD 'NEW_PASSWORD_HERE';
   ```

3. **Update AWS Secrets Manager secret:**
   ```bash
   # Create new credentials JSON
   cat > db-credentials-new.json <<EOF
   {
     "username": "pazpaz",
     "password": "NEW_PASSWORD_HERE",
     "host": "prod-db.internal",
     "port": 5432,
     "database": "pazpaz",
     "ssl_cert_path": "/etc/ssl/certs/rds-ca-2019-root.pem"
   }
   EOF

   # Update secret
   aws secretsmanager update-secret \
       --secret-id pazpaz/database-credentials \
       --secret-string file://db-credentials-new.json

   # Securely delete credentials file
   shred -u db-credentials-new.json
   ```

4. **Restart application:**
   ```bash
   # ECS
   aws ecs update-service --cluster pazpaz-prod --service pazpaz-api --force-new-deployment

   # EC2/systemd
   sudo systemctl restart pazpaz-api
   ```

5. **Verify connectivity:**
   ```bash
   # Check application logs for successful database connection
   kubectl logs -f deployment/pazpaz-api | grep "database_credentials_fetched_from_aws"
   ```

### Automatic Rotation with AWS Secrets Manager

AWS Secrets Manager supports automatic rotation via Lambda functions. See:
- [AWS Secrets Manager Rotation Tutorial](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)

**Recommended:** Set up automatic 90-day rotation for HIPAA compliance.

---

## Troubleshooting

### Error: "Database credentials not found in AWS Secrets Manager"

**Cause:** Secret doesn't exist or application doesn't have IAM permissions.

**Solution:**
1. Verify secret exists:
   ```bash
   aws secretsmanager describe-secret --secret-id pazpaz/database-credentials
   ```

2. Check IAM permissions:
   ```bash
   aws iam simulate-principal-policy \
       --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/YOUR_ROLE \
       --action-names secretsmanager:GetSecretValue \
       --resource-arns arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/database-credentials-*
   ```

3. Check application logs:
   ```bash
   # Look for specific error messages
   grep "failed_to_fetch_secret" /var/log/pazpaz/api.log
   ```

### Error: "Unable to locate credentials"

**Cause:** No AWS credentials available (IAM role not attached or AWS credentials not configured).

**Solution:**
1. If using ECS/EC2, attach IAM role with Secrets Manager permissions
2. If using local AWS CLI, configure credentials:
   ```bash
   aws configure --profile production
   ```

### Secret Fetched but Database Connection Fails

**Cause:** Incorrect credentials in secret or database not accessible.

**Solution:**
1. Verify secret contents:
   ```bash
   aws secretsmanager get-secret-value --secret-id pazpaz/database-credentials \
       --query SecretString --output text | jq .
   ```

2. Test database connection manually:
   ```bash
   psql "postgresql://pazpaz:PASSWORD@prod-db.internal:5432/pazpaz?sslmode=require"
   ```

3. Check database firewall/security groups

### Credentials Not Updating After Rotation

**Cause:** Application caches credentials using `@lru_cache`.

**Solution:** Restart the application to clear the cache:
```bash
# ECS
aws ecs update-service --cluster pazpaz-prod --service pazpaz-api --force-new-deployment

# Kubernetes
kubectl rollout restart deployment/pazpaz-api

# Systemd
sudo systemctl restart pazpaz-api
```

---

## Security Best Practices

### ✅ DO

- Use AWS Secrets Manager for production and staging environments
- Rotate database passwords every 90 days (HIPAA requirement)
- Use strong passwords (minimum 32 characters, recommend 64)
- Enable AWS CloudTrail to audit secret access
- Use IAM roles instead of IAM users for application access
- Test credential rotation in staging before production
- Monitor secret access patterns for anomalies

### ❌ DON'T

- Don't store database passwords in `.env` files in production
- Don't commit `db-credentials.json` to git (add to `.gitignore`)
- Don't hardcode database passwords in code
- Don't share production database passwords via email/Slack
- Don't use weak passwords or default passwords
- Don't grant overly broad IAM permissions
- Don't skip password rotation schedule

---

## Monitoring & Alerting

Set up CloudWatch alarms for:

1. **Secret access failures**
   - Metric: `secretsmanager:GetSecretValue` API errors
   - Threshold: > 5 failures in 5 minutes
   - Action: Alert security team

2. **Excessive secret access**
   - Metric: `secretsmanager:GetSecretValue` API calls
   - Threshold: > 100 calls in 1 minute (indicates potential breach)
   - Action: Alert security team immediately

3. **Secret not rotated**
   - Metric: Days since last rotation
   - Threshold: > 90 days
   - Action: Alert DevOps team

---

## Cost Optimization

AWS Secrets Manager pricing (as of 2025):
- **$0.40 per secret per month**
- **$0.05 per 10,000 API calls**

**Estimated monthly cost for database credentials:**
- Secret storage: $0.40/month
- API calls: ~$0.01/month (assuming 2,000 calls/day with caching)
- **Total: ~$0.41/month**

**Note:** The `@lru_cache` decorator in `get_database_credentials()` reduces API calls to 1 per application instance, significantly reducing costs.

---

## HIPAA Compliance Checklist

- [x] Database credentials stored in encrypted service (AWS Secrets Manager)
- [x] Credentials encrypted at rest using AWS KMS
- [x] Access logged via AWS CloudTrail (audit trail)
- [x] Fine-grained access control via IAM policies
- [ ] 90-day password rotation schedule implemented
- [ ] Automatic rotation configured (optional but recommended)
- [ ] Monitoring and alerting for secret access anomalies
- [ ] Incident response plan for credential compromise

---

## Related Documentation

- [AWS Secrets Manager Setup (Encryption Keys)](/docs/security/encryption/AWS_SECRETS_MANAGER_SETUP.md)
- [Database SSL/TLS Configuration](/docs/backend/database/SSL_TLS_CONFIGURATION.md)
- [Security Remediation Plan](/docs/SECURITY_REMEDIATION_PLAN.md) - Task 2.1
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [HIPAA Security Rule - Access Control](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)

---

## Support

**Security Issues:** security@pazpaz.com
**AWS Support:** Open ticket via AWS Console
**Internal Documentation:** `/docs/backend/database/`
