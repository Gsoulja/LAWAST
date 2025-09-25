#!/usr/bin/env python3
"""Test article title extraction with real HTML files."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
from src.extractors.article_extractor import ArticleExtractor

# Test with actual file
html_file = Path("fedlex-assets/eli/cc/X/35_37_37/19890810/it/html/fedlex-data-admin-ch-eli-cc-X-35_37_37-19890810-it-html-1.html")

print(f"Testing with file: {html_file}")
print("=" * 60)

if html_file.exists():
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    articles = soup.find_all('article', limit=5)

    print(f"Found {len(articles)} articles in the HTML")
    print()

    extractor = ArticleExtractor()

    for i, article in enumerate(articles, 1):
        print(f"Article {i}:")

        # Get article ID
        article_id = article.get('id', 'unknown')
        print(f"  ID: {article_id}")

        # Check heading structure
        heading = article.select_one('h6.heading, h6')
        if heading:
            print(f"  Raw heading text: '{heading.get_text(strip=True)}'")

            # Check for bold tag
            bold = heading.find('b')
            if bold:
                print(f"  Bold tag text: '{bold.get_text(strip=True)}'")

                # Check what comes after bold
                after_bold = []
                for sibling in bold.next_siblings:
                    if isinstance(sibling, str):
                        text = sibling.strip()
                        if text:
                            after_bold.append(text)
                    elif sibling.name:
                        text = sibling.get_text(strip=True)
                        if text:
                            after_bold.append(text)

                if after_bold:
                    print(f"  Text after bold: '{' '.join(after_bold)}'")
                else:
                    print(f"  No text found after bold tag")
        else:
            print(f"  No heading found")

        # Test extraction
        titles = extractor._extract_article_title(article, 'it')
        print(f"  Extracted titles: {titles}")
        print()

        if i >= 3:
            break
else:
    print(f"File not found: {html_file}")