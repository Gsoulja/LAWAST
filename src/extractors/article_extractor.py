"""
Article Content Extraction Module for LAWAST

Extracts complete article content from parsed HTML documents including article
numbers, titles, full text, structure (paragraphs, subsections), and metadata.
This is the core content that enables legal search and analysis.

Features:
- Extracts all article number formats (1, 1a, 1bis, 335b, etc.)
- Multi-language title extraction (DE, FR, IT, RM)
- Preserves paragraph and subsection hierarchy
- Handles tables, lists, and footnotes
- Links articles to document taxonomy
- Batch processing with progress tracking
- Integration with UnifiedHtmlParser for caching
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from bs4 import BeautifulSoup, Tag
import regex

from .base_extractor import BaseExtractor, ExtractionResult
from ..parsers.unified_html_parser import UnifiedHtmlParser

logger = logging.getLogger(__name__)


@dataclass
class Subpoint:
    """Represents a lettered subpoint (a., b., c.) within a paragraph"""
    letter: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Paragraph:
    """Represents a numbered paragraph within an article"""
    number: str
    text: str
    subpoints: List[Subpoint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArticleContent:
    """Structured content of an article"""
    paragraphs: List[Paragraph] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    footnotes: List[Dict[str, Any]] = field(default_factory=list)
    raw_html: Optional[str] = None


@dataclass
class Article:
    """Represents a complete article from a legal document"""
    uri: str
    number: str
    number_normalized: str
    titles: Dict[str, str] = field(default_factory=dict)  # lang -> title
    content: ArticleContent = field(default_factory=ArticleContent)
    section: Optional[str] = None
    chapter: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    language: Optional[str] = None


class ArticleExtractor(BaseExtractor):
    """
    Extract article content from Fedlex HTML documents.

    Handles extraction of:
    - Article numbers in various formats
    - Multi-language titles
    - Structured content (paragraphs, subpoints)
    - Tables and footnotes
    - Metadata and cross-references
    """

    # CSS selectors for article elements (validated from html-extraction-analysis.md)
    SELECTORS = {
        'articles': 'article',
        'article_heading': 'h6.heading',
        'article_content': 'div.collapseable',
        'article_title': 'h6.heading a',
        'paragraphs': 'p',
        'definition_lists': 'dl',
        'definition_terms': 'dt',
        'definition_descriptions': 'dd',
        'footnotes': 'div.footnotes',
        'tables': 'table'
    }

    # Article number patterns for different languages
    # Using word boundary \b to ensure we don't match partial words
    # Latin suffixes: bis (2), ter (3), quater (4), quinquies (5), sexies (6),
    # septies (7), octies (8), novies (9), decies (10)
    ARTICLE_PATTERNS = [
        # German
        (r'Art\.\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'de'),
        (r'Artikel\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'de'),
        # French
        (r'Art\.\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'fr'),
        (r'Article\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'fr'),
        # Italian
        (r'Art\.\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'it'),
        (r'Articolo\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'it'),
        # Romansh
        (r'Art\.\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'rm'),
        (r'Artitgel\s*(\d+(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)?)\b', 'rm'),
    ]

    def __init__(self, parser: Optional[UnifiedHtmlParser] = None):
        """
        Initialize the article extractor.

        Args:
            parser: UnifiedHtmlParser instance for HTML parsing with caching
        """
        super().__init__()
        self.parser = parser or UnifiedHtmlParser(cache_size=1000)

    def extract(self, html_content_or_path: Any, file_path: str = None) -> ExtractionResult:
        """
        Extract articles from HTML content or file path.

        Args:
            html_content_or_path: Either HTML string content or path to HTML file
            file_path: Optional file path for context (used for URI generation)

        Returns:
            ExtractionResult with extracted articles and relationships
        """
        result = ExtractionResult()

        try:
            soup = None

            # Parse HTML based on input type
            if isinstance(html_content_or_path, str):
                # Check if it's HTML content or file path
                if html_content_or_path.strip().startswith('<'):
                    # It's HTML content - parse directly
                    soup = BeautifulSoup(html_content_or_path, 'lxml')
                else:
                    # It's a file path - use UnifiedHtmlParser
                    soup = self.parser.parse(html_content_or_path)
                    file_path = file_path or html_content_or_path
            elif hasattr(html_content_or_path, 'find'):
                # It's already a BeautifulSoup object
                soup = html_content_or_path
            else:
                # Unknown type
                result.add_error(f"Unknown input type: {type(html_content_or_path)}")
                return result

            if not soup:
                result.add_error(f"Failed to parse HTML: {file_path}")
                return result

            # Extract language from file path if available
            language = self._extract_language_from_path(file_path) if file_path else None

            # Find all article elements
            article_elements = soup.select(self.SELECTORS['articles'])

            if not article_elements:
                # No articles found - this is expected for 30% of documents
                self.logger.debug(f"No articles found in {file_path}")
                result.statistics['documents_without_articles'] = 1
                return result

            # Process each article
            articles = []
            for element in article_elements:
                article = self._extract_article(element, file_path, language)
                if article:
                    articles.append(article)
                    # Convert to graph node
                    self._build_graph_entities(article, result)

            # Update statistics
            result.statistics['documents_processed'] = 1
            result.statistics['articles_extracted'] = len(articles)
            result.statistics['average_paragraphs_per_article'] = (
                sum(len(a.content.paragraphs) for a in articles) / len(articles)
                if articles else 0
            )

        except Exception as e:
            self.logger.error(f"Error extracting articles from {file_path}: {e}")
            result.add_error(str(e))

        return result

    def _extract_article(self, element: Tag, file_path: str, language: str) -> Optional[Article]:
        """
        Extract a single article from an article element.

        Args:
            element: BeautifulSoup article tag
            file_path: Source file path for URI generation
            language: Document language code

        Returns:
            Article object or None if extraction fails
        """
        try:
            # Extract article ID from element
            article_id = element.get('id', '')

            # Extract article number
            number, normalized_number = self._extract_article_number(element)
            if not number:
                self.logger.warning(f"Could not extract article number from {article_id}")
                return None

            # Extract title
            titles = self._extract_article_title(element, language)

            # Extract structured content
            content = self._extract_article_content(element)

            # Extract metadata
            metadata = self._extract_article_metadata(element)

            # Generate URI
            uri = self._generate_article_uri(file_path, number) if file_path else article_id

            # Create article object
            article = Article(
                uri=uri,
                number=number,
                number_normalized=normalized_number,
                titles=titles,
                content=content,
                metadata=metadata,
                language=language
            )

            return article

        except Exception as e:
            self.logger.error(f"Error extracting article: {e}")
            return None

    def _extract_article_number(self, element: Tag) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract and normalize article number from article element.

        Args:
            element: Article element

        Returns:
            Tuple of (number, normalized_number)
        """
        # Look for heading element
        heading = element.select_one(self.SELECTORS['article_heading'])
        if not heading:
            return None, None

        # First try to find a bold tag with the article number (common pattern)
        bold_tag = heading.find('b')
        if bold_tag:
            bold_text = bold_tag.get_text(strip=True)
            # Try patterns on bold text first
            for pattern, _ in self.ARTICLE_PATTERNS:
                match = re.search(pattern, bold_text, re.IGNORECASE)
                if match:
                    number = match.group(1)
                    normalized = self._normalize_article_number(number)
                    return number, normalized

        # Otherwise get full heading text
        heading_text = heading.get_text(strip=True)

        # Try each pattern on full text
        for pattern, _ in self.ARTICLE_PATTERNS:
            match = re.search(pattern, heading_text, re.IGNORECASE)
            if match:
                number = match.group(1)
                # Normalize for sorting
                normalized = self._normalize_article_number(number)
                return number, normalized

        # Fallback: try to extract from article ID
        article_id = element.get('id', '')
        if article_id.startswith('art_'):
            number = article_id.replace('art_', '')
            normalized = self._normalize_article_number(number)
            return number, normalized

        return None, None

    def _normalize_article_number(self, number: str) -> str:
        """
        Normalize article number for sorting.

        Examples:
        - "1" -> "001"
        - "1a" -> "001a"
        - "335b" -> "335b"
        - "1bis" -> "001bis"
        """
        # Extract numeric part and suffix
        match = re.match(r'(\d+)(.*)$', number)
        if match:
            num_part = match.group(1).zfill(3)  # Pad with zeros
            suffix_part = match.group(2)
            return f"{num_part}{suffix_part}"
        return number

    def _extract_article_title(self, element: Tag, language: str) -> Dict[str, str]:
        """
        Extract article title (marginal note) in available languages.

        Args:
            element: Article element
            language: Document language

        Returns:
            Dictionary mapping language codes to titles
        """
        titles = {}

        # Look for title after article number in heading
        heading = element.select_one(self.SELECTORS['article_heading'])
        if heading:
            # First try to get the text after the bold tag (common pattern)
            bold_tag = heading.find('b')
            if bold_tag:
                # Get all text nodes after the bold tag
                title_parts = []
                for sibling in bold_tag.next_siblings:
                    if isinstance(sibling, str):
                        title_parts.append(sibling.strip())
                    elif sibling.name:
                        title_parts.append(sibling.get_text(strip=True))

                title_text = ' '.join(title_parts).strip()
                if title_text:
                    key = language if language else 'unknown'
                    titles[key] = title_text
                    return titles

            # Fallback: use regex to remove article number
            heading_text = heading.get_text(' ', strip=True)  # Add space between tags

            # Try to find and remove just the article number part
            for pattern, _ in self.ARTICLE_PATTERNS:
                # Use sub to remove the article number part
                title_text = re.sub(pattern, '', heading_text, flags=re.IGNORECASE).strip()
                if title_text and title_text != heading_text:
                    key = language if language else 'unknown'
                    titles[key] = title_text
                    break

        return titles

    def _extract_article_content(self, element: Tag) -> ArticleContent:
        """
        Extract structured content from article element.

        Args:
            element: Article element

        Returns:
            ArticleContent object with paragraphs, tables, footnotes
        """
        content = ArticleContent()

        # Find collapseable content div
        content_div = element.select_one(self.SELECTORS['article_content'])
        if not content_div:
            # Fallback to article element itself
            content_div = element

        # Extract paragraphs first
        paragraphs = self._extract_paragraphs(content_div)

        # Extract definition lists (numbered items with subpoints)
        definition_lists = self._extract_definition_lists(content_div)

        # Merge paragraphs and definition lists
        # If we have both paragraphs and definition lists with only subpoints,
        # try to attach the subpoints to the last paragraph
        if paragraphs and definition_lists:
            # Check if first definition list is just subpoints (no number)
            if definition_lists and not definition_lists[0].number and definition_lists[0].subpoints:
                # Attach subpoints to last paragraph
                if paragraphs[-1].subpoints == []:
                    paragraphs[-1].subpoints = definition_lists[0].subpoints
                    definition_lists.pop(0)

        content.paragraphs = paragraphs + definition_lists

        # Extract tables
        tables = content_div.select(self.SELECTORS['tables'])
        for table in tables:
            content.tables.append({
                'html': str(table),
                'text': table.get_text(strip=True)
            })

        # Extract footnotes
        footnotes_div = content_div.select_one(self.SELECTORS['footnotes'])
        if footnotes_div:
            for footnote in footnotes_div.find_all('p'):
                footnote_id = footnote.get('id', '')
                content.footnotes.append({
                    'id': footnote_id,
                    'text': footnote.get_text(strip=True)
                })

        # Store raw HTML for reference
        content.raw_html = str(content_div)

        return content

    def _extract_paragraphs(self, element: Tag) -> List[Paragraph]:
        """
        Extract regular paragraphs from content element.

        Args:
            element: Content element

        Returns:
            List of Paragraph objects
        """
        paragraphs = []

        for p_tag in element.select(self.SELECTORS['paragraphs']):
            # Skip if inside footnotes
            if p_tag.find_parent('div', class_='footnotes'):
                continue

            text = p_tag.get_text(strip=True)
            if not text:
                continue

            # Check for paragraph numbering (superscript numbers)
            # Pattern: ¹, ², ³ or 1, 2, 3 at the start
            para_match = re.match(r'^([¹²³⁴⁵⁶⁷⁸⁹⁰]+|\d+)\s*(.+)$', text)
            if para_match:
                para_num = para_match.group(1)
                para_text = para_match.group(2)
                # Convert superscript to normal numbers
                para_num = self._normalize_superscript(para_num)
            else:
                para_num = ""
                para_text = text

            paragraph = Paragraph(
                number=para_num,
                text=para_text,
                subpoints=[]
            )
            paragraphs.append(paragraph)

        return paragraphs

    def _extract_definition_lists(self, element: Tag) -> List[Paragraph]:
        """
        Extract numbered items with subpoints from definition lists.

        Args:
            element: Content element

        Returns:
            List of Paragraph objects with subpoints
        """
        paragraphs = []

        for dl_tag in element.select(self.SELECTORS['definition_lists']):
            # Get all dt/dd pairs
            terms = dl_tag.select(self.SELECTORS['definition_terms'])
            descriptions = dl_tag.select(self.SELECTORS['definition_descriptions'])

            current_paragraph = None
            standalone_subpoints = []  # For subpoints without a parent paragraph

            for term, desc in zip(terms, descriptions):
                term_text = term.get_text(strip=True)
                desc_text = desc.get_text(strip=True)

                # Check if this is a numbered item (1., 2., etc.)
                if re.match(r'^\d+\.?$', term_text):
                    # Start new paragraph
                    if current_paragraph:
                        paragraphs.append(current_paragraph)

                    current_paragraph = Paragraph(
                        number=term_text.rstrip('.'),
                        text=desc_text,
                        subpoints=[]
                    )
                # Check if this is a lettered subpoint (a., b., etc.)
                elif re.match(r'^[a-z]\.?$', term_text):
                    subpoint = Subpoint(
                        letter=term_text.rstrip('.'),
                        text=desc_text
                    )

                    if current_paragraph:
                        # Add to current paragraph
                        current_paragraph.subpoints.append(subpoint)
                    else:
                        # Store for later - might belong to a preceding paragraph
                        standalone_subpoints.append(subpoint)

            # Add last paragraph if exists
            if current_paragraph:
                paragraphs.append(current_paragraph)

            # If we have standalone subpoints, create a paragraph for them
            # or attach them to the last regular paragraph if one exists
            if standalone_subpoints:
                if paragraphs and not paragraphs[-1].subpoints:
                    # Attach to the last paragraph from regular paragraphs
                    # This handles the case where paragraph text comes before the dl
                    paragraphs[-1].subpoints.extend(standalone_subpoints)
                else:
                    # Create a new paragraph for these subpoints
                    paragraphs.append(Paragraph(
                        number='',
                        text='',
                        subpoints=standalone_subpoints
                    ))

        return paragraphs

    def _normalize_superscript(self, text: str) -> str:
        """
        Convert superscript numbers to normal numbers.

        Args:
            text: Text with possible superscript numbers

        Returns:
            Normalized number string
        """
        superscript_map = {
            '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
            '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
        }

        result = text
        for super_char, normal_char in superscript_map.items():
            result = result.replace(super_char, normal_char)

        return result

    def _extract_article_metadata(self, element: Tag) -> Dict[str, Any]:
        """
        Extract metadata from article element.

        Args:
            element: Article element

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        # Check for status indicators (repealed, in force, etc.)
        content_text = element.get_text(strip=True).lower()

        if any(word in content_text for word in ['aufgehoben', 'abrogé', 'abrogato', 'abolì']):
            metadata['status'] = 'repealed'
        else:
            metadata['status'] = 'in_force'

        # Extract any footnote references
        footnote_refs = element.select('sup a[href^="#fn"]')
        if footnote_refs:
            metadata['footnote_refs'] = [ref.get('href') for ref in footnote_refs]

        return metadata

    def _extract_language_from_path(self, file_path: str) -> Optional[str]:
        """
        Extract language code from file path.

        Args:
            file_path: Path to HTML file

        Returns:
            Language code (de, fr, it, rm) or None
        """
        path = Path(file_path)
        parts = path.parts

        # Look for language code in path
        for part in parts:
            if part in ['de', 'fr', 'it', 'rm']:
                return part

        return None

    def _generate_article_uri(self, file_path: str, article_number: str) -> str:
        """
        Generate URI for article based on file path and article number.

        Args:
            file_path: Path to HTML file
            article_number: Article number

        Returns:
            Generated URI
        """
        # Extract base URI from file path
        path = Path(file_path)

        # Build URI parts from path
        parts = []
        capture = False

        for part in path.parts:
            if part == 'eli':
                capture = True
                parts.append(part)
            elif capture and part not in ['html', 'pdf', 'xml']:
                parts.append(part)
                # Stop at date or language
                if part in ['de', 'fr', 'it', 'rm'] or re.match(r'\d{8}', part):
                    break

        if parts:
            base_uri = '/'.join(parts)
            return f"{base_uri}/art_{article_number}"

        return f"article_{article_number}"

    def _build_graph_entities(self, article: Article, result: ExtractionResult):
        """
        Convert article to graph nodes and relationships.

        Args:
            article: Extracted article
            result: ExtractionResult to populate
        """
        # Create article node
        node = {
            'uri': article.uri,
            'type': 'Article',
            'number': article.number,
            'number_normalized': article.number_normalized,
            'language': article.language,
            'status': article.metadata.get('status', 'in_force')
        }

        # Add titles
        for lang, title in article.titles.items():
            node[f'title_{lang}'] = title

        # Add content summary
        node['paragraph_count'] = len(article.content.paragraphs)
        node['has_tables'] = len(article.content.tables) > 0
        node['has_footnotes'] = len(article.content.footnotes) > 0

        # Store full content as JSON
        node['content'] = {
            'paragraphs': [
                {
                    'number': p.number,
                    'text': p.text,
                    'subpoints': [
                        {'letter': s.letter, 'text': s.text}
                        for s in p.subpoints
                    ]
                }
                for p in article.content.paragraphs
            ],
            'footnotes': article.content.footnotes
        }

        result.add_node(node)

        # Create relationships if we can determine the parent law
        # This would typically be done by the integration layer
        # that knows the document context

    def process_batch(self, file_paths: List[str],
                     progress_callback: Optional[callable] = None) -> List[ExtractionResult]:
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

    def validate_performance(self) -> Dict[str, Any]:
        """
        Validate extractor performance against requirements.

        Returns:
            Dictionary of performance metrics and pass/fail status
        """
        import time
        import tempfile

        # Create a test HTML with multiple articles
        test_html = """
        <html><body><main id="maintext">
        """ + "\n".join([f"""
        <article id="art_{i}">
            <h6 class="heading">Art. {i}</h6>
            <div class="collapseable">
                <p>Test content for article {i}</p>
            </div>
        </article>
        """ for i in range(1, 201)]) + """
        </main></body></html>
        """

        # Time extraction of 200 articles
        start = time.time()
        soup = BeautifulSoup(test_html, 'lxml')
        result = self.extract(soup)
        elapsed = time.time() - start

        articles_per_second = result.statistics.get('articles_extracted', 0) / elapsed

        return {
            'articles_extracted': result.statistics.get('articles_extracted', 0),
            'extraction_time_ms': elapsed * 1000,
            'articles_per_second': articles_per_second,
            'meets_200_per_second_target': articles_per_second >= 200,
            'errors': len(result.errors)
        }