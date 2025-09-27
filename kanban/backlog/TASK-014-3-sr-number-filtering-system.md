# TASK-014.3: SR Number Filtering System

**Status**: BACKLOG
**Priority**: MEDIUM
**Type**: feature
**Parent**: TASK-014
**Estimated Effort**: 1 day
**Created**: 2025-09-26
**Assigned**: Unassigned

## Description
Implement a comprehensive SR number filtering system that enables targeted graph building for specific Swiss laws. This dramatically reduces build time from hours to minutes and enables focused development and testing.

## Problem Analysis
Current limitations:
- No SR filtering capability in build script
- Must process all 305,440 JSON files for any build
- Build time is hours even for single law testing
- Development cycle is slow due to full builds
- No validation of SR number formats

## Business Value
- **Development Speed**: Build SR 101 in minutes vs hours
- **Testing Efficiency**: Fast iteration on specific laws
- **Resource Optimization**: Reduced CPU/memory usage
- **Debugging**: Isolated law processing for troubleshooting
- **Demo Capability**: Quick setup of specific law examples

## Acceptance Criteria
- [ ] SR filtering works with command line argument `--sr-filter 101`
- [ ] Supports specific SR numbers (e.g., "101", "220", "311.0")
- [ ] Supports SR ranges (e.g., "100-199", "300.*")
- [ ] Supports multiple SR filters (e.g., "101,220,311.0")
- [ ] Validates SR number format before processing
- [ ] Build time < 5 minutes for SR 101 (vs 2+ hours full build)
- [ ] Maintains all existing functionality when no filter applied
- [ ] Clear feedback on filtered file counts
- [ ] Error handling for invalid SR patterns

## Technical Implementation

### 1. SR Number Pattern Validation
```python
class SRNumberValidator:
    """Validates and normalizes Swiss SR numbers"""

    # Valid SR patterns
    SR_PATTERNS = [
        r'^\d{1,3}$',                    # 101, 22, 7
        r'^\d{1,3}\.\d{1,3}$',          # 101.1, 220.3
        r'^\d{1,3}\.\d{1,3}\.\d{1,3}$', # 311.0.1, 101.1.1
        r'^\d{1,3}\*$',                  # 100*, 200* (wildcard)
        r'^\d{1,3}-\d{1,3}$',           # 100-199 (range)
    ]

    @classmethod
    def validate_sr_number(cls, sr_input: str) -> bool:
        """Validate SR number format"""
        if not sr_input:
            return False

        # Handle multiple SR numbers (comma-separated)
        sr_numbers = [s.strip() for s in sr_input.split(',')]

        for sr in sr_numbers:
            if not any(re.match(pattern, sr) for pattern in cls.SR_PATTERNS):
                return False

        return True

    @classmethod
    def normalize_sr_number(cls, sr_input: str) -> List[str]:
        """Normalize and expand SR patterns"""
        sr_numbers = [s.strip() for s in sr_input.split(',')]
        normalized = []

        for sr in sr_numbers:
            if '*' in sr:
                # Expand wildcard (e.g., "100*" -> ["100", "101", "102", ...])
                base = sr.replace('*', '')
                normalized.extend(cls._expand_wildcard(base))
            elif '-' in sr:
                # Expand range (e.g., "100-199" -> ["100", "101", ...])
                start, end = sr.split('-')
                normalized.extend(cls._expand_range(int(start), int(end)))
            else:
                normalized.append(sr)

        return normalized

    @classmethod
    def _expand_wildcard(cls, base: str) -> List[str]:
        """Expand SR wildcard pattern"""
        # This would need access to actual SR database
        # For now, return the base number
        return [base]

    @classmethod
    def _expand_range(cls, start: int, end: int) -> List[str]:
        """Expand SR range pattern"""
        return [str(i) for i in range(start, end + 1)]
```

### 2. Enhanced SR Extraction
Improve SR number extraction from JSON files:

```python
def extract_sr_number_enhanced(self, data: Dict) -> Optional[str]:
    """Enhanced SR number extraction with multiple fallback methods"""

    # Method 1: From ELI (most reliable)
    eli = data.get('data', {}).get('attributes', {}).get('eli', '')
    if eli:
        # Extract from URLs like: https://fedlex.data.admin.ch/eli/cc/1999/404
        eli_match = re.search(r'/cc/\d{4}/(\d+)', eli)
        if eli_match:
            eli_number = eli_match.group(1)
            sr_mapping = self.get_eli_to_sr_mapping()
            if eli_number in sr_mapping:
                return sr_mapping[eli_number]

    # Method 2: From taxonomic classification
    taxonomy = data.get('data', {}).get('references', {}).get('classifiedByTaxonomyEntry')
    if taxonomy:
        sr_match = re.search(r'SR\s*(\d+(?:\.\d+)*)', taxonomy)
        if sr_match:
            return sr_match.group(1)

    # Method 3: From title parsing
    title_de = data.get('data', {}).get('attributes', {}).get('title_de', '')
    if 'Bundesverfassung' in title_de:
        return '101'

    # Method 4: From URI patterns
    uri = data.get('data', {}).get('uri', '')
    uri_patterns = [
        r'/cc/1999/404',  # SR 101
        r'/cc/(\d{4})/(\d+)',  # General pattern
    ]

    for pattern in uri_patterns:
        match = re.search(pattern, uri)
        if match:
            if '1999/404' in pattern:
                return '101'
            # Add more specific mappings as needed

    return None

def get_eli_to_sr_mapping(self) -> Dict[str, str]:
    """Mapping of ELI numbers to SR numbers"""
    return {
        '404': '101',  # Bundesverfassung
        '220': '220',  # ZGB
        # Add more mappings as discovered
    }
```

### 3. File Filtering Implementation
Add filtering logic to the download_data method:

```python
def download_data(self, sr_filter: str = None) -> List[Path]:
    """Enhanced data download/location with SR filtering"""
    console.print("\n[bold cyan]📥 Locating data files...[/bold cyan]")

    # Validate SR filter
    if sr_filter:
        if not SRNumberValidator.validate_sr_number(sr_filter):
            raise ValueError(f"Invalid SR number format: {sr_filter}")

        sr_numbers = SRNumberValidator.normalize_sr_number(sr_filter)
        console.print(f"  🎯 Filtering for SR numbers: {', '.join(sr_numbers)}")

    # Find all JSON files
    json_files = self._find_all_json_files()
    console.print(f"  Found {len(json_files)} total JSON files")

    # Apply SR filtering
    if sr_filter:
        filtered_files = []
        sr_numbers = set(SRNumberValidator.normalize_sr_number(sr_filter))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:

            task = progress.add_task("Filtering files by SR number...", total=len(json_files))

            for file_path in json_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    sr_num = self.extract_sr_number_enhanced(data)
                    if sr_num and self._matches_sr_filter(sr_num, sr_numbers):
                        filtered_files.append(file_path)

                except Exception as e:
                    logger.warning(f"Could not process {file_path}: {e}")

                progress.advance(task)

        console.print(f"  🎯 Filtered to {len(filtered_files)} files matching SR filter")
        json_files = filtered_files

    return json_files

def _matches_sr_filter(self, sr_number: str, filter_numbers: Set[str]) -> bool:
    """Check if SR number matches any filter patterns"""
    # Exact match
    if sr_number in filter_numbers:
        return True

    # Hierarchical match (e.g., "101.1" matches filter "101")
    for filter_sr in filter_numbers:
        if sr_number.startswith(filter_sr + '.'):
            return True

    return False
```

### 4. Command Line Integration
Enhance argument parsing:

```python
def main():
    parser = argparse.ArgumentParser(
        description="LAWAST Unified Graph Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # ... existing arguments ...

    parser.add_argument(
        "--sr-filter",
        type=str,
        default=None,
        help="Filter to specific SR number(s). Examples: '101', '101,220', '100-199', '100*'"
    )

    parser.add_argument(
        "--validate-sr",
        action="store_true",
        help="Validate SR filter pattern without building"
    )

    args = parser.parse_args()

    # Validate SR filter if provided
    if args.sr_filter:
        if not SRNumberValidator.validate_sr_number(args.sr_filter):
            console.print(f"[red]❌ Invalid SR filter format: {args.sr_filter}[/red]")
            console.print("Valid formats: '101', '101,220', '100-199', '100*'")
            sys.exit(1)

    if args.validate_sr:
        if args.sr_filter:
            console.print(f"[green]✅ SR filter is valid: {args.sr_filter}[/green]")
            normalized = SRNumberValidator.normalize_sr_number(args.sr_filter)
            console.print(f"Expanded to: {', '.join(normalized)}")
        else:
            console.print("[yellow]No SR filter provided to validate[/yellow]")
        sys.exit(0)
```

### 5. Performance Monitoring
Add filtering statistics:

```python
@dataclass
class FilteringStatistics:
    """Statistics for SR filtering"""
    total_files: int = 0
    filtered_files: int = 0
    sr_numbers_found: Set[str] = field(default_factory=set)
    filter_time: float = 0.0

    @property
    def filter_ratio(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.filtered_files / self.total_files

def report_filtering_stats(self, stats: FilteringStatistics):
    """Report filtering performance"""
    console.print("\n[bold cyan]📊 SR Filtering Statistics[/bold cyan]")
    console.print(f"  Total files scanned: {stats.total_files:,}")
    console.print(f"  Files matching filter: {stats.filtered_files:,}")
    console.print(f"  Filtering ratio: {stats.filter_ratio:.1%}")
    console.print(f"  Filtering time: {stats.filter_time:.2f}s")
    console.print(f"  SR numbers found: {len(stats.sr_numbers_found)}")
```

## Usage Examples

```bash
# Build only Swiss Federal Constitution (SR 101)
python scripts/build_lawast_graph.py --sr-filter 101

# Build multiple specific laws
python scripts/build_lawast_graph.py --sr-filter "101,220,311.0"

# Build SR 100 series (if wildcard supported)
python scripts/build_lawast_graph.py --sr-filter "100*"

# Build range of SR numbers
python scripts/build_lawast_graph.py --sr-filter "100-199"

# Validate SR filter without building
python scripts/build_lawast_graph.py --validate-sr --sr-filter "101,invalid"
```

## Testing Requirements
- **Validation Tests**: All SR number formats validate correctly
- **Filtering Tests**: Correct files selected for various patterns
- **Performance Tests**: Build time < 5 minutes for SR 101
- **Error Handling Tests**: Invalid patterns handled gracefully
- **Integration Tests**: Works with existing build pipeline

## Success Metrics
- [ ] Build time for SR 101: < 5 minutes (vs 2+ hours full build)
- [ ] Correctly filters files for all supported SR patterns
- [ ] No false positives/negatives in filtering
- [ ] Clear user feedback on filtering process
- [ ] Backward compatibility: full build works when no filter specified

## Dependencies
- **JSON Parsing**: Existing JSON file processing
- **Progress Reporting**: Rich library for user feedback
- **File System**: Access to fedlex directory structure

## Risk Assessment
- **Risk Level**: LOW
- **Main Risks**:
  - Incorrect SR extraction: MEDIUM impact, LOW probability
  - Performance regression: LOW impact, LOW probability
- **Mitigation**: Comprehensive testing, validation framework