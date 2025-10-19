# Production Deployment Checklist

**Last Updated:** 2025-10-19

Use this checklist before deploying PazPaz backend to production to ensure all security and infrastructure requirements are met.

---

## Pre-Deployment Checklist

### 1. AWS IAM Roles Configuration

- [ ] **Task Execution Role Created**
  - Role name: `pazpaz-ecs-task-execution-role`
  - Trust policy allows `ecs-tasks.amazonaws.com`
  - Has `AmazonECSTaskExecutionRolePolicy` attached
  - Can access Secrets Manager for `pazpaz/database-url` and `pazpaz/redis-url`

- [ ] **Application Task Role Created**
  - Role name: `pazpaz-backend-task-role`
  - Trust policy allows `ecs-tasks.amazonaws.com`
  - Custom policy attached with:
    - Secrets Manager access (encryption keys, JWT secrets)
    - S3 access (attachments bucket with encryption enforced)
    - RDS IAM authentication
    - CloudWatch metrics

- [ ] **IAM Roles Tested Locally**
  - Assumed role using `aws sts assume-role`
  - Verified Secrets Manager access
  - Verified S3 upload with encryption
  - Verified RDS connection with IAM auth

**Reference:** [AWS_IAM_ROLES.md](/Users/yussieik/Desktop/projects/pazpaz/docs/deployment/AWS_IAM_ROLES.md)

---

### 2. AWS Secrets Manager

- [ ] **Encryption Master Key Stored**
  - Secret name: `pazpaz/encryption-key-v1`
  - Value: Base64-encoded Fernet key (44 characters)
  - Region: `us-east-1`
  - Automatic rotation: Disabled (versioned instead)

- [ ] **JWT Secret Stored**
  - Secret name: `pazpaz/jwt-secret`
  - Value: Strong random string (64+ characters)
  - Region: `us-east-1`
  - Automatic rotation: Enabled (90-day rotation)

- [ ] **Database URL Stored**
  - Secret name: `pazpaz/database-url`
  - Value: `postgresql+asyncpg://USER:PASS@HOST:5432/pazpaz`
  - Region: `us-east-1`
  - Automatic rotation: Enabled (90-day rotation)

- [ ] **Redis URL Stored**
  - Secret name: `pazpaz/redis-url`
  - Value: `redis://HOST:6379/0`
  - Region: `us-east-1`

- [ ] **Email Credentials Stored** (if using SMTP)
  - Secret name: `pazpaz/email-credentials`
  - Format: JSON with `username`, `password`, `smtp_host`, `smtp_port`

---

### 3. Database (RDS PostgreSQL)

- [ ] **RDS Instance Configured**
  - Engine: PostgreSQL 16
  - Instance class: At least `db.t3.medium` for production
  - Multi-AZ: Enabled for high availability
  - Storage: Encrypted with AWS KMS
  - Backup retention: 7 days minimum

- [ ] **IAM Database Authentication Enabled**
  - RDS instance parameter: `rds.force_ssl=1`
  - IAM authentication enabled in RDS settings
  - Database user `pazpaz` created with IAM auth

- [ ] **Security Group Configured**
  - Inbound rule: PostgreSQL (5432) from ECS security group only
  - Outbound: All traffic allowed

- [ ] **Database Initialized**
  - Schema created via Alembic migrations
  - Initial data seeded (if applicable)
  - Verified workspace isolation with test data

---

### 4. S3 Storage (Attachments)

- [ ] **S3 Bucket Created**
  - Bucket name: `pazpaz-attachments-prod`
  - Region: `us-east-1`
  - Versioning: Enabled
  - Server-side encryption: AES-256 (enforced via bucket policy)

- [ ] **Bucket Policy Enforces Encryption**
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "DenyUnencryptedObjectUploads",
        "Effect": "Deny",
        "Principal": "*",
        "Action": "s3:PutObject",
        "Resource": "arn:aws:s3:::pazpaz-attachments-prod/*",
        "Condition": {
          "StringNotEquals": {
            "s3:x-amz-server-side-encryption": "AES256"
          }
        }
      }
    ]
  }
  ```

- [ ] **Lifecycle Policy Configured** (optional)
  - Transition to IA after 90 days
  - Delete incomplete multipart uploads after 7 days

- [ ] **Public Access Blocked**
  - Block all public access enabled
  - Bucket ACL disabled

---

### 5. Redis (ElastiCache)

- [ ] **ElastiCache Cluster Created**
  - Engine: Redis 7.x
  - Node type: At least `cache.t3.medium`
  - Encryption in transit: Enabled (TLS)
  - Encryption at rest: Enabled

- [ ] **Security Group Configured**
  - Inbound rule: Redis (6379) from ECS security group only

- [ ] **Connection Tested**
  - Verified connectivity from ECS task
  - Tested rate limiting functionality

---

### 6. ECS Task Definition

- [ ] **Task Definition Registered**
  - Family: `pazpaz-backend`
  - CPU: 512 (minimum)
  - Memory: 1024 MB (minimum)
  - Network mode: `awsvpc`
  - Compatibility: `FARGATE`

- [ ] **IAM Roles Attached**
  - Execution role ARN: `arn:aws:iam::ACCOUNT_ID:role/pazpaz-ecs-task-execution-role`
  - Task role ARN: `arn:aws:iam::ACCOUNT_ID:role/pazpaz-backend-task-role`

- [ ] **Environment Variables Set**
  - `ENVIRONMENT=production`
  - `AWS_REGION=us-east-1`
  - `LOG_LEVEL=info`

- [ ] **Secrets from Secrets Manager**
  - `DATABASE_URL` → `pazpaz/database-url`
  - `REDIS_URL` → `pazpaz/redis-url`

- [ ] **Health Check Configured**
  - Command: `curl -f http://localhost:8000/health || exit 1`
  - Interval: 30 seconds
  - Timeout: 5 seconds
  - Retries: 3
  - Start period: 60 seconds

- [ ] **Logging Configured**
  - Log driver: `awslogs`
  - Log group: `/ecs/pazpaz-backend`
  - Stream prefix: `ecs`

---

### 7. Application Load Balancer (ALB)

- [ ] **ALB Created**
  - Scheme: Internet-facing
  - IP address type: IPv4
  - Availability Zones: At least 2

- [ ] **SSL Certificate Attached**
  - Certificate: AWS ACM certificate for `api.pazpaz.com`
  - Protocol: HTTPS (443)
  - SSL policy: `ELBSecurityPolicy-TLS-1-2-2017-01` or higher

- [ ] **Target Group Configured**
  - Protocol: HTTP
  - Port: 8000
  - Health check path: `/health`
  - Health check interval: 30 seconds
  - Healthy threshold: 2
  - Unhealthy threshold: 3

- [ ] **Security Group Configured**
  - Inbound: HTTPS (443) from `0.0.0.0/0`
  - Outbound: HTTP (8000) to ECS security group

---

### 8. DNS Configuration

- [ ] **Route 53 Hosted Zone**
  - Domain: `pazpaz.com`
  - NS records propagated

- [ ] **A Record for API**
  - Record: `api.pazpaz.com`
  - Type: A (Alias to ALB)
  - Target: ALB DNS name

---

### 9. Monitoring & Alerts

- [ ] **CloudWatch Log Group Created**
  - Log group: `/ecs/pazpaz-backend`
  - Retention: 30 days (or as required by compliance)

- [ ] **CloudWatch Alarms Configured**
  - High CPU utilization (>80% for 5 minutes)
  - High memory utilization (>80% for 5 minutes)
  - High error rate (>10 errors/minute)
  - Decryption failures (>10 failures in 5 minutes)

- [ ] **Prometheus Metrics Endpoint**
  - Exposed at `/metrics`
  - Scraped by Prometheus/CloudWatch

- [ ] **Alert Integration**
  - PagerDuty/OpsGenie configured for critical alerts
  - Email notifications for warnings

**Reference:** [MONITORING_ALERTS.md](/Users/yussieik/Desktop/projects/pazpaz/docs/deployment/MONITORING_ALERTS.md)

---

### 10. Security Scanning

- [ ] **GitHub Actions Workflows Enabled**
  - Security scanning workflow running
  - Dependency audit (pip-audit)
  - Secrets scanning (gitleaks)
  - Docker image scanning (Trivy)

- [ ] **CI/CD Blocks Deployment on Critical Issues**
  - Critical vulnerabilities block PR merge
  - Secrets detected block PR merge

**Reference:** [.github/workflows/security-scan.yml](/Users/yussieik/Desktop/projects/pazpaz/.github/workflows/security-scan.yml)

---

### 11. Application Configuration

- [ ] **Environment Validation**
  - Application starts successfully in production mode
  - IAM role verified at startup (logs show `aws_iam_role_verified`)
  - Encryption master key loaded from Secrets Manager
  - Database migrations applied

- [ ] **Rate Limiting Enabled**
  - Magic link verification: 5 requests/minute per IP
  - API endpoints: Appropriate limits configured

- [ ] **Error Sanitization Active**
  - Production errors return generic messages
  - Internal details logged but not exposed

- [ ] **Audit Logging Enabled**
  - All data access/modifications logged to `AuditEvent` table
  - No PII in audit logs

---

### 12. Performance Validation

- [ ] **Performance Targets Met**
  - Schedule endpoints (GET /appointments): p95 < 150ms
  - Database queries optimized with indexes
  - Connection pooling configured

- [ ] **Load Testing Completed**
  - Simulated production load (concurrent users)
  - No performance degradation under load
  - Auto-scaling tested (if configured)

---

### 13. Backup & Recovery

- [ ] **Database Backups Configured**
  - Automated daily backups (RDS)
  - Backup retention: 7 days minimum
  - Point-in-time recovery enabled

- [ ] **S3 Bucket Versioning Enabled**
  - Accidental deletions recoverable
  - Lifecycle policy for old versions (optional)

- [ ] **Disaster Recovery Plan Documented**
  - RTO (Recovery Time Objective): < 4 hours
  - RPO (Recovery Point Objective): < 1 hour
  - Runbook for database restore
  - Runbook for S3 restore

---

### 14. Compliance (HIPAA)

- [ ] **Encryption at Rest**
  - Database: RDS encryption enabled (AWS KMS)
  - S3: Server-side encryption enforced (AES-256)
  - Redis: Encryption at rest enabled
  - Application: PHI encrypted with Fernet before storage

- [ ] **Encryption in Transit**
  - ALB → ECS: HTTPS enforced
  - ECS → RDS: SSL/TLS required
  - ECS → Redis: TLS enabled
  - ECS → Secrets Manager: HTTPS (default)

- [ ] **Access Controls**
  - IAM roles enforce least privilege
  - Workspace isolation enforced in all queries
  - Audit logging captures all data access

- [ ] **Audit Trail**
  - CloudTrail enabled for AWS API calls
  - Application audit events logged to database
  - Logs retained for 7 years (HIPAA requirement)

**Reference:** [/docs/security/HIPAA_COMPLIANCE.md](/Users/yussieik/Desktop/projects/pazpaz/docs/security/HIPAA_COMPLIANCE.md)

---

### 15. Final Checks

- [ ] **No Hardcoded Credentials**
  - No AWS access keys in code or environment variables
  - All secrets in AWS Secrets Manager
  - `.env` files not committed to git

- [ ] **Debug Mode Disabled**
  - `ENVIRONMENT=production`
  - `DEBUG=false`
  - Detailed error messages disabled

- [ ] **Gitleaks Scan Passed**
  - No secrets in git history
  - `.gitleaks.toml` configured

- [ ] **Dependency Audit Passed**
  - No critical vulnerabilities in dependencies
  - All dependencies up to date

- [ ] **Docker Image Scanned**
  - Trivy scan passed (no critical/high vulnerabilities)
  - Image tagged with version

---

## Post-Deployment Verification

After deploying to production:

### Immediate Checks (within 1 hour)

- [ ] **Health Check Passing**
  - `/health` endpoint returns 200 OK
  - ECS tasks running and healthy in target group

- [ ] **IAM Role Verification**
  - Check logs for `aws_iam_role_verified` message
  - Verify account ID and ARN are correct

- [ ] **Database Connectivity**
  - Application can connect to RDS
  - Workspace isolation working (test with multiple workspaces)

- [ ] **Secrets Manager Access**
  - Encryption key loaded successfully
  - JWT secret loaded successfully

- [ ] **S3 Upload Test**
  - Upload a test attachment
  - Verify encryption enforced (try upload without encryption, should fail)
  - Verify file accessible via pre-signed URL

- [ ] **Rate Limiting Active**
  - Test magic link verification rate limit (5 attempts/minute)
  - Verify 429 response after threshold

### 24-Hour Monitoring

- [ ] **CloudWatch Metrics**
  - No sustained high CPU/memory usage
  - Error rate < 1%
  - Decryption failures = 0

- [ ] **Application Logs**
  - No unexpected errors or warnings
  - Audit events logging correctly

- [ ] **Performance**
  - Schedule endpoints p95 < 150ms
  - No slow query warnings

### 7-Day Monitoring

- [ ] **Auto-Scaling** (if configured)
  - Scaling policies working correctly
  - Tasks scale up/down based on load

- [ ] **Backup Verification**
  - Daily RDS snapshots created
  - Backups restorable (test restore in staging)

- [ ] **Security Alerts**
  - No unauthorized access attempts
  - No decryption failures

---

## Rollback Plan

If deployment fails or critical issues arise:

### Immediate Rollback

1. **Revert to previous ECS task definition:**
   ```bash
   aws ecs update-service \
     --cluster pazpaz-cluster \
     --service pazpaz-backend \
     --task-definition pazpaz-backend:PREVIOUS_REVISION
   ```

2. **Monitor rollback:**
   - Verify tasks running healthy
   - Check logs for errors
   - Verify health checks passing

### Database Rollback

1. **Restore from snapshot:**
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier pazpaz-prod-rollback \
     --db-snapshot-identifier pazpaz-prod-snapshot-YYYY-MM-DD
   ```

2. **Update DNS to point to rollback instance**

3. **Verify data integrity**

---

## Deployment Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| **Backend Engineer** | | | |
| **DevOps Engineer** | | | |
| **Security Officer** | | | |
| **Product Owner** | | | |

---

**Deployment Approved:** ☐ Yes ☐ No

**Deployment Date:** _______________

**Deployment Time:** _______________

**Deployed By:** _______________

---

## Appendix: Deployment Commands

**Deploy new version:**
```bash
# Build and push Docker image
docker build -t pazpaz-backend:v1.0.0 ./backend
docker tag pazpaz-backend:v1.0.0 ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pazpaz-backend:v1.0.0
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pazpaz-backend:v1.0.0

# Update ECS service
aws ecs update-service \
  --cluster pazpaz-cluster \
  --service pazpaz-backend \
  --force-new-deployment
```

**Check deployment status:**
```bash
aws ecs describe-services \
  --cluster pazpaz-cluster \
  --services pazpaz-backend
```

**View logs:**
```bash
aws logs tail /ecs/pazpaz-backend --follow
```
