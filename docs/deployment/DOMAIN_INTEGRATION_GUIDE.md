# Domain Integration Guide

## Current Status

✅ **Infrastructure Ready**
- Hetzner VPS: `5.161.241.81` (CPX41: 8 vCPU, 16GB RAM)
- Ubuntu 24.04 LTS
- Docker Engine v28.5.1 & Compose v2.40.2
- Project deployed at `/opt/pazpaz`
- Environment configured (`.env.production`)
- Docker images built and pushed to GHCR
- SSH access configured for GitHub Actions

⏸️ **Waiting For**
- Domain name purchase
- DNS configuration

---

## When You Get Your Domain

Follow these steps in order. Expected total time: **30-45 minutes**

### Step 1: Purchase Domain (5 minutes)

Recommended registrars:
- **Namecheap**: $10-15/year, good UI, fast DNS
- **Cloudflare**: At-cost pricing (~$10/year), excellent DNS/security
- **Google Domains** (now Squarespace): $12/year, simple

Choose any `.com`, `.net`, or `.org` domain.

### Step 2: Configure DNS (10-15 minutes)

Add an **A record** pointing to your VPS:

```
Type: A
Name: @ (or your-domain.com)
Value: 5.161.241.81
TTL: 300 (5 minutes) or Auto
```

**Also add www subdomain:**
```
Type: CNAME
Name: www
Value: your-domain.com
TTL: 300 or Auto
```

**Wait for DNS propagation** (usually 5-15 minutes):
```bash
# Test from your local machine
dig your-domain.com +short
# Should return: 5.161.241.81

# Alternative test
nslookup your-domain.com
```

### Step 3: Update Environment Variables (2 minutes)

SSH into the server:
```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@5.161.241.81
cd /opt/pazpaz
```

Edit `.env.production`:
```bash
nano .env.production
```

Update these values:
```env
# Change from IP to domain
FRONTEND_URL=https://your-domain.com
BACKEND_URL=https://your-domain.com

# Update allowed hosts (keep IP for direct access if needed)
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,5.161.241.81,localhost

# Email configuration (update if needed)
SMTP_FROM_EMAIL=noreply@your-domain.com
```

Save and exit (Ctrl+X, Y, Enter)

### Step 4: Set Up Let's Encrypt SSL (10 minutes)

Run the SSL setup script:

```bash
cd /opt/pazpaz
sudo ./scripts/setup-ssl.sh your-domain.com
```

This script will:
1. Install certbot and dependencies
2. Request SSL certificates from Let's Encrypt
3. Configure automatic renewal (every 60 days)
4. Update nginx configuration for HTTPS
5. Set up HTTP → HTTPS redirect

**Certbot will ask for:**
- Email address (for renewal notifications)
- Agree to Terms of Service (Y)
- Share email with EFF (optional, N is fine)

### Step 5: Deploy with HTTPS (5 minutes)

Now deploy all services with SSL enabled:

```bash
cd /opt/pazpaz
./scripts/deploy.sh
```

The deploy script will:
1. Validate environment (including SSL certs)
2. Pull latest Docker images from GHCR
3. Start all 8 services with HTTPS enabled
4. Run health checks
5. Display deployment status

**Wait for all services to start** (30-60 seconds)

### Step 6: Run Database Migrations (2 minutes)

Initialize the database schema:

```bash
cd /opt/pazpaz
./scripts/migrate.sh upgrade
```

This creates all tables, indexes, and initial data.

### Step 7: Verify Deployment (2 minutes)

Check all services are healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

All 8 containers should show "Up" and "healthy":
- pazpaz-nginx
- pazpaz-frontend
- pazpaz-api
- pazpaz-arq-worker
- pazpaz-db
- pazpaz-redis
- pazpaz-minio
- pazpaz-clamav

**Test HTTPS access:**
```bash
curl -I https://your-domain.com
# Should return: HTTP/2 200
```

**Test in browser:**
1. Open `https://your-domain.com`
2. Should see PazPaz login page
3. No security warnings
4. Green padlock in address bar

### Step 8: Create Admin User (1 minute)

Create your first administrative user:

```bash
cd /opt/pazpaz
./scripts/create-admin.sh
```

Follow prompts:
- Email: your-email@domain.com
- First Name: Your Name
- Last Name: Last Name
- Workspace Name: Your Practice Name

You'll receive a magic link via email to set up your account.

### Step 9: Enable Automated Deployments (5 minutes)

Configure GitHub Actions to auto-deploy on push to `main`:

```bash
# From your local machine
cd /Users/yussieik/Desktop/projects/pazpaz

# Add production deployment secrets to GitHub
gh secret set DEPLOY_HOST --body "5.161.241.81"
gh secret set DEPLOY_USER --body "pazpaz"
gh secret set DEPLOY_SSH_KEY < ~/.ssh/pazpaz-deploy
gh secret set PRODUCTION_DOMAIN --body "your-domain.com"
```

Verify secrets are set:
```bash
gh secret list
```

**Update deployment workflow:**

Edit `.github/workflows/deploy-production.yml` and update the domain:

```yaml
env:
  PRODUCTION_DOMAIN: your-domain.com  # Update this line
```

Commit and push:
```bash
git add .github/workflows/deploy-production.yml
git commit -m "ci: configure production domain for automated deployments"
git push origin main
```

From now on, every push to `main` will automatically deploy to production.

---

## Post-Deployment Checklist

After successful deployment:

- [ ] HTTPS working with valid certificate
- [ ] HTTP redirects to HTTPS
- [ ] All 8 containers running and healthy
- [ ] Database migrations applied
- [ ] Admin user created and can log in
- [ ] Email notifications working (test magic link)
- [ ] Automated deployments configured
- [ ] SSL auto-renewal scheduled (check: `sudo certbot renew --dry-run`)

---

## Security Notes

### SSL Certificate Renewal

Certificates auto-renew via cron job. Check status:
```bash
sudo certbot certificates
sudo systemctl status certbot.timer
```

Manual renewal (if needed):
```bash
sudo certbot renew
sudo docker compose -f /opt/pazpaz/docker-compose.prod.yml restart nginx
```

### Firewall Configuration

Ensure firewall allows HTTPS:
```bash
sudo ufw status
# Should allow: 22/tcp (SSH), 80/tcp (HTTP), 443/tcp (HTTPS)

# If not configured:
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### HIPAA Compliance Checklist

With domain and HTTPS:
- ✅ Encryption in transit (TLS 1.3)
- ✅ Encryption at rest (PostgreSQL + app-level)
- ✅ Audit logging (all data access tracked)
- ✅ Workspace isolation (multi-tenant security)
- ✅ Secure session management (HttpOnly cookies)
- ✅ No data in logs (PII/PHI scrubbed)

---

## Troubleshooting

### DNS Not Resolving

**Symptoms:** `dig your-domain.com` doesn't return `5.161.241.81`

**Solutions:**
1. Wait 5-15 minutes for DNS propagation
2. Check DNS records in registrar dashboard
3. Flush local DNS cache:
   ```bash
   # macOS
   sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

   # Linux
   sudo systemd-resolve --flush-caches
   ```

### Let's Encrypt Certificate Failed

**Symptoms:** `certbot` command fails or certificate not issued

**Common causes:**
1. DNS not propagated yet → Wait and retry
2. Port 80 blocked → Check firewall: `sudo ufw status`
3. Domain not pointing to server → Verify: `dig your-domain.com +short`
4. Rate limit reached → Let's Encrypt has limits (5 certs/week per domain)

**Solution:**
```bash
# Check certbot logs
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Retry with staging (for testing)
sudo certbot certonly --staging -d your-domain.com
```

### Services Not Starting

**Symptoms:** Containers exit or restart continuously

**Diagnosis:**
```bash
docker ps -a
docker logs pazpaz-api --tail 50
docker logs pazpaz-db --tail 50
```

**Common fixes:**
1. Environment variables missing → Check `.env.production`
2. Database not ready → Wait for `pazpaz-db` to be healthy
3. Ports already in use → Stop conflicting services

### Email Not Working

**Symptoms:** Magic links not received

**Check:**
1. SMTP credentials in `.env.production`
2. ARQ worker logs: `docker logs pazpaz-arq-worker`
3. Email queue: Check Redis

**Test email:**
```bash
docker exec pazpaz-api python -c "
from pazpaz.core.email import send_magic_link
send_magic_link('test@example.com', 'test-token-123')
"
```

---

## Quick Reference

### Important Paths
```
Server:   /opt/pazpaz
Certs:    /etc/letsencrypt/live/your-domain.com/
Logs:     docker logs <container-name>
Backups:  /opt/pazpaz/backups/
```

### Important Commands
```bash
# View all containers
docker ps

# Restart services
cd /opt/pazpaz && docker compose -f docker-compose.prod.yml restart

# View logs
docker logs -f pazpaz-api

# Run migrations
cd /opt/pazpaz && ./scripts/migrate.sh upgrade

# Create backup
cd /opt/pazpaz && ./scripts/backup.sh

# Check SSL expiry
sudo certbot certificates
```

### Support Contacts

- Hetzner Support: https://console.hetzner.cloud
- Let's Encrypt Status: https://letsencrypt.status.io
- PazPaz Docs: `/Users/yussieik/Desktop/projects/pazpaz/docs/`

---

## Next Steps After Domain Setup

Once everything is deployed:

1. **Backup Configuration**
   - Document all credentials in secure location (1Password, etc.)
   - Save `.env.production` backup offline
   - Test backup/restore procedures

2. **Monitoring Setup**
   - Configure uptime monitoring (UptimeRobot, Pingdom)
   - Set up error tracking (Sentry configuration)
   - Enable log aggregation

3. **Security Hardening**
   - Review HIPAA compliance checklist
   - Enable 2FA for admin accounts
   - Schedule security audits

4. **Performance Tuning**
   - Monitor response times (target: <150ms p95)
   - Optimize database queries
   - Configure CDN if needed

5. **Operational Procedures**
   - Document incident response
   - Create runbooks for common issues
   - Train team on deployment procedures

---

**Last Updated:** 2025-10-25
**Server:** 5.161.241.81 (Hetzner VPS)
**Status:** ⏸️ Waiting for domain purchase
