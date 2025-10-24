# Local Production Testing Guide

## Overview

This guide provides comprehensive instructions for testing the PazPaz production Docker Compose stack locally. The testing procedure validates all aspects of the production deployment including network isolation, service health, and HIPAA compliance requirements.

## Prerequisites

### Required Software
- Docker Engine 20.10+ with Docker Compose v2
- bash 4.0+ (for script execution)
- curl (for endpoint testing)
- nc (netcat) for network testing
- jq (for JSON parsing)

### Required Files
- `docker-compose.prod.yml` - Production Docker Compose configuration
- `.env.production` - Production environment variables
- `scripts/test-production-local.sh` - Automated testing script
- `scripts/validate-env.sh` - Environment validation script

### System Requirements
- Minimum 8GB RAM available for Docker
- 20GB free disk space
- Ports 80 and 443 available on host

## Quick Start

### Automated Testing

Run the complete test suite with cleanup:

```bash
./scripts/test-production-local.sh --cleanup
```

### Manual Testing

Follow the step-by-step procedures below for manual validation.

## Testing Procedures

### Task 3.20: Prepare Test Environment

#### 1. Create Test Environment File

**IMPORTANT**: Never commit the `.env.production` file to version control.

```bash
# Copy the example template
cp .env.production.example .env.production

# Edit with your test values
nano .env.production
```

Example test configuration:

```env
# GitHub/Docker Registry
GITHUB_REPOSITORY=yourusername/pazpaz
IMAGE_TAG=latest
VERSION=test

# Database (generate secure password)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
DB_SSL_ENABLED=true

# Redis (generate secure password)
REDIS_PASSWORD=$(openssl rand -base64 32)

# MinIO/S3
S3_ACCESS_KEY=$(openssl rand -hex 16)
S3_SECRET_KEY=$(openssl rand -base64 32)
S3_BUCKET_NAME=pazpaz-test-attachments
S3_REGION=us-east-1
MINIO_ENCRYPTION_KEY=$(openssl rand -base64 32)

# Application Security
SECRET_KEY=$(openssl rand -base64 64)
JWT_SECRET_KEY=$(openssl rand -base64 32)
ENCRYPTION_MASTER_KEY=$(openssl rand -base64 32)

# Application Configuration
FRONTEND_URL=http://localhost
ALLOWED_HOSTS=localhost,127.0.0.1

# Email (using MailHog for testing)
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=test@pazpaz.local
SMTP_PASSWORD=testpassword
SMTP_USE_TLS=false
EMAILS_FROM_EMAIL=noreply@pazpaz.local
```

#### 2. Validate Environment

```bash
./scripts/validate-env.sh
```

Expected output:
```
✓ All required variables are present
✓ All secrets meet strength requirements
✓ No example/placeholder values found
✓ All value formats are valid
✅ VALIDATION PASSED: All checks successful!
```

#### 3. Clean Previous Test Runs

```bash
# Stop and remove all containers
docker-compose -f docker-compose.prod.yml down

# Remove all volumes (WARNING: data loss)
docker-compose -f docker-compose.prod.yml down -v

# Remove test images (optional)
docker rmi $(docker images -q "pazpaz/*")
```

### Task 3.21: Start Production Stack

#### 1. Pull or Build Images

For production testing, images should be pulled from the registry:

```bash
# Pull images from GitHub Container Registry
docker-compose -f docker-compose.prod.yml pull
```

If images don't exist yet, build them locally:

```bash
# Build backend image
docker build -t ghcr.io/yourusername/pazpaz/backend:latest ./backend

# Build frontend image
docker build -t ghcr.io/yourusername/pazpaz/frontend:latest ./frontend
```

#### 2. Start the Stack

```bash
# Start all services in detached mode
docker-compose -f docker-compose.prod.yml up -d

# Monitor startup logs
docker-compose -f docker-compose.prod.yml logs -f
```

#### 3. Verify Container Status

```bash
# Check all containers are running
docker-compose -f docker-compose.prod.yml ps

# Expected output (all services "Up"):
NAME                STATUS              PORTS
pazpaz-nginx        Up (healthy)        0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
pazpaz-api          Up (healthy)
pazpaz-arq-worker   Up (healthy)
pazpaz-db           Up (healthy)
pazpaz-redis        Up (healthy)
pazpaz-minio        Up (healthy)
pazpaz-clamav       Up (healthy)
pazpaz-frontend     Up (healthy)
```

#### 4. Check for Restart Loops

```bash
# No containers should be restarting
docker-compose -f docker-compose.prod.yml ps | grep -c "Restarting"
# Expected: 0
```

### Task 3.22: Verify Network Isolation

**CRITICAL**: This validates HIPAA-required network isolation.

#### 1. Test Database Isolation

```bash
# Database should NOT be accessible from host
nc -zv localhost 5432
# Expected: Connection refused

# But should be accessible internally
docker exec pazpaz-api nc -zv db 5432
# Expected: Connection successful
```

#### 2. Test Redis Isolation

```bash
# Redis should NOT be accessible from host
nc -zv localhost 6379
# Expected: Connection refused

# But should be accessible internally
docker exec pazpaz-api nc -zv redis 6379
# Expected: Connection successful
```

#### 3. Test MinIO Isolation

```bash
# MinIO should NOT be accessible from host
nc -zv localhost 9000
nc -zv localhost 9001
# Expected: Connection refused for both
```

#### 4. Verify Network Configuration

```bash
# List PazPaz networks
docker network ls --filter "label=app=pazpaz"

# Inspect network isolation
docker network inspect pazpaz_backend | grep "Internal"
# Expected: "Internal": true

docker network inspect pazpaz_database | grep "Internal"
# Expected: "Internal": true
```

### Task 3.23: Test API Endpoints via Nginx

#### 1. Test Health Check

```bash
# API health endpoint
curl -v http://localhost/api/v1/health

# Expected response:
HTTP/1.1 200 OK
Content-Type: application/json
{"status":"healthy","timestamp":"..."}
```

#### 2. Test API Documentation

```bash
# OpenAPI documentation
curl -I http://localhost/api/docs

# Expected: 200 OK or 307 Redirect
```

#### 3. Verify Security Headers

```bash
# Check response headers
curl -I http://localhost/api/v1/health | grep -E "X-Content-Type-Options|X-Frame-Options|X-XSS-Protection"

# Expected headers:
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

#### 4. Test Rate Limiting (Optional)

```bash
# Send rapid requests
for i in {1..50}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/v1/health; done | sort | uniq -c

# Expected: Some 429 (Too Many Requests) responses if rate limiting is enabled
```

### Task 3.24: Test Frontend via Nginx

#### 1. Test Frontend Root

```bash
# Frontend should be accessible
curl -I http://localhost/

# Expected: 200 OK
```

#### 2. Verify HTML Content

```bash
# Check for Vue.js application
curl -s http://localhost/ | head -20

# Expected: HTML with Vue app mount point
<!DOCTYPE html>
<html>
  <head>
    <title>PazPaz</title>
    ...
  </head>
  <body>
    <div id="app"></div>
    ...
  </body>
</html>
```

#### 3. Test Static Assets

```bash
# Check for compressed responses
curl -H "Accept-Encoding: gzip" -I http://localhost/

# Expected header:
Content-Encoding: gzip
```

#### 4. Verify CSP Headers

```bash
# Check Content Security Policy
curl -I http://localhost/ | grep "Content-Security-Policy"

# Expected: CSP header present
```

### Task 3.25: Test Database Migrations

#### 1. Run Migrations

```bash
# Execute Alembic migrations
docker exec pazpaz-api alembic upgrade head

# Expected: Migrations applied successfully
```

#### 2. Verify Tables

```bash
# List database tables
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\dt"

# Expected tables:
- workspace
- user
- client
- appointment
- session
- service
- location
- plan_of_care
- audit_event
- alembic_version
```

#### 3. Test Data Persistence

```bash
# Create test data
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "
CREATE TABLE test_table (id serial primary key, data text);
INSERT INTO test_table (data) VALUES ('test');
SELECT * FROM test_table;
"

# Restart container
docker-compose -f docker-compose.prod.yml restart db

# Verify data persists
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT * FROM test_table;"

# Clean up
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "DROP TABLE test_table;"
```

### Task 3.26: Test Background Worker

#### 1. Check Worker Status

```bash
# Verify worker is running
docker ps --filter "name=pazpaz-arq-worker"

# Check worker logs
docker logs pazpaz-arq-worker --tail 50

# Expected: No errors, worker connected to Redis
```

#### 2. Test Worker Process

```bash
# Verify ARQ process
docker exec pazpaz-arq-worker pgrep -f "arq"

# Expected: Process ID returned
```

#### 3. Test Redis Connection

```bash
# Worker should connect to Redis
docker exec pazpaz-arq-worker nc -zv redis 6379

# Expected: Connection successful
```

### Task 3.27: Verify Health Checks

#### 1. Check Individual Service Health

```bash
# Check health status for each service
for service in nginx api arq-worker db redis minio clamav frontend; do
  echo "Checking $service..."
  docker inspect pazpaz-$service | jq '.[0].State.Health.Status'
done

# Expected: All services report "healthy"
```

#### 2. Monitor Health Check Logs

```bash
# View recent health check results
docker inspect pazpaz-api | jq '.[0].State.Health.Log[-3:]'
```

#### 3. Test Endpoint Health Checks

```bash
# Nginx health
curl http://localhost/health

# API health
docker exec pazpaz-api curl http://localhost:8000/health

# Frontend health
docker exec pazpaz-frontend wget --spider http://localhost:80/
```

### Task 3.28: Verify Log Rotation

#### 1. Check Log Configuration

```bash
# Verify log driver settings
docker inspect pazpaz-api | jq '.[] | .HostConfig.LogConfig'

# Expected output:
{
  "Type": "json-file",
  "Config": {
    "max-file": "3",
    "max-size": "10m"
  }
}
```

#### 2. Check Log Volumes

```bash
# List log volumes
docker volume ls --filter "label=type=logs"

# Expected volumes:
- pazpaz_app_logs
- pazpaz_nginx_logs
```

#### 3. Verify Log Writing

```bash
# Check nginx logs
docker exec pazpaz-nginx ls -la /var/log/nginx/

# Check application logs
docker exec pazpaz-api ls -la /app/logs/

# View recent logs
docker logs --tail 20 pazpaz-api
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Images Not Found

**Problem**: `docker-compose pull` fails with "image not found"

**Solution**:
```bash
# Build images locally
docker build -t ghcr.io/yourusername/pazpaz/backend:latest ./backend
docker build -t ghcr.io/yourusername/pazpaz/frontend:latest ./frontend
```

#### 2. Port Already in Use

**Problem**: "bind: address already in use"

**Solution**:
```bash
# Find process using port 80
sudo lsof -i :80

# Stop conflicting service or use different ports
```

#### 3. Container Health Check Failures

**Problem**: Services show "unhealthy" status

**Solution**:
```bash
# Check health check logs
docker inspect <container> | jq '.[0].State.Health.Log'

# Check container logs
docker logs <container> --tail 100

# Restart unhealthy container
docker-compose -f docker-compose.prod.yml restart <service>
```

#### 4. Database Connection Errors

**Problem**: API cannot connect to database

**Solution**:
```bash
# Verify database is running
docker ps --filter "name=pazpaz-db"

# Check database logs
docker logs pazpaz-db

# Test connection manually
docker exec pazpaz-api nc -zv db 5432

# Check environment variables
docker exec pazpaz-api env | grep DATABASE_URL
```

#### 5. Network Isolation Too Restrictive

**Problem**: Services cannot communicate internally

**Solution**:
```bash
# Verify network configuration
docker network ls --filter "label=app=pazpaz"

# Inspect network settings
docker network inspect pazpaz_backend
docker network inspect pazpaz_database

# Ensure services are on correct networks
docker inspect pazpaz-api | jq '.[0].NetworkSettings.Networks | keys'
```

## Performance Validation

### Response Time Testing

```bash
# Test API response times (p95 should be <150ms)
for i in {1..100}; do
  curl -w "@curl-format.txt" -o /dev/null -s http://localhost/api/v1/health
done | awk '{sum+=$1; sumsq+=$1*$1} END {print "Mean:", sum/NR, "StdDev:", sqrt(sumsq/NR - (sum/NR)^2)}'
```

Create `curl-format.txt`:
```
%{time_total}\n
```

### Resource Usage Monitoring

```bash
# Monitor container resource usage
docker stats --no-stream

# Check specific container
docker stats pazpaz-api --no-stream
```

## Security Validation

### SSL/TLS Configuration

```bash
# Test SSL certificate (when configured)
openssl s_client -connect localhost:443 -servername pazpaz.local

# Verify cipher suites
nmap --script ssl-enum-ciphers -p 443 localhost
```

### Security Headers Audit

```bash
# Full security header check
curl -I https://localhost/ | grep -E "Strict-Transport-Security|Content-Security-Policy|X-Frame-Options|X-Content-Type-Options|X-XSS-Protection"
```

## Cleanup Procedures

### Stop All Services

```bash
# Stop containers
docker-compose -f docker-compose.prod.yml down

# Stop and remove volumes (WARNING: data loss)
docker-compose -f docker-compose.prod.yml down -v
```

### Remove Test Data

```bash
# Remove test environment file
rm .env.production

# Remove test certificates
rm -rf ./certs/test/

# Remove log files
docker volume rm pazpaz_app_logs pazpaz_nginx_logs
```

### Clean Docker System

```bash
# Remove unused containers, networks, images
docker system prune -a

# Remove all PazPaz-related resources
docker ps -a --filter "label=app=pazpaz" -q | xargs docker rm -f
docker network ls --filter "label=app=pazpaz" -q | xargs docker network rm
docker volume ls --filter "label=app=pazpaz" -q | xargs docker volume rm
```

## CI/CD Integration

### Using the Test Script in CI

```yaml
# GitHub Actions example
- name: Test Production Stack
  run: |
    ./scripts/test-production-local.sh --cleanup
  env:
    GITHUB_REPOSITORY: ${{ github.repository }}
    IMAGE_TAG: ${{ github.sha }}
```

### Exit Codes

The test script returns specific exit codes:

- `0` - All tests passed
- `1` - Environment validation failed
- `2` - Docker stack startup failed
- `3` - Network isolation test failed
- `4` - Service health check failed
- `5` - API/Frontend test failed

## Best Practices

### Before Production Deployment

1. **Always test locally first** - Run the full test suite
2. **Validate secrets** - Ensure all secrets are strong and unique
3. **Check resource limits** - Verify containers have appropriate limits
4. **Test rollback procedure** - Practice reverting to previous version
5. **Document any deviations** - Note any test failures or warnings

### Testing Checklist

- [ ] Environment variables validated
- [ ] All containers start successfully
- [ ] No containers in restart loop
- [ ] Database NOT accessible from host
- [ ] Redis NOT accessible from host
- [ ] Internal network communication works
- [ ] API endpoints respond correctly
- [ ] Frontend loads successfully
- [ ] Security headers present
- [ ] Health checks passing
- [ ] Logs being written and rotated
- [ ] Background worker processing jobs
- [ ] Data persists across restarts

## Additional Resources

- [Docker Compose Production Best Practices](https://docs.docker.com/compose/production/)
- [HIPAA Compliance Requirements](../security/HIPAA_COMPLIANCE.md)
- [Network Architecture](./NETWORK_ARCHITECTURE.md)
- [SSL Certificate Management](./SSL_CERTIFICATE_MANAGEMENT.md)
- [Production Deployment Checklist](./PRODUCTION_DEPLOYMENT_CHECKLIST.md)

## Support

For issues or questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review container logs: `docker logs <container-name>`
3. Consult the [deployment documentation](./README.md)
4. Check GitHub Issues for known problems
5. Contact the DevOps team

---

**Last Updated**: October 24, 2024
**Version**: 1.0.0
**Status**: Ready for Testing