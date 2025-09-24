# TASK-006: Temporal Version Handler

**Status**: BACKLOG
**Priority**: MEDIUM
**Type**: feature
**Assigned**: Unassigned
**Created**: 2024-09-24
**Updated**: 2024-09-24
**Estimated Effort**: 2 days

## Description
Implement temporal query capabilities to find the correct version of any law at any point in time. Build version timelines, handle overlapping dates, query historical states, and ensure legal validity checking. This enables answering questions like "What was the law on January 1, 2020?" or "When did this article change?"

## Business Value
- Enable point-in-time legal queries
- Track law evolution over time
- Ensure legal validity for specific dates
- Support historical legal research
- Critical for accurate legal advice

## Acceptance Criteria
- [ ] Track complete version timelines for all laws
- [ ] Find active version at any given date
- [ ] Build and validate version chains
- [ ] Handle overlapping date ranges correctly
- [ ] Query historical states efficiently
- [ ] Identify gaps in version coverage
- [ ] Support date range queries
- [ ] All tests pass
- [ ] Performance < 100ms for version lookup
- [ ] Documentation updated

## Technical Approach

### Existing Resources to Reuse
- Version nodes from TASK-003
- SUPERSEDES relationships from TASK-004
- Date attributes in JSON data

### New Components Needed
- Version timeline builder
- Temporal query interface
- Date range validator
- Version chain integrity checker
- Historical state reconstructor

### Dependencies
- Frontend: N/A
- Backend: neo4j-driver, datetime handling
- Database: Version nodes and relationships

### Implementation Steps
1. Analyze version date patterns in data
2. Build version timeline for each law
3. Create temporal query functions
4. Implement date range validation
5. Add version chain verification
6. Optimize temporal queries with indexes

## Temporal Data Model

### Version Node Properties
```cypher
(:Version {
  uri: String,
  law_uri: String,
  date_applicable: Date,        // When version becomes active
  date_end_applicable: Date,    // When version ends (null if current)
  is_current: Boolean           // Computed flag for current version
})
```

### Version Chain Relationships
```cypher
// Version succession
(:Version)-[:SUPERSEDES]->(:Version)

// Law to versions
(:Law)-[:HAS_VERSION]->(:Version)

// Current version marker
(:Law)-[:CURRENT_VERSION]->(:Version)
```

## Temporal Query Functions

### Find Version at Date
```cypher
// Get law version valid on specific date
MATCH (l:Law {sr_number: $sr_number})
MATCH (l)-[:HAS_VERSION]->(v:Version)
WHERE v.date_applicable <= $query_date
  AND (v.date_end_applicable IS NULL
       OR v.date_end_applicable > $query_date)
RETURN v
```

### Version Timeline Query
```cypher
// Get complete version history
MATCH (l:Law {sr_number: $sr_number})
MATCH (l)-[:HAS_VERSION]->(v:Version)
RETURN v.date_applicable, v.date_end_applicable
ORDER BY v.date_applicable
```

### Change Detection
```cypher
// Find when an article changed
MATCH (l:Law {sr_number: $sr_number})
MATCH (l)-[:HAS_VERSION]->(v:Version)
WHERE v.date_applicable >= $start_date
  AND v.date_applicable <= $end_date
RETURN v.date_applicable AS change_date
ORDER BY change_date
```

## Version Chain Validation

### Integrity Checks
```python
def validate_version_chain(law_uri):
    checks = {
        'no_gaps': check_for_timeline_gaps(),
        'no_overlaps': check_for_date_overlaps(),
        'chain_complete': verify_supersedes_chain(),
        'current_marked': verify_current_version(),
        'dates_ordered': check_date_ordering()
    }
    return checks

def check_for_timeline_gaps():
    # Ensure continuous coverage
    query = """
    MATCH (l:Law {uri: $law_uri})
    MATCH (l)-[:HAS_VERSION]->(v:Version)
    WITH v ORDER BY v.date_applicable
    WITH collect(v) AS versions
    // Check each version's end matches next's start
    """
```

### Gap Detection
```cypher
// Find laws with version gaps
MATCH (l:Law)
MATCH (l)-[:HAS_VERSION]->(v1:Version)
MATCH (l)-[:HAS_VERSION]->(v2:Version)
WHERE v1.date_end_applicable < v2.date_applicable
  AND NOT EXISTS {
    MATCH (l)-[:HAS_VERSION]->(v3:Version)
    WHERE v3.date_applicable >= v1.date_end_applicable
      AND v3.date_applicable < v2.date_applicable
  }
RETURN l.sr_number, v1.date_end_applicable AS gap_start,
       v2.date_applicable AS gap_end
```

## Historical State Reconstruction

### Point-in-Time Snapshot
```python
def get_legal_state_at_date(date):
    """
    Reconstruct complete legal system state at specific date
    """
    query = """
    MATCH (l:Law)
    MATCH (l)-[:HAS_VERSION]->(v:Version)
    WHERE v.date_applicable <= $date
      AND (v.date_end_applicable IS NULL
           OR v.date_end_applicable > $date)
    RETURN l.sr_number, v.uri, v.date_applicable
    """
```

### Delta Between Dates
```python
def get_changes_between_dates(start_date, end_date):
    """
    Find all law changes in date range
    """
    query = """
    MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
    WHERE v.date_applicable > $start_date
      AND v.date_applicable <= $end_date
    RETURN l.sr_number, v.date_applicable, 'NEW_VERSION' AS change_type
    UNION
    MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
    WHERE v.date_end_applicable > $start_date
      AND v.date_end_applicable <= $end_date
    RETURN l.sr_number, v.date_end_applicable, 'VERSION_ENDED' AS change_type
    ORDER BY date_applicable
    """
```

## Performance Optimization

### Temporal Indexes
```cypher
CREATE INDEX version_date_range
FOR (v:Version)
ON (v.date_applicable, v.date_end_applicable);

CREATE INDEX current_version
FOR (v:Version)
ON (v.is_current)
WHERE v.is_current = true;
```

### Caching Strategy
```python
class VersionCache:
    def __init__(self):
        self.current_versions = {}  # Cache current versions
        self.version_timelines = {}  # Cache full timelines

    def get_version_at_date(self, law_uri, date):
        # Check cache first
        # Fall back to database query
```

## Testing Requirements
- Unit tests for date range logic
- Integration tests for version queries
- Validation of version chains
- Performance tests with 1000 queries
- Edge case testing (gaps, overlaps)
- Manual verification of known changes

## Expected Metrics
- Average versions per law: 10-15
- Total version nodes: ~200,000
- Query response time: < 100ms
- Version coverage: > 99% (minimal gaps)
- Chain integrity: 100% valid

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Incomplete version data | HIGH | Validation checks, gap reporting |
| Date parsing errors | MEDIUM | Standardize date format handling |
| Query performance | MEDIUM | Indexes, caching, query optimization |
| Overlapping dates | HIGH | Strict validation, data cleaning |

## Related Tasks
- Dependencies: TASK-003, TASK-004
- Related: TASK-001 (parent epic)
- Blocks: TASK-007 (queries need temporal support)

## Example Queries

### Legal Question Examples
```python
# "What was employment law on 2020-01-01?"
get_version("OR", "2020-01-01")

# "When did data protection law last change?"
get_last_change("DSG")

# "Show all law changes in 2023"
get_changes_in_year(2023)

# "Was this article valid on this date?"
check_validity("OR:335b", "2022-06-15")
```

## Notes
- Consider timezone handling (Swiss time)
- Plan for retroactive changes
- Document version numbering scheme
- Consider building timeline visualization