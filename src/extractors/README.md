# Fedlex Data Extractors

This module contains components for extracting entities and relationships from Fedlex legal data.

## Components

### 1. URI Resolver (`uri_resolver.py`)
Handles normalization and decomposition of Fedlex URIs.

**Key Functions:**
- `normalize_uri()`: Ensures consistent URI format
- `extract_language_code()`: Gets language from URI (de/fr/it/rm/en)
- `extract_format()`: Gets document format (html/pdf/xml/docx)
- `get_parent_law_uri()`: Extracts parent law from version URI
- `extract_sr_number()`: Generates SR number with special case handling

**Special Cases Handled:**
- Roman numerals: `/eli/cc/I/271` → "SR I 271"
- Double underscores: `/eli/cc/1959/__1811` → "Special 1811"
- Multi-part numbers: `271_271_445` → Historical numbering

### 2. Relationship Extractor (`relationship_extractor.py`)
Extracts relationships from JSON metadata files.

**Relationship Types:**
- `HAS_VERSION`: Law → Version
- `SUPERSEDES`: Version → Older Version
- `EXPRESSED_IN`: Entity → Language Expression
- `MANIFESTED_AS`: Expression → Format
- `AMENDS`: Act → Amended Law
- `REFERENCES`: Cross-references (for TASK-005)

**Processing Methods:**
- `extract_from_consolidation_abstract()`: Main law files
- `extract_from_version()`: Version-specific files
- `extract_from_act()`: Official compilation files

### 3. Version Chain Builder (`version_chain_builder.py`)
Creates temporal chains between law versions.

**Key Features:**
- Builds SUPERSEDES relationships chronologically
- Validates chain integrity
- Repairs broken chains
- Provides version timelines

## Usage

### Basic Extraction
```python
from src.extractors.relationship_extractor import RelationshipExtractor
from src.data_access.graph_builder import GraphBuilder

builder = GraphBuilder()
extractor = RelationshipExtractor(builder)

# Process single file
relationships = extractor.extract_from_file("fedlex/eli/cc/1999/404.json")

# Process directory
stats = extractor.process_directory("fedlex/eli/cc", pattern="*.json")
```

### URI Resolution
```python
from src.extractors.uri_resolver import URIResolver

resolver = URIResolver()

# Normalize URI
uri = resolver.normalize_uri("http://fedlex.data.admin.ch/eli/cc/1999/404/")
# Returns: "https://fedlex.data.admin.ch/eli/cc/1999/404"

# Extract components
components = resolver.decompose_uri(uri)
# Returns: {
#   "normalized": "...",
#   "type": "cc",
#   "sr_number": "SR 1999.404",
#   "is_version": False,
#   "language": None,
#   "format": None
# }
```

### Version Chains
```python
from src.extractors.version_chain_builder import VersionChainBuilder

chain_builder = VersionChainBuilder()

# Build all chains
stats = chain_builder.build_all_chains()

# Build for specific law
result = chain_builder.build_chain_for_law("https://fedlex.data.admin.ch/eli/cc/1999/404")

# Validate chains
validation = chain_builder.validate_chains()
```

## Running the Complete Extraction

Use the provided script:
```bash
# Test with limited files
python scripts/run_relationship_extraction.py --limit 100

# Full extraction
python scripts/run_relationship_extraction.py

# Custom batch size
python scripts/run_relationship_extraction.py --batch-size 10000

# Skip validation
python scripts/run_relationship_extraction.py --skip-validation
```

## Performance Considerations

- **Batch Size**: Default 5000 relationships per batch
- **Memory Usage**: ~2GB for extraction process
- **Processing Rate**: ~100 files/second
- **Total Time**: ~2 hours for complete Fedlex dataset

## Dependencies

Required packages (in requirements.txt):
- `neo4j>=5.14.0`: Graph database driver
- `ijson>=3.2.0`: Streaming JSON parser
- `rich>=13.0.0`: Progress display
- `python-dotenv>=1.0.0`: Environment configuration

## Testing

Run tests with:
```bash
pytest tests/test_relationship_extractor.py -v
```

## Data Flow

1. **JSON Files** → URI Resolver → Normalized URIs
2. **Normalized URIs** → Relationship Extractor → Relationship Tuples
3. **Relationship Tuples** → Graph Builder → Neo4j Database
4. **Version Data** → Version Chain Builder → SUPERSEDES Relationships

## Error Handling

- Malformed JSON: Logged and skipped
- Missing nodes: Relationships skipped, logged as warnings
- URI parsing errors: Returns None, continues processing
- Batch failures: Retries with exponential backoff

## Statistics Tracking

The extractor tracks:
- Files processed
- Relationships created by type
- Processing errors
- Time elapsed
- Processing rate (files/second)

## Future Enhancements

- Parallel processing for faster extraction
- Incremental updates (only process changed files)
- Relationship validation rules
- Custom relationship properties extraction