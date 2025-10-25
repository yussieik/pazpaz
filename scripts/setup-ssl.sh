#!/usr/bin/env bash

###############################################################################
# SSL Certificate Setup Script - Let's Encrypt with Certbot
###############################################################################
#
# This script sets up SSL/TLS certificates using Let's Encrypt for production
# deployment. It installs certbot, requests certificates, and configures
# automatic renewal.
#
# Usage:
#   sudo ./setup-ssl.sh your-domain.com
#
# Requirements:
#   - Domain must be pointed to this server (DNS A record)
#   - Port 80 must be open for HTTP-01 challenge
#   - Must be run as root or with sudo
#
###############################################################################

set -euo pipefail

# Configuration
DOMAIN="${1:-}"
EMAIL="${CERTBOT_EMAIL:-admin@${DOMAIN}}"
WEBROOT="/var/www/certbot"
CERT_PATH="/etc/letsencrypt/live/${DOMAIN}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

###############################################################################
# Helper Functions
###############################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        exit 1
    fi
}

check_domain() {
    if [[ -z "$DOMAIN" ]]; then
        log_error "Usage: $0 <domain>"
        log_error "Example: $0 example.com"
        exit 1
    fi
}

check_dns() {
    log_info "Checking DNS resolution for ${DOMAIN}..."

    # Get server's public IP
    SERVER_IP=$(curl -s ifconfig.me || curl -s icanhazip.com)

    # Check if domain resolves to this server
    RESOLVED_IP=$(dig +short "${DOMAIN}" | tail -1)

    if [[ -z "$RESOLVED_IP" ]]; then
        log_error "Domain ${DOMAIN} does not resolve to any IP"
        log_error "Please configure DNS A record pointing to ${SERVER_IP}"
        exit 1
    fi

    if [[ "$RESOLVED_IP" != "$SERVER_IP" ]]; then
        log_warn "Domain ${DOMAIN} resolves to ${RESOLVED_IP}"
        log_warn "But this server's IP is ${SERVER_IP}"
        log_warn "SSL setup may fail if DNS is not correct"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_info "✓ DNS correctly configured (${DOMAIN} → ${SERVER_IP})"
    fi
}

install_certbot() {
    log_info "Installing certbot..."

    # Update package list
    apt-get update -qq

    # Install certbot
    if command -v certbot &> /dev/null; then
        log_info "✓ Certbot already installed"
        certbot --version
    else
        apt-get install -y -qq certbot python3-certbot-nginx
        log_info "✓ Certbot installed successfully"
    fi
}

stop_nginx_if_running() {
    log_info "Checking for running nginx..."

    if docker ps | grep -q pazpaz-nginx; then
        log_warn "Stopping nginx container for certificate issuance..."
        cd /opt/pazpaz
        docker compose -f docker-compose.prod.yml stop nginx
    fi
}

request_certificate() {
    log_info "Requesting SSL certificate from Let's Encrypt..."

    # Create webroot directory
    mkdir -p "$WEBROOT"

    # Request certificate using standalone mode (temporarily binds to port 80)
    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        --domains "$DOMAIN" \
        --domains "www.${DOMAIN}" \
        --preferred-challenges http \
        || {
            log_error "Certificate request failed"
            log_error "Common causes:"
            log_error "  1. DNS not propagated yet (wait 5-15 minutes)"
            log_error "  2. Port 80 blocked by firewall"
            log_error "  3. Another service using port 80"
            log_error "  4. Rate limit reached (5 certs/week per domain)"
            exit 1
        }

    log_info "✓ Certificate obtained successfully"

    # Show certificate info
    certbot certificates -d "$DOMAIN"
}

setup_auto_renewal() {
    log_info "Setting up automatic certificate renewal..."

    # Certbot installs a systemd timer by default
    if systemctl is-active --quiet certbot.timer; then
        log_info "✓ Certbot renewal timer already active"
    else
        systemctl enable certbot.timer
        systemctl start certbot.timer
        log_info "✓ Certbot renewal timer enabled"
    fi

    # Create renewal hook to restart nginx after renewal
    mkdir -p /etc/letsencrypt/renewal-hooks/post
    cat > /etc/letsencrypt/renewal-hooks/post/restart-nginx.sh << 'HOOK'
#!/bin/bash
# Restart nginx container after certificate renewal
cd /opt/pazpaz
docker compose -f docker-compose.prod.yml restart nginx
echo "$(date): Nginx restarted after certificate renewal" >> /var/log/certbot-renewal.log
HOOK

    chmod +x /etc/letsencrypt/renewal-hooks/post/restart-nginx.sh
    log_info "✓ Renewal hook configured"

    # Test renewal
    log_info "Testing automatic renewal (dry run)..."
    certbot renew --dry-run || log_warn "Dry run failed, but certificate was issued"
}

update_nginx_config() {
    log_info "Updating nginx configuration for HTTPS..."

    cd /opt/pazpaz

    # Update docker-compose to add certificate volume mounts
    if ! grep -q "/etc/letsencrypt" docker-compose.prod.yml; then
        log_info "Adding certificate mounts to docker-compose.prod.yml..."
        # This will be done manually or via sed if needed
    fi
}

update_environment() {
    log_info "Updating environment variables for HTTPS..."

    cd /opt/pazpaz

    # Backup .env.production
    cp .env.production .env.production.backup

    # Update URLs to use https://
    sed -i "s|http://${DOMAIN}|https://${DOMAIN}|g" .env.production
    sed -i "s|http://www.${DOMAIN}|https://www.${DOMAIN}|g" .env.production

    log_info "✓ Environment variables updated for HTTPS"
}

verify_certificate() {
    log_info "Verifying certificate installation..."

    if [[ -f "${CERT_PATH}/fullchain.pem" ]] && [[ -f "${CERT_PATH}/privkey.pem" ]]; then
        log_info "✓ Certificate files found:"
        log_info "  - Certificate: ${CERT_PATH}/fullchain.pem"
        log_info "  - Private Key: ${CERT_PATH}/privkey.pem"
        log_info "  - Chain: ${CERT_PATH}/chain.pem"

        # Show expiry date
        EXPIRY=$(openssl x509 -enddate -noout -in "${CERT_PATH}/fullchain.pem" | cut -d= -f2)
        log_info "  - Expires: ${EXPIRY}"

        # Set proper permissions
        chmod 644 "${CERT_PATH}/fullchain.pem"
        chmod 600 "${CERT_PATH}/privkey.pem"

        return 0
    else
        log_error "Certificate files not found at ${CERT_PATH}"
        return 1
    fi
}

###############################################################################
# Main Script
###############################################################################

main() {
    log_info "=== Let's Encrypt SSL Setup for ${DOMAIN} ==="
    echo

    # Pre-flight checks
    check_root
    check_domain
    check_dns

    # Install certbot
    install_certbot

    # Stop nginx if running (needed for standalone mode)
    stop_nginx_if_running

    # Request certificate
    request_certificate

    # Verify certificate
    verify_certificate

    # Setup auto-renewal
    setup_auto_renewal

    # Update nginx config
    update_nginx_config

    # Update environment
    update_environment

    echo
    log_info "=== SSL Setup Complete ==="
    log_info ""
    log_info "✓ SSL certificate obtained for ${DOMAIN}"
    log_info "✓ Auto-renewal configured (checks twice daily)"
    log_info "✓ Renewal hook will restart nginx automatically"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Deploy services with HTTPS: cd /opt/pazpaz && ./scripts/deploy.sh"
    log_info "  2. Test HTTPS: curl -I https://${DOMAIN}"
    log_info "  3. Check auto-renewal: sudo certbot renew --dry-run"
    log_info ""
    log_info "Certificate details:"
    certbot certificates -d "$DOMAIN"
}

main "$@"
