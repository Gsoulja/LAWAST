# LAWAST - Legal AI with Syntax Trees
### An Intelligent Swiss Legal Assistant System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-v3.10+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-concept-orange.svg)]()

## 🎯 Overview

LAWAST (Legal AI With Abstract Syntax Trees) is an advanced legal intelligence system that combines Graph RAG, AST parsing, and intelligent agent reasoning to provide accurate, context-aware legal guidance for Swiss federal law. Unlike traditional legal search systems, LAWAST engages in intelligent dialogue to understand complete context before providing comprehensive legal advice.

## 🚀 Key Features

- **Multi-Modal Intelligence**: Combines Graph RAG, Vector RAG, and AST RAG for comprehensive understanding
- **Progressive Context Building**: Asks clarifying questions to build complete understanding
- **Chain-of-Thought Reasoning**: Applies legal logic step-by-step
- **Multilingual Support**: Works with German, French, Italian, Romansh, and English
- **Temporal Awareness**: Understands law evolution and version history
- **Relationship Intelligence**: Maps complex relationships between laws, amendments, and treaties

## 📊 Data Foundation

The system operates on two comprehensive Swiss legal datasets:

### Fedlex Metadata Repository (`fedlex/`)
- **Size**: 5.6GB
- **Files**: ~305,440 JSON documents
- **Content**: Structured metadata for all Swiss federal publications
- **Coverage**: Laws, ordinances, treaties, federal gazette, consultation procedures

### Fedlex Assets Repository (`fedlex-assets/`)
- **Size**: 18GB
- **Content**: HTML manifestations of legal texts
- **Languages**: DE, FR, IT, RM, EN
- **Structure**: Hierarchical organization by date and language

## 🏗️ System Architecture

```
┌─────────────────────────────────────────┐
│           User Interface Layer          │
│         (Conversational Agent)          │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│         Intelligent Agent System         │
│   (Question Planning & Context Tree)    │
└────────────────┬────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│          Reasoning Engine               │
│    (Chain-of-Thought & Analysis)        │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┬────────────┐
        │                 │            │
┌───────▼──────┐ ┌────────▼──────┐ ┌───▼────┐
│  Graph RAG   │ │   AST RAG     │ │Vector  │
│(Relationships)│ │  (Structure)  │ │  RAG   │
└───────┬──────┘ └────────┬──────┘ └───┬────┘
        │                 │            │
┌───────▼─────────────────▼────────────▼────┐
│           Knowledge Base                   │
│   (Neo4j + Vector DB + AST Store)         │
└────────────────────────────────────────────┘
```

## 💡 How It Works

### 1. Initial Question Analysis
When you ask a legal question, LAWAST doesn't immediately search for answers. Instead, it:
- Analyzes your question to understand intent
- Identifies missing critical information
- Plans an efficient clarification strategy

### 2. Progressive Context Building
The system engages in intelligent dialogue:
- Asks focused, relevant questions one at a time
- Builds a context tree from your answers
- Adapts follow-up questions based on previous responses

### 3. Multi-System Analysis
With complete context, LAWAST leverages:
- **Graph RAG**: Finds relationships between laws
- **AST RAG**: Understands document structure and logic
- **Vector RAG**: Identifies semantically similar content

### 4. Comprehensive Answer Generation
Finally, it provides:
- Complete legal analysis specific to your situation
- Precise citations and article references
- Step-by-step reasoning explanation
- Practical recommendations and next steps

## 🔧 Technical Requirements

### Minimum System Requirements
- **CPU**: 8 cores
- **RAM**: 32GB
- **Storage**: 100GB SSD
- **OS**: Linux/macOS/Windows
- **Python**: 3.10+

### Recommended Production Setup
- **CPU**: 16+ cores
- **RAM**: 64GB
- **Storage**: 250GB NVMe SSD
- **GPU**: NVIDIA RTX 3060 or better (optional, for embeddings)

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/LAWAST.git
cd LAWAST

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download and setup databases
python setup_databases.py

# Initialize the knowledge base
python initialize_knowledge_base.py
```

## 📖 Documentation

- [System Architecture](./GRAPH_RAG_ARCHITECTURE.md) - Detailed technical architecture
- [Data Connection Guide](./FEDLEX_DATA_CONNECTION_GUIDE.md) - How metadata connects to content
- [API Documentation](./docs/api.md) - API reference and examples
- [Development Guide](./docs/development.md) - Contributing and development setup

## 🎮 Usage Example

```python
from lawast import LegalAssistant

# Initialize the assistant
assistant = LegalAssistant()

# Ask a question
response = assistant.query(
    "Can I terminate an employee who violated data protection?"
)

# The system will:
# 1. Ask clarifying questions (type of violation, employee role, etc.)
# 2. Build context through dialogue
# 3. Provide comprehensive legal analysis with citations

print(response.answer)
print(response.citations)
print(response.reasoning_chain)
```

## 🗺️ Roadmap

### Phase 1: Foundation ✅
- [x] Data analysis and architecture design
- [x] Graph schema definition
- [x] System documentation

### Phase 2: Core Development 🚧
- [ ] Graph database setup (Neo4j)
- [ ] AST parser implementation
- [ ] Vector embedding pipeline
- [ ] Basic RAG integration

### Phase 3: Intelligence Layer
- [ ] Agent system development
- [ ] Context tree implementation
- [ ] Chain-of-thought reasoning
- [ ] Question planning algorithm

### Phase 4: Integration
- [ ] Conversational interface
- [ ] Multi-language support
- [ ] API development
- [ ] Testing framework

### Phase 5: Optimization
- [ ] Performance tuning
- [ ] Caching layer
- [ ] Incremental updates
- [ ] Production deployment

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](./CONTRIBUTING.md) for details.

### Areas for Contribution
- Legal domain expertise for validation
- NLP improvements for Swiss legal language
- Frontend development for user interface
- Testing and quality assurance
- Documentation and translations

## 📊 Project Status

Current Status: **Concept & Architecture Phase**

- ✅ Data analysis complete
- ✅ System architecture designed
- ✅ Technical documentation created
- 🚧 Prototype development in progress
- ⏳ Full implementation pending

## 🔬 Research Foundation

This project builds on cutting-edge research in:
- Graph-based retrieval augmented generation
- Legal document analysis with ASTs
- Progressive context building in dialogue systems
- Chain-of-thought reasoning for legal AI

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

**Note**: The underlying Swiss federal legal data has its own licensing requirements:
- Fedlex data usage requirements: [fedlex.admin.ch/broadcasters](https://www.fedlex.admin.ch/broadcasters)
- Repository data license: CC BY-NC-SA 4.0 (non-commercial use only)

## 🙏 Acknowledgments

- Swiss Federal Chancellery for providing open legal data
- [Droid Factory](https://github.com/droid-f) for maintaining fedlex repositories
- Open source community for foundational libraries

## 📞 Contact

- **Project Lead**: [Your Name]
- **Email**: your.email@example.com
- **Issues**: [GitHub Issues](https://github.com/yourusername/LAWAST/issues)

## ⚠️ Disclaimer

LAWAST is a research project and should not be used as a substitute for professional legal advice. Always consult with qualified legal professionals for official legal guidance.

---

<p align="center">
Built with ❤️ for accessible legal intelligence
</p>

<p align="center">
<sub>Making Swiss law understandable through AI</sub>
</p>