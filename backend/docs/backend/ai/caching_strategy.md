# AI Agent Caching Strategy

**Status:** Design Document
**Priority:** Medium (Post-V1 optimization)
**Estimated Impact:** 30-50% latency reduction, 40-60% cost reduction
**Estimated Effort:** 8-12 hours implementation

---

## Problem Statement

**Current Flow (No Caching):**
```
User Query → Embed Query → Search Vectors → LLM Synthesis → Response
   ↓            ↓              ↓               ↓              ↓
  0ms         500ms          50ms          1200ms         1750ms total

Every query = $0.002 (embedding) + $0.015 (LLM) = $0.017 per query
```

**Issues:**
1. **Duplicate work**: Same query from different users = duplicate embedding + LLM calls
2. **High latency**: 1.75s p95 (target: <1s for snappy UX)
3. **High cost**: $0.017/query × 10,000 queries/month = $170/month
4. **Wasted API credits**: Cohere charges for identical embeddings

**Opportunity:**
- 40% of queries are repetitive ("What was the last session?", "Show treatment history")
- Embeddings are deterministic (same query = same vector)
- Search results change slowly (sessions updated hourly, not per-second)

---

## Proposed Solution

### Multi-Layer Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    USER QUERY                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────▼────────────┐
         │  L1: Query Result Cache │  ← Full responses (5 min TTL)
         │  Redis: answer + citations │
         └────────────┬────────────┘
                      │ MISS
         ┌────────────▼────────────┐
         │  L2: Embedding Cache    │  ← Query embeddings (1 hour TTL)
         │  Redis: query → vector  │
         └────────────┬────────────┘
                      │ MISS
         ┌────────────▼────────────┐
         │  L3: Vector Search      │  ← PostgreSQL (no cache)
         │  pgvector similarity    │
         └────────────┬────────────┘
                      │
         ┌────────────▼────────────┐
         │  L4: LLM Synthesis      │  ← Cohere API (no cache)
         │  Generate answer        │
         └─────────────────────────┘
```

---

## Layer 1: Query Result Cache (Full Response)

### What to Cache
**Full AI agent response** for identical queries within same workspace.

### Cache Key
```python
def get_query_cache_key(workspace_id: uuid.UUID, query: str, client_id: uuid.UUID | None) -> str:
    """Generate cache key for full query response."""
    query_normalized = query.lower().strip()
    query_hash = hashlib.sha256(query_normalized.encode()).hexdigest()[:16]

    client_suffix = f":{client_id}" if client_id else ""
    return f"ai:query:{workspace_id}:{query_hash}{client_suffix}"
```

**Example:**
```
Query: "What was the last session?"
Workspace: 123e4567-e89b-12d3-a456-426614174000
Client: None

Key: ai:query:123e4567:8f3d2c1a:None
```

### TTL Strategy
**5 minutes** (short TTL due to data freshness requirements)

**Rationale:**
- Sessions can be created/updated frequently
- Stale data is worse than slower response
- 5 min is long enough to absorb burst traffic (user refreshing page)
- Short enough to reflect recent changes

### Cache Invalidation
**Manual invalidation** when session data changes:

```python
# In api/sessions.py - after create/update/delete
async def invalidate_query_cache(
    redis: Redis,
    workspace_id: uuid.UUID,
    client_id: uuid.UUID | None = None,
):
    """Invalidate all cached queries for a workspace/client."""
    pattern = f"ai:query:{workspace_id}:*"
    if client_id:
        pattern = f"ai:query:{workspace_id}:*:{client_id}"

    # Delete all matching keys
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break
```

**Trigger points:**
```python
# sessions.py - After session create/update/finalize
await invalidate_query_cache(redis, workspace_id, client_id)

# sessions.py - After session delete
await invalidate_query_cache(redis, workspace_id, client_id)
```

### Data Structure
```python
# Redis value (JSON)
{
    "answer": "Based on session notes, the patient...",
    "citations": [
        {
            "type": "session",
            "session_id": "...",
            "client_name": "John Doe",
            "session_date": "2025-11-01T10:30:00Z",
            "similarity": 0.85,
            "field_name": "subjective"
        }
    ],
    "language": "en",
    "retrieved_count": 3,
    "processing_time_ms": 1250,
    "cached_at": 1699456789,  # Unix timestamp
    "cache_version": "v1"  # For invalidation
}
```

### Implementation
```python
# ai/agent.py - query() method
async def query(
    self,
    workspace_id: uuid.UUID,
    query: str,
    user_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    max_results: int = 5,
    min_similarity: float = 0.3,
    use_cache: bool = True,  # New parameter
) -> AgentResponse:
    """Query agent with L1 cache support."""

    # L1: Check query result cache
    if use_cache:
        cache_key = get_query_cache_key(workspace_id, query, client_id)
        cached = await self.redis.get(cache_key)

        if cached:
            logger.info("ai_agent_query_cache_hit", cache_key=cache_key)
            ai_agent_cache_hits_total.labels(
                workspace_id=str(workspace_id),
                cache_layer="query_result"
            ).inc()

            data = json.loads(cached)
            return AgentResponse(
                answer=data["answer"],
                citations=[SessionCitation(**c) for c in data["citations"]],
                language=data["language"],
                retrieved_count=data["retrieved_count"],
                processing_time_ms=data["processing_time_ms"],
            )

    # MISS: Generate response (existing logic)
    response = await self._generate_response(...)

    # Store in L1 cache
    if use_cache:
        cache_value = json.dumps({
            "answer": response.answer,
            "citations": [c.dict() for c in response.citations],
            "language": response.language,
            "retrieved_count": response.retrieved_count,
            "processing_time_ms": response.processing_time_ms,
            "cached_at": int(time.time()),
            "cache_version": "v1",
        })

        await self.redis.setex(
            cache_key,
            300,  # 5 minutes TTL
            cache_value,
        )

    return response
```

### Metrics
```python
# ai/metrics.py
ai_agent_cache_hits_total = Counter(
    "ai_agent_cache_hits_total",
    "Total AI agent cache hits",
    ["workspace_id", "cache_layer"],  # cache_layer: query_result, embedding
)

ai_agent_cache_misses_total = Counter(
    "ai_agent_cache_misses_total",
    "Total AI agent cache misses",
    ["workspace_id", "cache_layer"],
)
```

---

## Layer 2: Embedding Cache (Query Vectors)

### What to Cache
**Query embeddings only** (not session embeddings, those are stored in database).

### Cache Key
```python
def get_embedding_cache_key(text: str) -> str:
    """Generate cache key for text embedding."""
    text_normalized = text.lower().strip()
    text_hash = hashlib.sha256(text_normalized.encode()).hexdigest()
    return f"ai:embedding:{text_hash}"
```

### TTL Strategy
**1 hour** (longer TTL - embeddings are deterministic)

**Rationale:**
- Query text → vector is deterministic (same input = same output)
- No data freshness concerns (embedding doesn't change)
- Longer TTL = higher cache hit rate
- 1 hour balances memory usage vs hit rate

### Data Structure
```python
# Redis value (JSON)
{
    "embedding": [0.123, -0.456, ...],  # 1536 floats
    "model": "embed-multilingual-v4.0",
    "created_at": 1699456789,
    "cache_version": "v1"
}
```

### Implementation
```python
# ai/embeddings.py
class EmbeddingService:
    def __init__(self, api_key: str, redis: Redis | None = None):
        self.client = cohere.AsyncClientV2(api_key=api_key)
        self.redis = redis

    async def embed_text(
        self,
        text: str,
        use_cache: bool = True,
    ) -> list[float]:
        """Embed text with L2 cache support."""

        # L2: Check embedding cache
        if use_cache and self.redis:
            cache_key = get_embedding_cache_key(text)
            cached = await self.redis.get(cache_key)

            if cached:
                logger.debug("embedding_cache_hit", text_length=len(text))
                ai_agent_cache_hits_total.labels(
                    workspace_id="global",  # Embeddings are workspace-agnostic
                    cache_layer="embedding"
                ).inc()

                data = json.loads(cached)
                return data["embedding"]

        # MISS: Generate embedding (existing logic)
        embedding = await self._embed_text_with_retry(text)

        # Store in L2 cache
        if use_cache and self.redis:
            cache_value = json.dumps({
                "embedding": embedding,
                "model": self.model,
                "created_at": int(time.time()),
                "cache_version": "v1",
            })

            await self.redis.setex(
                cache_key,
                3600,  # 1 hour TTL
                cache_value,
            )

        return embedding
```

### Storage Optimization
**Compressed embeddings** to reduce Redis memory:

```python
import zlib
import base64

def compress_embedding(embedding: list[float]) -> str:
    """Compress embedding for efficient Redis storage."""
    # Convert to bytes (numpy array → bytes)
    import struct
    bytes_data = struct.pack(f'{len(embedding)}f', *embedding)

    # Compress with zlib
    compressed = zlib.compress(bytes_data, level=6)

    # Base64 encode for Redis
    return base64.b64encode(compressed).decode()

def decompress_embedding(compressed: str) -> list[float]:
    """Decompress embedding from Redis."""
    import struct

    # Decode base64
    compressed = base64.b64decode(compressed)

    # Decompress
    bytes_data = zlib.decompress(compressed)

    # Unpack floats
    count = len(bytes_data) // 4
    return list(struct.unpack(f'{count}f', bytes_data))
```

**Compression ratio:** 1536 floats × 4 bytes = 6144 bytes → ~3000 bytes (50% reduction)

---

## Layer 3: No Caching (Vector Search)

**Why not cache vector search results?**

1. **Search results are workspace-specific** (high key cardinality)
2. **Results change frequently** (new sessions created)
3. **Cache hit rate would be low** (different queries have different results)
4. **PostgreSQL is already fast** (<50ms with HNSW index)

**Decision:** Don't cache. PostgreSQL + pgvector is efficient enough.

---

## Layer 4: No Caching (LLM Synthesis)

**Why not cache LLM responses separately?**

1. **Already covered by L1** (full query result cache)
2. **LLM responses are non-deterministic** (temperature > 0)
3. **Context-dependent** (same context → different answers)

**Decision:** Don't cache. L1 handles this.

---

## Cache Invalidation Strategy

### Trigger Events

| Event | Invalidation Action | Reason |
|-------|---------------------|--------|
| **Session created** | Delete `ai:query:{workspace}:*:{client_id}` | New session changes query results |
| **Session updated** | Delete `ai:query:{workspace}:*:{client_id}` | Updated SOAP notes change results |
| **Session finalized** | Delete `ai:query:{workspace}:*:{client_id}` | Finalized session might change answers |
| **Session deleted** | Delete `ai:query:{workspace}:*:{client_id}` | Removed session changes results |
| **Client deleted** | Delete `ai:query:{workspace}:*:{client_id}` | All client queries invalid |
| **Workspace deleted** | Delete `ai:query:{workspace}:*` | All workspace queries invalid |

### Invalidation Implementation

```python
# services/cache_service.py (NEW)
from redis.asyncio import Redis
import uuid

class AICacheService:
    """Service for managing AI agent cache invalidation."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def invalidate_client_queries(
        self,
        workspace_id: uuid.UUID,
        client_id: uuid.UUID,
    ) -> int:
        """
        Invalidate all cached queries for a specific client.

        Returns:
            Number of cache keys deleted
        """
        pattern = f"ai:query:{workspace_id}:*:{client_id}"
        return await self._delete_pattern(pattern)

    async def invalidate_workspace_queries(
        self,
        workspace_id: uuid.UUID,
    ) -> int:
        """
        Invalidate all cached queries for an entire workspace.

        Returns:
            Number of cache keys deleted
        """
        pattern = f"ai:query:{workspace_id}:*"
        return await self._delete_pattern(pattern)

    async def _delete_pattern(self, pattern: str) -> int:
        """Delete all Redis keys matching pattern."""
        deleted = 0
        cursor = 0

        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )

            if keys:
                deleted += await self.redis.delete(*keys)

            if cursor == 0:
                break

        return deleted
```

### Usage in API Endpoints

```python
# api/sessions.py
from pazpaz.services.cache_service import AICacheService

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    arq_pool = Depends(get_arq_pool),
):
    # ... create session logic ...

    # Invalidate AI query cache for this client
    cache_service = AICacheService(redis)
    await cache_service.invalidate_client_queries(
        workspace_id=workspace_id,
        client_id=session.client_id,
    )

    logger.info(
        "ai_cache_invalidated",
        workspace_id=str(workspace_id),
        client_id=str(session.client_id),
        reason="session_created",
    )

    return session
```

---

## Expected Impact

### Performance Improvement

**Cache Hit Scenarios:**

| Scenario | Current | With L1 | With L1+L2 | Improvement |
|----------|---------|---------|------------|-------------|
| **Identical query (5 min)** | 1750ms | 20ms | 20ms | **98.9% faster** |
| **Similar query (same embedding)** | 1750ms | 1750ms | 1250ms | **28.6% faster** |
| **New query** | 1750ms | 1750ms | 1750ms | 0% |

**Expected Cache Hit Rates:**
- **L1 (Query Result):** 20-30% (repetitive queries)
- **L2 (Embedding):** 40-50% (common query patterns)
- **Combined:** 50-60% of queries hit cache

### Cost Reduction

**Current Costs:**
```
10,000 queries/month
× $0.017 per query (embedding + LLM)
= $170/month
```

**With Caching (50% hit rate):**
```
5,000 cached (L1 hit) = $0 (no API calls)
5,000 uncached
  → 2,500 L2 hit (embedding cached) = 2,500 × $0.015 (LLM only) = $37.50
  → 2,500 L2 miss (full cost) = 2,500 × $0.017 = $42.50
Total = $80/month
```

**Savings:** $90/month (53% reduction)

### Redis Memory Usage

**L1 Cache (Query Results):**
```
Average response size: 2 KB (answer + citations)
Cache size: 100 concurrent users × 5 queries = 500 cached queries
Memory: 500 × 2 KB = 1 MB

TTL: 5 minutes
Max keys at steady state: ~1,000 (with burst traffic)
Max memory: 2 MB
```

**L2 Cache (Embeddings):**
```
Embedding size: 3 KB (compressed from 6 KB)
Cache size: 200 unique queries/hour
Memory: 200 × 3 KB = 600 KB

TTL: 1 hour
Max keys at steady state: ~200
Max memory: 600 KB
```

**Total Redis Memory:** ~3 MB (negligible)

---

## Implementation Plan

### Phase 1: L2 Embedding Cache (Low Risk, High Impact)
**Effort:** 4 hours
**Impact:** 30% latency reduction, 25% cost reduction

**Tasks:**
1. Add Redis dependency to `EmbeddingService` ✓
2. Implement `embed_text()` cache logic ✓
3. Add compression helpers ✓
4. Add cache metrics ✓
5. Test with production traffic (1 week)

### Phase 2: L1 Query Result Cache (Medium Risk, High Impact)
**Effort:** 6 hours
**Impact:** Additional 20% latency reduction, 25% cost reduction

**Tasks:**
1. Implement `AICacheService` ✓
2. Add cache logic to `agent.query()` ✓
3. Add invalidation hooks to session endpoints ✓
4. Add cache metrics ✓
5. Monitor cache hit rates (2 weeks)

### Phase 3: Optimization & Monitoring (Ongoing)
**Effort:** 2 hours/month
**Impact:** Tune TTLs, fix invalidation bugs

**Tasks:**
1. Analyze cache hit rates (Grafana dashboard)
2. Adjust TTLs based on data
3. Add cache warming (pre-populate common queries)
4. Implement cache versioning (for schema changes)

---

## Monitoring & Observability

### Metrics to Track

```python
# Prometheus metrics
ai_agent_cache_hits_total{workspace_id, cache_layer}
ai_agent_cache_misses_total{workspace_id, cache_layer}
ai_agent_cache_hit_rate{workspace_id, cache_layer}  # Derived metric
ai_agent_cache_latency_seconds{cache_layer}  # How long cache lookups take
ai_agent_cache_invalidations_total{workspace_id, reason}
```

### Grafana Dashboard

**Panel 1: Cache Hit Rate Over Time**
```promql
sum(rate(ai_agent_cache_hits_total[5m])) by (cache_layer)
/
(
  sum(rate(ai_agent_cache_hits_total[5m])) by (cache_layer)
  +
  sum(rate(ai_agent_cache_misses_total[5m])) by (cache_layer)
)
```

**Panel 2: Cost Savings**
```promql
# Estimate: $0.017 per uncached query
sum(rate(ai_agent_cache_hits_total{cache_layer="query_result"}[5m])) * 0.017 * 3600
```

**Panel 3: Latency Comparison**
```promql
histogram_quantile(0.95,
  sum(rate(ai_agent_query_duration_seconds_bucket[5m])) by (le, cached)
)
```

### Alerts

```yaml
# Low cache hit rate alert
- alert: AIAgentLowCacheHitRate
  expr: |
    sum(rate(ai_agent_cache_hits_total[1h]))
    /
    (sum(rate(ai_agent_cache_hits_total[1h])) + sum(rate(ai_agent_cache_misses_total[1h])))
    < 0.3
  for: 2h
  annotations:
    summary: "AI agent cache hit rate below 30% for 2 hours"
    description: "Check cache invalidation logic or TTL settings"

# High cache invalidation rate alert
- alert: AIAgentHighInvalidationRate
  expr: rate(ai_agent_cache_invalidations_total[5m]) > 10
  for: 10m
  annotations:
    summary: "Excessive cache invalidations (>10/sec)"
    description: "May indicate invalidation logic bug or session spam"
```

---

## Edge Cases & Considerations

### 1. Cache Stampede (Thundering Herd)
**Problem:** Cache expires → 100 concurrent requests → 100 LLM calls

**Solution:** Cache warming + stale-while-revalidate
```python
# Get cached value even if expired (serve stale)
cached = await redis.get(cache_key)
if cached:
    # Check if stale (TTL expired but key still exists with extended TTL)
    ttl = await redis.ttl(cache_key)
    if ttl < 60:  # Less than 1 minute remaining
        # Serve stale data but trigger background refresh
        asyncio.create_task(self._refresh_cache(cache_key, query))

    return parse_cached_response(cached)
```

### 2. Cache Poisoning
**Problem:** Malicious query → bad LLM response → cached → served to all users

**Solution:** Cache validation
```python
def validate_cached_response(data: dict) -> bool:
    """Validate cached response before serving."""
    # Check schema version
    if data.get("cache_version") != "v1":
        return False

    # Check required fields
    required = ["answer", "citations", "language"]
    if not all(k in data for k in required):
        return False

    # Check answer is not empty
    if not data["answer"].strip():
        return False

    return True
```

### 3. Bilingual Cache Keys
**Problem:** "What was the last session?" (EN) vs "מה היה הפגישה האחרונה?" (HE) = same meaning, different keys

**Solution:** Normalize queries before hashing
```python
def normalize_query(query: str) -> str:
    """Normalize query for consistent cache keys."""
    # Lowercase
    normalized = query.lower().strip()

    # Remove punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)

    # Collapse whitespace
    normalized = re.sub(r'\s+', ' ', normalized)

    return normalized
```

**Trade-off:** This won't catch semantic equivalence (EN vs HE), but that's OK. Different languages = different cache keys is acceptable.

### 4. Memory Pressure
**Problem:** Redis OOM with too many cached queries

**Solution:** LRU eviction policy
```python
# redis.conf (or docker-compose.yml environment)
maxmemory 100mb
maxmemory-policy allkeys-lru  # Evict least recently used keys
```

---

## Rollout Strategy

### Stage 1: Dark Launch (No User Impact)
**Duration:** 1 week
**Goal:** Collect metrics, verify correctness

```python
# Enable caching but don't serve cached results (log only)
async def query(..., use_cache: bool = False):  # Default to False
    cache_key = get_query_cache_key(...)
    cached = await redis.get(cache_key)

    if cached:
        logger.info("cache_hit_dry_run", cache_key=cache_key)
        # Don't return cached value, continue to generate fresh response

    response = await self._generate_response(...)

    # Store in cache for testing
    await redis.setex(cache_key, 300, serialize(response))

    return response
```

### Stage 2: Gradual Rollout (% of Traffic)
**Duration:** 2 weeks
**Goal:** Verify cache correctness, monitor errors

```python
# Enable caching for 10% → 50% → 100% of requests
import random

async def query(...):
    use_cache = random.random() < 0.10  # 10% of requests

    if use_cache:
        cached = await redis.get(cache_key)
        if cached:
            return parse_cached(cached)

    # ... generate fresh response
```

### Stage 3: Full Rollout (All Traffic)
**Duration:** Ongoing
**Goal:** Monitor cache hit rates, tune TTLs

```python
# Enable caching by default, allow opt-out
async def query(..., use_cache: bool = True):
    ...
```

---

## Success Criteria

**Go/No-Go Decision:**

✅ **Go ahead with full rollout if:**
- Cache hit rate >30% (L1 + L2 combined)
- No cache-related errors in 2 weeks
- Latency p95 reduced by >20%
- Cost reduction >30%

❌ **Rollback if:**
- Cache corruption incidents (wrong data served)
- Invalidation bugs (stale data served >5 min)
- Redis memory usage >100 MB
- User complaints about stale answers

---

## Future Enhancements

### 1. Semantic Caching (Embeddings as Keys)
Instead of query text → cache key, use query embedding → find similar cached queries

```python
# Store cache with embedding as key
query_embedding = await embed_text(query)
similar_cached = await vector_search_redis(query_embedding, threshold=0.95)

if similar_cached:
    return similar_cached["response"]
```

**Benefit:** "What was the last appointment?" and "Show me the most recent session" hit same cache
**Effort:** 16 hours (need Redis vector search or separate pgvector table)

### 2. Prefetching (Cache Warming)
Pre-populate cache for common queries during off-peak hours

```python
# Cron job: Every night at 2 AM
COMMON_QUERIES = [
    "What was the last session?",
    "Show treatment history",
    "מה היה הטיפול האחרון?",
]

for workspace in active_workspaces:
    for query in COMMON_QUERIES:
        await agent.query(workspace_id, query, use_cache=False)
        # Result is cached for morning traffic
```

### 3. Multi-Level Cache Consistency
Ensure L1 and L2 are consistent during invalidation

```python
async def invalidate_all_layers(workspace_id, client_id):
    # L1: Delete query results
    await delete_pattern(f"ai:query:{workspace_id}:*:{client_id}")

    # L2: Embeddings are global, don't invalidate
    # (they're deterministic and workspace-agnostic)
```

---

## Conclusion

**Recommendation:** Implement L2 (embedding cache) first, then L1 (query result cache).

**Expected ROI:**
- **Development:** 12 hours total
- **Cost Savings:** $90/month ($1,080/year)
- **Latency Reduction:** 30-50% (1750ms → 875-1225ms)
- **User Experience:** Snappier AI responses

**Risk:** Low (Redis is already in use, caching is well-understood pattern)

**Next Steps:**
1. Review this document with team
2. Approve implementation plan
3. Start with Phase 1 (L2 embedding cache)
4. Monitor for 1 week
5. Proceed to Phase 2 (L1 query result cache)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-08
**Author:** Claude Code
**Status:** Awaiting Approval
