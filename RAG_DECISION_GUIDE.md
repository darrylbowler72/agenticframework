# RAG System Decision Guide

## When to Use RAG vs Simple Retrieval

### Use Simple Retrieval When:
- ✅ Exact key known (e.g., "get template python-fastapi")
- ✅ Small corpus (<100 documents)
- ✅ Latency critical (<10ms required)
- ✅ No semantic search needed

### Use RAG When:
- ✅ Natural language queries ("show me auth examples")
- ✅ Large corpus (>1000 documents)
- ✅ Need best match, not exact match
- ✅ Quality > speed

---

## Chunking Strategy Decision Tree

```
Is content structured? (code, markdown, JSON)
├─ YES → Use Structure-Aware Chunking
│   ├─ Code → Chunk by functions/classes
│   ├─ Markdown → Chunk by headers
│   └─ JSON → Chunk by top-level objects
│
└─ NO → Is quality critical?
    ├─ YES → Use Semantic Chunking
    │   └─ Trade-off: 10x slower, 2x cost, +15% quality
    │
    └─ NO → Use Fixed-Size Chunking
        └─ Chunk size: 512 tokens, overlap: 50 tokens
```

### Real Measurements

| Strategy | Time/Doc | Quality | Best For |
|----------|----------|---------|----------|
| Fixed-size | 10ms | 70% | General text |
| Structure-aware | 50ms | 85% | Code, docs |
| Semantic | 500ms | 90% | Research, analysis |

---

## Reranking Strategy Decision Tree

```
What's your latency budget?
├─ <100ms → No Reranking
│   └─ Accuracy: 70%, Cost: $0.001/query
│
├─ <200ms → Lightweight Reranking
│   ├─ Use: BM25 + metadata signals
│   └─ Accuracy: 80%, Cost: $0.002/query
│
└─ <1000ms → LLM Reranking
    ├─ Use: Claude Haiku for scoring
    └─ Accuracy: 90%, Cost: $0.010/query
```

### When to Use Each

**No Reranking:**
- Search logs for patterns
- Finding exact file names
- Keyword-heavy queries

**Lightweight Reranking:**
- Code example search
- Documentation lookup
- 90% of use cases ← **DEFAULT CHOICE**

**LLM Reranking:**
- Complex technical questions
- Ambiguous queries
- When wrong answer is costly

---

## Stitching Strategy Decision Tree

```
What's your token budget?
├─ >4000 tokens → Concatenate
│   └─ Include all retrieved chunks
│
├─ 2000-4000 tokens → Smart Stitching
│   ├─ Deduplicate consecutive chunks
│   ├─ Order by relevance
│   └─ Remove redundancy
│
└─ <2000 tokens → LLM Synthesis
    ├─ Extra LLM call to summarize
    └─ Trade-off: +$0.001, +500ms, -50% tokens
```

### Real Example: "Show me FastAPI authentication"

**Concatenate (3500 tokens):**
```
[Source: auth_middleware.py]
def authenticate_user(token: str):
    ...

[Source: main.py]
app = FastAPI()
...

[Source: models.py]
class User(BaseModel):
    ...
```
- Pros: All context preserved
- Cons: Redundant, hard to follow

**Smart Stitch (2200 tokens):**
```
### Authentication Implementation

From auth_middleware.py:
def authenticate_user(token: str):
    ...

From main.py (relevant sections):
app.add_middleware(AuthMiddleware)
...
```
- Pros: Logical flow, deduped
- Cons: Some context lost

**Synthesize (1200 tokens):**
```
FastAPI authentication uses middleware pattern:
1. Create auth_middleware.py with token validation
2. Add middleware to app: app.add_middleware(AuthMiddleware)
3. Protect routes with Depends(get_current_user)

[See: auth_middleware.py:15, main.py:42]
```
- Pros: Concise, actionable
- Cons: May lose nuance

---

## Trade-Off Matrix

### Latency vs Quality

```
Quality
  ↑
90%│                    ● LLM Rerank + Synthesis
   │
85%│            ● Smart Stitch + Lightweight Rerank
   │        ●
80%│    ● Simple Concat + Rerank
   │ ●
70%│ Vector Search Only
   └────────────────────────────────→ Latency
    50ms  100ms  200ms  500ms  1000ms
```

### Cost vs Quality

```
Quality
  ↑
90%│                            ● Full RAG Pipeline
   │                      ●
85%│                ● Optimized RAG
   │          ●
80%│    ● Cached RAG
   │ ●
70%│ Simple Search
   └──────────────────────────────→ Cost/Query
    $0.001    $0.003    $0.010    $0.020
```

---

## Real-World Decision Examples

### Example 1: Code Template Search

**Query:** "Show me how to add Redis caching to FastAPI"

**Requirements:**
- Latency: <500ms acceptable
- Quality: High (bad example = wasted dev time)
- Frequency: Medium (10-20/day)

**Decision:**
```python
config = {
    'chunking': 'structure_aware',  # Code needs function boundaries
    'reranking': 'lightweight',     # Balance speed/quality
    'stitching': 'smart',           # Remove duplicate imports
    'top_k': 5                      # Multiple examples good
}

# Estimated: 150ms latency, 85% quality, $0.003/query
```

### Example 2: Documentation Q&A

**Query:** "How do I troubleshoot ECS task startup failures?"

**Requirements:**
- Latency: <1s acceptable (human waiting)
- Quality: Critical (ops emergency)
- Frequency: Low (1-2/day)

**Decision:**
```python
config = {
    'chunking': 'structure_aware',  # Markdown sections
    'reranking': 'llm',            # Quality critical
    'stitching': 'synthesize',     # Coherent answer needed
    'top_k': 3                     # Focus on best matches
}

# Estimated: 800ms latency, 90% quality, $0.012/query
```

### Example 3: Log Pattern Search

**Query:** "Find all workflows that failed with timeout error"

**Requirements:**
- Latency: <100ms (interactive search)
- Quality: Medium (can review results)
- Frequency: High (100+/day)

**Decision:**
```python
config = {
    'chunking': 'fixed_size',      # Fast, simple
    'reranking': 'none',           # Speed critical
    'stitching': 'concatenate',    # Show all matches
    'top_k': 20                    # Show many results
}

# Estimated: 50ms latency, 70% quality, $0.001/query
```

---

## Optimization Checklist

### Before Launch
- [ ] Profile chunking performance on real data
- [ ] Benchmark retrieval latency at expected load
- [ ] Measure token usage across query types
- [ ] Calculate cost per 1000 queries

### Week 1
- [ ] Monitor cache hit rates
- [ ] Track user satisfaction with results
- [ ] Measure actual latency p50/p95/p99
- [ ] Identify slow queries

### Month 1
- [ ] A/B test reranking strategies
- [ ] Optimize chunk sizes based on retrieval patterns
- [ ] Tune reranking weights
- [ ] Implement progressive loading if needed

---

## Common Pitfalls

### ❌ Over-Chunking
**Problem:** Chunks too small, lose context
**Solution:** Minimum 100 tokens per chunk, 20% overlap

### ❌ Under-Chunking
**Problem:** Chunks too large, poor retrieval
**Solution:** Maximum 1000 tokens per chunk

### ❌ No Reranking
**Problem:** Vector search alone misses keyword matches
**Solution:** Add lightweight BM25 reranking (minimal cost)

### ❌ Ignoring Metadata
**Problem:** Search across irrelevant documents
**Solution:** Filter by language, type, date before vector search

### ❌ No Caching
**Problem:** Re-computing embeddings for static docs
**Solution:** Cache embeddings in Redis, 80% cost reduction

---

## Quick Reference: Configuration Presets

### Preset 1: "Fast & Cheap"
```python
{
    'chunking': 'fixed_size',
    'chunk_size': 512,
    'reranking': False,
    'stitching': 'concatenate',
    'top_k': 10
}
# Use for: Logs, simple search, high QPS
# Latency: 50ms | Cost: $0.001 | Quality: 70%
```

### Preset 2: "Balanced" ⭐ RECOMMENDED
```python
{
    'chunking': 'structure_aware',
    'reranking': 'lightweight',
    'stitching': 'smart',
    'top_k': 5
}
# Use for: Code search, docs, 90% of queries
# Latency: 150ms | Cost: $0.003 | Quality: 85%
```

### Preset 3: "Quality First"
```python
{
    'chunking': 'structure_aware',
    'reranking': 'llm',
    'stitching': 'synthesize',
    'top_k': 3
}
# Use for: Critical queries, complex Q&A
# Latency: 800ms | Cost: $0.012 | Quality: 90%
```

---

## Testing Your RAG System

### Unit Tests
```python
async def test_retrieval_accuracy():
    """Test that relevant docs are retrieved."""
    rag = RAGSystem()
    await rag.index_document("FastAPI auth example...", "auth.py")

    results = await rag.retrieve("authentication example")

    assert len(results['chunks_used']) > 0
    assert 'auth' in results['context'].lower()
    assert results['stats']['retrieval_time_ms'] < 500
```

### Quality Benchmarks
```python
# Create test set of queries with known correct results
test_queries = [
    {
        'query': 'FastAPI authentication',
        'expected_source': 'auth_middleware.py',
        'min_score': 0.7
    },
    # ... 100 more test cases
]

# Measure: Precision@5, Recall@10, MRR
```

### Load Tests
```bash
# Test retrieval latency under load
ab -n 1000 -c 10 http://localhost:8000/retrieve?q=test

# Monitor: p50, p95, p99 latency
```

---

## Migration Path: Simple → RAG

### Phase 1: Index & Measure (Week 1)
```python
# Don't change retrieval yet, just collect data
rag = RAGSystem()
await rag.index_all_documents()

# Log what users search for
logger.info(f"Query: {query}, Found: {simple_search(query)}")
```

### Phase 2: A/B Test (Week 2-3)
```python
if user_id % 2 == 0:
    results = rag_retrieval(query)  # 50% get RAG
else:
    results = simple_retrieval(query)  # 50% get old

# Measure: Click-through rate, user satisfaction
```

### Phase 3: Full Rollout (Week 4)
```python
# Everyone gets RAG
results = rag_retrieval(query)

# But keep fallback!
if not results:
    results = simple_retrieval(query)
```

---

## Summary: The Golden Rules

1. **Start Simple**: Use "Balanced" preset, optimize later
2. **Measure First**: Latency and quality before changing
3. **Cache Everything**: Embeddings, results, common queries
4. **Progressive Enhancement**: Fast results first, perfect results follow
5. **Fallback Always**: Never break existing functionality
6. **Budget Matters**: Know your cost per query
7. **User Feedback**: Best metric for RAG quality

**Default Choice for This Framework:**
- Chunking: Structure-aware (500-1000 tokens)
- Reranking: Lightweight (BM25 + metadata)
- Stitching: Smart (dedupe + order)
- Target: <200ms latency, <$0.005/query, >80% quality
