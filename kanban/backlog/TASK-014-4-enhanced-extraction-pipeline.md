# TASK-014.4: Enhanced Extraction Pipeline

**Status**: BACKLOG
**Priority**: MEDIUM
**Type**: feature
**Parent**: TASK-014
**Estimated Effort**: 2 days
**Created**: 2025-09-26
**Assigned**: Unassigned

## Description
Enhance the existing extraction pipeline to handle the complete schema requirements and new node types. This integrates all previous sub-tasks into a cohesive, efficient pipeline that maintains backward compatibility while enabling full graph schema coverage.

## Problem Analysis
Current pipeline limitations:
- Limited integration between extractors
- No centralized property mapping
- Inconsistent error handling across extractors
- No validation pipeline for schema compliance
- Performance not optimized for new node types
- No extraction orchestration for complex relationships

## Acceptance Criteria
- [ ] Unified extraction pipeline handles all 8 node types
- [ ] Property mapping layer ensures schema compliance
- [ ] Error handling is consistent across all extractors
- [ ] Performance improved or maintained despite new functionality
- [ ] Backward compatibility with existing functionality
- [ ] Comprehensive logging and monitoring
- [ ] Extraction orchestration for complex multi-node relationships
- [ ] Validation pipeline ensures data quality

## Technical Implementation

### 1. Enhanced Extraction Orchestrator
Create a master orchestrator that coordinates all extractors:

```python
class EnhancedExtractionPipeline:
    """
    Orchestrates extraction of all node types with proper dependency handling
    """

    def __init__(self, connection, schema_mapper, sr_filter=None):
        self.connection = connection
        self.schema_mapper = schema_mapper
        self.sr_filter = sr_filter

        # Initialize all extractors
        self.extractors = {
            'law': LawExtractor(schema_mapper),
            'version': VersionExtractor(schema_mapper),
            'act': ActExtractor(schema_mapper),
            'article': ArticleExtractor(schema_mapper),
            'paragraph': ParagraphExtractor(schema_mapper),
            'subpoint': SubpointExtractor(schema_mapper),
            'manifestation': ManifestationExtractor(schema_mapper)
        }

        # Extraction order (dependencies matter)
        self.extraction_order = [
            'law',          # Must be first (other nodes reference laws)
            'version',      # Versions belong to laws
            'act',          # Acts relate to laws
            'manifestation', # Document formats for laws
            'article',      # Articles belong to laws
            'paragraph',    # Paragraphs belong to articles
            'subpoint'      # Subpoints belong to paragraphs
        ]

        self.stats = ExtractionStatistics()

    def extract_from_file(self, file_path: Path) -> ExtractionResult:
        """Extract all node types from a single JSON file"""
        result = ExtractionResult()

        try:
            # Load and validate JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Apply SR filtering early if specified
            if self.sr_filter:
                sr_number = self.extractors['law'].extract_sr_number(data)
                if not self._matches_sr_filter(sr_number):
                    return result  # Skip this file

            # Extract nodes in dependency order
            extracted_data = {}

            for node_type in self.extraction_order:
                extractor = self.extractors[node_type]

                try:
                    # Pass previously extracted data for dependency resolution
                    extraction_context = ExtractionContext(
                        file_path=file_path,
                        source_data=data,
                        extracted_nodes=extracted_data,
                        sr_filter=self.sr_filter
                    )

                    node_result = extractor.extract(extraction_context)
                    if node_result.has_nodes():
                        extracted_data[node_type] = node_result.nodes
                        result.merge(node_result)

                    self.stats.record_extraction(node_type, len(node_result.nodes))

                except Exception as e:
                    error_msg = f"Failed to extract {node_type} from {file_path}: {e}"
                    logger.error(error_msg)
                    result.add_error(error_msg)
                    self.stats.record_error(node_type, str(e))

            # Validate extracted data
            validation_result = self._validate_extracted_data(extracted_data)
            result.merge(validation_result)

        except Exception as e:
            error_msg = f"Failed to process file {file_path}: {e}"
            logger.error(error_msg)
            result.add_error(error_msg)

        return result

    def _validate_extracted_data(self, extracted_data: Dict) -> ExtractionResult:
        """Validate consistency across extracted nodes"""
        result = ExtractionResult()

        try:
            # Validate required relationships exist
            law_nodes = extracted_data.get('law', [])
            article_nodes = extracted_data.get('article', [])

            # Check that articles reference valid laws
            law_uris = {law['uri'] for law in law_nodes}
            for article in article_nodes:
                law_uri = article.get('law_uri')
                if law_uri and law_uri not in law_uris:
                    result.add_warning(f"Article {article['uri']} references unknown law {law_uri}")

            # Validate AST paths are consistent
            self._validate_ast_paths(extracted_data, result)

            # Validate property completeness
            self._validate_property_completeness(extracted_data, result)

        except Exception as e:
            result.add_error(f"Validation failed: {e}")

        return result

    def _validate_ast_paths(self, extracted_data: Dict, result: ExtractionResult):
        """Validate AST path consistency"""
        for node_type, nodes in extracted_data.items():
            for node in nodes:
                ast_path = node.get('ast_path')
                ast_level = node.get('ast_level')

                if ast_path and ast_level:
                    # Validate path depth matches level
                    path_depth = len(ast_path.strip('/').split('/'))
                    if path_depth != ast_level:
                        result.add_warning(
                            f"{node_type} node {node['uri']} has inconsistent AST path depth"
                        )
```

### 2. Extraction Context System
Provide rich context to extractors:

```python
@dataclass
class ExtractionContext:
    """Context provided to extractors with all necessary information"""
    file_path: Path
    source_data: Dict[str, Any]
    extracted_nodes: Dict[str, List[Dict]]  # Previously extracted nodes
    sr_filter: Optional[str] = None
    extraction_options: Dict[str, Any] = field(default_factory=dict)

    def get_law_nodes(self) -> List[Dict]:
        """Get previously extracted law nodes"""
        return self.extracted_nodes.get('law', [])

    def get_primary_law_uri(self) -> Optional[str]:
        """Get the primary law URI from extracted data"""
        laws = self.get_law_nodes()
        return laws[0]['uri'] if laws else None

    def get_articles_for_law(self, law_uri: str) -> List[Dict]:
        """Get articles for a specific law"""
        articles = self.extracted_nodes.get('article', [])
        return [a for a in articles if a.get('law_uri') == law_uri]
```

### 3. Enhanced Property Mapping Integration
Integrate the schema mapper throughout the pipeline:

```python
class SchemaCompliantExtractor(BaseExtractor):
    """Base extractor that ensures schema compliance"""

    def __init__(self, schema_mapper: SchemaPropertyMapper):
        super().__init__()
        self.schema_mapper = schema_mapper

    def extract_and_validate(self, context: ExtractionContext, node_type: str) -> ExtractionResult:
        """Extract nodes and validate against schema"""
        result = self.extract_nodes(context)

        # Validate and map each node
        validated_nodes = []
        for node in result.nodes:
            try:
                validated_node = self.schema_mapper.validate_and_map(node_type, node)
                validated_nodes.append(validated_node)
            except ValueError as e:
                result.add_error(f"Schema validation failed for {node_type}: {e}")

        result.nodes = validated_nodes
        return result

    def extract_nodes(self, context: ExtractionContext) -> ExtractionResult:
        """Override in subclasses to implement specific extraction logic"""
        raise NotImplementedError
```

### 4. Performance Optimization
Optimize pipeline for new node types:

```python
class PerformanceOptimizedPipeline(EnhancedExtractionPipeline):
    """Pipeline with performance optimizations"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_caching = True
        self.batch_size = 100
        self.parallel_processing = True

    def extract_from_files_batch(self, file_paths: List[Path]) -> List[ExtractionResult]:
        """Process multiple files in parallel with caching"""
        if not self.parallel_processing:
            return [self.extract_from_file(f) for f in file_paths]

        # Use ThreadPoolExecutor for I/O bound operations
        with ThreadPoolExecutor(max_workers=self.batch_size // 10) as executor:
            futures = [executor.submit(self.extract_from_file, f) for f in file_paths]
            results = []

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    error_result = ExtractionResult()
                    error_result.add_error(f"Parallel processing failed: {e}")
                    results.append(error_result)

        return results

    def _cache_extraction_results(self, file_path: Path, result: ExtractionResult):
        """Cache extraction results for reuse"""
        if not self.enable_caching:
            return

        cache_key = f"{file_path.stat().st_mtime}_{file_path.stat().st_size}"
        # Implement caching logic here
```

### 5. Enhanced Error Handling and Monitoring
Comprehensive error handling across the pipeline:

```python
class ExtractionMonitor:
    """Monitors extraction pipeline health and performance"""

    def __init__(self):
        self.metrics = {
            'files_processed': 0,
            'nodes_extracted': defaultdict(int),
            'errors': defaultdict(list),
            'warnings': defaultdict(list),
            'processing_times': defaultdict(list),
            'start_time': datetime.now()
        }

    def record_file_processing(self, file_path: Path, processing_time: float):
        """Record file processing metrics"""
        self.metrics['files_processed'] += 1
        self.metrics['processing_times']['file'].append(processing_time)

    def record_node_extraction(self, node_type: str, count: int, processing_time: float):
        """Record node extraction metrics"""
        self.metrics['nodes_extracted'][node_type] += count
        self.metrics['processing_times'][node_type].append(processing_time)

    def record_error(self, component: str, error: str):
        """Record extraction error"""
        self.metrics['errors'][component].append({
            'error': error,
            'timestamp': datetime.now().isoformat()
        })

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive extraction report"""
        end_time = datetime.now()
        duration = (end_time - self.metrics['start_time']).total_seconds()

        return {
            'summary': {
                'total_duration': duration,
                'files_processed': self.metrics['files_processed'],
                'total_nodes': sum(self.metrics['nodes_extracted'].values()),
                'total_errors': sum(len(errors) for errors in self.metrics['errors'].values()),
                'throughput': self.metrics['files_processed'] / duration if duration > 0 else 0
            },
            'nodes_by_type': dict(self.metrics['nodes_extracted']),
            'average_processing_times': {
                component: statistics.mean(times) if times else 0
                for component, times in self.metrics['processing_times'].items()
            },
            'error_summary': {
                component: len(errors)
                for component, errors in self.metrics['errors'].items()
            }
        }
```

### 6. Integration with Build Script
Integrate enhanced pipeline into build script:

```python
def run_enhanced_extraction(self, json_files: List[Path]):
    """Run the enhanced extraction pipeline"""
    console.print("\n[bold cyan]🔄 Running Enhanced Extraction Pipeline[/bold cyan]")

    # Initialize enhanced pipeline
    schema_mapper = SchemaPropertyMapper(GraphSchema())
    pipeline = EnhancedExtractionPipeline(
        connection=self.connection,
        schema_mapper=schema_mapper,
        sr_filter=getattr(self.args, 'sr_filter', None)
    )

    monitor = ExtractionMonitor()
    all_results = []

    # Process files in batches
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:

        task = progress.add_task(
            f"Processing {len(json_files)} files...",
            total=len(json_files)
        )

        for i in range(0, len(json_files), self.batch_size):
            batch = json_files[i:i+self.batch_size]

            start_time = time.time()
            batch_results = pipeline.extract_from_files_batch(batch)
            processing_time = time.time() - start_time

            # Record metrics
            for result in batch_results:
                monitor.record_file_processing(batch[0], processing_time / len(batch))
                all_results.append(result)

            progress.advance(task, len(batch))

    # Generate and display report
    report = monitor.generate_report()
    self._display_extraction_report(report)

    return all_results
```

## Integration Points
- **TASK-014.1**: Uses property mapping layer
- **TASK-014.2**: Orchestrates all new node extractors
- **TASK-014.3**: Integrates SR filtering system
- **Existing extractors**: Extends current extraction capabilities

## Testing Requirements
- **Pipeline Integration Tests**: End-to-end extraction workflow
- **Performance Tests**: Ensure no regression in processing speed
- **Error Handling Tests**: Graceful failure recovery
- **Schema Validation Tests**: All nodes validate correctly
- **Parallel Processing Tests**: Thread safety and correctness

## Success Metrics
- [ ] All 8 node types extracted correctly in single pipeline run
- [ ] Schema validation passes for 100% of extracted nodes
- [ ] Performance maintained or improved despite new functionality
- [ ] Error rate < 1% for well-formed input files
- [ ] Processing throughput > 10 files/second
- [ ] Memory usage remains stable during large batch processing

## Dependencies
- **TASK-014.1**: Property mapping layer
- **TASK-014.2**: New node type extractors
- **TASK-014.3**: SR filtering system
- **Existing extractors**: Current article and law extractors

## Risk Assessment
- **Risk Level**: MEDIUM
- **Main Risks**:
  - Integration complexity: HIGH impact, MEDIUM probability
  - Performance degradation: MEDIUM impact, LOW probability
  - Breaking existing functionality: HIGH impact, LOW probability
- **Mitigation**: Comprehensive testing, gradual rollout, feature flags