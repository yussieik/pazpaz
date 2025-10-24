# SSL Certificate Management Guide

## Overview

SSL/TLS encryption is **critical for HIPAA compliance** and protecting patient health information (PHI) during transmission. This guide covers the complete lifecycle of SSL certificates for PazPaz production deployments.

### Why SSL/TLS is Required

1. **HIPAA Compliance**: HIPAA Technical Safeguards (§164.312(e)) require encryption of PHI in transit
2. **Data Protection**: Prevents interception of sensitive therapy session notes and client data
3. **Authentication**: Verifies server identity to prevent man-in-the-middle attacks
4. **Trust**: Modern browsers require HTTPS for many features (WebSockets, geolocation, etc.)

### Certificate Lifecycle

- **Provider**: Let's Encrypt (free, automated, trusted by all browsers)
- **Validity Period**: 90 days (enforces automation and regular key rotation)
- **Renewal Window**: Certificates are renewed when < 30 days remain
- **Automatic Renewal**: Daily cron job checks and renews certificates

## Initial Setup

### Prerequisites

1. **Domain Name**: Valid domain pointing to your server
   - DNS A record: `pazpaz.com → your.server.ip`
   - DNS A record: `www.pazpaz.com → your.server.ip` (optional)

2. **Server Access**: Root or sudo access on Ubuntu/Debian server

3. **Port Access**:
   - Port 80 open for certificate validation
   - Port 443 open for HTTPS traffic

4. **Docker Running**: Ensure docker-compose stack is running
   ```bash
   cd /path/to/pazpaz
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Step-by-Step Setup

1. **Run the SSL Setup Script**
   ```bash
   sudo ./scripts/setup-ssl.sh
   ```

2. **Follow Interactive Prompts**
   - Enter your domain name (e.g., `pazpaz.com`)
   - Choose whether to include www subdomain
   - Provide email for renewal notifications
   - Script will automatically:
     - Install certbot if needed
     - Request certificate from Let's Encrypt
     - Configure automatic renewal
     - Generate DH parameters
     - Test the configuration

3. **Enable SSL in Nginx**
   ```bash
   ./nginx/enable-ssl.sh
   ```

4. **Reload Nginx**
   ```bash
   # If using Docker
   docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

   # If using system nginx
   sudo systemctl reload nginx
   ```

5. **Verify HTTPS Access**
   ```bash
   # Test HTTPS connection
   curl -I https://your-domain.com

   # Check certificate details
   echo | openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates
   ```

### Troubleshooting Initial Setup

#### Problem: "Challenge failed for domain"

**Cause**: Let's Encrypt cannot reach your server on port 80

**Solutions**:
1. Check firewall rules: `sudo ufw status`
2. Ensure port 80 is open: `sudo ufw allow 80/tcp`
3. Verify nginx is running: `docker ps | grep nginx`
4. Check DNS propagation: `nslookup your-domain.com`

#### Problem: "Too many certificates already issued"

**Cause**: Let's Encrypt rate limit (5 certificates per week per domain)

**Solutions**:
1. Wait until rate limit resets (1 week)
2. Use staging environment for testing:
   ```bash
   certbot certonly --staging --webroot -w /var/www/acme-challenge -d your-domain.com
   ```

#### Problem: "Connection refused on port 443"

**Cause**: Nginx not configured for SSL or not running

**Solutions**:
1. Check nginx config: `nginx -t`
2. Ensure SSL config is active: `cat nginx/nginx.conf | grep 443`
3. Restart nginx container: `docker-compose -f docker-compose.prod.yml restart nginx`

## Automatic Renewal

### How It Works

1. **Cron Job**: Runs daily at 3 AM server time
   ```bash
   0 3 * * * certbot renew --quiet
   ```

2. **Renewal Check**: Certbot checks all certificates
   - Skips if >30 days remaining
   - Renews if ≤30 days remaining

3. **Post-Renewal Hook**: Automatically reloads nginx after successful renewal
   ```bash
   /etc/letsencrypt/renewal-hooks/post/reload-nginx.sh
   ```

### Verify Automatic Renewal

1. **Check Cron Job**
   ```bash
   sudo crontab -l | grep certbot
   ```

2. **Test Renewal (Dry Run)**
   ```bash
   sudo certbot renew --dry-run
   ```

3. **Check Renewal Logs**
   ```bash
   sudo cat /var/log/letsencrypt/letsencrypt.log
   ```

4. **Monitor Certificate Expiry**
   ```bash
   # Check all certificates
   sudo certbot certificates

   # Check specific certificate
   echo | openssl s_client -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -enddate
   ```

## Manual Renewal

### When to Manually Renew

- Automatic renewal failed
- Certificate expires in < 7 days
- After configuration changes
- Testing renewal process

### Manual Renewal Process

1. **Check Current Status**
   ```bash
   sudo certbot certificates
   ```

2. **Force Renewal**
   ```bash
   # Renew all certificates
   sudo certbot renew

   # Force renewal even if not due
   sudo certbot renew --force-renewal

   # Renew specific certificate
   sudo certbot renew --cert-name your-domain.com
   ```

3. **Reload Nginx**
   ```bash
   # Docker
   docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

   # System
   sudo systemctl reload nginx
   ```

4. **Verify New Certificate**
   ```bash
   echo | openssl s_client -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -dates
   ```

### Test Without Renewing

```bash
# Dry run - simulates renewal without actually renewing
sudo certbot renew --dry-run

# Check what would be renewed
sudo certbot renew --dry-run --cert-name your-domain.com
```

## Certificate Expiry Monitoring

### Manual Checks

1. **Command Line Check**
   ```bash
   # Simple expiry check
   echo | openssl s_client -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -enddate

   # Detailed certificate info
   echo | openssl s_client -connect your-domain.com:443 2>/dev/null | openssl x509 -noout -text
   ```

2. **Certbot Status**
   ```bash
   sudo certbot certificates
   ```

### Automated Monitoring

#### UptimeRobot Configuration

1. Create HTTPS monitor for `https://your-domain.com`
2. Enable SSL certificate monitoring
3. Set alert threshold to 14 days before expiry
4. Configure email/SMS alerts

#### Custom Monitoring Script

Create `/usr/local/bin/check-ssl-expiry.sh`:

```bash
#!/bin/bash

DOMAIN="your-domain.com"
ALERT_DAYS=14
EMAIL="admin@your-domain.com"

# Get expiry date
EXPIRY=$(echo | openssl s_client -connect ${DOMAIN}:443 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

if [ $DAYS_LEFT -lt $ALERT_DAYS ]; then
    echo "SSL certificate expires in $DAYS_LEFT days" | mail -s "SSL Certificate Expiry Warning" $EMAIL
fi
```

Add to crontab:
```bash
0 9 * * * /usr/local/bin/check-ssl-expiry.sh
```

#### Sentry Integration

Configure Sentry cron monitoring:
```python
# In your application
import certifi
import ssl
import socket
from datetime import datetime
import sentry_sdk

def check_ssl_expiry():
    hostname = 'your-domain.com'
    port = 443

    context = ssl.create_default_context()
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_left = (expiry - datetime.now()).days

            if days_left < 14:
                sentry_sdk.capture_message(
                    f"SSL certificate expires in {days_left} days",
                    level="warning"
                )
```

## Troubleshooting

### Certificate Validation Failures

#### Problem: "Failed authorization procedure"

**Causes**:
- Domain not pointing to server
- Firewall blocking port 80
- Nginx not serving .well-known directory

**Solutions**:

1. **Check DNS**:
   ```bash
   dig your-domain.com
   nslookup your-domain.com
   ```

2. **Test HTTP access**:
   ```bash
   curl -I http://your-domain.com/.well-known/acme-challenge/test
   ```

3. **Check nginx config**:
   ```bash
   grep -A 5 "well-known" /etc/nginx/nginx.conf
   ```

4. **Verify directory exists**:
   ```bash
   ls -la /var/www/acme-challenge/
   ```

### Port 80 Not Accessible

#### Problem: "Connection timeout on port 80"

**Solutions**:

1. **Check firewall**:
   ```bash
   sudo ufw status
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

2. **Check cloud provider firewall** (AWS Security Groups, etc.)

3. **Verify nginx is listening**:
   ```bash
   sudo netstat -tlnp | grep :80
   ```

### DNS Issues

#### Problem: "DNS problem: NXDOMAIN"

**Solutions**:

1. **Verify DNS records**:
   ```bash
   dig your-domain.com @8.8.8.8
   ```

2. **Wait for propagation** (can take up to 48 hours)

3. **Use DNS checker**:
   ```bash
   curl -s "https://dns.google/resolve?name=your-domain.com&type=A" | jq
   ```

### Nginx Reload Failures

#### Problem: "nginx: [emerg] cannot load certificate"

**Solutions**:

1. **Check certificate paths**:
   ```bash
   ls -la /etc/letsencrypt/live/your-domain.com/
   ```

2. **Verify nginx user permissions**:
   ```bash
   sudo -u nginx cat /etc/letsencrypt/live/your-domain.com/cert.pem
   ```

3. **Test nginx config**:
   ```bash
   nginx -t
   ```

### Rollback Procedures

If SSL configuration causes issues:

1. **Restore Previous Nginx Config**:
   ```bash
   cp nginx/nginx.conf.backup nginx/nginx.conf
   docker-compose -f docker-compose.prod.yml restart nginx
   ```

2. **Disable HTTPS Redirect** (temporary):
   ```nginx
   # Comment out in nginx.conf
   # return 301 https://$host$request_uri;
   ```

3. **Use HTTP-only** (emergency):
   ```bash
   # Edit docker-compose.prod.yml
   # Remove port 443 mapping
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Certificate Revocation

### When to Revoke

- Private key compromised
- Certificate issued incorrectly
- Domain no longer in use
- Security incident

### Revocation Process

1. **Revoke Certificate**:
   ```bash
   sudo certbot revoke --cert-path /etc/letsencrypt/live/your-domain.com/cert.pem
   ```

2. **Choose Reason** (optional):
   ```bash
   sudo certbot revoke --cert-path /etc/letsencrypt/live/your-domain.com/cert.pem --reason keycompromise
   ```

   Reasons:
   - `unspecified`
   - `keycompromise`
   - `affiliationchanged`
   - `superseded`
   - `cessationofoperation`

3. **Delete Certificate**:
   ```bash
   sudo certbot delete --cert-name your-domain.com
   ```

4. **Request New Certificate**:
   ```bash
   sudo certbot certonly --webroot -w /var/www/acme-challenge -d your-domain.com
   ```

## Multi-Domain Setup

### Adding Additional Domains

1. **Expand Existing Certificate**:
   ```bash
   sudo certbot certonly --webroot -w /var/www/acme-challenge \
     --cert-name your-domain.com \
     --expand \
     -d your-domain.com \
     -d www.your-domain.com \
     -d api.your-domain.com
   ```

2. **Separate Certificates** (recommended for different services):
   ```bash
   # Main domain
   sudo certbot certonly --webroot -w /var/www/acme-challenge \
     -d your-domain.com -d www.your-domain.com

   # API subdomain
   sudo certbot certonly --webroot -w /var/www/acme-challenge \
     -d api.your-domain.com
   ```

### Wildcard Certificates

For `*.your-domain.com`:

1. **DNS Challenge Required**:
   ```bash
   sudo certbot certonly --manual --preferred-challenges dns \
     -d "*.your-domain.com" -d your-domain.com
   ```

2. **Add DNS TXT Record** (as prompted):
   ```
   _acme-challenge.your-domain.com TXT "challenge-value"
   ```

3. **Verify and Continue**:
   ```bash
   dig TXT _acme-challenge.your-domain.com
   ```

### Subdomain Management

1. **List All Certificates**:
   ```bash
   sudo certbot certificates
   ```

2. **Update Nginx for Each Domain**:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name api.your-domain.com;

       ssl_certificate /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

       # ... rest of config
   }
   ```

## Security Best Practices

### Certificate Security

1. **Protect Private Keys**:
   ```bash
   chmod 600 /etc/letsencrypt/live/*/privkey.pem
   chown root:root /etc/letsencrypt/live/*/privkey.pem
   ```

2. **Regular Backups**:
   ```bash
   # Backup certificates
   tar -czf /backup/letsencrypt-$(date +%Y%m%d).tar.gz /etc/letsencrypt/

   # Exclude from version control
   echo "/etc/letsencrypt/" >> .gitignore
   ```

3. **Monitor Access Logs**:
   ```bash
   grep "privkey.pem" /var/log/auth.log
   ```

### HIPAA Compliance Checklist

- [ ] TLS 1.2 or higher enabled
- [ ] Weak ciphers disabled
- [ ] Certificate valid and not expired
- [ ] HSTS header configured
- [ ] Perfect Forward Secrecy enabled
- [ ] Regular certificate rotation (90-day max)
- [ ] Certificate monitoring in place
- [ ] Incident response plan for key compromise
- [ ] Audit logs for certificate access
- [ ] Documented renewal procedures

## Quick Reference

### Essential Commands

```bash
# Check certificate status
sudo certbot certificates

# Test renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# Check expiry
echo | openssl s_client -connect domain.com:443 2>/dev/null | openssl x509 -noout -enddate

# Reload nginx (Docker)
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

# View logs
sudo tail -f /var/log/letsencrypt/letsencrypt.log
```

### File Locations

- Certificates: `/etc/letsencrypt/live/your-domain.com/`
- Renewal config: `/etc/letsencrypt/renewal/your-domain.com.conf`
- Logs: `/var/log/letsencrypt/letsencrypt.log`
- Nginx config: `/path/to/pazpaz/nginx/nginx.conf`
- ACME webroot: `/var/www/acme-challenge/`

### Support Resources

- Let's Encrypt Documentation: https://letsencrypt.org/docs/
- Certbot Documentation: https://certbot.eff.org/docs/
- SSL Labs Test: https://www.ssllabs.com/ssltest/
- Certificate Transparency: https://crt.sh/

## Incident Response

### Key Compromise Response

1. **Immediate Actions**:
   ```bash
   # Revoke compromised certificate
   sudo certbot revoke --cert-path /etc/letsencrypt/live/domain/cert.pem --reason keycompromise

   # Generate new certificate
   sudo certbot certonly --webroot -w /var/www/acme-challenge -d domain.com --force-renewal

   # Update nginx
   docker-compose -f docker-compose.prod.yml restart nginx
   ```

2. **Investigation**:
   - Review access logs
   - Check for unauthorized certificate requests
   - Audit system for other compromises

3. **Notification**:
   - Inform security team
   - Document incident
   - Update security procedures

---

*Last Updated: 2024*
*Next Review: Before production deployment*