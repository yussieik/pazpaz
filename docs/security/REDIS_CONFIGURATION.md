# Redis Configuration

## Security Requirements

PazPaz uses Redis for caching and background job queues. Redis MUST be configured with authentication to prevent unauthorized access to sensitive data.

**Why this matters:**
- Redis may cache PII/PHI (client names, appointment data)
- Background job payloads may contain sensitive information
- Unauthenticated Redis is a critical security vulnerability
- Network-accessible Redis without password = data breach waiting to happen

## Configuration

### 1. Environment Variables

Add to `.env`:

```bash
# Generate strong password (32+ characters)
REDIS_PASSWORD=<strong-random-password-32-chars-min>
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
```

**Generate strong password:**

```bash
# Option 1: OpenSSL (recommended)
openssl rand -base64 32

# Option 2: Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 3: /dev/urandom
head -c 32 /dev/urandom | base64
```

### 2. Docker Compose Configuration

Redis is configured in `docker-compose.yml` with:

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

**Security features:**
- `--requirepass`: Requires password authentication
- `127.0.0.1:6379`: Binds to localhost only (not accessible from external network)
- Health check: Validates Redis is running and responsive

### 3. Application Configuration

All Redis clients use authenticated connection via `settings.redis_url`.

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

## Testing

### Verify Redis Authentication

**Test 1: Connection without password should fail**

```bash
# Should fail with: (error) NOAUTH Authentication required
docker exec pazpaz-redis redis-cli ping
```

**Test 2: Connection with password should succeed**

```bash
# Should return: PONG
docker exec pazpaz-redis redis-cli -a $REDIS_PASSWORD ping
```

**Test 3: Application should connect successfully**

```bash
# Start services
docker-compose up -d

# Check logs for Redis connection success
docker-compose logs api | grep redis_connection_initialized

# Expected output:
# {"event": "redis_connection_initialized", "url": "localhost:6379/0"}
```

**Test 4: External connections should fail**

```bash
# From different machine (should timeout or refuse connection)
redis-cli -h <server-ip> ping
# Connection refused or timeout
```

### Health Check Endpoint

Add Redis health check to API:

```python
from pazpaz.core.redis import check_redis_health

@app.get("/api/v1/health")
async def health_check():
    redis_healthy = await check_redis_health()
    return {
        "status": "ok" if redis_healthy else "degraded",
        "redis": "healthy" if redis_healthy else "unhealthy"
    }
```

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
```
healthcheck failed: ERR operation not permitted
```

**Solution:**
Update health check command to use authentication:

```yaml
healthcheck:
  test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
```

## Best Practices

1. **Never commit passwords**: Use `.env` (gitignored) for local development
2. **Use secrets manager in production**: AWS Secrets Manager, HashiCorp Vault, etc.
3. **Rotate passwords regularly**: Every 90 days minimum
4. **Monitor failed auth attempts**: Enable Redis logging and alert on `NOAUTH` errors
5. **Limit Redis commands**: Use Redis ACLs to restrict dangerous commands (FLUSHALL, KEYS, etc.)
6. **Set connection limits**: Configure `maxclients` in Redis
7. **Use separate Redis instances**: Different databases/instances for cache vs sessions vs queues

## References

- [Redis Security Documentation](https://redis.io/docs/manual/security/)
- [Redis ACL Documentation](https://redis.io/docs/manual/security/acl/)
- [Redis TLS Documentation](https://redis.io/docs/manual/security/encryption/)
- [OWASP Redis Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Redis_Security_Cheat_Sheet.html)
