#!/usr/bin/env python3
"""
Extract all articles from Swiss Constitution (Bundesverfassung) HTML files
"""

import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any

def extract_articles_from_html(html_path: Path) -> List[Dict[str, Any]]:
    """Extract all articles from Constitution HTML file"""

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')

    articles = []
    article_elements = soup.find_all('article')

    for article_elem in article_elements:
        # Extract article number and title
        article_data = {}

        # Get article ID if available
        article_id = article_elem.get('id', '')

        # Find article number (Art. X)
        art_pattern = re.compile(r'Art\.\s+(\d+[a-z]?)', re.I)
        art_match = None

        # Check in various places for article number
        for elem in article_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div']):
            text = elem.get_text()
            match = art_pattern.search(text)
            if match:
                art_match = match
                article_data['number'] = match.group(1)

                # Extract title (text after Art. X)
                title_text = text[match.end():].strip()
                if title_text:
                    # Clean up title - remove footnote markers
                    title_text = re.sub(r'\d+$', '', title_text).strip()
                    article_data['title'] = title_text
                break

        if not art_match:
            # Skip if no article number found
            continue

        # Extract article content (paragraphs)
        paragraphs = []
        content_full = ""

        # Find all paragraph-like elements within article
        for p_elem in article_elem.find_all(['p', 'div']):
            text = p_elem.get_text().strip()

            # Skip if it's the article header we already processed
            if art_pattern.match(text):
                continue

            # Skip empty paragraphs
            if not text:
                continue

            # Check if it's a numbered paragraph (1. 2. 3. etc)
            para_pattern = re.compile(r'^(\d+)\.\s+(.+)')
            para_match = para_pattern.match(text)

            if para_match:
                para_num = para_match.group(1)
                para_text = para_match.group(2)

                paragraphs.append({
                    'number': int(para_num),
                    'text': para_text
                })

                content_full += text + " "
            else:
                # Non-numbered paragraph or continuation
                if text and not text.startswith('Art.'):
                    # Add to last paragraph if exists, otherwise create new
                    if paragraphs:
                        paragraphs[-1]['text'] += " " + text
                    else:
                        paragraphs.append({
                            'number': 1,
                            'text': text
                        })
                    content_full += text + " "

        # Store article data
        article_data['paragraphs'] = paragraphs
        article_data['content_full'] = content_full.strip()
        article_data['uri'] = f"https://fedlex.data.admin.ch/eli/cc/1999/404/art_{article_data['number']}"

        articles.append(article_data)

    return articles


def extract_all_bv_articles() -> List[Dict[str, Any]]:
    """Extract all articles from the latest Constitution version"""

    # Find the latest German HTML file
    html_pattern = Path("fedlex-assets/eli/cc/1999/404/20240101/de/html")
    main_html = html_pattern / "fedlex-data-admin-ch-eli-cc-1999-404-20240101-de-html.html"

    if not main_html.exists():
        # Try to find any German HTML file
        html_files = list(Path("fedlex-assets/eli/cc/1999/404").glob("*/de/html/*-de-html.html"))
        if html_files:
            main_html = html_files[0]
        else:
            raise FileNotFoundError("No Constitution HTML file found")

    print(f"Extracting articles from: {main_html}")
    articles = extract_articles_from_html(main_html)

    # Sort by article number (handle 'a', 'b' suffixes)
    def sort_key(art):
        num = art['number']
        # Split number and suffix
        match = re.match(r'(\d+)([a-z]?)', num)
        if match:
            return (int(match.group(1)), match.group(2))
        return (999, '')

    articles.sort(key=sort_key)

    return articles


def main():
    """Main function to extract and save Constitution articles"""

    print("Extracting Swiss Constitution articles...")

    try:
        articles = extract_all_bv_articles()

        print(f"\nExtracted {len(articles)} articles")

        # Show sample
        for art in articles[:5]:
            print(f"  Art. {art['number']}: {art.get('title', 'No title')[:50]}...")
            print(f"    Paragraphs: {len(art['paragraphs'])}")

        print("...")

        for art in articles[-5:]:
            print(f"  Art. {art['number']}: {art.get('title', 'No title')[:50]}...")
            print(f"    Paragraphs: {len(art['paragraphs'])}")

        # Count total paragraphs
        total_paragraphs = sum(len(art['paragraphs']) for art in articles)
        print(f"\nTotal paragraphs: {total_paragraphs}")

        # Save to JSON file for later use
        output_file = Path("extracted_bv_articles.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)

        print(f"\nSaved to: {output_file}")

        # Check for Article 16 (Meinungsfreiheit)
        art_16 = next((art for art in articles if art['number'] == '16'), None)
        if art_16:
            print(f"\n✓ Article 16 found: {art_16.get('title', '')}")
            print(f"  Content: {art_16['content_full'][:200]}...")
        else:
            print("\n✗ Article 16 not found!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()