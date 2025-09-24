# TASK-008.3: Article Content Extraction Module

**Status**: BACKLOG
**Priority**: CRITICAL
**Type**: feature
**Parent**: TASK-008
**Estimated Effort**: 2 days
**Created**: 2024-01-24

## Description
Extract complete article content from parsed HTML including article numbers, titles, full text, structure (paragraphs, subsections), and metadata. This is the core content that enables legal search and analysis.

### 📊 FEASIBILITY ANALYSIS: CONFIRMED EASY ✅
Based on comprehensive analysis of Fedlex HTML files (see `/docs/html-extraction-analysis.md`):
- **70% of documents** have `<article>` tags with consistent structure
- **Article ID pattern**: `id="art_1"`, `id="art_2"`, etc.
- **Article heading**: `h6.heading` contains "Art. N"
- **Article content**: `div.collapseable` contains all paragraphs and lists
- **Numbered items**: Use `<dl>`, `<dt>`, `<dd>` tags consistently

## Acceptance Criteria
- [ ] Extracts all article numbers (1, 1a, 1bis, 335b formats)
- [ ] Captures article titles in all languages
- [ ] Preserves complete text with structure
- [ ] Maintains paragraph/subsection hierarchy
- [ ] Handles tables and lists correctly
- [ ] Extracts marginalia and annotations
- [ ] Links articles to taxonomy
- [ ] Performance: 200+ articles/second
- [ ] All tests pass
- [ ] Documentation complete

## Technical Implementation

### Article Extractor
```python
class ArticleExtractor:
    def extract(self, parsed_doc: ParsedDocument) -> List[Article]:
        articles = []

        # Find all article containers
        article_elements = self.find_article_elements(parsed_doc)

        for element in article_elements:
            article = Article()

            # Extract number (handle complex formats)
            article.number = self.extract_article_number(element)

            # Extract titles (multi-language)
            article.titles = self.extract_titles(element)

            # Extract content with structure
            article.content = self.extract_structured_content(element)

            # Extract metadata
            article.metadata = self.extract_metadata(element)

            # Link to taxonomy
            article.taxonomy_path = self.get_taxonomy_path(element)

            articles.append(article)

        return articles

    def extract_article_number(self, element):
        # Patterns: Art. 1, 1a, 1bis, 1ter, 335b, etc.
        patterns = [
            r'Art\.\s*(\d+[a-z]?(?:bis|ter|quater)?)',
            r'Article\s*(\d+[a-z]?)',
            r'Artikel\s*(\d+[a-z]?)',
            r'Articolo\s*(\d+[a-z]?)'
        ]
        # Extract and normalize
        ...
```

## Content Structure to Preserve

### Article Components
1. **Number**: Including complex formats (1, 1a, 1bis, 335b)
2. **Title**: Marginal title in all languages
3. **Lead paragraph**: Opening text
4. **Subsections**: Numbered paragraphs (1., 2., 3.)
5. **Letters**: Sub-points (a., b., c.)
6. **Tables**: Structured data
7. **Footnotes**: Explanatory notes
8. **Annotations**: Editorial notes

### Example Structure
```
Art. 1 Persönlichkeit
¹ Die Persönlichkeit beginnt mit der Geburt.
² Das Kind wird mit der Geburt rechtsfähig.
³ Vorbehalten bleiben:
  a. die Handlungsfähigkeit;
  b. besondere Vorschriften.
```

## Storage Format
```json
{
  "uri": "eli/cc/24/233_245_233/art_1",
  "number": "1",
  "number_normalized": "001",
  "titles": {
    "de": "Persönlichkeit",
    "fr": "Personnalité",
    "it": "Personalità"
  },
  "content": {
    "paragraphs": [
      {
        "number": "1",
        "text": "Die Persönlichkeit beginnt mit der Geburt.",
        "subpoints": []
      },
      {
        "number": "3",
        "text": "Vorbehalten bleiben:",
        "subpoints": [
          {"letter": "a", "text": "die Handlungsfähigkeit"},
          {"letter": "b", "text": "besondere Vorschriften"}
        ]
      }
    ]
  }
}
```

## Edge Cases to Handle
- Articles split across multiple pages
- Articles with complex numbering (335b, 41bis)
- Repealed articles (aufgehoben/abrogé)
- Transitional provisions
- Articles with tables or formulas
- Multi-column layouts

## Testing Requirements
- Test all article number formats
- Verify structure preservation
- Test multi-language extraction
- Validate against ground truth
- Performance benchmarks

## Success Metrics
- 99%+ article extraction rate
- Correct structure preservation
- All languages captured
- < 1% missing content