# LAWAST Project Structure - Aligned with Architecture
## Based on Artificial Reasoning & Law Classification Systems

### Architecture Alignment

From our two key documents:
1. **Artificial Reasoning Architecture**: Deterministic reasoning + Apertus for articulation
2. **Law Classification System**: SR hierarchy, multi-tagging, relationship mapping

### Proposed Folder Structure

```
LAWAST/
├── README.md                    # Project overview
├── requirements.txt             # Dependencies
├── Makefile                     # Quick commands
├── setup.py                     # Package setup
│
├── src/
│   ├── __init__.py
│   │
│   ├── reasoning/              # DETERMINISTIC REASONING LAYER
│   │   ├── __init__.py
│   │   ├── rule_engine.py      # Legal rule execution
│   │   ├── graph_algorithms.py # Graph traversal logic
│   │   ├── ast_parser.py       # Legal document parser
│   │   ├── logic_solver.py     # Constraint checking
│   │   └── constraint_checker.py
│   │
│   ├── classification/         # LAW CLASSIFICATION SYSTEM
│   │   ├── __init__.py
│   │   ├── sr_classifier.py    # SR number ranges
│   │   ├── article_mapper.py   # Article range mapping
│   │   ├── tag_system.py       # Multi-tagging
│   │   ├── relationships.py    # DEFINES, AMENDS, etc.
│   │   └── law_layers.py       # Universal/Domain/Specific
│   │
│   ├── articulation/           # APERTUS ARTICULATION LAYER
│   │   ├── __init__.py
│   │   ├── apertus_client.py   # LLM interface
│   │   ├── templates.py        # Response templates
│   │   ├── reasoning_articulator.py
│   │   └── multilingual.py     # DE/FR/IT/RM/EN
│   │
│   ├── retrieval/              # RAG IMPLEMENTATION
│   │   ├── __init__.py
│   │   ├── graph_rag.py        # Graph-based retrieval
│   │   ├── vector_rag.py       # Semantic search
│   │   ├── ast_rag.py          # Structure-based
│   │   └── hybrid_rag.py       # Combined approach
│   │
│   ├── data_access/            # DATA LAYER
│   │   ├── __init__.py
│   │   ├── fedlex_loader.py    # Load JSON/HTML
│   │   ├── graph_builder.py    # Build Neo4j/NetworkX
│   │   ├── vector_store.py     # Embeddings storage
│   │   └── cache_manager.py    # Response caching
│   │
│   ├── core/                   # DOMAIN ENTITIES
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── law.py          # Law entity
│   │   │   ├── article.py      # Article entity
│   │   │   ├── context_tree.py # Context building
│   │   │   └── query.py        # Query entity
│   │   └── use_cases/
│   │       ├── search_law.py
│   │       ├── analyze_query.py
│   │       └── generate_answer.py
│   │
│   ├── interfaces/             # CLEAN INTERFACES
│   │   ├── __init__.py
│   │   ├── cli/                # Command line
│   │   │   ├── main.py
│   │   │   └── commands.py
│   │   ├── api/                # REST API
│   │   │   ├── app.py
│   │   │   └── endpoints.py
│   │   └── web/                # Web UI
│   │       └── streamlit_app.py
│   │
│   └── config/                 # CONFIGURATION
│       ├── __init__.py
│       ├── settings.py         # Environment config
│       ├── law_mappings.py     # From LAW_CLASSIFICATION_SYSTEM.md
│       └── reasoning_rules.py  # Legal rules
│
├── data/                       # PROCESSED DATA
│   ├── laws/
│   │   ├── employment/         # OR 319-362
│   │   │   ├── articles.json
│   │   │   ├── relationships.json
│   │   │   └── metadata.json
│   │   ├── rental/            # OR 253-304
│   │   │   └── ...
│   │   └── credit/            # OR 312-318
│   │       └── ...
│   ├── graph/
│   │   └── law_graph.db       # Neo4j/NetworkX export
│   ├── embeddings/
│   │   └── vectors.faiss      # Pre-computed embeddings
│   └── cache/
│       └── responses.db       # Cached responses
│
├── scripts/                   # UTILITY SCRIPTS
│   ├── extract_target_laws.py # Extract our 3 domains
│   ├── build_classification.py # Apply classification system
│   ├── generate_graph.py     # Build relationship graph
│   ├── compute_embeddings.py
│   └── demo.py               # Quick demo runner
│
├── tests/
│   ├── unit/
│   │   ├── test_reasoning/   # Test rule engine
│   │   ├── test_classification/
│   │   └── test_articulation/
│   ├── integration/
│   │   └── test_full_flow.py
│   └── scenarios/            # Demo scenarios
│       ├── employment_termination.py
│       ├── rent_increase.py
│       └── credit_limits.py
│
├── notebooks/               # EXPLORATION
│   ├── data_exploration.ipynb
│   ├── graph_visualization.ipynb
│   └── demo_walkthrough.ipynb
│
├── docs/
│   ├── ARCHITECTURE.md     # System design
│   ├── API.md              # API documentation
│   ├── DEMO_GUIDE.md       # For judges
│   └── references/         # Our existing docs
│       ├── ARTIFICIAL_REASONING_ARCHITECTURE.md
│       └── LAW_CLASSIFICATION_SYSTEM.md
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

### Key Architectural Alignments

#### 1. Reasoning Layer (from ARTIFICIAL_REASONING_ARCHITECTURE.md)
```
src/reasoning/
- Implements deterministic logic
- No reliance on LLM reasoning
- Clear separation from articulation
```

#### 2. Classification System (from LAW_CLASSIFICATION_SYSTEM.md)
```
src/classification/
- SR number mapping
- Article range identification
- Multi-layer tagging
- Relationship strength (STRONG/MEDIUM/WEAK)
```

#### 3. Clean Separation
```
Reasoning → produces structured answer
     ↓
Articulation → uses Apertus to express naturally
     ↓
Interface → delivers to user
```

### Implementation Priority for Hackathon

#### Phase 1: Core (Friday Morning)
```
1. src/classification/sr_classifier.py
2. src/data_access/fedlex_loader.py
3. src/retrieval/vector_rag.py
4. src/articulation/apertus_client.py
```

#### Phase 2: Reasoning (Friday Afternoon)
```
1. src/reasoning/rule_engine.py
2. src/classification/relationships.py
3. src/retrieval/graph_rag.py
```

#### Phase 3: Polish (Friday Night/Saturday)
```
1. src/interfaces/cli/main.py
2. tests/scenarios/
3. Demo preparation
```

### Makefile for Quick Access

```makefile
# LAWAST Makefile
.PHONY: help setup demo test clean

help:
	@echo "LAWAST - Legal AI with Syntax Trees"
	@echo "===================================="
	@echo "make setup   - Set up project structure"
	@echo "make extract - Extract target laws"
	@echo "make build   - Build graph and embeddings"
	@echo "make demo    - Run demo"
	@echo "make test    - Run tests"

setup:
	mkdir -p src/{reasoning,classification,articulation,retrieval}
	mkdir -p src/{data_access,core/entities,core/use_cases,interfaces}
	mkdir -p data/{laws/{employment,rental,credit},graph,embeddings,cache}
	mkdir -p tests/{unit,integration,scenarios}
	mkdir -p scripts docs notebooks

extract:
	python scripts/extract_target_laws.py

build:
	python scripts/build_classification.py
	python scripts/generate_graph.py
	python scripts/compute_embeddings.py

demo:
	python scripts/demo.py

test:
	pytest tests/ -v

run-cli:
	python -m src.interfaces.cli.main

run-api:
	uvicorn src.interfaces.api.app:app --reload
```

### Benefits for Judges

1. **Clear Architecture**: Follows documented design
2. **SOLID Principles**: Clean separation of concerns
3. **Easy to Navigate**: Logical folder structure
4. **Quick Demo**: `make demo` works immediately
5. **Professional**: Shows planning and architecture skills

This structure directly implements our two architecture documents while keeping it clean and navigable for the hackathon judges!