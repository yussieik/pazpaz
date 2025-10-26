#!/bin/bash
# Generate SSL certificates for MinIO signed by PazPaz CA
# HIPAA Compliance: MinIO SSL/TLS required for PHI file attachments in transit
# Uses existing CA from PostgreSQL certificate generation

set -e

CERTS_DIR="/opt/pazpaz/backend/certs"
MINIO_DIR="$CERTS_DIR/minio"
DAYS_VALID=3650  # 10 years for production

echo "======================================================================="
echo "  Generating MinIO SSL Certificates (HIPAA-Compliant)"
echo "======================================================================="
echo "Location: $MINIO_DIR"
echo "Validity: $DAYS_VALID days"
echo "CA: $CERTS_DIR/ca-cert.pem"
echo ""

# Verify CA exists
if [ ! -f "$CERTS_DIR/ca-cert.pem" ] || [ ! -f "$CERTS_DIR/ca-key.pem" ]; then
    echo "ERROR: CA certificates not found in $CERTS_DIR"
    echo "Please run regenerate-ssl-certs-v2.sh first to create the CA"
    exit 1
fi

# Backup existing MinIO certificates if they exist
if [ -f "$MINIO_DIR/public.crt" ]; then
    echo "Backing up existing MinIO certificates..."
    mkdir -p "$MINIO_DIR/backup-$(date +%Y%m%d-%H%M%S)"
    cp -p "$MINIO_DIR"/*.{crt,key} "$MINIO_DIR/backup-$(date +%Y%m%d-%H%M%S)/" 2>/dev/null || true
fi

# Create minio directory if it doesn't exist
mkdir -p "$MINIO_DIR"

# Generate MinIO private key and CSR
echo "[1/4] Generating MinIO certificate request..."
openssl req -new -nodes \
    -out "$MINIO_DIR/minio-req.pem" \
    -keyout "$MINIO_DIR/private.key" \
    -subj "/C=US/ST=State/L=City/O=PazPaz Production/CN=minio"

# Create OpenSSL config for MinIO certificate with SAN
echo "[2/4] Creating OpenSSL config with SAN extensions..."
cat > "$MINIO_DIR/minio-openssl.cnf" << 'EOF'
[req]
distinguished_name = req_distinguished_name

[req_distinguished_name]

[v3_server]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = minio
DNS.2 = localhost
DNS.3 = pazpaz-minio
IP.1 = 127.0.0.1
EOF

# Sign MinIO certificate with CA
echo "[3/4] Signing MinIO certificate with CA..."
openssl x509 -req -in "$MINIO_DIR/minio-req.pem" \
    -days $DAYS_VALID -CA "$CERTS_DIR/ca-cert.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -set_serial 03 -out "$MINIO_DIR/public.crt" \
    -extfile "$MINIO_DIR/minio-openssl.cnf" -extensions v3_server

# Copy CA certificate to MinIO directory (MinIO needs it for client verification)
echo "[4/4] Copying CA certificate to MinIO directory..."
cp "$CERTS_DIR/ca-cert.pem" "$MINIO_DIR/ca-cert.pem"

# Set proper permissions
chmod 600 "$MINIO_DIR/private.key"
chmod 644 "$MINIO_DIR/public.crt"
chmod 644 "$MINIO_DIR/ca-cert.pem"
chown -R pazpaz:pazpaz "$MINIO_DIR"

# Clean up temporary files
rm -f "$MINIO_DIR/minio-req.pem" "$MINIO_DIR/minio-openssl.cnf"

echo ""
echo "✅ MinIO SSL certificates generated successfully!"
echo ""
echo "Files created:"
ls -lh "$MINIO_DIR"/*.{crt,key}
echo ""
echo "Certificate details:"
openssl x509 -in "$MINIO_DIR/public.crt" -noout -subject -dates -ext subjectAltName
echo ""
echo "Next steps:"
echo "1. Restart MinIO service: docker compose --env-file .env.production restart minio"
echo "2. Restart API service: docker compose --env-file .env.production restart api"
echo "3. Verify no SSL warnings in API logs"
echo ""
