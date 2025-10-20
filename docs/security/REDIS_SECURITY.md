# Redis Security

**Last Updated:** 2025-10-20
**Implementation Date:** October 3, 2025 (Week 1, Day 1)
**Security Level:** Critical Infrastructure Hardening

---

## Table of Contents
1. [Overview](#overview)
2. [Security Requirements](#security-requirements)
3. [Configuration](#configuration)
4. [Migration Guide](#migration-guide)
5. [Testing & Verification](#testing--verification)
6. [Production Deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)
9. [Implementation History](#implementation-history)

---

## Overview

PazPaz uses Redis for caching and background job queues. Redis MUST be configured with authentication to prevent unauthorized access to sensitive data.

### Why This Matters

- **PII/PHI Protection:** Redis may cache client names, appointment data, and session information
- **Background Job Security:** Job payloads may contain sensitive information
- **HIPAA Compliance:** Unauthenticated Redis is a critical security vulnerability
- **Data Breach Prevention:** Network-accessible Redis without password = data breach waiting to happen

### Security Improvements Implemented

**Before (VULNERABLE):**
- ❌ No password required to connect
- ❌ Exposed on 0.0.0.0:6379 (all interfaces)
- ❌ Anyone with network access could read/write data
- ❌ PII/PHI potentially accessible without authentication

**After (SECURED):**
- ✅ Password authentication required (`--requirepass`)
- ✅ Bound to localhost only (`127.0.0.1:6379`)
- ✅ Connection test on initialization (PING with auth)
- ✅ Password masked in logs (prevents credential leaks)
- ✅ Health check monitoring
- ✅ Proper error handling and logging

---

## Security Requirements

### Authentication
- **Minimum Password Length:** 32 characters (production)
- **Character Set:** Alphanumeric + special characters
- **Rotation Schedule:** Every 90 days (documented in [CREDENTIAL_ROTATION_CHECKLIST.md](CREDENTIAL_ROTATION_CHECKLIST.md))

### Network Security
- **Production:** TLS encryption required (`rediss://` protocol)
- **Development:** Localhost binding (`127.0.0.1:6379`)
- **Network Isolation:** Firewall rules, VPC isolation (cloud deployments)

### Access Control
- **Redis 6+:** Use ACLs for fine-grained access control
- **Principle:** Least privilege (restrict dangerous commands)
- **Monitoring:** Track failed authentication attempts

---

## Configuration

### 1. Environment Variables

Add to `.env`:

```bash
# Generate strong password (32+ characters)
REDIS_PASSWORD=<strong-random-password-32-chars-min>
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
```

**Generate Strong Password:**

```bash
# Option 1: OpenSSL (recommended)
openssl rand -base64 32

# Option 2: Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 3: /dev/urandom
head -c 32 /dev/urandom | base64
```

### 2. Docker Compose Configuration

Redis is configured in `docker-compose.yml`:

```yaml
redis:
  image: redis:7-alpine
  container_name: pazpaz-redis
  command: redis-server --requirepass ${REDIS_PASSWORD}
  environment:
    REDIS_PASSWORD: ${REDIS_PASSWORD}
  ports:
    - "127.0.0.1:6379:6379"  # Localhost only
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

**Security Features:**
- `--requirepass`: Requires password authentication
- `127.0.0.1:6379`: Binds to localhost only (not accessible from external network)
- Health check: Validates Redis is running and responsive

### 3. Application Configuration

**Backend configuration (`backend/src/pazpaz/core/config.py`):**

```python
class Settings(BaseSettings):
    # Redis
    redis_password: str = "change-me-in-production"
    redis_url: str = "redis://:change-me-in-production@localhost:6379/0"
```

**Redis client (`backend/src/pazpaz/core/redis.py`):**

```python
from pazpaz.core.config import settings
import redis.asyncio as redis

_redis_client = redis.from_url(
    settings.redis_url,  # Includes password
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=5,
    socket_keepalive=True,
    health_check_interval=30,
)
```

---

## Migration Guide

### Pre-Migration Checklist

Before starting the migration, ensure:

- [ ] You have SSH/terminal access to the server
- [ ] You have permissions to edit `.env` and `docker-compose.yml`
- [ ] You can restart Docker containers
- [ ] You have a maintenance window (if production)
- [ ] You've notified users of planned downtime (if production)

### Migration Steps

#### Step 1: Backup Redis Data (Optional but Recommended)

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

#### Step 2: Generate Strong Redis Password

```bash
# Generate 32-character random password
openssl rand -base64 32

# Example output: 7Qf8K2mNxVp1rT3jL9sW6hY4cZ5bA8nU0dE1gH2iF=
```

**Save this password securely!** You'll need it in the next steps.

#### Step 3: Stop Services

```bash
# Stop all services
cd /path/to/pazpaz
docker-compose down

# Verify all containers stopped
docker-compose ps
```

#### Step 4: Update Configuration Files

**4.1: Update `.env`**

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

**4.2: Update `docker-compose.yml`**

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

#### Step 5: Restart Services

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

### Rollback Procedure

If authentication causes issues and you need to rollback:

#### Step 1: Remove Authentication (Temporary)

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

#### Step 2: Restart Redis

```bash
docker-compose restart redis
```

#### Step 3: Debug Application Connection

```bash
# Check application logs
docker-compose logs api | grep redis

# Test Redis directly
docker exec pazpaz-redis redis-cli ping
# Should return: PONG (no password required)
```

#### Step 4: Fix Application Connection Issues

Common issues:
- **Wrong password in `.env`**: Verify `REDIS_PASSWORD` matches `docker-compose.yml`
- **Malformed `REDIS_URL`**: Should be `redis://:PASSWORD@host:port/db` (note colon before password)
- **Environment variables not loaded**: Restart application: `docker-compose restart api`

#### Step 5: Re-apply Authentication

Once issues are fixed, follow Steps 4-5 again.

---

## Testing & Verification

### Test 1: Authentication Requirement

Connection without password should fail:

```bash
docker exec pazpaz-redis redis-cli ping
```

**Expected output:**
```
(error) NOAUTH Authentication required.
```

✅ **PASS** - Connection rejected without password

### Test 2: Authenticated Connection

Connection with password should succeed:

```bash
docker exec pazpaz-redis redis-cli -a $REDIS_PASSWORD ping
```

**Expected output:**
```
PONG
```

✅ **PASS** - Connection successful with correct password

### Test 3: Port Binding

Verify Redis is bound to localhost only:

```bash
docker port pazpaz-redis
```

**Expected output:**
```
6379/tcp -> 127.0.0.1:6379
```

✅ **PASS** - Redis only accessible from localhost

### Test 4: Application Connection

Check application logs:

```bash
docker-compose logs api | grep redis
```

**Expected output:**
```
{"event": "redis_connection_initialized", "url": "localhost:6379/0"}
```

Test health endpoint:

```bash
curl http://localhost:8000/health
```

**Expected output:**
```json
{"status": "ok"}
```

✅ **PASS** - Application connects and authenticates successfully

### Test 5: Health Check

Verify Docker health check is passing:

```bash
docker-compose ps
```

**Expected output:**
```
NAME             STATUS
pazpaz-redis     Up XX seconds (healthy)
```

✅ **PASS** - Docker health check passing

### Test 6: External Access (Security Validation)

From a **different machine** on the same network:

```bash
# This should timeout or refuse connection
redis-cli -h <your-server-ip> ping

# Expected: Connection refused or timeout
```

If you can connect from an external machine, **STOP** and review your `docker-compose.yml`. The Redis port should be bound to `127.0.0.1` only.

---

## Production Deployment

### Security Checklist

- [ ] Use strong password (32+ characters, generated randomly)
- [ ] Store password in secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] Enable TLS for Redis connections in production (`rediss://` protocol)
- [ ] Restrict network access via firewall rules (only allow app servers)
- [ ] Use Redis ACLs for fine-grained access control (Redis 6+)
- [ ] Enable Redis persistence (RDB or AOF) if data must survive restarts
- [ ] Monitor Redis memory usage and set `maxmemory` policy
- [ ] Rotate Redis password periodically (every 90 days)

### TLS Configuration (Production)

For production, enable TLS encryption:

**docker-compose.yml (production):**

```yaml
redis:
  image: redis:7-alpine
  command: redis-server --requirepass ${REDIS_PASSWORD} --tls-port 6380 --port 0 --tls-cert-file /tls/redis.crt --tls-key-file /tls/redis.key --tls-ca-cert-file /tls/ca.crt
  environment:
    REDIS_PASSWORD: ${REDIS_PASSWORD}
  volumes:
    - redis_data:/data
    - ./tls:/tls:ro
```

**Application configuration:**

```bash
REDIS_URL=rediss://:${REDIS_PASSWORD}@localhost:6380/0?ssl_cert_reqs=required&ssl_ca_certs=/path/to/ca.crt
```

### AWS/Cloud Deployment

**Recommended approach:**

1. **Use managed Redis service:**
   - AWS ElastiCache for Redis
   - Azure Cache for Redis
   - Google Cloud Memorystore

2. **Configuration:**
   - Enable in-transit encryption (TLS)
   - Enable at-rest encryption
   - Use VPC security groups (no public access)
   - Enable automatic backups
   - Use AUTH token (password) authentication

3. **Connection string:**
   ```bash
   REDIS_URL=rediss://:${REDIS_PASSWORD}@your-cluster.cache.amazonaws.com:6380/0
   ```

---

## Troubleshooting

### Problem: Application can't connect to Redis

**Symptoms:**
```
redis_connection_failed error="Error 111 connecting to localhost:6379. Connection refused."
```

**Solutions:**
1. Verify Redis is running: `docker-compose ps redis`
2. Check Redis logs: `docker-compose logs redis`
3. Verify password is set: `echo $REDIS_PASSWORD`
4. Test Redis connection: `docker exec pazpaz-redis redis-cli -a $REDIS_PASSWORD ping`

### Problem: Authentication failed

**Symptoms:**
```
redis_connection_failed error="NOAUTH Authentication required"
```

**Solutions:**
1. Verify `REDIS_PASSWORD` is set in `.env`
2. Verify `REDIS_URL` includes password: `redis://:PASSWORD@host:port/db`
3. Restart services: `docker-compose restart`

### Problem: Redis health check failing

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

---

## Best Practices

1. **Never commit passwords**: Use `.env` (gitignored) for local development
2. **Use secrets manager in production**: AWS Secrets Manager, HashiCorp Vault, etc.
3. **Rotate passwords regularly**: Every 90 days minimum (see [CREDENTIAL_ROTATION_CHECKLIST.md](CREDENTIAL_ROTATION_CHECKLIST.md))
4. **Monitor failed auth attempts**: Enable Redis logging and alert on `NOAUTH` errors
5. **Limit Redis commands**: Use Redis ACLs to restrict dangerous commands (FLUSHALL, KEYS, etc.)
6. **Set connection limits**: Configure `maxclients` in Redis
7. **Use separate Redis instances**: Different databases/instances for cache vs sessions vs queues

---

## Implementation History

### Week 1, Day 1 (October 3, 2025)

**Implementation:** Redis password authentication and localhost binding
**Status:** ✅ COMPLETED
**Agent:** fullstack-backend-specialist

**Deliverables:**
1. Docker Compose configuration updated
2. Environment configuration with `REDIS_PASSWORD` and `REDIS_URL`
3. Application Redis client enhanced (connection timeout, keepalive, health checks)
4. Documentation created (this file, consolidated from 3 separate docs)

**Testing Results:**
- ✅ Authentication requirement validated
- ✅ Authenticated connection successful
- ✅ Port binding to localhost verified
- ✅ Application connection tested
- ✅ Health check passing
- ✅ External access blocked

**For detailed implementation report, see:**
- [/docs/reports/implementations/redis-security-week1-day1.md](/docs/reports/implementations/redis-security-week1-day1.md)

---

## References

- [Redis Security Documentation](https://redis.io/docs/manual/security/)
- [Redis ACL Documentation](https://redis.io/docs/manual/security/acl/)
- [Redis TLS Documentation](https://redis.io/docs/manual/security/encryption/)
- [OWASP Redis Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Redis_Security_Cheat_Sheet.html)
- [CREDENTIAL_ROTATION_CHECKLIST.md](CREDENTIAL_ROTATION_CHECKLIST.md) - Password rotation procedures
- [KEY_MANAGEMENT.md](KEY_MANAGEMENT.md) - Comprehensive key management guide

---

**Last Updated:** 2025-10-20
**Next Review:** 2026-01-20 (Quarterly)
