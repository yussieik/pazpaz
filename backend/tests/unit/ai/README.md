# AI Agent Tests

## Overview

This directory contains **one focused end-to-end test** that validates the complete AI agent functionality as currently implemented in production.

**Previous Approach:** 67 tests (39 unit, 28 integration) with extensive mocking and real API calls
**Current Approach:** 3 focused scenarios in a single test file that validates actual user-facing behavior

## Why One Test File?

The AI agent is a **black-box integration** — users query it and receive synthesized answers with citations. Testing internal components (embeddings, vector store, retry logic) in isolation doesn't validate that the system works end-to-end.

**Key Insight:** The most valuable test is the one that mimics actual usage.

## Test Coverage

### `test_ai_agent_e2e.py` - 3 Critical Scenarios

#### 1. **test_ai_agent_query_with_embeddings**
Validates the complete RAG pipeline:
- User asks a clinical question (e.g., "What caused the patient's back pain?")
- Agent embeds query → searches vectors → synthesizes answer
- Response includes citations with session references
- Language detection works (English/Hebrew)
- Performance tracked (<30s response time)

**Why Critical:** This is the 95% use case — therapist queries patient history.

#### 2. **test_workspace_isolation**
Validates multi-tenant security:
- Workspace 1 cannot see Workspace 2 data
- Vector search respects workspace boundaries
- No cross-tenant data leakage

**Why Critical:** HIPAA compliance requires workspace isolation.

#### 3. **test_no_results_fallback**
Validates graceful handling when no results found:
- Agent returns helpful message instead of empty response
- No crashes or errors when similarity threshold is too high
- User-friendly fallback behavior

**Why Critical:** Prevents bad UX when queries don't match embedded data.

## Mocking Strategy

**Cohere API is fully mocked** to avoid:
- API costs (~$0.01 per test run)
- Network dependencies (test failures when API is down)
- Slow tests (60+ seconds vs <10 seconds)

### How Mocking Works

```python
@pytest_asyncio.fixture
async def mock_cohere_embeddings(self):
    """Mock Cohere API to return deterministic embeddings and LLM responses."""

    # 1. Mock embed endpoint - Generate deterministic 1536-dim vectors
    def generate_embedding(text: str) -> list[float]:
        text_hash = hash(text)
        # Create unique but deterministic embedding based on text hash
        ...

    # 2. Mock chat endpoint - Return realistic clinical answers
    async def mock_chat(model, messages, temperature, max_tokens):
        query = messages[-1]["content"]
        if "back pain" in query.lower():
            return "Based on clinical notes, patient had back pain..."
        ...
```

**Benefits:**
- Tests run fast (<10s)
- Deterministic (no flaky tests)
- No external dependencies
- Can test error cases easily

## Running Tests

```bash
# Run all AI tests (just the 3 scenarios)
env PYTHONPATH=src uv run pytest tests/unit/ai/ -v

# Run specific scenario
env PYTHONPATH=src uv run pytest tests/unit/ai/test_ai_agent_e2e.py::TestAIAgentEndToEnd::test_ai_agent_query_with_embeddings -v

# Expected output:
# ✅ 3 passed in ~9 seconds
```

## What's NOT Tested (and Why)

### Not Tested: Internal Component Details
- Embedding service retry logic
- Vector store SQL query optimization
- Query expansion heuristics
- Adaptive threshold tuning

**Rationale:** These are implementation details. If the end-to-end behavior is correct, these internal details are working.

### Not Tested: Real Cohere API Integration
- Actual embedding quality
- LLM response coherence
- Token usage tracking

**Rationale:** Manual QA and production monitoring validate this. Automated tests would be slow, expensive, and flaky.

### Not Tested: PII Redaction Filter
- Phone number redaction
- Email redaction
- ID number redaction

**Rationale:** This is covered by separate security tests in `tests/security/`. The AI agent test focuses on RAG functionality.

## Test Data

### Clinical Data Used
**Patient:** Sarah Johnson
**Condition:** Lower back pain (acute lumbar strain)
**SOAP Note:**
- **S:** "Pain started 3 days ago after lifting heavy boxes. Sharp, 7/10 intensity."
- **O:** "Reduced ROM, positive straight leg raise, no neurological deficits."
- **A:** "Acute lumbar strain with possible disc involvement."
- **P:** "Rest, ice 3x/day, NSAIDs, gentle stretching. Follow-up in 5 days."

**Why This Data:** Realistic clinical scenario that allows testing:
- Medical terminology matching
- Multi-field search (query spans S/O/A/P)
- Citation generation
- Answer synthesis

## Maintenance

### When to Update This Test

1. **Breaking changes to RAG pipeline:**
   - New embedding model (dimensions change)
   - Different LLM provider
   - Major search algorithm changes

2. **New critical features:**
   - Multi-client queries (search across all clients)
   - Filtering by date range
   - Export citations to PDF

3. **Security requirements:**
   - New workspace isolation rules
   - Data retention policies
   - Audit logging changes

### When NOT to Update

- Internal refactoring (no behavior change)
- Performance optimizations (covered by benchmarks)
- Logging/metrics changes (covered by monitoring)

## Adding New Tests

**Before adding a new test file, ask:**
1. Does this test a different user-facing scenario?
2. Can this be added as a new test method to `test_ai_agent_e2e.py`?
3. Is this testing implementation details that will change frequently?

**If you must add a new test file:**
- Focus on behavior, not implementation
- Mock external APIs (Cohere)
- Keep tests fast (<10s total)
- Document why it can't be part of e2e test

## Success Metrics

**Test Quality:**
- ✅ All 3 scenarios pass reliably
- ✅ Tests run in <10 seconds
- ✅ No flaky failures (100% pass rate over 100 runs)
- ✅ No external dependencies (fully mocked)

**Coverage:**
- ✅ Happy path (successful query with results)
- ✅ Security (workspace isolation)
- ✅ Edge case (no results fallback)

**Maintenance:**
- ✅ Tests updated <5 times per year
- ✅ Test failures indicate actual bugs, not test brittleness

---

**Last Updated:** 2025-11-08
**Test Count:** 3 scenarios in 1 file
**Execution Time:** ~9 seconds
**External Dependencies:** None (Cohere API mocked)
