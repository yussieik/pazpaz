# Logging Configuration

## Overview

PazPaz implements centralized JSON-structured logging for all services with automatic rotation, compression, and HIPAA-compliant retention policies. This document describes the logging architecture, configuration, and operational procedures.

## Architecture

### Log Flow

```
Services → Docker JSON Driver → /opt/pazpaz/logs/ → Log Rotation → Archive/Forward
     ↓                                   ↓                              ↓
  stdout/stderr                    JSON Files                    Loki/ELK (Optional)
```

### Directory Structure

```
/opt/pazpaz/logs/
├── nginx/         # Reverse proxy access and error logs
├── api/           # FastAPI application logs
├── worker/        # ARQ background worker logs
├── db/            # PostgreSQL query and error logs
├── redis/         # Redis operation logs
├── minio/         # Object storage access logs
├── clamav/        # Antivirus scan logs
├── frontend/      # Vue.js application logs
├── audit/         # HIPAA audit trail (90-day retention)
├── aggregated/    # Combined logs for analysis
└── forwarding/    # Log forwarding configurations
```

## Configuration

### Docker Logging Driver

All containers use the JSON-file driver with the following configuration:

```yaml
# docker-compose.prod.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"      # Maximum size per log file
    max-file: "7"        # Number of rotated files to keep
    labels: "service,environment,version"
    compress: "true"     # Compress rotated logs
```

### Docker Daemon Configuration

System-wide Docker logging configured in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "7",
    "labels": "service,environment,version",
    "env": "ENVIRONMENT,SERVICE_NAME",
    "compress": "true"
  },
  "log-level": "info",
  "debug": false
}
```

### Logrotate Configuration

Additional log rotation via `/etc/logrotate.d/pazpaz`:

```
# Application logs
/opt/pazpaz/logs/*/*.log {
    daily
    rotate 30
    maxsize 10m
    missingok
    notifempty
    compress
    delaycompress
    create 0644 root root
}

# Audit logs (HIPAA - longer retention)
/opt/pazpaz/logs/audit/*.log {
    daily
    rotate 90
    maxsize 50M
    missingok
    notifempty
    compress
    delaycompress
    create 0640 root root
}
```

## Setup Instructions

### Initial Setup

1. **Run the setup script:**
   ```bash
   sudo ./scripts/setup-logging.sh --apply
   ```

2. **Verify configuration:**
   ```bash
   ./scripts/setup-logging.sh --validate-only
   ```

3. **Test logging:**
   ```bash
   docker exec pazpaz-api logger "Test log message"
   ./scripts/aggregate-logs.sh --last 10
   ```

### Manual Setup (Alternative)

1. **Create log directories:**
   ```bash
   sudo mkdir -p /opt/pazpaz/logs/{nginx,api,worker,db,redis,minio,clamav,frontend,audit,aggregated}
   sudo chmod 755 /opt/pazpaz/logs
   ```

2. **Configure Docker daemon:**
   ```bash
   sudo nano /etc/docker/daemon.json
   # Add configuration from above
   sudo systemctl reload docker
   ```

3. **Setup logrotate:**
   ```bash
   sudo nano /etc/logrotate.d/pazpaz
   # Add configuration from above
   sudo logrotate -d /etc/logrotate.d/pazpaz
   ```

## Log Management

### Viewing Logs

**Real-time logs:**
```bash
# All services
./scripts/aggregate-logs.sh --follow

# Specific service
./scripts/aggregate-logs.sh --service api --follow

# With filtering
./scripts/aggregate-logs.sh --service api --level ERROR --follow
```

**Historical logs:**
```bash
# Last hour
./scripts/aggregate-logs.sh --since 1h

# Last 100 lines
./scripts/aggregate-logs.sh --last 100

# Search for pattern
./scripts/aggregate-logs.sh --grep "authentication failed"
```

**Docker logs directly:**
```bash
# API service logs
docker logs pazpaz-api --tail 100 --follow

# With timestamps
docker logs pazpaz-api --timestamps --since 2h
```

### Log Analysis

**Show statistics:**
```bash
./scripts/aggregate-logs.sh --stats
```

**Export logs:**
```bash
# Export last 24 hours
./scripts/aggregate-logs.sh --since 24h --export /tmp/pazpaz-logs.tar.gz

# Export specific service
./scripts/aggregate-logs.sh --service api --since 7d --export /tmp/api-logs.tar.gz
```

**Parse JSON logs:**
```bash
# Using jq
docker logs pazpaz-api --tail 100 | jq '.level, .message'

# Extract errors
docker logs pazpaz-api | jq 'select(.level == "ERROR")'
```

## Log Formats

### Application Logs (FastAPI)

```json
{
  "timestamp": "2024-10-24T12:34:56.789Z",
  "level": "INFO",
  "service": "api",
  "environment": "production",
  "message": "Request processed successfully",
  "request_id": "abc123",
  "user_id": "user456",
  "workspace_id": "ws789",
  "method": "GET",
  "path": "/api/v1/clients",
  "status_code": 200,
  "response_time_ms": 45
}
```

### Audit Logs (HIPAA)

```json
{
  "timestamp": "2024-10-24T12:34:56.789Z",
  "event_type": "DATA_ACCESS",
  "user_id": "user456",
  "workspace_id": "ws789",
  "resource_type": "client",
  "resource_id": "client123",
  "action": "READ",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "success": true,
  "metadata": {
    "fields_accessed": ["name", "email", "phone"]
  }
}
```

### Error Logs

```json
{
  "timestamp": "2024-10-24T12:34:56.789Z",
  "level": "ERROR",
  "service": "api",
  "error_type": "ValidationError",
  "message": "Invalid request data",
  "traceback": "...",
  "request_id": "abc123",
  "context": {
    "endpoint": "/api/v1/appointments",
    "method": "POST",
    "user_id": "user456"
  }
}
```

## Log Forwarding

### Loki/Promtail Setup

1. **Install Promtail:**
   ```bash
   wget https://github.com/grafana/loki/releases/latest/download/promtail-linux-amd64.zip
   unzip promtail-linux-amd64.zip
   sudo mv promtail-linux-amd64 /usr/local/bin/promtail
   ```

2. **Configure Promtail:**
   ```bash
   sudo cp /opt/pazpaz/logs/forwarding/promtail-config.yaml /etc/promtail/config.yaml
   sudo systemctl restart promtail
   ```

### ELK Stack Setup

1. **Install Logstash:**
   ```bash
   # Follow Elastic documentation for your OS
   ```

2. **Configure pipeline:**
   ```bash
   sudo cp /opt/pazpaz/logs/forwarding/logstash.conf /etc/logstash/conf.d/pazpaz.conf
   sudo systemctl restart logstash
   ```

## Monitoring & Alerting

### Log-based Alerts

Configure alerts for critical patterns:

```bash
# High error rate
tail -f /opt/pazpaz/logs/api/*.log | \
  grep ERROR | \
  awk 'BEGIN{c=0} {c++; if(c>10) {print "ALERT: High error rate"; exit}}'

# Authentication failures
tail -f /opt/pazpaz/logs/audit/*.log | \
  grep "authentication_failed" | \
  awk 'BEGIN{c=0} {c++; if(c>5) {print "ALERT: Multiple auth failures"; exit}}'
```

### Disk Usage Monitoring

```bash
# Check log disk usage
du -sh /opt/pazpaz/logs/*

# Alert on high usage
df -h /opt/pazpaz/logs | awk 'NR==2 {if($5+0 > 80) print "WARNING: Log disk usage above 80%"}'
```

## Troubleshooting

### Common Issues

**1. Logs not appearing:**
```bash
# Check container is running
docker ps | grep pazpaz

# Check Docker logging driver
docker inspect pazpaz-api | jq '.[0].HostConfig.LogConfig'

# Check permissions
ls -la /opt/pazpaz/logs/
```

**2. Disk space issues:**
```bash
# Manual rotation
logrotate -f /etc/logrotate.d/pazpaz

# Clean old logs
find /opt/pazpaz/logs -name "*.log.gz" -mtime +30 -delete
```

**3. Performance impact:**
```bash
# Reduce logging verbosity
docker exec pazpaz-api sh -c 'export LOG_LEVEL=WARNING'

# Disable debug logs
sed -i 's/DEBUG=true/DEBUG=false/' .env.production
```

### Log Recovery

**Recover from compressed logs:**
```bash
# Decompress specific log
gunzip /opt/pazpaz/logs/api/app.log.1.gz

# Search in compressed logs
zgrep "ERROR" /opt/pazpaz/logs/api/*.gz
```

**Restore from backup:**
```bash
# If logs were backed up
tar -xzf /backups/logs-20241024.tar.gz -C /opt/pazpaz/logs/
```

## Security Considerations

### HIPAA Compliance

1. **PHI Protection:**
   - Never log patient identifying information
   - Sanitize logs before export
   - Use field-level encryption for sensitive data

2. **Access Control:**
   ```bash
   # Restrict audit log access
   chmod 750 /opt/pazpaz/logs/audit
   chown root:auditors /opt/pazpaz/logs/audit
   ```

3. **Log Integrity:**
   ```bash
   # Generate checksums
   find /opt/pazpaz/logs -name "*.log" -exec sha256sum {} \; > /opt/pazpaz/logs/checksums.txt
   ```

### Log Sanitization

```bash
# Remove sensitive data before sharing
sed -E 's/[0-9]{3}-[0-9]{2}-[0-9]{4}/XXX-XX-XXXX/g' input.log > sanitized.log
sed -E 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}/email@redacted.com/g' input.log > sanitized.log
```

## Retention Policies

| Log Type | Retention | Rotation | Compression |
|----------|-----------|----------|-------------|
| Application | 30 days | Daily | After 1 day |
| Audit (HIPAA) | 90 days | Daily | After 1 day |
| Access logs | 30 days | Daily | After 1 day |
| Error logs | 60 days | Daily | Immediate |
| Debug logs | 7 days | Daily | Immediate |
| Docker logs | 7 files | 10MB size | Immediate |

## Performance Optimization

### Reduce Log Volume

1. **Adjust log levels:**
   ```python
   # backend/src/pazpaz/core/config.py
   LOG_LEVEL = "WARNING" if ENVIRONMENT == "production" else "INFO"
   ```

2. **Filter unnecessary logs:**
   ```python
   # Ignore health check logs
   if request.url.path != "/health":
       logger.info(f"Request: {request.method} {request.url.path}")
   ```

3. **Batch log writes:**
   ```python
   # Use buffered logging
   handler = logging.handlers.BufferingHandler(capacity=1000)
   ```

### Optimize Storage

```bash
# Use log rotation
logrotate -f /etc/logrotate.d/pazpaz

# Archive old logs
tar -czf logs-$(date +%Y%m).tar.gz /opt/pazpaz/logs/*.log.gz
aws s3 cp logs-$(date +%Y%m).tar.gz s3://pazpaz-backups/logs/
```

## Related Documentation

- [Uptime Monitoring](./uptime-monitoring.md)
- [Error Tracking](./error-tracking.md)
- [Performance Monitoring](./performance-monitoring.md)
- [Infrastructure Security](./INFRASTRUCTURE_SECURITY_CHECKLIST.md)

---

**Last Updated:** 2024-10-24
**Version:** 1.0.0
**Status:** Production Ready