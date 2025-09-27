# TASK-014.2: Missing Node Types Implementation

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Parent**: TASK-014
**Estimated Effort**: 2-3 days
**Created**: 2025-09-26
**Assigned**: Unassigned

## Description
Implement the four completely missing node types from the graph schema: VersionNode, ActNode, SubpointNode, and ManifestationNode. These node types are critical for complete legal knowledge representation and temporal queries.

## Problem Analysis
Current gaps in node type coverage:
- **VersionNode**: Temporal version handling (0% implemented)
- **ActNode**: OC/AS/RO publication metadata (0% implemented)
- **SubpointNode**: Lettered subpoints within paragraphs (0% implemented)
- **ManifestationNode**: Document format representations (0% implemented)

These missing types prevent:
- Temporal queries (finding law versions at specific dates)
- Publication tracking (OC/AS/RO document management)
- Fine-grained content structure (subpoint-level navigation)
- Multi-format document management (HTML, PDF, XML)

## Acceptance Criteria
- [ ] VersionNode fully implemented with temporal relationships
- [ ] ActNode implemented for OC/AS/RO publications
- [ ] SubpointNode implemented for paragraph substructure
- [ ] ManifestationNode implemented for document formats
- [ ] All relationships between new node types created
- [ ] Integration with existing graph structure
- [ ] Temporal queries work correctly
- [ ] All unit tests pass
- [ ] Performance impact < 15%

## Technical Implementation

### 1. VersionNode Implementation
Integrate with TASK-006 temporal version handler:

```python
def create_version_nodes(self, law_data: Dict) -> List[Dict]:
    """Extract and create version nodes from JSON data"""
    versions = []

    # Extract from ConsolidationAbstract
    for version_ref in law_data.get('references', {}).get('hasVersion', []):
        version_uri = version_ref.get('@id')
        if not version_uri:
            continue

        # Parse version date from URI
        date_applicable = self.extract_version_date(version_uri)

        version_node = {
            'uri': version_uri,
            'law_uri': law_data.get('data', {}).get('uri'),
            'date_applicable': date_applicable.isoformat(),
            'date_end_applicable': self.extract_end_date(version_ref),
            'version_number': self.extract_version_number(version_uri),
            'is_current': self.is_current_version(version_uri, law_data),
            'ast_level': 4,  # Version is level 4 (below Law)
            'ast_path': f"{law_ast_path}/version_{date_applicable.strftime('%Y%m%d')}"
        }
        versions.append(version_node)

    return versions

def create_version_relationships(self, law_uri: str, versions: List[Dict]):
    """Create HAS_VERSION and SUPERSEDES relationships"""
    with self.connection.driver.session() as session:
        # Create HAS_VERSION relationships
        for version in versions:
            session.run("""
                MATCH (l:Law {uri: $law_uri})
                MATCH (v:Version {uri: $version_uri})
                MERGE (l)-[:HAS_VERSION]->(v)
            """, law_uri=law_uri, version_uri=version['uri'])

        # Create SUPERSEDES relationships (chronological order)
        sorted_versions = sorted(versions, key=lambda v: v['date_applicable'])
        for i in range(len(sorted_versions) - 1):
            current = sorted_versions[i]
            next_version = sorted_versions[i + 1]
            session.run("""
                MATCH (v1:Version {uri: $current_uri})
                MATCH (v2:Version {uri: $next_uri})
                MERGE (v2)-[:SUPERSEDES]->(v1)
            """, current_uri=current['uri'], next_uri=next_version['uri'])
```

### 2. ActNode Implementation
Extract OC/AS/RO publication metadata:

```python
def create_act_nodes(self, law_data: Dict) -> List[Dict]:
    """Extract Act nodes from ConsolidationAbstract references"""
    acts = []

    # Look for basicAct and amendingAct references
    attributes = law_data.get('data', {}).get('attributes', {})
    references = law_data.get('data', {}).get('references', {})

    # Basic act (original publication)
    basic_act_uri = attributes.get('basicAct', {}).get('rdfs:Resource')
    if basic_act_uri:
        act_node = self.extract_act_metadata(basic_act_uri, 'basicAct')
        if act_node:
            acts.append(act_node)

    # Amending acts
    for amending_ref in references.get('amendedBy', []):
        if isinstance(amending_ref, str):
            act_node = self.extract_act_metadata(amending_ref, 'amendingAct')
            if act_node:
                acts.append(act_node)

    return acts

def extract_act_metadata(self, act_uri: str, act_type: str) -> Optional[Dict]:
    """Extract metadata for a specific act"""
    # Parse publication type from URI (OC, AS, RO, etc.)
    type_document = self.parse_publication_type(act_uri)

    # Extract publication number and date
    pub_number = self.extract_publication_number(act_uri)
    pub_date = self.extract_publication_date(act_uri)

    return {
        'uri': act_uri,
        'type_document': type_document,
        'number': pub_number,
        'date_publication': pub_date.isoformat() if pub_date else None,
        'act_type': act_type,  # 'basicAct' or 'amendingAct'
        'ast_level': 3,  # Act is level 3
        'ast_path': f"/publications/{type_document}/{pub_number}"
    }
```

### 3. SubpointNode Implementation
Parse lettered subpoints from paragraph content:

```python
def extract_subpoints(self, paragraph_text: str, paragraph_uri: str) -> List[Dict]:
    """Extract lettered subpoints (a., b., c.) from paragraph text"""
    subpoints = []

    # Regex for lettered subpoints
    subpoint_pattern = r'^([a-z])\.\s+(.*?)(?=^[a-z]\.|$)'
    matches = re.finditer(subpoint_pattern, paragraph_text, re.MULTILINE | re.DOTALL)

    for i, match in enumerate(matches, 1):
        letter = match.group(1)
        text = match.group(2).strip()

        subpoint_node = {
            'uri': f"{paragraph_uri}/subpoint_{letter}",
            'paragraph_uri': paragraph_uri,
            'letter': letter,
            'text': text,
            'position': i,
            'ast_level': 8,  # Subpoint is level 8
            'ast_path': f"{paragraph_ast_path}/subpoint_{letter}",
            'parent_id': paragraph_uri,
            'language': 'de'  # Default, detect from content
        }
        subpoints.append(subpoint_node)

    return subpoints

def create_subpoint_relationships(self, paragraph_uri: str, subpoints: List[Dict]):
    """Create HAS_SUBPOINT relationships"""
    with self.connection.driver.session() as session:
        for subpoint in subpoints:
            session.run("""
                MATCH (p:Paragraph {uri: $paragraph_uri})
                MATCH (s:Subpoint {uri: $subpoint_uri})
                MERGE (p)-[:HAS_SUBPOINT]->(s)
            """, paragraph_uri=paragraph_uri, subpoint_uri=subpoint['uri'])
```

### 4. ManifestationNode Implementation
Track document format representations:

```python
def create_manifestation_nodes(self, law_uri: str) -> List[Dict]:
    """Create manifestation nodes for different document formats"""
    manifestations = []

    # Check for existing HTML files
    html_files = self.find_html_manifestations(law_uri)
    for html_file in html_files:
        manifestation = {
            'uri': f"{law_uri}/manifestation/html/{html_file.stem}",
            'format': 'html',
            'file_path': str(html_file),
            'file_size': html_file.stat().st_size,
            'checksum': self.calculate_file_hash(html_file),
            'language': self.detect_file_language(html_file),
            'date_created': datetime.fromtimestamp(html_file.stat().st_ctime).isoformat()
        }
        manifestations.append(manifestation)

    # Check for PDF files
    pdf_files = self.find_pdf_manifestations(law_uri)
    for pdf_file in pdf_files:
        manifestation = {
            'uri': f"{law_uri}/manifestation/pdf/{pdf_file.stem}",
            'format': 'pdf',
            'file_path': str(pdf_file),
            'file_size': pdf_file.stat().st_size,
            'checksum': self.calculate_file_hash(pdf_file),
            'language': self.detect_file_language(pdf_file)
        }
        manifestations.append(manifestation)

    return manifestations

def find_html_manifestations(self, law_uri: str) -> List[Path]:
    """Find HTML files for a law in fedlex-assets"""
    # Extract SR number from URI
    sr_number = self.extract_sr_from_uri(law_uri)

    # Search in fedlex-assets directory
    html_pattern = f"**/*/de/html/*{sr_number}*de-html.html"
    return list(Path("fedlex-assets").glob(html_pattern))
```

## Integration Points

### With Existing Systems
- **TASK-006 Integration**: Use temporal version handler for VersionNode dates
- **Article Extractor**: Extend to detect and extract subpoints
- **Storage Pipeline**: Add new node types to batch processing
- **Schema Validation**: Extend validation for new node types

### New Relationships to Create
```cypher
-- Version relationships
(Law)-[:HAS_VERSION]->(Version)
(Version)-[:SUPERSEDES]->(Version)

-- Act relationships
(Law)-[:ENACTED_BY]->(Act)
(Act)-[:AMENDS]->(Law)

-- Subpoint relationships
(Paragraph)-[:HAS_SUBPOINT]->(Subpoint)

-- Manifestation relationships
(Law)-[:MANIFESTED_AS]->(Manifestation)
(Article)-[:MANIFESTED_AS]->(Manifestation)
```

## Dependencies
- **TASK-006**: Temporal Version Handler (for VersionNode integration)
- **TASK-014.1**: Schema alignment (foundation)
- **File System**: Access to fedlex-assets for manifestations
- **HTML Parser**: For subpoint extraction from article content

## Testing Requirements
- **Unit Tests**: Each new node type extraction
- **Integration Tests**: New relationships work correctly
- **Temporal Tests**: Version queries return correct results
- **Performance Tests**: Impact on build time and memory
- **Validation Tests**: All new nodes validate against schema

## Success Metrics
- [ ] VersionNode: 100% of law versions extracted
- [ ] ActNode: All OC/AS/RO publications tracked
- [ ] SubpointNode: All lettered subpoints parsed
- [ ] ManifestationNode: All document formats catalogued
- [ ] Temporal queries work: "Find SR 101 version on 2020-01-01"
- [ ] Performance impact < 15% on build time
- [ ] Schema validation passes for all new nodes

## Files to Create/Modify
- `/home/mxlk/LAWAST/scripts/build_lawast_graph.py` - Add new node creation
- `/home/mxlk/LAWAST/src/extractors/version_extractor.py` - NEW (or extend existing)
- `/home/mxlk/LAWAST/src/extractors/act_extractor.py` - NEW (or extend existing)
- `/home/mxlk/LAWAST/src/extractors/subpoint_extractor.py` - NEW
- `/home/mxlk/LAWAST/src/extractors/manifestation_extractor.py` - NEW

## Risk Assessment
- **Risk Level**: HIGH (new functionality)
- **Main Risks**:
  - Complex temporal logic: HIGH impact, MEDIUM probability
  - File system dependencies: MEDIUM impact, HIGH probability
  - Performance degradation: MEDIUM impact, MEDIUM probability
- **Mitigation**: Incremental implementation, extensive testing, feature flags