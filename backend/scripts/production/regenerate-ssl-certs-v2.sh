#!/bin/bash
# Generate self-signed SSL certificates for PostgreSQL (production deployment)
# HIPAA Compliance: PostgreSQL SSL/TLS is REQUIRED for PHI data in transit
# Includes proper X.509 v3 extensions for modern certificate validation

set -e

CERTS_DIR="/opt/pazpaz/backend/certs"
DAYS_VALID=3650  # 10 years for production

echo "======================================================================="
echo "  Regenerating PostgreSQL SSL Certificates (HIPAA-Compliant v2)"
echo "======================================================================="
echo "Location: $CERTS_DIR"
echo "Validity: $DAYS_VALID days"
echo ""

# Backup existing certificates
if [ -f "$CERTS_DIR/ca-cert.pem" ]; then
    echo "Backing up existing certificates..."
    mkdir -p "$CERTS_DIR/backup-$(date +%Y%m%d-%H%M%S)"
    cp -p "$CERTS_DIR"/*.pem "$CERTS_DIR/backup-$(date +%Y%m%d-%H%M%S)/" 2>/dev/null || true
fi

# Create certs directory if it doesn't exist
mkdir -p "$CERTS_DIR"

# Create OpenSSL config for CA with proper extensions
cat > "$CERTS_DIR/ca-openssl.cnf" << 'EOF'
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no

[req_distinguished_name]
C = US
ST = State
L = City
O = PazPaz Production
CN = PazPaz Production CA

[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign,digitalSignature
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF

# Generate CA certificate with proper extensions
echo "[1/6] Generating CA certificate with Key Usage extension..."
openssl req -new -x509 -days $DAYS_VALID -nodes \
    -out "$CERTS_DIR/ca-cert.pem" \
    -keyout "$CERTS_DIR/ca-key.pem" \
    -config "$CERTS_DIR/ca-openssl.cnf"

# Generate server certificate request
echo "[2/6] Generating server certificate request..."
openssl req -new -nodes \
    -out "$CERTS_DIR/server-req.pem" \
    -keyout "$CERTS_DIR/server-key.pem" \
    -subj "/C=US/ST=State/L=City/O=PazPaz Production/CN=db"

# Create OpenSSL config for server certificate with SAN
cat > "$CERTS_DIR/server-openssl.cnf" << 'EOF'
[req]
distinguished_name = req_distinguished_name

[req_distinguished_name]

[v3_server]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = db
DNS.2 = localhost
DNS.3 = pazpaz-db
IP.1 = 127.0.0.1
EOF

# Sign server certificate with CA and proper extensions
echo "[3/6] Signing server certificate with CA..."
openssl x509 -req -in "$CERTS_DIR/server-req.pem" \
    -days $DAYS_VALID -CA "$CERTS_DIR/ca-cert.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -set_serial 01 -out "$CERTS_DIR/server-cert.pem" \
    -extfile "$CERTS_DIR/server-openssl.cnf" -extensions v3_server

# Generate client certificate request
echo "[4/6] Generating client certificate request..."
openssl req -new -nodes \
    -out "$CERTS_DIR/client-req.pem" \
    -keyout "$CERTS_DIR/client-key.pem" \
    -subj "/C=US/ST=State/L=City/O=PazPaz Production/CN=pazpaz"

# Create OpenSSL config for client certificate
cat > "$CERTS_DIR/client-openssl.cnf" << 'EOF'
[v3_client]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
EOF

# Sign client certificate with CA
echo "[5/6] Signing client certificate with CA..."
openssl x509 -req -in "$CERTS_DIR/client-req.pem" \
    -days $DAYS_VALID -CA "$CERTS_DIR/ca-cert.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -set_serial 02 -out "$CERTS_DIR/client-cert.pem" \
    -extfile "$CERTS_DIR/client-openssl.cnf" -extensions v3_client

# Set proper permissions
echo "[6/6] Setting file permissions and ownership..."
chmod 600 "$CERTS_DIR/server-key.pem"
chmod 600 "$CERTS_DIR/client-key.pem"
chmod 600 "$CERTS_DIR/ca-key.pem"
chmod 644 "$CERTS_DIR/server-cert.pem"
chmod 644 "$CERTS_DIR/client-cert.pem"
chmod 644 "$CERTS_DIR/ca-cert.pem"

# Set ownership: server certs to postgres (UID 70), others to pazpaz
chown 70:70 "$CERTS_DIR/server-cert.pem" "$CERTS_DIR/server-key.pem" 2>/dev/null || echo "Note: chown requires sudo, run manually after script completes"
chown paz paz:pazpaz "$CERTS_DIR/ca-cert.pem" "$CERTS_DIR/ca-key.pem" "$CERTS_DIR/client-cert.pem" "$CERTS_DIR/client-key.pem" 2>/dev/null || true

# Create root.crt symlink (PostgreSQL expects this name)
ln -sf "$CERTS_DIR/ca-cert.pem" "$CERTS_DIR/root.crt"

# Clean up temporary files
rm -f "$CERTS_DIR/server-req.pem" "$CERTS_DIR/client-req.pem" "$CERTS_DIR"/*-openssl.cnf

echo ""
echo "✅ SSL certificates regenerated successfully with proper extensions!"
echo ""
echo "Files created:"
ls -lh "$CERTS_DIR"/*.pem
echo ""
echo "Certificate details:"
openssl x509 -in "$CERTS_DIR/ca-cert.pem" -noout -subject -dates -ext keyUsage
echo ""
