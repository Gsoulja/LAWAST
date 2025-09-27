#!/usr/bin/env python3
"""
Debug why Article 114 is always being returned
"""

import asyncio
from rich.console import Console
from rich.panel import Panel

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig

console = Console()


async def test_different_queries():
    """Test multiple queries to see if they all return Article 114"""

    queries = [
        "Entstehen mir Nachteile wenn ich eine Petition einreiche?",  # Should be Art. 33
        "Was regelt die Meinungsfreiheit?",  # Should be Art. 16
        "Welche Rechte haben Kinder?",  # Should be Art. 11
        "Was ist das Diskriminierungsverbot?",  # Should be Art. 8
    ]

    config = PipelineConfig(
        enable_agent=False,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_legal_logic=True,
        enable_court_decisions=False  # Disable to focus on article issue
    )

    pipeline = QueryPipeline(config=config)

    console.print("\n" + "="*80)
    console.print("[bold red]DEBUGGING: Article 114 Hardcoding Issue[/bold red]")
    console.print("="*80)

    for query in queries:
        console.print(f"\n[bold cyan]Query:[/bold cyan] {query}")
        console.print("-"*60)

        result = await pipeline.execute(query)

        # Check what article is in the answer
        answer_start = result.answer[:100]
        console.print(f"[yellow]Answer start:[/yellow] {answer_start}")

        # Check citations
        if result.citations:
            console.print(f"[green]Citations:[/green]")
            for citation in result.citations[:3]:
                console.print(f"  • {citation}")

        # Highlight if Article 114 appears
        if "114" in result.answer:
            console.print(Panel(
                "[red]⚠️  Article 114 found in answer![/red]",
                border_style="red"
            ))
        else:
            console.print("[green]✓ No Article 114 in answer[/green]")

        # Check what the top RAG result was
        if hasattr(result, 'rag_results') and result.rag_results:
            console.print(f"\n[dim]Top RAG result: {result.rag_results[0].title if result.rag_results else 'N/A'}[/dim]")


async def check_rag_directly():
    """Check RAG retrieval directly"""

    console.print("\n" + "="*80)
    console.print("[bold yellow]Checking RAG Retrieval Directly[/bold yellow]")
    console.print("="*80)

    from src.rag.enhanced_triple_rag import EnhancedTripleRAG
    from src.data_access.neo4j_connection import Neo4jConnectionManager

    connection = Neo4jConnectionManager()
    rag = EnhancedTripleRAG(connection)

    query = "Entstehen mir Nachteile wenn ich eine Petition einreiche?"
    console.print(f"\n[cyan]Query:[/cyan] {query}")

    # Test retrieval
    results, metrics = rag.search(query, limit=5)

    console.print(f"\n[green]Top 5 RAG Results:[/green]")
    for i, result in enumerate(results, 1):
        title = result.title
        score = result.combined_score if hasattr(result, 'combined_score') else result.score

        # Highlight Article 114 and Article 33
        if "114" in title:
            console.print(f"  {i}. [red]{title}[/red] (Score: {score:.3f}) ⚠️")
        elif "33" in title or "Petition" in title:
            console.print(f"  {i}. [green]{title}[/green] (Score: {score:.3f}) ✓")
        else:
            console.print(f"  {i}. {title} (Score: {score:.3f})")


async def check_articulation_prompt():
    """Check if the articulation prompt is hardcoded"""

    console.print("\n" + "="*80)
    console.print("[bold magenta]Checking Articulation Context[/bold magenta]")
    console.print("="*80)

    from src.pipeline.query_pipeline import QueryPipeline

    pipeline = QueryPipeline()

    # Create mock RAG results
    class MockResult:
        def __init__(self, title, content):
            self.title = title
            self.content = content
            self.combined_score = 0.9

    mock_results = [
        MockResult("Art. 33 Petitionsrecht", "Jede Person hat das Recht, Petitionen an Behörden zu richten; es dürfen ihr daraus keine Nachteile erwachsen."),
        MockResult("Art. 16 Meinungsfreiheit", "Die Meinungs- und Informationsfreiheit ist gewährleistet."),
        MockResult("Art. 8 Rechtsgleichheit", "Alle Menschen sind vor dem Gesetz gleich.")
    ]

    query = "Entstehen mir Nachteile wenn ich eine Petition einreiche?"
    context = pipeline._prepare_articulation_context(query, mock_results)

    console.print("[yellow]Generated articulation context:[/yellow]")
    console.print(context)

    # Check if 114 is hardcoded in context
    if "114" in context:
        console.print(Panel(
            "[red]⚠️  Article 114 found in articulation context![/red]",
            border_style="red"
        ))
    else:
        console.print("[green]✓ No Article 114 in articulation context[/green]")


async def main():
    """Run all debugging tests"""

    try:
        # Test different queries
        await test_different_queries()

        # Check RAG directly
        await check_rag_directly()

        # Check articulation prompt
        await check_articulation_prompt()

        console.print("\n" + "="*80)
        console.print("[bold green]Debugging Complete[/bold green]")
        console.print("="*80 + "\n")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())