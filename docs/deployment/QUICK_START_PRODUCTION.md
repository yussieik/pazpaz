# Quick Start: Production Deployment

## Prerequisites

- Docker Engine 24.0+ with Docker Compose
- 4GB+ RAM available for containers
- SSL certificates (or use Let's Encrypt)
- Domain name configured with DNS

## Step 1: Environment Configuration

1. Copy the environment template:
```bash
cp .env.prod.example .env.prod
```

2. Generate secure passwords:
```bash
# PostgreSQL password
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)" >> .env.prod

# Redis password
echo "REDIS_PASSWORD=$(openssl rand -base64 32)" >> .env.prod

# MinIO credentials
echo "S3_ACCESS_KEY=$(openssl rand -base64 16 | tr -d '/+=' | cut -c1-16)" >> .env.prod
echo "S3_SECRET_KEY=$(openssl rand -base64 32 | tr -d '/+=')" >> .env.prod

# Application secrets
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env.prod
echo "ENCRYPTION_MASTER_KEY=$(python3 -c 'import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())')" >> .env.prod
echo "MINIO_ENCRYPTION_KEY=$(python3 -c 'import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())')" >> .env.prod
```

3. Edit `.env.prod` and configure:
   - `FRONTEND_URL`: Your production URL (e.g., https://app.pazpaz.com)
   - `SMTP_*`: Email service credentials
   - `ALLOWED_HOSTS`: Your domain names

## Step 2: SSL Certificates

### Option A: Let's Encrypt (Recommended)

1. Install certbot:
```bash
sudo apt-get install certbot  # Ubuntu/Debian
# or
sudo yum install certbot      # RHEL/CentOS
```

2. Generate certificates:
```bash
sudo certbot certonly --standalone -d app.pazpaz.com -d www.pazpaz.com
```

3. Create certificate directory:
```bash
mkdir -p certs/ssl
sudo cp /etc/letsencrypt/live/app.pazpaz.com/fullchain.pem certs/ssl/
sudo cp /etc/letsencrypt/live/app.pazpaz.com/privkey.pem certs/ssl/
sudo chown -R $USER:$USER certs/
```

### Option B: Custom Certificates

Place your certificates in:
- `certs/ssl/fullchain.pem` (certificate chain)
- `certs/ssl/privkey.pem` (private key)

## Step 3: Build Images

```bash
# Build API image
docker compose -f docker-compose.prod.yml build api

# Build frontend (if using separate build)
docker compose -f docker-compose.prod.yml build frontend-builder
```

## Step 4: Database Initialization

1. Start only the database:
```bash
docker compose -f docker-compose.prod.yml up -d db
```

2. Wait for it to be healthy:
```bash
docker compose -f docker-compose.prod.yml exec db pg_isready
```

3. Run migrations:
```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

## Step 5: Start All Services

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

## Step 6: Verify Deployment

1. Check health endpoints:
```bash
# Nginx health
curl http://localhost/health

# API health (through nginx)
curl http://localhost/api/health
```

2. Verify network isolation:
```bash
./verify-network-isolation.sh
```

3. Check that databases are NOT accessible:
```bash
# These should all fail (timeout or connection refused)
telnet localhost 5432  # PostgreSQL
telnet localhost 6379  # Redis
telnet localhost 9000  # MinIO
```

## Step 7: Configure Nginx SSL (if not done)

Update `frontend/nginx.prod.conf` to include SSL configuration:

```nginx
server {
    listen 80;
    server_name app.pazpaz.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.pazpaz.com;

    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # ... rest of configuration
}
```

## Monitoring

### View Logs
```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f api
```

### Check Resource Usage
```bash
docker stats
```

### Database Backup
```bash
# Manual backup
docker compose -f docker-compose.prod.yml exec db pg_dump -U pazpaz pazpaz | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Automated backup (add to crontab)
0 2 * * * cd /path/to/pazpaz && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U pazpaz pazpaz | gzip > /backups/pazpaz-$(date +\%Y\%m\%d).sql.gz
```

## Maintenance

### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild images
docker compose -f docker-compose.prod.yml build

# Restart services (rolling update)
docker compose -f docker-compose.prod.yml up -d
```

### Scale Services
```bash
# Scale API to 3 instances (requires load balancer configuration)
docker compose -f docker-compose.prod.yml up -d --scale api=3
```

### Emergency Shutdown
```bash
# Stop all services immediately
docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (DESTRUCTIVE)
docker compose -f docker-compose.prod.yml down -v
```

## Troubleshooting

### Service Won't Start
```bash
# Check logs
docker compose -f docker-compose.prod.yml logs [service_name]

# Check configuration
docker compose -f docker-compose.prod.yml config

# Restart individual service
docker compose -f docker-compose.prod.yml restart [service_name]
```

### Database Connection Issues
```bash
# Test from API container
docker compose -f docker-compose.prod.yml exec api python -c "
from pazpaz.database import engine
import asyncio
asyncio.run(engine.connect())
"
```

### Network Issues
```bash
# Inspect networks
docker network ls
docker network inspect pazpaz_backend
docker network inspect pazpaz_database

# Test connectivity
docker compose -f docker-compose.prod.yml exec api ping db
docker compose -f docker-compose.prod.yml exec nginx ping api
```

## Security Checklist

Before going live:

- [ ] Changed all default passwords in `.env.prod`
- [ ] SSL certificates configured and tested
- [ ] Network isolation verified
- [ ] No database ports exposed to host
- [ ] Firewall rules configured on host
- [ ] Backup strategy implemented
- [ ] Monitoring and alerting configured
- [ ] Rate limiting tested
- [ ] Security headers verified
- [ ] CORS properly configured

## Support

For issues or questions:
1. Check logs: `docker compose -f docker-compose.prod.yml logs`
2. Review network architecture: `docs/deployment/NETWORK_ARCHITECTURE.md`
3. Consult security documentation: `docs/security/`