#!/bin/bash
# Script to enable SSL configuration for nginx

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if domain is configured
if [[ ! -f "$SCRIPT_DIR/../.ssl-domain" ]]; then
    echo "Error: SSL not configured. Run scripts/setup-ssl.sh first"
    exit 1
fi

DOMAIN=$(cat "$SCRIPT_DIR/../.ssl-domain")

echo "Enabling SSL configuration for domain: $DOMAIN"

# Backup current config
cp "$SCRIPT_DIR/nginx.conf" "$SCRIPT_DIR/nginx.conf.backup"

# Copy SSL config and replace domain placeholder
sed "s/\${DOMAIN_NAME}/$DOMAIN/g" "$SCRIPT_DIR/nginx-ssl.conf" > "$SCRIPT_DIR/nginx.conf"

echo "SSL configuration enabled. Please reload nginx."