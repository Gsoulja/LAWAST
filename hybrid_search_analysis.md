# Hybrid Search Analysis: Vector Similarity + BM25 Text Search

## Executive Summary

The current LAWAST system uses vector similarity search which has semantic understanding issues - Article 7 (Human Dignity) consistently outranks Article 41 (Social Goals) for health-related queries despite Article 41 containing the exact keywords "Gesundheit" (health) and "Pflege" (care).

A hybrid approach combining **vector similarity** with **BM25 text search** would improve accuracy by:
1. Capturing semantic relationships (vector)
2. Rewarding exact keyword matches (BM25)
3. Balancing conceptual and literal relevance

## Current Implementation Analysis

### Search Architecture
```
Query → Triple RAG Orchestrator
         ├── Vector Search (40% weight)
         ├── Graph Search (30% weight)
         └── AST Search (30% weight)
              ↓
         Result Merger → Final Results
```

### Key Components

1. **Vector Search** (`src/retrieval/vector_search.py`)
   - Uses multilingual-e5-large model (1024 dimensions)
   - Cosine similarity scoring
   - Separate indexes per node type (law, article, paragraph, subpoint)
   - Query prefix: "query: " for E5 model

2. **Current Scoring**
   - Pure cosine similarity (0-1 range)
   - Article 7: 0.9350 similarity
   - Article 41: 0.9210 similarity
   - Article 9: 0.9221 similarity

### Problem Analysis

For query: "Erhält jede Person die für ihre Gesundheit notwendige Pflege?"

**Article 7** (ranks #1, similarity 0.9350):
```
1. Die Würde des Menschen ist zu achten und zu schützen.
```
- Semantic: Human dignity, protection
- Keywords: None match query

**Article 41** (ranks #4-5, similarity 0.9210):
```
1. Bund und Kantone setzen sich...
b. jede Person die für ihre Gesundheit notwendige Pflege erhält
```
- Semantic: Social goals, healthcare
- Keywords: EXACT MATCH - "Gesundheit", "Pflege", entire phrase

## Neo4j Full-Text Search Capabilities

### 1. Native Full-Text Indexes
```cypher
-- Create full-text index
CALL db.index.fulltext.createNodeIndex(
  'article_fulltext',
  ['Article'],
  ['content_full', 'content_preview'],
  {analyzer: 'german'}
)

-- Query with Lucene scoring
CALL db.index.fulltext.queryNodes(
  'article_fulltext',
  'Gesundheit Pflege'
) YIELD node, score
```

### 2. Built-in Analyzers
- **Standard**: Basic tokenization
- **German**: German stemming, stop words
- **Whitespace**: Simple splitting
- **Keyword**: No tokenization

### 3. Lucene Query Syntax
- Boolean: `Gesundheit AND Pflege`
- Phrase: `"notwendige Pflege"`
- Fuzzy: `Gesundheit~`
- Proximity: `"Gesundheit Pflege"~5`

### 4. Scoring Algorithm
Neo4j uses **Lucene's BM25** by default:
```
score = IDF * (TF * (k1 + 1)) / (TF + k1 * (1 - b + b * (docLen / avgDocLen)))
```
- IDF: Inverse Document Frequency
- TF: Term Frequency
- k1: Term saturation (default 1.2)
- b: Length normalization (default 0.75)

## Proposed Hybrid Search Design

### 1. Architecture
```
Query → Hybrid Search Orchestrator
         ├── Vector Search (semantic)
         │    └── Cosine Similarity Score
         ├── BM25 Search (keyword)
         │    └── Lucene BM25 Score
         └── Graph/AST Search (structural)
              ↓
         Hybrid Scorer → Weighted Combination
              ↓
         Final Ranked Results
```

### 2. Hybrid Scoring Formula

```python
hybrid_score = α * vector_score + β * bm25_normalized + γ * graph_score

where:
- α = 0.5 (semantic weight)
- β = 0.3 (keyword weight)
- γ = 0.2 (structural weight)
- α + β + γ = 1.0
```

### 3. Score Normalization

BM25 scores need normalization to [0,1] range:
```python
bm25_normalized = min(bm25_score / max_bm25_score, 1.0)
# or
bm25_normalized = 1 - exp(-bm25_score * scaling_factor)
```

### 4. Language-Aware Processing

```python
def get_analyzer_for_query(query: str) -> str:
    if detect_language(query) == 'de':
        return 'german'
    elif detect_language(query) == 'fr':
        return 'french'
    # ... etc
```

## Implementation Plan

### Phase 1: Index Creation
```cypher
-- Create multilingual full-text indexes
CALL db.index.fulltext.createNodeIndex(
  'articles_fulltext_de',
  ['Article'],
  ['content_full'],
  {analyzer: 'german'}
);

CALL db.index.fulltext.createNodeIndex(
  'articles_fulltext_fr',
  ['Article'],
  ['content_full'],
  {analyzer: 'french'}
);
```

### Phase 2: Hybrid Search Class
```python
class HybridSearch:
    def search(self, query: str, top_k: int = 20):
        # 1. Generate vector embedding
        embedding = self.generate_embedding(query)

        # 2. Parallel search
        vector_results = self.vector_search(embedding, top_k * 2)
        bm25_results = self.fulltext_search(query, top_k * 2)

        # 3. Merge and score
        return self.hybrid_score(vector_results, bm25_results, top_k)
```

### Phase 3: Integration Points

1. **New Component**: `src/retrieval/hybrid_search.py`
2. **Modify**: `src/retrieval/triple_rag.py`
   - Add HybridSearch as option
   - Configure weights
3. **Update**: `src/pipeline/query_pipeline.py`
   - Add hybrid search strategy

### Phase 4: Testing Strategy

Test queries for Article 41 validation:
```python
test_queries = {
    'exact': "Gesundheit notwendige Pflege",  # Should rank #1
    'semantic': "healthcare for everyone",     # Should still rank high
    'mixed': "soziale Ziele Gesundheit"       # Balance both
}
```

## Expected Improvements

### Before (Vector Only):
1. Article 7 (0.9350) - Human dignity
2. Article 9 (0.9221) - Protection from arbitrariness
3. Article 12 (0.9189) - Right to assistance
4. **Article 41 (0.9210)** - Social goals ❌

### After (Hybrid):
1. **Article 41** - High BM25 (exact match) + Good vector ✅
2. Article 12 - Good vector + Some keyword overlap
3. Article 7 - High vector only
4. Article 9 - Medium vector only

## Configuration Recommendations

### Initial Weights
```python
config = {
    'vector_weight': 0.5,    # Semantic understanding
    'bm25_weight': 0.3,      # Keyword matching
    'graph_weight': 0.2,     # Structural relationships

    'bm25_boost_exact': 2.0, # Boost exact phrase matches
    'bm25_k1': 1.2,         # Term frequency saturation
    'bm25_b': 0.75          # Document length normalization
}
```

### Language-Specific Tuning
```python
language_configs = {
    'de': {'analyzer': 'german', 'bm25_weight': 0.35},
    'fr': {'analyzer': 'french', 'bm25_weight': 0.30},
    'it': {'analyzer': 'italian', 'bm25_weight': 0.30},
    'rm': {'analyzer': 'standard', 'bm25_weight': 0.25}
}
```

## Performance Considerations

1. **Index Size**: Full-text indexes add ~20-30% storage
2. **Query Time**: Parallel execution keeps latency low
3. **Memory**: BM25 scoring is memory-efficient
4. **Caching**: Cache normalized BM25 scores

## Next Steps

1. ✅ Analyze current implementation
2. ✅ Research Neo4j capabilities
3. ⏳ Design hybrid algorithm
4. 🔲 Implement proof-of-concept
5. 🔲 Test with health queries
6. 🔲 Tune weights empirically
7. 🔲 Deploy to production