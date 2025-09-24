# Neo4j Graph Database Setup Guide

## Overview

This document provides comprehensive instructions for setting up and managing the Neo4j graph database for the LAWAST system. The graph database stores Swiss federal legal data with complex relationships between laws, versions, articles, and cross-references.

## Table of Contents
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Installation](#installation)
- [Schema](#schema)
- [Operations](#operations)
- [Backup & Restore](#backup--restore)
- [Troubleshooting](#troubleshooting)
- [Common Cypher Queries](#common-cypher-queries)

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Neo4j with Docker
```bash
docker-compose up -d
```

### 3. Initialize Schema
```bash
python scripts/init_neo4j_schema.py
```

### 4. Verify Setup
```bash
python scripts/init_neo4j_schema.py --report-only
```

### 5. Access Neo4j Browser
Open http://localhost:7474 in your browser
- Username: neo4j
- Password: lawast2024 (or value from .env)

## Architecture

### Components

1. **Connection Manager** (`neo4j_connection.py`)
   - Connection pooling
   - Retry logic with exponential backoff
   - Health checks
   - Singleton pattern for global access

2. **Graph Schema** (`graph_schema.py`)
   - Node type definitions
   - Relationship type definitions
   - Constraints and indexes
   - Data validation

3. **Graph Builder** (`graph_builder.py`)
   - CRUD operations
   - Batch processing
   - Relationship management
   - Query operations

4. **Batch Processor** (`batch_processor.py`)
   - Large-scale data processing
   - Checkpointing for recovery
   - Parallel processing
   - Progress tracking

## Installation

### Docker Setup (Recommended)

1. **Ensure Docker is installed:**
```bash
docker --version
```

2. **Start Neo4j container:**
```bash
docker-compose up -d
```

3. **Check container status:**
```bash
docker ps | grep lawast-neo4j
```

4. **View logs:**
```bash
docker logs lawast-neo4j
```

### Native Installation

1. **Download Neo4j Community Edition:**
   - Visit https://neo4j.com/download-center/
   - Download version 5.x

2. **Install and configure:**
```bash
# Set environment variables
export NEO4J_HOME=/path/to/neo4j
export PATH=$NEO4J_HOME/bin:$PATH

# Configure memory (conf/neo4j.conf)
server.memory.heap.initial_size=2g
server.memory.heap.max_size=4g
server.memory.pagecache.size=2g
```

3. **Start Neo4j:**
```bash
neo4j start
```

## Schema

### Node Types

#### Law Node
```cypher
(:Law {
  uri: String,           // Unique identifier
  sr_number: String,     // SR classification number
  title_de: String,      // German title
  title_fr: String,      // French title
  title_it: String,      // Italian title
  date_enacted: Date,    // Enactment date
  date_modified: Date,   // Last modification
  type: String,          // Law type
  status: String         // Current status
})
```

#### Version Node
```cypher
(:Version {
  uri: String,                  // Unique identifier
  law_uri: String,              // Reference to law
  date_applicable: Date,        // Start date
  date_end_applicable: Date,    // End date (optional)
  version_number: String        // Version identifier
})
```

#### Article Node
```cypher
(:Article {
  uri: String,         // Unique identifier
  law_uri: String,     // Reference to law
  number: String,      // Article number (e.g., "1", "1a", "335b")
  title: String,       // Article title
  content_uri: String, // Reference to content
  section: String,     // Section name
  chapter: String      // Chapter name
})
```

#### Language Node
```cypher
(:Language {
  code: String,  // DE, FR, IT, RM, EN
  name: String   // Full language name
})
```

#### Manifestation Node
```cypher
(:Manifestation {
  uri: String,        // Unique identifier
  format: String,     // html, pdf, xml, docx, json
  file_path: String,  // Path to file
  file_size: Integer, // Size in bytes
  checksum: String    // File checksum
})
```

### Relationship Types

- `HAS_VERSION`: Law → Version
- `SUPERSEDES`: Version → Version (newer → older)
- `EXPRESSED_IN`: Version → Language
- `MANIFESTED_AS`: Language → Manifestation
- `CONTAINS`: Law → Article
- `AMENDS`: Law → Law
- `REFERENCES`: Law/Article → Law/Article

### Indexes and Constraints

#### Unique Constraints
- Law.uri
- Version.uri
- Article.uri
- Language.code
- Manifestation.uri

#### Performance Indexes
- Law.sr_number
- Law.date_enacted
- Version.date_applicable
- Article.number
- (Law.uri, Article.number) - Composite

## Operations

### Basic CRUD Operations

#### Create a Law Node
```python
from src.data_access.graph_builder import GraphBuilder
from src.data_access.graph_schema import LawNode
from datetime import datetime

gb = GraphBuilder()

law = LawNode(
    uri="https://fedlex.data.admin.ch/eli/cc/1999/404",
    sr_number="101",
    title_de="Bundesverfassung",
    title_fr="Constitution fédérale",
    date_enacted=datetime(1999, 4, 18)
)

result = gb.create_law_node(law)
```

#### Create Relationships
```python
# Create HAS_VERSION relationship
gb.create_has_version(law_uri, version_uri)

# Create SUPERSEDES chain
gb.build_version_chains(law_uri)

# Create cross-reference
gb.create_references(from_uri, to_uri, context="Art. 12")
```

### Batch Processing

#### Process Large Datasets
```python
from src.data_access.batch_processor import BatchProcessor

processor = BatchProcessor(batch_size=1000)

# Process files with checkpointing
def process_json_file(file_path):
    # Your processing logic here
    return {"statistics": {"nodes_created": 1}}

checkpoint = processor.process_files(
    file_paths=json_files,
    processor_func=process_json_file,
    resume=True,  # Resume from checkpoint if exists
    save_interval=100
)
```

#### Batch Create Nodes
```python
nodes = [
    LawNode(uri=f"law_{i}", sr_number=str(i))
    for i in range(10000)
]

count = gb.batch_create_nodes(nodes, batch_size=1000)
```

### Query Operations

#### Get Law Information
```python
# By URI
law = gb.get_law_by_uri("https://fedlex.data.admin.ch/eli/cc/1999/404")

# By SR number
law = gb.get_law_by_sr_number("101")

# Get all versions
versions = gb.get_law_versions(law_uri)

# Get all articles
articles = gb.get_law_articles(law_uri)
```

## Backup & Restore

### Backup Database

#### Using Neo4j Admin
```bash
# Stop database
docker-compose stop neo4j

# Create backup
docker run --rm \
  -v $(pwd)/data/neo4j:/data \
  -v $(pwd)/backups:/backups \
  neo4j:5-community \
  neo4j-admin database dump neo4j --to-path=/backups

# Restart database
docker-compose start neo4j
```

#### Using Cypher Export
```cypher
// Export all nodes and relationships
CALL apoc.export.cypher.all(
  "backup.cypher",
  {
    format: "cypher-shell",
    useOptimizations: {type: "UNWIND_BATCH", unwindBatchSize: 1000}
  }
)
```

### Restore Database

#### From Admin Backup
```bash
# Stop database
docker-compose stop neo4j

# Restore backup
docker run --rm \
  -v $(pwd)/data/neo4j:/data \
  -v $(pwd)/backups:/backups \
  neo4j:5-community \
  neo4j-admin database load neo4j --from-path=/backups/neo4j.dump

# Start database
docker-compose start neo4j
```

#### From Cypher Export
```bash
cat backup.cypher | docker exec -i lawast-neo4j cypher-shell -u neo4j -p lawast2024
```

## Troubleshooting

### Common Issues

#### Connection Refused
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Check logs
docker logs lawast-neo4j

# Restart container
docker-compose restart neo4j
```

#### Memory Issues
```bash
# Increase memory in docker-compose.yml
environment:
  - NEO4J_server_memory_heap_max__size=8G
  - NEO4J_server_memory_pagecache_size=4G

# Or adjust system swap
sudo sysctl vm.swappiness=10
```

#### Slow Queries
```cypher
// Check query plan
EXPLAIN <your query>

// Profile query execution
PROFILE <your query>

// Check missing indexes
SHOW INDEXES
```

#### Transaction Timeout
```python
# Increase timeout in connection
connection = Neo4jConnectionManager(
    connection_timeout=60  # 60 seconds
)
```

### Performance Tuning

#### Memory Configuration
```bash
# Calculate optimal settings
# Heap: 40% of available RAM
# Page Cache: 30% of available RAM
# Leave 30% for OS

# Example for 16GB RAM system:
NEO4J_server_memory_heap_max__size=6G
NEO4J_server_memory_pagecache_size=5G
```

#### Index Optimization
```cypher
// Create composite index for common queries
CREATE INDEX article_lookup IF NOT EXISTS
FOR (a:Article) ON (a.law_uri, a.number)

// Analyze index usage
CALL db.index.usage()
```

## Common Cypher Queries

### Administrative Queries

```cypher
// Database size
MATCH (n) RETURN count(n) AS node_count;
MATCH ()-[r]->() RETURN count(r) AS relationship_count;

// Node distribution
MATCH (n)
WITH labels(n)[0] AS label, count(n) AS count
RETURN label, count ORDER BY count DESC;

// Memory usage
CALL dbms.listPools();
```

### Legal Data Queries

```cypher
// Find law by SR number
MATCH (l:Law {sr_number: "101"})
RETURN l;

// Get law with all versions
MATCH (l:Law {sr_number: "101"})
MATCH (l)-[:HAS_VERSION]->(v:Version)
RETURN l, collect(v) AS versions
ORDER BY v.date_applicable DESC;

// Find laws that reference each other
MATCH (l1:Law)-[:REFERENCES]->(l2:Law)
RETURN l1.sr_number, l2.sr_number, count(*) AS reference_count
ORDER BY reference_count DESC
LIMIT 10;

// Get amendment chain
MATCH path = (amender:Law)-[:AMENDS*]->(original:Law {sr_number: "220"})
RETURN path;

// Find articles with most cross-references
MATCH (a:Article)-[:REFERENCES]->(:Article)
WITH a, count(*) AS ref_count
RETURN a.law_uri, a.number, ref_count
ORDER BY ref_count DESC
LIMIT 20;

// Temporal query - law version at specific date
MATCH (l:Law {sr_number: "101"})
MATCH (l)-[:HAS_VERSION]->(v:Version)
WHERE v.date_applicable <= date("2023-06-01")
  AND (v.date_end_applicable IS NULL OR v.date_end_applicable > date("2023-06-01"))
RETURN v;
```

### Maintenance Queries

```cypher
// Find orphaned nodes
MATCH (n)
WHERE NOT (n)-[]-()
RETURN labels(n)[0] AS type, count(n) AS count;

// Clean test data
MATCH (n) WHERE n.uri STARTS WITH "test_"
DETACH DELETE n;

// Verify relationship integrity
MATCH (v:Version)
WHERE NOT (v)<-[:HAS_VERSION]-(:Law)
RETURN count(v) AS orphaned_versions;
```

## Best Practices

1. **Always use MERGE for idempotent operations**
2. **Batch operations for large datasets (1000-5000 items per batch)**
3. **Use parameters in queries to prevent injection**
4. **Create indexes before bulk imports**
5. **Monitor memory usage during large operations**
6. **Implement checkpointing for long-running processes**
7. **Use connection pooling for concurrent access**
8. **Regular backups before major operations**

## Resources

- [Neo4j Documentation](https://neo4j.com/docs/)
- [Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- [APOC Procedures](https://neo4j.com/docs/apoc/current/)
- [Graph Data Science Library](https://neo4j.com/docs/graph-data-science/current/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)