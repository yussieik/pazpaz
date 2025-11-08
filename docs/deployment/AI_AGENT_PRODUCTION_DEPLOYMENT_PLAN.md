# PazPaz AI Agent Production Deployment Plan

**Date:** November 8, 2025
**Feature:** AI Clinical Documentation Assistant with Vector Search
**Risk Level:** HIGH (Database migrations + new pgvector extension)
**Estimated Downtime:** 5-10 minutes (during migration)

---

## 🚨 CRITICAL DEPLOYMENT CHECKLIST

### Pre-Deployment Requirements
- [ ] Production server access verified (SSH pazpaz@5.161.241.81)
- [ ] Database backup strategy confirmed
- [ ] Cohere API key ready for production
- [ ] Rollback procedure understood
- [ ] 30-minute deployment window scheduled

---

## 📋 DEPLOYMENT OVERVIEW

### What's Being Deployed

#### 1. **Database Changes (HIGH RISK)**
- **pgvector extension** - PostgreSQL extension for vector similarity search
- **session_vectors table** - Stores 1536-dimensional embeddings for SOAP notes
- **client_vectors table** - Stores embeddings for client medical history
- **3 Alembic migrations** requiring sequential execution

#### 2. **Backend Changes**
- New AI agent API endpoint (`/api/v1/ai-agent/`)
- Embedding generation service (Cohere embed-v4.0)
- Vector search implementation (cosine similarity)
- Background task workers for embedding generation
- Cache service for query optimization

#### 3. **Frontend Changes**
- AI chat interface component
- Markdown rendering enhancements
- Localization updates (English/Hebrew)

#### 4. **Configuration Changes**
- New environment variables for Cohere API
- AI agent feature flags and rate limits
- Vector dimension upgrade (1024 → 1536)

---

## 🔒 SECURITY CONSIDERATIONS

### HIPAA Compliance
- ✅ Embeddings are workspace-scoped (multi-tenant isolation)
- ✅ PHI remains encrypted at rest (Fernet encryption)
- ✅ Cohere API calls use TLS 1.2+
- ✅ No raw PHI sent to Cohere (only encrypted text)
- ✅ Audit logging for all AI queries

### API Key Security
- ⚠️ **MVP Mode**: Cohere API key will be in production .env temporarily
- 📅 **Post-MVP**: Move to AWS Secrets Manager
- 🔑 **Current Key Type**: Trial key for development/testing
- 💳 **Production Ready**: Upgrade to paid key when live with patients

---

## 📦 STEP-BY-STEP DEPLOYMENT PROCESS

### Phase 1: Local Preparation (15 minutes)

#### Step 1.1: Review Changes
```bash
# Review all uncommitted changes
git status
git diff --stat

# Verify migration files
ls -la backend/alembic/versions/*.py | tail -3
```

#### Step 1.2: Commit Changes in Logical Groups

**IMPORTANT**: Commit order matters for clean history and potential rollback.

```bash
# 1. First commit: Database migrations
git add backend/alembic/versions/154da4b93b1d_add_pgvector_extension_and_session_.py
git add backend/alembic/versions/5407ac8bbc2b_upgrade_embeddings_to_1536_dimensions_.py
git add backend/alembic/versions/fd96a368a54b_add_client_vectors_table_for_ai_agent.py
git commit -m "feat(db): add pgvector extension and vector tables for AI agent

- Install pgvector extension for vector similarity search
- Add session_vectors table for SOAP note embeddings (1536 dimensions)
- Add client_vectors table for medical history embeddings
- Create HNSW indexes for efficient cosine similarity search
- Implement workspace isolation for multi-tenant security

BREAKING CHANGE: Requires pgvector extension in PostgreSQL 16"

# 2. Second commit: Backend AI implementation
git add backend/src/pazpaz/ai/
git add backend/src/pazpaz/api/ai_agent.py
git add backend/src/pazpaz/models/client_vector.py
git add backend/src/pazpaz/models/session_vector.py
git add backend/src/pazpaz/schemas/ai_agent.py
git add backend/src/pazpaz/services/cache_service.py
git add backend/src/pazpaz/workers/ai_tasks.py
git add backend/src/pazpaz/api/__init__.py
git add backend/src/pazpaz/models/__init__.py
git add backend/src/pazpaz/core/config.py
git add backend/src/pazpaz/workers/scheduler.py
git add backend/pyproject.toml
git add backend/uv.lock
git add backend/.env.example
git commit -m "feat(backend): implement AI clinical documentation assistant

- Add Cohere integration for embeddings (embed-v4.0) and chat (command-a-03-2025)
- Implement RAG pipeline with vector search for contextual responses
- Add background tasks for automatic embedding generation
- Implement caching service for query optimization
- Add rate limiting (30 queries/hour) and token limits
- Configure AI agent feature flags for opt-in deployment

Security: Workspace-scoped queries, PHI encryption maintained"

# 3. Third commit: Frontend AI interface
git add frontend/src/components/ai-agent/
git add frontend/src/composables/useAIAgent.ts
git add frontend/src/api/client.ts
git add frontend/src/views/ClientDetailView.vue
git add frontend/src/locales/en.json
git add frontend/src/locales/he.json
git commit -m "feat(frontend): add AI agent chat interface

- Create floating chat widget with markdown support
- Add real-time streaming responses
- Implement bilingual support (English/Hebrew)
- Add loading states and error handling
- Integrate with backend AI agent API"

# 4. Fourth commit: Documentation and scripts
git add backend/docs/
git add backend/scripts/backfill_client_embeddings.py
git add backend/scripts/generate_session_embeddings_manual.py
git add backend/tests/manual/
git add backend/tests/unit/ai/
git add backend/tests/unit/services/test_cache_service.py
git add docs/adr/
git add docs/architecture/search-improvement-plan.md
git add docs/*.md
git add docker-compose.yml
git commit -m "docs: add AI agent architecture documentation and utilities

- Document AI agent architecture and extensibility
- Add migration scripts for embedding backfill
- Include comprehensive test coverage
- Add ADR for vector search decision
- Update docker-compose for development"

# 5. Push all commits
git push origin main
```

---

### Phase 2: Pre-Deployment Verification (10 minutes)

#### Step 2.1: SSH to Production Server
```bash
# Connect to production
ssh pazpaz@5.161.241.81

# Navigate to deployment directory
cd /opt/pazpaz
```

#### Step 2.2: Verify Current State
```bash
# Check Docker services
docker compose -f docker-compose.prod.yml --env-file .env.production ps

# Verify PostgreSQL version supports pgvector
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT version();"
# Expected: PostgreSQL 16.x

# Check current migrations
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -m alembic current"

# Check disk space
df -h /opt/pazpaz
# Ensure at least 10GB free
```

#### Step 2.3: Create Pre-Deployment Backup
```bash
# Create backup directory with timestamp
BACKUP_DIR="/opt/pazpaz/backups/ai-deployment-$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup database (compressed format)
docker exec pazpaz-db pg_dump -Fc -U pazpaz -d pazpaz > $BACKUP_DIR/database.dump
echo "Database backup size: $(du -h $BACKUP_DIR/database.dump | cut -f1)"

# Backup current .env.production
cp .env.production $BACKUP_DIR/.env.production.backup

# Backup docker-compose.prod.yml
cp docker-compose.prod.yml $BACKUP_DIR/docker-compose.prod.yml.backup

# Create restore script
cat > $BACKUP_DIR/restore.sh << 'EOF'
#!/bin/bash
# Emergency restore script
echo "Restoring database..."
docker exec -i pazpaz-db pg_restore -U pazpaz -d pazpaz --clean --if-exists < database.dump
echo "Restoring configuration..."
cp .env.production.backup /opt/pazpaz/.env.production
cp docker-compose.prod.yml.backup /opt/pazpaz/docker-compose.prod.yml
echo "Restarting services..."
cd /opt/pazpaz
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
echo "Restore complete"
EOF
chmod +x $BACKUP_DIR/restore.sh

echo "Backup complete: $BACKUP_DIR"
```

---

### Phase 3: Configuration Update (5 minutes)

#### Step 3.1: Update Production Environment Variables
```bash
# Edit production environment file
nano .env.production

# Add the following AI configuration (at the end of file):
```

Add these lines to `.env.production`:
```bash
# AI Patient Agent (Cohere API)
# MVP Mode: Using trial key initially, will upgrade to production key
COHERE_API_KEY=YOUR_ACTUAL_COHERE_API_KEY_HERE  # Get from https://dashboard.cohere.com
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
```

#### Step 3.2: Verify Configuration
```bash
# Check that all required variables are set
grep -E "COHERE_API_KEY|AI_AGENT_ENABLED" .env.production

# Ensure no syntax errors in .env file
docker compose -f docker-compose.prod.yml --env-file .env.production config > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Configuration valid"
else
    echo "❌ Configuration error - check .env.production"
fi
```

---

### Phase 4: Deployment Execution (10-15 minutes)

#### Step 4.1: Pull Latest Code
```bash
# Pull latest changes
git pull origin main

# Verify migrations are present
ls -la backend/alembic/versions/*.py | tail -3
```

#### Step 4.2: Pull Docker Images
```bash
# Pull latest backend image (includes AI features)
docker compose -f docker-compose.prod.yml --env-file .env.production pull api

# Pull latest frontend image (includes chat UI)
docker compose -f docker-compose.prod.yml --env-file .env.production pull frontend
```

#### Step 4.3: Run Database Migrations (CRITICAL)

**⚠️ WARNING**: This is the most critical step. Migrations will:
1. Install pgvector extension
2. Create new vector tables
3. Delete any existing embeddings (dimension change)

```bash
# Run migrations with safety checks
./scripts/migrate.sh upgrade

# If migrate.sh is not available, run manually:
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -m alembic upgrade head"

# Verify migrations completed
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -m alembic current"
# Should show: fd96a368a54b (head)
```

#### Step 4.4: Restart Services
```bash
# Restart services with new configuration
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Monitor startup logs
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
# Press Ctrl+C after services stabilize
```

#### Step 4.5: Verify Health
```bash
# Check all services are healthy
docker compose -f docker-compose.prod.yml --env-file .env.production ps

# Test API health endpoint
curl -s https://pazpaz.health/api/v1/health | jq .

# Test AI agent endpoint (should return 401 without auth)
curl -s https://pazpaz.health/api/v1/ai-agent/health
```

---

### Phase 5: Post-Deployment Verification (10 minutes)

#### Step 5.1: Database Verification
```bash
# Verify pgvector extension installed
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\dx" | grep vector
# Expected: vector | 0.8.0 | public | vector data type and ivfflat and hnsw access methods

# Verify new tables created
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\dt" | grep vector
# Expected: session_vectors and client_vectors tables

# Check indexes
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\di" | grep vector
# Expected: Multiple indexes including HNSW indexes
```

#### Step 5.2: Application Testing
1. **Login to PazPaz**: https://pazpaz.health
2. **Navigate to a client detail page**
3. **Look for AI chat widget** (bottom-right corner)
4. **Test basic query**: "What is this patient's diagnosis?"
5. **Verify response** indicates no session data available (expected for new deployment)

#### Step 5.3: Generate Initial Embeddings (Optional)
```bash
# Generate embeddings for existing sessions (if any)
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python scripts/generate_session_embeddings_manual.py"

# Generate embeddings for client medical history
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python scripts/backfill_client_embeddings.py"
```

#### Step 5.4: Monitor Logs
```bash
# Check for errors in API logs
docker logs pazpaz-api --tail 100 | grep -i error

# Monitor AI agent queries
docker logs pazpaz-api -f | grep "ai_agent"
```

---

## 🔄 ROLLBACK PROCEDURE

If deployment fails or critical issues are discovered:

### Immediate Rollback (< 5 minutes)
```bash
# 1. Stop services
cd /opt/pazpaz
docker compose -f docker-compose.prod.yml --env-file .env.production down

# 2. Restore from backup
cd /opt/pazpaz/backups/ai-deployment-[TIMESTAMP]
./restore.sh

# 3. Verify restoration
docker compose -f docker-compose.prod.yml --env-file .env.production ps
curl -s https://pazpaz.health/api/v1/health | jq .
```

### Migration Rollback (if needed)
```bash
# Downgrade migrations in reverse order
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -m alembic downgrade -3"

# Verify rollback
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -m alembic current"
```

---

## 📊 SUCCESS CRITERIA

Deployment is successful when:

- [ ] All Docker containers are healthy
- [ ] API health check returns 200 OK
- [ ] pgvector extension is installed
- [ ] Vector tables (session_vectors, client_vectors) exist
- [ ] AI chat widget appears in client detail view
- [ ] No critical errors in logs
- [ ] Response time remains < 150ms for non-AI endpoints

---

## 🚨 KNOWN ISSUES & MITIGATIONS

### Issue 1: pgvector Extension Not Available
**Error**: `ERROR: could not open extension control file "vector.control"`
**Solution**: PostgreSQL 16 Alpine image should include pgvector. If not:
```bash
docker exec pazpaz-db apk add --no-cache postgresql16-pgvector
docker restart pazpaz-db
```

### Issue 2: Migration Timeout
**Error**: Migration takes > 5 minutes
**Solution**: Run with extended timeout:
```bash
./scripts/migrate.sh --timeout 600 upgrade
```

### Issue 3: Cohere API Key Invalid
**Error**: `401 Unauthorized` from Cohere
**Solution**: Verify API key at https://dashboard.cohere.com and update .env.production

### Issue 4: Out of Memory During Embedding Generation
**Error**: Container killed (OOM)
**Solution**: Process embeddings in smaller batches:
```bash
docker exec pazpaz-api bash -c "cd /app && PYTHONPATH=/app/src uv run --no-sync python -c 'from pazpaz.workers.ai_tasks import generate_embeddings_batch; generate_embeddings_batch(batch_size=10)'"
```

---

## 📝 POST-DEPLOYMENT TASKS

### Immediate (Day 1)
- [ ] Monitor AI agent usage and performance
- [ ] Check Cohere API usage dashboard
- [ ] Review error logs for any issues
- [ ] Document any deployment variations

### Week 1
- [ ] Generate embeddings for all historical sessions
- [ ] Gather user feedback on AI agent
- [ ] Monitor vector search performance
- [ ] Plan production API key upgrade if needed

### Month 1
- [ ] Review AI agent query patterns
- [ ] Optimize embedding generation schedule
- [ ] Consider index tuning for vector search
- [ ] Evaluate need for dedicated vector database

---

## 📞 SUPPORT CONTACTS

**Deployment Issues**:
- Server Access: SSH pazpaz@5.161.241.81
- Root Password: Cluster1! (if needed)

**API Issues**:
- Cohere Dashboard: https://dashboard.cohere.com
- Cohere Support: https://cohere.com/support

**Monitoring**:
- Production URL: https://pazpaz.health
- Health Check: https://pazpaz.health/api/v1/health
- Container Registry: https://github.com/yussieik?tab=packages

---

## 🎯 DEPLOYMENT CHECKLIST

### Pre-Deployment
- [ ] Backup database
- [ ] Backup configuration
- [ ] Verify disk space
- [ ] Schedule maintenance window
- [ ] Prepare Cohere API key

### During Deployment
- [ ] Pull latest code
- [ ] Update .env.production
- [ ] Run migrations
- [ ] Restart services
- [ ] Monitor logs

### Post-Deployment
- [ ] Verify pgvector extension
- [ ] Test AI chat widget
- [ ] Check health endpoints
- [ ] Monitor performance
- [ ] Document any issues

---

**Last Updated**: November 8, 2025
**Author**: DevOps Infrastructure Specialist
**Status**: Ready for Deployment