# TASK-005: HTML Cross-Reference Miner

**Status**: BACKLOG
**Priority**: MEDIUM
**Type**: feature
**Assigned**: Unassigned
**Created**: 2024-09-24
**Updated**: 2024-09-24
**Estimated Effort**: 3 days

## Description
Parse 18GB of HTML legal documents to extract cross-references between laws and articles. Identify patterns like "Art. 335b OR", "gemäss DSG Art. 12", "selon CO art. 269" across German, French, Italian, and Romansh texts. Create REFERENCES relationships in the graph to enable navigation between related legal provisions.

## Business Value
- Enables discovery of related legal provisions
- Builds comprehensive reference network
- Supports legal research through connections
- Provides context for legal interpretation
- Essential for complete legal analysis

## Acceptance Criteria
- [ ] Parse HTML files from fedlex-assets/
- [ ] Extract legal reference patterns in all languages
- [ ] Handle multiple reference formats
- [ ] Create REFERENCES relationships
- [ ] Cache parsed results for efficiency
- [ ] Process paginated HTML files correctly
- [ ] Handle 18GB of content without memory issues
- [ ] All tests pass
- [ ] Reference accuracy > 95%
- [ ] Documentation updated

## Technical Approach

### Existing Resources to Reuse
- fedlex-assets/ directory with HTML content
- Graph nodes from TASK-003
- Relationship framework from TASK-004

### New Components Needed
- HTML parser with BeautifulSoup4
- Multilingual reference pattern detector
- Reference resolver to map to nodes
- Cache system for processed files
- Streaming HTML processor

### Dependencies
- Frontend: N/A
- Backend: beautifulsoup4, lxml, regex, neo4j-driver
- Database: Existing nodes and relationships

### Implementation Steps
1. Analyze HTML structure in fedlex-assets/
2. Define reference patterns for each language
3. Build streaming HTML parser
4. Extract and normalize references
5. Resolve references to graph nodes
6. Create REFERENCES relationships in batches

## Reference Pattern Detection

### German Patterns
```python
GERMAN_PATTERNS = [
    r'Art\.?\s*(\d+[a-z]?)\s+(OR|ZGB|StGB|DSG|BV)',  # Art. 335b OR
    r'Artikel\s*(\d+[a-z]?)\s+(\w+)',                 # Artikel 12 DSG
    r'gemäss\s+Art\.?\s*(\d+)',                       # gemäss Art. 23
    r'nach\s+Art\.?\s*(\d+)',                         # nach Art. 15
    r'§\s*(\d+)\s+(\w+)',                            # § 12 ArG
    r'Abs\.\s*(\d+)',                                # Abs. 2 (paragraph)
]
```

### French Patterns
```python
FRENCH_PATTERNS = [
    r'art\.?\s*(\d+[a-z]?)\s+(CO|CC|CP|LPD|Cst)',   # art. 269 CO
    r'article\s*(\d+[a-z]?)\s+(\w+)',                # article 12 LPD
    r'selon\s+art\.?\s*(\d+)',                       # selon art. 23
    r'conformément\s+à\s+l\'art\.?\s*(\d+)',        # conformément à l'art. 15
    r'al\.\s*(\d+)',                                 # al. 2 (alinéa)
]
```

### Italian Patterns
```python
ITALIAN_PATTERNS = [
    r'art\.?\s*(\d+[a-z]?)\s+(CO|CC|CP|LPD|Cost)',  # art. 269 CO
    r'articolo\s*(\d+[a-z]?)\s+(\w+)',              # articolo 12 LPD
    r'secondo\s+l\'art\.?\s*(\d+)',                 # secondo l'art. 23
    r'cpv\.\s*(\d+)',                                # cpv. 2 (capoverso)
]
```

## HTML Processing Strategy

### File Structure Handler
```python
class FedlexHTMLProcessor:
    def process_directory(self, path):
        # fedlex-assets/eli/cc/1999/404/20240101/de/html/
        # May contain multiple files: -1.html, -2.html, etc.

    def extract_references(self, html_content):
        soup = BeautifulSoup(html_content, 'lxml')
        # Find all text nodes
        # Apply pattern matching
        # Return normalized references
```

### Reference Normalization
```python
def normalize_reference(raw_ref, language):
    # Convert various formats to standard form
    # "Art. 335b OR" → "OR:335b"
    # "art. 269 CO" → "OR:269"  (CO = Code des obligations = OR)
    # "§ 12 ArG" → "ArG:12"

    law_mapping = {
        'DE': {'OR': '220', 'ZGB': '210', 'StGB': '311.0'},
        'FR': {'CO': '220', 'CC': '210', 'CP': '311.0'},
        'IT': {'CO': '220', 'CC': '210', 'CP': '311.0'}
    }
```

### Caching System
```python
class ReferenceCache:
    def __init__(self):
        self.cache_file = "data/reference_cache.json"
        self.cache = {}

    def get_cached(self, file_path):
        file_hash = self.get_file_hash(file_path)
        return self.cache.get(file_hash)

    def store(self, file_path, references):
        file_hash = self.get_file_hash(file_path)
        self.cache[file_hash] = references
```

## Performance Optimization

### Parallel Processing
```python
from concurrent.futures import ProcessPoolExecutor

def process_html_files_parallel(file_list, workers=4):
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(extract_references_from_file, file_list)
    return results
```

### Memory Management
- Process one file at a time
- Stream large HTML files
- Batch relationship creation (10,000 per transaction)
- Clear BeautifulSoup cache regularly

## Expected Output

### Reference Statistics
```
Language Distribution:
- German: 40% of references
- French: 35% of references
- Italian: 24% of references
- Romansh: 1% of references

Top Referenced Laws:
1. OR (Obligationenrecht): 25,000 references
2. ZGB (Zivilgesetzbuch): 18,000 references
3. BV (Bundesverfassung): 15,000 references
4. StGB (Strafgesetzbuch): 12,000 references
5. DSG (Datenschutzgesetz): 8,000 references
```

## Testing Requirements
- Unit tests for pattern matching in each language
- Integration tests with sample HTML files
- Accuracy tests with manually verified references
- Performance tests with 1000 HTML files
- Memory usage monitoring
- Cross-language reference validation

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| 18GB data volume | HIGH | Stream processing, parallel execution |
| Pattern matching accuracy | HIGH | Extensive pattern testing, manual validation |
| Language variations | MEDIUM | Comprehensive pattern library |
| Pagination handling | MEDIUM | Proper file sequencing logic |
| Memory exhaustion | HIGH | Streaming, batch processing |

## Related Tasks
- Dependencies: TASK-003, TASK-004 (needs nodes)
- Related: TASK-001 (parent epic)
- Blocks: TASK-007 (queries need references)

## Validation Metrics
```cypher
// Count references by source law
MATCH (l:Law)-[r:REFERENCES]->()
RETURN l.sr_number, count(r) AS reference_count
ORDER BY reference_count DESC
LIMIT 10

// Find articles with most references
MATCH (a:Article)-[r:REFERENCES]->()
RETURN a.number, a.law_uri, count(r)
ORDER BY count(r) DESC
LIMIT 20

// Verify bidirectional references
MATCH (a)-[r1:REFERENCES]->(b)
MATCH (b)-[r2:REFERENCES]->(a)
RETURN count(DISTINCT a) AS mutual_references
```

## Notes
- Consider NLP for context understanding
- Plan for OCR if PDFs contain images
- Monitor reference quality metrics
- Consider building reference index for search