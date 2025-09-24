# TASK-008: Unified Content Extraction - Technical Specification

**Version**: 1.0
**Date**: 2025-09-24
**Status**: Ready for Implementation

## Overview

This document provides the complete technical specification for implementing the Unified Content Extraction pipeline based on the comprehensive analysis of Fedlex HTML files.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Unified Pipeline                        │
├───────────────┬──────────────┬──────────────┬───────────┤
│ HTML Parser   │ Taxonomy     │ Article      │ Reference │
│ (TASK-008.1)  │ Extractor    │ Extractor    │ Resolver  │
│               │ (TASK-008.2) │ (TASK-008.3) │ (008.4)   │
└───────────────┴──────────────┴──────────────┴───────────┘
        ↓               ↓              ↓             ↓
┌─────────────────────────────────────────────────────────┐
│                    Neo4j Graph Store                      │
└─────────────────────────────────────────────────────────┘
```

## Module Specifications

### 1. UnifiedHtmlParser (TASK-008.1)

**Purpose**: Robust HTML parsing with caching and fallback strategies

```python
from bs4 import BeautifulSoup
import lxml
from functools import lru_cache
from typing import Optional, Dict, Any
import logging

class UnifiedHtmlParser:
    """
    Unified HTML parser with multi-parser fallback and caching.
    Handles all Fedlex HTML formats efficiently.
    """

    def __init__(self, cache_size: int = 1000):
        self.cache_size = cache_size
        self.stats = {'parsed': 0, 'cache_hits': 0, 'errors': 0}
        self.logger = logging.getLogger(__name__)

    @lru_cache(maxsize=1000)
    def parse(self, html_path: str) -> Optional[BeautifulSoup]:
        """
        Parse HTML file with fallback strategy.

        Args:
            html_path: Path to HTML file

        Returns:
            Parsed BeautifulSoup object or None on failure
        """
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Try parsers in order of preference
            parsers = ['lxml', 'html.parser', 'html5lib']

            for parser in parsers:
                try:
                    soup = BeautifulSoup(html_content, parser)
                    self.stats['parsed'] += 1
                    return soup
                except Exception as e:
                    self.logger.debug(f"Parser {parser} failed: {e}")
                    continue

            self.stats['errors'] += 1
            return None

        except Exception as e:
            self.logger.error(f"Failed to parse {html_path}: {e}")
            self.stats['errors'] += 1
            return None

    def get_stats(self) -> Dict[str, int]:
        """Return parsing statistics"""
        return self.stats.copy()
```

### 2. TaxonomyExtractor (TASK-008.2)

**Purpose**: Extract classification and metadata from HTML

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
import re

@dataclass
class TaxonomyData:
    sr_number: Optional[str]
    title: Dict[str, str]  # {language: title}
    conclusion_date: Optional[str]
    entry_force_date: Optional[str]
    status_date: Optional[str]
    references: List[str]
    language: str

class TaxonomyExtractor:
    """
    Extract taxonomy and classification data from Fedlex HTML.
    """

    # CSS Selectors for taxonomy elements
    SELECTORS = {
        'sr_number': 'p.srnummer',
        'title': 'h1.erlasstitel',
        'preface': 'div#preface',
        'cross_refs': 'a[href*="fedlex.data.admin.ch"]'
    }

    def extract(self, soup: BeautifulSoup, file_path: str) -> TaxonomyData:
        """
        Extract all taxonomy data from parsed HTML.

        Args:
            soup: Parsed HTML document
            file_path: Original file path (for language detection)

        Returns:
            TaxonomyData object with all extracted information
        """
        taxonomy = TaxonomyData(
            sr_number=None,
            title={},
            conclusion_date=None,
            entry_force_date=None,
            status_date=None,
            references=[],
            language=self._detect_language(file_path)
        )

        # Extract SR Number
        sr_elem = soup.select_one(self.SELECTORS['sr_number'])
        if sr_elem:
            taxonomy.sr_number = sr_elem.get_text(strip=True)

        # Extract Title
        title_elem = soup.select_one(self.SELECTORS['title'])
        if title_elem:
            taxonomy.title[taxonomy.language] = title_elem.get_text(strip=True)

        # Extract dates from preface
        preface = soup.select_one(self.SELECTORS['preface'])
        if preface:
            self._extract_dates(preface, taxonomy)

        # Extract cross-references
        for link in soup.select(self.SELECTORS['cross_refs']):
            taxonomy.references.append(link.get('href'))

        return taxonomy

    def _detect_language(self, file_path: str) -> str:
        """Detect language from file path"""
        for lang in ['de', 'fr', 'it', 'rm']:
            if f'/{lang}/html/' in file_path:
                return lang
        return 'unknown'

    def _extract_dates(self, preface, taxonomy):
        """Extract various dates from preface text"""
        date_patterns = {
            'conclusion': r'(?:Abgeschlossen|Conclu|Concluso) .*?(\d{1,2}\.\s*\w+\s+\d{4})',
            'force': r'(?:Kraft|vigueur|vigore) .*?(\d{1,2}\.\s*\w+\s+\d{4})',
            'status': r'(?:Stand|État|Stato) .*?(\d{1,2}\.\s*\w+\s+\d{4})'
        }

        preface_text = preface.get_text()
        for date_type, pattern in date_patterns.items():
            match = re.search(pattern, preface_text)
            if match:
                setattr(taxonomy, f'{date_type}_date', match.group(1))
```

### 3. ArticleExtractor (TASK-008.3)

**Purpose**: Extract structured article content

```python
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class ArticleContent:
    article_id: str
    number: str
    heading: str
    paragraphs: List[Dict[str, Any]]
    numbered_items: List[Dict[str, str]]
    footnotes: List[str]

class ArticleExtractor:
    """
    Extract article content with structure preservation.
    """

    def extract_all(self, soup: BeautifulSoup) -> List[ArticleContent]:
        """
        Extract all articles from HTML document.

        Args:
            soup: Parsed HTML document

        Returns:
            List of ArticleContent objects
        """
        articles = []

        for article_elem in soup.find_all('article'):
            article = self._extract_article(article_elem)
            if article:
                articles.append(article)

        return articles

    def _extract_article(self, article_elem) -> Optional[ArticleContent]:
        """Extract single article with all content"""

        # Get article ID
        article_id = article_elem.get('id', '')
        if not article_id:
            return None

        # Extract heading
        heading_elem = article_elem.find('h6', class_='heading')
        heading = heading_elem.get_text(strip=True) if heading_elem else ''

        # Extract article number from heading
        number_match = re.search(r'Art\.\s*(\d+\w*)', heading)
        number = number_match.group(1) if number_match else ''

        # Extract content
        content_div = article_elem.find('div', class_='collapseable')
        if not content_div:
            return None

        # Extract paragraphs
        paragraphs = []
        for p in content_div.find_all('p', recursive=False):
            paragraphs.append({
                'text': p.get_text(strip=True),
                'html': str(p)
            })

        # Extract numbered items (definition lists)
        numbered_items = []
        for dl in content_div.find_all('dl'):
            for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                numbered_items.append({
                    'number': dt.get_text(strip=True),
                    'text': dd.get_text(strip=True)
                })

        # Extract footnotes
        footnotes = []
        footnote_div = content_div.find('div', class_='footnotes')
        if footnote_div:
            for fn in footnote_div.find_all('p'):
                footnotes.append(fn.get_text(strip=True))

        return ArticleContent(
            article_id=article_id,
            number=number,
            heading=heading,
            paragraphs=paragraphs,
            numbered_items=numbered_items,
            footnotes=footnotes
        )
```

### 4. Neo4j Integration

```python
class GraphIntegrator:
    """
    Integrate extracted data into Neo4j graph.
    """

    def __init__(self, connection):
        self.connection = connection

    def create_law_node(self, taxonomy: TaxonomyData) -> str:
        """Create or update law node with taxonomy"""
        query = """
        MERGE (l:Law {sr_number: $sr_number})
        SET l.title = $title,
            l.conclusion_date = $conclusion_date,
            l.entry_force_date = $entry_force_date,
            l.status_date = $status_date,
            l.language = $language
        RETURN l.uri as uri
        """
        result = self.connection.execute_write(
            query,
            sr_number=taxonomy.sr_number,
            title=taxonomy.title,
            conclusion_date=taxonomy.conclusion_date,
            entry_force_date=taxonomy.entry_force_date,
            status_date=taxonomy.status_date,
            language=taxonomy.language
        )
        return result[0]['uri'] if result else None

    def create_article_nodes(self, articles: List[ArticleContent], law_uri: str):
        """Create article nodes and link to law"""
        for article in articles:
            query = """
            MATCH (l:Law {uri: $law_uri})
            CREATE (a:Article {
                uri: $article_uri,
                number: $number,
                heading: $heading,
                content: $content
            })
            CREATE (l)-[:HAS_ARTICLE]->(a)
            """

            self.connection.execute_write(
                query,
                law_uri=law_uri,
                article_uri=f"{law_uri}/art_{article.number}",
                number=article.number,
                heading=article.heading,
                content=json.dumps({
                    'paragraphs': article.paragraphs,
                    'numbered_items': article.numbered_items,
                    'footnotes': article.footnotes
                })
            )
```

## Implementation Plan

### Phase 1: Foundation (Day 1)
1. Implement `UnifiedHtmlParser` with caching
2. Set up testing framework
3. Create sample data fixtures

### Phase 2: Extractors (Day 2-3)
1. Implement `TaxonomyExtractor`
2. Implement `ArticleExtractor`
3. Unit test each extractor

### Phase 3: Integration (Day 4)
1. Neo4j integration layer
2. Batch processing logic
3. Error handling and logging

### Phase 4: Testing (Day 5)
1. Integration tests
2. Performance benchmarks
3. Multi-language validation

### Phase 5: Documentation (Day 6)
1. API documentation
2. Usage examples
3. Deployment guide

## Performance Targets

| Metric | Target | Current Estimate |
|--------|--------|------------------|
| Parse time per file | <300ms | ✅ Achievable |
| Articles per second | 200+ | ✅ Achievable |
| Memory usage (1000 files) | <100MB | ✅ 30MB cache |
| Extraction accuracy | >95% | ✅ Structure supports |

## Testing Strategy

### Unit Tests
```python
def test_article_extraction():
    html = '<article id="art_1">...</article>'
    soup = BeautifulSoup(html, 'html.parser')
    extractor = ArticleExtractor()
    articles = extractor.extract_all(soup)
    assert len(articles) == 1
    assert articles[0].number == "1"
```

### Integration Tests
- Process sample of 100 files
- Verify graph consistency
- Check cross-references

### Performance Tests
- Batch of 1000 files
- Memory monitoring
- Concurrent processing

## Dependencies

### Required (Already Installed)
- `beautifulsoup4>=4.12.2`
- `lxml>=4.9.0`
- `neo4j>=5.14.0`

### To Add
- `html5lib` - For fallback parsing
- `pytest-benchmark` - For performance testing

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Memory overflow | LRU cache with configurable size |
| Malformed HTML | Multi-parser fallback strategy |
| Missing elements | Graceful degradation, log warnings |
| Performance regression | Benchmark tests in CI |

## Success Criteria

1. ✅ Parse 99%+ of Fedlex HTML files
2. ✅ Extract articles from 70%+ of documents
3. ✅ Capture all taxonomy elements
4. ✅ Process 100 files in <30 seconds
5. ✅ Zero memory leaks after 10K files

## Conclusion

The Fedlex HTML structure is **exceptionally well-suited** for automated extraction. With clear semantic markup and consistent patterns, the implementation is straightforward and low-risk. The proposed architecture provides robust parsing with excellent performance characteristics.