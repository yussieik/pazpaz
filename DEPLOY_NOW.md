# 🚀 Deploy AI Agent to Production - Quick Guide

**Server:** 5.161.241.81
**User:** pazpaz
**Password:** Cluster1!

---

## Copy & Paste These Commands

### Step 1: Connect to Production
```bash
ssh pazpaz@5.161.241.81
# Enter password: Cluster1!
```

### Step 2: Navigate and Create Backup
```bash
cd /opt/pazpaz

# Create backup with timestamp
BACKUP_DIR="/opt/pazpaz/backups/ai-deployment-$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR
echo "Backup directory: $BACKUP_DIR"

# Backup database
docker exec pazpaz-db pg_dump -U pazpaz -F c -b -v -f /tmp/db_backup.dump pazpaz
docker cp pazpaz-db:/tmp/db_backup.dump $BACKUP_DIR/
docker exec pazpaz-db rm /tmp/db_backup.dump

echo "✅ Backup complete: $BACKUP_DIR/db_backup.dump"
```

### Step 3: Pull Latest Code
```bash
git pull origin main
echo "✅ Code updated"
```

### Step 4: Add AI Configuration to .env.production
```bash
# Check if AI config already exists
if grep -q "^COHERE_API_KEY=" .env.production 2>/dev/null; then
    echo "✅ AI config already exists"
else
    echo "Adding AI configuration..."
    cat >> .env.production << 'EOF'

# ============================================
# AI Agent Configuration
# ============================================
COHERE_API_KEY=32LXdDIoANDKxNPoMl1eYCamxZUf54wOYPBFEgnf
COHERE_EMBED_MODEL=embed-v4.0
COHERE_CHAT_MODEL=command-a-03-2025
AI_EMBEDDING_PROVIDER=cohere
AI_CHAT_PROVIDER=cohere
AI_AGENT_ENABLED=true
AI_AGENT_MAX_QUERIES_PER_HOUR=30
AI_AGENT_MAX_CONTEXT_TOKENS=8000
AI_AGENT_MAX_OUTPUT_TOKENS=4000
EOF
    echo "✅ AI config added"
fi
```

### Step 5: Run Database Migrations
```bash
echo "Running migrations (this installs pgvector)..."
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -m alembic upgrade head"
echo "✅ Migrations complete"
```

### Step 6: Verify pgvector Installation
```bash
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```
**Expected output:** `vector | 0.x.x`

### Step 7: Verify Vector Tables Created
```bash
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\dt *vectors"
```
**Expected output:** `session_vectors` and `client_vectors` tables

### Step 8: Restart Services
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production restart
echo "✅ Services restarted"
```

### Step 9: Wait for Services to Start
```bash
sleep 15
echo "Waiting for services to become healthy..."
```

### Step 10: Health Check
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T api curl -s http://localhost:8000/health
```

### Step 11: Check for Errors
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail=100 api | grep -i error || echo "✅ No errors found"
```

---

## 🎉 Deployment Complete!

Your AI Agent is now live in production!

### Test It:
1. Go to your production domain in browser
2. Navigate to a client detail page
3. You should see the AI chat interface

### Monitor Logs:
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f api
```

---

## 🛟 Rollback (If Needed)

If something went wrong, restore from backup:

```bash
# Find your backup (use the timestamp from Step 2)
ls -lt /opt/pazpaz/backups/

# Restore (replace YYYYMMDD-HHMMSS with your backup timestamp)
cd /opt/pazpaz/backups/ai-deployment-YYYYMMDD-HHMMSS
docker cp db_backup.dump pazpaz-db:/tmp/
docker exec pazpaz-db pg_restore -U pazpaz -d pazpaz -c /tmp/db_backup.dump
docker compose -f docker-compose.prod.yml --env-file .env.production restart
```

---

## 📊 What Changed:

- ✅ pgvector extension installed
- ✅ 2 new tables: `session_vectors`, `client_vectors`
- ✅ New API endpoint: `/api/v1/ai/agent/chat`
- ✅ AI chat widget in client detail pages
- ✅ Automatic embedding generation for sessions

**Estimated time:** 5-10 minutes
**Downtime:** ~30 seconds (during restart)
