# Deployment Documentation

Infrastructure, deployment, and production operations documentation.

## 📋 Contents

### Production-Ready Documentation

- **[GitHub Secrets Configuration](GITHUB_SECRETS.md)** - Complete GitHub Secrets setup guide for CI/CD and production deployment
- **[Docker Security](DOCKER_SECURITY.md)** - Hardened container configuration for HIPAA compliance
- **[AWS IAM Roles](AWS_IAM_ROLES.md)** - IAM role configuration for ECS tasks (task execution role, application role)
- **[AWS Secrets Manager](AWS_SECRETS_MANAGER.md)** - Centralized secret management (encryption keys, database credentials, JWT secrets)
- **[Production Deployment Checklist](PRODUCTION_DEPLOYMENT_CHECKLIST.md)** - Complete pre-deployment verification checklist
- **[Infrastructure Security Checklist](INFRASTRUCTURE_SECURITY_CHECKLIST.md)** - Security baseline requirements for HIPAA compliance

### Coming in Week 5

- **CI/CD Pipeline** - GitHub Actions, deployment automation
- **Environment Configuration** - Production, staging, development setup
- **Database Migrations** - Alembic migration deployment procedures
- **Monitoring & Alerting** - Logging, metrics, alerts configuration (CloudWatch/Datadog)
- **Backup & Recovery** - Database backup procedures, disaster recovery
- **Scaling** - Horizontal/vertical scaling strategies
- **SSL/TLS** - Certificate management, HTTPS configuration

## 🔐 Security Requirements

### AWS Secrets Manager (Required for Production)

All production secrets MUST be stored in AWS Secrets Manager:
- ✅ Encryption master key (v2)
- ✅ JWT signing secret
- ✅ Database credentials
- ✅ Redis credentials
- ✅ S3/Storage credentials (if using IAM user instead of role)

See [AWS_SECRETS_MANAGER.md](AWS_SECRETS_MANAGER.md) for complete setup guide.

### IAM Roles (Required for Production)

Production deployments MUST use IAM roles (not access keys):
- ✅ Task Execution Role (`pazpaz-ecs-task-execution-role`)
- ✅ Application Task Role (`pazpaz-backend-task-role`)

See [AWS_IAM_ROLES.md](AWS_IAM_ROLES.md) for configuration.

## 📝 Prerequisites

Before production deployment:

- [ ] **AWS Secrets Manager configured** - All secrets created and replicated (see [AWS_SECRETS_MANAGER.md](AWS_SECRETS_MANAGER.md))
- [ ] **IAM Roles created** - Task execution and application roles (see [AWS_IAM_ROLES.md](AWS_IAM_ROLES.md))
- [ ] **SSL certificates configured** - AWS ACM certificate for API domain
- [ ] **Production database provisioned** - RDS PostgreSQL 16 with encryption
- [ ] **Redis cluster configured** - ElastiCache Redis 7.x with encryption
- [ ] **S3 bucket created** - `pazpaz-attachments-prod` with encryption enforced
- [ ] **Monitoring/logging setup** - CloudWatch logs and alarms
- [ ] **Backup automation configured** - RDS automated backups (7-day retention)

## 📊 Deployment Checklist

Use the comprehensive deployment checklist:
- [Production Deployment Checklist](PRODUCTION_DEPLOYMENT_CHECKLIST.md)

This includes:
1. IAM roles verification (15 items)
2. AWS Secrets Manager setup (24 items)
3. Database configuration (9 items)
4. S3 storage (9 items)
5. Redis (6 items)
6. ECS task definition (12 items)
7. Application Load Balancer (10 items)
8. DNS configuration (4 items)
9. Monitoring & alerts (8 items)
10. Security scanning (5 items)
11. Application configuration (10 items)
12. Performance validation (6 items)
13. Backup & recovery (6 items)
14. HIPAA compliance (12 items)
15. Final checks (8 items)

**Total:** 144 deployment verification items

## 🔍 Quick Reference

### GitHub Secrets Validation
```bash
# Validate secrets configuration locally
python3 scripts/validate-secrets.py

# Validate production secrets
export PROD_ENCRYPTION_MASTER_KEY="your-key-here"
export PROD_SECRET_KEY="your-secret-here"
export PROD_JWT_SECRET_KEY="your-jwt-secret-here"
python3 scripts/validate-secrets.py --env production

# Run GitHub Actions validation workflow
gh workflow run validate-secrets.yml
```

### Secret Management (AWS)
```bash
# List all PazPaz secrets
aws secretsmanager list-secrets --filters Key=name,Values=pazpaz/ --region us-east-1

# Get secret value
aws secretsmanager get-secret-value --secret-id pazpaz/encryption-key-v2 --region us-east-1
```

### IAM Roles
```bash
# Verify task role permissions
aws iam get-role-policy \
  --role-name pazpaz-backend-task-role \
  --policy-name pazpaz-backend-permissions

# Check IAM role attached to ECS task
aws ecs describe-task-definition \
  --task-definition pazpaz-backend \
  --query 'taskDefinition.taskRoleArn'
```

### Docker Compose (Development)
```bash
# Start all services
docker compose up -d

# Check service health
docker compose ps

# View logs
docker compose logs -f api
```

## 🚀 Deployment Timeline

- **Week 5 Day 23:** Production configuration and optimization
- **Week 5 Day 25:** Final deployment preparation and runbooks
- **Post-V1:** Continuous monitoring and optimization

---

**Last Updated:** 2025-10-20
**Status:** Pre-Production (Infrastructure Ready)
