#!/usr/bin/env python3
"""
Debug SR 101 extraction issue
"""

import json
from pathlib import Path
from src.data_access.neo4j_connection import Neo4jConnectionManager

def check_what_we_have():
    """Check what files we have for SR 101"""

    # Check JSON files
    json_files = [
        Path("fedlex/eli/cc/1999/404.json"),
        Path("fedlex/eli/cc/1999/404/20240101.json"),
        Path("fedlex/eli/cc/1999/404/20220213.json"),
    ]

    print("JSON files for SR 101:")
    for f in json_files:
        if f.exists():
            print(f"  ✓ {f}")

            # Check content
            with open(f, 'r') as fp:
                data = json.load(fp)

            # Check if it has SR number
            title = data.get('data', {}).get('attributes', {}).get('title', {})
            if isinstance(title, dict):
                title_de = title.get('xsd:string', '')
            else:
                included = data.get('included', [])
                for item in included:
                    if item.get('type') == 'Expression':
                        attrs = item.get('attributes', {})
                        if 'title' in attrs:
                            title_de = attrs['title'].get('xsd:string', '')
                            break
                else:
                    title_de = ''

            print(f"    Title: {title_de[:50]}...")

            # Check for Bundesverfassung
            if 'Bundesverfassung' in str(title_de):
                print(f"    → This is the Constitution!")

                # Manually extract SR number
                import re

                # Check URI
                uri = data.get('data', {}).get('uri', '')
                print(f"    URI: {uri}")

                # Extract from URI
                match = re.search(r'/(\d{4})/(\d+)', uri)
                if match:
                    print(f"    SR number from URI: {match.group(2)}")

    print("\n" + "="*60)

def test_process_law():
    """Test processing a single law file"""

    from scripts.build_lawast_graph import LawastGraphBuilder

    # Initialize builder
    builder = LawastGraphBuilder(
        clean_db=True,
        skip_download=True,
        skip_embeddings=True,
        sr_filter='101'
    )

    # Test with first JSON file
    test_file = Path("fedlex/eli/cc/1999/404.json")
    if test_file.exists():
        print(f"\nProcessing: {test_file}")

        result = builder.process_law_file(test_file)
        print(f"Result: {result}")

        # Check database
        conn = Neo4jConnectionManager()
        with conn.get_session() as session:
            # Count articles
            result = session.run("MATCH (a:Article) RETURN count(a) as count")
            count = result.single()['count']
            print(f"\nArticles in database: {count}")

            # Check for Article 16
            result = session.run("""
                MATCH (a:Article)
                WHERE a.number = '16'
                RETURN a.title_de as title, a.content_full as content
            """)
            record = result.single()
            if record:
                print(f"\n✓ Article 16 found!")
                print(f"  Title: {record['title']}")
                print(f"  Content: {record['content'][:200]}...")
            else:
                print("\n✗ Article 16 not found")
        conn.close()

if __name__ == "__main__":
    check_what_we_have()
    test_process_law()