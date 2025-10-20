# Operations Documentation

Day-to-day operations, maintenance, and troubleshooting guides for PazPaz production infrastructure.

## 📋 Contents

### Current Documentation

- **Key Rotation Procedures** - See [/docs/security/encryption/KEY_ROTATION_PROCEDURE.md](/docs/security/encryption/KEY_ROTATION_PROCEDURE.md)
- **AWS Secrets Manager** - See [/docs/deployment/AWS_SECRETS_MANAGER.md](/docs/deployment/AWS_SECRETS_MANAGER.md)
- **Deployment Checklist** - See [/docs/deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md](/docs/deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md)

### Coming in Week 5

- **Runbooks** - Step-by-step operational procedures (database maintenance, service restart, rollback)
- **Troubleshooting Guides** - Common issues and solutions (connection errors, performance degradation, auth failures)
- **Monitoring Dashboards** - Key metrics and alerts (CloudWatch/Datadog dashboards)
- **On-Call Procedures** - Incident response, escalation paths, contact lists
- **Maintenance Windows** - Scheduled maintenance procedures (database vacuum, index optimization)
- **Performance Tuning** - Query optimization, caching strategies, connection pool tuning
- **Security Incidents** - Breach response procedures, credential rotation, audit log analysis

## 🚨 Critical Procedures

### Key Rotation

**Routine Schedule:**
- **Encryption Keys:** Versioned (not rotated) - New versions created manually
- **JWT Secrets:** 90 days (automatic via AWS Secrets Manager Lambda)
- **Database Credentials:** 90 days (automatic via AWS Secrets Manager Lambda)
- **S3 Credentials:** 90 days (manual rotation if using IAM user)
- **Redis Password:** 180 days (manual rotation)

**Rotation Procedure:**
See [/docs/security/encryption/KEY_ROTATION_PROCEDURE.md](/docs/security/encryption/KEY_ROTATION_PROCEDURE.md) for complete encryption key rotation guide.

**Emergency Rotation:**
- Within 24 hours of suspected compromise
- Follow zero-downtime rotation procedure (overlap period)
- Update CloudTrail audit logs
- Notify security team and stakeholders

### Database Maintenance

**Automated Tasks:**
- **Vacuum:** Weekly (automated via RDS maintenance window)
- **Backups:** Daily automated snapshots (7-day retention)
- **Index Optimization:** Monthly via cron job

**Manual Tasks:**
- **Migrations:** Deploy during maintenance window (Sundays 2-4 AM UTC)
- **Performance Tuning:** Quarterly query optimization review
- **Connection Pool Tuning:** As needed based on load

**Backup Verification:**
```bash
# List recent RDS snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier pazpaz-prod \
  --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime]' \
  --output table

# Test restore (in staging)
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier pazpaz-staging-restore-test \
  --db-snapshot-identifier pazpaz-prod-snapshot-YYYY-MM-DD
```

### Incident Response

**5-Step Process:**
1. **Detect** - Monitoring alerts (CloudWatch, Datadog, PagerDuty)
2. **Assess** - Severity classification (P0-P4), impact analysis
3. **Contain** - Isolate affected systems, prevent further damage
4. **Remediate** - Fix root cause, deploy hotfix if needed
5. **Document** - Post-mortem report, lessons learned

**Severity Levels:**
- **P0 (Critical):** Production down, data breach, security incident
- **P1 (High):** Major functionality broken, performance severely degraded
- **P2 (Medium):** Minor functionality broken, workaround available
- **P3 (Low):** Cosmetic issues, feature requests
- **P4 (Planning):** Technical debt, future enhancements

**Response Times:**
- P0: Immediate (5 minutes)
- P1: 15 minutes
- P2: 1 hour
- P3: Next business day
- P4: Backlog planning

### Common Operational Tasks

**Service Health Check:**
```bash
# Check all service health
docker compose ps

# Check API health endpoint
curl -f https://api.pazpaz.com/health

# Check database connectivity
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT 1;"

# Check Redis connectivity
docker exec pazpaz-redis redis-cli -a "$REDIS_PASSWORD" ping
```

**View Application Logs:**
```bash
# Local development
docker compose logs -f api

# Production (CloudWatch)
aws logs tail /ecs/pazpaz-backend --follow

# Filter for errors
aws logs tail /ecs/pazpaz-backend --follow --filter-pattern "ERROR"
```

**Database Connection Troubleshooting:**
```bash
# Check active connections
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "
  SELECT count(*) as connections,
         state,
         application_name
  FROM pg_stat_activity
  WHERE datname = 'pazpaz'
  GROUP BY state, application_name
  ORDER BY connections DESC;
"

# Check slow queries (> 1 second)
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "
  SELECT pid,
         now() - pg_stat_activity.query_start AS duration,
         query
  FROM pg_stat_activity
  WHERE state = 'active'
    AND now() - pg_stat_activity.query_start > interval '1 second';
"
```

**Deployment Rollback:**
```bash
# ECS rollback to previous task definition
aws ecs update-service \
  --cluster pazpaz-cluster \
  --service pazpaz-backend \
  --task-definition pazpaz-backend:PREVIOUS_REVISION

# Monitor rollback
aws ecs describe-services \
  --cluster pazpaz-cluster \
  --services pazpaz-backend \
  --query 'services[0].deployments'
```

## 📊 Monitoring & Alerts

### Key Metrics (CloudWatch)

**Application Metrics:**
- API response time (p50, p95, p99)
- Error rate (5xx responses)
- Request rate (requests/second)
- Active connections (database, Redis)

**Infrastructure Metrics:**
- CPU utilization (ECS tasks, RDS, Redis)
- Memory utilization (ECS tasks, RDS, Redis)
- Disk I/O (RDS)
- Network throughput

**Security Metrics:**
- Failed authentication attempts
- Unauthorized API access (401/403 responses)
- Secrets Manager access failures
- S3 encryption validation failures

### Alert Thresholds

**Critical Alerts (P0):**
- API health check failures (3+ consecutive failures)
- Error rate > 10% for 5 minutes
- Database connection failures
- Secrets Manager access denied errors
- S3 encryption enforcement failures

**Warning Alerts (P1):**
- API p95 response time > 500ms for 5 minutes
- CPU utilization > 80% for 5 minutes
- Memory utilization > 85% for 5 minutes
- Disk space > 85% used
- Secret rotation failures

## 📚 Reference Documentation

### Security
- [AWS Secrets Manager](/docs/deployment/AWS_SECRETS_MANAGER.md)
- [Key Rotation Procedure](/docs/security/encryption/KEY_ROTATION_PROCEDURE.md)
- [HIPAA Compliance](/docs/security/HIPAA_COMPLIANCE.md)

### Deployment
- [Production Deployment Checklist](/docs/deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md)
- [AWS IAM Roles](/docs/deployment/AWS_IAM_ROLES.md)
- [Infrastructure Security Checklist](/docs/deployment/INFRASTRUCTURE_SECURITY_CHECKLIST.md)

### Performance
- [Performance Testing Guide](/docs/performance/backend/PERFORMANCE_TESTING.md)
- [Backend Performance Benchmarks](/docs/performance/backend/README.md)

---

**Last Updated:** 2025-10-20
**Status:** Pre-Production (Infrastructure Ready)
**Coming in Week 5:** Full operational runbooks and procedures
