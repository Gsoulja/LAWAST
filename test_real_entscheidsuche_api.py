#!/usr/bin/env python3
"""
Test real EntscheidSuche.ch API calls
"""

import requests
import json
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from rich.table import Table

console = Console()


def test_real_api_search():
    """Test the real Elasticsearch search API"""

    console.print("\n" + "="*80)
    console.print("[bold cyan]TESTING REAL ENTSCHEIDSUCHE.CH API[/bold cyan]")
    console.print("="*80 + "\n")

    # Test queries for Swiss law articles
    test_queries = [
        {
            "description": "Meinungsfreiheit (Art. 16 BV)",
            "query": "Art. 16 BV Meinungsfreiheit"
        },
        {
            "description": "Kündigungsfrist Probezeit (Art. 335b OR)",
            "query": "Art. 335b OR Kündigungsfrist Probezeit"
        },
        {
            "description": "Datenschutz",
            "query": "Datenschutz Bundesbehörden DSG"
        }
    ]

    for test in test_queries:
        console.print(f"\n[bold magenta]{test['description']}[/bold magenta]")
        console.print(f"Query: {test['query']}")
        console.print("-" * 60)

        # Construct Elasticsearch query
        es_query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "content": test['query']
                            }
                        }
                    ],
                    "filter": [
                        {
                            "terms": {
                                "spider": ["CH_BGer", "CH_BGE", "CH_BVGer"]  # Federal courts
                            }
                        }
                    ]
                }
            },
            "size": 3,
            "_source": ["signatur", "datum", "num", "kopfzeile_de", "abstract_de", "spider", "pdf_url", "html_url"],
            "highlight": {
                "fields": {
                    "content": {
                        "fragment_size": 150,
                        "number_of_fragments": 1
                    }
                }
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {"datum": {"order": "desc"}}
            ]
        }

        try:
            # Send request to documented endpoint
            response = requests.post(
                "https://entscheidsuche.ch/_search.php",
                json=es_query,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            console.print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # Check if we got results
                total_hits = data.get('hits', {}).get('total', {})
                if isinstance(total_hits, dict):
                    total = total_hits.get('value', 0)
                else:
                    total = total_hits

                console.print(f"[green]✓ Found {total} results[/green]\n")

                # Display results in a table
                if data.get('hits', {}).get('hits'):
                    table = Table(show_header=True, header_style="bold blue")
                    table.add_column("ID", style="cyan", width=20)
                    table.add_column("Date", style="yellow", width=12)
                    table.add_column("Title", style="white", width=40)
                    table.add_column("Score", style="green", width=8)

                    for hit in data['hits']['hits'][:3]:
                        source = hit['_source']
                        table.add_row(
                            source.get('num', source.get('signatur', 'N/A'))[:20],
                            source.get('datum', 'N/A')[:12],
                            source.get('kopfzeile_de', source.get('abstract_de', 'N/A'))[:40],
                            f"{hit.get('_score', 0):.2f}"
                        )

                    console.print(table)

                    # Show first result details
                    first_hit = data['hits']['hits'][0]
                    source = first_hit['_source']
                    highlights = first_hit.get('highlight', {}).get('content', [])

                    console.print("\n[bold]First Result Details:[/bold]")
                    details_panel = f"""
**Signatur:** {source.get('signatur', 'N/A')}
**Case Number:** {source.get('num', 'N/A')}
**Date:** {source.get('datum', 'N/A')}
**Spider:** {source.get('spider', 'N/A')}
**Title:** {source.get('kopfzeile_de', 'N/A')[:100]}...

**Excerpt:** {highlights[0][:200] if highlights else source.get('abstract_de', 'No excerpt')[:200]}...

**PDF:** {source.get('pdf_url', 'N/A')}
**HTML:** {source.get('html_url', 'N/A')}
"""
                    console.print(Panel(details_panel, title="Court Decision", border_style="green"))

                else:
                    console.print("[yellow]No results found[/yellow]")

            else:
                console.print(f"[red]Error: {response.status_code}[/red]")
                console.print(response.text[:500])

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")


def test_direct_api_with_client():
    """Test using our client with real API"""

    console.print("\n" + "="*80)
    console.print("[bold yellow]TESTING WITH OUR CLIENT[/bold yellow]")
    console.print("="*80 + "\n")

    from src.enrichment.court_decision_client import EntscheidSucheClient

    client = EntscheidSucheClient()

    # Test searches
    test_cases = [
        ("16", "BV", "Meinungsfreiheit"),
        ("335b", "OR", "Kündigungsfrist"),
        ("4", "DSG", "Datenschutz")
    ]

    for article, law, description in test_cases:
        console.print(f"\n[bold]{description} - Art. {article} {law}[/bold]")
        console.print("-" * 40)

        decisions = client.search_by_article(article, law, limit=3)

        if decisions:
            for i, decision in enumerate(decisions, 1):
                console.print(f"\n{i}. [cyan]{decision.decision_id}[/cyan]")
                console.print(f"   Court: {decision.court}")
                console.print(f"   Date: {decision.date}")
                console.print(f"   Title: {decision.title[:80]}...")
                console.print(f"   Score: {decision.relevance_score:.2f}")
                if decision.excerpt:
                    console.print(f"   Excerpt: {decision.excerpt[:150]}...")
                console.print(f"   URL: {decision.url}")
        else:
            console.print("[yellow]No decisions found[/yellow]")


def test_alternative_endpoint():
    """Test the alternative direct Elasticsearch endpoint"""

    console.print("\n" + "="*80)
    console.print("[bold red]TESTING ALTERNATIVE ELASTICSEARCH ENDPOINT[/bold red]")
    console.print("="*80 + "\n")

    # Try the direct Elasticsearch endpoint mentioned in docs
    es_query = {
        "query": {
            "match": {
                "content": "Art. 16 BV"
            }
        },
        "size": 1
    }

    try:
        response = requests.post(
            "https://entscheidsuche.pansoft.de:9200/entscheidsuche-*/_search",
            json=es_query,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        console.print(f"Direct ES endpoint status: {response.status_code}")
        if response.status_code == 200:
            console.print("[green]✓ Direct Elasticsearch endpoint accessible[/green]")
            data = response.json()
            console.print(f"Total hits: {data.get('hits', {}).get('total', 0)}")
        else:
            console.print("[yellow]Direct endpoint not accessible[/yellow]")

    except Exception as e:
        console.print(f"[yellow]Direct endpoint error: {str(e)}[/yellow]")


def main():
    """Run all tests"""

    # Test real API search
    test_real_api_search()

    # Test with our client
    test_direct_api_with_client()

    # Test alternative endpoint
    test_alternative_endpoint()

    console.print("\n" + "="*80)
    console.print("[bold green]✅ Real API Testing Complete![/bold green]")
    console.print("="*80 + "\n")


if __name__ == "__main__":
    main()