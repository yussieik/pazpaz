# Manual Production Fix - Immediate Deployment Triage

**Date:** 2025-10-27
**Issue:** CI/CD deploys are not taking effect on production server
**Root Cause:** Configuration files on server are outdated; removed git pull without replacement sync mechanism

---

## 🚨 Immediate Action Required

Run these commands to manually sync config files and redeploy with latest images:

### Step 1: Backup Current Production Config

```bash
ssh root@5.161.241.81 << 'EOF'
  cd /opt/pazpaz

  # Backup current configuration
  cp docker-compose.prod.yml docker-compose.prod.yml.backup-$(date +%Y%m%d-%H%M%S)

  # Verify backup
  ls -lh docker-compose.prod.yml*
EOF
```

### Step 2: Sync Latest Config Files from Local Repository

**From your local machine** (in the pazpaz repository directory):

```bash
# Copy docker-compose configuration
scp docker-compose.prod.yml root@5.161.241.81:/opt/pazpaz/

# Copy frontend nginx configuration
scp frontend/nginx.prod.conf root@5.161.241.81:/opt/pazpaz/frontend/

# Verify files were copied
ssh root@5.161.241.81 'ls -lh /opt/pazpaz/docker-compose.prod.yml /opt/pazpaz/frontend/nginx.prod.conf'
```

### Step 3: Pull Latest Docker Images and Restart

```bash
ssh root@5.161.241.81 << 'EOF'
  set -e
  cd /opt/pazpaz

  echo "📦 Pulling latest Docker images..."

  # Set explicit image tag
  export IMAGE_TAG=latest

  # Pull latest images (frontend, backend, arq-worker)
  docker compose --env-file .env.production -f docker-compose.prod.yml pull frontend api arq-worker

  # Show image digests for verification
  echo ""
  echo "🔍 Verifying image digests:"
  docker images --digests ghcr.io/yussieik/pazpaz-frontend:latest
  docker images --digests ghcr.io/yussieik/pazpaz-backend:latest

  echo ""
  echo "🔄 Recreating containers with fresh images..."

  # Recreate all containers with --pull always to bypass any cache
  docker compose --env-file .env.production -f docker-compose.prod.yml up -d --force-recreate --pull always

  echo ""
  echo "⏳ Waiting for services to become healthy..."
  sleep 30

  # Verify containers are running
  echo ""
  echo "✅ Container status:"
  docker ps --filter "name=pazpaz-" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"

  echo ""
  echo "🔍 Checking container health:"
  docker compose --env-file .env.production -f docker-compose.prod.yml ps
EOF
```

### Step 4: Verify Deployment

```bash
# Check API health
curl -s https://pazpaz.health/api/v1/health | jq '.'

# Check frontend accessibility
curl -I https://pazpaz.health/ | head -1

# Check for Content-Type fix in browser DevTools:
# 1. Open https://pazpaz.health in browser
# 2. Open DevTools (F12) > Network tab
# 3. Try "Finalize Session" on Session Note page
# 4. Check request headers - should now have "Content-Type: application/json"
```

### Step 5: Check Logs for Errors

```bash
ssh root@5.161.241.81 << 'EOF'
  cd /opt/pazpaz

  echo "🔍 Recent frontend logs:"
  docker compose --env-file .env.production -f docker-compose.prod.yml logs frontend --tail=50

  echo ""
  echo "🔍 Recent API logs:"
  docker compose --env-file .env.production -f docker-compose.prod.yml logs api --tail=50

  echo ""
  echo "🔍 Recent nginx logs:"
  docker compose --env-file .env.production -f docker-compose.prod.yml logs nginx --tail=50
EOF
```

---

## 🎯 Expected Outcome

After running these steps:

✅ The Content-Type fix should now work in production
✅ "Finalize Session" should no longer throw 415 errors
✅ All POST/PUT/PATCH requests should include proper Content-Type headers
✅ Container images match the latest commit (fb09125 or later)

---

## 🔍 Troubleshooting

### If Content-Type error persists:

1. **Clear browser cache:**
   ```bash
   # Hard refresh in browser
   Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
   ```

2. **Verify image is actually updated:**
   ```bash
   ssh root@5.161.241.81 'docker exec pazpaz-frontend cat /usr/share/nginx/html/assets/index-*.js | grep -o "Content-Type" | head -1'
   ```
   - Should output "Content-Type" if the fix is in the deployed code

3. **Check image build date:**
   ```bash
   ssh root@5.161.241.81 'docker inspect ghcr.io/yussieik/pazpaz-frontend:latest | jq ".[0].Created"'
   ```
   - Should be today's date (2025-10-27) or after commit fb09125

4. **Force pull from registry (bypass all caching):**
   ```bash
   ssh root@5.161.241.81 << 'EOF'
     cd /opt/pazpaz

     # Remove local images to force fresh pull
     docker rmi ghcr.io/yussieik/pazpaz-frontend:latest
     docker rmi ghcr.io/yussieik/pazpaz-backend:latest

     # Pull fresh and restart
     docker compose --env-file .env.production -f docker-compose.prod.yml pull
     docker compose --env-file .env.production -f docker-compose.prod.yml up -d --force-recreate
   EOF
   ```

### If containers fail to start:

1. **Check logs for errors:**
   ```bash
   ssh root@5.161.241.81 'cd /opt/pazpaz && docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100'
   ```

2. **Verify environment variables:**
   ```bash
   ssh root@5.161.241.81 'cd /opt/pazpaz && grep -v "^#" .env.production | wc -l'
   ```
   - Should have 30+ environment variables set

3. **Check disk space:**
   ```bash
   ssh root@5.161.241.81 'df -h /opt/pazpaz'
   ```

4. **Rollback if needed:**
   ```bash
   ssh root@5.161.241.81 << 'EOF'
     cd /opt/pazpaz

     # Restore backup
     cp docker-compose.prod.yml.backup-* docker-compose.prod.yml

     # Restart with old config
     docker compose --env-file .env.production -f docker-compose.prod.yml up -d --force-recreate
   EOF
   ```

---

## 📝 Post-Fix Actions

Once production is working:

1. ✅ Verify the Content-Type fix works in production
2. ✅ Update CI/CD workflows to sync files automatically (see PR #XXX)
3. ✅ Document this incident in deployment runbook
4. ✅ Add deployment verification tests to CI/CD

---

## 🔗 Related Issues

- Commit fb09125: "build(frontend): force cache invalidation for Content-Type fix deployment"
- Commit 0d3884a: "fix(frontend): enforce Content-Type header in request interceptor"
- Commit 68e600e: "fix(ci): remove git pull from deployment workflows" (THIS CAUSED THE ISSUE)

---

**Status:** 🟡 Awaiting manual execution
**Next Steps:** Run commands above, then update CI/CD workflows
