# PazPaz Production Runbook

**Operational Guide for pazpaz.health**

This runbook contains procedures for operating, maintaining, and troubleshooting the PazPaz production environment.

---

## Quick Reference

**Production URL:** https://pazpaz.health
**Server IP:** 5.161.241.81
**Provider:** Hetzner Cloud CPX41
**Deploy Date:** 2025-10-25
**Last Updated:** 2025-10-26

**Key Personnel:**
- Owner/Admin: Yoseph Eikelman
- GitHub: @yussieik
- Email: yussieik@gmail.com

---

## Table of Contents

1. [Access & Authentication](#access--authentication)
2. [Service Management](#service-management)
3. [Deployment Procedures](#deployment-procedures)
4. [Monitoring & Health Checks](#monitoring--health-checks)
5. [SSL Certificate Management](#ssl-certificate-management)
6. [Database Operations](#database-operations)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)
9. [Emergency Procedures](#emergency-procedures)
10. [Maintenance Tasks](#maintenance-tasks)

---

## Access & Authentication

### SSH Access

**Standard User:**
```bash
ssh pazpaz@5.161.241.81
# Use SSH key: ~/.ssh/pazpaz-deploy
```

**Root Access:**
```bash
# From pazpaz user
sudo -i
# Password: Cluster1!
```

**Security Notes:**
- SSH key authentication configured
- Password authentication available as backup
- UFW firewall active (ports 22, 80, 443)

### Server Locations

```bash
# Application root
cd /opt/pazpaz

# Configuration
/opt/pazpaz/.env.production          # Environment variables (600 permissions)
/opt/pazpaz/docker-compose.prod.yml  # Service definitions

# Logs
/opt/pazpaz/logs/                    # Application logs (if configured)
docker logs pazpaz-api               # Container logs

# Certificates
/opt/pazpaz/backend/certs/           # PostgreSQL & CA certificates
/opt/pazpaz/backend/certs/minio/     # MinIO certificates
/etc/letsencrypt/live/pazpaz.health/ # Let's Encrypt certificates

# Scripts
/opt/pazpaz/scripts/production/      # Deployment scripts
```

---

## Service Management

### Check All Services

```bash
cd /opt/pazpaz
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

**Expected Output:**
```
NAME             STATUS
pazpaz-nginx     Up X minutes (healthy)
pazpaz-api       Up X minutes (healthy)
pazpaz-db        Up X minutes (healthy)
pazpaz-redis     Up X minutes (healthy)
pazpaz-minio     Up X minutes (healthy)
pazpaz-clamav    Up X minutes (healthy)
pazpaz-frontend  Up X minutes (unhealthy)*
pazpaz-arq-worker Up X minutes (unhealthy)*
```

*Note: frontend and arq-worker show "unhealthy" but are functional (health checks need tuning).

### Restart a Service

```bash
# Restart single service
docker compose -f docker-compose.prod.yml --env-file .env.production restart api

# Restart multiple services
docker compose -f docker-compose.prod.yml --env-file .env.production restart api nginx

# Restart all services
docker compose -f docker-compose.prod.yml --env-file .env.production restart
```

### Stop/Start Services

```bash
# Stop all services
docker compose -f docker-compose.prod.yml --env-file .env.production down

# Start all services
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Stop specific service
docker compose -f docker-compose.prod.yml --env-file .env.production stop api

# Start specific service
docker compose -f docker-compose.prod.yml --env-file .env.production start api
```

### View Service Logs

```bash
# Follow logs for all services
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f

# Follow logs for specific service
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f api

# Last N lines
docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail=100 api

# Logs since timestamp
docker compose -f docker-compose.prod.yml --env-file .env.production logs --since="2025-10-26T10:00:00" api
```

---

## Deployment Procedures

### Deploy Backend Update

**Prerequisites:**
- New image built and pushed to ghcr.io/yussieik/pazpaz-backend
- Review changes in GitHub
- Notify users of maintenance window (if necessary)

**Procedure:**
```bash
# 1. SSH to server
ssh pazpaz@5.161.241.81

# 2. Navigate to app directory
cd /opt/pazpaz

# 3. Pull new image
docker compose -f docker-compose.prod.yml --env-file .env.production pull api

# 4. Verify image was pulled
docker images | grep pazpaz-backend

# 5. Recreate API container with new image
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate api

# 6. Wait for health check
sleep 10

# 7. Check service status
docker compose -f docker-compose.prod.yml --env-file .env.production ps api

# 8. Check logs for errors
docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail=50 api

# 9. Test API health
curl https://pazpaz.health/api/v1/health
# Expected: {"status":"ok","version":"v1"}
```

**Rollback Procedure:**
```bash
# If deployment fails, roll back to previous image
docker compose -f docker-compose.prod.yml --env-file .env.production pull api:previous-tag
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate api
```

### Deploy Frontend Update

**Procedure:**
```bash
# 1-3. Same as backend (SSH, cd, pull)
docker compose -f docker-compose.prod.yml --env-file .env.production pull frontend

# 4. Recreate frontend container
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate frontend

# 5. Restart nginx (clears cache)
docker compose -f docker-compose.prod.yml --env-file .env.production restart nginx

# 6. Test frontend
curl -I https://pazpaz.health
# Expected: HTTP/2 200
```

### Run Database Migration

**Prerequisites:**
- Backend image contains new migration
- Database backup completed (see Backup section)

**Procedure:**
```bash
# 1. Enter API container
docker compose -f docker-compose.prod.yml --env-file .env.production exec api bash

# 2. Inside container - run migration
cd /app
export PYTHONPATH=/app/src
alembic upgrade head

# 3. Verify migration
alembic current

# 4. Exit container
exit
```

**Rollback Migration:**
```bash
# Inside API container
alembic downgrade -1  # Go back one migration
```

---

## Monitoring & Health Checks

### Quick Health Check

```bash
# Test HTTPS
curl -I https://pazpaz.health

# Test API
curl https://pazpaz.health/api/v1/health

# Check all service status
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

### Detailed Service Check

```bash
# Check container resource usage
docker stats --no-stream

# Check disk space
df -h

# Check memory
free -h

# Check Docker disk usage
docker system df
```

### Application Logs

```bash
# Check for errors in last hour
docker compose -f docker-compose.prod.yml --env-file .env.production logs --since="1h" | grep -i error

# Check for 5xx errors in nginx
docker compose -f docker-compose.prod.yml --env-file .env.production logs nginx | grep " 5[0-9][0-9] "

# Check database connections
docker compose -f docker-compose.prod.yml --env-file .env.production logs db | grep "connection"
```

---

## SSL Certificate Management

### Check Let's Encrypt Certificate

```bash
# Check certificate status
sudo certbot certificates

# Expected output:
# Certificate Name: pazpaz.health
# Expiry Date: 2026-01-23 (VALID: 89 days)
```

### Test Certificate Auto-Renewal

```bash
# Dry run (doesn't actually renew)
sudo certbot renew --dry-run

# Expected: "Congratulations, all simulated renewals succeeded"
```

### Force Certificate Renewal

```bash
# Only if certificate is expiring soon
sudo certbot renew --force-renewal

# Restart nginx to use new certificate
docker compose -f docker-compose.prod.yml --env-file .env.production restart nginx
```

### Check Certificate Auto-Renewal Timer

```bash
# Check if systemd timer is active
sudo systemctl list-timers | grep certbot

# Expected: certbot.timer line showing next run time
```

### Regenerate Internal Certificates

**PostgreSQL Certificates:**
```bash
cd /opt/pazpaz
sudo ./scripts/production/regenerate-ssl-certs-v2.sh

# Restart database
docker compose -f docker-compose.prod.yml --env-file .env.production restart db api
```

**MinIO Certificates:**
```bash
cd /opt/pazpaz
sudo ./scripts/production/generate-minio-certs.sh

# Restart MinIO and API
docker compose -f docker-compose.prod.yml --env-file .env.production restart minio api
```

---

## Database Operations

### Access Database

```bash
# Using docker exec
docker compose -f docker-compose.prod.yml --env-file .env.production exec db psql -U pazpaz -d pazpaz

# Or from host (if psql installed)
PGPASSWORD=<password> psql -h 5.161.241.81 -U pazpaz -d pazpaz
```

### Database Backup

**Manual Backup:**
```bash
# Create backup directory
mkdir -p /opt/pazpaz/backups

# Backup database
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_dump -U pazpaz -F c pazpaz > /opt/pazpaz/backups/pazpaz-$(date +%Y%m%d-%H%M%S).dump

# Verify backup was created
ls -lh /opt/pazpaz/backups/
```

**Backup with Compression:**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_dump -U pazpaz -F c pazpaz | gzip > /opt/pazpaz/backups/pazpaz-$(date +%Y%m%d-%H%M%S).dump.gz
```

### Database Restore

**From Backup:**
```bash
# DANGER: This will overwrite current database

# 1. Stop API and worker (prevent writes)
docker compose -f docker-compose.prod.yml --env-file .env.production stop api arq-worker

# 2. Drop and recreate database
docker compose -f docker-compose.prod.yml --env-file .env.production exec db \
  psql -U postgres -c "DROP DATABASE pazpaz;"
docker compose -f docker-compose.prod.yml --env-file .env.production exec db \
  psql -U postgres -c "CREATE DATABASE pazpaz OWNER pazpaz;"

# 3. Restore from backup
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_restore -U pazpaz -d pazpaz --no-owner --no-acl < /opt/pazpaz/backups/backup-file.dump

# 4. Restart services
docker compose -f docker-compose.prod.yml --env-file .env.production start api arq-worker
```

### Database Maintenance

**Vacuum:**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec db \
  psql -U pazpaz -d pazpaz -c "VACUUM ANALYZE;"
```

**Check Database Size:**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec db \
  psql -U pazpaz -d pazpaz -c "SELECT pg_size_pretty(pg_database_size('pazpaz'));"
```

---

## Backup & Recovery

### What to Backup

1. **Database** (critical)
   - `/opt/pazpaz/backups/*.dump`
   - Frequency: Daily
   - Retention: 30 days

2. **Configuration** (critical)
   - `/opt/pazpaz/.env.production`
   - `/opt/pazpaz/docker-compose.prod.yml`
   - `/opt/pazpaz/nginx/nginx-ssl.conf`

3. **Certificates** (important)
   - `/opt/pazpaz/backend/certs/`
   - `/etc/letsencrypt/` (backed up by certbot)

4. **User Uploads** (critical)
   - MinIO data volume
   - Location: Docker volume `pazpaz_minio_data`

### Backup MinIO Data

```bash
# Create backup directory
mkdir -p /opt/pazpaz/backups/minio

# Backup MinIO data volume
docker run --rm \
  -v pazpaz_minio_data:/data \
  -v /opt/pazpaz/backups/minio:/backup \
  alpine tar czf /backup/minio-data-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
```

### Disaster Recovery

**Full System Recovery:**

1. **Provision new server** (follow PRODUCTION_DEPLOYMENT_GUIDE.md Phase 1)

2. **Restore configuration files**
```bash
# Copy backed up files to /opt/pazpaz/
scp .env.production docker-compose.prod.yml pazpaz@NEW_IP:/opt/pazpaz/
```

3. **Regenerate certificates**
```bash
sudo ./scripts/production/regenerate-ssl-certs-v2.sh
sudo ./scripts/production/generate-minio-certs.sh
```

4. **Start services**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

5. **Restore database**
```bash
# See "Database Restore" section above
```

6. **Restore MinIO data**
```bash
docker run --rm \
  -v pazpaz_minio_data:/data \
  -v /opt/pazpaz/backups/minio:/backup \
  alpine tar xzf /backup/minio-data-TIMESTAMP.tar.gz -C /data
```

7. **Setup Let's Encrypt**
```bash
# Follow Let's Encrypt setup in PRODUCTION_DEPLOYMENT_GUIDE.md
```

---

## Troubleshooting

### Service Won't Start

**Symptoms:** Container immediately exits or restarts

**Diagnosis:**
```bash
# Check container exit code
docker ps -a | grep pazpaz

# Check logs
docker compose -f docker-compose.prod.yml --env-file .env.production logs SERVICE_NAME

# Check if port is already in use
sudo netstat -tulpn | grep PORT_NUMBER
```

**Common Causes:**
1. **Missing environment variables** - Check `.env.production`
2. **Port conflict** - Another service using the port
3. **Volume permission issues** - Check ownership: `ls -la /opt/pazpaz/`
4. **Database connection failure** - Verify DB is running and credentials are correct

### High CPU/Memory Usage

**Diagnosis:**
```bash
# Check container resource usage
docker stats

# Check processes inside container
docker compose -f docker-compose.prod.yml --env-file .env.production exec api top
```

**Solutions:**
- Restart container
- Check for slow queries in database
- Review application logs for errors
- Consider scaling if persistent

### Database Connection Errors

**Symptoms:** API logs show "could not connect to server"

**Diagnosis:**
```bash
# Check if database is running
docker compose -f docker-compose.prod.yml --env-file .env.production ps db

# Test database connection
docker compose -f docker-compose.prod.yml --env-file .env.production exec db psql -U pazpaz -d pazpaz -c "SELECT 1;"
```

**Solutions:**
1. Restart database: `docker compose restart db`
2. Check database logs: `docker compose logs db`
3. Verify connection string in `.env.production`
4. Check if database volume is full: `df -h`

### SSL Certificate Errors

**Symptoms:** Browser shows "Your connection is not private"

**Diagnosis:**
```bash
# Check certificate status
sudo certbot certificates

# Test HTTPS
curl -vI https://pazpaz.health 2>&1 | grep -i "ssl\\|certificate"
```

**Solutions:**
1. Renew Let's Encrypt certificate: `sudo certbot renew --force-renewal`
2. Restart nginx: `docker compose restart nginx`
3. Check nginx configuration: `docker compose exec nginx nginx -t`

### Disk Space Full

**Symptoms:** Services failing, "no space left on device" errors

**Diagnosis:**
```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Find large directories
du -sh /opt/pazpaz/* | sort -h
```

**Solutions:**
```bash
# Clean Docker system
docker system prune -a --volumes

# Remove old backups
find /opt/pazpaz/backups -type f -mtime +30 -delete

# Remove old logs
docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail=0 api
```

---

## Emergency Procedures

### Complete Service Outage

**Steps:**

1. **Assess situation**
```bash
ssh pazpaz@5.161.241.81
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

2. **Restart all services**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production restart
```

3. **If restart fails, rebuild**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

4. **Check logs**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
```

5. **Test endpoints**
```bash
curl https://pazpaz.health/api/v1/health
```

### Data Corruption

**Steps:**

1. **Stop services immediately**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

2. **Backup current state**
```bash
cp -r /opt/pazpaz /opt/pazpaz.backup-$(date +%Y%m%d-%H%M%S)
```

3. **Restore from latest backup** (see Backup & Recovery section)

4. **Investigate root cause** before restarting

### Security Breach

**Steps:**

1. **Isolate system**
```bash
sudo ufw deny from any to any
# Keep only your IP: sudo ufw allow from YOUR_IP
```

2. **Stop services**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

3. **Preserve evidence**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs > /tmp/incident-logs-$(date +%Y%m%d-%H%M%S).txt
```

4. **Investigate and remediate**
- Review access logs
- Check for unauthorized changes
- Rotate all secrets
- Update `.env.production` with new credentials

5. **Restore from clean backup if compromised**

6. **Re-enable firewall properly**
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Maintenance Tasks

### Daily

**Automated:**
- Let's Encrypt renewal check (via systemd timer)

**Manual:**
- Check service health: `docker compose ps`
- Review error logs: `docker compose logs --since="24h" | grep -i error`

### Weekly

- Check disk space: `df -h`
- Review nginx access logs for anomalies
- Verify backups are being created
- Check container resource usage: `docker stats --no-stream`

### Monthly

- Review and clean old backups
- Test backup restore procedure
- Update OS packages: `sudo apt update && sudo apt upgrade`
- Review security logs
- Test disaster recovery plan

### Quarterly (Every 90 Days)

- Rotate secrets:
  - Database password
  - Redis password
  - JWT secret
  - Encryption master key
- Review and update firewall rules
- Security audit
- Performance review

### Certificate Maintenance

**Let's Encrypt (automated):**
- Renewal: Every 60 days (auto via certbot)
- Expiry check: Run `sudo certbot certificates`

**Internal Certificates (manual):**
- Validity: 10 years
- Rotation: Only if compromised or before expiry

---

## Related Documentation

- `/DEPLOYMENT_STATUS.md` - Current production status
- `/docs/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md` - Initial deployment guide
- `/scripts/production/README.md` - Deployment scripts documentation
- `.github/workflows/` - CI/CD workflows

---

## Support Contacts

**Technical Owner:** Yussie (yussieik@gmail.com)
**Server Provider:** Hetzner Cloud
**Domain Registrar:** [Check DNS records]
**SSL Provider:** Let's Encrypt (automated)

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2025-10-26 | Initial runbook created | Claude |
| 2025-10-26 | Added SSL certificate procedures | Claude |
| 2025-10-26 | Added backup/recovery procedures | Claude |

---

**Last Reviewed:** 2025-10-26
**Next Review:** 2025-11-26
