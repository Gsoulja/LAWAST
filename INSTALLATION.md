# LAWAST Installation Guide

## Prerequisites

- Python 3.8 or higher
- Docker and Docker Compose
- 8GB+ RAM recommended
- 30GB+ free disk space for data

## Quick Setup

### 1. Clone and Setup Virtual Environment

```bash
# Clone repository (if not already done)
git clone <repository-url>
cd LAWAST

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate     # On Windows
```

### 2. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=lawast2024  # CHANGE THIS!
NEO4J_DATABASE=neo4j

# Batch Processing
BATCH_SIZE=1000
CHECKPOINT_FILE=processing_checkpoint.json

# Optional: Hugging Face API
# HUGGINGFACE_API_KEY=your_key_here
```

### 4. Start Neo4j Database

```bash
# Start Neo4j container
docker-compose up -d

# Verify it's running
docker ps | grep neo4j

# Check logs if needed
docker logs lawast-neo4j
```

### 5. Initialize Database Schema

```bash
# Run schema initialization
python scripts/init_neo4j_schema.py

# Access Neo4j Browser (optional)
# Open http://localhost:7474 in browser
# Login with neo4j/lawast2024
```

## Running Tasks

### TASK-003: JSON Parser & Node Creator

**Status**: In Progress

```bash
# Implementation needed - see kanban/in-progress/TASK-003-json-parser-node-creator.md
# Will parse JSON files and create nodes
```

### TASK-004: Relationship Extractor

**Status**: Ready (requires TASK-003 nodes)

```bash
# Test with limited files
python scripts/run_relationship_extraction.py --limit 100

# Full extraction (after TASK-003)
python scripts/run_relationship_extraction.py

# With custom options
python scripts/run_relationship_extraction.py \
  --directory fedlex \
  --batch-size 10000 \
  --skip-validation
```

## Required Packages

### Core Dependencies
- `huggingface-hub>=0.19.0` - Apertus client
- `click>=8.1.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting and progress

### Graph Database
- `neo4j>=5.14.0` - Neo4j Python driver
- `python-dotenv>=1.0.0` - Environment configuration

### JSON Processing
- `ijson>=3.2.0` - Streaming JSON parser for large files

### Testing
- `pytest>=7.4.0` - Test framework
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.11.0` - Mocking utilities

## Verification

### Check Installation

```bash
# Run tests
pytest tests/test_relationship_extractor.py -v

# Check Neo4j connection
python -c "from src.data_access.neo4j_connection import get_connection; get_connection().driver.verify_connectivity()"

# Run setup script (alternative)
./scripts/setup_environment.sh
```

### Check Data

Ensure you have the Fedlex data:
```bash
# Check JSON metadata (5.6GB)
ls -la fedlex/eli/cc/ | head

# Check HTML content (18GB - if available)
ls -la fedlex-assets/eli/cc/ | head
```

## Troubleshooting

### Neo4j Connection Issues

If you can't connect to Neo4j:
```bash
# Check if container is running
docker ps | grep neo4j

# Restart container
docker-compose restart neo4j

# Check logs
docker logs lawast-neo4j --tail 50

# Reset password (if needed)
docker exec -it lawast-neo4j cypher-shell -u neo4j -p neo4j \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'lawast2024'"
```

### Memory Issues

If you encounter memory problems:
```bash
# Adjust Neo4j heap in docker-compose.yml
NEO4J_server_memory_heap_max__size=2G  # Reduce if needed
NEO4J_server_memory_pagecache_size=1G  # Reduce if needed

# Restart container
docker-compose down
docker-compose up -d
```

### Missing Dependencies

```bash
# If ijson is not installed
pip install ijson>=3.2.0

# If tests fail due to missing pytest
pip install pytest pytest-cov pytest-mock

# Update all packages
pip install --upgrade -r requirements.txt
```

## Development Tools (Optional)

For better development experience, install:

```bash
# Code formatting
pip install black

# Linting
pip install flake8

# Type checking
pip install mypy

# Run formatting
black src/

# Run linting
flake8 src/

# Run type checking
mypy src/
```

## Next Steps

1. Complete TASK-003 implementation (JSON parser)
2. Run TASK-003 to populate Neo4j with nodes
3. Run TASK-004 to create relationships
4. Validate graph integrity
5. Proceed with TASK-005 (HTML cross-reference mining)

## Support

- Check `kanban/` directory for task status
- See `docs/` for technical documentation
- Review test files for usage examples