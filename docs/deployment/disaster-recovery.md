# PazPaz Disaster Recovery Plan

## Table of Contents

1. [Overview](#overview)
2. [Recovery Objectives](#recovery-objectives)
3. [Backup Strategy](#backup-strategy)
4. [Disaster Scenarios](#disaster-scenarios)
5. [Recovery Procedures](#recovery-procedures)
6. [Testing and Validation](#testing-and-validation)
7. [Contact Information](#contact-information)
8. [Appendix](#appendix)

---

## Overview

This document outlines the disaster recovery (DR) procedures for the PazPaz practice management system. It provides step-by-step instructions for recovering from various failure scenarios while maintaining HIPAA compliance and minimizing data loss.

### Scope

This DR plan covers:
- Database recovery from backups
- Application recovery from container failures
- Infrastructure recovery from server failures
- Security incident response procedures
- Data corruption recovery
- Network failure mitigation

### Responsibilities

- **DevOps Team**: Infrastructure recovery, backup management
- **Security Team**: Security incident response, access control
- **Database Admin**: Database recovery, data integrity
- **On-Call Engineer**: Initial response, escalation
- **Management**: Communication, decision making

## Recovery Objectives

### Recovery Time Objective (RTO)

**Target: 2 hours** - Maximum acceptable downtime

| Component | RTO | Priority |
|-----------|-----|----------|
| Database | 30 min | Critical |
| API Services | 45 min | Critical |
| Frontend | 60 min | High |
| Background Jobs | 90 min | Medium |
| File Storage | 120 min | Medium |

### Recovery Point Objective (RPO)

**Target: 24 hours** - Maximum acceptable data loss

| Data Type | RPO | Backup Frequency |
|-----------|-----|------------------|
| Database | 24 hours | Daily at 2 AM |
| File Attachments | 24 hours | Continuous to S3 |
| Configurations | 0 hours | Version controlled |
| Audit Logs | 1 hour | Streamed to S3 |

## Backup Strategy

### Backup Schedule

```bash
# Daily Backups - 2:00 AM UTC
0 2 * * * /opt/pazpaz/scripts/backup-db.sh daily

# Weekly Full Backups - Sundays 3:00 AM UTC
0 3 * * 0 /opt/pazpaz/scripts/backup-db.sh weekly

# Monthly Archives - 1st of month 4:00 AM UTC
0 4 1 * * /opt/pazpaz/scripts/backup-db.sh monthly

# Automated Testing - First Sunday 5:00 AM UTC
0 5 1-7 * 0 /opt/pazpaz/scripts/test-backup-restore.sh
```

### Backup Locations

1. **Local Storage**: `/var/backups/pazpaz/`
   - Daily: 7 days retention
   - Weekly: 4 weeks retention
   - Monthly: 12 months retention

2. **S3/Cloud Storage**: `s3://pazpaz-backups/`
   - Encrypted at rest (AES-256)
   - Versioning enabled
   - Cross-region replication (if configured)
   - Lifecycle policies for automatic cleanup

3. **Backup Encryption**:
   - GPG encryption with dedicated backup key
   - Key stored separately from backups
   - Regular key rotation (quarterly)

## Disaster Scenarios

### 1. Database Corruption

**Symptoms**:
- Application errors referencing database
- Data inconsistencies
- Failed health checks
- Slow queries or timeouts

**Impact**: Critical - Complete service outage

### 2. Server Hardware Failure

**Symptoms**:
- Server unreachable
- No response to health checks
- Infrastructure monitoring alerts

**Impact**: Critical - Complete service outage

### 3. Ransomware/Security Breach

**Symptoms**:
- Encrypted files
- Unauthorized access in audit logs
- Modified system files
- Ransom messages

**Impact**: Critical - Data compromise + service outage

### 4. Accidental Data Deletion

**Symptoms**:
- Missing records
- User reports of lost data
- Audit logs showing DELETE operations

**Impact**: High - Partial data loss

### 5. Network Failure

**Symptoms**:
- Services cannot communicate
- External access blocked
- DNS resolution failures

**Impact**: High - Service degradation or outage

## Recovery Procedures

### 1. Database Recovery from Backup

#### Prerequisites
- Access to backup files (local or S3)
- GPG key for decryption
- Database credentials
- Sufficient disk space

#### Procedure

```bash
# 1. Stop application to prevent data corruption
cd /opt/pazpaz
docker-compose -f docker-compose.prod.yml stop api arq-worker

# 2. Identify latest valid backup
ls -la /var/backups/pazpaz/daily/
# Or from S3:
aws s3 ls s3://pazpaz-backups/database/daily/

# 3. Create recovery point (backup current state if possible)
docker exec pazpaz-db pg_dump -U pazpaz -d pazpaz -Fc > /tmp/pazpaz-prerecovery-$(date +%Y%m%d-%H%M%S).dump

# 4. Decrypt backup file
gpg --decrypt /var/backups/pazpaz/daily/pazpaz-daily-20240324-020000.dump.gpg > /tmp/restore.dump

# 5. Drop and recreate database
docker exec pazpaz-db psql -U pazpaz -c "DROP DATABASE IF EXISTS pazpaz;"
docker exec pazpaz-db psql -U pazpaz -c "CREATE DATABASE pazpaz WITH ENCODING='UTF8';"

# 6. Restore from backup
pg_restore \
    --host=localhost \
    --port=5432 \
    --username=pazpaz \
    --dbname=pazpaz \
    --no-owner \
    --no-privileges \
    --verbose \
    /tmp/restore.dump

# 7. Verify restoration
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT COUNT(*) FROM users;"
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT COUNT(*) FROM appointments;"

# 8. Run any missing migrations
cd /opt/pazpaz/backend
docker-compose -f ../docker-compose.prod.yml run --rm api alembic upgrade head

# 9. Restart services
cd /opt/pazpaz
docker-compose -f docker-compose.prod.yml start api arq-worker

# 10. Verify application functionality
curl -f http://localhost/api/v1/health
```

#### Post-Recovery
1. Run comprehensive health checks
2. Verify data integrity
3. Check recent transactions
4. Notify users of potential data loss
5. Document incident and recovery time

### 2. Complete Server Recovery

#### Prerequisites
- New server provisioned
- Access to configuration repository
- Backup access (S3 credentials)
- SSL certificates
- Environment variables

#### Procedure

```bash
# 1. Provision new server (Ubuntu 22.04 LTS recommended)
# Via your cloud provider's console or CLI

# 2. Install Docker and dependencies
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
sudo apt-get update && sudo apt-get install -y git awscli postgresql-client

# 3. Clone repository
git clone https://github.com/yourusername/pazpaz.git /opt/pazpaz
cd /opt/pazpaz

# 4. Restore environment configuration
# Copy .env.production from secure storage or recreate
aws s3 cp s3://pazpaz-configs/.env.production .env.production
# Or use secrets manager:
aws secretsmanager get-secret-value --secret-id pazpaz/production/env --query SecretString --output text > .env.production

# 5. Restore SSL certificates
mkdir -p certs
aws s3 sync s3://pazpaz-configs/certs/ certs/

# 6. Pull Docker images
docker-compose -f docker-compose.prod.yml pull

# 7. Start infrastructure services first
docker-compose -f docker-compose.prod.yml up -d db redis minio

# 8. Wait for database to be ready
until docker exec pazpaz-db pg_isready -U pazpaz; do
    echo "Waiting for database..."
    sleep 5
done

# 9. Restore database from backup
./scripts/backup-db.sh --restore --backup-file s3://pazpaz-backups/database/latest.dump.gpg

# 10. Start application services
docker-compose -f docker-compose.prod.yml up -d

# 11. Verify all services are running
docker-compose -f docker-compose.prod.yml ps
curl -f http://localhost/api/v1/health

# 12. Update DNS to point to new server
# Via your DNS provider's console
```

### 3. Security Breach Response

#### Immediate Actions (First 15 minutes)

```bash
# 1. ISOLATE affected systems
# Disconnect from network if possible
sudo iptables -I INPUT -j DROP
sudo iptables -I OUTPUT -j DROP
# Allow only SSH for management
sudo iptables -I INPUT -p tcp --dport 22 -j ACCEPT

# 2. PRESERVE evidence
# Create forensic snapshot
dd if=/dev/sda of=/mnt/forensics/disk-image-$(date +%Y%m%d-%H%M%S).img bs=4M

# 3. ASSESS scope
# Check audit logs
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT * FROM audit_events WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at DESC;"

# Check system logs
journalctl -u docker --since "24 hours ago" > /tmp/docker-logs.txt
grep -r "unauthorized\|breach\|attack" /var/log/

# 4. NOTIFY stakeholders
# - Security team
# - Management
# - Legal/Compliance (if PHI affected)
# - Users (if required by HIPAA)
```

#### Recovery Actions

```bash
# 1. Rotate ALL credentials
./scripts/rotate-secrets.sh --all --emergency

# 2. Restore from known-good backup (pre-breach)
# Identify breach time from logs
BREACH_TIME="2024-03-24 10:00:00"

# Find last good backup before breach
aws s3 ls s3://pazpaz-backups/database/ --recursive | grep -B 100 "$BREACH_TIME" | tail -1

# 3. Rebuild infrastructure
# Deploy fresh containers
docker-compose -f docker-compose.prod.yml down
docker system prune -af
docker-compose -f docker-compose.prod.yml up -d

# 4. Apply security patches
apt-get update && apt-get upgrade -y
docker pull --all-tags

# 5. Enhance monitoring
# Add additional security monitoring
# Update WAF rules
# Enable additional audit logging

# 6. Verify system integrity
# Run security scan
docker run --rm aquasec/trivy image ghcr.io/yourusername/pazpaz/backend:latest
```

### 4. Data Corruption Recovery

#### Identify Corruption

```bash
# 1. Check database integrity
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "
    SELECT schemaname, tablename
    FROM pg_tables
    WHERE schemaname = 'public'
" | while read schema table; do
    echo "Checking $table..."
    docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT COUNT(*) FROM $table;" || echo "ERROR: $table corrupted"
done

# 2. Run consistency checks
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "
    -- Check referential integrity
    SELECT
        conname AS constraint_name,
        conrelid::regclass AS table_name,
        confrelid::regclass AS referenced_table
    FROM pg_constraint
    WHERE contype = 'f'
    AND NOT EXISTS (
        SELECT 1 FROM pg_constraint c2
        WHERE c2.oid = pg_constraint.confrelid
    );
"
```

#### Recovery Procedure

```bash
# 1. Attempt repair with PostgreSQL tools
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "REINDEX DATABASE pazpaz;"
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "VACUUM FULL ANALYZE;"

# 2. If repair fails, restore specific tables
# Export non-corrupted data
docker exec pazpaz-db pg_dump -U pazpaz -d pazpaz -t users -t workspaces > /tmp/good-data.sql

# Restore from backup
./scripts/test-backup-restore.sh --backup-file /var/backups/pazpaz/latest.dump.gpg

# Re-import good data
docker exec -i pazpaz-db psql -U pazpaz -d pazpaz < /tmp/good-data.sql

# 3. Validate data consistency
./scripts/test-backup-restore.sh --full-validation
```

## Testing and Validation

### Monthly DR Testing Schedule

| Week | Test Type | Procedure |
|------|-----------|-----------|
| 1st Sunday | Backup Restore | `./scripts/test-backup-restore.sh` |
| 2nd Week | Failover Test | Simulate server failure |
| 3rd Week | Security Drill | Breach response exercise |
| 4th Week | Review & Update | Update DR documentation |

### Validation Checklist

After any recovery procedure:

- [ ] All services are running (`docker-compose ps`)
- [ ] Health checks passing (`curl http://localhost/api/v1/health`)
- [ ] Database accessible and queries working
- [ ] User authentication functional
- [ ] Critical business functions tested:
  - [ ] User login
  - [ ] Appointment creation
  - [ ] Session note saving
  - [ ] File upload/download
- [ ] Monitoring and alerting operational
- [ ] Backup schedule resumed
- [ ] Audit logging functional
- [ ] Performance within acceptable limits (p95 < 150ms)

### Recovery Time Recording

Document actual recovery times for continuous improvement:

```bash
# Log recovery event
cat >> /var/log/pazpaz/dr-events.log << EOF
Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Incident: [Type of incident]
Detection Time: [When detected]
Recovery Started: [Start time]
Recovery Completed: [End time]
Total Downtime: [Duration]
Data Loss: [Amount if any]
Root Cause: [Brief description]
Actions Taken: [Summary]
Lessons Learned: [Improvements needed]
EOF
```

## Contact Information

### Emergency Contacts

| Role | Name | Primary Contact | Backup Contact |
|------|------|-----------------|----------------|
| On-Call Engineer | [Name] | [Phone] | [Email] |
| DevOps Lead | [Name] | [Phone] | [Email] |
| Database Admin | [Name] | [Phone] | [Email] |
| Security Lead | [Name] | [Phone] | [Email] |
| CTO/VP Engineering | [Name] | [Phone] | [Email] |

### External Contacts

| Service | Contact | Account # | Support Level |
|---------|---------|-----------|---------------|
| Cloud Provider | [Provider] | [Account] | [24/7 Phone] |
| DNS Provider | [Provider] | [Account] | [Support URL] |
| SSL Certificate | [Provider] | [Account] | [Support] |
| Monitoring Service | [Provider] | [Account] | [Status Page] |

### Escalation Path

1. **Level 1** (0-15 min): On-Call Engineer
2. **Level 2** (15-30 min): DevOps Lead + Database Admin
3. **Level 3** (30-60 min): Security Lead (if breach)
4. **Level 4** (60+ min): CTO/VP Engineering
5. **Level 5** (2+ hours): CEO (if customer impact)

## Appendix

### A. Quick Commands Reference

```bash
# Check system status
docker-compose -f docker-compose.prod.yml ps
docker stats --no-stream

# View recent logs
docker logs --tail 100 -f pazpaz-api
docker logs --tail 100 -f pazpaz-db

# Database operations
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT version();"
docker exec pazpaz-db pg_isready -U pazpaz

# Backup operations
./scripts/backup-db.sh daily
./scripts/test-backup-restore.sh
./scripts/backup-cleanup.sh --dry-run

# Emergency shutdown
docker-compose -f docker-compose.prod.yml stop

# Emergency startup
docker-compose -f docker-compose.prod.yml up -d
```

### B. Configuration Files

Key configuration files and their locations:

- Production environment: `/opt/pazpaz/.env.production`
- Docker Compose: `/opt/pazpaz/docker-compose.prod.yml`
- Nginx config: `/opt/pazpaz/nginx/nginx.conf`
- Backup scripts: `/opt/pazpaz/scripts/backup-*.sh`
- SSL certificates: `/opt/pazpaz/certs/`

### C. Monitoring URLs

- Health Check: `http://[server]/api/v1/health`
- Metrics: `http://[server]/api/v1/metrics`
- Admin Panel: `http://[server]/admin/` (if enabled)
- Monitoring Dashboard: `[UptimeRobot/StatusPage URL]`

### D. HIPAA Compliance Notes

When recovering from any incident involving PHI:

1. **Document** all access to PHI during recovery
2. **Notify** compliance officer within 24 hours
3. **Assess** if breach notification is required
4. **Preserve** audit logs for investigation
5. **Report** to HHS if required (within 60 days)

### E. Lessons Learned Template

After each incident or DR test:

```markdown
## Incident/Test Date: [DATE]

### What Went Well
- [List successes]

### What Went Wrong
- [List failures]

### Action Items
- [ ] [Improvement 1]
- [ ] [Improvement 2]

### Documentation Updates Needed
- [ ] [Update 1]
- [ ] [Update 2]

### Training Needs Identified
- [ ] [Training 1]
- [ ] [Training 2]
```

---

**Last Updated**: October 2024
**Next Review**: January 2025
**Document Owner**: DevOps Team
**Classification**: Confidential - Internal Use Only