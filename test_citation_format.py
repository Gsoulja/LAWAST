#!/usr/bin/env python3
"""
Test that citations include law abbreviation (BV)
"""

import asyncio
from rich.console import Console
from rich.panel import Panel

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig
from src.reasoning.citation_tracker import CitationTracker
from src.reasoning.models import Citation

console = Console()


def test_citation_formatting():
    """Test that Citation objects format correctly with BV"""

    console.print("\n[bold cyan]Testing Citation Formatting[/bold cyan]\n")

    # Test different citation scenarios
    test_cases = [
        {
            "name": "Citation with SR 101 and article",
            "citation": Citation(sr_number="101", article="16"),
            "expected": "Art. 16 BV"
        },
        {
            "name": "Citation with SR 101, article and paragraph",
            "citation": Citation(sr_number="101", article="16", paragraph="2"),
            "expected": "Art. 16 Abs. 2 BV"
        },
        {
            "name": "Citation with article and BV abbreviation",
            "citation": Citation(article="16", law_abbreviation="BV"),
            "expected": "Art. 16 BV"
        },
        {
            "name": "Citation with only article (defaults to BV)",
            "citation": Citation(article="16"),
            "expected": "Art. 16 BV"
        }
    ]

    for test in test_cases:
        result = str(test["citation"])
        status = "✅" if result == test["expected"] else "❌"
        console.print(f"{status} {test['name']}")
        console.print(f"   Expected: [green]{test['expected']}[/green]")
        console.print(f"   Got: [{'green' if result == test['expected'] else 'red'}]{result}[/]")
        console.print()


def test_citation_tracker():
    """Test that CitationTracker properly adds BV"""

    console.print("\n[bold yellow]Testing Citation Tracker[/bold yellow]\n")

    tracker = CitationTracker()

    # Test law abbreviation mapping
    console.print("Law abbreviation mappings:")
    test_sr_numbers = ["101", "220", "235.1", "311.0"]
    for sr in test_sr_numbers:
        abbrev = tracker.get_law_abbreviation(sr)
        console.print(f"  SR {sr} → {abbrev}")

    # Test parsing citations
    console.print("\nParsing citations from titles:")
    test_titles = [
        "Art. 16 Meinungs- und Informationsfreiheit",
        "Art. 16 BV",
        "Art. 335b OR",
        "SR 101 Art. 16"
    ]

    for title in test_titles:
        citation = tracker._parse_title_citation(title)
        if citation:
            console.print(f"  '{title}' → {str(citation)}")


async def test_pipeline_citations():
    """Test that the pipeline produces citations with BV"""

    console.print("\n[bold magenta]Testing Pipeline Citations[/bold magenta]\n")

    config = PipelineConfig(
        enable_agent=False,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_legal_logic=True,
        enable_court_decisions=False  # Disable to focus on citations
    )

    pipeline = QueryPipeline(config=config)

    # Test query about BV article
    query = "Was besagt Artikel 16 der Bundesverfassung?"

    console.print(f"Query: {query}")
    result = await pipeline.execute(query)

    if result.citations:
        console.print(f"\n[green]Citations found:[/green]")
        for i, citation in enumerate(result.citations, 1):
            citation_str = str(citation)
            has_bv = "BV" in citation_str
            status = "✅" if has_bv else "⚠️"
            console.print(f"  {i}. {status} {citation_str}")

        # Check if any citation has BV
        if any("BV" in str(c) for c in result.citations):
            console.print(Panel("[bold green]✅ Citations correctly include 'BV' abbreviation![/bold green]",
                              border_style="green"))
        else:
            console.print(Panel("[bold yellow]⚠️ Citations missing 'BV' abbreviation[/bold yellow]",
                              border_style="yellow"))
    else:
        console.print("[red]No citations found[/red]")

    # Also check the answer text
    console.print(f"\nChecking answer text for proper citations:")
    if "Art. 16 BV" in result.answer or "Artikel 16 BV" in result.answer:
        console.print("[green]✅ Answer contains 'Art. 16 BV'[/green]")
    elif "Art. 16" in result.answer:
        console.print("[yellow]⚠️ Answer contains 'Art. 16' without 'BV'[/yellow]")


async def main():
    """Run all tests"""

    console.print("\n" + "="*70)
    console.print("[bold]TESTING CITATION FORMAT WITH LAW ABBREVIATION (BV)[/bold]")
    console.print("="*70)

    # Test citation formatting
    test_citation_formatting()

    # Test citation tracker
    test_citation_tracker()

    # Test pipeline
    await test_pipeline_citations()

    console.print("\n" + "="*70)
    console.print("[bold green]Citation Format Testing Complete![/bold green]")
    console.print("Citations should now show 'Art. X BV' instead of just 'Art. X'")
    console.print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())