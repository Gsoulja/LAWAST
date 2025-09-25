# TASK-008.5: Neo4j Storage Pipeline

**Status**: IN-PROGRESS
**Priority**: CRITICAL
**Type**: feature
**Parent**: TASK-008
**Estimated Effort**: 2 days
**Created**: 2024-01-24
**Started**: 2025-09-24
**Assigned**: Unassigned
**Analysis Completed**: 2025-09-24

## Description
Build efficient batch storage pipeline for Neo4j that creates nodes and relationships for taxonomy, articles, and references. Must handle 500K+ articles with proper indexing, deduplication, and transaction management.

## Acceptance Criteria
- [ ] Batch creates taxonomy nodes
- [ ] Batch creates article nodes
- [ ] Creates all relationship types
- [ ] Handles duplicates correctly
- [ ] Transaction management with rollback
- [ ] Checkpoint/resume capability
- [ ] Performance: 1000+ nodes/second
- [ ] Memory efficient batching
- [ ] All tests pass
- [ ] Documentation complete

## Technical Implementation

### Storage Pipeline
```python
class Neo4jStoragePipeline:
    def __init__(self, batch_size=1000):
        self.connection = get_connection()
        self.batch_size = batch_size
        self.checkpoint_manager = CheckpointManager()

    def store_extracted_content(self, content: ExtractedContent):
        # Phase 1: Create taxonomy nodes
        self.create_taxonomy_nodes(content.taxonomy)

        # Phase 2: Create article nodes
        self.create_article_nodes(content.articles)

        # Phase 3: Create relationships
        self.create_relationships(content.relationships)

        # Checkpoint progress
        self.checkpoint_manager.save()

    def create_article_nodes(self, articles: List[Article]):
        # Batch create with UNWIND
        query = '''
        UNWIND $batch as article
        MERGE (a:Article {uri: article.uri})
        SET a += article.properties
        RETURN a.uri as created
        '''

        for batch in chunks(articles, self.batch_size):
            params = {'batch': [a.to_dict() for a in batch]}
            self.connection.execute_write(query, params)
```

## Node Types to Create

### Taxonomy Nodes
```cypher
CREATE (d:Domain {name: $name})
CREATE (b:Book {number: $number, title: $title})
CREATE (c:Chapter {number: $number, title: $title})
CREATE (s:Section {number: $number, title: $title})
```

### Article Nodes
```cypher
CREATE (a:Article {
  uri: $uri,
  number: $number,
  number_normalized: $norm_number,
  law_uri: $law_uri,
  title_de: $title_de,
  title_fr: $title_fr,
  title_it: $title_it,
  content: $content,
  date_created: $date
})
```

## Relationships to Create
```cypher
// Taxonomy relationships
(domain)-[:CONTAINS]->(book)
(book)-[:CONTAINS]->(chapter)
(chapter)-[:CONTAINS]->(section)
(section)-[:CONTAINS]->(article)

// Article relationships
(law)-[:HAS_ARTICLE]->(article)
(article)-[:REFERENCES]->(other_article)
(article)-[:CITES]->(external_law)
(article)-[:FOLLOWS]->(previous_article)
```

## Batch Operations

### Efficient Batching
```python
def batch_create_nodes(nodes, batch_size=1000):
    query = '''
    UNWIND $batch as node
    CALL apoc.create.node(node.labels, node.properties)
    YIELD node as created
    RETURN count(created)
    '''

    total = 0
    for batch in chunks(nodes, batch_size):
        result = execute_write(query, {'batch': batch})
        total += result[0]['count']

    return total
```

### Transaction Management
```python
def with_transaction(func):
    def wrapper(*args, **kwargs):
        tx = begin_transaction()
        try:
            result = func(*args, **kwargs)
            tx.commit()
            return result
        except Exception as e:
            tx.rollback()
            raise
    return wrapper
```

## Performance Optimization
- Use UNWIND for batch operations
- Create indexes before bulk insert
- Use MERGE to handle duplicates
- Periodic ANALYZE for statistics
- Connection pooling

## Testing Requirements
- Test batch creation at scale
- Verify deduplication
- Test transaction rollback
- Memory usage tests
- Checkpoint recovery tests

## Success Metrics
- 1000+ nodes/second throughput
- < 4GB memory for 10K batch
- Zero data loss on failure
- Successful recovery from checkpoint

## Technical Analysis (Auto-generated 2025-09-24)

### Existing Resources Found
- **Components**:
  - `Neo4jConnectionManager` with pooling, retry logic, batch_write (src/data_access/neo4j_connection.py)
  - `GraphBuilder` with batch_create_nodes, batch_create_relationships (src/data_access/graph_builder.py)
  - `BatchProcessor` with checkpoint/resume capability (src/data_access/batch_processor.py)
  - `ProcessingCheckpoint` dataclass for recovery (src/data_access/batch_processor.py:20-59)
- **Services**:
  - Connection pooling with 50 max connections
  - Retry logic with exponential backoff
  - Transaction management with execute_write
- **APIs**:
  - batch_write() for bulk operations
  - UNWIND support already in graph_builder.py:176
- **Database**:
  - 10 Law nodes, 43 Expression nodes already exist
  - Schema initialization in scripts/init_neo4j_schema.py
- **Utilities**:
  - Extraction modules (TASK-008.1-4) completed
  - UnifiedHtmlParser, TaxonomyExtractor, ArticleExtractor, ReferenceResolver

### Dependencies Required
- **Frontend packages**: N/A (backend only)
- **Backend packages**:
  - neo4j>=5.14.0 (already installed)
  - python-dotenv>=1.0.0 (already installed)
  - No new dependencies needed
- **Database migrations**:
  - Create indexes on Article.uri, Article.number_normalized
  - Add constraints for new node types (Domain, Book, Chapter, Section)
- **Docker services**: Neo4j (already configured)

### Impact Assessment
#### Files to Modify
- `src/data_access/__init__.py`: Export new Neo4jStoragePipeline
- `src/extractors/__init__.py`: Add ExtractedContent dataclass

#### Files to Create
- `src/data_access/storage_pipeline.py`: Main pipeline implementation

#### Components Affected
- `GraphBuilder`: LOW - Can reuse existing batch methods
- `BatchProcessor`: LOW - Can extend for article processing
- Extraction modules: MEDIUM - Need standardized output format

#### API Changes
- None - New functionality only

#### Database Changes
- New node types: Domain, Book, Chapter, Section, Article
- New relationships: CONTAINS, HAS_ARTICLE, REFERENCES, CITES, FOLLOWS
- Estimated 500K+ nodes, 2M+ relationships

### Implementation Checklist
Based on CLAUDE.md principles:
- [x] Reuse existing Neo4jConnectionManager instead of creating new
- [x] Extend BatchProcessor rather than duplicate checkpoint logic
- [x] Follow SOLID principles - separate concerns
- [ ] Maintain backwards compatibility - no breaking changes
- [ ] Add proper error handling with rollback
- [ ] Include progress tracking/reporting
- [ ] Write self-documenting code with type hints

### Risk Analysis
- **Risk Level**: MEDIUM
- **Main Risks**:
  - Memory overflow with large batches: Use streaming, configurable batch sizes
  - Incomplete checkpoint recovery: Extend existing BatchProcessor
  - Performance < 1000 nodes/sec: Use UNWIND, optimize batch size
  - Data duplication: Use MERGE instead of CREATE

### Estimated Effort
- Original: 2 days
- Adjusted: 2 days
- Reason: Can leverage significant existing infrastructure