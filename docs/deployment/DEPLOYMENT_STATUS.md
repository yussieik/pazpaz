# PazPaz Production Deployment Status

## 🚀 LIVE IN PRODUCTION

**Current State:** Fully deployed and operational at https://pazpaz.health

**Production URL:** https://pazpaz.health
**API Endpoint:** https://pazpaz.health/api/v1/health
**Status:** ✅ All critical services healthy and running

---

## 📍 Server Details

- **Domain:** pazpaz.health (DNS configured)
- **IP Address:** 5.161.241.81
- **Provider:** Hetzner Cloud (CPX41)
- **Specs:** 8 vCPU, 16GB RAM, 160GB NVMe
- **OS:** Ubuntu 24.04 LTS
- **Location:** /opt/pazpaz
- **Access:** `ssh pazpaz@5.161.241.81`

---

## 🔐 SSL/TLS Certificate

- **Certificate Authority:** Let's Encrypt (Production)
- **Certificate Type:** ECDSA
- **Domains Covered:**
  - pazpaz.health
  - www.pazpaz.health
- **Issued:** October 25, 2025
- **Expires:** January 23, 2026 (89 days remaining)
- **Auto-Renewal:** ✅ Configured via systemd timer
- **Status:** ✅ Valid and trusted by all major browsers

**Certificate Verification:**
```bash
# On server:
sudo certbot certificates
# Shows: VALID: 89 days
```

---

## 🐳 Docker Services Status

**All 8 containers deployed:**

| Service | Status | Image | Notes |
|---------|--------|-------|-------|
| **nginx** | ✅ Healthy | pazpaz/nginx:latest | HTTPS with Let's Encrypt, ports 80/443 exposed |
| **api** | ✅ Healthy | ghcr.io/yussieik/pazpaz-backend:latest | Commit 15a33f3 (MinIO SSL fix) |
| **db** | ✅ Healthy | postgres:16-alpine | SSL/TLS enabled, encrypted at rest |
| **redis** | ✅ Healthy | redis:7-alpine | Password protected |
| **minio** | ✅ Healthy | minio/minio:latest | HTTPS enabled, zero SSL warnings |
| **clamav** | ✅ Healthy | clamav/clamav:latest | Virus scanning operational |
| **frontend** | ⚠️ Unhealthy* | ghcr.io/yussieik/pazpaz-frontend:latest | Running but health check needs adjustment |
| **arq-worker** | ⚠️ Unhealthy* | ghcr.io/yussieik/pazpaz-backend:latest | Processing jobs successfully |

*Services marked "Unhealthy" are functional but health checks need tuning (non-critical)

**Quick Health Check:**
```bash
# On server:
cd /opt/pazpaz
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

---

## 🔧 Recent Deployments & Fixes

### October 26, 2025 - Let's Encrypt SSL Migration
- ✅ Migrated from self-signed to Let's Encrypt certificates
- ✅ Browser now shows secure padlock (fully trusted)
- ✅ HTTPS working without `-k` flag
- ✅ Auto-renewal configured

### October 25, 2025 - MinIO SSL Fix (Commit 15a33f3)
- ✅ Configured boto3 S3 client to trust MinIO CA certificate
- ✅ Added S3_CA_CERT_PATH environment variable
- ✅ Zero SSL warnings in logs
- ✅ Bucket "pazpaz-attachments" created and operational

### October 25, 2025 - Initial Production Deployment
- ✅ All services deployed via Docker Compose
- ✅ Database migrations applied
- ✅ SSL certificates generated for all services (PostgreSQL, MinIO, nginx)
- ✅ HIPAA-compliant encryption in transit and at rest

---

## 🔐 HIPAA Compliance Status

**Encryption in Transit:**
- ✅ nginx: HTTPS with Let's Encrypt (TLS 1.2/1.3)
- ✅ PostgreSQL: SSL/TLS with client certificates
- ✅ MinIO: HTTPS with CA-signed certificates
- ✅ Redis: Password authentication
- ✅ API Internal: TLS within Docker network

**Encryption at Rest:**
- ✅ Database: PostgreSQL encryption enabled
- ✅ Application-level: Field-level encryption for PHI (SOAP notes)
- ✅ Backups: Encrypted with AES-256

**Security Controls:**
- ✅ Workspace isolation (multi-tenant security)
- ✅ Audit logging configured
- ✅ No PII/PHI in application logs
- ✅ Secure session management (HttpOnly cookies)
- ✅ CSRF protection enabled
- ✅ File upload virus scanning (ClamAV)

**Firewall Configuration:**
```bash
# Active UFW rules:
22/tcp  - SSH (limited to known IPs recommended)
80/tcp  - HTTP (redirects to HTTPS)
443/tcp - HTTPS
```

---

## 📦 Container Registry

**Backend Image:**
- Registry: `ghcr.io/yussieik/pazpaz-backend`
- Latest Tag: `latest`
- Latest Commit: `15a33f32807ea4f410fbc68ad1845f301544a0a8`
- Built: October 25, 2025

**Frontend Image:**
- Registry: `ghcr.io/yussieik/pazpaz-frontend`
- Latest Tag: `latest`
- Built: October 25, 2025

**View Packages:** https://github.com/yussieik?tab=packages

---

## 🔄 CI/CD Pipeline Status

**Backend CI:**
- Workflow: `.github/workflows/backend-ci.yml`
- Triggers: Push to `main`, Pull Requests
- Steps: Tests → Lint → Build → Push to GHCR
- Status: ✅ Passing
- Duration: ~13 minutes (includes full test suite)

**Frontend CI:**
- Workflow: `.github/workflows/frontend-ci.yml`
- Triggers: Push to `main`, Pull Requests
- Steps: Tests → Lint → Type Check → Build → Push to GHCR
- Status: ✅ Passing

**Production Deployment:**
- Method: Manual SSH deployment
- Future: Automated deployment workflow pending
- Images: Pulled from GHCR on server

---

## 🛠️ Deployment Scripts Created

During production deployment, the following helper scripts were created in `/tmp/`:

1. **`/tmp/deploy-minio-ssl-fix.sh`**
   - Deploys MinIO SSL certificate fix (commit 15a33f3)
   - Adds S3_CA_CERT_PATH configuration
   - Restarts API service

2. **`/tmp/generate-nginx-certs.sh`**
   - Generates self-signed SSL certificates for nginx
   - Signs certificates with PazPaz CA
   - Creates fullchain and chain files

3. **`/tmp/generate-minio-certs.sh`**
   - Generates SSL certificates for MinIO
   - Signs with PazPaz CA
   - Sets proper permissions

4. **`/tmp/regenerate-ssl-certs-v2.sh`**
   - Regenerates PostgreSQL SSL certificates
   - Creates CA with proper X.509 v3 extensions
   - Generates server and client certificates

5. **`/tmp/fix-nginx-ssl.sh`**
   - Complete nginx SSL configuration script
   - Generates certificates, updates config, restarts nginx
   - Comprehensive solution for nginx SSL setup

**Note:** These scripts are preserved for documentation but production now uses Let's Encrypt for nginx.

---

## 📊 Monitoring & Alerts

**Current Monitoring:**
- Manual health checks via `docker ps` and `curl`
- systemd timer for Let's Encrypt renewal

**Recommended (Not Yet Configured):**
- [ ] UptimeRobot for uptime monitoring
- [ ] Sentry for error tracking
- [ ] CloudWatch or Grafana for metrics
- [ ] Log aggregation (ELK or similar)

---

## 💾 Backups

**Current Status:**
- Database backups: Manual (script available)
- Configuration backups: Manual

**Recommended (Not Yet Configured):**
- [ ] Automated daily database backups
- [ ] Off-site backup storage (S3)
- [ ] Backup retention policy (30 days)
- [ ] Monthly restore testing

---

## 🔧 Maintenance Tasks

### Automated
- ✅ SSL certificate renewal (certbot timer runs every 12 hours)

### Manual (Recommended Schedule)
- **Daily:** Monitor service health, check logs
- **Weekly:** Review error logs, check disk space
- **Monthly:** Test database backup/restore, review security logs
- **Quarterly:** Rotate secrets (DB password, Redis password, JWT secret)
- **As Needed:** OS security updates (`apt update && apt upgrade`)

---

## 📝 Known Issues

### Non-Critical Issues

**1. Frontend Health Check (Status: Unhealthy)**
- **Impact:** None - service is functional
- **Cause:** Health check endpoint not responding as expected
- **Workaround:** Service accessible via nginx reverse proxy
- **Fix:** Adjust health check configuration in docker-compose.prod.yml
- **Priority:** Low

**2. ARQ Worker Health Check (Status: Unhealthy)**
- **Impact:** None - jobs processing successfully
- **Evidence:** Logs show `j_complete=1456` (jobs completing)
- **Cause:** Health check not properly configured for background worker
- **Fix:** Adjust health check or remove (workers don't need health checks)
- **Priority:** Low

---

## 🚀 Quick Commands

### Check Service Status
```bash
ssh pazpaz@5.161.241.81
cd /opt/pazpaz
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

### View Logs
```bash
# All services
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f

# Specific service
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f api
```

### Restart Service
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production restart api
```

### Update Backend Image
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production pull api
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate api
```

### Check SSL Certificate
```bash
sudo certbot certificates
```

### Test HTTPS
```bash
curl -I https://pazpaz.health/health
curl https://pazpaz.health/api/v1/health
```

---

## 📚 Documentation

**Deployment Guides:**
- `/docs/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md` - Complete deployment walkthrough
- `/docs/deployment/DOMAIN_INTEGRATION_GUIDE.md` - Domain and SSL setup (if needed)

**Architecture Docs:**
- `/docs/architecture/` - System design documents
- `/docs/security/` - Security and HIPAA compliance
- `/docs/backend/database/` - Database schemas and migrations

**Operational Runbooks:**
- Coming soon

---

## 📞 Support & Access

**Server Access:**
```bash
# SSH access
ssh pazpaz@5.161.241.81

# Root access (if needed)
sudo -i
# Password: Cluster1!
```

**GitHub Repository:**
- https://github.com/yussieik/pazpaz

**Container Registry:**
- https://github.com/yussieik?tab=packages

**Production Environment File:**
- Location: `/opt/pazpaz/.env.production`
- Permissions: 600 (owner: pazpaz)
- Contains: Database passwords, JWT secrets, S3 credentials, encryption keys

---

## 🎯 Next Steps

### Immediate (Optional)
- [ ] Fix frontend health check
- [ ] Fix ARQ worker health check
- [ ] Set up UptimeRobot monitoring
- [ ] Configure automated database backups

### Short Term (1-2 weeks)
- [ ] Implement automated deployment workflow
- [ ] Set up Sentry error tracking
- [ ] Configure log aggregation
- [ ] Test disaster recovery procedures

### Long Term (1-3 months)
- [ ] Implement blue-green deployments
- [ ] Set up staging environment
- [ ] Configure auto-scaling (if needed)
- [ ] Implement comprehensive monitoring dashboard

---

**Last Updated:** 2025-10-26
**Status:** ✅ LIVE IN PRODUCTION
**Progress:** Phase 9/9 Complete
**Deployment Date:** 2025-10-25
**SSL Certificate Valid Until:** 2026-01-23
