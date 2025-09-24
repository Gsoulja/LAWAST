# TASK-003: JSON Parser & Node Creator

**Status**: IN-PROGRESS
**Priority**: HIGH
**Type**: feature
**Assigned**: Unassigned
**Created**: 2024-09-24
**Updated**: 2025-09-24
**Started**: 2025-09-24
**Analysis Completed**: 2025-09-24
**Estimated Effort**: 3 days

## Description
Build a robust JSON parser that processes 305,440 Fedlex JSON files to extract legal entities and create Neo4j nodes. The parser must handle multiple JSON object types (ConsolidationAbstract, Act, Treaty), extract multilingual properties, and use batch processing for performance with 5.6GB of data.

**IMPORTANT SCOPE CLARIFICATION**: This task focuses on JSON metadata extraction only. HTML content parsing (18GB in fedlex-assets/) is handled separately in TASK-005. The JSON contains references to HTML manifestations via URIs, but actual article text extraction from HTML is out of scope.

## Business Value
- Transforms raw Fedlex data into queryable graph nodes
- Enables legal entity extraction from 305,440 documents
- Provides foundation for relationship building
- Supports multilingual legal content

## Acceptance Criteria
- [ ] Parse all JSON object types correctly
- [ ] Extract entities from 305,440 files without errors
- [ ] Create Law, Version, Article nodes in Neo4j
- [ ] Handle multilingual properties (DE/FR/IT/RM/EN)
- [ ] Batch processing with configurable batch size
- [ ] Progress tracking and resume capability
- [ ] Error handling with detailed logging
- [ ] All tests pass
- [ ] No memory leaks during processing
- [ ] Documentation updated

## Technical Approach

### Existing Resources to Reuse
- fedlex/ directory structure already mapped
- src/data_access/fedlex_loader.py exists
- JSON structure documented in FEDLEX_DATA_CONNECTION_GUIDE.md

### New Components Needed
- Streaming JSON parser for large files
- Entity extraction classes
- Batch processor with checkpointing
- Progress tracker
- Error recovery mechanism

### Dependencies
- Frontend: N/A
- Backend: ijson (streaming JSON), tqdm (progress), neo4j-driver
- Database: Neo4j connection from TASK-002

### Implementation Steps
1. Analyze JSON structure patterns in fedlex/
2. Build entity extraction classes for each type
3. Implement streaming parser with ijson
4. Create batch processing pipeline
5. Add checkpointing for resume capability
6. Build progress tracking and logging

## JSON Object Types to Parse

### ConsolidationAbstract (fedlex/eli/cc/*)
```python
{
  "data": {
    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404",
    "type": ["ConsolidationAbstract", "Work"],
    "attributes": {
      "dateDocument": {"xsd:date": "1999-04-18"},
      "dateEntryInForce": {"xsd:date": "2000-01-01"},
      "classifiedByTaxonomyEntryLabel": {
        "de": "SR 101 Bundesverfassung",
        "fr": "RS 101 Constitution fédérale",
        "it": "RS 101 Costituzione federale"
      }
    },
    "references": {
      "isRealizedBy": [
        "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/fr",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/it"
      ]
    }
  }
}
```

### Consolidation Version (fedlex/eli/cc/*/[date].json)
```python
{
  "data": {
    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101",
    "attributes": {
      "dateApplicability": {"xsd:date": "2024-01-01"},
      "dateEndApplicability": {"xsd:date": "2024-03-02"}
    }
  }
}
```

## Parser Architecture

### Entity Extractor Classes (Updated with Edge Cases)
```python
class LawExtractor:
    def extract(self, json_data) -> dict:
        """Extract Law node handling historical formats"""
        # Handle Roman numerals (I/, II/, III/)
        # Handle double underscores (__1811)
        # Handle multi-part numbers (271_271_445)
        # Check for dateNoLongerInForce
        # Handle language placeholders ("nur ital.")

class VersionExtractor:
    def extract(self, json_data) -> dict:
        """Extract Version node with temporal data"""
        # Handle missing dateEndApplicability
        # Link to parent law URI
        # Extract all language expressions

class ActExtractor:
    def extract(self, json_data) -> dict:
        """Extract Act nodes from publications"""
        # Handle publication metadata
        # Extract memorial information
```

### Batch Processing Pipeline
```python
class BatchProcessor:
    def __init__(self, batch_size=1000):
        self.batch_size = batch_size
        self.checkpoint_file = "processing_checkpoint.json"

    def process_files(self, file_list):
        # Process in batches with checkpointing

    def resume_from_checkpoint(self):
        # Resume processing after failure
```

## File Processing Strategy

### Directory Priority Order
1. `/eli/cc/` - Classified compilation (17,000 files) - PRIMARY
2. `/eli/oc/` - Official compilation (45,000 files) - SECONDARY
3. `/eli/fga/` - Federal gazette (146,000 files) - TERTIARY
4. `/eli/treaty/` - Treaties (18,500 files) - QUATERNARY

### Batch Sizes
- Initial testing: 100 files
- Development: 1,000 files
- Production: 10,000 files

## Testing Requirements
- Unit tests for each extractor class
- Integration tests with sample JSON files
- Performance tests with 10,000 files
- Memory leak tests
- Manual testing of entity extraction

## Performance Targets
- Processing rate: > 100 files/second
- Memory usage: < 4GB for parser
- Batch insert: 1000 nodes per transaction
- Total processing time: < 1 hour for 305k files

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Memory overflow with large files | HIGH | Use streaming parser (ijson) |
| Processing interruption | HIGH | Implement checkpointing |
| Malformed JSON files | MEDIUM | Error handling, skip and log |
| Duplicate entities | LOW | Use MERGE instead of CREATE |

## Related Tasks
- Dependencies: TASK-002 (Neo4j must be ready)
- Related: TASK-001 (parent epic)
- Blocks: TASK-004 (needs nodes for relationships)

## Progress Tracking Format
```
Processing Fedlex JSON Files
============================
Directory: /eli/cc/
Files: 17,000 / 17,000 [##########] 100%
Nodes Created: 34,521
Errors: 3
Time Elapsed: 00:05:23
Rate: 105 files/sec
Memory: 2.3GB / 4.0GB

Current File: fedlex/eli/cc/2024/123.json
Status: Extracting entities...
```

## Notes
- Consider parallel processing for speed
- Monitor Neo4j write performance
- Plan for incremental updates
- Keep statistics for verification

## Technical Analysis (Auto-generated 2025-09-24)

### Existing Resources Found
- **Components**:
  - `src/data_access/batch_processor.py` - Complete batch processing with checkpointing (REUSE!)
  - `src/data_access/graph_builder.py` - CRUD operations for Neo4j nodes
  - `src/data_access/neo4j_connection.py` - Connection pooling with retry logic
  - `src/data_access/graph_schema.py` - Node/relationship type definitions
- **Services**:
  - Neo4j running in Docker (lawast-neo4j container)
  - Connection pool configured (max 50 connections)
- **APIs**:
  - GraphBuilder methods: create_law_node(), create_version_node(), create_article_node()
  - BatchProcessor: process_files(), save_checkpoint(), load_checkpoint()
- **Database**:
  - Neo4j 5.x running on ports 7474/7687
  - Schema already initialized from TASK-002
  - Indexes on uri, sr_number, dates
- **Utilities**:
  - ProcessingCheckpoint class for recovery
  - Rich library for progress display (alternative to tqdm)

### Dependencies Required
- **Frontend packages**: N/A (backend only)
- **Backend packages**:
  - neo4j>=5.14.0 ✅ (already in requirements.txt)
  - python-dotenv>=1.0.0 ✅ (installed)
  - rich>=13.0.0 ✅ (installed, use instead of tqdm)
  - ijson ❌ (MUST ADD for streaming JSON)
  - orjson ⚠️ (CONSIDER for faster parsing)
- **Database migrations**: None (schema ready)
- **Docker services**: Neo4j ✅ (running)

### Impact Assessment

#### Files to Create
- `src/data_access/fedlex_parser.py`: Main parser implementation
- `src/extractors/__init__.py`: Extractor package
- `src/extractors/law_extractor.py`: Extract Law nodes from ConsolidationAbstract
- `src/extractors/version_extractor.py`: Extract Version nodes from Consolidation
- `src/extractors/act_extractor.py`: Extract Act nodes from publications
- `tests/test_fedlex_parser.py`: Unit tests

#### Files to Modify
- `requirements.txt`: Add ijson for streaming JSON
- `src/data_access/batch_processor.py`: Integrate with parser (minimal changes)
- `.env`: Add BATCH_SIZE, CHECKPOINT_FILE variables

#### Components Affected
- **TASK-004 (Relationship Extractor)**: HIGH - Requires nodes from this task
- **TASK-005 (HTML Cross-Reference)**: MEDIUM - Needs Law/Version nodes
- **TASK-006 (Temporal Version Handler)**: HIGH - Depends on Version nodes
- **Neo4j Database**: Will receive 305k+ new nodes

#### API Changes
- None (internal processing only)

#### Database Changes
- None (schema already defined)
- Estimated data volume:
  - ~72,717 Law nodes (from /eli/cc/)
  - ~200,000+ Version nodes (temporal snapshots)
  - ~500,000+ Manifestation nodes (language/format combinations)

### Implementation Checklist
Based on analysis:
- [x] ✅ Reuse existing BatchProcessor instead of creating new
- [x] ✅ Extend GraphBuilder rather than duplicate
- [x] ✅ Use existing ProcessingCheckpoint for recovery
- [x] ✅ Leverage Rich library instead of adding tqdm
- [ ] Add ijson for streaming large JSON files
- [ ] Follow SOLID principles in extractor classes
- [ ] Maintain backwards compatibility (N/A - new feature)
- [ ] Add proper error handling for malformed JSON
- [ ] Include progress tracking with Rich
- [ ] Write self-documenting code with type hints
- [ ] Handle edge cases (Roman numerals, __ prefixes)

### Risk Analysis
- **Risk Level**: MEDIUM
- **Main Risks**:
  - **Large file memory usage**: Use ijson streaming parser
  - **Processing interruption**: BatchProcessor checkpointing already handles this ✅
  - **Malformed JSON**: Add try-except blocks with detailed logging
  - **Historical law formats (I/, II/, __1811)**: Create robust SR number extraction
  - **Neo4j performance**: Batch size of 1000, connection pool ready ✅
  - **Missing language titles**: Handle placeholder text ("nur ital.", etc.)

### Estimated Effort
- **Original**: 3 days
- **Adjusted**: 2.5 days
- **Reason**: Significant infrastructure already exists (BatchProcessor, GraphBuilder, Neo4j setup). Main work is implementing extractors and parser logic.

### Data Anomalies & Edge Cases Found

#### ✅ Good News
All tested JSON files are valid and parseable - no parse errors found in samples.

#### 🔍 Edge Cases Found

##### 1. Special Naming Patterns
Found several non-standard naming conventions:

- **Roman Numerals**: `fedlex/eli/cc/I/`, `fedlex/eli/cc/II/`, `fedlex/eli/cc/III/`
  - Example: `/eli/cc/I/271_271_445.json` (Old law from 1849)
  - These represent historical legal collections (1840s-1970s)

- **Double Underscores**: `__1811` format
  - Example: `/eli/cc/1959/__1811.json`
  - Appears to be for special or temporary legislation
  - Note: Title shows "nur ital." (only Italian) - language-specific laws

- **Multi-part Numbers**: `271_271_445` format
  - Represents different language versions (DE_FR_IT numbering)
  - Common in older laws (pre-1950s)

##### 2. Data Variations

**No Longer In Force Laws**:
```json
{
  "dateNoLongerInForce": "1979-01-01",
  "inForceStatus": "https://fedlex.data.admin.ch/vocabulary/enforcement-status/3"
}
```
- Need to handle expired/repealed laws
- Status codes: 0 (active), 3 (no longer in force)

**Language-Specific Laws**:
```json
{
  "title": {
    "xsd:string": "nur ital."  // Only Italian
  }
}
```
- Some laws only exist in specific languages
- Title might be placeholder text for missing translations
- Common placeholders: "nur ital.", "seulement en italien", "solo italiano"

**Missing Optional Fields**:
- `dateEndApplicability` - not always present
- `titleShort` - missing in older laws
- `classifiedByTaxonomyEntry` - may be absent

##### 3. File Structure Patterns
Distribution in first 5000 files:
- Standard format (YYYY/NNN): 2,684 files (54%)
- Other formats: 2,316 files (46%)
  - Includes Roman numerals
  - Multi-part numbers
  - Special prefixes

- **Large files**: Main law files can be 500KB+ (need streaming)

#### ⚠️ Important Parsing Considerations

1. **Historical Laws**: Roman numeral directories contain very old laws (1840s-1970s)
2. **Language Gaps**: Some laws have placeholder text instead of translations
3. **Status Tracking**: Must differentiate active vs. repealed laws
4. **SR Number Variations**: Multiple formats need normalization

#### ✅ Summary
The data is well-structured but has legitimate variations for:
- Historical legal collections (Roman numerals)
- Special/temporary legislation (double underscores)
- Multilingual gaps (placeholder titles)
- Lifecycle states (active/repealed)

The parser must handle these gracefully without failing. All variations follow consistent JSON schema, just with different optional fields and naming conventions.

### Performance Projections
- Files to process: 305,440 total (72,717 in primary /eli/cc/)
- Target rate: 100 files/second
- With existing BatchProcessor: ~51 minutes for all files
- Memory usage: <500MB with streaming (ijson)
- Neo4j heap: 4GB allocated (sufficient)

## HTML Content Relationship

### Data Architecture
The Fedlex data follows a two-tier structure:
1. **JSON Metadata** (5.6GB in `fedlex/`) - This task's focus
2. **HTML Content** (18GB in `fedlex-assets/`) - TASK-005's responsibility

### Connection Points
JSON files contain URI references that map to HTML files:
```json
{
  "isEmbodiedBy": [
    "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/it/html"
  ]
}
```
Maps to: `fedlex-assets/eli/cc/1999/404/20240101/it/html/*.html`

### What This Task Extracts from JSON
- **Law metadata**: URI, SR number, dates, status
- **Version information**: Temporal validity periods
- **Language references**: Links to DE/FR/IT/RM/EN expressions
- **Manifestation URIs**: References to HTML/PDF/XML/DOCX locations

### What This Task DOES NOT Extract
- **Article text**: Contained in HTML files (TASK-005)
- **Cross-references**: Found within HTML content (TASK-005)
- **Legal provisions**: Detailed text in HTML (TASK-005)
- **Article numbers**: Only in HTML structure (TASK-005)

### Node Creation Strategy
This task creates:
1. **Law nodes**: Basic metadata from ConsolidationAbstract
2. **Version nodes**: Temporal snapshots with validity dates
3. **Language nodes**: Language expressions
4. **Manifestation nodes**: Format references (URI only, no content)

TASK-005 will later:
- Parse HTML to extract Article nodes with actual text
- Mine cross-references between articles
- Add REFERENCES relationships based on HTML content

## Expected Outcome Test

### What the Parser Will Produce

```bash
# Run the parser (when implemented)
python scripts/run_json_parser.py --limit 100
```

### Expected Output Example

#### INPUT: Sample JSON Files
```
Processing: fedlex/eli/cc/1999/404.json (ConsolidationAbstract)
Processing: fedlex/eli/cc/1999/404/20240101.json (Version)
Processing: fedlex/eli/oc/2024/500.json (Act)
```

#### OUTPUT: Neo4j Nodes Created

**1. From ConsolidationAbstract (fedlex/eli/cc/1999/404.json)**
```cypher
// Law Node Created
(:Law {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404",
  sr_number: "SR 1999.404",
  title_de: "Bundesverfassung der Schweizerischen Eidgenossenschaft",
  title_fr: "Constitution fédérale de la Confédération suisse",
  title_it: "Costituzione federale della Confederazione Svizzera",
  date_document: "1999-04-18",
  date_entry_in_force: "2000-01-01",
  in_force: true,
  type: "ConsolidationAbstract"
})

// Language Expression Nodes
(:Expression {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
  language: "DE",
  parent_uri: "https://fedlex.data.admin.ch/eli/cc/1999/404"
})

(:Expression {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/fr",
  language: "FR",
  parent_uri: "https://fedlex.data.admin.ch/eli/cc/1999/404"
})

(:Expression {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/it",
  language: "IT",
  parent_uri: "https://fedlex.data.admin.ch/eli/cc/1999/404"
})
```

**2. From Version (fedlex/eli/cc/1999/404/20240101.json)**
```cypher
// Version Node Created
(:Version {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101",
  parent_law_uri: "https://fedlex.data.admin.ch/eli/cc/1999/404",
  date_applicable: "2024-01-01",
  date_end_applicable: "2024-03-02",
  type: "Consolidation"
})

// Version Language Expressions
(:Expression {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de",
  language: "DE",
  parent_uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101"
})

// Manifestation Nodes
(:Manifestation {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/html",
  format: "HTML",
  parent_uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de"
})

(:Manifestation {
  uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/pdf",
  format: "PDF",
  parent_uri: "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de"
})
```

**3. From Act (fedlex/eli/oc/2024/500.json)**
```cypher
// Act Node Created
(:Act {
  uri: "https://fedlex.data.admin.ch/eli/oc/2024/500",
  date_publication: "2024-09-15",
  type: "Act",
  impacted_laws: ["https://fedlex.data.admin.ch/eli/cc/1999/404"]
})
```

### Edge Cases Handled

**Roman Numerals (fedlex/eli/cc/I/271_271_445.json)**
```cypher
(:Law {
  uri: "https://fedlex.data.admin.ch/eli/cc/I/271_271_445",
  sr_number: "SR I 271",  // Correctly parsed Roman numeral
  title_de: "Historical Collection I",
  date_document: "1849-09-12",
  date_no_longer_in_force: "1979-01-01",
  in_force: false
})
```

**Double Underscore (fedlex/eli/cc/1959/__1811.json)**
```cypher
(:Law {
  uri: "https://fedlex.data.admin.ch/eli/cc/1959/__1811",
  sr_number: "Special 1811",  // Special format handled
  title_it: "Legge speciale",
  title_de: "nur ital.",  // Placeholder for missing translation
  title_fr: "seulement en italien"
})
```

### Processing Statistics

```
==============================================
JSON PARSING COMPLETE
==============================================
Total Files Processed: 305,440
Total Time: 51 minutes

Nodes Created by Type:
- Law nodes:          72,717
- Version nodes:      201,345
- Act nodes:          45,231
- Expression nodes:   612,890
- Manifestation nodes: 1,837,670

Total Nodes: 2,769,853

Edge Cases Handled:
- Roman numerals:     1,245 files
- Double underscores: 89 files
- Multi-part numbers: 2,134 files
- Missing languages:  4,521 placeholders

Errors:
- Malformed JSON:     12 files (skipped)
- Missing required:   3 files (skipped)

Memory Peak: 487 MB
Processing Rate: 99.7 files/second
==============================================
```

### Verification Queries

After parsing, these Cypher queries should work:

```cypher
// Count all law nodes
MATCH (l:Law) RETURN COUNT(l)
// Expected: ~72,717

// Find laws with Roman numerals
MATCH (l:Law) WHERE l.sr_number STARTS WITH 'SR I' RETURN COUNT(l)
// Expected: ~1,245

// Find no-longer-in-force laws
MATCH (l:Law) WHERE l.in_force = false RETURN COUNT(l)
// Expected: ~15,234

// Check version chains exist
MATCH (l:Law)-[:HAS_VERSION]->(v:Version) RETURN COUNT(DISTINCT l)
// Expected: 0 (relationships in TASK-004)

// Find laws with all 4 languages
MATCH (l:Law)
WHERE l.title_de IS NOT NULL
  AND l.title_fr IS NOT NULL
  AND l.title_it IS NOT NULL
  AND l.title_rm IS NOT NULL
RETURN COUNT(l)
// Expected: ~12,456
```

### Test Script Validation

```python
# Test file: tests/test_expected_outcome_task003.py

def test_parser_output():
    """Verify parser creates expected nodes"""

    # Parse sample file
    parser = FedlexParser()
    result = parser.parse_file("fedlex/eli/cc/1999/404.json")

    # Check Law node created
    assert result['nodes_created']['Law'] == 1
    assert result['nodes_created']['Expression'] == 3  # DE, FR, IT

    # Check SR number extraction
    assert result['law_node']['sr_number'] == "SR 1999.404"

    # Test edge cases
    roman = parser.parse_file("fedlex/eli/cc/I/271.json")
    assert roman['law_node']['sr_number'] == "SR I 271"

    special = parser.parse_file("fedlex/eli/cc/1959/__1811.json")
    assert special['law_node']['sr_number'] == "Special 1811"

    # Verify batch processing
    stats = parser.process_directory("fedlex/eli/cc", limit=100)
    assert stats['files_processed'] == 100
    assert stats['errors'] < 5
    assert stats['nodes_created'] > 200
```

### Command-Line Output During Processing

```
$ python scripts/run_json_parser.py

LAWAST JSON Parser v1.0
========================
Starting at: 2024-09-24 10:00:00
Config: Batch size=1000, Checkpoint enabled

[Phase 1: Classified Compilation]
Directory: fedlex/eli/cc/
Files found: 72,717
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 72,717/72,717 • 12:23 • 98 files/s

✓ Law nodes created: 72,717
✓ Expression nodes: 218,151
✓ Edge cases handled: 3,468

[Phase 2: Official Compilation]
Directory: fedlex/eli/oc/
Files found: 45,000
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 45,000/45,000 • 07:30 • 100 files/s

✓ Act nodes created: 45,000

[Phase 3: Versions]
Processing version files...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 201,345/201,345 • 33:35 • 100 files/s

✓ Version nodes: 201,345
✓ Manifestations: 1,837,670

[Final Summary]
Total processing time: 51 minutes 28 seconds
Total nodes created: 2,769,853
Database size: ~4.2 GB
Ready for TASK-004 relationship extraction!
```