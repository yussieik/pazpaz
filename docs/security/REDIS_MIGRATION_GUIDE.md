# Redis Security Migration Guide

## Overview

This guide helps you migrate from an unsecured Redis instance to a password-protected, secure Redis configuration.

**Target audience:**
- Existing PazPaz deployments with unsecured Redis
- Development environments that need security hardening
- Production deployments preparing for launch

**Migration time:** 5-10 minutes (with downtime)

**Downtime required:** Yes (~2-5 minutes)

## Pre-Migration Checklist

Before starting the migration, ensure:

- [ ] You have SSH/terminal access to the server
- [ ] You have permissions to edit `.env` and `docker-compose.yml`
- [ ] You can restart Docker containers
- [ ] You have a maintenance window (if production)
- [ ] You've notified users of planned downtime (if production)

## Migration Steps

### Step 1: Backup Redis Data (Optional but Recommended)

If you have important data in Redis (cached sessions, jobs, etc.):

```bash
# Create backup directory
mkdir -p ~/redis-backups

# Backup Redis data
docker exec pazpaz-redis redis-cli --rdb /data/backup.rdb
docker cp pazpaz-redis:/data/backup.rdb ~/redis-backups/redis-backup-$(date +%Y%m%d-%H%M%S).rdb

# Verify backup
ls -lh ~/redis-backups/
```

**Note:** If you're using Redis only for caching (no persistent jobs), you can skip backup. Cache will rebuild automatically.

### Step 2: Generate Strong Redis Password

```bash
# Generate 32-character random password
openssl rand -base64 32

# Example output: 7Qf8K2mNxVp1rT3jL9sW6hY4cZ5bA8nU0dE1gH2iF=
```

**Save this password securely!** You'll need it in the next steps.

### Step 3: Stop Services

```bash
# Stop all services
cd /path/to/pazpaz
docker-compose down

# Verify all containers stopped
docker-compose ps
```

### Step 4: Update Configuration Files

#### 4.1: Update `.env`

```bash
# Edit .env file
nano backend/.env
# or
vim backend/.env
```

Add or update these lines:

```bash
# Redis Configuration
REDIS_PASSWORD=<paste-generated-password-here>
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
```

**Example:**

```bash
REDIS_PASSWORD=7Qf8K2mNxVp1rT3jL9sW6hY4cZ5bA8nU0dE1gH2iF=
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
```

Save and exit.

#### 4.2: Update `docker-compose.yml`

```bash
# Edit docker-compose.yml
nano docker-compose.yml
```

Find the `redis` service and update it:

**Before:**
```yaml
redis:
  image: redis:7-alpine
  container_name: pazpaz-redis
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
```

**After:**
```yaml
redis:
  image: redis:7-alpine
  container_name: pazpaz-redis
  command: redis-server --requirepass ${REDIS_PASSWORD}
  environment:
    REDIS_PASSWORD: ${REDIS_PASSWORD}
  ports:
    - "127.0.0.1:6379:6379"  # Bind to localhost only
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

**Key changes:**
- Added `command: redis-server --requirepass ${REDIS_PASSWORD}`
- Added `environment:` section with `REDIS_PASSWORD`
- Changed port binding from `"6379:6379"` to `"127.0.0.1:6379:6379"`
- Updated health check command

Save and exit.

### Step 5: Restart Services

```bash
# Start services
docker-compose up -d

# Monitor logs
docker-compose logs -f
```

**Expected output:**

```
pazpaz-redis    | 1:C 03 Oct 2025 12:00:00.000 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
pazpaz-redis    | 1:C 03 Oct 2025 12:00:00.000 * Redis version=7.x.x
pazpaz-api      | {"event": "redis_connection_initialized", "url": "localhost:6379/0"}
```

Press `Ctrl+C` to exit log monitoring.

### Step 6: Verify Redis Authentication

**Test 1: Connection without password should fail**

```bash
docker exec pazpaz-redis redis-cli ping
```

**Expected output:**
```
(error) NOAUTH Authentication required.
```

If you see this error, authentication is working correctly!

**Test 2: Connection with password should succeed**

```bash
docker exec pazpaz-redis redis-cli -a $REDIS_PASSWORD ping
```

**Expected output:**
```
PONG
```

### Step 7: Verify Application Connection

**Check application logs:**

```bash
docker-compose logs api | grep redis
```

**Expected output:**
```
{"event": "redis_connection_initialized", "url": "localhost:6379/0"}
```

**Test health endpoint:**

```bash
curl http://localhost:8000/health
```

**Expected output:**
```json
{"status": "ok"}
```

### Step 8: Test External Access (Security Validation)

From a **different machine** on the same network:

```bash
# This should timeout or refuse connection
redis-cli -h <your-server-ip> ping

# Expected: Connection refused or timeout
```

If you can connect from an external machine, **STOP** and review your `docker-compose.yml`. The Redis port should be bound to `127.0.0.1` only.

## Post-Migration Validation

### Checklist

- [ ] Redis requires password (Test 1 failed with NOAUTH)
- [ ] Redis accepts correct password (Test 2 returned PONG)
- [ ] Application connects successfully (logs show `redis_connection_initialized`)
- [ ] Health endpoint returns `{"status": "ok"}`
- [ ] External connections are refused (security test passed)
- [ ] Application functionality works (can create/view appointments, clients, etc.)

### Smoke Tests

**Test basic application functionality:**

```bash
# Create a test client (adjust based on your API)
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Client", "email": "test@example.com"}'

# List clients
curl http://localhost:8000/api/v1/clients

# Test caching (if implemented)
# First request should be slower, second should be cached
time curl http://localhost:8000/api/v1/clients
time curl http://localhost:8000/api/v1/clients
```

## Rollback Procedure

If authentication causes issues and you need to rollback:

### Step 1: Remove Authentication (Temporary)

Edit `docker-compose.yml`:

```yaml
redis:
  image: redis:7-alpine
  container_name: pazpaz-redis
  # Remove: command: redis-server --requirepass ${REDIS_PASSWORD}
  # Remove: environment section
  ports:
    - "127.0.0.1:6379:6379"  # Keep localhost binding for security
  volumes:
    - redis_data:/data
```

### Step 2: Restart Redis

```bash
docker-compose restart redis
```

### Step 3: Debug Application Connection

```bash
# Check application logs
docker-compose logs api | grep redis

# Test Redis directly
docker exec pazpaz-redis redis-cli ping
# Should return: PONG (no password required)
```

### Step 4: Fix Application Connection Issues

Common issues:
- **Wrong password in `.env`**: Verify `REDIS_PASSWORD` matches `docker-compose.yml`
- **Malformed `REDIS_URL`**: Should be `redis://:PASSWORD@host:port/db` (note colon before password)
- **Environment variables not loaded**: Restart application: `docker-compose restart api`

### Step 5: Re-apply Authentication

Once issues are fixed, follow Steps 4-7 again.

## Troubleshooting

### Problem: "NOAUTH Authentication required" in application logs

**Cause:** Application is not sending password to Redis.

**Solutions:**
1. Verify `REDIS_URL` in `.env` includes password:
   ```bash
   echo $REDIS_URL
   # Should show: redis://:PASSWORD@localhost:6379/0
   ```

2. Restart application:
   ```bash
   docker-compose restart api
   ```

3. Verify settings are loaded:
   ```bash
   docker-compose exec api env | grep REDIS
   ```

### Problem: "Connection refused" from application

**Cause:** Redis is not running or port binding is incorrect.

**Solutions:**
1. Check Redis status:
   ```bash
   docker-compose ps redis
   ```

2. Check Redis logs:
   ```bash
   docker-compose logs redis
   ```

3. Verify port binding in `docker-compose.yml`:
   ```yaml
   ports:
     - "127.0.0.1:6379:6379"  # Correct
     # Not: - "6379:6379"       # Wrong (allows external access)
   ```

### Problem: Health check failing

**Symptoms:**
```bash
docker-compose ps
# Shows redis as "unhealthy"
```

**Cause:** Health check command doesn't include password.

**Solution:**

Update health check in `docker-compose.yml`:

```yaml
healthcheck:
  test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
  interval: 10s
  timeout: 3s
  retries: 3
```

Then restart:
```bash
docker-compose restart redis
```

### Problem: Data loss after migration

**Cause:** Redis data not persisted or backup failed.

**Recovery:**

1. If you have a backup:
   ```bash
   docker cp ~/redis-backups/redis-backup-TIMESTAMP.rdb pazpaz-redis:/data/dump.rdb
   docker-compose restart redis
   ```

2. If no backup:
   - Cache data will rebuild automatically
   - Background jobs may need to be re-queued (check job queue documentation)
   - Sessions will be logged out (users need to re-login)

## Migration for CI/CD Pipelines

If you're using automated deployment:

### GitHub Actions Example

```yaml
- name: Generate Redis password
  run: echo "REDIS_PASSWORD=$(openssl rand -base64 32)" >> $GITHUB_ENV

- name: Update .env
  run: |
    echo "REDIS_PASSWORD=${{ env.REDIS_PASSWORD }}" >> backend/.env
    echo "REDIS_URL=redis://:${{ env.REDIS_PASSWORD }}@localhost:6379/0" >> backend/.env

- name: Deploy
  run: docker-compose up -d
```

### Store Password in Secrets Manager

**AWS Secrets Manager:**

```bash
# Store password
aws secretsmanager create-secret \
  --name pazpaz/redis-password \
  --secret-string "$(openssl rand -base64 32)"

# Retrieve in application startup
REDIS_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id pazpaz/redis-password \
  --query SecretString \
  --output text)
```

## Production Considerations

### Security Hardening

After migration:

1. **Enable Redis ACLs** (Redis 6+):
   ```bash
   docker exec pazpaz-redis redis-cli -a $REDIS_PASSWORD ACL SETUSER appuser on >newpassword ~* +@all
   ```

2. **Rotate passwords every 90 days**:
   - Generate new password
   - Update `.env`
   - Restart services
   - Update secrets manager

3. **Enable TLS in production**:
   See [REDIS_CONFIGURATION.md](REDIS_CONFIGURATION.md) for TLS setup

4. **Monitor failed authentication attempts**:
   ```bash
   docker-compose logs redis | grep "NOAUTH"
   ```

5. **Set memory limits**:
   ```yaml
   redis:
     deploy:
       resources:
         limits:
           memory: 512M
   ```

## Support

If you encounter issues during migration:

1. Check logs: `docker-compose logs`
2. Review [REDIS_CONFIGURATION.md](REDIS_CONFIGURATION.md)
3. Open GitHub issue with:
   - Migration step where error occurred
   - Error messages from logs
   - Output of `docker-compose ps`
   - Redis configuration (redact password!)

## Summary

This migration adds critical security to your Redis instance by:
- ✅ Requiring password authentication
- ✅ Binding to localhost only (no external access)
- ✅ Protecting PII/PHI data in cache and queues
- ✅ Meeting compliance requirements for healthcare data

**Total time:** 5-10 minutes with ~2-5 minutes downtime

**Impact:** No data loss (if backed up), cache will rebuild automatically
