# Nginx Reverse Proxy Configuration

This directory contains the production-ready Nginx configuration for PazPaz, serving as the main entry point for all traffic.

## Features

### Security Hardening
- **HSTS**: Strict-Transport-Security with 1-year max-age and includeSubDomains
- **CSP**: Content-Security-Policy restricting resource loading to trusted sources
- **X-Frame-Options**: DENY to prevent clickjacking
- **X-Content-Type-Options**: nosniff to prevent MIME type sniffing
- **X-XSS-Protection**: Enabled for legacy browser support
- **Server tokens**: Hidden to avoid exposing Nginx version
- **Rate limiting**: Configured for API, auth, static files, and WebSocket endpoints

### Rate Limiting Zones
- **API endpoints**: 10 requests/second with burst of 20
- **Auth endpoints**: 5 requests/minute with burst of 2 (stricter for security)
- **Static files**: 100 requests/second with burst of 50
- **WebSocket**: 5 connections/second with burst of 5

### Proxy Configuration
- **Frontend**: Proxies to `frontend:80` container
- **API**: Proxies `/api/*` to `api:8000` with proper headers
- **WebSocket**: Proxies `/ws/*` with upgrade headers for real-time connections

### Performance Optimization
- **Gzip compression**: Enabled for text-based content with level 6 compression
- **File caching**: Configured for static assets with 1-year expiry
- **Connection pooling**: Keepalive connections to upstream servers
- **Buffer sizes**: Optimized for performance and security

## File Structure

```
nginx/
├── nginx.conf          # Main Nginx configuration
├── Dockerfile          # Docker image for Nginx
├── error-pages/        # Custom error pages
│   ├── 429.html       # Rate limit exceeded
│   └── 50x.html       # Server errors
└── README.md          # This file
```

## Network Architecture

The Nginx container connects to two networks:
- **frontend network**: To reach the frontend service
- **backend network**: To reach the API service

It is the ONLY service with exposed ports (80, 443) to the host system.

## SSL/TLS Configuration

The configuration is prepared for SSL certificates but currently runs on HTTP. To enable HTTPS:

1. Obtain SSL certificates (Let's Encrypt recommended)
2. Mount certificates to `/etc/letsencrypt/`
3. Uncomment the HTTPS server block in `nginx.conf`
4. Update the HTTP server to redirect to HTTPS

## Health Check

A simple health check endpoint is available at `/health` that returns "healthy" with a 200 status code.

## Logs

Logs are written to:
- Access logs: `/var/log/nginx/access.log`
- Error logs: `/var/log/nginx/error.log`

These are mounted as a Docker volume for persistence and rotation.

## Security Considerations

1. **No direct database access**: Nginx cannot reach the database network
2. **Request size limits**: 100MB max body size for file uploads
3. **Timeout protection**: 30-60 second timeouts to prevent slowloris attacks
4. **Hidden files blocked**: Access denied to `.git`, `.env`, etc.
5. **Sensitive files blocked**: `.sql`, `.bak`, `.log` extensions denied

## Deployment

The Nginx service is built and deployed as part of the docker-compose.prod.yml stack:

```bash
docker-compose -f docker-compose.prod.yml up -d nginx
```

For development, you can test the configuration:

```bash
docker build -t pazpaz-nginx ./nginx
docker run --rm -p 80:80 pazpaz-nginx nginx -t
```

## Monitoring

Monitor the following metrics:
- Request rate and response times in access logs
- 429 status codes indicating rate limiting
- 502/503 status codes indicating backend issues
- SSL certificate expiration (when configured)

## Troubleshooting

### Common Issues

1. **502 Bad Gateway**: Backend services not healthy or unreachable
   - Check if API service is running: `docker ps | grep pazpaz-api`
   - Check API health: `docker exec pazpaz-api curl http://localhost:8000/health`

2. **429 Too Many Requests**: Rate limiting triggered
   - Review rate limit zones in nginx.conf
   - Adjust burst values if legitimate traffic is blocked

3. **Connection refused**: Network configuration issue
   - Verify nginx is on both frontend and backend networks
   - Check service dependencies are healthy

### Debug Commands

```bash
# Test configuration syntax
docker exec pazpaz-nginx nginx -t

# View access logs
docker logs pazpaz-nginx

# Check upstream connectivity
docker exec pazpaz-nginx curl -I http://api:8000/health
docker exec pazpaz-nginx curl -I http://frontend:80/health

# Reload configuration without downtime
docker exec pazpaz-nginx nginx -s reload
```