# TASK-013: Main Query Pipeline Integration

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Assigned**: Unassigned
**Created**: 2025-09-25
**Updated**: 2025-09-25
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