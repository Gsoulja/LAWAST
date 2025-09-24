"""
Unified HTML Parser for LAWAST

A robust, multi-strategy HTML parser that handles all Fedlex HTML formats with
efficient caching, encoding detection, and graceful error recovery.

Features:
- Multi-parser fallback strategy (lxml → html.parser → html5lib)
- LRU cache for parsed DOMs to avoid re-parsing
- Automatic encoding detection
- Performance monitoring and statistics
- Graceful error recovery without pipeline interruption

Usage:
    parser = UnifiedHtmlParser(cache_size=1000)
    soup = parser.parse('/path/to/file.html')
    if soup:
        # Process the parsed document
        articles = soup.find_all('article')

    # Get parsing statistics
    stats = parser.get_stats()
    print(f"Parsed: {stats['parsed']}, Cache hits: {stats['cache_hits']}")
"""

import logging
import time
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
import chardet

logger = logging.getLogger(__name__)


@dataclass
class ParserStats:
    """Statistics tracking for the parser"""
    total_parsed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    parse_errors: int = 0
    parser_usage: Dict[str, int] = field(default_factory=lambda: {
        'lxml': 0,
        'html.parser': 0,
        'html5lib': 0
    })
    encoding_usage: Dict[str, int] = field(default_factory=dict)
    total_parse_time: float = 0.0
    average_parse_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary"""
        return {
            'parsed': self.total_parsed,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'errors': self.parse_errors,
            'parser_usage': self.parser_usage.copy(),
            'encoding_usage': self.encoding_usage.copy(),
            'avg_parse_time_ms': round(self.average_parse_time * 1000, 2)
        }


class UnifiedHtmlParser:
    """
    Unified HTML parser with multi-parser fallback and caching.

    This parser provides robust HTML parsing for all Fedlex documents,
    handling various formats, encodings, and malformed HTML gracefully.
    """

    # Supported encodings in order of preference
    ENCODINGS = ['utf-8', 'iso-8859-1', 'windows-1252', 'latin-1']

    # Parser strategies in order of preference
    PARSERS = ['lxml', 'html.parser', 'html5lib']

    def __init__(self, cache_size: int = 1000, enable_stats: bool = True):
        """
        Initialize the unified HTML parser.

        Args:
            cache_size: Maximum number of parsed documents to cache (default: 1000)
            enable_stats: Whether to track parsing statistics (default: True)
        """
        self.cache_size = cache_size
        self.enable_stats = enable_stats
        self.stats = ParserStats() if enable_stats else None

        # Set up the cached parse method
        self._cached_parse = lru_cache(maxsize=cache_size)(self._parse_internal)

        logger.info(f"UnifiedHtmlParser initialized with cache_size={cache_size}")

    def parse(self, html_path: str) -> Optional[BeautifulSoup]:
        """
        Parse an HTML file with caching and fallback strategies.

        Args:
            html_path: Path to the HTML file to parse

        Returns:
            Parsed BeautifulSoup object or None if parsing fails
        """
        # Convert to absolute path for consistent caching
        html_path = str(Path(html_path).absolute())

        # Check if file exists
        if not Path(html_path).exists():
            logger.error(f"File not found: {html_path}")
            if self.stats:
                self.stats.parse_errors += 1
            return None

        # Track cache hit/miss
        cache_info = self._cached_parse.cache_info()
        hits_before = cache_info.hits

        # Parse with caching
        result = self._cached_parse(html_path)

        # Update cache statistics
        if self.stats:
            cache_info_after = self._cached_parse.cache_info()
            if cache_info_after.hits > hits_before:
                self.stats.cache_hits += 1
            else:
                self.stats.cache_misses += 1

        return result

    def _parse_internal(self, html_path: str) -> Optional[BeautifulSoup]:
        """
        Internal parsing method (cached by lru_cache).

        Args:
            html_path: Absolute path to the HTML file

        Returns:
            Parsed BeautifulSoup object or None if parsing fails
        """
        start_time = time.time()

        try:
            # Read file content with encoding detection
            content, encoding = self._read_with_encoding(html_path)
            if not content:
                return None

            # Track encoding usage
            if self.stats:
                self.stats.encoding_usage[encoding] = self.stats.encoding_usage.get(encoding, 0) + 1

            # Try each parser in order
            for parser_name in self.PARSERS:
                soup = self._try_parser(content, parser_name)
                if soup:
                    # Successful parse
                    if self.stats:
                        self.stats.total_parsed += 1
                        self.stats.parser_usage[parser_name] += 1

                        # Update timing statistics
                        parse_time = time.time() - start_time
                        self.stats.total_parse_time += parse_time
                        self.stats.average_parse_time = (
                            self.stats.total_parse_time / self.stats.total_parsed
                        )

                    logger.debug(f"Successfully parsed {Path(html_path).name} with {parser_name}")
                    return soup

            # All parsers failed
            logger.error(f"All parsers failed for {html_path}")
            if self.stats:
                self.stats.parse_errors += 1
            return None

        except Exception as e:
            logger.error(f"Unexpected error parsing {html_path}: {e}")
            if self.stats:
                self.stats.parse_errors += 1
            return None

    def _read_with_encoding(self, file_path: str) -> Tuple[Optional[str], str]:
        """
        Read file content with automatic encoding detection.

        Args:
            file_path: Path to the file to read

        Returns:
            Tuple of (content, encoding) or (None, '') on failure
        """
        # Try each encoding in order
        for encoding in self.ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    return content, encoding
            except UnicodeDecodeError:
                continue

        # Fall back to chardet detection
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected.get('encoding', 'utf-8')

                content = raw_data.decode(encoding, errors='ignore')
                logger.info(f"Used chardet to detect encoding: {encoding}")
                return content, encoding

        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None, ''

    def _try_parser(self, content: str, parser_name: str) -> Optional[BeautifulSoup]:
        """
        Try to parse HTML content with a specific parser.

        Args:
            content: HTML content as string
            parser_name: Name of the parser to use

        Returns:
            BeautifulSoup object or None if parsing fails
        """
        try:
            # Special handling for html5lib - not installed by default
            if parser_name == 'html5lib':
                try:
                    import html5lib
                except ImportError:
                    logger.debug("html5lib not available, skipping")
                    return None

            soup = BeautifulSoup(content, parser_name)

            # Validate that we got a valid parse
            # Check if we have at least the basic structure
            if soup.find('body') or soup.find('div'):
                return soup
            else:
                logger.debug(f"Parser {parser_name} produced invalid structure")
                return None

        except Exception as e:
            logger.debug(f"Parser {parser_name} failed: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get parsing statistics.

        Returns:
            Dictionary containing parsing statistics
        """
        if not self.stats:
            return {}

        stats = self.stats.to_dict()

        # Add cache info
        cache_info = self._cached_parse.cache_info()
        stats['cache_info'] = {
            'size': cache_info.currsize,
            'maxsize': cache_info.maxsize,
            'hits': cache_info.hits,
            'misses': cache_info.misses,
            'hit_rate': round(cache_info.hits / max(1, cache_info.hits + cache_info.misses), 3)
        }

        return stats

    def clear_cache(self):
        """Clear the parser cache."""
        self._cached_parse.cache_clear()
        logger.info("Parser cache cleared")

    def parse_batch(self, file_paths: List[str],
                   progress_callback: Optional[callable] = None) -> List[Optional[BeautifulSoup]]:
        """
        Parse multiple HTML files in batch.

        Args:
            file_paths: List of file paths to parse
            progress_callback: Optional callback for progress updates

        Returns:
            List of parsed BeautifulSoup objects (None for failed parses)
        """
        results = []
        total = len(file_paths)

        for i, path in enumerate(file_paths):
            result = self.parse(path)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def validate_performance(self) -> Dict[str, bool]:
        """
        Validate parser performance against requirements.

        Returns:
            Dictionary of performance metrics and pass/fail status
        """
        if not self.stats:
            return {'stats_enabled': False}

        avg_time_ms = self.stats.average_parse_time * 1000
        parse_success_rate = (
            self.stats.total_parsed / max(1, self.stats.total_parsed + self.stats.parse_errors)
        )

        return {
            'avg_parse_time_ms': avg_time_ms,
            'meets_300ms_target': avg_time_ms < 300,
            'parse_success_rate': round(parse_success_rate, 3),
            'meets_99_percent_target': parse_success_rate >= 0.99,
            'cache_hit_rate': round(
                self.stats.cache_hits / max(1, self.stats.cache_hits + self.stats.cache_misses), 3
            )
        }