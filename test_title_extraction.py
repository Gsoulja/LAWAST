#!/usr/bin/env python3
"""
Test script to verify that law titles are correctly extracted from Expression objects
"""

import json
from pathlib import Path

def test_title_extraction():
    """Test title extraction with sample law data"""

    # Sample law path
    law_file = Path("fedlex/eli/cc/1979/10_10_10.json")

    if not law_file.exists():
        print(f"File not found: {law_file}")
        return

    # Load law data
    with open(law_file, 'r', encoding='utf-8') as f:
        law_data = json.load(f)

    # Extract titles using the same logic as unified_law_processor
    def extract_value(prop):
        if isinstance(prop, dict):
            return prop.get('xsd:string') or prop.get('xsd:date') or prop.get('rdfs:Resource') or prop.get('value')
        return prop

    titles = {'de': None, 'fr': None, 'it': None, 'rm': None}
    included = law_data.get('included', [])

    print("=" * 60)
    print("Testing Law Title Extraction")
    print("=" * 60)
    print(f"Law file: {law_file}")
    print(f"Found {len(included)} included items")
    print()

    expression_count = 0
    for item in included:
        if item.get('type') == 'Expression':
            expression_count += 1
            expr_attrs = item.get('attributes', {})

            # Extract title
            title = extract_value(expr_attrs.get('title')) or \
                    extract_value(expr_attrs.get('titleShort')) or \
                    extract_value(expr_attrs.get('titleAlternative'))

            # Extract language from references
            lang_ref = item.get('references', {}).get('language', '')

            print(f"Expression {expression_count}:")
            print(f"  URI: {item.get('uri', 'N/A')}")
            print(f"  Language reference: {lang_ref}")
            print(f"  Title: {title}")

            # Map language URI to language code
            if 'DEU' in lang_ref:
                titles['de'] = title
                print(f"  -> Assigned to German (de)")
            elif 'FRA' in lang_ref:
                titles['fr'] = title
                print(f"  -> Assigned to French (fr)")
            elif 'ITA' in lang_ref:
                titles['it'] = title
                print(f"  -> Assigned to Italian (it)")
            elif 'ROH' in lang_ref:
                titles['rm'] = title
                print(f"  -> Assigned to Romansh (rm)")
            else:
                print(f"  -> Language not recognized, using fallback")
            print()

    print("-" * 60)
    print("EXTRACTED TITLES:")
    print("-" * 60)
    for lang, title in titles.items():
        if title:
            print(f"{lang.upper()}: {title}")
        else:
            print(f"{lang.upper()}: [No title found]")

    print()
    print("=" * 60)
    print(f"SUMMARY: Found {sum(1 for t in titles.values() if t)} titles out of 4 languages")
    print("=" * 60)

    return titles


def test_multiple_laws(limit=5):
    """Test title extraction on multiple laws"""

    json_dir = Path("fedlex")
    laws_tested = 0
    laws_with_titles = 0
    total_titles = 0

    print("\n" + "=" * 60)
    print("Testing Multiple Laws")
    print("=" * 60)

    # Find law JSON files
    for json_file in json_dir.glob("eli/cc/**/*.json"):
        # Skip version files (date-named)
        if json_file.stem.isdigit() and len(json_file.stem) == 8:
            continue

        if laws_tested >= limit:
            break

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                law_data = json.load(f)

            # Check if it has included section with Expression objects
            included = law_data.get('included', [])
            expressions = [item for item in included if item.get('type') == 'Expression']

            if not expressions:
                continue

            laws_tested += 1

            # Extract titles
            def extract_value(prop):
                if isinstance(prop, dict):
                    return prop.get('xsd:string') or prop.get('xsd:date') or prop.get('rdfs:Resource') or prop.get('value')
                return prop

            titles = {'de': None, 'fr': None, 'it': None, 'rm': None}

            for item in expressions:
                expr_attrs = item.get('attributes', {})
                title = extract_value(expr_attrs.get('title')) or \
                        extract_value(expr_attrs.get('titleShort')) or \
                        extract_value(expr_attrs.get('titleAlternative'))

                if title:
                    lang_ref = item.get('references', {}).get('language', '')

                    if 'DEU' in lang_ref:
                        titles['de'] = title
                    elif 'FRA' in lang_ref:
                        titles['fr'] = title
                    elif 'ITA' in lang_ref:
                        titles['it'] = title
                    elif 'ROH' in lang_ref:
                        titles['rm'] = title

            title_count = sum(1 for t in titles.values() if t)
            if title_count > 0:
                laws_with_titles += 1
                total_titles += title_count

            print(f"\nLaw {laws_tested}: {json_file.relative_to(json_dir)}")
            print(f"  Titles found: {title_count}/4 languages")
            for lang, title in titles.items():
                if title:
                    print(f"  {lang.upper()}: {title[:60]}...")

        except Exception as e:
            print(f"Error processing {json_file}: {e}")

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)
    print(f"Laws tested: {laws_tested}")
    print(f"Laws with titles: {laws_with_titles}/{laws_tested} ({laws_with_titles*100//laws_tested if laws_tested else 0}%)")
    print(f"Average titles per law: {total_titles/laws_tested if laws_tested else 0:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    # Test single law
    test_title_extraction()

    # Test multiple laws
    test_multiple_laws(limit=10)