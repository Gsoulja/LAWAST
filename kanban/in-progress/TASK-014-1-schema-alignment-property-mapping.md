# TASK-014.1: Schema Alignment and Property Mapping

**Status**: IN-PROGRESS
**Priority**: HIGH
**Type**: feature
**Parent**: TASK-014
**Estimated Effort**: 2-3 days
**Created**: 2025-09-26
**Started**: 2025-09-26
**Assigned**: Active Development
**Analysis Completed**: 2025-09-26

## Description
Align existing node types (LawNode, ArticleNode, ParagraphNode) with complete schema definitions by implementing missing properties and fixing property name mismatches. This is the foundation for complete schema coverage.

## Problem Analysis
Current implementation gaps:
- **LawNode**: Missing 15 of 24 parameters (62% incomplete)
- **ArticleNode**: Missing 5 parameters (25% incomplete)
- **ParagraphNode**: Missing 3 parameters (25% incomplete)
- Property name mismatches between schema and implementation

## Acceptance Criteria
- [ ] All LawNode properties implemented according to schema
- [ ] All ArticleNode properties implemented according to schema
- [ ] All ParagraphNode properties implemented according to schema
- [ ] Property mapping layer validates schema compliance
- [ ] Backward compatibility maintained for existing builds
- [ ] Performance impact < 10% for property additions
- [ ] All unit tests pass
- [ ] Schema validation framework implemented

## Technical Analysis (Auto-generated 2025-09-26)

### Fedlex Data Pattern Analysis

#### Available Fields in ConsolidationAbstract JSON:
**Standard fields (always present):**
- `data.uri` - Law URI
- `data.type` - Always includes "ConsolidationAbstract"
- `data.attributes.dateDocument` - Original document date
- `data.attributes.dateEntryInForce` - When law became active
- `data.attributes.basicAct` - Reference to original act
- `data.attributes.typeDocument` - Document type URI
- `data.references.isRealizedBy` - Language expressions (DE, FR, IT, sometimes RM, EN)
- `data.references.inForceStatus` - Enforcement status URI
- `data.references.classifiedByTaxonomyEntry` - Taxonomy classification URI

**Optional fields (context-dependent):**
- `data.attributes.dateNoLongerInForce` - For repealed laws (e.g., historical laws)
- `included[].attributes.titleShort` - Abbreviations (BV, Cst., Cost.) - not all laws have this
- `included[].attributes.title` - Full titles in each language

**Missing fields (not in Fedlex data):**
- ❌ `dateModified` - Must generate from file timestamp or current date
- ❌ `status` - Must derive from inForceStatus URI
- ❌ `type` - Must hardcode as "Law"
- ❌ `language` - Must detect primary language from available expressions
- ❌ `parent_uri` - Rarely present, mostly null
- ❌ `ast_path`, `ast_level`, `parent_id` - Must generate programmatically

### Edge Cases Identified

1. **Language Variations**:
   - SR 101: Has all 5 languages (DE, FR, IT, RM, EN)
   - Historical laws: Often only 3 languages (DE, FR, IT)
   - Some laws: Missing RM and EN translations
   - **Solution**: Use dict.get() with None defaults for all language fields

2. **Date Fields**:
   - Active laws: Have dateDocument and dateEntryInForce
   - Repealed laws: Also have dateNoLongerInForce
   - Future laws: dateEntryInForce may be in future
   - **Solution**: Check existence before extraction

3. **Abbreviations (titleShort)**:
   - SR 101: Has abbreviations (BV, Cst., Cost.)
   - Many laws: No abbreviations at all
   - **Solution**: Extract only if present, default to None

4. **SR Number Extraction**:
   - Standard format: /eli/cc/1999/404 → SR 101 (from taxonomy)
   - Historical format: /eli/cc/I/271_271_445 → Need special parsing
   - **Solution**: Multiple extraction strategies with fallback

5. **Enforcement Status**:
   - Status 0: Currently in force
   - Status 3: No longer in force
   - **Solution**: Map vocabulary URIs to boolean/string values

### Multilingual Article/Paragraph Analysis

#### Article Extraction Findings:
- **Article Count Inconsistency**: DE/FR/IT have 231 articles, RM/EN have 232 articles
- **All languages present**: SR 101 has complete translations in all 5 languages
- **HTML structure**: Each language in separate directory with identical article structure
- **Article numbering**: Consistent across languages (Art. 1-197 + transitional provisions)

#### Paragraph Structure:
- **Numbered paragraphs**: Format "1 Text...", "2 Text...", "3 Text..."
- **Lettered subpoints**: Format "a. Text...", "b. Text...", "c. Text..."
- **Language consistency**: Same paragraph/subpoint structure across all languages
- **Text length variations**: DE ~400 chars, FR ~450 chars, EN ~380 chars per article

#### Critical Implementation Requirements:
1. **Multi-language node creation**:
   - Create ONE Article node with content from primary language
   - Store article URI with language suffix for each translation
   - Link to Law node regardless of language

2. **Paragraph handling**:
   - Create separate Paragraph nodes for EACH language
   - Include language property on each Paragraph node
   - Maintain paragraph numbering across languages

3. **Subpoint detection**:
   - Check for lettered items (a., b., c.)
   - Set `has_subpoints: true` on parent Paragraph
   - Consider creating Subpoint nodes for deep queries

### Existing Resources Found
- **Extractors**:
  - `law_extractor.py` - Basic LawNode extraction
  - `uri_resolver.py` - Has extract_sr_number(), extract_language_code()
  - `version_extractor.py` - Exists but not integrated
- **Services**:
  - Neo4j connection management
  - Embedding generator already configured
- **Database**:
  - Indexes on uri, sr_number, in_force already exist
  - Vector indexes configured for 768 dimensions

### Dependencies Required
- No new Python packages needed
- Neo4j driver already installed
- JSON parsing via built-in json module

### Impact Assessment
#### Files to Modify
- `/scripts/build_lawast_graph.py`: Add 23 new property extractions
- `/src/extractors/property_extractor.py`: NEW - Centralized extraction functions
- `/src/data_access/schema_mapper.py`: NEW - Validation layer

#### Breaking Change Risk
- **LOW**: All new properties are optional
- **Mitigation**: Use feature flag `--strict-schema` for validation

## Technical Implementation

### 1. Missing LawNode Properties
Implement the 15 missing properties with Fedlex-aware extraction:

```python
# Add to LawNode creation in process_bundesverfassung():
def extract_law_properties(data: Dict, file_path: Path) -> Dict:
    """Extract all LawNode properties from Fedlex data"""

    # Extract multilingual titles from included section
    titles = {}
    for item in data.get('included', []):
        if item.get('type') == 'Expression':
            lang = item.get('references', {}).get('language', '').split('/')[-1].lower()
            if lang in ['deu', 'fra', 'ita', 'roh', 'eng']:
                lang_map = {'deu': 'de', 'fra': 'fr', 'ita': 'it', 'roh': 'rm', 'eng': 'en'}
                titles[lang_map[lang]] = item.get('attributes', {}).get('title', {}).get('xsd:string')

                # Also extract abbreviations
                abbrev = item.get('attributes', {}).get('titleShort', {}).get('xsd:string')
                if abbrev:
                    titles[f'abbreviation_{lang_map[lang]}'] = abbrev

    attrs = data['data'].get('attributes', {})
    refs = data['data'].get('references', {})

    # Map enforcement status URI to boolean and string
    in_force_status_uri = refs.get('inForceStatus', '')
    in_force = not in_force_status_uri.endswith('/3')  # Status 3 = no longer in force
    status = 'in_force' if in_force else 'repealed'

    # Extract SR number from taxonomy or URI
    sr_number = extract_sr_from_taxonomy(refs.get('classifiedByTaxonomyEntry', ''))
    if not sr_number:
        sr_number = extract_sr_from_uri(data['data']['uri'])

    return {
        'uri': data['data']['uri'],
        'sr_number': sr_number,
        # Multilingual fields
        'title_de': titles.get('de'),
        'title_fr': titles.get('fr'),
        'title_it': titles.get('it'),
        'title_rm': titles.get('rm'),  # May be None
        'title_en': titles.get('en'),  # May be None
        'abbreviation_de': titles.get('abbreviation_de'),
        'abbreviation_fr': titles.get('abbreviation_fr'),
        'abbreviation_it': titles.get('abbreviation_it'),
        # Date fields
        'date_document': attrs.get('dateDocument', {}).get('xsd:date'),
        'date_entry_in_force': attrs.get('dateEntryInForce', {}).get('xsd:date'),
        'date_no_longer_in_force': attrs.get('dateNoLongerInForce', {}).get('xsd:date'),
        'date_modified': datetime.now().isoformat(),  # Generated
        # Status fields
        'in_force': in_force,
        'in_force_status': in_force_status_uri,
        'status': status,
        # References
        'basic_act': attrs.get('basicAct', {}).get('rdfs:Resource'),
        'classified_by_taxonomy': refs.get('classifiedByTaxonomyEntry'),
        'type_document': attrs.get('typeDocument', {}).get('rdfs:Resource'),
        # Metadata
        'type': 'Law',  # Hardcoded
        'language': detect_primary_language(titles),  # Based on available translations
        'parent_uri': None,  # Rarely present in Fedlex
        # AST properties
        'ast_path': f'/sr_{sr_number}',
        'ast_level': 5,
        'parent_id': None  # Will be set if part of hierarchy
    }
```

### 2. ArticleNode Properties with Multi-language Support

```python
def extract_article_multilingual(article_num: int, law_uri: str, languages: List[str]) -> Dict:
    """Extract article from all available language versions"""

    article_data = {
        'uri': f'{law_uri}/art_{article_num}',
        'law_uri': law_uri,
        'number': str(article_num),
        'number_normalized': article_num,
        'position': article_num,  # Order within law
        'parent_id': law_uri,
        'content_uri': f'{law_uri}/art_{article_num}/content',
        'ast_level': 6,
        'ast_path': f'{law_uri.split("/")[-1]}/art_{article_num}'
    }

    # Extract content from each language
    content_by_lang = {}
    for lang in languages:
        html_path = f'fedlex-assets/{law_uri}/{lang}/html/*.html'
        article_content = extract_article_from_html(html_path, article_num, lang)
        if article_content:
            content_by_lang[lang] = article_content

            # Use first available language for primary content
            if 'content_full' not in article_data:
                article_data['content_full'] = article_content['text']
                article_data['title'] = article_content.get('title', '')
                article_data['content_preview'] = article_content['text'][:500]

    # Store language variants
    article_data['content_languages'] = list(content_by_lang.keys())
    article_data['content_by_language'] = content_by_lang

    # Extract section/chapter from article title or structure
    if 'title' in article_data:
        article_data['section'] = extract_section_from_title(article_data['title'])
        article_data['chapter'] = extract_chapter_from_title(article_data['title'])

    return article_data
```

### 3. ParagraphNode Properties with Language Support

```python
def extract_paragraphs_multilingual(article_uri: str, article_content_by_lang: Dict) -> List[Dict]:
    """Extract paragraphs from article in all languages"""

    paragraphs = []

    for lang, content in article_content_by_lang.items():
        # Parse numbered paragraphs
        para_pattern = r'^(\d+)\s+(.+?)(?=^\d+\s+|\Z)'
        matches = re.findall(para_pattern, content['text'], re.MULTILINE | re.DOTALL)

        for para_num, para_text in matches:
            para_text = para_text.strip()

            # Check for subpoints
            subpoint_pattern = r'^[a-z]\.\s+'
            has_subpoints = bool(re.search(subpoint_pattern, para_text, re.MULTILINE))

            paragraph = {
                'uri': f'{article_uri}/para_{para_num}/{lang}',
                'article_uri': article_uri,
                'number': para_num,
                'text': para_text,
                'language': lang,  # Critical for multilingual support
                'position': int(para_num),
                'parent_id': article_uri,
                'word_count': len(para_text.split()),
                'has_subpoints': has_subpoints,
                'ast_level': 7,
                'ast_path': f'{article_uri}/para_{para_num}'
            }

            # Extract subpoints if present
            if has_subpoints:
                subpoints = re.findall(r'^([a-z])\.\s+(.+?)(?=^[a-z]\.\s+|^\d+\s+|\Z)',
                                     para_text, re.MULTILINE | re.DOTALL)
                paragraph['subpoint_count'] = len(subpoints)

            paragraphs.append(paragraph)

    return paragraphs
```

### 4. Property Mapping Layer
Create validation framework:

```python
class SchemaPropertyMapper:
    """Maps and validates properties against graph schema"""

    def __init__(self, schema: GraphSchema):
        self.schema = schema
        self.node_validators = {
            'Law': self._validate_law_node,
            'Article': self._validate_article_node,
            'Paragraph': self._validate_paragraph_node
        }

    def validate_and_map(self, node_type: str, properties: Dict) -> Dict:
        """Validate properties against schema and return mapped properties"""
        validator = self.node_validators.get(node_type)
        if not validator:
            raise ValueError(f"Unknown node type: {node_type}")

        return validator(properties)

    def _validate_law_node(self, props: Dict) -> Dict:
        """Validate LawNode properties against schema"""
        # Check required fields
        required = ['uri', 'sr_number']
        for field in required:
            if field not in props:
                raise ValueError(f"Missing required field: {field}")

        # Map optional fields with defaults
        mapped = props.copy()
        optional_defaults = {
            'ast_level': 5,
            'type': 'Law',
            'in_force': True,
        }

        for field, default in optional_defaults.items():
            mapped.setdefault(field, default)

        return mapped
```

## Dependencies
- **Schema Module**: `/home/mxlk/LAWAST/src/data_access/graph_schema.py`
- **Current Builder**: `/home/mxlk/LAWAST/scripts/build_lawast_graph.py`
- **Extractors**: Article and Law extractors for property extraction
- **JSON Data**: Fedlex ConsolidationAbstract files for metadata

## Implementation Steps
1. **Audit Current Implementation**
   - Map current properties to schema requirements
   - Identify exact gaps and mismatches

2. **Create Property Extraction Functions**
   - `extract_date_no_longer_in_force()` - Parse dateNoLongerInForce
   - `extract_in_force_status_uri()` - Get enforcement status URI
   - `extract_taxonomy_uri()` - Parse classifiedByTaxonomyEntry
   - `extract_basic_act_uri()` - Get original act reference
   - And 11 more extraction functions...

3. **Implement Property Mapping Layer**
   - Schema validation framework
   - Property name mapping
   - Default value handling

4. **Update Node Creation Logic**
   - Extend LawNode creation in `process_bundesverfassung()`
   - Enhance ArticleNode creation in `extract_bv_articles()`
   - Improve ParagraphNode creation in `extract_paragraphs()`

5. **Add Backward Compatibility**
   - Feature flags for new properties
   - Graceful degradation for missing data

6. **Testing and Validation**
   - Unit tests for each extraction function
   - Schema validation tests
   - Integration tests with real Fedlex data

## Testing Requirements
- **Property Extraction Tests**: Each new extraction function
- **Schema Validation Tests**: All node types validate correctly
- **Backward Compatibility Tests**: Existing builds still work
- **Integration Tests**: End-to-end graph building
- **Performance Tests**: < 10% impact from new properties

## Success Metrics
- [ ] LawNode: 24/24 properties implemented (100% complete)
- [ ] ArticleNode: All properties implemented (100% complete)
- [ ] ParagraphNode: All properties implemented (100% complete)
- [ ] Schema validation passes for all nodes
- [ ] No breaking changes to existing functionality
- [ ] Performance impact < 10%

## Files to Modify
- `/home/mxlk/LAWAST/scripts/build_lawast_graph.py` - Main implementation
- `/home/mxlk/LAWAST/src/data_access/schema_mapper.py` - NEW validation layer
- `/home/mxlk/LAWAST/src/extractors/property_extractor.py` - NEW extraction functions

## Implementation Checklist
Based on Fedlex data analysis:
- [ ] Handle missing languages gracefully (RM, EN often absent)
- [ ] Extract dateNoLongerInForce only when present
- [ ] Map enforcement status URIs correctly
- [ ] Parse historical SR formats (I/271_271_445)
- [ ] Generate dateModified as current timestamp
- [ ] Default parent_uri to None (rarely in data)
- [ ] Extract abbreviations when available
- [ ] Validate all dates are valid xsd:date format
- [ ] Test with both current and historical laws

## Risk Assessment
- **Risk Level**: MEDIUM
- **Adjusted Effort**: 2-3 days confirmed
- **Main Risks**:
  - Breaking existing builds: HIGH impact, LOW probability
  - Performance degradation: MEDIUM impact, MEDIUM probability
  - Property extraction errors: HIGH impact, MEDIUM probability
- **Mitigation**: Comprehensive testing, feature flags, gradual rollout