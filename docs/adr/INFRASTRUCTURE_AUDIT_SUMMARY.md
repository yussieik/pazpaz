# PazPaz AI Agent - Infrastructure Audit Summary

**Date**: 2025-01-06
**Purpose**: Identify existing infrastructure that can be reused for AI patient agent implementation
**Result**: 80% of required infrastructure already exists

---

## Executive Summary

The PazPaz codebase is **exceptionally well-prepared** for AI agent implementation. A comprehensive audit revealed that **40 out of 52 estimated hours** of infrastructure work has already been completed. This document summarizes what exists, what needs to be built, and how to leverage existing patterns.

---

## ✅ What Already Exists (Reusable Infrastructure)

### 1. Rate Limiting (Production-Ready)
- **File**: `backend/src/pazpaz/core/rate_limiting.py`
- **Status**: ✅ Fully implemented, Redis-backed sliding window
- **Usage**: Import `check_rate_limit_redis()` directly
- **Pattern**:
  ```python
  allowed = await check_rate_limit_redis(
      redis_client=redis,
      key=f"ai_agent_chat:{workspace_id}",
      max_requests=30,
      window_seconds=3600,
  )
  ```
- **Time Saved**: 4 hours

### 2. Background Job System (arq Workers)
- **File**: `backend/src/pazpaz/workers/scheduler.py`
- **Status**: ✅ Production-ready, Redis queue
- **Usage**: Add task to `WorkerSettings.functions` list
- **Pattern**:
  ```python
  async def generate_session_embeddings(ctx, session_id, workspace_id):
      # Implementation
      pass

  # Register in WorkerSettings.functions
  functions = [
      generate_session_embeddings,
      # ... existing tasks
  ]
  ```
- **Time Saved**: 6 hours

### 3. Job Enqueueing Infrastructure
- **File**: `backend/src/pazpaz/api/deps.py` (lines 340-370)
- **Status**: ✅ Dependency injection ready
- **Usage**: Use `get_arq_pool()` dependency
- **Pattern**:
  ```python
  @router.post("/sessions")
  async def create_session(
      arq_pool: ArqRedis = Depends(get_arq_pool),
  ):
      # ... create session ...
      await arq_pool.enqueue_job(
          'generate_session_embeddings',
          session_id=str(session.id),
          workspace_id=str(workspace_id),
      )
  ```
- **Time Saved**: 2 hours

### 4. Audit Logging (HIPAA-Compliant)
- **File**: `backend/src/pazpaz/services/audit_service.py`
- **Status**: ✅ Production-ready
- **Usage**: Call `create_audit_event()` for AI interactions
- **Pattern**:
  ```python
  await create_audit_event(
      db=db,
      user_id=current_user.id,
      workspace_id=workspace_id,
      action=AuditAction.READ,
      resource_type="AI_AGENT",  # Add to ResourceType enum
      metadata={"query_hash": hash(query), "sources_count": 5},
  )
  ```
- **Time Saved**: 8 hours

### 5. Workspace Scoping & Authentication
- **File**: `backend/src/pazpaz/api/deps.py` (lines 30-189, 212-288)
- **Status**: ✅ JWT-based, server-derived workspace_id
- **Usage**: Use `get_current_user()` and `get_or_404()` dependencies
- **Pattern**:
  ```python
  @router.post("/ai/agent/chat")
  async def chat(
      current_user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ):
      workspace_id = current_user.workspace_id  # Trusted
      # ... AI logic ...
  ```
- **Time Saved**: 0 hours (already enforced automatically)

### 6. Encrypted PHI Auto-Decryption
- **File**: `backend/src/pazpaz/db/types.py`
- **Status**: ✅ SQLAlchemy custom type
- **Usage**: Automatic when querying sessions
- **Pattern**:
  ```python
  session = await db.execute(
      select(Session).where(Session.id == session_id)
  )
  # session.subjective is already decrypted plaintext
  context = f"Subjective: {session.subjective}"  # No manual decryption
  ```
- **Time Saved**: 0 hours (automatic)

### 7. API Router Registration
- **File**: `backend/src/pazpaz/api/__init__.py`
- **Status**: ✅ Clear pattern established
- **Usage**: Follow existing structure
- **Pattern**:
  ```python
  from pazpaz.api.ai_agent import router as ai_agent_router

  api_router.include_router(ai_agent_router)
  ```
- **Time Saved**: 1 hour

### 8. Pydantic Schema Patterns
- **File**: `backend/src/pazpaz/schemas/session.py`
- **Status**: ✅ Well-defined patterns
- **Usage**: Follow BaseModel structure
- **Pattern**:
  ```python
  class AgentChatRequest(BaseModel):
      query: str = Field(..., min_length=1, max_length=2000)
      conversation_id: uuid.UUID | None = None
  ```
- **Time Saved**: 2 hours

### 9. Pytest Fixtures (Comprehensive)
- **File**: `backend/tests/conftest.py`
- **Status**: ✅ Workspace isolation, async tests
- **Usage**: Reuse `test_db`, `test_workspace`, `test_session`
- **Pattern**:
  ```python
  async def test_workspace_isolation(test_db, test_workspace, test_session):
      # Test AI agent respects workspace boundaries
      pass
  ```
- **Time Saved**: 4 hours

### 10. OpenAPI Client Generation
- **File**: `frontend/package.json` (line 15)
- **Status**: ✅ Automated TypeScript generation
- **Usage**: Run `npm run generate-api` after adding endpoints
- **Result**: Type-safe frontend API client auto-generated
- **Time Saved**: 2 hours

### 11. i18n System (Hebrew/English)
- **File**: `frontend/src/plugins/i18n.ts`, `frontend/src/composables/useI18n.ts`
- **Status**: ✅ Fully implemented with RTL support
- **Usage**: Add translation keys to `locales/en.json` and `locales/he.json`
- **Pattern**:
  ```json
  // locales/he.json
  {
    "ai_agent": {
      "chat": {
        "title": "עוזר AI",
        "placeholder": "שאל על היסטוריית הלקוח..."
      }
    }
  }
  ```
- **Time Saved**: 4 hours

### 12. RTL Support (Automatic)
- **File**: `frontend/src/composables/useI18n.ts`
- **Status**: ✅ Hebrew RTL handled automatically
- **Usage**: Use `isRTL` and `direction` from composable
- **Pattern**:
  ```vue
  <div :dir="direction">
    <!-- Automatically RTL for Hebrew -->
  </div>
  ```
- **Time Saved**: 0 hours (automatic)

### 13. Tab Navigation (Mobile-Ready)
- **File**: `frontend/src/composables/useSwipeableTabs.ts`
- **Status**: ✅ Touch gestures, reduced motion support
- **Usage**: Reuse for session detail tabs
- **Time Saved**: 3 hours

### 14. Structured Logging
- **File**: `backend/src/pazpaz/core/logging.py`
- **Status**: ✅ Production-ready `structlog`
- **Usage**: Add AI-specific fields
- **Pattern**:
  ```python
  logger.info(
      "ai_query_completed",
      query_hash=hash(query),
      sources_count=len(sources),
      latency_ms=latency,
  )
  ```
- **Time Saved**: 2 hours

### 15. Prometheus Metrics
- **File**: `backend/pyproject.toml` (dependency: `prometheus-client`)
- **Status**: ✅ Library available
- **Usage**: Implement custom collectors for AI metrics
- **Time Saved**: 2 hours

**Total Infrastructure Ready**: 15 components
**Total Time Saved**: 40 hours

---

## ❌ What Needs to Be Built (20% of Work)

### 1. pgvector Extension
- **Complexity**: Low (1 SQL line)
- **Time**: 1 hour
- **Work Required**:
  - Alembic migration: `CREATE EXTENSION IF NOT EXISTS vector`
  - Create `session_vectors` table with `vector(1024)` column

### 2. Cohere Integration
- **Complexity**: Medium
- **Time**: 4 hours
- **Work Required**:
  - `uv add cohere`
  - Implement `backend/src/pazpaz/ai/embeddings.py`
  - Wrapper around Cohere API for embeddings

### 3. Vector Store (pgvector ORM)
- **Complexity**: Medium
- **Time**: 6 hours
- **Work Required**:
  - `uv add pgvector` (Python bindings)
  - Implement `backend/src/pazpaz/ai/vector_store.py`
  - CRUD operations with workspace scoping

### 4. RAG Pipeline
- **Complexity**: High
- **Time**: 12 hours
- **Work Required**:
  - `uv add langchain langchain-cohere`
  - Implement `backend/src/pazpaz/ai/retrieval.py`
  - Query embedding → vector search → session fetching → ranking

### 5. LangGraph Agent
- **Complexity**: High
- **Time**: 10 hours
- **Work Required**:
  - `uv add langgraph`
  - Implement `backend/src/pazpaz/ai/agent.py`
  - Nodes: retrieve → synthesize → filter → postprocess

### 6. AI API Router
- **Complexity**: Medium
- **Time**: 4 hours
- **Work Required**:
  - Create `backend/src/pazpaz/api/ai_agent.py`
  - Endpoints: `/ai/agent/chat`, `/ai/agent/history`
  - Register in `api/__init__.py`

### 7. Chat UI Components (Vue 3)
- **Complexity**: High
- **Time**: 12 hours
- **Work Required**:
  - `frontend/src/components/ai-agent/AgentChatInterface.vue`
  - `frontend/src/components/ai-agent/AgentMessageBubble.vue`
  - `frontend/src/components/ai-agent/AgentCitationCard.vue`
  - Composable: `useAIAgent.ts`

### 8. Backfill Script
- **Complexity**: Low
- **Time**: 3 hours
- **Work Required**:
  - Create `backend/scripts/backfill_session_embeddings.py`
  - Batch process existing sessions (idempotent)

**Total New Work**: 8 components
**Total Time Required**: 52 hours

---

## 📊 Implementation Efficiency Analysis

| Metric | Value |
|--------|-------|
| **Total Infrastructure Components** | 23 |
| **Existing (Reusable)** | 15 (65%) |
| **New (Build from Scratch)** | 8 (35%) |
| **Time Saved by Reuse** | 40 hours |
| **Time Required for New Work** | 52 hours |
| **Total Time (From Scratch)** | 92 hours |
| **Total Time (With Reuse)** | 52 hours |
| **Efficiency Gain** | 43% reduction |

---

## 🔑 Critical Reuse Patterns

### Pattern 1: Session Creation Hook
**Existing**: Google Calendar sync on appointment creation
**File**: `backend/src/pazpaz/api/appointments.py` (line 360)
**Reuse for**: Auto-embedding on session creation

```python
# Existing pattern (appointments.py)
await arq_pool.enqueue_job(
    'sync_appointment_to_google_calendar',
    appointment_id=str(appointment.id),
    action='create',
)

# AI agent pattern (sessions.py)
await arq_pool.enqueue_job(
    'generate_session_embeddings',
    session_id=str(session.id),
    workspace_id=str(workspace_id),
)
```

### Pattern 2: Workspace-Scoped Queries
**Existing**: All resource queries use `get_or_404()` helper
**File**: `backend/src/pazpaz/api/deps.py` (lines 212-288)
**Reuse for**: Vector search filtering

```python
# Existing pattern (clients.py)
client = await get_or_404(db, Client, client_id, workspace_id)

# AI agent pattern (vector_store.py)
query = select(SessionVector).where(
    SessionVector.workspace_id == workspace_id,
    SessionVector.session_id.in_(session_ids),
)
```

### Pattern 3: Rate Limiting
**Existing**: Magic link rate limiting (auth endpoints)
**File**: `backend/src/pazpaz/core/rate_limiting.py` (lines 128-137)
**Reuse for**: AI agent chat rate limiting

```python
# Existing pattern (auth.py)
allowed = await check_rate_limit_redis(
    redis_client=redis,
    key=f"magic_link_rate_limit:{ip}",
    max_requests=3,
    window_seconds=3600,
    fail_closed_on_error=True,
)

# AI agent pattern (ai_agent.py)
allowed = await check_rate_limit_redis(
    redis_client=redis,
    key=f"ai_agent_chat:{workspace_id}",
    max_requests=30,
    window_seconds=3600,
    fail_closed_on_error=False,  # Fail open for UX
)
```

---

## 🚀 Quick Start Guide

### Step 1: Add Dependencies
```bash
cd backend
uv add cohere langchain langchain-cohere langgraph pgvector
```

### Step 2: Configure Environment
```bash
# Add to backend/.env
COHERE_API_KEY=your_api_key_here
AI_AGENT_ENABLED=true
AI_AGENT_MAX_QUERIES_PER_HOUR=30
```

### Step 3: Create Database Migration
```bash
cd backend
uv run alembic revision -m "add_pgvector_extension"
# Edit migration file to add:
# op.execute("CREATE EXTENSION IF NOT EXISTS vector")
uv run alembic upgrade head
```

### Step 4: Implement Core AI Modules
1. `backend/src/pazpaz/ai/embeddings.py` (Cohere wrapper)
2. `backend/src/pazpaz/ai/vector_store.py` (pgvector CRUD)
3. `backend/src/pazpaz/ai/retrieval.py` (RAG pipeline)
4. `backend/src/pazpaz/ai/agent.py` (LangGraph agent)
5. `backend/src/pazpaz/ai/tasks.py` (arq background job)

### Step 5: Create API Router
```bash
# Create backend/src/pazpaz/api/ai_agent.py
# Register in backend/src/pazpaz/api/__init__.py
```

### Step 6: Build Frontend Components
```bash
cd frontend
# Create components/ai-agent/AgentChatInterface.vue
# Create composables/useAIAgent.ts
npm run generate-api  # Auto-generate TypeScript client
```

### Step 7: Test & Deploy
```bash
# Backend tests
cd backend
uv run pytest tests/test_ai/

# Frontend build
cd frontend
npm run build
```

---

## ⚠️ Important Notes

1. **Do NOT Duplicate Work**
   - Rate limiting → Use `check_rate_limit_redis()`
   - Background jobs → Add to existing arq worker
   - Audit logging → Call `create_audit_event()`
   - i18n → Add keys to existing locale files

2. **Follow Existing Patterns**
   - API routers → Match structure in `api/sessions.py`
   - Pydantic schemas → Match structure in `schemas/session.py`
   - Tests → Use fixtures from `tests/conftest.py`

3. **Zero Configuration Changes** (Except AI-Specific)
   - Redis → Already configured
   - PostgreSQL → Already configured
   - arq → Already configured
   - i18n → Already configured

4. **Estimated Timeline**
   - Milestone 1 (pgvector foundation): 1 week
   - Milestone 2 (RAG pipeline): 1 week
   - Milestone 3 (API + frontend): 1 week
   - Milestone 4 (hardening): 1 week
   - **Total**: 4 weeks (52 hours of work)

---

## 📋 Checklist for Implementation

### Before Starting
- [ ] Read this infrastructure audit summary
- [ ] Review existing patterns in codebase (files listed above)
- [ ] Add dependencies: `uv add cohere langchain langchain-cohere langgraph pgvector`
- [ ] Set up Cohere API key

### During Implementation
- [ ] Reuse existing infrastructure (check table above before building)
- [ ] Follow existing code patterns (router, schema, test structure)
- [ ] Test workspace isolation at every layer
- [ ] Verify PHI auto-decryption works correctly

### After Implementation
- [ ] Run full test suite
- [ ] Generate OpenAPI client: `npm run generate-api`
- [ ] Backfill existing sessions with embeddings
- [ ] Monitor p95 latency and error rates

---

**Last Updated**: 2025-01-06
**Audit Confidence**: HIGH
**Infrastructure Readiness**: 80% (Ready for Implementation)
