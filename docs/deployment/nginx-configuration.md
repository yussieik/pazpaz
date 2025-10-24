# Nginx Configuration

## Overview

PazPaz uses Nginx as a reverse proxy to handle all incoming traffic, provide SSL/TLS termination, and route requests to the appropriate services. The configuration is HIPAA-compliant with security hardening and performance optimizations.

## Configuration Files

### nginx.conf
- **Location**: `/nginx/nginx.conf`
- **Purpose**: Development and non-SSL production configuration
- **Use Case**: Local development, initial deployment before SSL setup

### nginx-ssl.conf
- **Location**: `/nginx/nginx-ssl.conf`
- **Purpose**: Production configuration with SSL/TLS enabled
- **Use Case**: Production deployment with Let's Encrypt certificates
- **Variables**: Uses `${DOMAIN_NAME}` placeholder that must be replaced during deployment

## SSL/TLS Configuration

### Certificate Requirements
- TLS 1.2+ (HIPAA requirement)
- Strong cipher suites only
- OCSP stapling enabled
- HSTS header with 1-year max-age

### Certificate Paths
```nginx
ssl_certificate /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem;
ssl_trusted_certificate /etc/letsencrypt/live/${DOMAIN_NAME}/chain.pem;
```

### Diffie-Hellman Parameters
```bash
# Generate DH parameters (production should use 2048 or 4096 bits)
openssl dhparam -out /etc/nginx/dhparam.pem 2048
```

## Security Headers

All responses include the following security headers:

- **X-Frame-Options**: DENY (prevents clickjacking)
- **X-Content-Type-Options**: nosniff (prevents MIME type sniffing)
- **X-XSS-Protection**: 1; mode=block (XSS protection for older browsers)
- **Content-Security-Policy**: Strict policy for Vue.js application
- **Referrer-Policy**: strict-origin-when-cross-origin
- **Permissions-Policy**: Restricts browser features
- **Strict-Transport-Security**: max-age=31536000; includeSubDomains; preload (HSTS)

## Rate Limiting

### Zones Configuration
```nginx
# General API rate limiting (10 requests per second)
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

# Authentication endpoints (5 requests per minute - stricter)
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

# Static files (100 requests per second)
limit_req_zone $binary_remote_addr zone=static:10m rate=100r/s;

# WebSocket connections (5 connections per second)
limit_req_zone $binary_remote_addr zone=websocket:10m rate=5r/s;

# Connection limiting per IP (10 concurrent connections)
limit_conn_zone $binary_remote_addr zone=addr:10m;
```

### Application
- `/api/*`: 10 req/s with burst of 20
- `/api/v1/auth/*`: 5 req/min with burst of 2
- `/ws/*`: 5 conn/s with burst of 5
- Static files: 100 req/s with burst of 50

## Custom Error Pages

Custom error pages are located in `/nginx/error-pages/`:

- **404.html**: Page not found
- **429.html**: Too many requests (rate limiting)
- **50x.html**: Server errors (500, 502, 503, 504)

Error pages are styled with a consistent, user-friendly design that maintains the PazPaz brand.

## Upstream Configuration

### Backend API
```nginx
upstream backend_api {
    least_conn;
    server api:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

### Frontend Application
```nginx
upstream frontend_app {
    server frontend:80 max_fails=3 fail_timeout=30s;
    keepalive 16;
}
```

## Performance Optimizations

### Gzip Compression
- Enabled for text-based content
- Compression level: 6
- Minimum length: 1024 bytes

### Caching
- Static assets: 1 year cache with immutable flag
- File descriptor cache: max=2000, inactive=20s

### Buffer Sizes
- Client body buffer: 16k
- Client header buffer: 1k
- Large client headers: 4 buffers of 8k
- Client max body size: 100MB (for file uploads)

## Health Check Endpoint

```nginx
location /health {
    access_log off;
    add_header Content-Type text/plain;
    return 200 "healthy\n";
}
```

Used by:
- Docker health checks
- Load balancer health probes
- Monitoring systems (UptimeRobot)

## Docker Configuration

### Dockerfile
- Base image: `nginx:alpine`
- Non-root user execution
- Health check included
- Minimal attack surface

### Build Command
```bash
docker build -t pazpaz/nginx:latest -f nginx/Dockerfile nginx/
```

### Docker Compose Integration
```yaml
services:
  nginx:
    build: ./nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - letsencrypt:/etc/letsencrypt
    depends_on:
      - api
      - frontend
```

## CI/CD Validation

The Infrastructure CI workflow validates:

1. **Syntax Validation**: Both nginx.conf and nginx-ssl.conf
2. **Security Headers**: Verifies all required headers are present
3. **Rate Limiting**: Confirms rate limiting zones are configured
4. **SSL Configuration**: Validates TLS settings meet requirements
5. **Docker Build**: Tests the Nginx image builds successfully

### CI Testing Process

1. Creates dummy SSL certificates for validation
2. Substitutes `${DOMAIN_NAME}` with `example.com`
3. Generates DH parameters (512 bits for fast CI)
4. Validates configuration syntax
5. Builds and tests Docker image

## Deployment Checklist

- [ ] Generate production DH parameters (2048+ bits)
- [ ] Obtain SSL certificates via Let's Encrypt
- [ ] Replace `${DOMAIN_NAME}` in nginx-ssl.conf
- [ ] Verify all security headers are present
- [ ] Test rate limiting configuration
- [ ] Confirm health check endpoint responds
- [ ] Validate SSL configuration with SSL Labs
- [ ] Monitor nginx error logs for issues

## Troubleshooting

### Common Issues

#### SSL Certificate Loading Failed
```
SSL_CTX_load_verify_locations() failed
```
**Solution**: Ensure certificates exist at the specified paths and have correct permissions.

#### Upstream Connection Failed
```
connect() failed (111: Connection refused)
```
**Solution**: Verify backend services are running and accessible.

#### Rate Limiting Too Aggressive
**Solution**: Adjust rate limits in zone definitions and burst values.

### Useful Commands

```bash
# Test nginx configuration
nginx -t -c /etc/nginx/nginx.conf

# Reload configuration without downtime
nginx -s reload

# View access logs
tail -f /var/log/nginx/access.log

# View error logs
tail -f /var/log/nginx/error.log

# Test SSL configuration
openssl s_client -connect domain.com:443
```

## Security Considerations

1. **Never expose** database ports through Nginx
2. **Always use** HTTPS in production
3. **Regularly update** Nginx and base images
4. **Monitor** rate limiting logs for attacks
5. **Implement** fail2ban for persistent attackers
6. **Rotate** SSL certificates before expiration
7. **Audit** access logs for suspicious patterns

---

*Last updated: 2025-10-24*