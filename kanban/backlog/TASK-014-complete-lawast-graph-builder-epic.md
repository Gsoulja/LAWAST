# TASK-014: Complete LAWAST Graph Builder with Full Schema Coverage [EPIC]

**Status**: BACKLOG
**Priority**: HIGH
**Type**: EPIC
**Created**: 2025-09-26
**Total Effort**: 8-12 days

## Description
Build a complete LAWAST graph builder that fully implements the graph schema coverage. The current `build_lawast_graph.py` script is missing critical schema parameters and entire node types, preventing complete legal knowledge graph construction. This epic addresses all schema gaps and implements SR number filtering for targeted builds.

**Problem**: The existing build script only partially implements the schema:
- LawNode: Missing 15 of 24 parameters (62% incomplete)
- ArticleNode: Missing 5 parameters (25% incomplete)
- ParagraphNode: Missing 3 parameters (25% incomplete)
- Missing entire node types: VersionNode, ActNode, SubpointNode, ManifestationNode
- No SR number filtering capability for focused builds
- Schema property name mismatches in implementation

## Sub-tasks
- [ ] TASK-014.1: Schema Alignment and Property Mapping (2-3 days)
- [ ] TASK-014.2: Missing Node Types Implementation (2-3 days)
- [ ] TASK-014.3: SR Number Filtering System (1 day)
- [ ] TASK-014.4: Enhanced Extraction Pipeline (2 days)
- [ ] TASK-014.5: Testing and Validation Framework (1-2 days)

## Business Value
- **Complete Schema Coverage**: Full implementation of all 8 node types with all required properties
- **Targeted Building**: SR filtering enables focused graph construction (e.g., SR 101 only)
- **Data Integrity**: Proper schema compliance ensures reliable graph queries
- **Performance**: SR filtering reduces build time from hours to minutes for specific laws
- **Foundation**: Enables advanced features requiring complete graph structure

## Completion Criteria
All sub-tasks must be completed for this epic to be done.

## Technical Analysis

### Schema Gaps Identified
Based on analysis of `/home/mxlk/LAWAST/src/data_access/graph_schema.py` vs `/home/mxlk/LAWAST/scripts/build_lawast_graph.py`:

#### LawNode (Missing 15/24 parameters)
```python
# Missing in current implementation:
title_rm, title_en, date_no_longer_in_force, date_modified,
in_force_status, status, basic_act, classified_by_taxonomy,
type_document, type, language, parent_uri, ast_path, ast_level, parent_id
```

#### ArticleNode (Missing 5 parameters)
```python
# Missing: content_uri, section, chapter, parent_id, position
```

#### ParagraphNode (Missing 3 parameters)
```python
# Missing: parent_id, word_count, has_subpoints
```

#### Completely Missing Node Types
- **VersionNode**: Temporal version handling (TASK-006 integration needed)
- **ActNode**: OC/AS/RO publication metadata
- **SubpointNode**: Lettered subpoints within paragraphs
- **ManifestationNode**: Document format representations

### Dependencies Identified
- **Existing Resources**:
  - `/home/mxlk/LAWAST/scripts/build_lawast_graph.py` - Current implementation
  - `/home/mxlk/LAWAST/src/data_access/graph_schema.py` - Complete schema definitions
  - `/home/mxlk/LAWAST/src/data_access/storage_pipeline.py` - Neo4j storage infrastructure
  - `/home/mxlk/LAWAST/src/extractors/article_extractor.py` - Article content extraction
  - `/home/mxlk/LAWAST/src/extractors/law_extractor.py` - Law metadata extraction
  - `/home/mxlk/LAWAST/src/data_access/embedding_generator.py` - Vector embeddings

- **Required New Components**:
  - Version extraction from JSON temporal data
  - Act extraction from ConsolidationAbstract
  - Subpoint parsing from article HTML
  - Manifestation metadata from file system
  - SR number filtering and validation
  - Enhanced property mapping layer

### Architecture Overview
```
JSON/HTML Input → Enhanced Extraction Pipeline → Schema-Compliant Nodes
     ↓                        ↓                           ↓
SR Filter Logic → Property Mapping Layer → Neo4j Storage Pipeline
     ↓                        ↓                           ↓
Version Handler → Missing Node Extractors → Complete Graph Structure
```

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema complexity | HIGH | Incremental implementation, one node type at a time |
| Breaking existing builds | MEDIUM | Backward compatibility, feature flags |
| Performance degradation | MEDIUM | SR filtering to reduce data volume |
| Property mapping errors | HIGH | Validation framework, comprehensive testing |

## Expected Graph Scale (Complete Implementation)
- **Nodes**: ~3-4 million (vs current ~1-2 million)
  - Laws: 17,000 (complete metadata)
  - Versions: ~200,000 (NEW)
  - Acts: ~50,000 (NEW)
  - Articles: ~500,000 (enhanced)
  - Paragraphs: ~1,500,000 (enhanced)
  - Subpoints: ~500,000 (NEW)
  - Manifestations: ~1,000,000 (NEW)

- **Relationships**: ~8-12 million (vs current ~5-8 million)
  - All existing relationship types
  - HAS_VERSION: ~200,000 (NEW)
  - HAS_SUBPOINT: ~500,000 (NEW)
  - MANIFESTED_AS: ~1,000,000 (NEW)

## Success Metrics
- [ ] All 8 node types fully implemented with complete properties
- [ ] SR filtering enables targeted builds (e.g., `--sr-filter 101`)
- [ ] Build time < 30 minutes for SR 101 (vs hours for full build)
- [ ] Schema validation passes 100% for all created nodes
- [ ] No regression in existing functionality
- [ ] Complete test coverage for all new components
- [ ] Documentation updated with new capabilities

## Implementation Strategy
1. **Phase 1**: Schema alignment for existing node types (non-breaking)
2. **Phase 2**: Add missing node types incrementally
3. **Phase 3**: Implement SR filtering system
4. **Phase 4**: Enhanced extraction pipeline integration
5. **Phase 5**: Comprehensive testing and validation

## Technical Complexity Analysis
- Frontend complexity: 1/5 (no UI changes)
- Backend complexity: 5/5 (complex schema implementation, new extractors)
- Database complexity: 4/5 (schema extensions, new relationships)
- Integration complexity: 5/5 (multiple extractors, pipelines coordination)
- Testing complexity: 4/5 (schema validation, regression testing)
**Total Score: 19/25** - Requires splitting into sub-tasks

## Dependencies on Other Tasks
- **TASK-006**: Temporal Version Handler (integration needed for VersionNode)
- **TASK-008**: Unified Content Extraction (foundation extractors)
- **Neo4j setup**: Database infrastructure must be operational

## Notes
- This epic completes the graph schema implementation started in TASK-001
- Enables advanced legal queries requiring complete graph structure
- Provides foundation for intelligent legal assistant features
- SR filtering makes development and testing much more manageable