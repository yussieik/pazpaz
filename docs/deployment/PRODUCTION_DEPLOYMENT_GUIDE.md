# PazPaz Production Deployment Guide

**Owner's Manual for First-Time Production Setup**

This guide walks you through setting up PazPaz in production from scratch. Follow these steps in order.

---

## 🎉 PRODUCTION STATUS: DEPLOYED & LIVE

**Current Status:** PazPaz is **LIVE IN PRODUCTION** at https://pazpaz.health

This guide serves as both:
1. **Reference Documentation** - How the production environment was set up
2. **Future Deployment Guide** - Steps for setting up additional environments (staging, DR)

### Quick Production Summary

- **✅ Status:** Live and operational
- **🌐 URL:** https://pazpaz.health
- **🔐 SSL:** Let's Encrypt (valid until Jan 23, 2026)
- **🖥️ Server:** Hetzner Cloud CPX41 (5.161.241.81)
- **📦 Backend Commit:** 15a33f3 (MinIO SSL fix)
- **✅ HIPAA Compliance:** Full encryption in transit and at rest
- **⏱️ Deployed:** October 25-26, 2025

**For current production status, see:** `/DEPLOYMENT_STATUS.md`

---

## Prerequisites Checklist

Before starting, make sure you have:
- [ ] GitHub repository access (you're the owner)
- [ ] Credit card for Hetzner VPS ($22/month)
- [ ] Credit card for domain registration ($10-15/year) - **OPTIONAL for initial testing**
- [ ] GitHub CLI installed on your local machine
- [ ] SSH client on your local machine
- [ ] 2-3 hours of time to complete setup

---

## Deployment Paths: Choose Your Approach

You have two options for deploying PazPaz:

### Path A: Quick Deploy (HTTP Only) - **Recommended for Testing**
**Time:** 1.5 hours | **Access:** `http://YOUR_SERVER_IP`

✅ **Pros:**
- Faster setup (skip domain purchase and DNS wait)
- Test everything immediately
- Easy to add domain/SSL later (5-10 minutes)

❌ **Cons:**
- HTTP only (no HTTPS/SSL)
- Not HIPAA-compliant (don't use with real patient data)
- Access via IP address only

**Best for:** Testing, development, evaluation before going live

---

### Path B: Full Production Deploy (HTTPS)
**Time:** 2-3 hours | **Access:** `https://yourdomain.com`

✅ **Pros:**
- HIPAA-compliant with SSL/HTTPS
- Professional domain name
- Production-ready from day one

❌ **Cons:**
- Requires domain purchase (~$12/year)
- Need to wait for DNS propagation (10-30 minutes)
- 30 minutes extra setup time

**Best for:** Production use with real patients, going live immediately

---

**This guide covers BOTH paths.** Follow the instructions below and skip phases marked **[OPTIONAL]** if you're doing Path A.

---

## Phase 1: Provision Production Server

**Estimated Time:** 30 minutes

### Step 1.1: Create Hetzner Account and VPS

1. Go to https://www.hetzner.com/cloud
2. Click "Sign Up" and create an account
3. Verify your email address
4. Add payment method (credit card)
5. Create a new project called "PazPaz Production"

### Step 1.2: Provision the Server

1. Click "Add Server"
2. **Location:** Choose closest to your users (e.g., US East for USA)
3. **Image:** Ubuntu 24.04 LTS
4. **Type:** CPX41 (8 vCPU, 16GB RAM, 240GB SSD) - €20.46/month
5. **Networking:** Leave defaults (IPv4 + IPv6)
6. **SSH Keys:** Skip for now (we'll set up later)
7. **Name:** pazpaz-production
8. Click "Create & Buy Now"

**Important:** Write down the server IP address (will be shown after creation)

```
Server IP: 5.161.241.81
```

### Step 1.3: Initial Server Access

Open your terminal and SSH to the server:

```bash
# Replace with your actual server IP
ssh root@YOUR_SERVER_IP

# Use the root password from Hetzner email
```

### Step 1.4: Create Deployment User

On the server, run:

```bash
# Create pazpaz user
adduser pazpaz
# Set a strong password when prompted

# Add to sudo group
usermod -aG sudo pazpaz

# Create home directory structure
mkdir -p /home/pazpaz/.ssh
chown -R pazpaz:pazpaz /home/pazpaz/.ssh
chmod 700 /home/pazpaz/.ssh
```

### Step 1.5: Install Docker

Still on the server as root:

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Add pazpaz user to docker group
usermod -aG docker pazpaz

# Enable Docker on boot
systemctl enable docker
systemctl start docker

# Verify Docker is running
docker --version
docker compose version
```

Expected output:
```
Docker version 24.x.x
Docker Compose version v2.x.x
```

### Step 1.6: Configure Firewall

```bash
# Enable UFW firewall
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable

# Check status
ufw status
```

Expected output:
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

### Step 1.7: Create Production Directories

```bash
# Create application directories
mkdir -p /opt/pazpaz/{logs,backups,ssl,scripts,data}
chown -R pazpaz:pazpaz /opt/pazpaz
chmod 755 /opt/pazpaz

# Verify
ls -la /opt/pazpaz
```

### Step 1.8: Exit and Test Access

```bash
# Exit root session
exit

# Test pazpaz user access
ssh pazpaz@YOUR_SERVER_IP

# Should be able to login with password
```

**✅ Phase 1 Complete!** You now have a production server ready.

---

## Phase 2: Set Up SSH Keys for GitHub Actions

**Estimated Time:** 15 minutes

### Step 2.1: Generate SSH Key Pair (On Your Local Machine)

Open terminal on your Mac:

```bash
# Generate ED25519 SSH key
ssh-keygen -t ed25519 -f ~/.ssh/pazpaz-deploy -C "github-actions@pazpaz"

# When prompted:
# - Enter passphrase: Press Enter (no passphrase for automation)
# - Confirm: Press Enter

# Verify keys were created
ls -la ~/.ssh/pazpaz-deploy*
```

You should see:
```
~/.ssh/pazpaz-deploy       (private key)
~/.ssh/pazpaz-deploy.pub   (public key)
```

### Step 2.2: Copy Public Key to Server

```bash
# Copy public key to server
ssh-copy-id -i ~/.ssh/pazpaz-deploy.pub pazpaz@YOUR_SERVER_IP

# Enter pazpaz user password when prompted
```

### Step 2.3: Test SSH Key Authentication

```bash
# Test connection with key (should NOT ask for password)
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP "echo 'SSH key works!'"
```

Expected output:
```
SSH key works!
```

### Step 2.4: Install GitHub CLI (if not installed)

```bash
# macOS
brew install gh

# Verify installation
gh --version
```

### Step 2.5: Login to GitHub CLI

```bash
# Login to GitHub
gh auth login

# Choose:
# - GitHub.com
# - HTTPS
# - Login with a web browser
# - Follow the browser prompts
```

### Step 2.6: Add SSH Secrets to GitHub

```bash
# Navigate to your project
cd /Users/yussieik/Desktop/projects/pazpaz

# Add SSH private key
gh secret set SSH_PRIVATE_KEY < ~/.ssh/pazpaz-deploy

# Add server IP
gh secret set SSH_HOST --body "YOUR_SERVER_IP"

# Add SSH user
gh secret set SSH_USER --body "pazpaz"

# Add SSH port
gh secret set SSH_PORT --body "22"

# Verify secrets were added
gh secret list
```

Expected output:
```
SSH_HOST        Updated 2025-10-24
SSH_PORT        Updated 2025-10-24
SSH_PRIVATE_KEY Updated 2025-10-24
SSH_USER        Updated 2025-10-24
```

**✅ Phase 2 Complete!** GitHub Actions can now SSH to your server.

---

## Phase 3: Purchase and Configure Domain **[OPTIONAL - Skip for Path A]**

**Estimated Time:** 20 minutes (+ DNS propagation time)

> **⚠️ Skip this phase if you chose Path A (HTTP Only).** You can add a domain later by following the "Adding Domain Later" section at the end of this guide.

### Step 3.1: Purchase Domain Name

Choose a domain registrar:
- **Namecheap** (recommended): https://www.namecheap.com
- **Cloudflare Registrar**: https://www.cloudflare.com/products/registrar/
- **Google Domains**: https://domains.google

1. Search for available domain (e.g., `pazpaz-therapy.com`, `yourname-practice.com`)
2. Purchase domain (~$10-15/year)
3. Complete registration

**Write down your domain:**
```
Domain: ________________________
```

### Step 3.2: Configure DNS Records

In your domain registrar's control panel:

1. Go to DNS Management / DNS Settings
2. Add these records:

**Record 1:**
```
Type: A
Host: @ (or leave blank)
Value: YOUR_SERVER_IP
TTL: 300 (or 5 minutes)
```

**Record 2:**
```
Type: A
Host: www
Value: YOUR_SERVER_IP
TTL: 300 (or 5 minutes)
```

3. Save changes

### Step 3.3: Verify DNS Propagation

Wait 5-10 minutes, then test:

```bash
# Test DNS resolution
dig yourdomain.com +short
dig www.yourdomain.com +short

# Should return your server IP
```

If you get your server IP back, DNS is working! If not, wait another 10 minutes and try again.

### Step 3.4: Add Domain to GitHub Secrets

```bash
cd /Users/yussieik/Desktop/projects/pazpaz

# Add domain to GitHub secrets
gh secret set DOMAIN --body "yourdomain.com"

# Verify
gh secret list | grep DOMAIN
```

**✅ Phase 3 Complete!** Your domain now points to your server.

---

## Phase 4: Deploy Infrastructure to Server

**Estimated Time:** 20 minutes

### Step 4.1: Copy Project Files to Server

From your local machine:

```bash
cd /Users/yussieik/Desktop/projects/pazpaz

# Create tar archive of deployment files
tar czf pazpaz-deploy.tar.gz \
  scripts/ \
  docker-compose.prod.yml \
  nginx/ \
  .env.production.example

# Copy to server
scp -i ~/.ssh/pazpaz-deploy \
  pazpaz-deploy.tar.gz \
  pazpaz@YOUR_SERVER_IP:/home/pazpaz/

# Verify upload
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP \
  "ls -lh /home/pazpaz/pazpaz-deploy.tar.gz"
```

### Step 4.2: Extract Files on Server

SSH to server:

```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP
```

On the server:

```bash
# Extract files
cd /home/pazpaz
tar xzf pazpaz-deploy.tar.gz

# Move to /opt/pazpaz
sudo mv scripts /opt/pazpaz/
sudo mv docker-compose.prod.yml /opt/pazpaz/
sudo mv nginx /opt/pazpaz/
sudo mv .env.production.example /opt/pazpaz/

# Set ownership
sudo chown -R pazpaz:pazpaz /opt/pazpaz

# Make scripts executable
chmod +x /opt/pazpaz/scripts/*.sh

# Verify
ls -la /opt/pazpaz
```

### Step 4.3: Generate Production Secrets

On the server:

```bash
cd /opt/pazpaz

# Generate secrets (creates .env.production)
./scripts/generate-secrets.sh

# Verify secrets were created
ls -la .env.production

# Check permissions (should be 600)
stat -c "%a %n" .env.production
```

Expected output:
```
600 .env.production
```

### Step 4.4: Update .env.production with GitHub Repository

```bash
# Edit .env.production
nano .env.production

# Update these lines:
# GITHUB_REPOSITORY=yussieik/pazpaz
# IMAGE_TAG=latest
# VERSION=latest

# Save: Ctrl+O, Enter, Ctrl+X
```

**✅ Phase 4 Complete!** Server has all deployment files and secrets.

---

## Phase 5: Set Up SSL Certificate **[OPTIONAL - Skip for Path A]**

**Estimated Time:** 10 minutes

> **⚠️ Skip this phase if you chose Path A (HTTP Only) or if you skipped Phase 3.** You can set up SSL later when you're ready.

**Important:** Make sure DNS has propagated before this step!

### Step 5.1: Run SSL Setup Script

SSH to server:

```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP
cd /opt/pazpaz

# Run SSL setup (replace with your actual domain)
sudo ./scripts/setup-ssl.sh yourdomain.com
```

This script will:
- Install Certbot
- Request Let's Encrypt certificate
- Configure auto-renewal
- Generate DH parameters

**Watch for prompts:**
- Email address: Enter your email
- Terms of Service: Y (yes)
- Share email with EFF: N (no)

### Step 5.2: Verify Certificate

```bash
# Check certificate was created
sudo ls -la /etc/letsencrypt/live/yourdomain.com/

# Should see:
# - cert.pem
# - chain.pem
# - fullchain.pem
# - privkey.pem
```

### Step 5.3: Test Certificate Auto-Renewal

```bash
# Test renewal (dry run)
sudo certbot renew --dry-run
```

Expected output:
```
Congratulations, all simulated renewals succeeded
```

### Step 5.4: Update Nginx Configuration

```bash
# Copy SSL config
sudo cp /opt/pazpaz/nginx/nginx-ssl.conf /opt/pazpaz/nginx/nginx.conf

# Replace ${DOMAIN_NAME} with actual domain
sudo sed -i "s/\${DOMAIN_NAME}/yourdomain.com/g" /opt/pazpaz/nginx/nginx.conf

# Verify changes
grep "server_name" /opt/pazpaz/nginx/nginx.conf
```

**✅ Phase 5 Complete!** SSL certificate is installed and configured.

---

## Phase 6: First Production Deployment

**Estimated Time:** 30 minutes

### Step 6.1: Ensure Docker Images Are Built

**Important:** Before deploying, make sure your Docker images are pushed to GitHub Container Registry.

From your local machine:

```bash
cd /Users/yussieik/Desktop/projects/pazpaz

# Check if workflows have built and pushed images
gh run list --workflow="Build Backend" --limit 5
gh run list --workflow="Build Frontend" --limit 5

# If no successful builds, trigger them:
git commit --allow-empty -m "trigger: rebuild Docker images"
git push origin main

# Wait for builds to complete
gh run watch
```

### Step 6.2: Run First Deployment

SSH to server:

```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP
cd /opt/pazpaz

# Set required environment variables
export GITHUB_REPOSITORY="yussieik/pazpaz"
export IMAGE_TAG="latest"

# Run deployment
./scripts/deploy.sh
```

This will:
1. Pull Docker images from ghcr.io
2. Start all 8 services
3. Run health checks
4. Verify deployment

**Expected output (at the end):**
```
✅ Deployment completed successfully!
```

### Step 6.3: Run Database Migrations

```bash
# Still on server
cd /opt/pazpaz
./scripts/migrate.sh upgrade
```

Expected output:
```
✅ Migration completed successfully
```

### Step 6.4: Verify Services Are Running

```bash
# Check Docker containers
docker ps

# Should see 8 containers running:
# - pazpaz-api-1
# - pazpaz-arq-worker-1
# - pazpaz-db-1
# - pazpaz-redis-1
# - pazpaz-minio-1
# - pazpaz-clamav-1
# - pazpaz-frontend-1
# - pazpaz-nginx-1

# Check service health
docker ps --format "table {{.Names}}\t{{.Status}}"
```

All services should show "healthy" or "Up X minutes".

### Step 6.5: Test Application

**From your browser:**

**If you have a domain (Path B):**

1. Visit `https://yourdomain.com`
   - Should see PazPaz frontend

2. Visit `https://yourdomain.com/api/v1/health`
   - Should see: `{"status":"ok"}`

3. Check SSL certificate
   - Click the padlock in browser
   - Should show "Issued by Let's Encrypt"

**If using IP only (Path A):**

1. Visit `http://YOUR_SERVER_IP` (e.g., `http://5.161.241.81`)
   - Should see PazPaz frontend

2. Visit `http://YOUR_SERVER_IP/api/v1/health`
   - Should see: `{"status":"ok"}`

3. No SSL certificate (HTTP only)

**If you see errors:**
```bash
# Check logs
docker logs pazpaz-api-1 --tail 50
docker logs pazpaz-nginx-1 --tail 50
```

**✅ Phase 6 Complete!** Application is deployed and running!

---

## Phase 7: Create Admin User

**Estimated Time:** 10 minutes

### Step 7.1: Access API Container

SSH to server:

```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP

# Enter API container
docker exec -it pazpaz-api-1 bash
```

### Step 7.2: Create Admin User

Inside the container:

```bash
cd /app
export PYTHONPATH=/app/src

# Start Python interpreter
python3

# Run this Python code (replace with your email):
```

```python
from pazpaz.db.session import SessionLocal
from pazpaz.models.user import User
from pazpaz.core.security import get_password_hash
import asyncio

async def create_admin():
    db = SessionLocal()
    try:
        # Check if admin exists
        existing = db.query(User).filter(User.email == "your-email@example.com").first()
        if existing:
            print("Admin user already exists!")
            return

        # Create admin user
        admin = User(
            email="your-email@example.com",
            hashed_password=get_password_hash("temporary-password"),
            is_superuser=True,
            is_active=True,
            full_name="Admin User"
        )
        db.add(admin)
        db.commit()
        print(f"✅ Admin user created: {admin.email}")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

asyncio.run(create_admin())
```

Press Enter, then:

```python
quit()
```

Exit container:

```bash
exit
```

### Step 7.3: Test Login

1. Go to your application:
   - **Path B (domain):** `https://yourdomain.com/login`
   - **Path A (IP only):** `http://YOUR_SERVER_IP/login`
2. Enter your email
3. Click "Send Magic Link"
4. Check your email for login link
5. Click link to login

**✅ Phase 7 Complete!** You can now access the application as admin.

---

## Phase 8: Enable Automated Deployments

**Estimated Time:** 10 minutes

**Status:** ✅ **COMPLETE** - Automated deployments are live and working in production!

### Current Automated Deployment Status

Automated CI/CD is **fully operational** as of October 27, 2025:

- **Backend Deployment:** `.github/workflows/backend-ci.yml`
  - ✅ Automatically deploys on push to main
  - ✅ Runs database migrations before deployment
  - ✅ Deploys API and ARQ worker containers
  - ✅ Verifies deployment health (API health check)
  - Production URL: https://pazpaz.health/api

- **Frontend Deployment:** `.github/workflows/frontend-ci.yml`
  - ✅ Automatically deploys on push to main
  - ✅ Deploys frontend and nginx containers
  - ✅ Verifies site accessibility
  - Production URL: https://pazpaz.health

- **Secrets Validation:** `.github/workflows/validate-secrets.yml`
  - ✅ Weekly validation (Mondays 9 AM UTC)
  - ✅ Tests SSH connectivity
  - ✅ Validates encryption master key
  - Can be triggered manually: `gh workflow run "Validate GitHub Secrets Configuration"`

### How Automated Deployment Works

**On every push to main:**

1. **CI Phase** (5-10 minutes):
   - Runs all tests (backend and frontend)
   - Performs security scanning (Trivy, CodeQL)
   - Runs linting and type checking
   - Builds Docker images and pushes to ghcr.io

2. **CD Phase** (2-5 minutes):
   - SSH connects to production server (5.161.241.81)
   - Pulls latest Docker images
   - Runs database migrations (backend only)
   - Recreates containers with new images
   - Waits for health checks
   - Verifies deployment success

3. **Health Verification**:
   - Backend: `curl https://pazpaz.health/api/v1/health`
   - Frontend: `curl https://pazpaz.health/`
   - Container status: `docker ps | grep "Up.*pazpaz"`

### Required GitHub Secrets (Already Configured)

The following secrets are configured and working:

- ✅ `PRODUCTION_SSH_KEY` - ED25519 SSH private key for deployment
- ✅ `PROD_ENCRYPTION_MASTER_KEY` - PHI encryption master key (HIPAA compliance)
- ✅ SSH connection hardcoded to `root@5.161.241.81` in workflows
- ✅ Domain hardcoded to `pazpaz.health` for health checks

**Note:** SSH_HOST, SSH_USER, and SSH_PORT are **not used as secrets**. They are hardcoded directly in the workflow files for simplicity.

### Manual Deployment (If Needed)

While automated deployment works on every push to main, you can also deploy manually:

**Option 1: Trigger workflows manually**
```bash
# Trigger backend deployment
gh workflow run "Backend CI" --ref main

# Trigger frontend deployment
gh workflow run "Frontend CI" --ref main

# Watch the run
gh run watch
```

**Option 2: SSH to server and deploy manually**
```bash
# SSH to production
ssh root@5.161.241.81

# Navigate to deployment directory
cd /opt/pazpaz

# Pull latest images and redeploy
docker compose --env-file .env.production -f docker-compose.prod.yml pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --force-recreate
```

### Deployment Monitoring

**Check recent deployments:**
```bash
# List recent workflow runs
gh run list --workflow="Backend CI" --limit 5
gh run list --workflow="Frontend CI" --limit 5

# View specific run
gh run view <run-id>

# Watch live deployment
gh run watch
```

**Check production status:**
```bash
# SSH to server
ssh root@5.161.241.81

# Check container status
cd /opt/pazpaz
docker compose --env-file .env.production -f docker-compose.prod.yml ps

# View logs
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f api
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f frontend
```

### Troubleshooting Automated Deployments

**If deployment fails:**

1. **Check workflow logs:**
   ```bash
   gh run list --workflow="Backend CI" --limit 1
   gh run view --log
   ```

2. **Common issues:**
   - SSH connection failure → Verify `PRODUCTION_SSH_KEY` secret
   - Container health check failure → Check container logs on server
   - Migration failure → Check database connectivity
   - Image pull failure → Verify GITHUB_TOKEN has packages:read permission

3. **Manual intervention:**
   ```bash
   # SSH to server and check status
   ssh root@5.161.241.81
   cd /opt/pazpaz
   docker compose --env-file .env.production -f docker-compose.prod.yml logs
   ```

**✅ Phase 8 Complete!** Automated deployments are operational and have been tested in production.

---

## Phase 9: Set Up Monitoring (Optional but Recommended)

**Estimated Time:** 30 minutes

### Step 9.1: Set Up UptimeRobot

1. Go to https://uptimerobot.com
2. Sign up for free account (50 monitors free)
3. Click "Add New Monitor"

**Monitor 1: API Health**
- Monitor Type: HTTP(s)
- Friendly Name: PazPaz API Health
- URL: `https://yourdomain.com/api/v1/health`
- Monitoring Interval: 5 minutes
- Alert Contacts: Your email
- Click "Create Monitor"

**Monitor 2: Frontend**
- Monitor Type: HTTP(s)
- Friendly Name: PazPaz Frontend
- URL: `https://yourdomain.com`
- Monitoring Interval: 5 minutes
- Alert Contacts: Your email
- Click "Create Monitor"

### Step 9.2: Set Up Sentry (Optional)

1. Go to https://sentry.io
2. Sign up for free account
3. Create new project:
   - Platform: Python (for backend)
   - Project name: pazpaz-backend
4. Copy the DSN (looks like: `https://xxx@xxx.ingest.sentry.io/xxx`)

**Add to server:**

```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP

# Edit .env.production
nano /opt/pazpaz/.env.production

# Add line:
SENTRY_DSN=your_sentry_dsn_here

# Save: Ctrl+O, Enter, Ctrl+X

# Restart API
docker-compose -f /opt/pazpaz/docker-compose.prod.yml restart api
```

**Add to GitHub (optional, for release tracking):**

```bash
# On your local machine
gh secret set SENTRY_AUTH_TOKEN --body "your_sentry_auth_token"
gh variable set ENABLE_SENTRY_RELEASES --body "true"
```

### Step 9.3: Set Up Backups

SSH to server:

```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP
cd /opt/pazpaz

# Install backup cron jobs
sudo ./scripts/install-backup-cron.sh --user pazpaz

# Test manual backup
./scripts/backup-db.sh daily

# Verify backup was created
ls -lh /opt/pazpaz/backups/
```

### Step 9.4: Test Backup Restore

```bash
# Test restore process
./scripts/test-backup-restore.sh

# Should see:
# ✅ Backup restore test completed successfully
```

**✅ Phase 9 Complete!** Monitoring and backups are configured!

---

## Phase 10: Optional Features

### Enable Slack Notifications

If you want Slack notifications for deployments:

1. Create Slack workspace (if you don't have one)
2. Add "Incoming Webhooks" app
3. Create webhook for #deployments channel
4. Copy webhook URL

```bash
# Add to GitHub
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
gh variable set ENABLE_SLACK_NOTIFICATIONS --body "true"
```

### Set Up Off-Site Backups (S3)

To store backups in AWS S3 or DigitalOcean Spaces:

**On your server:**

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure (or use DigitalOcean Spaces)
aws configure
# Enter your access key, secret key, region
```

**Update .env.production:**

```bash
nano /opt/pazpaz/.env.production

# Add:
BACKUP_S3_BUCKET=your-backup-bucket
BACKUP_S3_ACCESS_KEY=your-access-key
BACKUP_S3_SECRET_KEY=your-secret-key
BACKUP_S3_REGION=us-east-1
```

Backups will now automatically upload to S3!

---

## Adding Domain Later (Upgrading from Path A to Path B)

If you deployed with Path A (HTTP only) and now want to add a domain and SSL certificate, follow these steps:

**Estimated Time:** 30 minutes (including DNS propagation wait)

### Step 1: Purchase Domain and Configure DNS

1. Purchase a domain from Namecheap, Cloudflare, or Google Domains
2. Add DNS A records pointing to your server IP:
   ```
   Type: A, Host: @, Value: YOUR_SERVER_IP
   Type: A, Host: www, Value: YOUR_SERVER_IP
   ```
3. Wait 10-30 minutes for DNS propagation
4. Test with: `dig yourdomain.com +short` (should return your server IP)

### Step 2: Add Domain to GitHub Secrets

```bash
# Add domain to GitHub secrets
gh secret set DOMAIN --body "yourdomain.com"

# Verify
gh secret list | grep DOMAIN
```

### Step 3: Run SSL Setup Script

SSH to your server and run the automated SSL setup:

```bash
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP

cd /opt/pazpaz

# Run SSL setup (replace with your actual domain)
sudo ./scripts/setup-ssl.sh yourdomain.com
```

**The script will automatically:**
- ✅ Install certbot
- ✅ Obtain Let's Encrypt certificate
- ✅ Switch nginx to SSL configuration
- ✅ Set up auto-renewal
- ✅ Restart services with HTTPS

**When prompted:**
- Email address: Enter your email
- Terms of Service: Y (yes)
- Share email with EFF: N (optional)

### Step 4: Verify SSL is Working

```bash
# Check certificate exists
sudo ls -la /etc/letsencrypt/live/yourdomain.com/

# Test certificate auto-renewal
sudo certbot renew --dry-run
```

Expected output:
```
Congratulations, all simulated renewals succeeded
```

### Step 5: Update Environment Variables (Optional)

If you want to update any environment variables to use your domain:

```bash
nano /opt/pazpaz/.env.production

# Update:
# FRONTEND_URL=https://yourdomain.com
# ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Save: Ctrl+O, Enter, Ctrl+X

# Restart services
docker compose -f /opt/pazpaz/docker-compose.prod.yml restart
```

### Step 6: Test HTTPS Access

Visit your domain in a browser:
1. `https://yourdomain.com` - Should see PazPaz frontend
2. `https://yourdomain.com/api/v1/health` - Should return `{"status":"ok"}`
3. Check the padlock icon - Should show "Issued by Let's Encrypt"

**That's it!** You're now running with HTTPS and are HIPAA-compliant. 🎉

---

## Troubleshooting

### Problem: Can't SSH to server

**Solution:**
```bash
# Check server is running in Hetzner console
# Check firewall allows port 22:
ssh root@YOUR_SERVER_IP
ufw status
```

### Problem: DNS not resolving

**Solution:**
```bash
# Wait longer (can take up to 48 hours)
# Check DNS with:
dig yourdomain.com
# Should return server IP
```

### Problem: SSL certificate fails

**Solution:**
```bash
# Make sure DNS is working first
# Check ports 80 and 443 are open:
sudo ufw status
# Try again:
sudo certbot certonly --standalone -d yourdomain.com
```

### Problem: Docker containers won't start

**Solution:**
```bash
# Check logs:
docker logs pazpaz-api-1
docker logs pazpaz-db-1

# Common issues:
# - Missing environment variables in .env.production
# - Database connection issues
# - Port conflicts
```

### Problem: Can't access application

**Solution:**
```bash
# Check nginx is running:
docker ps | grep nginx

# Check nginx logs:
docker logs pazpaz-nginx-1

# Test API directly:
curl https://yourdomain.com/api/v1/health
```

### Problem: Deployment workflow fails

**Solution:**
```bash
# Check GitHub Secrets are set:
gh secret list

# Required (all paths):
# - SSH_PRIVATE_KEY
# - SSH_HOST
# - SSH_USER
# - SSH_PORT

# Required (Path B only):
# - DOMAIN

# Check server is accessible:
ssh -i ~/.ssh/pazpaz-deploy pazpaz@YOUR_SERVER_IP "echo works"
```

---

## Maintenance Tasks

### Daily (Automated)
- ✅ Database backups (2 AM UTC)
- ✅ Health checks (every 5 minutes via UptimeRobot)
- ✅ SSL certificate renewal check

### Weekly
- Check UptimeRobot dashboard for downtime
- Review Sentry errors (if configured)
- Check disk space: `df -h`

### Monthly
- Review backup restore tests
- Check secret rotation schedule
- Review server logs for issues

### Quarterly (Every 90 days)
- Rotate database password
- Rotate Redis password
- Rotate JWT secret
- Update server packages: `sudo apt update && sudo apt upgrade`

---

## Cost Summary

**Monthly Costs:**
- Hetzner VPS (CPX41): €20.46/month (~$22/month)
- UptimeRobot: Free (up to 50 monitors)
- Sentry: Free (up to 5K errors/month)

**Annual Costs:**
- Domain name: $10-15/year
- SSL certificate: Free (Let's Encrypt)

**Total:** ~$25/month + $12/year = ~$27/month

---

## Support

If you need help:

1. Check the troubleshooting section above
2. Check deployment logs:
   ```bash
   ssh pazpaz@yourdomain.com
   cd /opt/pazpaz/logs
   tail -100 deployment.log
   ```
3. Check application logs:
   ```bash
   docker logs pazpaz-api-1 --tail 100
   ```
4. Review documentation:
   - `/docs/deployment/` folder
   - GitHub Actions workflow logs

---

## Actual Production Deployment Notes

**This section documents what was actually done for the production deployment at pazpaz.health.**

### Deployment Path Taken

The production environment was deployed using a **hybrid approach**:
- Started with infrastructure setup (Phases 1-2)
- Domain (pazpaz.health) was already registered
- Initial deployment used self-signed SSL certificates
- Later migrated to Let's Encrypt for production-grade SSL

### Key Differences from Guide

**Manual vs. Automated:**
- Infrastructure setup: Manual SSH
- Service deployment: Manual Docker Compose commands
- SSL setup: Custom scripts + manual Let's Encrypt configuration
- No automated deployment workflow (yet)

**SSL Certificate Journey:**
1. **Phase 1:** Generated self-signed CA and certificates for:
   - PostgreSQL (SSL/TLS for database connections)
   - MinIO (HTTPS for S3-compatible storage)
   - nginx (initially self-signed HTTPS)

2. **Phase 2:** Migrated nginx to Let's Encrypt:
   - Obtained Let's Encrypt certificate for pazpaz.health
   - Updated nginx configuration to use Let's Encrypt
   - Configured auto-renewal via certbot systemd timer

**Deployment Scripts Created:**

During deployment, several helper scripts were created in `/tmp/` on the server:

1. **`/tmp/regenerate-ssl-certs-v2.sh`** - PostgreSQL SSL certificates
   - Creates CA with proper X.509 v3 extensions
   - Generates server and client certificates
   - Used for initial PostgreSQL SSL setup

2. **`/tmp/generate-minio-certs.sh`** - MinIO SSL certificates
   - Generates certificates signed by PazPaz CA
   - Configures SAN (Subject Alternative Names)
   - Used for MinIO HTTPS setup

3. **`/tmp/generate-nginx-certs.sh`** - nginx self-signed certificates
   - Initial nginx SSL setup (before Let's Encrypt)
   - Later replaced by Let's Encrypt certificates

4. **`/tmp/fix-nginx-ssl.sh`** - Complete nginx SSL setup
   - All-in-one script for nginx SSL configuration
   - Generates certs, updates config, restarts services

5. **`/tmp/deploy-minio-ssl-fix.sh`** - MinIO SSL fix deployment
   - Deploys commit 15a33f3 (boto3 CA certificate fix)
   - Adds S3_CA_CERT_PATH environment variable
   - Restarts API service with new configuration

**These scripts are preserved for documentation and can be reused for:**
- Setting up staging environments
- Disaster recovery scenarios
- Redeploying individual components

### Current Production Configuration

**Environment Variables (`.env.production`):**
- All secrets generated and configured
- S3_CA_CERT_PATH configured for MinIO SSL
- Database credentials secured
- JWT secrets configured
- Encryption master key set

**Services Running:**
- ✅ nginx: HTTPS with Let's Encrypt (ports 80, 443)
- ✅ api: Backend with MinIO SSL fix (commit 15a33f3)
- ✅ db: PostgreSQL 16 with SSL/TLS
- ✅ redis: Password-protected cache
- ✅ minio: HTTPS S3-compatible storage
- ✅ clamav: Virus scanning for file uploads
- ⚠️ frontend: Running (health check needs tuning)
- ⚠️ arq-worker: Processing jobs (health check needs tuning)

**SSL Certificates:**
- **PostgreSQL:** Self-signed CA (internal communication)
- **MinIO:** Self-signed CA (internal communication)
- **nginx (public):** Let's Encrypt (browser-trusted)

### Lessons Learned

**What Worked Well:**
1. Docker Compose for service orchestration
2. Self-signed CA for internal service communication
3. Let's Encrypt for public-facing SSL
4. GitHub Container Registry for image storage
5. Manual deployment initially (faster iteration)

**What Needs Improvement:**
1. **Automated deployments:** Need GitHub Actions workflow
2. **Health checks:** Frontend and ARQ worker need adjustment
3. **Monitoring:** Need UptimeRobot, Sentry, logging
4. **Backups:** Need automated backup system
5. **Documentation:** Scripts should be in `/opt/pazpaz/scripts/`

**Next Improvements:**
- Move deployment scripts from `/tmp/` to `/opt/pazpaz/scripts/`
- Create automated deployment workflow
- Fix frontend/ARQ worker health checks
- Set up monitoring and alerting
- Configure automated backups

### Manual Deployment Commands Used

**Pull and deploy backend update:**
```bash
cd /opt/pazpaz
docker compose -f docker-compose.prod.yml --env-file .env.production pull api
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate api
```

**Update nginx configuration:**
```bash
# Edit config
nano nginx/nginx-ssl.conf

# Restart nginx
docker compose -f docker-compose.prod.yml --env-file .env.production restart nginx
```

**Check service status:**
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f api
```

**Manage Let's Encrypt certificates:**
```bash
# Check certificate status
sudo certbot certificates

# Test renewal (dry run)
sudo certbot renew --dry-run

# Force renewal (if needed)
sudo certbot renew --force-renewal
```

---

## Next Steps

After completing this guide, you should have:
- ✅ Production server running on Hetzner
- ✅ Domain with SSL certificate
- ✅ Application deployed and accessible
- ✅ Automated deployments via GitHub Actions
- ✅ Monitoring and backups configured
- ✅ Admin user created

You can now:
1. Start using the application
2. Invite users
3. Monitor via UptimeRobot
4. Deploy updates with git push

**Congratulations on deploying PazPaz to production!** 🎉
