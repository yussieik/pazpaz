# Production Deployment Scripts

This directory contains shell scripts used during the production deployment of PazPaz to pazpaz.health (October 25-26, 2025).

## Scripts Overview

### 1. regenerate-ssl-certs-v2.sh
**Purpose:** Generate self-signed SSL certificates for PostgreSQL with proper X.509 v3 extensions.

**What it does:**
- Creates a Certificate Authority (CA) with proper key usage extensions
- Generates server certificates for PostgreSQL (CN=db)
- Generates client certificates for application (CN=pazpaz)
- Sets proper file permissions and ownership
- Backs up existing certificates before regeneration

**Usage:**
```bash
cd /opt/pazpaz
sudo ./scripts/production/regenerate-ssl-certs-v2.sh
```

**Output:**
- `/opt/pazpaz/backend/certs/ca-cert.pem` - CA certificate
- `/opt/pazpaz/backend/certs/ca-key.pem` - CA private key
- `/opt/pazpaz/backend/certs/server-cert.pem` - PostgreSQL server certificate
- `/opt/pazpaz/backend/certs/server-key.pem` - PostgreSQL server private key
- `/opt/pazpaz/backend/certs/client-cert.pem` - Client certificate
- `/opt/pazpaz/backend/certs/client-key.pem` - Client private key

**HIPAA Compliance:** Required for encryption of PHI data in transit to/from PostgreSQL.

---

### 2. generate-minio-certs.sh
**Purpose:** Generate SSL certificates for MinIO signed by the PazPaz CA.

**What it does:**
- Verifies CA exists (requires regenerate-ssl-certs-v2.sh to be run first)
- Generates MinIO private key and certificate request
- Signs certificate with PazPaz CA
- Creates proper Subject Alternative Names (SAN) for minio, localhost, pazpaz-minio
- Backs up existing MinIO certificates

**Usage:**
```bash
cd /opt/pazpaz
sudo ./scripts/production/generate-minio-certs.sh
```

**Output:**
- `/opt/paz paz/backend/certs/minio/public.crt` - MinIO public certificate
- `/opt/pazpaz/backend/certs/minio/private.key` - MinIO private key
- `/opt/pazpaz/backend/certs/minio/ca-cert.pem` - CA certificate copy

**HIPAA Compliance:** Required for encryption of PHI file attachments in transit to/from MinIO.

---

### 3. generate-nginx-certs.sh
**Purpose:** Generate self-signed SSL certificates for nginx signed by the PazPaz CA.

**What it does:**
- Verifies CA exists
- Generates nginx private key and certificate request for pazpaz.health
- Signs certificate with PazPaz CA
- Creates fullchain.pem (certificate + CA chain)
- Includes SAN for pazpaz.health, www.pazpaz.health, localhost

**Usage:**
```bash
cd /opt/pazpaz
sudo ./scripts/production/generate-nginx-certs.sh
```

**Output:**
- `/opt/pazpaz/ssl/privkey.pem` - nginx private key
- `/opt/pazpaz/ssl/cert.pem` - nginx certificate
- `/opt/pazpaz/ssl/fullchain.pem` - Certificate + CA chain
- `/opt/pazpaz/ssl/chain.pem` - CA certificate

**Note:** This script was used for initial deployment but production now uses Let's Encrypt certificates.

---

### 4. fix-nginx-ssl.sh
**Purpose:** Complete nginx SSL configuration script (all-in-one solution).

**What it does:**
- Generates nginx SSL certificates
- Backs up existing nginx.conf
- Writes complete nginx configuration with HIPAA-compliant security headers
- Restarts nginx with new configuration
- Verifies deployment and checks logs

**Usage:**
```bash
cd /opt/pazpaz
sudo ./scripts/production/fix-nginx-ssl.sh
```

**Features:**
- HTTP → HTTPS redirect
- HSTS, CSP, X-Frame-Options, X-Content-Type-Options headers
- API proxy configuration (/api/)
- WebSocket proxy (/ws/)
- Frontend SPA routing
- Gzip compression

**Note:** This was used for initial setup with self-signed certificates. Production now uses Let's Encrypt.

---

### 5. deploy-minio-ssl-fix.sh
**Purpose:** Deploy MinIO SSL certificate fix (commit 15a33f3).

**What it does:**
- Pulls updated backend image from GitHub Container Registry
- Adds S3_CA_CERT_PATH environment variable to .env.production
- Verifies CA certificate exists
- Restarts API service with new configuration
- Checks for SSL warnings in logs

**Usage:**
```bash
cd /opt/pazpaz
./scripts/production/deploy-minio-ssl-fix.sh
```

**Fix Applied:**
Configures boto3 S3 client to trust MinIO's self-signed CA certificate, eliminating SSL verification warnings.

**Environment Variable Added:**
```bash
S3_CA_CERT_PATH=/app/certs/ca-cert.pem
```

---

## Deployment Timeline

### October 25, 2025
1. **Initial Infrastructure Setup**
   - Ran `regenerate-ssl-certs-v2.sh` to create CA and PostgreSQL certificates
   - Ran `generate-minio-certs.sh` to create MinIO certificates
   - Ran `generate-nginx-certs.sh` to create initial nginx certificates

2. **MinIO SSL Fix Deployment**
   - Deployed commit 15a33f3 with `deploy-minio-ssl-fix.sh`
   - Zero SSL warnings achieved

### October 26, 2025
3. **Let's Encrypt Migration**
   - Obtained Let's Encrypt certificates for pazpaz.health
   - Updated nginx configuration to use Let's Encrypt
   - Production now uses browser-trusted certificates

---

## Production Status

**Current Certificate Setup:**
- ✅ **PostgreSQL:** Self-signed CA (internal communication)
- ✅ **MinIO:** Self-signed CA (internal communication)
- ✅ **nginx (public):** Let's Encrypt (browser-trusted)

**Scripts Usage:**
- Scripts 1-4: Used for initial deployment, preserved for disaster recovery
- Script 5: Successfully deployed, can be reused for future MinIO SSL updates

---

## When to Use These Scripts

### Disaster Recovery
If you need to rebuild the production environment from scratch:
1. Run `regenerate-ssl-certs-v2.sh` first (creates CA)
2. Run `generate-minio-certs.sh` (MinIO SSL)
3. Deploy services with docker-compose
4. Run `deploy-minio-ssl-fix.sh` (configure boto3 CA trust)
5. Set up Let's Encrypt for nginx (see /docs/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md)

### Staging Environment
Use these scripts to set up a staging environment with self-signed certificates (no Let's Encrypt needed).

### Certificate Rotation
If you need to rotate internal certificates:
1. Run the appropriate script (regenerate-ssl-certs-v2.sh, generate-minio-certs.sh)
2. Restart affected services

---

## Security Notes

**Certificate Validity:**
- All self-signed certificates: 10 years (3650 days)
- Let's Encrypt certificates: 90 days (auto-renew configured)

**File Permissions:**
- Private keys: 600 (owner read/write only)
- Public certificates: 644 (world-readable)
- Ownership: pazpaz:pazpaz (or postgres:postgres for DB certs)

**HIPAA Compliance:**
All scripts implement SSL/TLS encryption required for PHI data in transit (§164.312(e)(1)).

---

## Troubleshooting

### "CA certificates not found"
Run `regenerate-ssl-certs-v2.sh` first to create the CA before running other scripts.

### "Permission denied"
Scripts that create certificates in /opt/pazpaz require sudo:
```bash
sudo ./scripts/production/script-name.sh
```

### Certificate verification failures
After regenerating certificates, restart all affected services:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production restart db minio api
```

---

## Related Documentation

- `/DEPLOYMENT_STATUS.md` - Current production status
- `/docs/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md` - Complete deployment guide
- `/docs/deployment/PRODUCTION_RUNBOOK.md` - Operational runbook

---

**Last Updated:** 2025-10-26
**Production Environment:** pazpaz.health
**Backend Commit:** 15a33f3
