"""
Taxonomy Extraction Module for LAWAST

Extracts hierarchical taxonomy and classification from parsed HTML documents.
This includes legal domains, book/title/chapter structure, SR classifications,
and subject categories. The taxonomy provides navigational structure and
classification for all articles.

Features:
- SR number extraction with validation
- Multi-language title extraction (DE, FR, IT, RM)
- Hierarchical structure building (Book → Title → Chapter → Section → Article)
- Legal domain classification
- Metadata extraction (dates, status)
- Integration with UnifiedHtmlParser for caching
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from bs4 import BeautifulSoup, Tag

from .base_extractor import BaseExtractor, ExtractionResult
from ..parsers.unified_html_parser import UnifiedHtmlParser

logger = logging.getLogger(__name__)


@dataclass
class HierarchyLevel:
    """Represents a level in the legal document hierarchy"""
    type: str  # Book, Title, Chapter, Section
    number: str
    title: Dict[str, str]  # language -> title mapping
    uri: Optional[str] = None
    parent_uri: Optional[str] = None
    children: List['HierarchyLevel'] = field(default_factory=list)


@dataclass
class TaxonomyResult:
    """Result of taxonomy extraction from HTML document"""
    sr_number: Optional[str] = None
    title: Dict[str, str] = field(default_factory=dict)  # lang -> title
    domain: Optional[str] = None
    hierarchy: List[HierarchyLevel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    language: Optional[str] = None
    uri: Optional[str] = None


class TaxonomyExtractor(BaseExtractor):
    """
    Extract hierarchical taxonomy and classification from Fedlex HTML documents.

    Handles extraction of:
    - SR classification numbers
    - Multi-language titles
    - Hierarchical document structure
    - Legal domain classification
    - Temporal metadata
    """

    # CSS selectors for taxonomy elements (validated from html-extraction-analysis.md)
    SELECTORS = {
        'sr_number': 'p.srnummer',
        'title': 'h1.erlasstitel',
        'preface': 'div#preface',
        'preamble': 'div#preamble',
        'maintext': 'main#maintext',
        'articles': 'article',
        'footnotes': 'div.footnotes',
        'heading': 'h6.heading',
        'collapseable': 'div.collapseable'
    }

    # Hierarchy markers for different languages
    HIERARCHY_MARKERS = {
        'de': {
            'book': ['Buch', 'BUCH'],
            'title': ['Titel', 'TITEL'],
            'chapter': ['Kapitel', 'KAPITEL'],
            'section': ['Abschnitt', 'ABSCHNITT']
        },
        'fr': {
            'book': ['Livre', 'LIVRE'],
            'title': ['Titre', 'TITRE'],
            'chapter': ['Chapitre', 'CHAPITRE'],
            'section': ['Section', 'SECTION']
        },
        'it': {
            'book': ['Libro', 'LIBRO'],
            'title': ['Titolo', 'TITOLO'],
            'chapter': ['Capitolo', 'CAPITOLO'],
            'section': ['Sezione', 'SEZIONE']
        },
        'rm': {
            'book': ['Cudesch', 'CUDESCH'],
            'title': ['Titel', 'TITEL'],
            'chapter': ['Chapitel', 'CHAPITEL'],
            'section': ['Secziun', 'SECZIUN']
        }
    }

    # SR number domain mapping
    SR_DOMAIN_MAPPING = {
        '0': 'International Law - Treaties',
        '1': 'State - People - Authorities',
        '2': 'Private Law - Civil Procedure - Enforcement',
        '3': 'Criminal Law - Criminal Procedure - Execution',
        '4': 'Education - Science - Culture',
        '5': 'National Defence',
        '6': 'Finance',
        '7': 'Public Works - Energy - Transport',
        '8': 'Health - Employment - Social Security',
        '9': 'Economy - Technical Cooperation'
    }

    def __init__(self, parser: Optional[UnifiedHtmlParser] = None):
        """
        Initialize the taxonomy extractor.

        Args:
            parser: UnifiedHtmlParser instance for HTML parsing with caching
        """
        super().__init__()
        self.parser = parser or UnifiedHtmlParser(cache_size=1000)

    def extract(self, html_content_or_path: Any, file_path: str = None) -> ExtractionResult:
        """
        Extract taxonomy from HTML content or file path.

        Args:
            html_content_or_path: Either HTML string content or path to HTML file
            file_path: Optional file path for context (used for URI generation)

        Returns:
            ExtractionResult with taxonomy nodes and relationships
        """
        result = ExtractionResult()

        try:
            # Parse HTML
            if isinstance(html_content_or_path, str):
                if html_content_or_path.startswith('<') or html_content_or_path.startswith('<!'):
                    # It's HTML content
                    soup = BeautifulSoup(html_content_or_path, 'lxml')
                else:
                    # It's a file path
                    soup = self.parser.parse(html_content_or_path)
                    file_path = file_path or html_content_or_path
            else:
                # Assume it's already parsed
                soup = html_content_or_path

            if not soup:
                result.add_error(f"Failed to parse HTML: {file_path}")
                return result

            # Extract language from file path if available
            language = self._extract_language_from_path(file_path) if file_path else None

            # Extract SR number
            sr_number = self._extract_sr_number(soup)

            # Extract title
            title = self._extract_title(soup, language)

            # Extract metadata from preface
            metadata = self._extract_metadata(soup)

            # Extract hierarchy
            hierarchy = self._extract_hierarchy(soup, language)

            # Determine legal domain
            domain = self._classify_domain(sr_number) if sr_number else None

            # Build taxonomy result
            taxonomy = TaxonomyResult(
                sr_number=sr_number,
                title=title,
                domain=domain,
                hierarchy=hierarchy,
                metadata=metadata,
                language=language,
                uri=self._generate_uri(file_path) if file_path else None
            )

            # Store the TaxonomyResult in the ExtractionResult for access
            result.data = taxonomy

            # Convert to nodes and relationships
            self._build_graph_entities(taxonomy, result)

            # Update statistics
            result.statistics['documents_processed'] = 1
            result.statistics['sr_numbers_extracted'] = 1 if sr_number else 0
            result.statistics['hierarchies_built'] = len(hierarchy)

        except Exception as e:
            self.logger.error(f"Error extracting taxonomy from {file_path}: {e}")
            result.add_error(str(e))

        return result

    def _extract_sr_number(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract SR classification number from HTML.

        Args:
            soup: Parsed HTML document

        Returns:
            SR number string or None if not found
        """
        try:
            sr_element = soup.select_one(self.SELECTORS['sr_number'])
            if sr_element:
                sr_text = sr_element.get_text(strip=True)
                # Clean and normalize SR number
                sr_text = re.sub(r'\s+', ' ', sr_text)
                # Remove "SR" prefix if present for consistency
                if sr_text.startswith('SR '):
                    sr_text = sr_text[3:]
                return sr_text
        except Exception as e:
            self.logger.debug(f"Error extracting SR number: {e}")
        return None

    def _extract_title(self, soup: BeautifulSoup, language: Optional[str] = None) -> Dict[str, str]:
        """
        Extract law title, potentially in multiple languages.

        Args:
            soup: Parsed HTML document
            language: Document language code

        Returns:
            Dictionary mapping language codes to titles
        """
        titles = {}

        try:
            title_element = soup.select_one(self.SELECTORS['title'])
            if title_element:
                title_text = title_element.get_text(strip=True)
                if title_text:
                    # If we know the language, store with that key
                    if language:
                        titles[language] = title_text
                    else:
                        # Store as unknown language
                        titles['unknown'] = title_text

        except Exception as e:
            self.logger.debug(f"Error extracting title: {e}")

        return titles

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract metadata from document preface.

        Args:
            soup: Parsed HTML document

        Returns:
            Dictionary of metadata fields
        """
        metadata = {}

        try:
            preface = soup.select_one(self.SELECTORS['preface'])
            if preface:
                # Extract all paragraphs in preface
                for p in preface.find_all('p'):
                    text = p.get_text(strip=True)

                    # Try to identify date patterns
                    if 'Abgeschlossen' in text or 'Conclu' in text:
                        metadata['conclusion_date'] = self._extract_date(text)
                    elif 'Kraft' in text or 'vigueur' in text:
                        metadata['entry_force_date'] = self._extract_date(text)
                    elif 'Stand' in text or 'Etat' in text or 'Stato' in text:
                        metadata['status_date'] = self._extract_date(text)

                # Extract any cross-references in preface
                links = preface.find_all('a', href=True)
                if links:
                    metadata['preface_references'] = [
                        {'url': link['href'], 'text': link.get_text(strip=True)}
                        for link in links
                        if 'fedlex.data.admin.ch' in link['href']
                    ]

        except Exception as e:
            self.logger.debug(f"Error extracting metadata: {e}")

        return metadata

    def _extract_hierarchy(self, soup: BeautifulSoup, language: Optional[str] = None) -> List[HierarchyLevel]:
        """
        Extract hierarchical structure from document.

        Args:
            soup: Parsed HTML document
            language: Document language code

        Returns:
            List of HierarchyLevel objects representing document structure
        """
        hierarchy = []

        try:
            # Determine which language markers to use
            if language and language in self.HIERARCHY_MARKERS:
                markers = self.HIERARCHY_MARKERS[language]
            else:
                # Use German as default
                markers = self.HIERARCHY_MARKERS['de']

            # Search for structural elements
            maintext = soup.select_one(self.SELECTORS['maintext'])
            if not maintext:
                maintext = soup.body  # Fallback to body

            if maintext:
                # Look for headings that indicate structure
                for heading in maintext.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    heading_text = heading.get_text(strip=True)

                    # Check if this heading matches any hierarchy markers
                    level_type = self._identify_hierarchy_type(heading_text, markers)
                    if level_type:
                        # Extract number and title - parse before type identification for better results
                        number, title_text = self._parse_hierarchy_heading(heading_text)

                        level = HierarchyLevel(
                            type=level_type,
                            number=number if number else '',
                            title={language: title_text} if language else {'unknown': title_text}
                        )
                        hierarchy.append(level)

        except Exception as e:
            self.logger.debug(f"Error extracting hierarchy: {e}")

        return hierarchy

    def _identify_hierarchy_type(self, text: str, markers: Dict[str, List[str]]) -> Optional[str]:
        """
        Identify the type of hierarchy level from heading text.

        Args:
            text: Heading text
            markers: Language-specific hierarchy markers

        Returns:
            Hierarchy type (book, title, chapter, section) or None
        """
        text_upper = text.upper()

        for level_type, marker_list in markers.items():
            for marker in marker_list:
                if marker.upper() in text_upper:
                    return level_type

        return None

    def _parse_hierarchy_heading(self, text: str) -> Tuple[Optional[str], str]:
        """
        Parse hierarchy heading to extract number and title.

        Args:
            text: Heading text

        Returns:
            Tuple of (number, title)
        """
        # Common patterns:
        # "1. Buch: Allgemeine Bestimmungen"
        # "Titel 2: Die natürlichen Personen"
        # "Kapitel III: ..."

        number = None
        title = text

        # First remove the type marker to find the number after it
        # Pattern: "Titel 1:" or "1. Buch:" or "Chapter III:"

        # Try patterns with type marker first, then number
        type_then_number_pattern = r'^(Buch|Titel|Kapitel|Abschnitt|Livre|Titre|Chapitre|Section|Libro|Titolo|Capitolo|Sezione)\s+([IVX]+|\d+)[:\.\s]'
        match = re.match(type_then_number_pattern, text, flags=re.IGNORECASE)
        if match:
            number = match.group(2)
            title = text[match.end():].strip()
            return number, title

        # Try number first, then type marker
        number_then_type_pattern = r'^([IVX]+|\d+)\.?\s*(Buch|Titel|Kapitel|Abschnitt|Livre|Titre|Chapitre|Section|Libro|Titolo|Capitolo|Sezione)?[:\.\s]'
        match = re.match(number_then_type_pattern, text, flags=re.IGNORECASE)
        if match:
            number = match.group(1)
            title = text[match.end():].strip()
            return number, title

        # Try just Roman or Arabic numerals at start
        simple_number_pattern = r'^([IVX]+|\d+)[:\.\s]+'
        match = re.match(simple_number_pattern, text)
        if match:
            number = match.group(1)
            title = text[match.end():].strip()
            return number, title

        # No number found, clean up title
        title = re.sub(r'^(Buch|Titel|Kapitel|Abschnitt|Livre|Titre|Chapitre|Section|Libro|Titolo|Capitolo|Sezione):?\s*', '', title, flags=re.IGNORECASE)
        title = title.strip()

        return number, title

    def _classify_domain(self, sr_number: str) -> Optional[str]:
        """
        Classify legal domain based on SR number.

        Args:
            sr_number: SR classification number

        Returns:
            Legal domain name or None
        """
        if not sr_number:
            return None

        # Extract first digit of SR number
        match = re.match(r'^(\d)', sr_number)
        if match:
            first_digit = match.group(1)
            return self.SR_DOMAIN_MAPPING.get(first_digit)

        return None

    def _extract_language_from_path(self, file_path: str) -> Optional[str]:
        """
        Extract language code from file path.

        Args:
            file_path: Path to HTML file

        Returns:
            Language code (de, fr, it, rm) or None
        """
        # Pattern: .../eli/cc/XXX/date/{language}/html/...
        path = Path(file_path)
        parts = path.parts

        # Look for language code in path
        for i, part in enumerate(parts):
            if part in ['de', 'fr', 'it', 'rm']:
                return part

        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """
        Extract date from text string.

        Args:
            text: Text containing date

        Returns:
            Date string in ISO format or None
        """
        # Common date patterns in Fedlex
        # "1. Januar 2020", "1er janvier 2020", "1° gennaio 2020"
        date_patterns = [
            r'(\d{1,2})\.\s*(\w+)\s+(\d{4})',  # German format
            r'(\d{1,2})er?\s+(\w+)\s+(\d{4})',  # French format
            r'(\d{1,2})°?\s+(\w+)\s+(\d{4})',  # Italian format
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                # For simplicity, return as found (could be enhanced with proper parsing)
                return match.group(0)

        return None

    def _generate_uri(self, file_path: str) -> str:
        """
        Generate URI from file path.

        Args:
            file_path: Path to HTML file

        Returns:
            Generated URI
        """
        # Convert file path to fedlex URI format
        path = Path(file_path)

        # Extract relevant parts from path
        # Example: fedlex-assets/eli/cc/1999/404/20200101/de/html/file.html
        # -> https://fedlex.data.admin.ch/eli/cc/1999/404

        parts = []
        capture = False
        sr_parts_count = 0

        for part in path.parts:
            if part == 'eli':
                capture = True
                parts.append(part)
            elif capture:
                parts.append(part)
                # For /eli/cc/ paths, we need cc + year + number (3 parts after eli)
                if len(parts) >= 2 and parts[1] == 'cc':
                    if len(parts) == 4:  # eli/cc/year/number
                        break
                # For other paths, stop after finding a date-like part
                elif part.isdigit() and len(part) >= 4:
                    break

        if parts and len(parts) >= 2:
            return f"https://fedlex.data.admin.ch/{'/'.join(parts)}"
        else:
            return f"file://{file_path}"

    def _build_graph_entities(self, taxonomy: TaxonomyResult, result: ExtractionResult):
        """
        Convert taxonomy result to graph nodes and relationships.

        Args:
            taxonomy: Extracted taxonomy data
            result: ExtractionResult to populate
        """
        # Create main document node
        if taxonomy.uri:
            doc_node = {
                'uri': taxonomy.uri,
                'type': 'Document',
                'sr_number': taxonomy.sr_number,
                'domain': taxonomy.domain,
                'language': taxonomy.language,
                'metadata': taxonomy.metadata
            }

            # Add titles
            for lang, title in taxonomy.title.items():
                doc_node[f'title_{lang}'] = title

            result.add_node(doc_node)

            # Create hierarchy nodes and relationships
            parent_uri = taxonomy.uri
            for level in taxonomy.hierarchy:
                # Generate URI for hierarchy level
                level_uri = f"{taxonomy.uri}/hierarchy/{level.type}/{level.number}"

                level_node = {
                    'uri': level_uri,
                    'type': f'Hierarchy_{level.type.capitalize()}',
                    'number': level.number,
                    'level_type': level.type
                }

                # Add titles
                for lang, title in level.title.items():
                    level_node[f'title_{lang}'] = title

                result.add_node(level_node)

                # Create CONTAINS relationship
                result.add_relationship(
                    parent_uri,
                    level_uri,
                    'CONTAINS',
                    {'hierarchy_level': level.type}
                )

                # Update parent for next iteration
                parent_uri = level_uri

    def process_batch(self, file_paths: List[str], progress_callback: Optional[callable] = None) -> List[ExtractionResult]:
        """
        Process multiple HTML files in batch.

        Args:
            file_paths: List of HTML file paths
            progress_callback: Optional callback for progress updates

        Returns:
            List of ExtractionResult objects
        """
        results = []
        total = len(file_paths)

        for i, file_path in enumerate(file_paths):
            result = self.extract(file_path, file_path)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, total)

        return results