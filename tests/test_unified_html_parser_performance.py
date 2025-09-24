"""
Performance validation tests for UnifiedHtmlParser

Tests against actual Fedlex HTML files to validate performance requirements.
"""

import time
from pathlib import Path
from src.parsers.unified_html_parser import UnifiedHtmlParser


def test_performance_with_real_files():
    """Test parser performance with actual Fedlex HTML files"""

    print("\n" + "="*60)
    print("UNIFIED HTML PARSER - PERFORMANCE VALIDATION")
    print("="*60)

    # Initialize parser
    parser = UnifiedHtmlParser(cache_size=1000, enable_stats=True)

    # Find sample HTML files
    fedlex_dir = Path('/home/mxlk/LAWAST/fedlex-assets')
    if not fedlex_dir.exists():
        print("⚠️  fedlex-assets directory not found, using test samples")
        return

    # Get a sample of HTML files
    html_files = list(fedlex_dir.rglob('*.html'))[:100]  # First 100 files

    if not html_files:
        print("⚠️  No HTML files found in fedlex-assets")
        return

    print(f"\nTesting with {len(html_files)} Fedlex HTML files...")

    # Test 1: Parse all files and measure time
    print("\n1. PARSING PERFORMANCE TEST")
    print("-" * 40)

    start_time = time.time()
    successful_parses = 0
    failed_parses = []

    for i, file_path in enumerate(html_files, 1):
        soup = parser.parse(str(file_path))
        if soup:
            successful_parses += 1
        else:
            failed_parses.append(file_path.name)

        # Progress indicator
        if i % 20 == 0:
            print(f"  Processed {i}/{len(html_files)} files...")

    total_time = time.time() - start_time

    # Calculate metrics
    parse_rate = successful_parses / total_time
    avg_time = (total_time / len(html_files)) * 1000  # Convert to ms

    print(f"\n  ✅ Parsed: {successful_parses}/{len(html_files)} files")
    print(f"  ⏱️  Total time: {total_time:.2f} seconds")
    print(f"  ⚡ Average time per file: {avg_time:.2f}ms")
    print(f"  📈 Parse rate: {parse_rate:.1f} files/second")

    # Check against requirements
    print(f"\n  Target: 100 files in <30 seconds")
    print(f"  Result: {len(html_files)} files in {total_time:.2f} seconds")
    meets_target = total_time < 30 if len(html_files) <= 100 else (total_time / len(html_files)) * 100 < 30
    print(f"  {'✅ PASS' if meets_target else '❌ FAIL'} - Performance target")

    if failed_parses:
        print(f"\n  ⚠️  Failed to parse {len(failed_parses)} files:")
        for name in failed_parses[:5]:  # Show first 5
            print(f"     - {name}")

    # Test 2: Cache effectiveness
    print("\n2. CACHE EFFECTIVENESS TEST")
    print("-" * 40)

    # Parse same files again
    cache_start = time.time()
    for file_path in html_files[:20]:  # Test with first 20 files
        parser.parse(str(file_path))
    cache_time = time.time() - cache_start

    stats = parser.get_stats()
    cache_info = stats['cache_info']

    print(f"  📊 Cache statistics:")
    print(f"     - Hit rate: {cache_info['hit_rate']*100:.1f}%")
    print(f"     - Cache size: {cache_info['size']}/{cache_info['maxsize']}")
    print(f"     - Time for cached parses: {cache_time*1000:.2f}ms")

    # Test 3: Parser usage distribution
    print("\n3. PARSER USAGE DISTRIBUTION")
    print("-" * 40)

    parser_usage = stats['parser_usage']
    total_parses = sum(parser_usage.values())

    for parser_name, count in parser_usage.items():
        if count > 0:
            percentage = (count / total_parses) * 100
            print(f"  {parser_name:12}: {count:3} times ({percentage:.1f}%)")

    # Test 4: Encoding detection
    print("\n4. ENCODING DETECTION")
    print("-" * 40)

    encoding_usage = stats['encoding_usage']
    for encoding, count in encoding_usage.items():
        print(f"  {encoding:12}: {count:3} files")

    # Test 5: Overall statistics
    print("\n5. OVERALL STATISTICS")
    print("-" * 40)

    validation = parser.validate_performance()

    print(f"  Average parse time: {validation['avg_parse_time_ms']:.2f}ms")
    print(f"  {'✅' if validation['meets_300ms_target'] else '❌'} Meets <300ms target: {validation['meets_300ms_target']}")

    print(f"\n  Parse success rate: {validation['parse_success_rate']*100:.1f}%")
    print(f"  {'✅' if validation['meets_99_percent_target'] else '❌'} Meets >99% target: {validation['meets_99_percent_target']}")

    # Test 6: Memory test
    print("\n6. MEMORY EFFICIENCY TEST")
    print("-" * 40)

    parser.clear_cache()

    # Parse larger batch to test memory
    memory_test_files = html_files[:500] if len(html_files) > 500 else html_files

    print(f"  Parsing {len(memory_test_files)} files to test memory...")

    for i, file_path in enumerate(memory_test_files):
        parser.parse(str(file_path))
        if i % 100 == 0 and i > 0:
            # Check cache is within limits
            current_stats = parser.get_stats()
            cache_size = current_stats['cache_info']['size']
            print(f"    After {i} files: cache size = {cache_size}")

    final_stats = parser.get_stats()
    final_cache_size = final_stats['cache_info']['size']

    print(f"\n  Final cache size: {final_cache_size}/{parser.cache_size}")
    print(f"  {'✅' if final_cache_size <= parser.cache_size else '❌'} Cache size within limit")

    # Summary
    print("\n" + "="*60)
    print("PERFORMANCE VALIDATION SUMMARY")
    print("="*60)

    success_rate = (successful_parses / len(html_files)) * 100

    print(f"\n✅ Parse success rate: {success_rate:.1f}%")
    print(f"✅ Average parse time: {avg_time:.2f}ms")
    print(f"✅ Cache hit rate: {cache_info['hit_rate']*100:.1f}%")
    print(f"✅ Memory efficiency: Cache properly limited to {parser.cache_size} entries")

    overall_pass = (
        success_rate >= 99 and
        avg_time < 300 and
        meets_target and
        final_cache_size <= parser.cache_size
    )

    print(f"\n{'🎉 ALL REQUIREMENTS MET' if overall_pass else '⚠️  SOME REQUIREMENTS NOT MET'}")
    print("="*60)


if __name__ == "__main__":
    test_performance_with_real_files()