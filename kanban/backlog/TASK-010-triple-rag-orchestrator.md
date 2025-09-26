# TASK-010: Triple RAG Orchestrator

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Assigned**: Unassigned
**Created**: 2025-09-25
**Updated**: 2025-09-25
**Estimated Effort**: 3-4 days
**Parent**: TASK-009

## Description
Implement Triple RAG orchestrator that combines Graph RAG, Vector RAG, and AST RAG retrieval methods using Neo4j's native vector search and graph capabilities.

Must leverage existing Neo4j infrastructure with 13,753 embeddings already stored.

## Business Value
- Semantic similarity search via vector embeddings (find related concepts)
- Graph relationship traversal (find connected laws/articles)
- Structural navigation via AST paths (find hierarchical context)
- Hybrid scoring to rank best results from all three methods

## Acceptance Criteria
- [ ] Vector search using Neo4j vector indexes (db.index.vector.queryNodes)
- [ ] Graph traversal using APOC path finding
- [ ] AST search using path pattern matching
- [ ] Hybrid orchestrator with configurable weights
- [ ] Result merging and deduplication
- [ ] Score normalization across methods
- [ ] Unit tests with 90%+ coverage
- [ ] Integration tests with live Neo4j
- [ ] Documentation with usage examples

## Technical Approach

### Existing Resources to Reuse
- Neo4j driver connection (src/data_access/graph_builder.py)
- AST path builder (src/data_access/ast_path_builder.py)
- Existing embeddings in Neo4j (13,753 vectors)
- Node types: Law, Article, Paragraph with relationships

### New Components Needed
```
src/retrieval/
├── triple_rag.py         # Main orchestrator
├── vector_search.py      # Neo4j vector search
├── graph_search.py       # Relationship traversal
├── ast_search.py         # Structural search
└── result_merger.py      # Score normalization & merging
```

### Dependencies
- Neo4j 5.x with vector index support
- APOC procedures (apoc.path.subgraphAll, apoc.path.expandConfig)
- sentence-transformers for query embedding
- numpy for score normalization

### Implementation Steps

1. **Create Vector Indexes** (Day 1)
   ```cypher
   CREATE VECTOR INDEX law_title_embeddings IF NOT EXISTS
   FOR (l:Law) ON (l.embedding)
   OPTIONS {
     indexConfig: {
       `vector.dimensions`: 384,
       `vector.similarity_function`: 'cosine'
     }
   }

   CREATE VECTOR INDEX article_content_embeddings IF NOT EXISTS
   FOR (a:Article) ON (a.embedding)
   OPTIONS {
     indexConfig: {
       `vector.dimensions`: 384,
       `vector.similarity_function`: 'cosine'
     }
   }
   ```

2. **Implement Vector Search** (Day 1)
   - Query embedding generation
   - Neo4j vector.queryNodes call
   - Min score filtering
   - Return nodes with metadata

3. **Implement Graph Search** (Day 2)
   - Seed node expansion
   - APOC relationship traversal
   - Depth-limited exploration
   - Relationship type filtering

4. **Implement AST Search** (Day 2)
   - Path pattern matching
   - Level-based filtering
   - Parent-child navigation
   - Breadth-first traversal

5. **Implement Hybrid Orchestrator** (Day 3)
   - Parallel execution of all methods
   - Score normalization (min-max)
   - Configurable weights
   - Result deduplication
   - Combined ranking

6. **Testing & Documentation** (Day 4)
   - Unit tests for each search method
   - Integration tests with Neo4j
   - Performance benchmarks
   - Usage examples

## Testing Requirements
- Unit tests for vector_search, graph_search, ast_search
- Integration test with real Neo4j database
- Test data: 10 sample laws with embeddings
- Performance test: < 500ms for hybrid search
- Edge cases: empty results, single result, max results

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Neo4j vector index not created | HIGH | Check index existence before search, create if missing |
| APOC not installed | HIGH | Add APOC dependency check on startup |
| Score normalization bias | MEDIUM | Use multiple normalization methods, make configurable |
| Slow graph traversal | MEDIUM | Limit max depth, use relationship filters |

## Related Tasks
- Parent: TASK-009 (LAWAST Intelligent System Integration)
- Depends on: None (uses existing infrastructure)
- Blocks: TASK-011 (Agent needs RAG methods)
- Blocks: TASK-012 (Reasoning needs RAG results)

## Notes
- Embeddings already exist in Neo4j (13,753)
- Vector dimensions: 384 (all-MiniLM-L6-v2)
- Graph has: Law→Article→Paragraph→Subpoint hierarchy
- AST paths follow: /domain_X/section_X/law_X/art_X/para_X format