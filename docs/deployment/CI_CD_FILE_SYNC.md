# CI/CD Configuration File Synchronization

**Status:** ✅ Implemented (2025-10-27)
**Issue Fixed:** Configuration files on production server were outdated, preventing deployments from taking effect

---

## 📋 Overview

This document explains how configuration files are synchronized from the GitHub repository to the production server during CI/CD deployments.

### Background

Previously, the CI/CD workflows used `git pull origin main` on the production server to sync configuration files. This was removed in commit `68e600e` because `/opt/pazpaz` on the production server is not a git repository.

However, **no replacement sync mechanism was implemented**, causing:
- Outdated `docker-compose.prod.yml` on the server
- Outdated nginx configurations
- Deployments using wrong image tags or outdated settings
- New code in Docker images not taking effect

### Solution

Added explicit file synchronization steps to both frontend and backend CI/CD workflows using `scp` (secure copy over SSH).

---

## 🔄 How It Works

### Frontend Deployment Workflow

**File:** `.github/workflows/frontend-ci.yml`

**Synced files:**
1. `docker-compose.prod.yml` → `/opt/pazpaz/docker-compose.prod.yml`
2. `frontend/nginx.prod.conf` → `/opt/pazpaz/frontend/nginx.prod.conf`

**Process:**
```yaml
- name: Sync configuration files to server
  run: |
    # Copy docker-compose configuration
    scp docker-compose.prod.yml root@5.161.241.81:/opt/pazpaz/

    # Copy frontend nginx configuration
    scp frontend/nginx.prod.conf root@5.161.241.81:/opt/pazpaz/frontend/

    # Verify files on server
    ssh root@5.161.241.81 ls -lh /opt/pazpaz/docker-compose.prod.yml
```

### Backend Deployment Workflow

**File:** `.github/workflows/backend-ci.yml`

**Synced files:**
1. `docker-compose.prod.yml` → `/opt/pazpaz/docker-compose.prod.yml`
2. `backend/alembic.ini` → `/opt/pazpaz/backend/alembic.ini`
3. `backend/migrations/*` → `/opt/pazpaz/backend/migrations/`

**Process:**
```yaml
- name: Sync configuration files to server
  run: |
    # Copy docker-compose configuration
    scp docker-compose.prod.yml root@5.161.241.81:/opt/pazpaz/

    # Copy alembic configuration and migrations
    ssh root@5.161.241.81 'mkdir -p /opt/pazpaz/backend/migrations'
    scp backend/alembic.ini root@5.161.241.81:/opt/pazpaz/backend/
    scp -r backend/migrations/* root@5.161.241.81:/opt/pazpaz/backend/migrations/
```

---

## 🎯 Deployment Flow

### Complete Frontend Deployment

1. **Checkout code** - Get latest files from repository
2. **Set up SSH** - Configure SSH keys for server access
3. **Sync configuration files** - Copy config files to server (NEW STEP)
4. **Deploy frontend** - Pull images and recreate containers
   - Set `IMAGE_TAG=latest` explicitly
   - Pull images with `--quiet` flag
   - Show image digest for verification
   - Recreate containers with `--force-recreate --pull always`
5. **Verify deployment health** - Check if site is accessible
6. **Verify image deployment** - Confirm correct images are running (NEW STEP)

### Complete Backend Deployment

1. **Checkout code** - Get latest files from repository
2. **Set up SSH** - Configure SSH keys for server access
3. **Sync configuration files** - Copy config files to server (NEW STEP)
4. **Deploy backend** - Pull images, run migrations, recreate containers
   - Set `IMAGE_TAG=latest` explicitly
   - Pull images with `--quiet` flag
   - Show image digest for verification
   - Run database migrations
   - Recreate containers with `--force-recreate --pull always`
5. **Verify API health** - Check API health endpoint
6. **Verify ARQ worker** - Check background worker process
7. **Verify image deployment** - Confirm correct images are running (NEW STEP)

---

## 🔒 Security Considerations

### What Gets Synced

✅ **Configuration files that SHOULD be synced:**
- `docker-compose.prod.yml` - Container orchestration
- `nginx.prod.conf` - Web server configuration
- `alembic.ini` - Database migration configuration
- `migrations/` - Database migration scripts

❌ **Files that SHOULD NOT be synced:**
- `.env.production` - Contains secrets (managed separately)
- SSL certificates - Managed by Let's Encrypt on server
- Database backups - Managed on server
- Application logs - Generated on server

### SSH Security

- Uses ED25519 SSH keys (stored in GitHub Secrets: `PRODUCTION_SSH_KEY`)
- SSH key only has access to production server (root@5.161.241.81)
- Connections verified with `ssh-keyscan` to prevent MITM attacks
- All file copies use `scp` over encrypted SSH tunnel

---

## 🐛 Troubleshooting

### Files Not Syncing

**Symptom:** Configuration changes in repository not appearing on server

**Diagnosis:**
```bash
# On local machine
git log -1 --oneline docker-compose.prod.yml

# On server
ssh root@5.161.241.81 'stat -c "%y %n" /opt/pazpaz/docker-compose.prod.yml'
```

**Solution:**
- Check if workflow succeeded in GitHub Actions
- Verify SSH key permissions in GitHub Secrets
- Manually sync files using steps in `MANUAL_PRODUCTION_FIX.md`

### Permission Denied

**Symptom:** `scp: permission denied` in CI/CD logs

**Diagnosis:**
```bash
# Check directory permissions on server
ssh root@5.161.241.81 'ls -ld /opt/pazpaz'
```

**Solution:**
```bash
# Fix directory permissions
ssh root@5.161.241.81 'chmod 755 /opt/pazpaz'
```

### Sparse Checkout Issues

**Symptom:** Files not available in GitHub Actions workspace

**Diagnosis:**
```yaml
# In workflow, after checkout step
- name: Debug
  run: ls -la .
```

**Solution:**
- Ensure `sparse-checkout` in workflow includes all needed files
- For frontend: `docker-compose.prod.yml`, `frontend/nginx.prod.conf`
- For backend: `docker-compose.prod.yml`, `backend/alembic.ini`, `backend/migrations/`

---

## 🔍 Verification

### After Each Deployment

The workflows automatically verify:

1. **File sync completed:**
   ```bash
   ls -lh /opt/pazpaz/docker-compose.prod.yml
   ```

2. **Image digest:**
   ```bash
   docker images --digests ghcr.io/yussieik/pazpaz-frontend:latest
   ```

3. **Container creation time:**
   ```bash
   docker inspect pazpaz-frontend --format='Created: {{.Created}}'
   ```

### Manual Verification

Check if deployed image matches repository commit:

```bash
# Get commit SHA from repository
git rev-parse HEAD

# On server, check image label
ssh root@5.161.241.81 'docker inspect ghcr.io/yussieik/pazpaz-frontend:latest | jq ".[0].Config.Labels"'
```

---

## 🚀 Future Improvements

### Short-term (MVP)

- [x] Add file sync to frontend-ci.yml
- [x] Add file sync to backend-ci.yml
- [x] Add deployment verification steps
- [ ] Add rollback capability
- [ ] Add deployment notifications (Slack/Discord)

### Long-term (Nice-to-have)

- [ ] Create git repository on production server for config tracking
- [ ] Implement proper GitOps with separate config repository
- [ ] Add deployment history and audit trail
- [ ] Implement blue-green deployment strategy
- [ ] Add canary deployment option
- [ ] Automate rollback on health check failure

---

## 📚 Related Documentation

- [MANUAL_PRODUCTION_FIX.md](../../MANUAL_PRODUCTION_FIX.md) - Immediate manual fix for production
- [PRODUCTION_DEPLOYMENT_GUIDE.md](./PRODUCTION_DEPLOYMENT_GUIDE.md) - Complete deployment guide
- [PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md) - Operations runbook
- [CI/CD Workflows](../../.github/workflows/) - GitHub Actions workflow files

---

## 🔗 References

- **Issue Root Cause:** Commit `68e600e` removed `git pull` without replacement
- **Fix Implemented:** 2025-10-27
- **Production Server:** root@5.161.241.81 (`/opt/pazpaz`)
- **Image Registry:** GitHub Container Registry (ghcr.io)

---

**Questions?** See [PRODUCTION_RUNBOOK.md](./PRODUCTION_RUNBOOK.md) or create an issue in GitHub.
