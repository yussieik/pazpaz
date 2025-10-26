#!/bin/bash
# Fix nginx SSL Configuration with Self-Signed Certificates
# Generates certificates signed by PazPaz CA and configures nginx to use them

set -e

cd /opt/pazpaz

echo "======================================================================="
echo "  Fixing nginx SSL Configuration"
echo "======================================================================="
echo ""

# Step 1: Generate nginx SSL certificates
echo "[1/5] Generating nginx SSL certificates..."
echo ""

CERTS_DIR="/opt/pazpaz/backend/certs"
NGINX_SSL_DIR="/opt/pazpaz/ssl"
DOMAIN_NAME="pazpaz.health"
DAYS_VALID=3650

# Verify CA exists
if [ ! -f "$CERTS_DIR/ca-cert.pem" ] || [ ! -f "$CERTS_DIR/ca-key.pem" ]; then
    echo "❌ ERROR: CA certificates not found in $CERTS_DIR"
    exit 1
fi

# Create ssl directory
mkdir -p "$NGINX_SSL_DIR"

# Generate nginx private key and CSR
openssl req -new -nodes \
    -out "$NGINX_SSL_DIR/nginx-req.pem" \
    -keyout "$NGINX_SSL_DIR/privkey.pem" \
    -subj "/C=US/ST=State/L=City/O=PazPaz Production/CN=$DOMAIN_NAME" 2>/dev/null

# Create OpenSSL config for nginx certificate with SAN
cat > "$NGINX_SSL_DIR/nginx-openssl.cnf" << 'EOF'
[req]
distinguished_name = req_distinguished_name

[req_distinguished_name]

[v3_server]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = pazpaz.health
DNS.2 = www.pazpaz.health
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

# Sign nginx certificate with CA
openssl x509 -req -in "$NGINX_SSL_DIR/nginx-req.pem" \
    -days $DAYS_VALID -CA "$CERTS_DIR/ca-cert.pem" -CAkey "$CERTS_DIR/ca-key.pem" \
    -set_serial 04 -out "$NGINX_SSL_DIR/cert.pem" \
    -extfile "$NGINX_SSL_DIR/nginx-openssl.cnf" -extensions v3_server 2>/dev/null

# Create fullchain.pem (cert + CA chain)
cat "$NGINX_SSL_DIR/cert.pem" "$CERTS_DIR/ca-cert.pem" > "$NGINX_SSL_DIR/fullchain.pem"

# Create chain.pem (just CA)
cp "$CERTS_DIR/ca-cert.pem" "$NGINX_SSL_DIR/chain.pem"

# Set permissions
chmod 600 "$NGINX_SSL_DIR/privkey.pem"
chmod 644 "$NGINX_SSL_DIR/cert.pem"
chmod 644 "$NGINX_SSL_DIR/fullchain.pem"
chmod 644 "$NGINX_SSL_DIR/chain.pem"
chown -R pazpaz:pazpaz "$NGINX_SSL_DIR"

# Clean up
rm -f "$NGINX_SSL_DIR/nginx-req.pem" "$NGINX_SSL_DIR/nginx-openssl.cnf"

echo "✅ nginx SSL certificates generated"
ls -lh "$NGINX_SSL_DIR"/*.pem
echo ""

# Step 2: Backup current nginx.conf
echo "[2/5] Backing up current nginx.conf..."
if [ -f "nginx/nginx.conf" ]; then
    cp -p "nginx/nginx.conf" "nginx/nginx.conf.backup-$(date +%Y%m%d-%H%M%S)"
    echo "✅ Backup created"
else
    echo "⚠️  nginx.conf not found, will use default"
fi
echo ""

# Step 3: Update nginx.conf to use self-signed certificates
echo "[3/5] Updating nginx.conf to use self-signed certificates..."

cat > nginx/nginx.conf << 'NGINX_EOF'
# Production Nginx Configuration for PazPaz
# HIPAA-compliant reverse proxy with self-signed SSL certificates

user nginx;
worker_processes auto;
pid /var/run/nginx.pid;
error_log /var/log/nginx/error.log warn;

events {
    worker_connections 1024;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Security headers (applied to both HTTP and HTTPS)
    server_tokens off;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;

    # HTTP server - redirect to HTTPS
    server {
        listen 80;
        listen [::]:80;
        server_name pazpaz.health www.pazpaz.health;

        # Redirect all HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server with self-signed certificates
    server {
        listen 443 ssl;
        listen [::]:443 ssl;
        server_name pazpaz.health www.pazpaz.health;

        # SSL certificates (self-signed, signed by PazPaz CA)
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_trusted_certificate /etc/nginx/ssl/chain.pem;

        # SSL configuration (HIPAA-compliant)
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;
        ssl_stapling off;  # Disabled for self-signed certs
        ssl_stapling_verify off;  # Disabled for self-signed certs

        # HSTS header (only on HTTPS)
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # CSP header
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self' wss: ws:; frame-ancestors 'none'; base-uri 'self'; form-action 'self';" always;

        # Root and index for frontend
        root /usr/share/nginx/html;
        index index.html;

        # Backend API proxy
        location /api/ {
            proxy_pass http://api:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port $server_port;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;

            # Buffering
            proxy_buffering off;
            proxy_request_buffering off;
        }

        # WebSocket proxy
        location /ws/ {
            proxy_pass http://api:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket timeouts
            proxy_read_timeout 86400;
            proxy_send_timeout 86400;
        }

        # Frontend SPA routing
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
NGINX_EOF

echo "✅ nginx.conf updated for self-signed certificates"
echo ""

# Step 4: Restart nginx
echo "[4/5] Restarting nginx with new configuration..."
docker compose -f docker-compose.prod.yml --env-file .env.production restart nginx
echo "⏳ Waiting 10 seconds for nginx to start..."
sleep 10
echo ""

# Step 5: Verify nginx is running
echo "[5/5] Verifying nginx status..."
echo ""
docker compose -f docker-compose.prod.yml --env-file .env.production ps nginx
echo ""

# Check nginx logs for errors
echo "Checking nginx logs (last 30 lines)..."
echo "================================================================"
docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail=30 nginx
echo "================================================================"
echo ""

echo "✅ nginx SSL configuration complete!"
echo ""
echo "Certificate details:"
openssl x509 -in "$NGINX_SSL_DIR/cert.pem" -noout -subject -dates -ext subjectAltName
echo ""
echo "Next steps:"
echo "1. Test HTTP redirect: curl -I http://pazpaz.health"
echo "2. Test HTTPS access: curl -k https://pazpaz.health/health"
echo "3. Import CA certificate to browser for trusted access:"
echo "   - Download: /opt/pazpaz/backend/certs/ca-cert.pem"
echo "   - Import to browser's certificate authorities"
echo "4. Later: Replace with Let's Encrypt for production (certbot)"
echo ""
