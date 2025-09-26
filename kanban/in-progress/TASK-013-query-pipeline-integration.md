# TASK-013: Main Query Pipeline Integration

**Status**: IN-PROGRESS
**Priority**: HIGH
**Type**: feature
**Assigned**: AI Assistant
**Created**: 2025-09-25
**Updated**: 2025-09-26
**Started**: 2025-09-26
**Analysis Completed**: 2025-09-26
**Estimated Effort**: 2-3 days
**Parent**: TASK-009

## Description
Integrate all components into a unified query pipeline: User Query → Agent → Triple RAG → Reasoning → Apertus → Answer.

This task wires together the Agent System (TASK-011), Triple RAG (TASK-010), and Reasoning Engine (TASK-012) into a cohesive end-to-end system.

## Business Value
- End-to-end query processing
- Unified interface for legal questions
- Transparent execution flow
- Performance monitoring and logging
- Error handling and recovery

## Acceptance Criteria
- [ ] Main pipeline orchestrator
- [ ] Query execution flow: Agent → RAG → Reasoning → Articulation
- [ ] Multi-turn dialogue support
- [ ] Error handling at each stage
- [ ] Performance monitoring (latency, success rate)
- [ ] Logging for debugging
- [ ] CLI interface for testing
- [ ] REST API endpoint (optional, for future web integration)
- [ ] Integration tests for full pipeline
- [ ] Documentation with architecture diagram

## Technical Approach

### Existing Resources to Reuse
- Agent System (TASK-011)
- Triple RAG Orchestrator (TASK-010)
- Reasoning Engine (TASK-012)
- Apertus Client (src/articulation/apertus_client.py)

### New Components Needed
```
src/pipeline/
├── query_pipeline.py         # Main orchestrator
├── execution_flow.py         # Stage-by-stage execution
├── error_handler.py          # Handle failures gracefully
├── performance_monitor.py    # Track latency, success rate
└── logger.py                 # Structured logging

src/interfaces/
├── cli.py                    # Command-line interface
└── api.py                    # REST API (future)
```

### Dependencies
- All previous tasks (010, 011, 012)
- FastAPI (for REST API, optional)
- Click (for CLI)
- structlog (for structured logging)

### Implementation Steps

1. **Query Pipeline Orchestrator** (Day 1)
   ```python
   class QueryPipeline:
       def __init__(self):
           self.agent = IntelligentAgent()
           self.rag = TripleRAG()
           self.reasoning = ReasoningEngine()
           self.articulator = ApertusClient()

       async def execute(self, query: str, session_id: str = None):
           # Stage 1: Agent analyzes query
           strategy = await self.agent.analyze_query(query, session_id)

           # Stage 2: RAG retrieval
           results = await self.rag.search(
               query=query,
               strategy=strategy.method,
               weights=strategy.weights
           )

           # Stage 3: Reasoning
           reasoning = await self.reasoning.synthesize(
               query=query,
               results=results
           )

           # Stage 4: Articulation
           answer = await self.articulator.generate_answer(
               query=query,
               reasoning=reasoning
           )

           return {
               "answer": answer.text,
               "citations": reasoning.citations,
               "confidence": reasoning.confidence,
               "reasoning_chain": reasoning.chain_of_thought,
               "sources": results
           }
   ```

2. **Multi-Turn Dialogue Support** (Day 1)
   - Session management integration
   - Context passing between turns
   - Clarification handling
   - History accumulation

3. **Error Handling** (Day 2)
   - Stage-specific error recovery:
     - Agent failure → Use default strategy (hybrid)
     - RAG failure → Return partial results
     - Reasoning failure → Return raw results
     - Articulation failure → Return structured data
   - Graceful degradation
   - User-friendly error messages

4. **Performance Monitoring** (Day 2)
   - Latency tracking per stage
   - Success/failure rates
   - Cache hit rates
   - Resource usage
   - Metrics export (Prometheus format)

5. **CLI Interface** (Day 2)
   ```bash
   # Single query
   lawast query "What is the retirement age in Switzerland?"

   # Interactive mode
   lawast chat

   # Verbose mode (show reasoning)
   lawast query "..." --verbose

   # Specify strategy
   lawast query "..." --strategy vector
   ```

6. **Integration Testing** (Day 3)
   - End-to-end tests with real Neo4j
   - Multi-turn dialogue tests
   - Error recovery tests
   - Performance benchmarks

7. **Documentation** (Day 3)
   - Architecture diagram
   - API documentation
   - CLI usage guide
   - Performance tuning guide

## Testing Requirements
- Integration test: Simple factual query (single-turn)
- Integration test: Ambiguous query (multi-turn with clarification)
- Integration test: Complex query (hybrid RAG)
- Error test: Neo4j unavailable
- Error test: Invalid query
- Performance test: < 500ms P50 latency
- Load test: 10 concurrent queries

## Example Flow
```
User: "What is the retirement age in Switzerland?"

[AGENT]
├─ Intent: factual
├─ Complexity: simple
├─ Strategy: vector search
└─ No clarification needed

[RAG: Vector Search]
├─ Query embedding generated
├─ Neo4j vector search
├─ Found: AHVG Art. 21 (score: 0.94)
└─ Retrieved: 3 articles

[REASONING]
├─ Synthesize: AHVG Art. 21 describes retirement age
├─ Check temporal: Current version (2024-01-01)
├─ Apply legal logic: Federal law, in force
├─ Confidence: 0.95 (high source agreement)
└─ Citations: SR 831.10, Art. 21

[ARTICULATION]
├─ Generate natural language answer
└─ Include citations

[RESPONSE]
Answer: "In Switzerland, the retirement age is 65 for both men and women as of 2024."

Citations:
- AHVG Art. 21 (SR 831.10)

Confidence: 95%
```

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Component integration bugs | HIGH | Comprehensive integration tests |
| Performance degradation | MEDIUM | Profile each stage, optimize bottlenecks |
| Error cascade (one failure breaks all) | HIGH | Graceful degradation at each stage |
| Complex debugging | MEDIUM | Structured logging with trace IDs |

## Related Tasks
- Parent: TASK-009 (LAWAST Intelligent System Integration)
- Depends on: TASK-010 (Triple RAG)
- Depends on: TASK-011 (Agent System)
- Depends on: TASK-012 (Reasoning Engine)

## Notes
- Use async/await for parallel execution where possible
- Add trace IDs for request tracking across components
- Monitor each stage separately for performance tuning
- CLI should be the primary interface initially
- REST API can be added later for web integration

## Technical Analysis (Auto-generated 2025-09-26)

### Existing Resources Found
- **Components**:
  - `IntelligentAgent` (src/context/agent.py) - Fully functional orchestrator with query analysis
  - `TripleRAG` (src/retrieval/triple_rag.py) - Complete parallel RAG implementation
  - `ReasoningEngine` (src/reasoning/engine.py) - Legal reasoning with citations
  - `ApertusClient` (src/articulation/apertus_client.py) - Swiss AI natural language generation
  - Session management (src/context/session_manager.py)
  - Context tree for multi-turn dialogue (src/context/context_tree.py)
  - Query analyzer (src/context/query_analyzer.py)
  - Strategy planner (src/context/strategy_planner.py)
  - Chain of thought reasoning (src/reasoning/chain_of_thought.py)
  - Citation tracker (src/reasoning/citation_tracker.py)
  - Confidence scorer (src/reasoning/confidence_scorer.py)

- **Services**:
  - Neo4j graph database integration (src/data_access/)
  - Storage pipeline (src/data_access/storage_pipeline.py)
  - Embedding generation capabilities

- **APIs**:
  - No existing REST/GraphQL endpoints found
  - Basic CLI stub exists (src/interfaces/cli/main.py)

- **Database**:
  - Neo4j with vector search capabilities
  - Document storage with embeddings
  - Legal taxonomy and relationships

- **Utilities**:
  - HTML parsers (src/parsers/)
  - Legal extractors (src/extractors/)
  - Classification system

### Dependencies Required
- **Frontend packages**: N/A (CLI/API only)
- **Backend packages**:
  - fastapi>=0.104.0 (enabled in requirements.txt)
  - uvicorn>=0.24.0 (enabled in requirements.txt)
  - pydantic>=2.0.0 (enabled in requirements.txt)
  - httpx (for async HTTP - to be added)
  - python-multipart (for file uploads - to be added)
- **Database migrations**: None required (using existing Neo4j schema)
- **Docker services**: Neo4j (already configured)

### Impact Assessment
#### Files to Create (New)
- `src/pipeline/query_pipeline.py`: Main orchestrator class
- `src/pipeline/execution_flow.py`: Stage-by-stage execution logic
- `src/pipeline/error_handler.py`: Graceful degradation
- `src/pipeline/performance_monitor.py`: Metrics tracking
- `src/interfaces/api/app.py`: FastAPI application
- `src/interfaces/api/models.py`: Pydantic request/response models
- `src/interfaces/api/endpoints.py`: REST endpoints
- `src/interfaces/openwebui/lawast_pipeline.py`: OpenWebUI Pipeline integration

#### Files to Modify
- `src/interfaces/cli/main.py`: Implement actual CLI using pipeline
- `requirements.txt`: Add httpx, python-multipart

#### Components Affected
- IntelligentAgent: LOW (just needs async wrapper)
- TripleRAG: LOW (already has async support)
- ReasoningEngine: LOW (needs async wrapper)
- ApertusClient: LOW (already async-ready)

#### API Changes
- NEW `/v1/chat/completions`: OpenAI-compatible endpoint
- NEW `/v1/query`: Direct query endpoint
- NEW `/v1/sessions`: Session management
- NEW `/health`: Health check endpoint

#### Database Changes
- None required (using existing schema)

### OpenWebUI Integration Options

#### Option 1: Pipeline Module (Recommended)
- **Pros**: Native integration, no separate service, simpler deployment
- **Cons**: Requires OpenWebUI pipeline loader setup
- **Implementation**: Create Pipeline class following OpenWebUI format

#### Option 2: REST API with OpenAI Format
- **Pros**: Universal compatibility, standalone service, testable
- **Cons**: Requires service management, additional deployment step
- **Implementation**: FastAPI with OpenAI-compatible endpoints

### Implementation Checklist
Based on CLAUDE.md principles:
- [x] Reuse existing IntelligentAgent instead of creating new orchestrator
- [x] Extend existing components rather than duplicate
- [ ] Create async wrappers for synchronous operations
- [ ] Implement Pipeline class for OpenWebUI
- [ ] Add FastAPI endpoints for REST option
- [ ] Follow SOLID principles in pipeline design
- [ ] Maintain backwards compatibility
- [ ] Add proper error handling at each stage
- [ ] Include loading states for long operations
- [ ] Write self-documenting code
- [ ] Add comprehensive logging with trace IDs
- [ ] Implement graceful degradation
- [ ] Add performance monitoring

### Risk Analysis
- **Risk Level**: MEDIUM
- **Main Risks**:
  - **Async/Sync mismatch**: Some components are sync-only. **Mitigation**: Use asyncio.run_in_executor for sync operations
  - **OpenWebUI version compatibility**: Pipeline format may change. **Mitigation**: Test with multiple OpenWebUI versions, document version requirements
  - **Performance bottlenecks**: Neo4j queries may be slow. **Mitigation**: Implement caching, connection pooling, query optimization
  - **Error cascading**: One component failure breaks pipeline. **Mitigation**: Implement graceful degradation at each stage
  - **Session state management**: Multi-turn dialogue complexity. **Mitigation**: Use existing SessionManager, implement cleanup strategies

### Estimated Effort
- Original: 2-3 days
- Adjusted: 3-5 days
- Reason: Need to implement both Pipeline and REST API options for maximum flexibility, plus async wrappers

### Implementation Strategy

1. **Phase 1: Core Pipeline (Day 1)**
   - Create QueryPipeline orchestrator
   - Wire existing components together
   - Add async wrappers where needed
   - Implement basic error handling

2. **Phase 2: OpenWebUI Pipeline (Day 2)**
   - Create Pipeline class following OpenWebUI format
   - Test with OpenWebUI pipeline loader
   - Add response formatting for OpenWebUI

3. **Phase 3: REST API (Day 2-3)**
   - Implement FastAPI application
   - Add OpenAI-compatible endpoints
   - Create Pydantic models
   - Add API documentation

4. **Phase 4: Testing & Polish (Day 3-4)**
   - Integration tests
   - Performance optimization
   - Documentation
   - Error handling refinement

5. **Phase 5: Deployment Guide (Day 4-5)**
   - Docker configuration
   - Environment setup guide
   - OpenWebUI integration instructions
   - API usage examples