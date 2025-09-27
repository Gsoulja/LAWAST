#!/usr/bin/env python3
"""
Test fixed court decision enrichment
"""

import asyncio
from rich.console import Console
from rich.panel import Panel

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig

console = Console()


async def test_court_decision_parsing():
    """Test that court decisions are correctly parsed and displayed"""

    console.print("\n" + "="*80)
    console.print("[bold cyan]TESTING FIXED COURT DECISION PARSING[/bold cyan]")
    console.print("="*80 + "\n")

    config = PipelineConfig(
        enable_agent=False,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_legal_logic=True,
        enable_court_decisions=True  # Enable court decisions
    )

    pipeline = QueryPipeline(config=config)

    # Test queries
    test_queries = [
        "Was regelt Artikel 114 der Bundesverfassung?",
        "Welche Rechte gewährt die Meinungsfreiheit nach Artikel 16 BV?",
        "Was besagt das Petitionsrecht in der Bundesverfassung?"
    ]

    for query in test_queries:
        console.print(f"\n[bold magenta]Query:[/bold magenta] {query}")
        console.print("-" * 60)

        result = await pipeline.execute(query)

        # Show citations
        if result.citations:
            console.print(f"\n[cyan]Citations:[/cyan]")
            for citation in result.citations:
                citation_str = str(citation)
                console.print(f"  • {citation_str}")

        # Check court decisions
        if hasattr(result, 'court_decisions') and result.court_decisions:
            console.print(f"\n[green]Court Decisions Found:[/green]")
            for article_ref, decisions in result.court_decisions.items():
                console.print(f"\n  [bold]{article_ref}:[/bold]")
                for decision in decisions[:2]:
                    if decision.get('id'):  # Only show if decision has an ID
                        console.print(f"    • {decision.get('id')} - {decision.get('court', 'N/A')}")
                        console.print(f"      Date: {decision.get('date', 'N/A')}")
                        if decision.get('url'):
                            console.print(f"      [blue]URL: {decision.get('url')}[/blue]")
                    else:
                        console.print(f"    [red]• Empty decision entry[/red]")

            # Check for issues
            issues = []
            for article_ref in result.court_decisions.keys():
                # Check if BV articles are labeled correctly
                if "Art." in article_ref and "BV" not in article_ref and any(num in article_ref for num in ['114', '16', '33']):
                    issues.append(f"Missing BV in: {article_ref}")
                # Check for wrong law abbreviations
                if "OR" in article_ref and any(num in article_ref for num in ['114', '16', '33']):
                    issues.append(f"Wrong law (should be BV): {article_ref}")

            if issues:
                console.print(Panel(
                    "\n".join(issues),
                    title="[red]Issues Found[/red]",
                    border_style="red"
                ))
            else:
                console.print(Panel(
                    "[green]✅ Court decisions correctly labeled with BV![/green]",
                    border_style="green"
                ))
        else:
            console.print("[yellow]No court decisions found[/yellow]")

        # Show confidence
        console.print(f"\n[dim]Confidence: {result.confidence:.2%}[/dim]")


async def main():
    """Run tests"""
    try:
        await test_court_decision_parsing()

        console.print("\n" + "="*80)
        console.print("[bold green]✅ Court Decision Testing Complete![/bold green]")
        console.print("="*80 + "\n")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())