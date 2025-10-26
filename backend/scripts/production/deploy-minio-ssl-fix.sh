#!/bin/bash
# Deploy MinIO SSL Certificate Fix (commit 15a33f3)
# Adds S3_CA_CERT_PATH configuration and restarts API with updated image

set -e

cd /opt/pazpaz

echo "======================================================================="
echo "  Deploying MinIO SSL Certificate Fix"
echo "======================================================================="
echo "Commit: 15a33f3"
echo "Fix: Configure boto3 to trust MinIO self-signed CA certificates"
echo ""

# Step 1: Pull updated backend image
echo "[1/5] Pulling updated backend image from GitHub Container Registry..."
docker compose --env-file .env.production pull api
echo "✅ Backend image updated"
echo ""

# Step 2: Add S3_CA_CERT_PATH to .env.production
echo "[2/5] Adding S3_CA_CERT_PATH to .env.production..."
if grep -q "^S3_CA_CERT_PATH=" .env.production; then
    echo "⚠️  S3_CA_CERT_PATH already exists, updating..."
    sed -i 's|^S3_CA_CERT_PATH=.*|S3_CA_CERT_PATH=/app/certs/ca-cert.pem|' .env.production
else
    echo "" >> .env.production
    echo "# MinIO SSL Certificate Configuration (self-signed CA)" >> .env.production
    echo "S3_CA_CERT_PATH=/app/certs/ca-cert.pem" >> .env.production
fi
echo "✅ S3_CA_CERT_PATH configured"
echo ""

# Step 3: Verify CA certificate exists
echo "[3/5] Verifying CA certificate exists..."
if [ ! -f "/opt/pazpaz/backend/certs/ca-cert.pem" ]; then
    echo "❌ ERROR: CA certificate not found at /opt/pazpaz/backend/certs/ca-cert.pem"
    exit 1
fi
echo "✅ CA certificate verified: $(ls -lh /opt/pazpaz/backend/certs/ca-cert.pem)"
echo ""

# Step 4: Restart API service with updated configuration
echo "[4/5] Restarting API service with new configuration..."
docker compose --env-file .env.production up -d --force-recreate api
echo "⏳ Waiting 10 seconds for API to start..."
sleep 10
echo ""

# Step 5: Check service status and logs
echo "[5/5] Verifying deployment..."
echo ""
echo "Service status:"
docker compose --env-file .env.production ps api
echo ""

echo "Checking for SSL warnings in API logs (last 50 lines)..."
echo "================================================================"
docker compose --env-file .env.production logs --tail=50 api | grep -i "ssl\|certificate\|minio\|s3" || echo "No SSL-related messages in recent logs"
echo "================================================================"
echo ""

echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Monitor API logs for any SSL warnings: docker compose --env-file .env.production logs -f api"
echo "2. Test file upload to verify MinIO SSL works: curl -X POST https://pazpaz.health/api/v1/..."
echo "3. Verify all services encrypted (run HIPAA compliance check)"
echo ""
