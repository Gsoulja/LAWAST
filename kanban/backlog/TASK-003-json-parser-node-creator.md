# TASK-003: JSON Parser & Node Creator

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Assigned**: Unassigned
**Created**: 2024-09-24
**Updated**: 2024-09-24
**Estimated Effort**: 3 days

## Description
Build a robust JSON parser that processes 305,440 Fedlex JSON files to extract legal entities and create Neo4j nodes. The parser must handle multiple JSON object types (ConsolidationAbstract, Act, Treaty), extract multilingual properties, and use batch processing for performance with 5.6GB of data.

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

### Entity Extractor Classes
```python
class LawExtractor:
    def extract(self, json_data) -> dict:
        # Extract Law node properties

class VersionExtractor:
    def extract(self, json_data) -> dict:
        # Extract Version node properties

class ArticleExtractor:
    def extract(self, json_data) -> dict:
        # Extract Article node properties
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