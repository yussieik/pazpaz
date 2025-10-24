# Uptime Monitoring Configuration

## Overview

PazPaz uses UptimeRobot for external uptime monitoring, providing 24/7 availability checks, instant alerts, and detailed uptime statistics. This document covers the setup, configuration, and management of uptime monitoring for production services.

## Architecture

```
Internet → UptimeRobot Monitors → PazPaz Endpoints → Alert Channels
              ↓                         ↓                    ↓
         Health Checks            Response Metrics      Email/SMS/Slack
```

## UptimeRobot Account Setup

### 1. Create Free Account

1. Visit [UptimeRobot.com](https://uptimerobot.com)
2. Click "Register for FREE"
3. Use a team email address (e.g., ops@pazpaz.com)
4. Verify email and complete setup
5. Enable 2FA for security

### 2. Free Tier Limitations

- **50 monitors** maximum
- **5-minute intervals** for checks
- **2 status pages**
- **Email alerts** included
- **SMS/Voice** requires Pro ($7/month)
- **API access** included

## Monitor Configuration

### Critical Monitors (Priority 1)

#### 1. API Health Check

```yaml
Name: PazPaz API Health
URL: https://api.pazpaz.com/api/v1/health
Type: HTTPS
Interval: 1 minute (Pro) or 5 minutes (Free)
Timeout: 30 seconds
HTTP Method: GET
Expected Status: 200
Keywords to check: "healthy"
Alert Threshold: 2 consecutive failures
```

**Advanced Settings:**
```yaml
HTTP Headers:
  Accept: application/json
  X-Health-Check: uptimerobot

Response Time Threshold:
  Warning: >1000ms
  Critical: >3000ms

SSL Certificate Check: Enabled
SSL Expiry Alert: 30 days before
```

#### 2. Main Application

```yaml
Name: PazPaz Web Application
URL: https://pazpaz.com
Type: HTTPS
Interval: 5 minutes
Timeout: 30 seconds
HTTP Method: GET
Expected Status: 200
Keywords to check: "PazPaz"
Alert Threshold: 2 consecutive failures
```

#### 3. Authentication Endpoint

```yaml
Name: PazPaz Auth Service
URL: https://api.pazpaz.com/api/v1/auth/status
Type: HTTPS
Interval: 5 minutes
Timeout: 30 seconds
HTTP Method: GET
Expected Status: 200
Alert Threshold: 2 consecutive failures
```

### Additional Monitors (Priority 2)

#### 4. Database Connectivity

```yaml
Name: PazPaz Database Health
URL: https://api.pazpaz.com/api/v1/health/db
Type: HTTPS
Interval: 15 minutes
Timeout: 30 seconds
Expected Status: 200
Keywords: "database_connected"
```

#### 5. Redis Cache

```yaml
Name: PazPaz Cache Health
URL: https://api.pazpaz.com/api/v1/health/cache
Type: HTTPS
Interval: 15 minutes
Timeout: 30 seconds
Expected Status: 200
Keywords: "redis_connected"
```

#### 6. Storage Service

```yaml
Name: PazPaz Storage Health
URL: https://api.pazpaz.com/api/v1/health/storage
Type: HTTPS
Interval: 30 minutes
Timeout: 30 seconds
Expected Status: 200
Keywords: "storage_available"
```

## Alert Configuration

### Alert Contacts

#### Primary On-Call

```yaml
Name: Primary DevOps
Email: devops@pazpaz.com
SMS: +1-555-0100 (Pro only)
Notification Settings:
  - Send when down
  - Send when up
  - Send SSL expiry warnings
  - Send performance warnings
```

#### Secondary On-Call

```yaml
Name: Engineering Team
Email: engineering@pazpaz.com
Slack: #alerts-production
Notification Settings:
  - Send when down for 10+ minutes
  - Send when up
```

#### Management Escalation

```yaml
Name: Management
Email: cto@pazpaz.com
Notification Settings:
  - Send when down for 30+ minutes
  - Weekly reports
```

### Alert Rules

```yaml
Default Alert Rules:
  First Alert: Immediately (0 minutes)
  Escalation 1: After 5 minutes
  Escalation 2: After 15 minutes
  Escalation 3: After 30 minutes

Weekend/Night Rules:
  First Alert: After 5 minutes
  Escalation: After 15 minutes
  Final: After 1 hour
```

### Slack Integration

1. **Add Slack App:**
   ```
   My Settings → Alert Contacts → Add Alert Contact
   Type: Slack
   Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```

2. **Message Format:**
   ```
   🚨 *Monitor Alert*
   Monitor: {{monitorName}}
   Status: {{alertType}}
   URL: {{monitorURL}}
   Duration: {{alertDuration}}
   Details: {{alertDetails}}
   ```

### Email Templates

**Down Alert:**
```
Subject: 🔴 [CRITICAL] {{monitorName}} is DOWN

Body:
Alert Type: {{alertType}}
Monitor: {{monitorName}}
URL: {{monitorURL}}
Started: {{alertDateTime}}
Duration: {{alertDuration}}

Error Details:
{{alertDetails}}

Please check immediately:
1. Service logs: ./scripts/aggregate-logs.sh --service api --level ERROR
2. Health endpoint: curl https://api.pazpaz.com/api/v1/health
3. Server status: ssh pazpaz-prod

Status Page: https://status.pazpaz.com
```

**Recovery Alert:**
```
Subject: ✅ [RESOLVED] {{monitorName}} is UP

Body:
Monitor: {{monitorName}}
URL: {{monitorURL}}
Downtime Duration: {{alertDuration}}
Recovered: {{alertDateTime}}

The service has recovered and is operating normally.
```

## Status Page Setup

### Public Status Page

1. **Create Status Page:**
   ```
   Status Pages → Add New Status Page
   Domain: status.pazpaz.com
   Title: PazPaz System Status
   ```

2. **Configure Monitors:**
   ```yaml
   Displayed Monitors:
     - API Health (Show response time)
     - Web Application (Show uptime %)
     - Authentication Service (Show status only)

   Hidden Monitors:
     - Database Health (Internal only)
     - Cache Health (Internal only)
   ```

3. **Custom Domain Setup:**
   ```
   CNAME: status.pazpaz.com → stats.uptimerobot.com
   Custom Logo: /assets/pazpaz-logo.png
   Custom CSS: See template below
   ```

### Status Page CSS

```css
/* PazPaz Status Page Custom Theme */
.page-header {
  background: #4A90E2;
  color: white;
}

.monitor-status-ok {
  color: #27AE60;
}

.monitor-status-down {
  color: #E74C3C;
}

.response-time-chart {
  height: 200px;
}

.uptime-percentage {
  font-size: 2em;
  font-weight: bold;
}
```

## API Integration

### Get Monitor Status

```bash
#!/bin/bash
# Get all monitors status via API

API_KEY="your-uptimerobot-api-key"

curl -X POST https://api.uptimerobot.com/v2/getMonitors \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "'$API_KEY'",
    "format": "json",
    "logs": 1,
    "response_times": 1,
    "response_times_average": 30
  }' | jq '.monitors[] | {name: .friendly_name, status: .status, uptime: .all_time_uptime_ratio}'
```

### Create Monitor via API

```bash
#!/bin/bash
# Create a new monitor

API_KEY="your-uptimerobot-api-key"

curl -X POST https://api.uptimerobot.com/v2/newMonitor \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "'$API_KEY'",
    "friendly_name": "PazPaz New Endpoint",
    "url": "https://api.pazpaz.com/api/v1/new-endpoint",
    "type": 1,
    "interval": 300,
    "http_method": 1,
    "alert_contacts": "0544561_0_0"
  }'
```

## Health Endpoint Implementation

### FastAPI Health Endpoints

```python
# backend/src/pazpaz/api/health.py
from fastapi import APIRouter, status
from datetime import datetime
import asyncio
from sqlalchemy import select

router = APIRouter(tags=["Health"])

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic health check for uptime monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "pazpaz-api",
        "version": "1.0.0"
    }

@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive readiness check"""
    checks = {
        "database": False,
        "redis": False,
        "storage": False
    }

    # Check database
    try:
        await db.execute(select(1))
        checks["database"] = True
    except Exception:
        pass

    # Check Redis
    try:
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        pass

    # Check MinIO/S3
    try:
        await s3_client.head_bucket(Bucket=S3_BUCKET)
        checks["storage"] = True
    except Exception:
        pass

    all_healthy = all(checks.values())

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/db")
async def database_health(db: AsyncSession = Depends(get_db)):
    """Database-specific health check"""
    try:
        result = await db.execute(select(1))
        return {"status": "healthy", "database_connected": True}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "error": str(e)}
        )
```

## Test Script

Create `scripts/test-health-endpoints.sh`:

```bash
#!/bin/bash

# Test health endpoints locally
echo "Testing health endpoints..."

# Basic health
curl -f https://api.pazpaz.com/api/v1/health || echo "Basic health FAILED"

# Readiness
curl -f https://api.pazpaz.com/api/v1/health/ready || echo "Readiness FAILED"

# Database
curl -f https://api.pazpaz.com/api/v1/health/db || echo "Database health FAILED"

# Response time test
time curl -f https://api.pazpaz.com/api/v1/health
```

## Monitoring Dashboard

### Metrics to Track

1. **Availability Metrics:**
   - Overall uptime percentage
   - Downtime incidents count
   - Mean time between failures (MTBF)
   - Mean time to recovery (MTTR)

2. **Performance Metrics:**
   - Average response time
   - 95th percentile response time
   - Response time trends
   - Slowest endpoints

3. **Alert Metrics:**
   - Alert response time
   - False positive rate
   - Escalation frequency

### Monthly Report Template

```markdown
# PazPaz Uptime Report - [Month Year]

## Executive Summary
- Overall Uptime: XX.XX%
- Total Incidents: X
- Average Response Time: XXXms
- SLA Compliance: ✅/❌

## Detailed Metrics

### Availability
| Service | Uptime % | Downtime | Incidents |
|---------|----------|----------|-----------|
| API | 99.95% | 21m | 2 |
| Web App | 99.99% | 4m | 1 |
| Auth | 100% | 0m | 0 |

### Performance
| Endpoint | Avg Response | P95 Response | Degradations |
|----------|--------------|--------------|--------------|
| /health | 45ms | 120ms | 0 |
| /api/v1/* | 85ms | 180ms | 1 |

### Incidents
1. **[Date]** - API timeout (5 minutes)
   - Root Cause: Database connection pool exhaustion
   - Resolution: Increased pool size
   - Prevention: Added connection monitoring

## Action Items
- [ ] Implement redundant health checks
- [ ] Add geographic distribution monitoring
- [ ] Upgrade to Pro for 1-minute checks
```

## Troubleshooting

### Common Issues

**1. False Positives:**
```bash
# Check if service is actually down
curl -I https://api.pazpaz.com/api/v1/health

# Check from different locations
curl -I https://api.pazpaz.com/api/v1/health --resolve api.pazpaz.com:443:YOUR_IP

# Verify DNS resolution
nslookup api.pazpaz.com
```

**2. Monitor Not Triggering:**
```yaml
Checklist:
- Verify URL is publicly accessible
- Check firewall rules allow UptimeRobot IPs
- Confirm SSL certificate is valid
- Test with curl from external server
```

**3. Slow Response Times:**
```bash
# Diagnose slow responses
curl -w "@curl-format.txt" -o /dev/null -s https://api.pazpaz.com/api/v1/health

# curl-format.txt:
time_namelookup:  %{time_namelookup}s\n
time_connect:  %{time_connect}s\n
time_appconnect:  %{time_appconnect}s\n
time_pretransfer:  %{time_pretransfer}s\n
time_redirect:  %{time_redirect}s\n
time_starttransfer:  %{time_starttransfer}s\n
time_total:  %{time_total}s\n
```

## UptimeRobot IP Whitelist

Add these IPs to your firewall whitelist:

```
# UptimeRobot monitoring IPs (subject to change - check docs)
69.162.124.224/28
63.143.42.240/28
46.137.190.132/31
122.248.234.23/32
167.99.209.234/32
178.62.52.237/32
54.79.28.129/32
54.94.142.218/32
104.131.107.63/32
54.67.10.127/32
54.64.67.106/32
159.203.30.41/32
46.101.250.135/32
188.226.183.141/32
178.62.98.38/32
139.59.173.249/32
165.227.83.148/32
128.199.195.156/32
138.197.150.151/32
34.233.66.117/32
```

## Integration with CI/CD

### Deployment Notification

```yaml
# .github/workflows/deploy-production.yml
- name: Notify UptimeRobot of Deployment
  run: |
    curl -X POST https://api.uptimerobot.com/v2/editMonitor \
      -d "api_key=${{ secrets.UPTIMEROBOT_API_KEY }}" \
      -d "id=YOUR_MONITOR_ID" \
      -d "notes=Deployment: ${{ github.sha }}"
```

### Pause During Maintenance

```bash
#!/bin/bash
# Pause monitors during maintenance

API_KEY="your-api-key"
MONITOR_IDS="123456 789012 345678"

for id in $MONITOR_IDS; do
  curl -X POST https://api.uptimerobot.com/v2/editMonitor \
    -d "api_key=$API_KEY" \
    -d "id=$id" \
    -d "status=0"  # 0 = paused
done

# Run maintenance...

# Resume monitors
for id in $MONITOR_IDS; do
  curl -X POST https://api.uptimerobot.com/v2/editMonitor \
    -d "api_key=$API_KEY" \
    -d "id=$id" \
    -d "status=1"  # 1 = active
done
```

## Best Practices

1. **Monitor Setup:**
   - Use keyword checking for validation
   - Set appropriate timeout values (30s standard)
   - Configure SSL certificate monitoring
   - Use geographic distribution (Pro feature)

2. **Alert Configuration:**
   - Test alert channels regularly
   - Use escalation for critical services
   - Separate weekday/weekend rules
   - Document on-call procedures

3. **Maintenance:**
   - Pause monitors during planned maintenance
   - Update status page proactively
   - Review and tune alert thresholds monthly
   - Archive incident reports

## Related Documentation

- [Logging Configuration](./logging-configuration.md)
- [Error Tracking](./error-tracking.md)
- [Performance Monitoring](./performance-monitoring.md)
- [Infrastructure Security](./INFRASTRUCTURE_SECURITY_CHECKLIST.md)

---

**Last Updated:** 2024-10-24
**Version:** 1.0.0
**Status:** Ready for Implementation