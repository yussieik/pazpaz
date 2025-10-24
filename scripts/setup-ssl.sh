#!/bin/bash
# PazPaz SSL Setup Script
# Sets up Let's Encrypt SSL certificates with automatic renewal
# HIPAA-compliant TLS configuration for production deployment

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/var/log/pazpaz-ssl-setup.log"
CERT_DIR="/etc/letsencrypt/live"
BACKUP_DIR="/var/backups/letsencrypt"
DH_PARAMS_FILE="/etc/nginx/dhparam.pem"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*" | tee -a "${LOG_FILE}"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "${LOG_FILE}" >&2
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*" | tee -a "${LOG_FILE}"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "${LOG_FILE}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Detect OS and distribution
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        error "Cannot detect operating system"
        exit 1
    fi

    case "$OS" in
        ubuntu|debian)
            log "Detected OS: $OS $VER"
            ;;
        *)
            error "This script only supports Ubuntu/Debian systems"
            exit 1
            ;;
    esac
}

# =============================================================================
# Installation Functions
# =============================================================================

install_dependencies() {
    log "Installing dependencies..."

    # Update package list
    apt-get update -qq

    # Install certbot and nginx plugin
    if ! command -v certbot &> /dev/null; then
        log "Installing certbot..."
        apt-get install -y certbot python3-certbot-nginx
    else
        info "Certbot is already installed"
    fi

    # Verify installation
    if ! command -v certbot &> /dev/null; then
        error "Failed to install certbot"
        exit 1
    fi

    log "Certbot version: $(certbot --version 2>&1 | head -n1)"
}

# =============================================================================
# Certificate Management
# =============================================================================

get_domain_info() {
    echo ""
    read -p "Enter your domain name (e.g., example.com): " DOMAIN

    if [[ -z "$DOMAIN" ]]; then
        error "Domain name cannot be empty"
        exit 1
    fi

    # Validate domain format
    if ! echo "$DOMAIN" | grep -qE '^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'; then
        error "Invalid domain format: $DOMAIN"
        exit 1
    fi

    read -p "Include www subdomain? (y/n): " INCLUDE_WWW

    if [[ "$INCLUDE_WWW" =~ ^[Yy]$ ]]; then
        DOMAINS="$DOMAIN,www.$DOMAIN"
        log "Will request certificate for: $DOMAIN and www.$DOMAIN"
    else
        DOMAINS="$DOMAIN"
        log "Will request certificate for: $DOMAIN"
    fi

    read -p "Enter email for renewal notifications: " EMAIL

    if [[ -z "$EMAIL" ]]; then
        error "Email cannot be empty"
        exit 1
    fi

    # Validate email format
    if ! echo "$EMAIL" | grep -qE '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'; then
        error "Invalid email format: $EMAIL"
        exit 1
    fi
}

check_existing_certificate() {
    local domain=$1

    if [[ -d "$CERT_DIR/$domain" ]]; then
        info "Existing certificate found for $domain"

        # Check expiry
        local expiry=$(openssl x509 -enddate -noout -in "$CERT_DIR/$domain/fullchain.pem" 2>/dev/null | cut -d= -f2)

        if [[ -n "$expiry" ]]; then
            info "Certificate expires: $expiry"

            # Check if certificate is expiring soon (within 30 days)
            local expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$expiry" +%s)
            local now_epoch=$(date +%s)
            local days_until_expiry=$(( ($expiry_epoch - $now_epoch) / 86400 ))

            if [[ $days_until_expiry -lt 30 ]]; then
                warn "Certificate expires in $days_until_expiry days"
                read -p "Renew certificate? (y/n): " RENEW

                if [[ "$RENEW" =~ ^[Yy]$ ]]; then
                    return 1
                fi
            else
                log "Certificate is valid for $days_until_expiry more days"
                read -p "Force renewal anyway? (y/n): " FORCE_RENEW

                if [[ ! "$FORCE_RENEW" =~ ^[Yy]$ ]]; then
                    return 0
                fi
            fi
        fi
    fi

    return 1
}

backup_existing_certificate() {
    local domain=$1

    if [[ -d "$CERT_DIR/$domain" ]]; then
        log "Backing up existing certificate for $domain..."

        # Create backup directory
        mkdir -p "$BACKUP_DIR"

        # Create timestamped backup
        local backup_name="$domain-$(date +%Y%m%d-%H%M%S)"
        cp -r "$CERT_DIR/$domain" "$BACKUP_DIR/$backup_name"

        log "Certificate backed up to: $BACKUP_DIR/$backup_name"
    fi
}

request_certificate() {
    local domain=$1
    local email=$2
    local domains=$3

    log "Requesting certificate for $domains..."

    # Build certbot command
    local certbot_cmd="certbot certonly"
    certbot_cmd="$certbot_cmd --webroot"
    certbot_cmd="$certbot_cmd --webroot-path /var/www/acme-challenge"
    certbot_cmd="$certbot_cmd --email $email"
    certbot_cmd="$certbot_cmd --agree-tos"
    certbot_cmd="$certbot_cmd --non-interactive"
    certbot_cmd="$certbot_cmd --expand"
    certbot_cmd="$certbot_cmd --domains $domains"

    # Create webroot directory if it doesn't exist
    mkdir -p /var/www/acme-challenge

    # Execute certbot
    if $certbot_cmd; then
        log "Certificate successfully obtained!"
        return 0
    else
        error "Failed to obtain certificate"
        return 1
    fi
}

# =============================================================================
# Nginx Configuration
# =============================================================================

generate_dhparams() {
    if [[ ! -f "$DH_PARAMS_FILE" ]]; then
        log "Generating Diffie-Hellman parameters (this may take a while)..."
        openssl dhparam -out "$DH_PARAMS_FILE" 2048
        chmod 644 "$DH_PARAMS_FILE"
        log "DH parameters generated: $DH_PARAMS_FILE"
    else
        info "DH parameters already exist: $DH_PARAMS_FILE"
    fi
}

update_nginx_config() {
    local domain=$1
    local nginx_conf="/etc/nginx/nginx.conf"
    local project_nginx_conf="$PROJECT_ROOT/nginx/nginx.conf"

    # Check which nginx config to update
    if [[ -f "$project_nginx_conf" ]]; then
        nginx_conf="$project_nginx_conf"
        info "Updating project nginx configuration: $nginx_conf"
    elif [[ -f "$nginx_conf" ]]; then
        info "Updating system nginx configuration: $nginx_conf"
    else
        error "No nginx configuration found"
        return 1
    fi

    # Backup current config
    cp "$nginx_conf" "${nginx_conf}.backup-$(date +%Y%m%d-%H%M%S)"

    # Create a marker file to indicate SSL is configured
    echo "$domain" > "$PROJECT_ROOT/.ssl-domain"

    log "Nginx configuration prepared for SSL"
    info "Please update your nginx.conf with the SSL configuration for domain: $domain"
    info "Certificate paths:"
    info "  - Certificate: $CERT_DIR/$domain/fullchain.pem"
    info "  - Private Key: $CERT_DIR/$domain/privkey.pem"
    info "  - Chain: $CERT_DIR/$domain/chain.pem"
    info "  - DH Params: $DH_PARAMS_FILE"
}

test_nginx_config() {
    if command -v nginx &> /dev/null; then
        log "Testing nginx configuration..."

        if nginx -t; then
            log "Nginx configuration test passed"
            return 0
        else
            error "Nginx configuration test failed"
            return 1
        fi
    else
        warn "Nginx not installed locally - skipping configuration test"
        return 0
    fi
}

reload_nginx() {
    if systemctl is-active --quiet nginx; then
        log "Reloading nginx..."
        systemctl reload nginx
        log "Nginx reloaded successfully"
    elif docker ps --format '{{.Names}}' | grep -q nginx; then
        log "Reloading nginx container..."
        docker exec nginx nginx -s reload
        log "Nginx container reloaded successfully"
    else
        warn "Nginx is not running - please start it manually"
    fi
}

# =============================================================================
# Automatic Renewal Setup
# =============================================================================

setup_auto_renewal() {
    log "Setting up automatic certificate renewal..."

    # Create renewal hook script
    cat > /etc/letsencrypt/renewal-hooks/post/reload-nginx.sh << 'EOF'
#!/bin/bash
# Post-renewal hook to reload nginx

# Try systemd first
if systemctl is-active --quiet nginx; then
    systemctl reload nginx
# Try Docker container
elif docker ps --format '{{.Names}}' | grep -q nginx; then
    docker exec nginx nginx -s reload
fi
EOF

    chmod +x /etc/letsencrypt/renewal-hooks/post/reload-nginx.sh

    # Add cron job for renewal
    local cron_job="0 3 * * * certbot renew --quiet"

    if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
        (crontab -l 2>/dev/null; echo "$cron_job") | crontab -
        log "Added cron job for automatic renewal"
    else
        info "Renewal cron job already exists"
    fi

    # Test renewal
    log "Testing renewal configuration (dry run)..."

    if certbot renew --dry-run; then
        log "Renewal test passed"
    else
        error "Renewal test failed - please check configuration"
    fi
}

# =============================================================================
# Verification
# =============================================================================

verify_certificate() {
    local domain=$1

    log "Verifying certificate installation..."

    # Check certificate files exist
    local cert_files=(
        "$CERT_DIR/$domain/fullchain.pem"
        "$CERT_DIR/$domain/privkey.pem"
        "$CERT_DIR/$domain/chain.pem"
    )

    for file in "${cert_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            error "Certificate file missing: $file"
            return 1
        fi
    done

    # Check certificate validity
    local cert_info=$(openssl x509 -in "$CERT_DIR/$domain/fullchain.pem" -noout -text 2>/dev/null)

    if [[ -z "$cert_info" ]]; then
        error "Failed to read certificate"
        return 1
    fi

    # Extract certificate details
    local subject=$(openssl x509 -in "$CERT_DIR/$domain/fullchain.pem" -noout -subject 2>/dev/null)
    local issuer=$(openssl x509 -in "$CERT_DIR/$domain/fullchain.pem" -noout -issuer 2>/dev/null)
    local dates=$(openssl x509 -in "$CERT_DIR/$domain/fullchain.pem" -noout -dates 2>/dev/null)

    info "Certificate Details:"
    info "  $subject"
    info "  $issuer"
    echo "$dates" | while IFS= read -r line; do
        info "  $line"
    done

    # Test HTTPS connection (if nginx is running)
    if command -v curl &> /dev/null; then
        log "Testing HTTPS connection..."

        if curl -Is "https://$domain" --connect-timeout 5 > /dev/null 2>&1; then
            log "HTTPS connection successful!"
        else
            warn "Could not verify HTTPS connection (this is normal if nginx is not yet configured)"
        fi
    fi

    log "Certificate verification complete"
}

# =============================================================================
# Main Script
# =============================================================================

main() {
    log "=== PazPaz SSL Setup Script ==="
    log "Starting SSL certificate setup..."

    # Prerequisites
    check_root
    detect_os

    # Create log file if it doesn't exist
    touch "$LOG_FILE"
    chmod 644 "$LOG_FILE"

    # Install dependencies
    install_dependencies

    # Get domain information
    get_domain_info

    # Check for existing certificate
    if check_existing_certificate "$DOMAIN"; then
        info "Using existing certificate for $DOMAIN"

        # Still set up auto-renewal
        setup_auto_renewal
        verify_certificate "$DOMAIN"

        log "SSL setup complete (existing certificate retained)"
        exit 0
    fi

    # Backup existing certificate
    backup_existing_certificate "$DOMAIN"

    # Request new certificate
    if ! request_certificate "$DOMAIN" "$EMAIL" "$DOMAINS"; then
        error "Certificate request failed"

        # Restore backup if it exists
        if [[ -d "$BACKUP_DIR" ]]; then
            warn "You can restore the previous certificate from: $BACKUP_DIR"
        fi

        exit 1
    fi

    # Generate DH parameters
    generate_dhparams

    # Update nginx configuration
    update_nginx_config "$DOMAIN"

    # Test nginx configuration
    if test_nginx_config; then
        reload_nginx
    fi

    # Set up automatic renewal
    setup_auto_renewal

    # Verify installation
    verify_certificate "$DOMAIN"

    log "=== SSL Setup Complete ==="
    log ""
    log "Next steps:"
    log "1. Update your nginx.conf with the SSL configuration"
    log "2. Ensure DNS points to this server"
    log "3. Test HTTPS access: https://$DOMAIN"
    log "4. Monitor renewal: certbot renew --dry-run"
    log ""
    log "Certificate paths:"
    log "  - Certificate: $CERT_DIR/$DOMAIN/fullchain.pem"
    log "  - Private Key: $CERT_DIR/$DOMAIN/privkey.pem"
    log "  - Chain: $CERT_DIR/$DOMAIN/chain.pem"
    log ""
    log "Automatic renewal is configured via cron (daily at 3 AM)"

    exit 0
}

# Run main function
main "$@"