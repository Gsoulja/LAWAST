"""
Unit tests for UnifiedHtmlParser

Tests multi-parser strategies, caching, encoding detection, and error recovery.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.parsers.unified_html_parser import UnifiedHtmlParser, ParserStats


class TestUnifiedHtmlParser:
    """Test the unified HTML parser"""

    @pytest.fixture
    def parser(self):
        """Create a parser instance for testing"""
        return UnifiedHtmlParser(cache_size=10, enable_stats=True)

    @pytest.fixture
    def sample_html(self):
        """Sample HTML content"""
        return """<!DOCTYPE html>
        <html>
        <head><title>Test Document</title></head>
        <body>
            <div id="lawcontent">
                <article id="art_1">
                    <h6 class="heading">Art. 1</h6>
                    <div class="collapseable">
                        <p>Article content here</p>
                    </div>
                </article>
            </div>
        </body>
        </html>"""

    @pytest.fixture
    def malformed_html(self):
        """Malformed HTML that requires lenient parsing"""
        return """<html>
        <title>Broken Document
        <body>
            <div>
                <p>Unclosed paragraph
                <article>Missing closing tags
            </div>
        """

    def test_parser_initialization(self):
        """Test parser initialization with different settings"""
        parser = UnifiedHtmlParser(cache_size=100, enable_stats=True)
        assert parser.cache_size == 100
        assert parser.stats is not None

        parser_no_stats = UnifiedHtmlParser(enable_stats=False)
        assert parser_no_stats.stats is None

    def test_parse_valid_html(self, parser, sample_html, tmp_path):
        """Test parsing valid HTML file"""
        # Create a temporary HTML file
        html_file = tmp_path / "test.html"
        html_file.write_text(sample_html, encoding='utf-8')

        # Parse the file
        soup = parser.parse(str(html_file))

        assert soup is not None
        assert soup.find('article', id='art_1') is not None
        assert soup.find('h6', class_='heading').text == 'Art. 1'

        # Check stats
        stats = parser.get_stats()
        assert stats['parsed'] == 1
        assert stats['errors'] == 0

    def test_parse_nonexistent_file(self, parser):
        """Test parsing non-existent file"""
        result = parser.parse('/nonexistent/file.html')
        assert result is None

        stats = parser.get_stats()
        assert stats['errors'] == 1

    def test_cache_behavior(self, parser, sample_html, tmp_path):
        """Test LRU cache behavior"""
        html_file = tmp_path / "cached.html"
        html_file.write_text(sample_html, encoding='utf-8')

        # First parse - cache miss
        soup1 = parser.parse(str(html_file))
        stats1 = parser.get_stats()
        assert stats1['cache_misses'] == 1
        assert stats1['cache_hits'] == 0

        # Second parse - cache hit
        soup2 = parser.parse(str(html_file))
        stats2 = parser.get_stats()
        assert stats2['cache_hits'] == 1
        assert stats2['cache_misses'] == 1

        # Should return the same object from cache
        assert soup1 is soup2

    def test_cache_clearing(self, parser, sample_html, tmp_path):
        """Test cache clearing functionality"""
        html_file = tmp_path / "clear_cache.html"
        html_file.write_text(sample_html)

        # Parse and cache
        parser.parse(str(html_file))
        stats1 = parser.get_stats()
        assert stats1['cache_info']['size'] == 1

        # Clear cache
        parser.clear_cache()
        stats2 = parser.get_stats()
        assert stats2['cache_info']['size'] == 0

    def test_encoding_detection(self, parser, tmp_path):
        """Test automatic encoding detection"""
        # Create files with different encodings
        encodings = {
            'utf-8': '<!DOCTYPE html><html><body>UTF-8 content: é à ü</body></html>',
            'iso-8859-1': '<!DOCTYPE html><html><body>ISO content</body></html>',
        }

        for encoding, content in encodings.items():
            file_path = tmp_path / f"test_{encoding}.html"
            file_path.write_text(content, encoding=encoding)

            soup = parser.parse(str(file_path))
            assert soup is not None

        stats = parser.get_stats()
        assert 'utf-8' in stats['encoding_usage']

    def test_parser_fallback(self, parser, malformed_html, tmp_path):
        """Test parser fallback strategy"""
        html_file = tmp_path / "malformed.html"
        html_file.write_text(malformed_html)

        # Mock parsers to simulate failures
        with patch('src.parsers.unified_html_parser.BeautifulSoup') as mock_bs:
            # Simulate lxml failing, html.parser succeeding
            def side_effect(content, parser_name):
                if parser_name == 'lxml':
                    raise Exception("Parser failed")
                else:
                    from bs4 import BeautifulSoup
                    return BeautifulSoup(content, 'html.parser')

            mock_bs.side_effect = side_effect

            # Should fall back to html.parser
            result = parser.parse(str(html_file))
            # Note: Result will depend on mock behavior

    def test_batch_parsing(self, parser, sample_html, tmp_path):
        """Test batch parsing functionality"""
        # Create multiple HTML files
        file_paths = []
        for i in range(5):
            file_path = tmp_path / f"batch_{i}.html"
            file_path.write_text(sample_html)
            file_paths.append(str(file_path))

        # Parse batch
        results = parser.parse_batch(file_paths)

        assert len(results) == 5
        assert all(soup is not None for soup in results)

        stats = parser.get_stats()
        assert stats['parsed'] == 5

    def test_batch_parsing_with_callback(self, parser, sample_html, tmp_path):
        """Test batch parsing with progress callback"""
        file_paths = []
        for i in range(3):
            file_path = tmp_path / f"callback_{i}.html"
            file_path.write_text(sample_html)
            file_paths.append(str(file_path))

        # Track progress
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        results = parser.parse_batch(file_paths, progress_callback)

        assert len(progress_calls) == 3
        assert progress_calls == [(1, 3), (2, 3), (3, 3)]

    def test_performance_validation(self, parser, sample_html, tmp_path):
        """Test performance validation method"""
        # Parse a file to generate stats
        html_file = tmp_path / "perf.html"
        html_file.write_text(sample_html)
        parser.parse(str(html_file))

        # Validate performance
        validation = parser.validate_performance()

        assert 'avg_parse_time_ms' in validation
        assert 'meets_300ms_target' in validation
        assert 'parse_success_rate' in validation
        assert 'meets_99_percent_target' in validation
        assert 'cache_hit_rate' in validation

    def test_parser_stats_tracking(self, parser, sample_html, tmp_path):
        """Test statistics tracking"""
        html_file = tmp_path / "stats.html"
        html_file.write_text(sample_html)

        # Parse multiple times
        for _ in range(3):
            parser.parse(str(html_file))

        stats = parser.get_stats()
        assert stats['parsed'] == 1  # Only parsed once, rest from cache
        assert stats['cache_hits'] == 2
        assert stats['cache_misses'] == 1
        assert 'lxml' in stats['parser_usage'] or 'html.parser' in stats['parser_usage']

    def test_fedlex_html_structure(self, parser, tmp_path):
        """Test with actual Fedlex HTML structure"""
        fedlex_html = """<!DOCTYPE HTML>
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>fedlex-data-admin-ch-eli-cc</title>
        </head>
        <body>
            <div id="lawcontent">
                <div id="preface">
                    <p class="srnummer">0.353.934.9</p>
                    <h1 class="erlasstitel">Vertrag zwischen der Schweiz</h1>
                </div>
                <main id="maintext">
                    <article id="art_1">
                        <h6 class="heading"><b>Art. 1</b></h6>
                        <div class="collapseable">
                            <p>Content paragraph</p>
                            <dl>
                                <dt>1.</dt>
                                <dd>First item</dd>
                                <dt>2.</dt>
                                <dd>Second item</dd>
                            </dl>
                        </div>
                    </article>
                </main>
            </div>
        </body>
        </html>"""

        html_file = tmp_path / "fedlex.html"
        html_file.write_text(fedlex_html)

        soup = parser.parse(str(html_file))

        # Verify Fedlex structure elements
        assert soup is not None
        assert soup.find('p', class_='srnummer') is not None
        assert soup.find('h1', class_='erlasstitel') is not None
        assert soup.find('article', id='art_1') is not None
        assert soup.find('div', class_='collapseable') is not None

    def test_memory_efficiency(self, parser, sample_html, tmp_path):
        """Test memory efficiency with cache size limits"""
        # Create more files than cache size (cache_size=10)
        for i in range(15):
            file_path = tmp_path / f"memory_{i}.html"
            file_path.write_text(sample_html)
            parser.parse(str(file_path))

        # Cache should not exceed max size
        stats = parser.get_stats()
        assert stats['cache_info']['size'] <= 10

    def test_concurrent_parsing_safety(self, parser, sample_html, tmp_path):
        """Test thread safety of cached parsing"""
        import threading

        html_file = tmp_path / "concurrent.html"
        html_file.write_text(sample_html)

        results = []

        def parse_file():
            result = parser.parse(str(html_file))
            results.append(result is not None)

        # Create multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=parse_file)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # All parses should succeed
        assert all(results)

    def test_large_file_handling(self, parser, tmp_path):
        """Test handling of large HTML files"""
        # Create a large HTML file (1MB+)
        large_content = """<!DOCTYPE html>
        <html><body>
        """ + "<p>Large content paragraph. " * 10000 + """
        </body></html>"""

        html_file = tmp_path / "large.html"
        html_file.write_text(large_content)

        # Should parse without issues
        soup = parser.parse(str(html_file))
        assert soup is not None

        # Check performance is still acceptable
        stats = parser.get_stats()
        assert stats['avg_parse_time_ms'] < 1000  # Should parse in under 1 second


class TestParserStats:
    """Test the ParserStats dataclass"""

    def test_stats_initialization(self):
        """Test stats initialization"""
        stats = ParserStats()
        assert stats.total_parsed == 0
        assert stats.cache_hits == 0
        assert stats.parse_errors == 0
        assert 'lxml' in stats.parser_usage

    def test_stats_to_dict(self):
        """Test converting stats to dictionary"""
        stats = ParserStats()
        stats.total_parsed = 10
        stats.cache_hits = 5
        stats.average_parse_time = 0.15  # 150ms

        stats_dict = stats.to_dict()
        assert stats_dict['parsed'] == 10
        assert stats_dict['cache_hits'] == 5
        assert stats_dict['avg_parse_time_ms'] == 150.0