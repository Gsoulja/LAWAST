#!/usr/bin/env python3
"""
Test direct API calls to entscheidsuche.ch
Discover actual available endpoints
"""

import requests
import json
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON

console = Console()


def test_api_endpoints():
    """Test various possible API endpoints"""

    console.print("\n" + "="*80)
    console.print("[bold cyan]TESTING ENTSCHEIDSUCHE.CH API ENDPOINTS[/bold cyan]")
    console.print("="*80 + "\n")

    base_urls = [
        "https://entscheidsuche.ch",
        "https://api.entscheidsuche.ch",
        "https://entscheidsuche.ch/api"
    ]

    # Common API patterns to test
    endpoints = [
        "/search",
        "/api/search",
        "/api/v1/search",
        "/v1/search",
        "/decisions",
        "/api/decisions",
        "/query",
        "/api/query"
    ]

    headers = {
        'User-Agent': 'LAWAST/1.0 (Legal Assistant)',
        'Accept': 'application/json'
    }

    # Test each combination
    for base in base_urls:
        console.print(f"\n[bold]Testing base URL: {base}[/bold]")

        # First test if base URL is reachable
        try:
            response = requests.get(base, headers=headers, timeout=5)
            console.print(f"  Base URL status: [green]{response.status_code}[/green]")

            # Check if there's an API documentation endpoint
            for doc_endpoint in ["/docs", "/api-docs", "/swagger", "/openapi"]:
                try:
                    doc_url = base + doc_endpoint
                    doc_response = requests.get(doc_url, headers=headers, timeout=3)
                    if doc_response.status_code == 200:
                        console.print(f"  [green]✓ Found API docs at: {doc_url}[/green]")
                except:
                    pass

        except requests.exceptions.RequestException as e:
            console.print(f"  Base URL error: [red]{str(e)}[/red]")
            continue

        # Test search endpoints
        for endpoint in endpoints:
            url = base + endpoint

            # Test with a simple search query
            params = {
                'q': 'Art. 16 BV',
                'query': 'Art. 16 BV',
                'search': 'Art. 16 BV',
                'text': 'Art. 16 BV'
            }

            try:
                # Try GET request
                response = requests.get(url, params=params, headers=headers, timeout=3)
                if response.status_code < 400:
                    console.print(f"  [green]✓ GET {endpoint}: {response.status_code}[/green]")
                    if response.headers.get('content-type', '').startswith('application/json'):
                        try:
                            data = response.json()
                            console.print(f"    Response preview: {str(data)[:100]}...")
                        except:
                            pass

                # Try POST request
                response = requests.post(url, json={'query': 'Art. 16 BV'}, headers=headers, timeout=3)
                if response.status_code < 400:
                    console.print(f"  [green]✓ POST {endpoint}: {response.status_code}[/green]")

            except requests.exceptions.RequestException:
                pass


def test_web_interface():
    """Test the web interface search URL pattern"""

    console.print("\n[bold yellow]Testing Web Interface Search Pattern[/bold yellow]")
    console.print("-" * 60)

    # This is the pattern used in their web interface
    search_urls = [
        "https://entscheidsuche.ch/search?q=Art.+16+BV",
        "https://entscheidsuche.ch/docs/search?q=Art.+16+BV",
        "https://entscheidsuche.ch/api/search?q=Art.+16+BV"
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    for url in search_urls:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            console.print(f"\n[bold]URL:[/bold] {url}")
            console.print(f"Status: {response.status_code}")
            console.print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")

            if response.status_code == 200:
                # Check if it's HTML or JSON
                if 'json' in response.headers.get('content-type', ''):
                    data = response.json()
                    console.print(Panel(JSON.from_data(data), title="JSON Response"))
                else:
                    # It's probably HTML - check for results
                    content = response.text
                    if 'BGE' in content or 'Bundesgericht' in content:
                        console.print("[green]✓ Found court decision references in HTML[/green]")
                        # Extract some BGE references
                        import re
                        bge_matches = re.findall(r'BGE\s+\d+\s+[IVX]+\s+\d+', content)[:5]
                        if bge_matches:
                            console.print(f"Sample BGE references: {', '.join(bge_matches)}")
                    else:
                        console.print("[yellow]No court decisions found in response[/yellow]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")


def test_direct_decision_urls():
    """Test direct access to specific decisions"""

    console.print("\n[bold magenta]Testing Direct Decision Access[/bold magenta]")
    console.print("-" * 60)

    # Common BGE decision patterns
    decision_ids = [
        "BGE-148-I-1",
        "BGE_148_I_1",
        "148-I-1",
        "2022/1"
    ]

    url_patterns = [
        "https://entscheidsuche.ch/docs/{id}",
        "https://entscheidsuche.ch/docs/{id}.html",
        "https://entscheidsuche.ch/docs/{id}.json",
        "https://entscheidsuche.ch/decision/{id}",
        "https://entscheidsuche.ch/bge/{id}"
    ]

    headers = {
        'User-Agent': 'LAWAST/1.0',
        'Accept': '*/*'
    }

    for decision_id in decision_ids[:1]:  # Test first pattern
        console.print(f"\n[bold]Testing decision ID: {decision_id}[/bold]")

        for pattern in url_patterns:
            url = pattern.format(id=decision_id)

            try:
                response = requests.head(url, headers=headers, timeout=3, allow_redirects=True)
                if response.status_code < 400:
                    console.print(f"  [green]✓ {url}: {response.status_code}[/green]")

                    # Try to GET the content
                    response = requests.get(url, headers=headers, timeout=3)
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '')
                        console.print(f"    Content-Type: {content_type}")

                        if 'json' in content_type:
                            data = response.json()
                            console.print(f"    JSON keys: {list(data.keys())[:5]}")
                        elif 'html' in content_type:
                            if 'Bundesgericht' in response.text:
                                console.print(f"    [green]Contains court decision content[/green]")

            except requests.exceptions.RequestException:
                pass


def test_elasticsearch_endpoint():
    """Test if there's an Elasticsearch endpoint"""

    console.print("\n[bold red]Testing Elasticsearch-style Endpoints[/bold red]")
    console.print("-" * 60)

    urls = [
        "https://entscheidsuche.ch/_search",
        "https://entscheidsuche.ch/elasticsearch/_search",
        "https://entscheidsuche.ch/es/_search"
    ]

    # Elasticsearch query
    es_query = {
        "query": {
            "match": {
                "content": "Art. 16 BV"
            }
        },
        "size": 1
    }

    headers = {
        'User-Agent': 'LAWAST/1.0',
        'Content-Type': 'application/json'
    }

    for url in urls:
        try:
            response = requests.post(url, json=es_query, headers=headers, timeout=3)
            console.print(f"\n[bold]URL:[/bold] {url}")
            console.print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if 'hits' in data:
                    console.print("[green]✓ Elasticsearch endpoint found![/green]")
                    console.print(Panel(JSON.from_data(data), title="Elasticsearch Response"))

        except Exception as e:
            console.print(f"Error: {str(e)}")


def main():
    """Run all API tests"""

    console.print("\n[bold]Starting entscheidsuche.ch API Discovery[/bold]\n")

    # Test different endpoint patterns
    test_api_endpoints()

    # Test web interface patterns
    test_web_interface()

    # Test direct decision access
    test_direct_decision_urls()

    # Test Elasticsearch endpoints
    test_elasticsearch_endpoint()

    console.print("\n" + "="*80)
    console.print("[bold green]API Discovery Complete![/bold green]")
    console.print("="*80 + "\n")


if __name__ == "__main__":
    main()