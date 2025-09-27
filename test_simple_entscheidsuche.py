#!/usr/bin/env python3
"""
Test EntscheidSuche API with simple queries
"""

import requests
import json
from rich.console import Console

console = Console()


def test_simple_searches():
    """Test with very simple search queries"""

    console.print("\n[bold cyan]SIMPLE SEARCH TESTS[/bold cyan]\n")

    # Try different query formats
    queries = [
        {
            "query": {
                "match_all": {}
            },
            "size": 1,
            "_source": ["signatur", "datum", "spider"]
        },
        {
            "query": {
                "match": {
                    "_all": "Meinungsfreiheit"
                }
            },
            "size": 2
        },
        {
            "query": {
                "query_string": {
                    "query": "Meinungsfreiheit"
                }
            },
            "size": 2
        },
        {
            "query": {
                "simple_query_string": {
                    "query": "16 BV",
                    "fields": ["content", "kopfzeile_de", "abstract_de"]
                }
            },
            "size": 2
        }
    ]

    for i, query in enumerate(queries, 1):
        console.print(f"\n[bold]Test {i}: {list(query['query'].keys())[0]}[/bold]")

        try:
            response = requests.post(
                "https://entscheidsuche.ch/_search.php",
                json=query,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                total = data.get('hits', {}).get('total', 0)
                if isinstance(total, dict):
                    total = total.get('value', 0)

                console.print(f"Status: [green]200 OK[/green]")
                console.print(f"Total hits: {total}")

                if data.get('hits', {}).get('hits'):
                    hit = data['hits']['hits'][0]
                    console.print(f"First result: {hit.get('_source', {}).get('signatur', 'N/A')}")
                    console.print(f"Score: {hit.get('_score', 0)}")

            else:
                console.print(f"Status: [red]{response.status_code}[/red]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")


def test_index_info():
    """Try to get index information"""

    console.print("\n[bold yellow]INDEX INFORMATION[/bold yellow]\n")

    # Try to get mapping
    try:
        response = requests.get(
            "https://entscheidsuche.ch/_mapping",
            timeout=5
        )
        console.print(f"Mapping endpoint: {response.status_code}")
    except:
        pass

    # Try alternative Elasticsearch endpoint
    try:
        response = requests.get(
            "https://entscheidsuche.pansoft.de:9200/entscheidsuche-*/_mapping",
            timeout=5
        )
        console.print(f"Direct mapping: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # Show available fields
            for index_name, index_data in data.items():
                console.print(f"\nIndex: {index_name}")
                mappings = index_data.get('mappings', {})
                properties = mappings.get('properties', {})
                if properties:
                    console.print(f"Fields: {', '.join(list(properties.keys())[:10])}...")
                break
    except Exception as e:
        console.print(f"Direct endpoint: {str(e)}")


def test_web_scraping_fallback():
    """Test web scraping as fallback"""

    console.print("\n[bold magenta]WEB SCRAPING FALLBACK[/bold magenta]\n")

    # Search through web interface
    params = {
        'q': 'Art. 16 BV'
    }

    try:
        response = requests.get(
            "https://entscheidsuche.ch/search",
            params=params,
            timeout=10
        )

        if response.status_code == 200:
            console.print("[green]✓ Web search accessible[/green]")

            # Check if results in HTML
            if 'BGE' in response.text or 'Bundesgericht' in response.text:
                console.print("Found court decision references in HTML")

                # Count BGE references
                import re
                bge_pattern = r'BGE\s+\d+\s+[IVX]+\s+\d+'
                bge_matches = re.findall(bge_pattern, response.text)
                if bge_matches:
                    console.print(f"Sample BGE references: {', '.join(bge_matches[:5])}")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")


def main():
    test_simple_searches()
    test_index_info()
    test_web_scraping_fallback()

    console.print("\n[bold green]✅ Testing Complete![/bold green]\n")


if __name__ == "__main__":
    main()