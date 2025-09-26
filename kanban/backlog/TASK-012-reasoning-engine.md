# TASK-012: Reasoning Engine

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Assigned**: Unassigned
**Created**: 2025-09-25
**Updated**: 2025-09-25
**Estimated Effort**: 3-4 days
**Parent**: TASK-009

## Description
Implement reasoning engine that synthesizes results from multiple RAG sources, applies legal logic and chain-of-thought reasoning, validates consistency, and generates transparent explanations.

The reasoning engine bridges retrieval and articulation by:
- Combining results from vector, graph, and AST searches
- Applying legal reasoning rules (hierarchy, precedence, temporal)
- Validating consistency across sources
- Generating chain-of-thought explanations

## Business Value
- Multi-source synthesis (combine complementary information)
- Legal logic application (handle law hierarchy, amendments, conflicts)
- Transparent reasoning (explain how answer was derived)
- Factual validation (detect contradictions, cite sources)
- Confidence scoring (indicate answer quality)

## Acceptance Criteria
- [ ] Multi-source result synthesizer
- [ ] Chain-of-thought reasoning generator
- [ ] Legal logic flow analyzer (hierarchy, temporal, precedence)
- [ ] Consistency validator across sources
- [ ] Contradiction detector
- [ ] Citation tracker (source attribution)
- [ ] Confidence scorer
- [ ] Unit tests with 90%+ coverage
- [ ] Integration tests with mock RAG results
- [ ] Documentation with reasoning examples

## Technical Approach

### Existing Resources to Reuse
- Apertus client for LLM-based reasoning
- Triple RAG results (from TASK-010)
- AST path builder for hierarchy analysis

### New Components Needed
```
src/reasoning/
├── engine.py                 # Main reasoning orchestrator
├── synthesizer.py            # Combine multi-source results
├── chain_of_thought.py       # Generate reasoning steps
├── legal_logic.py            # Legal reasoning rules
├── validator.py              # Consistency & contradiction check
├── citation_tracker.py       # Track source attribution
└── confidence_scorer.py      # Score answer quality
```

### Dependencies
- Apertus client (swiss-ai/Apertus-8B-Instruct-2509)
- Triple RAG orchestrator (TASK-010)
- AST path builder for hierarchy
- dataclasses for structured reasoning

### Implementation Steps

1. **Multi-Source Synthesizer** (Day 1)
   - Merge results from vector, graph, AST
   - Identify complementary vs. redundant information
   - Resolve conflicts (e.g., different article versions)
   - Weight sources by reliability

2. **Legal Logic Analyzer** (Day 1-2)
   - Hierarchy rules (Constitution > Law > Ordinance)
   - Temporal rules (newer law overrides older)
   - Precedence rules (specific > general)
   - Scope rules (federal vs. cantonal)
   - Validity rules (in force vs. repealed)

3. **Chain-of-Thought Generator** (Day 2)
   - Structure: Question → Evidence → Logic → Conclusion
   - Step-by-step reasoning
   - Cite sources at each step
   - Example:
     ```
     Question: "What is the retirement age in Switzerland?"

     Step 1: Search for "retirement age" in laws
     → Found: AHVG Art. 21 (SR 831.10)

     Step 2: Extract relevant provision
     → "Men: 65 years, Women: 64 years (as of 2023)"

     Step 3: Check for recent amendments
     → Found: Amendment effective 2024-01-01 raising women's age

     Step 4: Apply temporal logic
     → Current date: 2025-09-25 → Use 2024 version

     Conclusion: "As of 2024, retirement age is 65 for both men and women."
     Citation: AHVG Art. 21 (SR 831.10), amended 2024-01-01
     ```

4. **Consistency Validator** (Day 3)
   - Cross-check information across sources
   - Detect contradictions (same article, different content)
   - Flag uncertainty when sources disagree
   - Provide confidence scores

5. **Citation Tracker** (Day 3)
   - Track which RAG source provided which fact
   - Generate proper citations (SR number, article, paragraph)
   - Link to AST paths for traceability

6. **Confidence Scorer** (Day 4)
   - Source agreement score (all sources agree? partial?)
   - Coverage score (comprehensive vs. partial answer)
   - Recency score (up-to-date vs. potentially outdated)
   - Authority score (primary law vs. secondary source)
   - Combined confidence: 0.0-1.0

7. **Testing & Documentation** (Day 4)
   - Unit tests for each component
   - Integration tests with full reasoning flow
   - Example reasoning chains
   - Edge cases: contradictions, missing info, outdated laws

## Testing Requirements
- Unit tests for synthesizer with conflicting sources
- Legal logic tests for hierarchy, temporal, precedence rules
- Chain-of-thought tests for 10 example queries
- Validator tests for consistency checking
- Confidence scorer tests with varying quality inputs
- Integration test: Full reasoning from RAG results to final answer

## Example Legal Logic Rules
```python
class LegalLogic:
    def apply_hierarchy_rule(self, sources):
        # Constitution > Federal Law > Ordinance > Cantonal Law
        priority = {"Constitution": 4, "Law": 3, "Ordinance": 2, "Cantonal": 1}
        return sorted(sources, key=lambda s: priority.get(s.type, 0), reverse=True)

    def apply_temporal_rule(self, versions):
        # Newer version overrides older (if in force)
        in_force = [v for v in versions if v.in_force_date <= today]
        return max(in_force, key=lambda v: v.in_force_date)

    def apply_precedence_rule(self, general, specific):
        # Specific provision overrides general (lex specialis)
        return specific if specific.scope < general.scope else general
```

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Contradictory sources | HIGH | Flag contradictions, show all sources |
| Complex legal logic | MEDIUM | Start with basic rules, expand iteratively |
| LLM hallucination in reasoning | HIGH | Validate each step against retrieved facts |
| Performance overhead | MEDIUM | Cache reasoning steps, limit depth |

## Related Tasks
- Parent: TASK-009 (LAWAST Intelligent System Integration)
- Depends on: TASK-010 (needs Triple RAG results)
- Blocks: TASK-013 (pipeline needs reasoning)

## Notes
- Use Apertus for chain-of-thought generation
- Keep legal logic rules explicit and auditable
- Always cite sources (SR number, article, paragraph)
- Confidence score should reflect uncertainty
- Log all reasoning steps for debugging