# Frontend Docker Configuration

## Overview

The PazPaz frontend uses a multi-stage Docker build to create an optimized, secure, production-ready container for serving the Vue.js application through Nginx.

## Files

- **`frontend/Dockerfile`** - Multi-stage build for production
- **`frontend/nginx.conf`** - Nginx configuration for standalone testing
- **`frontend/nginx.prod.conf`** - Nginx configuration for production with API proxy
- **`frontend/.dockerignore`** - Excludes unnecessary files from build context
- **`frontend/docker-compose.example.yml`** - Example production deployment

## Build Process

### Multi-Stage Build

1. **Dependencies Stage** - Installs npm packages with caching
2. **Builder Stage** - Builds the Vue.js application
3. **Production Stage** - Minimal nginx:alpine image with built assets

### Build Commands

```bash
# Build the image
cd frontend
docker build -t pazpaz-frontend:latest .

# Build with specific tag
docker build -t pazpaz-frontend:v1.0.0 .

# Build and load for local testing
docker build -t pazpaz-frontend:test --load .
```

## Security Features

### 1. Non-Root User
- Runs as `nginx` user (UID 101)
- No root privileges in runtime container

### 2. Security Headers
All responses include HIPAA-compliant security headers:
- **Content-Security-Policy** - Prevents XSS attacks
- **Strict-Transport-Security** - Forces HTTPS (HSTS)
- **X-Frame-Options** - Prevents clickjacking
- **X-Content-Type-Options** - Prevents MIME sniffing
- **X-XSS-Protection** - Legacy XSS protection
- **Referrer-Policy** - Controls referrer information
- **Permissions-Policy** - Disables unnecessary browser features

### 3. Rate Limiting
Protects against DoS attacks:
- General requests: 10 req/s
- API requests: 30 req/s
- Static assets: 100 req/s

### 4. Minimal Attack Surface
- Alpine Linux base (small footprint)
- Only necessary packages installed
- Regular security updates applied during build

## Performance Optimizations

### 1. Image Size
- **Final size: ~62MB** (well under 100MB target)
- Multi-stage build discards build dependencies
- Alpine Linux minimizes base image size

### 2. Compression
- Gzip compression enabled for all text assets
- Compression level 6 (optimal balance)
- Brotli ready (if nginx module available)

### 3. Caching Strategy
- Static assets: 1 year cache (`immutable`)
- HTML files: No cache (always fresh)
- Build output includes content hashes

### 4. Layer Caching
- Dependencies cached in separate layer
- Only rebuilds when package.json changes

## Configuration

### Standalone Mode (Testing)
Uses `nginx.conf` with API endpoints returning 503:
```bash
docker run -p 8080:80 pazpaz-frontend:test
```

### Production Mode
Uses `nginx.prod.conf` with Docker Compose:
```bash
# In production with docker-compose
docker-compose up -d
```

### Environment Variables
The build handles Vite environment variables:
- `VITE_API_URL` - API endpoint URL
- `VITE_CSP_SCRIPT_SRC` - CSP script source (dev only)

## Health Checks

The container includes a health check endpoint:
```bash
# Test health
curl http://localhost:80/health
# Returns: healthy
```

Docker health check configuration:
- Interval: 30s
- Timeout: 3s
- Retries: 3
- Start period: 5s

## Deployment

### Local Testing
```bash
# Build and run
docker build -t pazpaz-frontend:test .
docker run -d -p 8080:80 --name pazpaz-frontend pazpaz-frontend:test

# Verify
curl -I http://localhost:8080
docker logs pazpaz-frontend

# Clean up
docker stop pazpaz-frontend
docker rm pazpaz-frontend
```

### Production with Docker Compose
```bash
# Copy production nginx config
cp nginx.prod.conf nginx.conf

# Build and deploy
docker-compose up -d

# Scale if needed
docker-compose up -d --scale web=2
```

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Build Frontend
  run: |
    cd frontend
    docker build -t pazpaz-frontend:${{ github.sha }} .
    docker tag pazpaz-frontend:${{ github.sha }} pazpaz-frontend:latest

- name: Push to Registry
  run: |
    docker push pazpaz-frontend:${{ github.sha }}
    docker push pazpaz-frontend:latest
```

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   - Ensure nginx user owns required directories
   - Check `/tmp/nginx.pid` permissions

2. **502 Bad Gateway**
   - In production: Check if backend is running
   - Verify Docker network connectivity

3. **Assets Not Loading**
   - Check nginx logs: `docker logs <container>`
   - Verify build completed successfully

4. **Large Image Size**
   - Check `.dockerignore` is working
   - Ensure multi-stage build is functioning

### Debug Commands
```bash
# Check image layers
docker history pazpaz-frontend:test

# Inspect running container
docker exec -it pazpaz-frontend sh

# Check nginx configuration
docker exec pazpaz-frontend nginx -t

# View nginx logs
docker logs -f pazpaz-frontend

# Check file permissions
docker exec pazpaz-frontend ls -la /usr/share/nginx/html
```

## Maintenance

### Updating Dependencies
```bash
# Update base images
docker pull node:20-alpine
docker pull nginx:stable-alpine

# Rebuild with --no-cache
docker build --no-cache -t pazpaz-frontend:latest .
```

### Security Scanning
```bash
# Scan with Trivy
trivy image pazpaz-frontend:latest

# Scan with Docker Scout
docker scout cves pazpaz-frontend:latest
```

## Best Practices

1. **Always use multi-stage builds** to minimize image size
2. **Pin base image versions** for reproducibility
3. **Run as non-root user** for security
4. **Include health checks** for orchestration
5. **Use .dockerignore** to exclude unnecessary files
6. **Implement proper caching** headers for performance
7. **Enable compression** for text assets
8. **Set security headers** for HIPAA compliance
9. **Use secrets management** for sensitive data
10. **Regular security updates** of base images

## Related Documentation

- [CI/CD Implementation Plan](./CI_CD_IMPLEMENTATION_PLAN.md)
- [Backend Docker Configuration](./backend-docker.md)
- [Security Requirements](../security/README.md)
- [Deployment Guide](./README.md)