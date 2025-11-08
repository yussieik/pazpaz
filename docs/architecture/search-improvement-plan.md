# Search Improvement Plan

**Status:** Technical Debt - V1 Implementation
**Created:** 2025-11-08
**Owner:** Backend Team

## Current Implementation (V1)

### Overview
The AI agent search uses **semantic search with adaptive thresholds** and **rule-based query expansion**. This is a pragmatic V1 solution that works for ~80% of queries but has limitations.

### Architecture
```
User Query
    ↓
Language Detection
    ↓
Query Expansion (rule-based) ──→ [search_config.py]
    ↓
Adaptive Threshold Tuning ────→ [search_config.py]
    ↓
Vector Search (Cohere Embed v4.0)
    ↓
LLM Synthesis (Cohere Command-R)
```

### Key Files
- **`src/pazpaz/ai/search_config.py`** - Centralized search configuration
  - Similarity thresholds
  - Query classification patterns
  - Expansion triggers
- **`src/pazpaz/ai/query_expansion.py`** - Clinical term expansion logic
- **`src/pazpaz/ai/agent.py`** - Orchestrates search pipeline

### Configuration Parameters

All tuning parameters are centralized in `SearchConfig` dataclass:

```python
@dataclass
class SearchConfig:
    # Thresholds
    default_min_similarity: float = 0.3
    absolute_min_similarity: float = 0.15
    short_query_threshold_reduction: float = 0.10

    # Query classification
    short_query_word_threshold: int = 6
    general_query_patterns: list[str] = [
        "what is", "where is", "how is", "tell me", "explain", "describe"
    ]

    # Query expansion
    expansion_trigger_patterns: list[str] = [
        "treatment", "therapy", "pain", "diagnosis", ...
    ]
    no_expansion_patterns: list[str] = [
        "session", "date", "when", "who"
    ]
```

### Limitations

❌ **Hard-coded threshold tuning**
- Manual adjustment per query pattern
- Brittle, doesn't scale to edge cases
- Requires code changes for each new pattern

❌ **Rule-based query expansion**
- 90s-era NLP approach
- Limited to pre-defined synonym lists
- Doesn't learn from user queries

❌ **Single-stage retrieval**
- No reranking for precision
- False negatives on edge cases (e.g., "where is pain")

❌ **No keyword matching**
- Pure semantic search misses exact matches
- "where is pain" has low similarity despite containing "pain"

### What Works Well

✅ **Semantic search foundation**
- Cohere Embed v4.0 with input_type differentiation
- Separate embeddings per SOAP field
- Cosine similarity retrieval

✅ **RAG architecture**
- Retrieve → Format → Synthesize
- Citation tracking
- Chronological session ordering

✅ **Bilingual support**
- Hebrew and English
- Language detection

## Industry-Standard Solutions

### Option 1: Hybrid Search (Recommended for V2)

**Approach:** Combine semantic search + keyword search (BM25)

```sql
-- PostgreSQL full-text search + pgvector
SELECT *,
  (1 - (embedding <=> query_embedding)) * 0.7 +  -- Semantic (70%)
  ts_rank(text_vector, query_tsquery) * 0.3      -- Keyword (30%)
  AS combined_score
FROM session_vectors
WHERE combined_score > 0.2
ORDER BY combined_score DESC;
```

**Benefits:**
- Handles both semantic and lexical matches
- Fixes "where is pain" issue immediately
- No external API costs
- PostgreSQL native (already using pgvector)

**Effort:** 1-2 weeks
- Add `text_vector` tsvector column to `session_vectors`
- Create GIN index for full-text search
- Update retrieval queries to combine scores
- Tune score weights (0.7 semantic, 0.3 keyword)

**Examples:**
- Elasticsearch Hybrid Search
- Pinecone Sparse-Dense Search
- Weaviate Hybrid Search

---

### Option 2: Two-Stage Retrieval with Reranking

**Approach:** Cast wide net, then rerank with cross-encoder

```python
# Stage 1: Recall (low threshold)
candidates = await vector_search(query, threshold=0.1, limit=50)

# Stage 2: Precision (rerank top-k)
reranked = await cohere.rerank(
    query=query,
    documents=[c.text for c in candidates],
    top_n=5,
    model="rerank-english-v3.0"
)
```

**Benefits:**
- Cross-encoders see query + document together (more accurate)
- No manual threshold tuning needed
- Production-grade solution

**Costs:**
- Cohere Rerank API: $0.002 per 1K searches
- ~$2 per 1M searches (very cheap)

**Effort:** 1 week
- Integrate Cohere Rerank API
- Adjust retrieval to fetch 50 candidates instead of 5
- Remove adaptive threshold logic

**Used By:**
- Cohere (officially recommended for production)
- Anthropic retrieval documentation
- Most modern RAG systems

---

### Option 3: Query Understanding Layer

**Approach:** Use LLM to rewrite query before retrieval

```python
# LLM rewrites query to be more specific
original = "Where is Sarah's pain?"
rewritten = await llm.rewrite(original)
# → "lower back pain location lumbar spine radiating leg"

results = await vector_search(rewritten, threshold=0.3)
```

**Benefits:**
- Handles vague/ambiguous queries
- Can generate multiple query variations
- Improves recall significantly

**Costs:**
- Additional LLM call per query (~$0.01-0.10 per query)

**Effort:** 2-3 weeks
- Design query rewriting prompts
- Add LLM call before retrieval
- Handle multi-query generation
- Tune expansion vs. specificity trade-off

**Used By:**
- Perplexity.ai
- You.com
- Advanced RAG systems

---

### Option 4: Learned Thresholds (ML-Based)

**Approach:** Train model to predict optimal threshold per query

```python
# Train on labeled data (query → optimal threshold)
threshold = threshold_model.predict(
    query_length=len(query),
    query_type="location",
    embedding_variance=np.var(query_embedding)
)
```

**Benefits:**
- No manual tuning needed
- Adapts to query characteristics

**Drawbacks:**
- Requires labeled training data
- More complex to maintain

**Effort:** 4-6 weeks
- Collect labeled data (query, optimal threshold)
- Train model (gradient boosting, neural net)
- Deploy inference endpoint
- Monitor performance

---

## Recommended Migration Path

### Phase 1: V2 (Post-Launch, 1-2 weeks)
**Implement Hybrid Search (Option 1)**

**Why:**
- Biggest bang for buck
- Fixes most edge cases
- No external API dependencies
- Uses PostgreSQL features we already have

**Tasks:**
1. Add `text_content` and `text_vector` columns to `session_vectors`
2. Create GIN index for full-text search
3. Update `retrieve_relevant_sessions()` to combine semantic + keyword scores
4. Tune score weights (start with 0.7/0.3, adjust based on metrics)
5. A/B test against V1 baseline

**Metrics to track:**
- False negative rate (queries with no results)
- False positive rate (irrelevant results)
- User satisfaction (manual review of 100 random queries)

---

### Phase 2: V3 (2-3 months, optional)
**Add Cohere Rerank API (Option 2)**

**Why:**
- Further improves precision
- Removes remaining edge cases
- Industry-standard production solution

**Tasks:**
1. Integrate Cohere Rerank API
2. Fetch 50 candidates instead of 5
3. Rerank to top 5
4. Monitor API costs and latency
5. A/B test against V2 hybrid search

---

### Phase 3: V4 (6+ months, research)
**Explore Query Understanding (Option 3)**

**Why:**
- Handle complex/ambiguous queries
- Support conversational follow-ups
- Improve recall for difficult cases

**Tasks:**
1. Prototype LLM query rewriting
2. Measure impact on recall/precision
3. Evaluate cost/latency trade-offs
4. Decide if ROI justifies complexity

---

## Success Metrics

### V1 Baseline (Current)
- False negative rate: ~20% (1/5 test queries failed)
- False positive rate: <5% (no irrelevant results observed)
- Median latency: 10.5s (LLM synthesis dominates)

### V2 Targets (Hybrid Search)
- False negative rate: <10%
- False positive rate: <5%
- Median latency: <12s (slight increase due to BM25 computation)

### V3 Targets (+ Reranking)
- False negative rate: <5%
- False positive rate: <3%
- Median latency: <15s (reranking adds ~2-3s)

---

## Testing Strategy

### Before Migration
1. Collect 100 representative queries from beta users
2. Label expected results (ground truth)
3. Establish V1 baseline metrics

### During Migration
1. A/B test V2 vs V1 (50/50 split)
2. Monitor metrics daily
3. Collect user feedback
4. Roll back if metrics degrade

### After Migration
1. Compare V2 vs V1 metrics
2. Document improvements
3. Share results with team
4. Plan next iteration (V3)

---

## Cost Analysis

### V1 (Current)
- Embedding API: $0.0001 per query (Cohere Embed v4.0)
- LLM API: $0.015 per query (Cohere Command-R)
- **Total: ~$0.015 per query**

### V2 (Hybrid Search)
- Same as V1 (no additional API costs)
- **Total: ~$0.015 per query**

### V3 (+ Reranking)
- Embedding API: $0.0001 per query
- Rerank API: $0.002 per query (Cohere Rerank)
- LLM API: $0.015 per query
- **Total: ~$0.017 per query** (13% increase)

### V4 (+ Query Understanding)
- Query rewriting: $0.003 per query (Cohere Command-R-Light)
- Embedding API: $0.0001 per query
- Rerank API: $0.002 per query
- LLM API: $0.015 per query
- **Total: ~$0.020 per query** (33% increase)

---

## Decision Log

### 2025-11-08: Created V1 with Adaptive Thresholds
**Decision:** Implement rule-based adaptive thresholds and query expansion for V1

**Reasoning:**
- Need working search for launch
- Don't want to over-engineer before validating product-market fit
- Adaptive thresholds solve 80% of cases
- Can migrate to hybrid search post-launch

**Trade-offs:**
- Technical debt: Manual tuning required
- Brittleness: Edge cases require code changes
- Maintainability: Hard-coded rules in `search_config.py`

**Next Review:** Post-launch (after 1000+ real user queries)

---

## References

### Industry Examples
- [Cohere Rerank Documentation](https://docs.cohere.com/docs/reranking)
- [Pinecone Hybrid Search](https://docs.pinecone.io/guides/data/hybrid-search)
- [Elasticsearch Hybrid Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html#approximate-knn-hybrid)
- [Weaviate Hybrid Search](https://weaviate.io/developers/weaviate/search/hybrid)

### Academic Papers
- [Dense Passage Retrieval (DPR)](https://arxiv.org/abs/2004.04906) - Facebook AI, 2020
- [ColBERT](https://arxiv.org/abs/2004.12832) - Stanford, 2020
- [BEIR Benchmark](https://arxiv.org/abs/2104.08663) - Retrieval benchmark, 2021

### Blog Posts
- [Building RAG at Scale (Anthropic)](https://www.anthropic.com/index/retrieval-at-scale)
- [Improving RAG with Hybrid Search (Cohere)](https://txt.cohere.com/hybrid-search/)
- [PostgreSQL Full-Text Search Guide](https://www.postgresql.org/docs/current/textsearch.html)
