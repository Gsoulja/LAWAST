# TASK-008: Unified Content Extraction Pipeline [EPIC]

**Status**: BACKLOG
**Priority**: CRITICAL
**Type**: EPIC
**Created**: 2024-01-24
**Total Effort**: 10-12 days

## Description
Implement a unified HTML content extraction pipeline that processes Fedlex HTML files in a single pass to extract taxonomy, articles, and cross-references. This is critical for LAWAST to provide actual legal analysis capabilities.

## Business Value
- **Enables Core Functionality**: Without this, LAWAST cannot provide legal analysis
- **Efficiency**: Single pass through 139K HTML files instead of multiple
- **Complete Knowledge Graph**: Adds both structure (taxonomy) and content (articles)
- **RAG Enablement**: Provides data for Graph, Vector, and AST RAG components

## Sub-tasks
- [ ] TASK-008.1: Unified HTML Parser (2 days)
- [ ] TASK-008.2: Taxonomy Extraction (2 days)
- [ ] TASK-008.3: Article Extraction (2 days)
- [ ] TASK-008.4: Reference Resolution (1 day)
- [ ] TASK-008.5: Neo4j Storage Pipeline (2 days)
- [ ] TASK-008.6: Vector Indexing (2 days)
- [ ] TASK-008.7: Testing & Validation (1 day)

## Technical Approach

### Unified Extractor Architecture
```python
class UnifiedContentExtractor:
    """Single-pass extraction of all content types"""

    def process_html_file(self, html_path: str):
        # Parse HTML once
        soup = self.parse_html(html_path)

        # Extract everything in one pass
        result = {
            'taxonomy': self.extract_taxonomy(soup),
            'articles': self.extract_articles(soup),
            'references': self.extract_references(soup),
            'metadata': self.extract_metadata(soup)
        }

        # Store in Neo4j
        self.store_to_graph(result)

        # Create embeddings
        self.create_embeddings(result['articles'])

        return result
```

## What Gets Extracted

### Taxonomy & Hierarchy
- Legal domains (Civil, Criminal, Administrative)
- Hierarchical structure (Book → Title → Chapter → Section)
- SR classification numbers
- Subject categories

### Article Content
- Article numbers (1, 1a, 1bis, 335b, etc.)
- Titles in all languages
- Full text with structure
- Paragraphs and subsections

### Cross-References
- Internal references (same law)
- External references (other laws)
- Version-specific citations
- Hierarchical references

## Processing Strategy

### Batch Processing Pipeline
```
1. Load 1000 HTML files
2. Parse and extract content
3. Validate extraction results
4. Store to Neo4j in batch
5. Create vector embeddings
6. Checkpoint progress
7. Repeat until complete
```

### Performance Targets
- 100 HTML files/minute minimum
- Memory usage < 4GB
- Checkpoint every 1000 files
- Full recovery from failures

## Implementation Steps

### Phase 1: Parser (Days 1-2)
1. Build robust HTML parser
2. Handle multiple HTML formats
3. Implement caching layer
4. Add error recovery

### Phase 2: Extractors (Days 3-6)
1. Taxonomy extractor with hierarchy detection
2. Article extractor with structure preservation
3. Reference extractor with pattern matching
4. Language-specific rules

### Phase 3: Storage (Days 7-9)
1. Batch Neo4j operations
2. Vector embedding generation
3. Relationship creation
4. Index optimization

### Phase 4: Testing (Days 10-12)
1. Unit tests for each component
2. Integration testing
3. Performance benchmarking
4. Validation against sample data

## Dependencies & Resources

### New Components Needed
```
src/extractors/
├── unified_extractor.py       # Main orchestrator
├── html_parser.py             # Robust HTML parsing
├── taxonomy_extractor.py      # Hierarchy extraction
├── article_extractor.py       # Content extraction
└── storage_pipeline.py        # Batch storage
```

### Existing Resources to Reuse
- `HTMLReferenceExtractor` - HTML parsing patterns
- `ArticleNode` class - Graph schema
- `BatchProcessor` - Checkpoint management
- `RelationshipBuffer` - Efficient relationship creation
- Neo4j connection infrastructure

### External Libraries
- BeautifulSoup4 - HTML parsing
- lxml - Fast XML processing
- sentence-transformers - Embeddings
- langdetect - Language detection

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| 139K files scale | HIGH | Batch processing, checkpointing |
| HTML format variations | HIGH | Multiple parser strategies |
| Memory constraints | MEDIUM | Streaming, batch limits |
| Complex numbering | MEDIUM | Flexible patterns, validation |

## Success Criteria
- [ ] All HTML files processed successfully
- [ ] Taxonomy fully extracted and navigable
- [ ] Articles extracted with proper structure
- [ ] Cross-references resolved
- [ ] Vector search functional
- [ ] Performance targets met
- [ ] Tests passing with >90% coverage

## Example Output

### Extracted Article with Taxonomy
```json
{
  "uri": "https://fedlex.data.admin.ch/eli/cc/24/233_245_233/art_1",
  "number": "1",
  "law_uri": "https://fedlex.data.admin.ch/eli/cc/24/233_245_233",
  "taxonomy": {
    "domain": "Civil Law",
    "book": "First Part: Law of Persons",
    "title": "Natural Persons",
    "chapter": "Personality"
  },
  "title": {
    "de": "Persönlichkeit im Allgemeinen",
    "fr": "Personnalité en général",
    "it": "Personalità in genere"
  },
  "content": {
    "de": "Die Persönlichkeit beginnt...",
    "fr": "La personnalité commence...",
    "it": "La personalità incomincia..."
  },
  "references": ["Art. 31 ZGB", "Art. 54 OR"],
  "embedding": [0.123, 0.456, ...]
}
```

## Next Steps After Completion
1. Enable semantic search across articles
2. Build legal reasoning with full content
3. Implement taxonomy-based navigation
4. Deploy complete RAG system
5. Begin providing actual legal analysis

## Notes
- Critical path item - blocks all legal analysis features
- Unified approach saves ~50% processing time
- Must be completed before LAWAST can be functional
- Consider parallel processing for performance