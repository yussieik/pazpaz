#!/bin/bash
#
# PazPaz AI Agent Production Deployment Script
# Server: 5.161.241.81 (Hetzner)
# User: pazpaz
#
# This script automates the deployment of the AI Agent feature to production
#

set -e  # Exit on any error

echo "🚀 PazPaz AI Agent Production Deployment"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Production server details
PROD_SERVER="5.161.241.81"
PROD_USER="pazpaz"
PROD_DIR="/opt/pazpaz"

echo -e "${YELLOW}Step 1: Connecting to production server...${NC}"
ssh ${PROD_USER}@${PROD_SERVER} << 'ENDSSH'

set -e
cd /opt/pazpaz

echo ""
echo "✅ Connected to production server"
echo ""

# Step 2: Create backup
echo "📦 Step 2: Creating database backup..."
BACKUP_DIR="/opt/pazpaz/backups/ai-deployment-$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR
echo "Backup directory: $BACKUP_DIR"

docker exec pazpaz-db pg_dump -U pazpaz -F c -b -v -f /tmp/db_backup.dump pazpaz
docker cp pazpaz-db:/tmp/db_backup.dump $BACKUP_DIR/
docker exec pazpaz-db rm /tmp/db_backup.dump

echo "✅ Database backup created: $BACKUP_DIR/db_backup.dump"
echo ""

# Step 3: Pull latest code
echo "📥 Step 3: Pulling latest code from GitHub..."
git fetch origin
git pull origin main
echo "✅ Code updated to latest version"
echo ""

# Step 4: Check if AI config exists in .env.production
echo "🔧 Step 4: Checking environment configuration..."
if grep -q "^COHERE_API_KEY=" .env.production 2>/dev/null; then
    echo "✅ AI configuration already exists in .env.production"
else
    echo "➕ Adding AI configuration to .env.production..."
    cat >> .env.production << 'EOF'

# ============================================
# AI Agent Configuration (Added: $(date))
# ============================================

# Cohere API Configuration
COHERE_API_KEY=32LXdDIoANDKxNPoMl1eYCamxZUf54wOYPBFEgnf
COHERE_EMBED_MODEL=embed-v4.0
COHERE_CHAT_MODEL=command-a-03-2025

# AI Provider Selection
AI_EMBEDDING_PROVIDER=cohere
AI_CHAT_PROVIDER=cohere

# AI Agent Configuration
AI_AGENT_ENABLED=true
AI_AGENT_MAX_QUERIES_PER_HOUR=30
AI_AGENT_MAX_CONTEXT_TOKENS=8000
AI_AGENT_MAX_OUTPUT_TOKENS=4000
EOF
    echo "✅ AI configuration added to .env.production"
fi
echo ""

# Step 5: Verify PostgreSQL version
echo "🔍 Step 5: Verifying PostgreSQL version..."
PG_VERSION=$(docker exec pazpaz-db psql -U pazpaz -d pazpaz -t -c "SELECT version();" | head -1)
echo "PostgreSQL Version: $PG_VERSION"
if echo "$PG_VERSION" | grep -q "PostgreSQL 16"; then
    echo "✅ PostgreSQL 16 detected (pgvector compatible)"
else
    echo "⚠️  WARNING: PostgreSQL version may not support pgvector"
fi
echo ""

# Step 6: Run migrations
echo "🗄️  Step 6: Running database migrations..."
echo "This will install pgvector extension and create vector tables..."
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -m alembic upgrade head"
echo "✅ Migrations completed successfully"
echo ""

# Step 7: Verify pgvector extension
echo "✅ Step 7: Verifying pgvector installation..."
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
echo ""

# Step 8: Verify vector tables
echo "📊 Step 8: Verifying vector tables..."
echo "Checking session_vectors table..."
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\d session_vectors" | head -20
echo ""
echo "Checking client_vectors table..."
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\d client_vectors" | head -20
echo ""

# Step 9: Restart services
echo "🔄 Step 9: Restarting Docker services..."
docker compose -f docker-compose.prod.yml --env-file .env.production restart
echo "✅ Services restarted"
echo ""

# Wait for services to be healthy
echo "⏳ Waiting for services to become healthy..."
sleep 10

# Step 10: Health checks
echo "🏥 Step 10: Running health checks..."
echo "API health check:"
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T api curl -s http://localhost:8000/health | python3 -m json.tool || echo "Health check endpoint returned non-JSON response"
echo ""

# Step 11: Check logs for errors
echo "📋 Step 11: Checking recent logs for errors..."
docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail=50 api | grep -i error || echo "✅ No errors in recent logs"
echo ""

# Final summary
echo ""
echo "================================================"
echo "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "================================================"
echo ""
echo "Backup location: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "1. Test AI chat in browser at your domain"
echo "2. Monitor logs: docker compose -f docker-compose.prod.yml --env-file .env.production logs -f api"
echo "3. Check metrics at /health endpoint"
echo ""
echo "To rollback if needed:"
echo "  cd $BACKUP_DIR"
echo "  docker cp db_backup.dump pazpaz-db:/tmp/"
echo "  docker exec pazpaz-db pg_restore -U pazpaz -d pazpaz -c /tmp/db_backup.dump"
echo ""

ENDSSH

echo ""
echo -e "${GREEN}✅ Deployment script completed!${NC}"
echo ""
echo "The AI Agent feature is now live in production!"
echo ""
