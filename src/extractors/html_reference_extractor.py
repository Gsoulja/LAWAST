"""
HTML Cross-Reference Extractor for LAWAST

Extracts legal cross-references from HTML documents in fedlex-assets/
Handles multilingual patterns across German, French, Italian, and Romansh texts.
"""
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

from bs4 import BeautifulSoup, NavigableString
import regex

from .base_extractor import BaseExtractor, ExtractionResult
from .reference_patterns import ReferencePatternDetector
from .reference_cache import ReferenceCache
from .uri_resolver import URIResolver

logger = logging.getLogger(__name__)


@dataclass
class HTMLReference:
    """
    Represents a cross-reference found in HTML content
    """
    source_file: str
    source_uri: str
    target_law: str
    target_article: Optional[str]
    raw_text: str
    normalized_reference: str
    language: str
    confidence: float
    context: str


class HTMLPaginationHandler:
    """
    Handles multi-part HTML documents (pagination)
    Groups related files like: file.html, file-1.html, file-2.html, etc.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def group_paginated_files(self, html_files: List[Path]) -> Dict[str, List[Path]]:
        """
        Group paginated HTML files by base document
        
        Args:
            html_files: List of HTML file paths
            
        Returns:
            Dict mapping base document to list of file parts
        """
        groups = defaultdict(list)
        
        for file_path in html_files:
            base_name = self._get_base_name(file_path)
            groups[base_name].append(file_path)
        
        # Sort each group by page number
        for base_name in groups:
            groups[base_name] = sorted(
                groups[base_name], 
                key=self._extract_page_number
            )
        
        self.logger.info(f"Grouped {len(html_files)} files into {len(groups)} document sets")
        return dict(groups)
    
    def _get_base_name(self, file_path: Path) -> str:
        """
        Extract base document name from file path
        
        Examples:
        - file.html -> file.html
        - file-1.html -> file.html
        - file-2.html -> file.html
        """
        name = file_path.name
        # Remove page suffix pattern: -N.html
        base_pattern = r'^(.+?)-\d+\.html$'
        match = re.match(base_pattern, name)
        if match:
            base_name = f"{match.group(1)}.html"
        else:
            base_name = name
        
        # Include parent directory for uniqueness
        return f"{file_path.parent}/{base_name}"
    
    def _extract_page_number(self, file_path: Path) -> int:
        """Extract page number from filename, return 0 for base file"""
        name = file_path.name
        page_pattern = r'-(\d+)\.html$'
        match = re.search(page_pattern, name)
        return int(match.group(1)) if match else 0


class HTMLReferenceExtractor(BaseExtractor):
    """
    Main HTML cross-reference extractor
    
    Processes HTML files from fedlex-assets/ to extract legal cross-references
    and create REFERENCES relationships in the graph database.
    """
    
    def __init__(
        self,
        uri_resolver: Optional[URIResolver] = None,
        use_cache: bool = True,
        memory_limit_mb: int = 1024
    ):
        """
        Initialize HTML reference extractor
        
        Args:
            uri_resolver: URI resolver for normalization
            use_cache: Whether to use reference caching
            memory_limit_mb: Memory limit per processing worker
        """
        super().__init__()
        self.uri_resolver = uri_resolver or URIResolver()
        self.pattern_detector = ReferencePatternDetector()
        self.pagination_handler = HTMLPaginationHandler()
        self.cache = ReferenceCache() if use_cache else None
        self.memory_limit_mb = memory_limit_mb
        
        # Statistics tracking
        self.stats = defaultdict(int)
        
    def extract(self, json_data: Dict[str, Any], file_path: str) -> ExtractionResult:
        """
        Extract references from HTML files (not JSON)
        This method processes HTML files directly
        """
        if file_path.endswith('.html'):
            return self.extract_from_html_file(file_path)
        else:
            self.logger.warning(f"HTMLReferenceExtractor called with non-HTML file: {file_path}")
            return ExtractionResult()
    
    def extract_from_html_file(self, file_path: str) -> ExtractionResult:
        """
        Extract cross-references from a single HTML file
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            ExtractionResult with references as relationships
        """
        result = ExtractionResult()
        
        try:
            # Check cache first
            if self.cache:
                cached_result = self.cache.get_cached(file_path)
                if cached_result:
                    self.stats['cache_hits'] += 1
                    return cached_result
            
            # Read and parse HTML
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Check memory usage
            if len(html_content) > self.memory_limit_mb * 1024 * 1024:
                self.logger.warning(f"File {file_path} exceeds memory limit, processing in chunks")
                return self._process_large_file(file_path, html_content)
            
            # Extract references
            references = self._extract_references_from_content(html_content, file_path)
            
            # Convert to relationships
            for ref in references:
                result.add_relationship(
                    ref.source_uri,
                    ref.normalized_reference,
                    "REFERENCES",
                    {
                        "raw_text": ref.raw_text,
                        "language": ref.language,
                        "confidence": ref.confidence,
                        "context": ref.context[:200]  # Limit context size
                    }
                )
            
            self.stats['files_processed'] += 1
            self.stats['references_found'] += len(references)
            
            # Cache result
            if self.cache:
                self.cache.store(file_path, result)
            
        except Exception as e:
            error_msg = f"Failed to process HTML file {file_path}: {e}"
            result.add_error(error_msg)
            self.stats['processing_errors'] += 1
        
        return result
    
    def process_paginated_document(self, file_group: List[Path]) -> ExtractionResult:
        """
        Process a group of paginated HTML files as a single document
        
        Args:
            file_group: List of file paths in page order
            
        Returns:
            Combined extraction result
        """
        combined_result = ExtractionResult()
        combined_content = ""
        source_uri = None
        
        try:
            # Combine content from all pages
            for file_path in file_group:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    combined_content += content + "\n<!-- PAGE_BREAK -->\n"
                
                # Use first file's URI as source
                if source_uri is None:
                    source_uri = self._extract_source_uri(file_path)
            
            # Extract references from combined content
            references = self._extract_references_from_content(
                combined_content, 
                str(file_group[0])  # Use first file as representative
            )
            
            # Convert to relationships
            for ref in references:
                combined_result.add_relationship(
                    ref.source_uri,
                    ref.normalized_reference,
                    "REFERENCES",
                    {
                        "raw_text": ref.raw_text,
                        "language": ref.language,
                        "confidence": ref.confidence,
                        "context": ref.context[:200],
                        "pages": len(file_group)
                    }
                )
            
            self.stats['paginated_docs_processed'] += 1
            self.stats['total_pages_processed'] += len(file_group)
            
        except Exception as e:
            error_msg = f"Failed to process paginated document {file_group[0]}: {e}"
            combined_result.add_error(error_msg)
            self.stats['processing_errors'] += 1
        
        return combined_result
    
    def _extract_references_from_content(
        self, 
        html_content: str, 
        file_path: str
    ) -> List[HTMLReference]:
        """
        Extract cross-references from HTML content
        
        Args:
            html_content: Raw HTML content
            file_path: Source file path for context
            
        Returns:
            List of found references
        """
        references = []
        
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Detect language from file path
            language = self._detect_language(file_path)
            
            # Extract source URI
            source_uri = self._extract_source_uri(file_path)
            
            # Find all text content
            text_content = soup.get_text(separator=' ', strip=True)
            
            # Apply pattern detection
            found_patterns = self.pattern_detector.find_references(text_content, language)
            
            # Process each found pattern
            for pattern_match in found_patterns:
                try:
                    reference = HTMLReference(
                        source_file=file_path,
                        source_uri=source_uri,
                        target_law=pattern_match['law'],
                        target_article=pattern_match.get('article'),
                        raw_text=pattern_match['raw_text'],
                        normalized_reference=pattern_match['normalized'],
                        language=language,
                        confidence=pattern_match['confidence'],
                        context=self._extract_context(soup, pattern_match['raw_text'])
                    )
                    references.append(reference)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to process pattern match: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Failed to parse HTML content from {file_path}: {e}")
        
        return references
    
    def _detect_language(self, file_path: str) -> str:
        """
        Detect language from file path
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            Language code (de, fr, it, rm, en)
        """
        # Extract language from path: .../de/html/, .../fr/html/, etc.
        path_parts = Path(file_path).parts
        for part in path_parts:
            if part in ['de', 'fr', 'it', 'rm', 'en']:
                return part
        
        # Default to German if not detected
        self.logger.warning(f"Could not detect language from path {file_path}, defaulting to 'de'")
        return 'de'
    
    def _extract_source_uri(self, file_path: str) -> str:
        """
        Extract source document URI from file path
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            Normalized document URI
        """
        # Convert file path to fedlex URI
        # Example: fedlex-assets/eli/cc/1999/404/20240101/de/html/file.html
        # Should become: https://fedlex.data.admin.ch/eli/cc/1999/404/20240101
        
        path = Path(file_path)
        path_parts = list(path.parts)
        
        try:
            # Find eli index
            eli_idx = path_parts.index('eli')
            
            # Extract URI parts: eli/cc/1999/404/20240101
            uri_parts = path_parts[eli_idx:eli_idx + 5]  # eli, cc, year, number, date
            
            # Construct URI
            uri_path = '/'.join(uri_parts)
            full_uri = f"https://fedlex.data.admin.ch/{uri_path}"
            
            return self.uri_resolver.normalize_uri(full_uri)
            
        except (ValueError, IndexError) as e:
            self.logger.warning(f"Could not extract URI from path {file_path}: {e}")
            return f"file://{file_path}"
    
    def _extract_context(self, soup: BeautifulSoup, reference_text: str, context_length: int = 200) -> str:
        """
        Extract surrounding context for a reference
        
        Args:
            soup: Parsed HTML
            reference_text: The reference text to find context for
            context_length: Maximum context length
            
        Returns:
            Context string
        """
        try:
            # Find the element containing the reference
            for element in soup.find_all(string=regex.compile(regex.escape(reference_text))):
                if isinstance(element, NavigableString):
                    parent = element.parent
                    if parent:
                        context = parent.get_text(strip=True)
                        if len(context) > context_length:
                            # Truncate but try to keep reference in center
                            ref_pos = context.find(reference_text)
                            start = max(0, ref_pos - context_length // 2)
                            end = min(len(context), start + context_length)
                            context = context[start:end]
                            if start > 0:
                                context = "..." + context
                            if end < len(context):
                                context = context + "..."
                        return context
        except Exception as e:
            self.logger.debug(f"Could not extract context for '{reference_text}': {e}")
        
        return ""
    
    def _process_large_file(self, file_path: str, html_content: str) -> ExtractionResult:
        """
        Process large HTML files in chunks to manage memory
        
        Args:
            file_path: Path to file
            html_content: HTML content
            
        Returns:
            Extraction result
        """
        # For now, skip very large files
        # TODO: Implement chunked processing if needed
        result = ExtractionResult()
        result.add_error(f"File {file_path} too large for processing")
        self.stats['skipped_large_files'] += 1
        return result
    
    def get_statistics(self) -> Dict[str, int]:
        """Get processing statistics"""
        return dict(self.stats)
