# LAWAST Complete Project Structure
## Including AST System for Legal Document Structure Analysis

### Updated Architecture with AST

From our three core systems:
1. **Artificial Reasoning**: Deterministic logic + Apertus articulation
2. **Law Classification**: SR hierarchy, multi-tagging, relationships
3. **AST System**: Legal document structure parsing and traversal

### Complete Folder Structure

```
LAWAST/
├── README.md
├── requirements.txt
├── Makefile
├── setup.py
│
├── src/
│   ├── __init__.py
│   │
│   ├── reasoning/              # DETERMINISTIC REASONING LAYER
│   │   ├── __init__.py
│   │   ├── rule_engine.py      # Legal rule execution
│   │   ├── graph_algorithms.py # Graph traversal logic
│   │   ├── logic_solver.py     # Constraint checking
│   │   └── constraint_checker.py
│   │
│   ├── ast/                    # AST SYSTEM (LEGAL STRUCTURE)
│   │   ├── __init__.py
│   │   ├── legal_parser.py     # Parse legal documents into AST
│   │   ├── ast_nodes.py        # Node types for legal structures
│   │   ├── traverser.py        # AST traversal algorithms
│   │   ├── extractors/         # Extract specific patterns
│   │   │   ├── __init__.py
│   │   │   ├── conditions.py   # IF/THEN/UNLESS patterns
│   │   │   ├── exceptions.py   # Exception clauses
│   │   │   ├── definitions.py  # Legal definitions
│   │   │   └── references.py   # Cross-references
│   │   └── analyzers/          # AST analysis tools
│   │       ├── __init__.py
│   │       ├── structure_analyzer.py
│   │       ├── logic_flow.py   # Legal logic flow analysis
│   │       └── scope_analyzer.py # Scope and applicability
│   │
│   ├── classification/         # LAW CLASSIFICATION SYSTEM
│   │   ├── __init__.py
│   │   ├── sr_classifier.py
│   │   ├── article_mapper.py
│   │   ├── tag_system.py
│   │   ├── relationships.py
│   │   └── law_layers.py
│   │
│   ├── articulation/           # APERTUS ARTICULATION LAYER
│   │   ├── __init__.py
│   │   ├── apertus_client.py
│   │   ├── templates.py
│   │   ├── reasoning_articulator.py
│   │   └── multilingual.py
│   │
│   ├── retrieval/              # TRIPLE RAG IMPLEMENTATION
│   │   ├── __init__.py
│   │   ├── graph_rag.py        # Graph-based (relationships)
│   │   ├── vector_rag.py       # Semantic search (similarity)
│   │   ├── ast_rag.py          # Structure-based (document logic)
│   │   └── hybrid_rag.py       # Combined Graph+Vector+AST
│   │
│   ├── context/                # CONTEXT TREE MANAGEMENT
│   │   ├── __init__.py
│   │   ├── context_tree.py     # Build context progressively
│   │   ├── clarification.py    # Generate clarifying questions
│   │   ├── session_manager.py  # Manage conversation state
│   │   └── gap_analyzer.py     # Identify missing information
│   │
│   ├── data_access/
│   │   ├── __init__.py
│   │   ├── fedlex_loader.py
│   │   ├── graph_builder.py
│   │   ├── vector_store.py
│   │   ├── ast_indexer.py      # Index AST structures
│   │   └── cache_manager.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── law.py
│   │   │   ├── article.py
│   │   │   ├── ast_document.py # Document with AST
│   │   │   ├── context_tree.py
│   │   │   └── query.py
│   │   └── use_cases/
│   │       ├── search_law.py
│   │       ├── analyze_structure.py # AST analysis use case
│   │       ├── build_context.py
│   │       └── generate_answer.py
│   │
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── cli/
│   │   ├── api/
│   │   └── web/
│   │
│   └── config/
│       ├── __init__.py
│       ├── settings.py
│       ├── law_mappings.py
│       ├── ast_patterns.py     # Legal AST patterns
│       └── reasoning_rules.py
│
├── data/
│   ├── laws/
│   │   ├── employment/
│   │   │   ├── articles.json
│   │   │   ├── ast_trees.json  # Pre-parsed AST
│   │   │   └── relationships.json
│   │   ├── rental/
│   │   └── credit/
│   ├── ast/
│   │   ├── parsed_trees/       # Cached AST structures
│   │   └── patterns/           # Common legal patterns
│   ├── graph/
│   ├── embeddings/
│   └── cache/
│
├── scripts/
│   ├── extract_target_laws.py
│   ├── build_ast_index.py     # Parse laws into AST
│   ├── analyze_structure.py   # Analyze legal structure
│   ├── build_classification.py
│   ├── generate_graph.py
│   ├── compute_embeddings.py
│   └── demo.py
│
├── tests/
│   ├── unit/
│   │   ├── test_reasoning/
│   │   ├── test_ast/          # AST parser tests
│   │   ├── test_classification/
│   │   └── test_articulation/
│   ├── integration/
│   │   ├── test_triple_rag.py # Test Graph+Vector+AST
│   │   └── test_full_flow.py
│   └── scenarios/
│
└── notebooks/
    ├── ast_exploration.ipynb  # Explore legal structures
    ├── pattern_discovery.ipynb # Find legal patterns
    └── triple_rag_demo.ipynb  # Demo all three RAG types
```

### AST System Components

#### 1. Legal AST Node Types (`ast/ast_nodes.py`)

```python
class LegalASTNode:
    """Base node for legal document AST"""

class LawNode(LegalASTNode):
    """Entire law document"""

class ChapterNode(LegalASTNode):
    """Chapter/Section"""

class ArticleNode(LegalASTNode):
    """Individual article"""

class ParagraphNode(LegalASTNode):
    """Paragraph within article"""

class ConditionNode(LegalASTNode):
    """IF/WHEN/UNLESS conditions"""

class ExceptionNode(LegalASTNode):
    """EXCEPT/NOTWITHSTANDING clauses"""

class ListNode(LegalASTNode):
    """Enumerated lists (a,b,c)"""

class ReferenceNode(LegalASTNode):
    """Cross-references to other articles"""
```

#### 2. AST Pattern Extractors (`ast/extractors/`)

```python
# conditions.py - Extract legal conditions
def extract_conditions(ast_node):
    """
    Find patterns like:
    - "If X then Y"
    - "When A applies, B must"
    - "Unless C, D is required"
    """

# exceptions.py - Extract exceptions
def extract_exceptions(ast_node):
    """
    Find patterns like:
    - "Except in cases of..."
    - "This does not apply when..."
    - "Notwithstanding..."
    """

# definitions.py - Extract legal definitions
def extract_definitions(ast_node):
    """
    Find patterns like:
    - "X means..."
    - "For purposes of this law, Y is..."
    - "The term Z refers to..."
    """
```

#### 3. Triple RAG Integration

```python
class TripleRAG:
    """Combines Graph, Vector, and AST retrieval"""

    def query(self, question):
        # 1. Vector RAG - Semantic similarity
        similar_articles = self.vector_rag.search(question)

        # 2. AST RAG - Structural patterns
        relevant_structures = self.ast_rag.find_patterns(question)
        # E.g., "What are exceptions?" → Find ExceptionNodes

        # 3. Graph RAG - Relationships
        connected_laws = self.graph_rag.traverse(similar_articles)

        # Combine all three
        return self.merge_results(
            similar_articles,
            relevant_structures,
            connected_laws
        )
```

### AST Use Cases

#### Example 1: Finding All Exceptions
```python
# User: "What exceptions exist for termination?"
ast_results = ast_rag.find_all(
    node_type=ExceptionNode,
    context="termination"
)
# Returns all exception clauses related to termination
```

#### Example 2: Understanding Conditions
```python
# User: "Under what conditions can rent be increased?"
conditions = ast_rag.extract_conditions(
    article="OR 269-270"
)
# Returns structured conditions with IF/THEN logic
```

#### Example 3: Tracing Legal Logic
```python
# User: "Explain the logic flow of Article 337"
logic_flow = ast_analyzer.analyze_logic(
    article="OR 337"
)
# Returns:
# IF grave_misconduct
#   THEN immediate_termination_allowed
#   EXCEPT protected_categories
#     UNLESS criminal_act
```

### Implementation Priority with AST

#### Phase 1: Core + Basic AST (Friday Morning)
```
1. src/ast/legal_parser.py      # Basic parsing
2. src/ast/ast_nodes.py         # Node definitions
3. src/retrieval/ast_rag.py     # Simple AST search
```

#### Phase 2: Advanced AST (Friday Afternoon)
```
1. src/ast/extractors/*         # Pattern extraction
2. src/ast/analyzers/*          # Structure analysis
3. src/retrieval/hybrid_rag.py  # Combine all three
```

#### Phase 3: Polish (Friday Night)
```
1. Optimize AST traversal
2. Cache parsed structures
3. Demo AST capabilities
```

### Benefits of AST System

1. **Structural Understanding**: Knows document hierarchy
2. **Logic Extraction**: Finds IF/THEN/EXCEPT patterns
3. **Precise Retrieval**: Can find specific structural elements
4. **Better Context**: Understands scope and applicability
5. **Legal Reasoning**: Follows document logic flow

### For the Judges

The AST system shows:
- **Technical sophistication**: Parsing legal documents into trees
- **Deep understanding**: Not just text search, but structure comprehension
- **Innovation**: Triple RAG (Graph + Vector + AST) is unique
- **Practical value**: Can answer structure-based queries

This completes the LAWAST architecture with all three intelligent systems working together!