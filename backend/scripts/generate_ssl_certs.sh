#!/bin/bash
# Generate self-signed SSL certificates for PostgreSQL (development only)
#
# For production, use proper CA-signed certificates from:
# - AWS RDS Certificate Authority
# - Let's Encrypt
# - Your organization's internal CA
#
# HIPAA Compliance: PostgreSQL SSL/TLS is REQUIRED for PHI data in transit

set -e

CERTS_DIR="/Users/yussieik/Desktop/projects/pazpaz/backend/certs"
DAYS_VALID=365

echo "Generating PostgreSQL SSL certificates for development..."
echo "Location: $CERTS_DIR"
echo ""

# Create certs directory if it doesn't exist
mkdir -p "$CERTS_DIR"

# Generate CA certificate (Certificate Authority)
echo "1. Generating CA certificate..."
openssl req -new -x509 -days $DAYS_VALID -nodes \
    -out "$CERTS_DIR/ca-cert.pem" \
    -keyout "$CERTS_DIR/ca-key.pem" \
    -subj "/C=US/ST=California/L=San Francisco/O=PazPaz Dev/CN=PazPaz Development CA"

# Generate server certificate request
echo "2. Generating server certificate request..."
openssl req -new -nodes \
    -out "$CERTS_DIR/server-req.pem" \
    -keyout "$CERTS_DIR/server-key.pem" \
    -subj "/C=US/ST=California/L=San Francisco/O=PazPaz Dev/CN=localhost"

# Sign server certificate with CA
echo "3. Signing server certificate with CA..."
openssl x509 -req -in "$CERTS_DIR/server-req.pem" \
    -days $DAYS_VALID -CA "$CERTS_DIR/ca-cert.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -set_serial 01 -out "$CERTS_DIR/server-cert.pem"

# Generate client certificate request
echo "4. Generating client certificate request..."
openssl req -new -nodes \
    -out "$CERTS_DIR/client-req.pem" \
    -keyout "$CERTS_DIR/client-key.pem" \
    -subj "/C=US/ST=California/L=San Francisco/O=PazPaz Dev/CN=pazpaz"

# Sign client certificate with CA
echo "5. Signing client certificate with CA..."
openssl x509 -req -in "$CERTS_DIR/client-req.pem" \
    -days $DAYS_VALID -CA "$CERTS_DIR/ca-cert.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -set_serial 02 -out "$CERTS_DIR/client-cert.pem"

# Set proper permissions (PostgreSQL requires specific permissions)
echo "6. Setting file permissions..."
chmod 600 "$CERTS_DIR/server-key.pem"
chmod 600 "$CERTS_DIR/client-key.pem"
chmod 644 "$CERTS_DIR/server-cert.pem"
chmod 644 "$CERTS_DIR/client-cert.pem"
chmod 644 "$CERTS_DIR/ca-cert.pem"

# Create root.crt symlink (PostgreSQL expects this name)
ln -sf "$CERTS_DIR/ca-cert.pem" "$CERTS_DIR/root.crt"

# Clean up certificate requests
rm -f "$CERTS_DIR/server-req.pem" "$CERTS_DIR/client-req.pem"

echo ""
echo "✅ SSL certificates generated successfully!"
echo ""
echo "Files created:"
echo "  - ca-cert.pem (CA certificate - used for verification)"
echo "  - server-cert.pem (PostgreSQL server certificate)"
echo "  - server-key.pem (PostgreSQL server private key)"
echo "  - client-cert.pem (Client certificate for mutual TLS)"
echo "  - client-key.pem (Client private key)"
echo "  - root.crt (symlink to ca-cert.pem)"
echo ""
echo "⚠️  IMPORTANT: These are self-signed certificates for DEVELOPMENT ONLY"
echo "    For production, use CA-signed certificates from:"
echo "    - AWS RDS: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html"
echo "    - Let's Encrypt: https://letsencrypt.org/"
echo ""
echo "Next steps:"
echo "  1. Update docker-compose.yml to mount certificates into PostgreSQL container"
echo "  2. Configure PostgreSQL to require SSL (ssl=on)"
echo "  3. Update DATABASE_URL to include ?ssl=require or ?ssl=verify-full"
echo ""
