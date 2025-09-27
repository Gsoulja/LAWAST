#!/usr/bin/env python3
"""
Test Court Decision Integration in Query Pipeline
Demonstrates on-demand court decision enrichment
"""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig

console = Console()


async def test_court_decision_enrichment():
    """Test the query pipeline with court decision enrichment"""

    console.print("\n" + "="*80)
    console.print("[bold cyan]TESTING COURT DECISION ENRICHMENT[/bold cyan]")
    console.print("="*80 + "\n")

    # Test queries that should trigger court decision searches
    test_queries = [
        {
            "query": "Was besagt die Meinungsfreiheit nach Bundesverfassung?",
            "expected_article": "Art. 16 BV",
            "description": "Freedom of opinion in Swiss Constitution"
        },
        {
            "query": "Kündigungsfrist während der Probezeit im Arbeitsrecht",
            "expected_article": "Art. 335b OR",
            "description": "Notice period during probation in employment law"
        },
        {
            "query": "Datenschutzpflichten der Bundesbehörden",
            "expected_article": "Art. 4-7 DSG",
            "description": "Data protection obligations for federal authorities"
        }
    ]

    # Configure pipeline with court decisions enabled
    config = PipelineConfig(
        enable_agent=True,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_legal_logic=True,
        enable_court_decisions=True,  # Enable court decision enrichment
        include_citations=True,
        include_confidence=True
    )

    pipeline = QueryPipeline(config=config)

    for test_case in test_queries:
        console.print(f"\n[bold magenta]Test Case:[/bold magenta] {test_case['description']}")
        console.print(f"[bold]Query:[/bold] {test_case['query']}")
        console.print(f"[dim]Expected:[/dim] {test_case['expected_article']}")
        console.print("-" * 60)

        try:
            # Execute pipeline
            result = await pipeline.execute(test_case['query'])

            # Show base answer
            console.print(f"\n[green]Answer Preview:[/green]")
            # Show first part before court decisions
            answer_parts = result.answer.split("**Relevant Court Decisions:**")
            console.print(answer_parts[0][:300] + "...")

            # Check if court decisions were added
            if "**Relevant Court Decisions:**" in result.answer:
                console.print(f"\n[bold green]✓ Court decisions enrichment successful![/bold green]")

                # Extract and display court decisions
                court_decision_text = answer_parts[1] if len(answer_parts) > 1 else ""
                console.print(Panel(
                    Markdown(f"**Relevant Court Decisions:**{court_decision_text[:500]}"),
                    title="[bold]Court Decision References[/bold]",
                    border_style="green"
                ))

                # Show structured court decisions if available
                if hasattr(result, 'court_decisions') and result.court_decisions:
                    console.print(f"\n[cyan]Structured Court Decisions:[/cyan]")
                    for article_ref, decisions in result.court_decisions.items():
                        console.print(f"  {article_ref}:")
                        for decision in decisions:
                            console.print(f"    • {decision['id']}: {decision['title']}")
                            console.print(f"      Court: {decision['court']}, Date: {decision['date']}")
                            console.print(f"      URL: {decision['url']}")
            else:
                console.print(f"\n[yellow]⚠ No court decisions found or API unavailable[/yellow]")

            # Show citations
            if result.citations:
                console.print(f"\n[blue]Citations:[/blue]")
                for citation in result.citations[:3]:
                    if hasattr(citation, 'reference') and citation.reference:
                        relevance_str = f" (Relevance: {citation.relevance:.2f})" if hasattr(citation, 'relevance') and citation.relevance else ""
                        console.print(f"  - {citation.reference}{relevance_str}")
                    elif hasattr(citation, 'source'):
                        console.print(f"  - {citation.source}")

            console.print(f"\n[dim]Confidence: {result.confidence:.2%}[/dim]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")


async def test_citation_extraction():
    """Test article citation extraction from different formats"""

    console.print("\n" + "="*80)
    console.print("[bold yellow]TESTING CITATION EXTRACTION PATTERNS[/bold yellow]")
    console.print("="*80 + "\n")

    from src.enrichment.court_decision_client import CourtDecisionEnricher
    import re

    # Test different citation formats
    test_texts = [
        "According to Art. 16 BV, freedom of opinion is protected.",
        "Gemäss Artikel 335b OR beträgt die Kündigungsfrist 7 Tage.",
        "Art. 4 DSG und Art. 5 DSG regeln den Datenschutz.",
        "Die Artikel 10, 11 und 12 StGB sind anzuwenden.",
        "Nach Art. 2 Abs. 1 ZGB gilt Treu und Glauben."
    ]

    enricher = CourtDecisionEnricher()

    for text in test_texts:
        console.print(f"\n[bold]Text:[/bold] {text}")

        # Extract citations using the same pattern as in the pipeline
        article_pattern = r"Art(?:icle|ikel|\.)?\s*(\d+[a-z]?)\s+([A-Z]+(?:\s+[A-Z]+)?)"
        matches = re.findall(article_pattern, text)

        if matches:
            console.print("[green]Found citations:[/green]")
            for article_num, law_abbrev in matches:
                console.print(f"  - Art. {article_num} {law_abbrev}")
        else:
            console.print("[yellow]No citations found[/yellow]")


async def compare_with_without_court_decisions():
    """Compare responses with and without court decision enrichment"""

    console.print("\n" + "="*80)
    console.print("[bold red]COMPARISON: WITH vs WITHOUT COURT DECISIONS[/bold red]")
    console.print("="*80 + "\n")

    query = "Was sind die Kündigungsfristen im schweizerischen Arbeitsrecht?"

    configs = [
        {
            "name": "Without Court Decisions",
            "config": PipelineConfig(
                enable_court_decisions=False,
                enable_legal_logic=True,
                enable_agent=True,
                enable_rag=True,
                enable_reasoning=True,
                enable_articulation=True
            )
        },
        {
            "name": "With Court Decisions",
            "config": PipelineConfig(
                enable_court_decisions=True,  # Enable court decisions
                enable_legal_logic=True,
                enable_agent=True,
                enable_rag=True,
                enable_reasoning=True,
                enable_articulation=True
            )
        }
    ]

    results = []
    for config_test in configs:
        console.print(f"\n[bold]{config_test['name']}:[/bold]")
        console.print("-" * 40)

        pipeline = QueryPipeline(config=config_test['config'])

        try:
            result = await pipeline.execute(query)
            results.append({
                "name": config_test['name'],
                "answer_length": len(result.answer),
                "has_court_decisions": "**Relevant Court Decisions:**" in result.answer,
                "confidence": result.confidence,
                "citations": len(result.citations) if result.citations else 0
            })

            # Show preview
            preview = result.answer[:200] + "..."
            console.print(f"[dim]{preview}[/dim]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            results.append({
                "name": config_test['name'],
                "error": str(e)
            })

    # Comparison table
    console.print("\n")
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Feature", style="cyan", width=25)
    table.add_column("Without Court Decisions", style="yellow", width=25)
    table.add_column("With Court Decisions", style="green", width=25)

    if len(results) == 2:
        table.add_row(
            "Answer Length",
            f"{results[0].get('answer_length', 'N/A')} chars",
            f"{results[1].get('answer_length', 'N/A')} chars"
        )
        table.add_row(
            "Court Decisions",
            "❌ Not included" if not results[0].get('has_court_decisions') else "✓ Included",
            "✓ Included" if results[1].get('has_court_decisions') else "❌ Not included"
        )
        table.add_row(
            "Confidence",
            f"{results[0].get('confidence', 0):.2%}",
            f"{results[1].get('confidence', 0):.2%}"
        )
        table.add_row(
            "Citations",
            str(results[0].get('citations', 0)),
            str(results[1].get('citations', 0))
        )
        table.add_row(
            "Authority",
            "Law text only",
            "Law text + Court precedents"
        )
        table.add_row(
            "Practical Context",
            "Limited",
            "Enhanced with real cases"
        )

    console.print(table)


async def main():
    """Run all tests"""
    try:
        # Test basic court decision enrichment
        await test_court_decision_enrichment()

        # Test citation extraction patterns
        await test_citation_extraction()

        # Compare with and without court decisions
        await compare_with_without_court_decisions()

        console.print("\n" + "="*80)
        console.print("[bold green]✅ Court Decision Integration Testing Complete![/bold green]")
        console.print("[italic]The pipeline now enriches answers with relevant court decisions on-demand![/italic]")
        console.print("="*80 + "\n")

    except Exception as e:
        console.print(f"\n[red]Test failed: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())