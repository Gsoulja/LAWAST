# TASK-004: Relationship Extractor

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Assigned**: Unassigned
**Created**: 2024-09-24
**Updated**: 2024-09-24
**Estimated Effort**: 3 days

## Description
Extract and create relationships between legal entities in the Neo4j graph. Process URI references from JSON files to build connections like HAS_VERSION, SUPERSEDES, EXPRESSED_IN, AMENDS, and REFERENCES. This creates the navigable structure that enables graph traversal for legal queries.

## Business Value
- Enables relationship-based legal queries
- Builds version chains for temporal navigation
- Connects laws through amendments and references
- Links multilingual versions of same content
- Foundation for graph-based legal reasoning

## Acceptance Criteria
- [ ] Extract all isRealizedBy relationships
- [ ] Extract all isEmbodiedBy relationships
- [ ] Create HAS_VERSION relationships between laws and versions
- [ ] Build SUPERSEDES chains for version history
- [ ] Map EXPRESSED_IN for language variants
- [ ] Identify AMENDS relationships from /eli/oc/ data
- [ ] Process REFERENCES between articles
- [ ] Batch relationship creation for performance
- [ ] All tests pass
- [ ] No orphaned relationships
- [ ] Documentation updated

## Technical Approach

### Existing Resources to Reuse
- Nodes created by TASK-003
- URI patterns documented in FEDLEX_DATA_CONNECTION_GUIDE.md
- Graph schema from TASK-002

### New Components Needed
- URI resolver for entity linking
- Relationship batch creator
- Version chain builder
- Amendment detector
- Reference parser

### Dependencies
- Frontend: N/A
- Backend: neo4j-driver, existing parser from TASK-003
- Database: Nodes must exist from TASK-003

### Implementation Steps
1. Parse URI references from JSON
2. Resolve URIs to existing nodes
3. Build relationship creation queries
4. Batch insert relationships
5. Verify relationship integrity
6. Build version chains

## Relationship Types to Extract

### From JSON References
```python
# isRealizedBy → EXPRESSED_IN
"references": {
  "isRealizedBy": [
    "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
    "https://fedlex.data.admin.ch/eli/cc/1999/404/fr"
  ]
}
# Creates: (:Law)-[:EXPRESSED_IN]->(:Language)

# isEmbodiedBy → MANIFESTED_AS
"references": {
  "isEmbodiedBy": [
    "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/html",
    "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/pdf"
  ]
}
# Creates: (:Language)-[:MANIFESTED_AS]->(:Manifestation)
```

### Version Relationships
```cypher
// Laws to Versions
MATCH (l:Law {uri: $law_uri})
MATCH (v:Version {law_uri: $law_uri})
CREATE (l)-[:HAS_VERSION]->(v)

// Version Chains
MATCH (v1:Version {law_uri: $uri, date_end: $date})
MATCH (v2:Version {law_uri: $uri, date_start: $date})
CREATE (v2)-[:SUPERSEDES]->(v1)
```

### Amendment Detection (/eli/oc/)
```python
# From official compilation files
{
  "impactedResources": [
    "https://fedlex.data.admin.ch/eli/cc/1999/404",
    "https://fedlex.data.admin.ch/eli/cc/2000/123"
  ]
}
# Creates: (:Law)-[:AMENDS]->(:Law)
```

## Relationship Creation Strategy

### Batch Processing
```python
class RelationshipBatchCreator:
    def __init__(self, batch_size=5000):
        self.batch_size = batch_size
        self.relationships = []

    def add_relationship(self, from_uri, to_uri, rel_type):
        self.relationships.append({
            'from': from_uri,
            'to': to_uri,
            'type': rel_type
        })
        if len(self.relationships) >= self.batch_size:
            self.flush()

    def flush(self):
        # Batch create relationships in Neo4j
        query = """
        UNWIND $rels AS rel
        MATCH (a {uri: rel.from})
        MATCH (b {uri: rel.to})
        CALL apoc.create.relationship(a, rel.type, {}, b)
        YIELD rel AS r
        RETURN count(r)
        """
```

### Version Chain Builder
```python
def build_version_chains():
    # For each law, sort versions by date
    # Create SUPERSEDES between consecutive versions
    query = """
    MATCH (l:Law)
    MATCH (l)-[:HAS_VERSION]->(v:Version)
    WITH l, v ORDER BY v.date_applicable
    WITH l, collect(v) AS versions
    UNWIND range(0, size(versions)-2) AS i
    WITH versions[i] AS v1, versions[i+1] AS v2
    CREATE (v2)-[:SUPERSEDES]->(v1)
    """
```

## Expected Relationship Counts

| Relationship Type | Estimated Count | Source |
|------------------|-----------------|---------|
| HAS_VERSION | ~200,000 | Law to versions |
| SUPERSEDES | ~180,000 | Version chains |
| EXPRESSED_IN | ~600,000 | Version to languages |
| MANIFESTED_AS | ~3,000,000 | Language to formats |
| AMENDS | ~50,000 | From /eli/oc/ |
| REFERENCES | ~1,000,000 | Cross-references |
| CONTAINS | ~500,000 | Law to articles |

## Testing Requirements
- Unit tests for URI resolution
- Integration tests for relationship creation
- Verify version chains are complete
- Test amendment detection accuracy
- Performance tests with 10,000 relationships
- Manual verification of graph structure

## Performance Targets
- Relationship creation: > 1000/second
- Batch size optimization: 5000 relationships
- Memory usage: < 2GB
- Total processing: < 2 hours

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Broken URI references | HIGH | Validate URIs, log missing nodes |
| Duplicate relationships | MEDIUM | Use MERGE instead of CREATE |
| Memory overflow | MEDIUM | Batch processing, flush regularly |
| Incorrect version chains | HIGH | Sort validation, extensive testing |

## Related Tasks
- Dependencies: TASK-002, TASK-003 (needs nodes)
- Related: TASK-001 (parent epic)
- Blocks: TASK-006 (temporal queries need relationships)

## Validation Queries
```cypher
// Verify all laws have versions
MATCH (l:Law)
WHERE NOT (l)-[:HAS_VERSION]->()
RETURN count(l) AS laws_without_versions

// Check version chain integrity
MATCH (v:Version)
WHERE NOT (v)-[:SUPERSEDES]->()
  AND v.date_end_applicable IS NOT NULL
RETURN count(v) AS broken_chains

// Find orphaned nodes
MATCH (n)
WHERE NOT (n)-[]-()
RETURN labels(n), count(n)
```

## Notes
- Consider using APOC procedures for bulk operations
- Monitor Neo4j transaction log size
- Plan for relationship updates when laws change
- Document relationship semantics clearly