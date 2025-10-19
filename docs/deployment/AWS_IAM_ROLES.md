# AWS IAM Roles for PazPaz Backend

**Last Updated:** 2025-10-19

## Overview

PazPaz uses IAM roles instead of access keys in production to eliminate credential management and reduce security risks. This approach provides automatic credential rotation, fine-grained permissions, and comprehensive audit trails.

**Benefits:**
- No credentials in environment variables or configuration files
- Automatic credential rotation (no manual key management)
- CloudTrail audit logs for all AWS API calls
- HIPAA compliance (§164.312(a)(2)(i) - Unique User Identification)

---

## Required IAM Roles

### 1. ECS Task Execution Role

**Purpose:** Allows ECS to pull container images from ECR and write logs to CloudWatch.

**Role Name:** `pazpaz-ecs-task-execution-role`

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Permissions Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/ecs/pazpaz-backend:*"
    },
    {
      "Sid": "SecretsManagerForEnv",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/database-url-*",
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/redis-url-*"
      ]
    }
  ]
}
```

---

### 2. Application Task Role

**Purpose:** Grants the running application permissions to access AWS resources (Secrets Manager, S3, RDS).

**Role Name:** `pazpaz-backend-task-role`

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Permissions Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/encryption-key-*",
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/jwt-secret-*",
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/email-credentials-*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "S3AttachmentsAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:PutObjectTagging",
        "s3:GetObjectTagging"
      ],
      "Resource": "arn:aws:s3:::pazpaz-attachments-prod/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    },
    {
      "Sid": "S3ListBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::pazpaz-attachments-prod",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["workspace-*/*"]
        }
      }
    },
    {
      "Sid": "RDSIAMAuth",
      "Effect": "Allow",
      "Action": ["rds-db:connect"],
      "Resource": "arn:aws:rds-db:us-east-1:*:dbuser:*/pazpaz"
    },
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "PazPaz/Backend"
        }
      }
    }
  ]
}
```

**Security Features:**
- **Least Privilege:** Only grants access to `pazpaz/*` secrets
- **Encryption Enforced:** S3 operations require server-side encryption
- **Region Restricted:** Secrets Manager access limited to `us-east-1`
- **Workspace Scoped:** S3 list operations scoped to workspace prefixes
- **Metrics Isolated:** CloudWatch metrics scoped to `PazPaz/Backend` namespace

---

## Deployment Steps

### Prerequisites

- AWS CLI configured with admin credentials
- Account ID and region determined
- ECS cluster created (`pazpaz-cluster`)
- S3 bucket created (`pazpaz-attachments-prod`)
- RDS instance created with IAM authentication enabled

### 1. Create Trust Policy Files

Save the trust policy for ECS tasks:

**File:** `trust-policy-ecs.json`
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 2. Create IAM Roles

```bash
# Set your AWS account ID and region
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1

# Create task execution role
aws iam create-role \
  --role-name pazpaz-ecs-task-execution-role \
  --assume-role-policy-document file://trust-policy-ecs.json \
  --description "ECS task execution role for PazPaz backend"

# Attach AWS managed policy for ECS task execution
aws iam attach-role-policy \
  --role-name pazpaz-ecs-task-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Create application task role
aws iam create-role \
  --role-name pazpaz-backend-task-role \
  --assume-role-policy-document file://trust-policy-ecs.json \
  --description "Application task role for PazPaz backend with access to Secrets Manager, S3, and RDS"
```

### 3. Create and Attach Custom Policies

**Create execution role custom policy:**
```bash
# Save the execution role policy to file
cat > pazpaz-execution-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerForEnv",
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/database-url-*",
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/redis-url-*"
      ]
    }
  ]
}
EOF

# Attach custom policy
aws iam put-role-policy \
  --role-name pazpaz-ecs-task-execution-role \
  --policy-name pazpaz-execution-secrets \
  --policy-document file://pazpaz-execution-policy.json
```

**Create application role custom policy:**
```bash
# Save the application policy to file (use policy from section 2 above)
cat > pazpaz-backend-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/encryption-key-*",
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/jwt-secret-*",
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/email-credentials-*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "S3AttachmentsAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:PutObjectTagging",
        "s3:GetObjectTagging"
      ],
      "Resource": "arn:aws:s3:::pazpaz-attachments-prod/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    },
    {
      "Sid": "S3ListBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::pazpaz-attachments-prod",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["workspace-*/*"]
        }
      }
    },
    {
      "Sid": "RDSIAMAuth",
      "Effect": "Allow",
      "Action": ["rds-db:connect"],
      "Resource": "arn:aws:rds-db:us-east-1:*:dbuser:*/pazpaz"
    },
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": ["cloudwatch:PutMetricData"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "PazPaz/Backend"
        }
      }
    }
  ]
}
EOF

# Attach custom policy
aws iam put-role-policy \
  --role-name pazpaz-backend-task-role \
  --policy-name pazpaz-backend-permissions \
  --policy-document file://pazpaz-backend-policy.json
```

### 4. Create Secrets in AWS Secrets Manager

```bash
# Encryption master key (base64-encoded Fernet key)
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v1 \
  --description "PazPaz encryption master key version 1" \
  --secret-string "$(openssl rand -base64 32)" \
  --region us-east-1

# JWT secret
aws secretsmanager create-secret \
  --name pazpaz/jwt-secret \
  --description "PazPaz JWT signing secret" \
  --secret-string "$(openssl rand -base64 64)" \
  --region us-east-1

# Database URL (example - adjust for your RDS instance)
aws secretsmanager create-secret \
  --name pazpaz/database-url \
  --description "PazPaz PostgreSQL connection URL" \
  --secret-string "postgresql+asyncpg://pazpaz:PASSWORD@pazpaz-prod.xxxxx.us-east-1.rds.amazonaws.com:5432/pazpaz" \
  --region us-east-1

# Redis URL (example - adjust for your ElastiCache instance)
aws secretsmanager create-secret \
  --name pazpaz/redis-url \
  --description "PazPaz Redis connection URL" \
  --secret-string "redis://pazpaz-redis.xxxxx.cache.amazonaws.com:6379/0" \
  --region us-east-1
```

### 5. Update ECS Task Definition

Create or update your ECS task definition to use IAM roles:

**File:** `task-definition.json`
```json
{
  "family": "pazpaz-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/pazpaz-ecs-task-execution-role",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/pazpaz-backend-task-role",
  "containerDefinitions": [
    {
      "name": "pazpaz-backend",
      "image": "ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pazpaz-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "AWS_REGION", "value": "us-east-1"},
        {"name": "LOG_LEVEL", "value": "info"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/database-url"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:pazpaz/redis-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/pazpaz-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

**Important:** Replace `ACCOUNT_ID` with your AWS account ID.

Register the task definition:
```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

### 6. Verify IAM Role at Application Startup

The PazPaz backend automatically verifies IAM role configuration at startup:

**File:** `/backend/src/pazpaz/main.py`
```python
@app.on_event("startup")
async def verify_aws_iam_role():
    """Verify AWS IAM role is configured in production."""
    if settings.environment in ("production", "staging"):
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            logger.info(
                "aws_iam_role_verified",
                account=identity['Account'],
                arn=identity['Arn'],
                user_id=identity['UserId']
            )
        except Exception as e:
            logger.error("aws_iam_role_verification_failed", error=str(e))
            raise RuntimeError(
                "AWS IAM role not configured. "
                "Production deployment requires IAM roles, not access keys."
            )
```

---

## Testing IAM Roles

### Local Testing with AssumeRole

For local development/testing with IAM roles:

```bash
# Assume the application task role
aws sts assume-role \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/pazpaz-backend-task-role \
  --role-session-name local-testing

# The output contains temporary credentials. Set them as environment variables:
export AWS_ACCESS_KEY_ID="ASIAxxxxxxxxxxxx"
export AWS_SECRET_ACCESS_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export AWS_SESSION_TOKEN="FwoGZXIvYXdzEBYaDxxxxxxxxxxxxxxxxxxxx..."

# Test the application with assumed role
cd /Users/yussieik/Desktop/projects/pazpaz/backend
env ENVIRONMENT=production uv run uvicorn pazpaz.main:app --host 0.0.0.0 --port 8000
```

### Verify Permissions

**Test Secrets Manager Access:**
```bash
# Should succeed
aws secretsmanager get-secret-value --secret-id pazpaz/encryption-key-v1

# Should fail (not in allowed secrets)
aws secretsmanager get-secret-value --secret-id some-other-secret
```

**Test S3 Access:**
```bash
# Should succeed (list bucket)
aws s3 ls s3://pazpaz-attachments-prod/

# Should succeed (upload with encryption)
echo "test" > test.txt
aws s3 cp test.txt s3://pazpaz-attachments-prod/workspace-123/test.txt \
  --server-side-encryption AES256

# Should fail (upload without encryption)
aws s3 cp test.txt s3://pazpaz-attachments-prod/workspace-123/test2.txt
```

**Test RDS IAM Authentication:**
```bash
# Generate auth token
export PGPASSWORD=$(aws rds generate-db-auth-token \
  --hostname pazpaz-prod.xxxxx.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --username pazpaz \
  --region us-east-1)

# Connect to database
psql -h pazpaz-prod.xxxxx.us-east-1.rds.amazonaws.com \
  -U pazpaz \
  -d pazpaz
```

### Integration Tests

Run the backend test suite with IAM role credentials:

```bash
cd /Users/yussieik/Desktop/projects/pazpaz/backend
env ENVIRONMENT=staging uv run pytest tests/ -v
```

---

## Security Best Practices

### 1. Principle of Least Privilege

✅ **Do:**
- Grant only the minimum permissions required
- Use resource-level permissions (ARNs) instead of `*`
- Add conditions to further restrict access
- Regularly review and remove unused permissions

❌ **Don't:**
- Use wildcard (`*`) for resources unless necessary
- Grant broad permissions like `s3:*` or `secretsmanager:*`
- Reuse roles across multiple applications

### 2. Secret Rotation

Enable automatic secret rotation for:
- Database credentials (90-day rotation)
- JWT secrets (annual rotation)
- Encryption keys (version-based, not rotation)

```bash
# Enable automatic rotation for database password
aws secretsmanager rotate-secret \
  --secret-id pazpaz/database-url \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:ACCOUNT_ID:function:SecretsManagerRDSPostgreSQLRotation \
  --rotation-rules AutomaticallyAfterDays=90
```

### 3. Audit and Monitoring

Enable CloudTrail for IAM role usage:

```bash
# Create CloudTrail trail for IAM events
aws cloudtrail create-trail \
  --name pazpaz-iam-audit \
  --s3-bucket-name pazpaz-cloudtrail-logs

aws cloudtrail start-logging --name pazpaz-iam-audit
```

Monitor suspicious activity:
- Failed `AssumeRole` attempts
- Access to secrets outside normal hours
- S3 uploads without encryption
- Multiple failed decryption attempts

### 4. Environment Separation

Use separate IAM roles for each environment:
- `pazpaz-backend-task-role-dev` (development)
- `pazpaz-backend-task-role-staging` (staging)
- `pazpaz-backend-task-role-prod` (production)

Each role should have access to environment-specific resources only.

---

## Troubleshooting

### Error: "User is not authorized to perform: sts:AssumeRole"

**Cause:** ECS task execution role missing or incorrect trust policy.

**Solution:**
1. Verify trust policy includes `ecs-tasks.amazonaws.com`
2. Check role exists: `aws iam get-role --role-name pazpaz-ecs-task-execution-role`

### Error: "AccessDeniedException: User is not authorized to perform: secretsmanager:GetSecretValue"

**Cause:** Application task role missing Secrets Manager permissions.

**Solution:**
1. Verify secret ARN in IAM policy matches actual secret
2. Check secret exists: `aws secretsmanager describe-secret --secret-id pazpaz/encryption-key-v1`
3. Verify resource ARN includes wildcard suffix: `pazpaz/encryption-key-*`

### Error: "Access Denied" when uploading to S3

**Cause:** S3 object not uploaded with server-side encryption.

**Solution:**
Ensure all S3 uploads include `--server-side-encryption AES256`:
```python
s3_client.put_object(
    Bucket='pazpaz-attachments-prod',
    Key=f'workspace-{workspace_id}/file.jpg',
    Body=file_data,
    ServerSideEncryption='AES256'  # Required by IAM policy condition
)
```

### Logs showing "Unable to locate credentials"

**Cause:** Application not running in ECS with task role attached.

**Solution:**
1. Verify task definition has `taskRoleArn` set
2. Restart ECS service to use updated task definition
3. Check ECS task metadata endpoint is accessible

---

## HIPAA Compliance

IAM roles fulfill these HIPAA requirements:

| Requirement | How IAM Roles Help |
|-------------|-------------------|
| §164.312(a)(2)(i) - Unique User Identification | Each ECS task assumes a unique role session with audit trail |
| §164.308(a)(4)(ii)(C) - Access Establishment | Centralized access control via IAM policies |
| §164.312(a)(1) - Access Control | Least privilege enforced via resource-level permissions |
| §164.312(b) - Audit Controls | CloudTrail logs all API calls with IAM role identity |
| §164.308(a)(3)(ii)(A) - Authorization/Supervision | IAM policies define exactly what each role can access |

---

## References

- [AWS IAM Roles for Tasks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [IAM Policy Conditions](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition.html)
- [RDS IAM Database Authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)

---

**Next Steps:**
1. Follow deployment steps to create IAM roles
2. Update ECS task definition with role ARNs
3. Test permissions with AssumeRole locally
4. Deploy to staging environment for validation
5. Monitor CloudTrail for IAM activity
