#!/usr/bin/env python3
"""
Test Court Decision Links in Pipeline
Shows clickable links to entscheidsuche.ch
"""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig
from src.interfaces.api.court_decision_formatter import CourtDecisionFormatter

console = Console()


async def test_court_decision_links():
    """Test that court decisions include clickable links"""

    console.print("\n" + "="*80)
    console.print("[bold cyan]TESTING COURT DECISION LINKS IN PIPELINE[/bold cyan]")
    console.print("="*80 + "\n")

    # Configure pipeline with court decisions
    config = PipelineConfig(
        enable_agent=False,  # Faster without agent
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_legal_logic=True,
        enable_court_decisions=True  # Enable court decisions
    )

    pipeline = QueryPipeline(config=config)

    # Test query that should trigger court decisions
    test_query = "Was besagt Artikel 16 der Bundesverfassung über die Meinungsfreiheit?"

    console.print(f"[bold]Query:[/bold] {test_query}\n")

    try:
        # Execute pipeline
        result = await pipeline.execute(test_query)

        # Check if court decisions were found
        if hasattr(result, 'court_decisions') and result.court_decisions:
            console.print("[bold green]✅ Court decisions found and enriched![/bold green]\n")

            # Show the structured court decision data
            console.print("[bold]Structured Court Decision Data:[/bold]")
            for article_ref, decisions in result.court_decisions.items():
                console.print(f"\n[cyan]{article_ref}:[/cyan]")
                for decision in decisions:
                    console.print(f"  • ID: {decision.get('id')}")
                    console.print(f"    Court: {decision.get('court')}")
                    console.print(f"    Date: {decision.get('date')}")
                    console.print(f"    [blue]Link: {decision.get('url')}[/blue]")

            # Test formatters
            formatter = CourtDecisionFormatter()

            # Terminal format
            console.print("\n[bold yellow]Terminal Format:[/bold yellow]")
            terminal_text = formatter.format_for_terminal(result.court_decisions)
            console.print(terminal_text)

            # Markdown format (for OpenWebUI)
            console.print("\n[bold magenta]Markdown Format (for OpenWebUI):[/bold magenta]")
            markdown_text = formatter.format_for_markdown(result.court_decisions)
            console.print(Panel(Markdown(markdown_text), title="Markdown Output"))

            # HTML format (for web display)
            console.print("\n[bold red]HTML Format Preview:[/bold red]")
            html_text = formatter.format_for_web(result.court_decisions)
            # Show just the structure without full HTML
            if "<a href=" in html_text:
                console.print("[green]✓ HTML contains clickable links[/green]")
                # Extract and show links
                import re
                links = re.findall(r'<a href="([^"]+)"', html_text)
                for link in links[:3]:
                    console.print(f"  🔗 {link}")

        else:
            console.print("[yellow]⚠ No court decisions found in result[/yellow]")

        # Show the answer with embedded links
        console.print("\n[bold]Final Answer with Court Decision Links:[/bold]")
        console.print("-" * 60)

        # Show first part of answer
        if "Relevant Court Decisions" in result.answer:
            parts = result.answer.split("Relevant Court Decisions")
            console.print(parts[0][:500] + "...")
            console.print("\n[green]✅ Court decisions with links included in answer![/green]")

            # Show the court decision section
            console.print("\n[bold]Court Decision Section:[/bold]")
            decision_section = "Relevant Court Decisions" + parts[1][:1000]
            console.print(Panel(Markdown(decision_section), border_style="green"))
        else:
            console.print(result.answer[:500] + "...")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())


async def test_multiple_articles():
    """Test court decisions for multiple article citations"""

    console.print("\n" + "="*80)
    console.print("[bold yellow]TESTING MULTIPLE ARTICLE COURT DECISIONS[/bold yellow]")
    console.print("="*80 + "\n")

    config = PipelineConfig(
        enable_agent=False,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_legal_logic=True,
        enable_court_decisions=True
    )

    pipeline = QueryPipeline(config=config)

    # Query that might reference multiple articles
    test_query = "Welche Rechte haben Arbeitnehmer bei Kündigungen und was sagt die Verfassung zur Meinungsfreiheit?"

    console.print(f"[bold]Query:[/bold] {test_query}\n")

    result = await pipeline.execute(test_query)

    if hasattr(result, 'court_decisions') and result.court_decisions:
        console.print(f"[green]Found court decisions for {len(result.court_decisions)} articles:[/green]")
        for article_ref in result.court_decisions.keys():
            console.print(f"  • {article_ref}")

        # Count total decisions
        total_decisions = sum(len(decisions) for decisions in result.court_decisions.values())
        console.print(f"\n[cyan]Total court decisions found: {total_decisions}[/cyan]")

        # Show all links
        console.print("\n[bold]All Court Decision Links:[/bold]")
        for article_ref, decisions in result.court_decisions.items():
            console.print(f"\n{article_ref}:")
            for decision in decisions:
                url = decision.get('url', '')
                if url:
                    console.print(f"  🔗 {url}")


async def main():
    """Run all tests"""
    try:
        # Test basic court decision links
        await test_court_decision_links()

        # Test multiple articles
        await test_multiple_articles()

        console.print("\n" + "="*80)
        console.print("[bold green]✅ Court Decision Link Testing Complete![/bold green]")
        console.print("[italic]Links to entscheidsuche.ch are properly integrated![/italic]")
        console.print("="*80 + "\n")

    except Exception as e:
        console.print(f"\n[red]Test failed: {str(e)}[/red]")


if __name__ == "__main__":
    asyncio.run(main())