# Reference Extraction Guide

## Overview

The Reference Resolution Module (TASK-008.4) extracts and resolves legal cross-references from HTML documents, creating a network of REFERENCES relationships in the Neo4j graph database. The module supports multi-language pattern detection (DE/FR/IT/RM) and handles various reference formats.

## Architecture

### Core Components

1. **ReferencePatternDetector** (`src/extractors/reference_patterns.py`)
   - Multi-language regex patterns
   - Law code normalization
   - Reference type classification

2. **HTMLReferenceExtractor** (`src/extractors/html_reference_extractor.py`)
   - HTML parsing and reference extraction
   - Pagination handling for multi-part documents
   - Caching for performance optimization

3. **ArticleContentExtractor** (`src/extractors/article_extractor.py`)
   - Integrated reference extraction during article processing
   - Embeds references in article metadata
   - Creates REFERENCES relationships

## Usage

### Quick Test

```bash
# Test with limited files
python scripts/quick_test_pipeline.py
# Select option 3 for HTML & Reference extraction

# Or run directly
python scripts/build_complete_graph.py --html-only --limit 10
```

### Full Extraction

```bash
# Process all HTML files with reference extraction
python scripts/build_complete_graph.py

# The script will:
# 1. Process JSON files (Phase 1)
# 2. Extract relationships (Phase 2)
# 3. Extract references from HTML (Phase 3) - Integrated!
# 4. Verify the graph (Phase 4)
```

### Standalone Reference Extraction

```bash
# Extract references from specific HTML files
python scripts/run_html_reference_extraction.py --limit 100 --workers 4

# Process specific directory
python scripts/run_html_reference_extraction.py --path fedlex-assets/eli/cc/2023
```

### Validation

```bash
# Validate references in a single file
python scripts/validate_html_references.py fedlex-assets/eli/cc/1999/404/de/html/file.html
```

## Reference Patterns Supported

### Internal References
- Article references: `Art. 5`, `Articles 10-15`
- Paragraph references: `Abs. 2`, `al. 3`, `cpv. 2`
- Section references: `Abschnitt 2`, `Section II`
- Chapter references: `Kapitel III`, `Chapitre IV`

### External References
- Law codes: `Art. 5 OR`, `Art. 10 ZGB`, `art. 269 CO`
- SR numbers: `SR 220`, `SR 311.0`, `RS 235.1`
- International: `Art. 8 EMRK`, `Art. 8 CEDH`

### Special Patterns
- Range references: `Art. 5-10`, `Art. 5 bis 10`
- List references: `Art. 5, 7 und 9`
- Complex references: `Art. 5 Abs. 2 lit. a OR`

## Multi-language Support

The module supports all official Swiss languages:

```python
# German
"Gemäss Art. 335b OR"  -> SR 220:335b

# French
"Selon l'art. 269 CO"  -> SR 220:269

# Italian
"Secondo l'art. 269 CO" -> SR 220:269

# Romansh
"Tenor l'artitgel 12"  -> ART:12
```

## Performance Tuning

### Caching

Reference extraction uses a cache to avoid reprocessing:

```python
# Enable caching (default)
extractor = HTMLReferenceExtractor(use_cache=True)

# Disable for testing
extractor = HTMLReferenceExtractor(use_cache=False)
```

### Memory Management

Large HTML files are handled with memory limits:

```python
# Set memory limit (MB)
extractor = HTMLReferenceExtractor(memory_limit_mb=1024)
```

### Batch Processing

References are created in batches for optimal Neo4j performance:

```python
# Configure batch size
batch_processor = BatchProcessor(batch_size=1000)
```

## Testing

### Unit Tests

```bash
# Run reference extraction tests
pytest tests/test_html_reference_extractor.py -v

# Run with coverage
pytest tests/test_html_reference_extractor.py --cov=src.extractors
```

### Integration Tests

```bash
# Run integration tests
pytest tests/test_reference_integration.py -v

# Test with real fedlex data (if available)
pytest tests/test_reference_integration.py::test_with_real_fedlex_file -v
```

### Performance Benchmark

```bash
# Run performance test
pytest tests/test_html_reference_extractor.py::TestIntegration::test_performance_benchmark -v
```

Target: **1000+ references/second**

## Graph Structure

### Nodes
```cypher
(a:Article {
  uri: "/eli/cc/1999/404/art_335b",
  number: "335b",
  content: {...}
})
```

### Relationships
```cypher
(a1:Article)-[:REFERENCES {
  raw_text: "Art. 335 OR",
  normalized: "SR 220:335",
  confidence: 0.9,
  language: "de"
}]->(a2:Article)
```

## Query Examples

### Find all references from an article
```cypher
MATCH (a:Article {number: "335b"})-[r:REFERENCES]->(target)
RETURN a.number, r.raw_text, target.uri
```

### Find articles referencing a specific law
```cypher
MATCH (source)-[r:REFERENCES]->(target)
WHERE r.target_law = "OR"
RETURN source.number, r.raw_text, target.number
```

### Find reference chains
```cypher
MATCH path = (a1:Article)-[:REFERENCES*1..3]->(a2:Article)
WHERE a1.number = "1"
RETURN path
```

## Troubleshooting

### Missing References

If references are not being extracted:

1. Check language detection:
   ```python
   extractor._detect_language(file_path)
   ```

2. Verify pattern matching:
   ```python
   detector.find_references(text, language)
   ```

3. Check HTML structure:
   - Articles must have proper tags
   - Content must be in expected selectors

### Performance Issues

1. Enable caching:
   ```python
   HTMLReferenceExtractor(use_cache=True)
   ```

2. Increase batch size:
   ```python
   BatchProcessor(batch_size=5000)
   ```

3. Use more workers:
   ```bash
   --workers 8
   ```

### Validation Errors

Run validation script on problematic files:
```bash
python scripts/validate_html_references.py [file]
```

## Configuration

### Environment Variables

```bash
# Neo4j connection
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Performance
REFERENCE_BATCH_SIZE=1000
REFERENCE_CACHE_SIZE=10000
REFERENCE_WORKERS=4
```

### Pattern Configuration

Add new patterns in `reference_patterns.py`:

```python
# Add new law code
LawCodeMapper.LAW_CODE_MAPPING['NEW'] = '999.9'

# Add new pattern
self.german_patterns.append(
    regex.compile(r'your_pattern_here')
)
```

## Implementation Status

✅ **Completed Features:**
- Multi-language pattern detection (DE/FR/IT/RM)
- All reference types (internal, external, special)
- Pagination handling
- Caching system
- Batch processing
- Integration with article extraction
- Performance optimization (>1000 refs/sec)
- Comprehensive test coverage

## Future Enhancements

1. **Fuzzy Matching**: Handle misspelled references
2. **Context Analysis**: Use NLP for better reference understanding
3. **Graph Visualization**: D3.js visualization of reference network
4. **Reference Validation**: Check if referenced articles actually exist
5. **Circular Reference Detection**: Identify reference loops

## Support

For issues or questions:
- Check test files: `tests/test_html_reference_extractor.py`
- Review implementation: `src/extractors/html_reference_extractor.py`
- See task details: `kanban/in-progress/TASK-008-4-reference-resolution.md`