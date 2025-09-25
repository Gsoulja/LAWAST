#!/usr/bin/env python3
"""Test article title extraction with debugging."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
from src.extractors.article_extractor import ArticleExtractor

# Sample HTML from our earlier analysis
html_content = """
<article id="art_1">
  <h6 class="heading" id="art_1">
    <span>
      <b>Art. 1</b> Zweck
    </span>
  </h6>
  <div class="collapseable">
    <p>Dieses Gesetz regelt...</p>
  </div>
</article>
"""

# Parse HTML
soup = BeautifulSoup(html_content, 'html.parser')
article = soup.find('article')

# Create extractor
extractor = ArticleExtractor()

# Debug title extraction
print("=== DEBUGGING ARTICLE TITLE EXTRACTION ===\n")

# Check selector
heading = article.select_one('h6.heading, h6')
print(f"1. Found heading element: {heading is not None}")
if heading:
    print(f"   Raw heading HTML: {heading}")
    print(f"   Raw heading text: '{heading.get_text(strip=True)}'")

# Check for bold tag
if heading:
    bold_tag = heading.find('b')
    print(f"\n2. Found bold tag: {bold_tag is not None}")
    if bold_tag:
        print(f"   Bold tag text: '{bold_tag.get_text(strip=True)}'")

        # Check siblings after bold tag
        print(f"\n3. Checking siblings after bold tag:")
        title_parts = []
        for sibling in bold_tag.next_siblings:
            if isinstance(sibling, str):
                cleaned = sibling.strip()
                if cleaned:
                    print(f"   - Text node: '{cleaned}'")
                    title_parts.append(cleaned)
            elif sibling.name:
                text = sibling.get_text(strip=True)
                if text:
                    print(f"   - Element ({sibling.name}): '{text}'")
                    title_parts.append(text)

        title_text = ' '.join(title_parts).strip()
        print(f"\n   Combined title: '{title_text}'")

# Now test the actual method
print("\n4. Testing actual _extract_article_title method:")
titles = extractor._extract_article_title(article, 'de')
print(f"   Result: {titles}")

# Test with actual file
print("\n=== TESTING WITH ACTUAL FILE ===\n")
html_file = Path("fedlex-assets/fedlex-data-admin-ch-eli-cc-1999-404-20240101-de-html-1.html")
if html_file.exists():
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    articles = soup.find_all('article', limit=3)

    for i, article in enumerate(articles, 1):
        print(f"Article {i}:")
        heading = article.select_one('h6.heading, h6')
        if heading:
            print(f"  Raw heading: {heading.get_text(strip=True)}")

        titles = extractor._extract_article_title(article, 'de')
        print(f"  Extracted titles: {titles}")
        print()
else:
    print(f"File {html_file} not found")