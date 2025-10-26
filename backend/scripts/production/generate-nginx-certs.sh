#!/bin/bash
# Generate SSL certificates for nginx signed by PazPaz CA
# HIPAA Compliance: HTTPS/TLS required for all web traffic with PHI
# Uses existing CA from PostgreSQL certificate generation

set -e

CERTS_DIR="/opt/pazpaz/backend/certs"
NGINX_SSL_DIR="/opt/pazpaz/ssl"
DOMAIN_NAME="pazpaz.health"
DAYS_VALID=3650  # 10 years for production

echo "======================================================================="
echo "  Generating nginx SSL Certificates (HIPAA-Compliant)"
echo "======================================================================="
echo "Location: $NGINX_SSL_DIR"
echo "Domain: $DOMAIN_NAME"
echo "Validity: $DAYS_VALID days"
echo "CA: $CERTS_DIR/ca-cert.pem"
echo ""

# Verify CA exists
if [ ! -f "$CERTS_DIR/ca-cert.pem" ] || [ ! -f "$CERTS_DIR/ca-key.pem" ]; then
    echo "❌ ERROR: CA certificates not found in $CERTS_DIR"
    echo "Please run regenerate-ssl-certs-v2.sh first to create the CA"
    exit 1
fi

# Backup existing nginx certificates if they exist
if [ -f "$NGINX_SSL_DIR/fullchain.pem" ]; then
    echo "Backing up existing nginx certificates..."
    mkdir -p "$NGINX_SSL_DIR/backup-$(date +%Y%m%d-%H%M%S)"
    cp -p "$NGINX_SSL_DIR"/*.pem "$NGINX_SSL_DIR/backup-$(date +%Y%m%d-%H%M%S)/" 2>/dev/null || true
fi

# Create ssl directory if it doesn't exist
mkdir -p "$NGINX_SSL_DIR"

# Generate nginx private key and CSR
echo "[1/4] Generating nginx certificate request..."
openssl req -new -nodes \
    -out "$NGINX_SSL_DIR/nginx-req.pem" \
    -keyout "$NGINX_SSL_DIR/privkey.pem" \
    -subj "/C=US/ST=State/L=City/O=PazPaz Production/CN=$DOMAIN_NAME"

# Create OpenSSL config for nginx certificate with SAN
echo "[2/4] Creating OpenSSL config with SAN extensions..."
cat > "$NGINX_SSL_DIR/nginx-openssl.cnf" << EOF
[req]
distinguished_name = req_distinguished_name

[req_distinguished_name]

[v3_server]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $DOMAIN_NAME
DNS.2 = www.$DOMAIN_NAME
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

# Sign nginx certificate with CA
echo "[3/4] Signing nginx certificate with CA..."
openssl x509 -req -in "$NGINX_SSL_DIR/nginx-req.pem" \
    -days $DAYS_VALID -CA "$CERTS_DIR/ca-cert.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -set_serial 04 -out "$NGINX_SSL_DIR/cert.pem" \
    -extfile "$NGINX_SSL_DIR/nginx-openssl.cnf" -extensions v3_server

# Create fullchain.pem (cert + CA chain) for nginx
echo "[4/4] Creating fullchain.pem (cert + CA)..."
cat "$NGINX_SSL_DIR/cert.pem" "$CERTS_DIR/ca-cert.pem" > "$NGINX_SSL_DIR/fullchain.pem"

# Also create chain.pem (just CA) for nginx
cp "$CERTS_DIR/ca-cert.pem" "$NGINX_SSL_DIR/chain.pem"

# Set proper permissions
chmod 600 "$NGINX_SSL_DIR/privkey.pem"
chmod 644 "$NGINX_SSL_DIR/cert.pem"
chmod 644 "$NGINX_SSL_DIR/fullchain.pem"
chmod 644 "$NGINX_SSL_DIR/chain.pem"
chown -R pazpaz:pazpaz "$NGINX_SSL_DIR"

# Clean up temporary files
rm -f "$NGINX_SSL_DIR/nginx-req.pem" "$NGINX_SSL_DIR/nginx-openssl.cnf"

echo ""
echo "✅ nginx SSL certificates generated successfully!"
echo ""
echo "Files created:"
ls -lh "$NGINX_SSL_DIR"/*.pem
echo ""
echo "Certificate details:"
openssl x509 -in "$NGINX_SSL_DIR/cert.pem" -noout -subject -dates -ext subjectAltName
echo ""
echo "Next steps:"
echo "1. Update nginx.conf to use self-signed certificates in /etc/nginx/ssl/"
echo "2. Restart nginx service: docker compose --env-file .env.production restart nginx"
echo "3. Test HTTPS access: curl -k https://pazpaz.health"
echo "4. Later: Replace with Let's Encrypt certificates for production"
echo ""
