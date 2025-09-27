# TASK-014.5: Testing and Validation Framework

**Status**: BACKLOG
**Priority**: MEDIUM
**Type**: feature
**Parent**: TASK-014
**Estimated Effort**: 1-2 days
**Created**: 2025-09-26
**Assigned**: Unassigned

## Description
Build a comprehensive testing and validation framework for the complete LAWAST graph builder. This ensures data quality, schema compliance, and system reliability across all new node types and functionality.

## Problem Analysis
Current testing gaps:
- No schema validation framework
- Limited integration testing for complex pipelines
- No regression testing for new node types
- Insufficient performance testing for complete builds
- No data quality validation
- Missing validation for complex relationships

## Business Value
- **Data Quality**: Ensures reliable graph data for legal queries
- **Development Confidence**: Comprehensive test coverage enables rapid iteration
- **Production Readiness**: Validation framework catches issues before deployment
- **Performance Assurance**: Prevents performance regressions
- **Schema Compliance**: Guarantees all nodes meet schema requirements

## Acceptance Criteria
- [ ] Schema validation framework tests all 8 node types
- [ ] Integration tests cover complete pipeline workflows
- [ ] Performance tests validate build time requirements
- [ ] Data quality tests ensure relationship integrity
- [ ] Regression tests prevent breaking changes
- [ ] All tests run in CI/CD pipeline
- [ ] Test coverage > 90% for new components
- [ ] Clear test documentation and examples

## Technical Implementation

### 1. Schema Validation Framework
Comprehensive validation for all node types:

```python
class GraphSchemaValidator:
    """Validates graph nodes against complete schema requirements"""

    def __init__(self, schema: GraphSchema):
        self.schema = schema
        self.validation_rules = self._initialize_validation_rules()

    def validate_node(self, node_type: str, node_data: Dict[str, Any]) -> ValidationResult:
        """Validate a single node against schema"""
        result = ValidationResult()

        # Get validation rules for node type
        rules = self.validation_rules.get(node_type)
        if not rules:
            result.add_error(f"Unknown node type: {node_type}")
            return result

        # Validate required fields
        for field in rules.required_fields:
            if field not in node_data:
                result.add_error(f"Missing required field: {field}")

        # Validate field types
        for field, expected_type in rules.field_types.items():
            if field in node_data:
                if not isinstance(node_data[field], expected_type):
                    result.add_error(f"Field {field} should be {expected_type.__name__}")

        # Validate field formats
        for field, validator in rules.field_validators.items():
            if field in node_data:
                try:
                    validator(node_data[field])
                except ValidationError as e:
                    result.add_error(f"Field {field} validation failed: {e}")

        # Validate AST properties
        if node_type in ['Law', 'Article', 'Paragraph', 'Subpoint']:
            ast_result = self._validate_ast_properties(node_data)
            result.merge(ast_result)

        return result

    def validate_relationships(self, nodes: Dict[str, List[Dict]]) -> ValidationResult:
        """Validate relationships between nodes"""
        result = ValidationResult()

        # Validate Law -> Article relationships
        laws = nodes.get('Law', [])
        articles = nodes.get('Article', [])

        law_uris = {law['uri'] for law in laws}
        for article in articles:
            law_uri = article.get('law_uri')
            if law_uri and law_uri not in law_uris:
                result.add_error(f"Article {article['uri']} references unknown law {law_uri}")

        # Validate Article -> Paragraph relationships
        paragraphs = nodes.get('Paragraph', [])
        article_uris = {article['uri'] for article in articles}

        for paragraph in paragraphs:
            article_uri = paragraph.get('article_uri')
            if article_uri and article_uri not in article_uris:
                result.add_error(f"Paragraph {paragraph['uri']} references unknown article {article_uri}")

        # Validate temporal relationships (Version nodes)
        versions = nodes.get('Version', [])
        self._validate_temporal_consistency(versions, result)

        return result

    def _validate_ast_properties(self, node_data: Dict) -> ValidationResult:
        """Validate AST path and level consistency"""
        result = ValidationResult()

        ast_path = node_data.get('ast_path')
        ast_level = node_data.get('ast_level')

        if ast_path and ast_level:
            # Count path segments
            path_segments = ast_path.strip('/').split('/')
            expected_segments = ast_level

            if len(path_segments) != expected_segments:
                result.add_error(
                    f"AST path depth ({len(path_segments)}) doesn't match level ({ast_level})"
                )

        return result

    def _validate_temporal_consistency(self, versions: List[Dict], result: ValidationResult):
        """Validate temporal version consistency"""
        # Group versions by law
        versions_by_law = defaultdict(list)
        for version in versions:
            law_uri = version.get('law_uri')
            if law_uri:
                versions_by_law[law_uri].append(version)

        # Check temporal ordering
        for law_uri, law_versions in versions_by_law.items():
            sorted_versions = sorted(
                law_versions,
                key=lambda v: v.get('date_applicable', ''),
                reverse=False
            )

            # Validate no overlapping date ranges
            for i in range(len(sorted_versions) - 1):
                current = sorted_versions[i]
                next_version = sorted_versions[i + 1]

                current_end = current.get('date_end_applicable')
                next_start = next_version.get('date_applicable')

                if current_end and next_start and current_end > next_start:
                    result.add_error(
                        f"Overlapping version dates for law {law_uri}: "
                        f"{current_end} > {next_start}"
                    )
```

### 2. Integration Test Framework
End-to-end pipeline testing:

```python
class PipelineIntegrationTests(unittest.TestCase):
    """Integration tests for complete extraction pipeline"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.test_data_dir = Path("tests/data")
        cls.neo4j_connection = get_test_connection()
        cls.schema_mapper = SchemaPropertyMapper(GraphSchema())

    def test_complete_pipeline_sr_101(self):
        """Test complete pipeline with SR 101 (Bundesverfassung)"""
        # Prepare test data
        sr_101_files = self._get_test_files("sr_101")

        # Initialize pipeline
        pipeline = EnhancedExtractionPipeline(
            connection=self.neo4j_connection,
            schema_mapper=self.schema_mapper,
            sr_filter="101"
        )

        # Run extraction
        results = []
        for file_path in sr_101_files:
            result = pipeline.extract_from_file(file_path)
            results.append(result)

        # Validate results
        self.assertGreater(len(results), 0, "Should extract some results")

        # Check all expected node types are present
        all_nodes = {}
        for result in results:
            for node in result.nodes:
                node_type = node.get('type', 'Unknown')
                if node_type not in all_nodes:
                    all_nodes[node_type] = []
                all_nodes[node_type].append(node)

        # Should have at least Law and Article nodes
        self.assertIn('Law', all_nodes, "Should extract Law nodes")
        self.assertIn('Article', all_nodes, "Should extract Article nodes")

        # Validate schema compliance
        validator = GraphSchemaValidator(GraphSchema())
        for node_type, nodes in all_nodes.items():
            for node in nodes:
                validation_result = validator.validate_node(node_type, node)
                self.assertFalse(
                    validation_result.has_errors(),
                    f"Schema validation failed for {node_type}: {validation_result.errors}"
                )

    def test_sr_filtering_accuracy(self):
        """Test that SR filtering returns only correct files"""
        pipeline = EnhancedExtractionPipeline(
            connection=self.neo4j_connection,
            schema_mapper=self.schema_mapper,
            sr_filter="101"
        )

        # Test with files that should and shouldn't match
        test_files = [
            ("sr_101_test.json", True),   # Should match
            ("sr_220_test.json", False),  # Should not match
            ("sr_311_test.json", False),  # Should not match
        ]

        for filename, should_match in test_files:
            file_path = self.test_data_dir / filename
            if file_path.exists():
                result = pipeline.extract_from_file(file_path)

                if should_match:
                    self.assertGreater(
                        len(result.nodes), 0,
                        f"Should extract nodes from {filename}"
                    )
                else:
                    self.assertEqual(
                        len(result.nodes), 0,
                        f"Should not extract nodes from {filename}"
                    )

    def test_relationship_integrity(self):
        """Test that all relationships are created correctly"""
        # Extract test data
        test_files = self._get_test_files("relationship_test")
        pipeline = EnhancedExtractionPipeline(
            connection=self.neo4j_connection,
            schema_mapper=self.schema_mapper
        )

        all_nodes = defaultdict(list)
        for file_path in test_files:
            result = pipeline.extract_from_file(file_path)
            for node in result.nodes:
                node_type = node.get('type', 'Unknown')
                all_nodes[node_type].append(node)

        # Validate relationships
        validator = GraphSchemaValidator(GraphSchema())
        relationship_result = validator.validate_relationships(dict(all_nodes))

        self.assertFalse(
            relationship_result.has_errors(),
            f"Relationship validation failed: {relationship_result.errors}"
        )
```

### 3. Performance Test Suite
Validate performance requirements:

```python
class PerformanceTests(unittest.TestCase):
    """Performance tests for graph builder"""

    def test_sr_101_build_time(self):
        """Test that SR 101 builds in under 5 minutes"""
        start_time = time.time()

        builder = UnifiedGraphBuilder(
            workers=8,
            batch_size=100,
            checkpoint_enabled=False
        )

        # Mock args for SR 101 build
        args = argparse.Namespace(
            clean=False,
            skip_download=False,
            skip_embeddings=True,  # Skip embeddings for speed
            sr_filter="101"
        )

        success = builder.run(args)
        build_time = time.time() - start_time

        self.assertTrue(success, "Build should succeed")
        self.assertLess(build_time, 300, f"Build time {build_time:.2f}s should be < 300s")

    def test_memory_usage_stability(self):
        """Test that memory usage remains stable during large builds"""
        import psutil
        import gc

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Run multiple extraction cycles
        pipeline = EnhancedExtractionPipeline(
            connection=get_test_connection(),
            schema_mapper=SchemaPropertyMapper(GraphSchema())
        )

        test_files = self._get_large_test_dataset()
        for i in range(10):  # Multiple cycles
            for file_path in test_files[:10]:  # Process subset
                result = pipeline.extract_from_file(file_path)

            # Force garbage collection
            gc.collect()

            current_memory = process.memory_info().rss
            memory_growth = (current_memory - initial_memory) / (1024 * 1024)  # MB

            # Memory should not grow significantly
            self.assertLess(
                memory_growth, 100,
                f"Memory growth {memory_growth:.2f}MB should be < 100MB after {i+1} cycles"
            )

    def test_throughput_requirements(self):
        """Test that processing throughput meets requirements"""
        pipeline = EnhancedExtractionPipeline(
            connection=get_test_connection(),
            schema_mapper=SchemaPropertyMapper(GraphSchema())
        )

        test_files = self._get_test_files("throughput_test")[:100]  # 100 files
        start_time = time.time()

        results = pipeline.extract_from_files_batch(test_files)
        processing_time = time.time() - start_time

        throughput = len(test_files) / processing_time  # files per second
        self.assertGreater(
            throughput, 5.0,
            f"Throughput {throughput:.2f} files/sec should be > 5 files/sec"
        )
```

### 4. Data Quality Validation
Ensure extracted data meets quality standards:

```python
class DataQualityValidator:
    """Validates extracted data quality"""

    def __init__(self):
        self.quality_rules = self._initialize_quality_rules()

    def validate_law_completeness(self, law_nodes: List[Dict]) -> ValidationResult:
        """Validate law data completeness"""
        result = ValidationResult()

        for law in law_nodes:
            # Check for essential titles
            has_german_title = bool(law.get('title_de'))
            has_french_title = bool(law.get('title_fr'))

            if not (has_german_title or has_french_title):
                result.add_warning(
                    f"Law {law['uri']} has no German or French title"
                )

            # Check SR number format
            sr_number = law.get('sr_number')
            if sr_number and not re.match(r'^\d+(\.\d+)*$', sr_number):
                result.add_error(
                    f"Invalid SR number format: {sr_number}"
                )

            # Check date consistency
            date_entry = law.get('date_entry_in_force')
            date_end = law.get('date_no_longer_in_force')

            if date_entry and date_end and date_entry > date_end:
                result.add_error(
                    f"Law {law['uri']} has entry date after end date"
                )

        return result

    def validate_article_structure(self, article_nodes: List[Dict]) -> ValidationResult:
        """Validate article structure quality"""
        result = ValidationResult()

        for article in article_nodes:
            # Check article number format
            number = article.get('number')
            if number and not re.match(r'^\d+[a-z]*$', number):
                result.add_warning(
                    f"Unusual article number format: {number}"
                )

            # Check content completeness
            content_full = article.get('content_full', '')
            content_preview = article.get('content_preview', '')

            if len(content_full) > 0 and len(content_preview) == 0:
                result.add_warning(
                    f"Article {article['uri']} has content but no preview"
                )

            # Check AST consistency
            ast_path = article.get('ast_path')
            if ast_path and not ast_path.endswith(f"/art_{number}"):
                result.add_warning(
                    f"Article {article['uri']} AST path doesn't match number"
                )

        return result
```

### 5. Automated Testing Pipeline
Integration with CI/CD:

```python
#!/usr/bin/env python3
"""
Automated testing pipeline for LAWAST graph builder
"""

class TestPipeline:
    """Coordinates all testing phases"""

    def __init__(self):
        self.test_phases = [
            ('Unit Tests', self.run_unit_tests),
            ('Schema Validation', self.run_schema_tests),
            ('Integration Tests', self.run_integration_tests),
            ('Performance Tests', self.run_performance_tests),
            ('Data Quality Tests', self.run_quality_tests),
        ]

    def run_all_tests(self) -> bool:
        """Run complete test suite"""
        overall_success = True

        for phase_name, test_function in self.test_phases:
            console.print(f"\n[bold cyan]Running {phase_name}...[/bold cyan]")

            try:
                success = test_function()
                if success:
                    console.print(f"[green]✓ {phase_name} passed[/green]")
                else:
                    console.print(f"[red]✗ {phase_name} failed[/red]")
                    overall_success = False

            except Exception as e:
                console.print(f"[red]✗ {phase_name} crashed: {e}[/red]")
                overall_success = False

        return overall_success

    def run_unit_tests(self) -> bool:
        """Run unit test suite"""
        result = subprocess.run(['python', '-m', 'pytest', 'tests/unit/'],
                              capture_output=True, text=True)
        return result.returncode == 0

    def run_schema_tests(self) -> bool:
        """Run schema validation tests"""
        validator = GraphSchemaValidator(GraphSchema())

        # Test sample data
        test_nodes = self._load_test_node_samples()
        for node_type, nodes in test_nodes.items():
            for node in nodes:
                result = validator.validate_node(node_type, node)
                if result.has_errors():
                    return False

        return True

if __name__ == "__main__":
    pipeline = TestPipeline()
    success = pipeline.run_all_tests()
    sys.exit(0 if success else 1)
```

## Testing Data Requirements
- **Sample SR 101 Files**: Complete Bundesverfassung JSON and HTML
- **Schema Test Cases**: Examples of all 8 node types
- **Edge Cases**: Malformed data, missing fields, invalid relationships
- **Performance Test Dataset**: Large collection of representative files
- **Regression Test Data**: Known-good baseline results

## Integration with CI/CD
```bash
# .github/workflows/test-graph-builder.yml
name: Test Graph Builder

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5.0
        env:
          NEO4J_AUTH: neo4j/testpassword
        ports:
          - 7687:7687

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run test pipeline
        run: python tests/test_pipeline.py
```

## Success Metrics
- [ ] Test coverage > 90% for all new components
- [ ] Schema validation passes for all 8 node types
- [ ] Integration tests validate complete workflows
- [ ] Performance tests confirm sub-5-minute SR 101 builds
- [ ] Data quality validation catches common issues
- [ ] All tests run in under 10 minutes in CI/CD

## Dependencies
- **All previous sub-tasks**: Testing validates their implementations
- **Test data**: Sample JSON/HTML files for comprehensive testing
- **Neo4j test instance**: Isolated database for testing

## Risk Assessment
- **Risk Level**: LOW (testing reduces overall risk)
- **Main Risks**:
  - Test data maintenance: LOW impact, MEDIUM probability
  - Test execution time: MEDIUM impact, LOW probability
- **Mitigation**: Automated test data generation, parallel test execution