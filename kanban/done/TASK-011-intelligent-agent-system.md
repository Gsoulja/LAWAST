# TASK-011: Intelligent Agent System

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Assigned**: Unassigned
**Created**: 2025-09-25
**Updated**: 2025-09-25
**Estimated Effort**: 2-3 days
**Parent**: TASK-009

## Description
Implement intelligent agent system that plans retrieval strategies, generates clarifying questions, builds context trees, and manages multi-turn dialogue sessions.

The agent analyzes user queries to determine:
- Which RAG method(s) to use (vector, graph, AST, or hybrid)
- When to ask clarifying questions
- How to build progressive context from user responses
- Session state management

## Business Value
- Optimal retrieval strategy selection (don't waste resources)
- Progressive context building for ambiguous queries
- Multi-turn dialogue support
- Query intent classification
- Context accumulation across conversation

## Acceptance Criteria
- [ ] Query analyzer determines retrieval strategy
- [ ] Clarification generator for ambiguous queries
- [ ] Context tree builder accumulates information
- [ ] Session manager for multi-turn dialogue
- [ ] Query intent classifier (factual, comparative, procedural, etc.)
- [ ] Confidence scoring for strategy selection
- [ ] Unit tests with 90%+ coverage
- [ ] Integration tests with mock RAG
- [ ] Documentation with decision tree diagrams

## Technical Approach

### Existing Resources to Reuse
- Apertus client for LLM-based analysis
- Triple RAG methods (from TASK-010)

### New Components Needed
```
src/context/
├── agent.py                  # Main agent orchestrator
├── query_analyzer.py         # Analyze query intent & complexity
├── strategy_planner.py       # Decide which RAG methods to use
├── clarification_generator.py # Generate clarifying questions
├── context_tree.py           # Build context tree from dialogue
└── session_manager.py        # Multi-turn session state
```

### Dependencies
- Apertus client (swiss-ai/Apertus-8B-Instruct-2509)
- Triple RAG orchestrator (TASK-010)
- dataclasses for state management

### Implementation Steps

1. **Query Analyzer** (Day 1)
   - Intent classification (factual, comparative, procedural, exploratory)
   - Complexity scoring (simple, medium, complex)
   - Ambiguity detection (vague terms, missing context)
   - Entity extraction (law names, article numbers, dates)

2. **Strategy Planner** (Day 1)
   - Decision matrix for RAG method selection:
     ```python
     if query.has_article_number():
         use_ast_search()
     elif query.is_conceptual():
         use_vector_search()
     elif query.mentions_relationship():
         use_graph_search()
     else:
         use_hybrid_search()
     ```
   - Confidence scoring for strategy
   - Fallback strategies

3. **Clarification Generator** (Day 2)
   - Detect missing context (time period, jurisdiction, specific law)
   - Generate targeted questions
   - Template-based generation for common cases
   - LLM-based generation for complex cases

4. **Context Tree Builder** (Day 2)
   - Node structure: Question → Answer → Extracted Info
   - Progressive accumulation
   - Context pruning (keep relevant, discard tangential)
   - Context serialization for session storage

5. **Session Manager** (Day 3)
   - Session creation and lifecycle
   - Context persistence
   - History tracking
   - Session timeout and cleanup

6. **Integration & Testing** (Day 3)
   - Wire all components together
   - Unit tests for each component
   - Integration tests for full agent flow
   - Example dialogues

## Testing Requirements
- Unit tests for query_analyzer with 50 test queries
- Strategy planner tests with all intent types
- Clarification generator tests for ambiguous queries
- Context tree tests for multi-turn dialogue
- Session manager tests for state persistence
- Integration test: 5-turn dialogue with context building

## Example Decision Flow
```
User: "What are the requirements for Swiss citizenship?"

Agent Analysis:
- Intent: procedural (how-to)
- Complexity: medium (broad topic)
- Ambiguity: high (naturalization vs birth vs marriage?)
- Strategy: hybrid search + clarification

Agent Response:
- Clarifying question: "Are you asking about naturalization, citizenship by birth, or citizenship by marriage?"
- Context tree: {topic: citizenship, type: UNKNOWN, jurisdiction: Switzerland}

User: "Naturalization"

Agent Analysis:
- Context update: {topic: citizenship, type: naturalization, jurisdiction: Switzerland}
- Strategy: vector search for "Swiss naturalization requirements"
- No more clarification needed

Agent executes RAG and returns answer...
```

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Over-clarification (too many questions) | HIGH | Limit to 1-2 questions per turn |
| Wrong strategy selection | MEDIUM | Use confidence scores, fallback to hybrid |
| Context explosion (too much history) | MEDIUM | Implement context pruning |
| Session state loss | LOW | Persist to disk/database |

## Related Tasks
- Parent: TASK-009 (LAWAST Intelligent System Integration)
- Depends on: TASK-010 (needs Triple RAG)
- Blocks: TASK-013 (pipeline needs agent)

## Notes
- Use Apertus for intent classification and question generation
- Keep decision logic simple and transparent
- Log all strategy decisions for debugging
- Session timeout: 30 minutes of inactivity