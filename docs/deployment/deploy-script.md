# Production Deployment Script

## Overview

The `scripts/deploy.sh` script implements a comprehensive blue-green deployment strategy for PazPaz production deployments. It ensures zero-downtime deployments with automatic health checks, database backups, and rollback capabilities.

## Features

### Blue-Green Deployment
- Deploys new containers alongside existing ones
- Labels containers with deployment colors (blue/green)
- Performs health checks before switching traffic
- Gracefully drains connections from old containers
- Removes old containers only after successful deployment

### Pre-Deployment Validation
- Environment file validation (all required variables, no placeholders)
- Disk space check (minimum 20GB required)
- Database connectivity verification
- Redis connectivity verification
- Docker daemon health check
- GitHub Container Registry access verification

### Database Protection
- Automatic database backup before deployment
- Compressed backups stored with timestamps
- Keeps last 10 backups automatically
- Restore capability during rollback

### Health Monitoring
- Container health status checks
- API endpoint validation (`/api/v1/health`)
- Frontend accessibility check
- Database query tests
- Redis write tests
- Configurable retry logic (5 retries, 10s timeout)

### Automatic Rollback
- Triggers on deployment failure
- Restores database from backup
- Restarts previous deployment containers
- Verifies rollback success with health checks
- Detailed logging of rollback reason

## Usage

### Basic Deployment

```bash
# Standard deployment with latest tag
./scripts/deploy.sh

# Deploy specific version
./scripts/deploy.sh --tag v1.2.3

# Test deployment without making changes
./scripts/deploy.sh --dry-run
```

### Advanced Options

```bash
# Skip database backup (not recommended)
./scripts/deploy.sh --skip-backup

# Skip health checks (dangerous)
./scripts/deploy.sh --skip-health-checks

# Force deployment despite warnings
./scripts/deploy.sh --force

# Rollback to previous deployment
./scripts/deploy.sh --rollback
```

## Required Environment

### Environment Variables

The following environment variables must be set:

```bash
export GITHUB_REPOSITORY="yourusername/pazpaz"  # GitHub repo path
export IMAGE_TAG="latest"                        # Docker image tag
```

### Environment File

The script requires `.env.production` in the project root with all required variables properly configured. Use `scripts/validate-env.sh` to verify your environment file.

### Docker Registry Access

Ensure you're logged in to GitHub Container Registry:

```bash
docker login ghcr.io -u USERNAME -p GITHUB_TOKEN
```

## Deployment Process

### 1. Pre-Deployment Phase
```
├── Validate environment configuration
├── Check disk space (20GB minimum)
├── Verify service connectivity
├── Test registry access
└── Backup database
```

### 2. Deployment Phase
```
├── Pull latest images from registry
├── Deploy new containers (blue/green)
├── Wait for containers to start
├── Run health checks (with retries)
└── Execute smoke tests
```

### 3. Traffic Switch Phase
```
├── Drain connections (30s timeout)
├── Switch nginx upstream
├── Remove old containers
└── Clean up temporary files
```

### 4. Rollback Phase (if needed)
```
├── Stop failed containers
├── Restore database backup
├── Restart previous containers
├── Verify rollback health
└── Log failure details
```

## Deployment Tracking

Each deployment is tracked with:
- Unique deployment ID: `deploy-YYYYMMDD-HHMMSS-PID`
- Deployment color label: `blue` or `green`
- Timestamp labels on all containers
- Comprehensive logging to `$DEPLOYMENT_DIR/logs/`

## Directory Structure

```
/opt/pazpaz/                    # Production deployment directory
├── backups/                    # Database backups
│   └── pazpaz-backup-*.sql.gz  # Timestamped backups
└── logs/                       # Deployment logs
    └── deployment-*.log        # Timestamped deployment logs

# Or if /opt/pazpaz is not writable:
$PROJECT_ROOT/.deployment/      # Local deployment directory
├── backups/
└── logs/
```

## Health Checks

The script performs comprehensive health checks:

### Container Health
- Checks Docker health status for each container
- Retries up to 5 times with 10s timeout
- Validates all 8 services are healthy

### API Health
```bash
curl -f http://localhost:8000/api/v1/health
```

### Frontend Health
```bash
curl -f http://localhost:80/
```

### Database Health
```bash
docker exec pazpaz-db pg_isready -U pazpaz
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT 1"
```

### Redis Health
```bash
docker exec pazpaz-redis redis-cli -a $REDIS_PASSWORD ping
docker exec pazpaz-redis redis-cli -a $REDIS_PASSWORD SET test_key test_value EX 10
```

## Rollback Procedure

### Automatic Rollback

Triggered automatically when:
- Container startup fails
- Health checks fail
- Traffic switch fails

### Manual Rollback

```bash
# Rollback to previous deployment
./scripts/deploy.sh --rollback

# Force rollback even with warnings
./scripts/deploy.sh --rollback --force
```

### Rollback Process

1. Identifies previous deployment from container labels
2. Stops failed deployment containers
3. Restores database from pre-deployment backup
4. Restarts previous deployment containers
5. Verifies health of restored deployment
6. Logs detailed rollback information

## Exit Codes

- `0` - Deployment successful
- `1` - Pre-deployment checks failed
- `2` - Deployment failed
- `3` - Health checks failed
- `4` - Rollback failed

## Troubleshooting

### Common Issues

#### Permission Denied for /opt/pazpaz
**Problem**: Cannot create deployment directory
**Solution**: Script automatically falls back to `$PROJECT_ROOT/.deployment/`

#### Environment Validation Failed
**Problem**: Missing or invalid environment variables
**Solution**: Run `scripts/validate-env.sh` to identify issues

#### Registry Access Failed
**Problem**: Cannot pull images from GitHub Container Registry
**Solution**:
```bash
# Login to registry
docker login ghcr.io -u USERNAME -p GITHUB_TOKEN

# Verify access
docker pull ghcr.io/$GITHUB_REPOSITORY/backend:$IMAGE_TAG
```

#### Health Checks Timeout
**Problem**: Services not becoming healthy
**Solution**:
- Check container logs: `docker logs pazpaz-api`
- Verify database migrations: `docker exec pazpaz-api alembic current`
- Check network connectivity between containers

### Debug Mode

Enable verbose logging:
```bash
# View deployment logs in real-time
tail -f $DEPLOYMENT_DIR/logs/deployment-*.log

# Check container logs
docker-compose -f docker-compose.prod.yml logs -f

# Inspect container health
docker inspect pazpaz-api | jq '.[0].State.Health'
```

## Best Practices

### Before Deployment

1. **Test in staging environment first**
2. **Verify database backups are working**
3. **Check monitoring dashboards**
4. **Notify team of deployment window**
5. **Review recent commits and changes**

### During Deployment

1. **Monitor logs in real-time**
2. **Watch error rates and latency**
3. **Be ready to rollback quickly**
4. **Keep deployment window short**

### After Deployment

1. **Monitor for 30 minutes**
2. **Check critical user journeys**
3. **Verify background jobs are running**
4. **Review deployment logs for warnings**
5. **Update deployment documentation**

## Security Considerations

- Database passwords never logged
- Secrets loaded from environment files only
- SSL/TLS required for all production traffic
- Automatic cleanup of old backups
- Deployment logs excluded from version control

## Integration with CI/CD

The deployment script can be triggered from GitHub Actions:

```yaml
- name: Deploy to Production
  env:
    GITHUB_REPOSITORY: ${{ github.repository }}
    IMAGE_TAG: ${{ github.sha }}
  run: |
    ssh deploy@production-server "cd /opt/pazpaz && ./scripts/deploy.sh --tag $IMAGE_TAG"
```

## Maintenance

### Backup Retention

- Keeps last 10 database backups automatically
- Manual cleanup: `ls -t $BACKUP_DIR/*.sql.gz | tail -n +11 | xargs rm -f`

### Log Rotation

- Deployment logs are timestamped
- Manual cleanup: `find $LOG_DIR -name "*.log" -mtime +30 -delete`

### Container Cleanup

- Old containers removed automatically after successful deployment
- Manual cleanup: `docker container prune -f`

## Related Documentation

- [Environment Setup](./environment-setup.md)
- [Docker Compose Configuration](./docker-compose-config.md)
- [Health Check Implementation](./health-checks.md)
- [Disaster Recovery](./disaster-recovery.md)
- [Monitoring Setup](./monitoring.md)