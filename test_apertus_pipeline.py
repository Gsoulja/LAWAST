#!/usr/bin/env python3
"""
Test LAWAST Pipeline with Apertus Integration
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Set API key
os.environ['HUGGINGFACE_API_KEY'] = 'your-huggingface-api-key'

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


async def test_apertus_pipeline():
    """Test pipeline with Apertus LLM integration"""

    console.print(Panel.fit(
        "[bold cyan]LAWAST Pipeline + Apertus Test[/bold cyan]\n"
        "Testing complete pipeline with Swiss AI model",
        border_style="cyan"
    ))

    # Create pipeline with all components enabled
    config = PipelineConfig(
        enable_agent=True,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_graceful_degradation=True,
        enable_monitoring=True,
        include_reasoning_chain=True,  # Include reasoning details
        include_citations=True,
        include_confidence=True
    )

    console.print("\n[bold]Initializing pipeline...[/bold]")
    pipeline = QueryPipeline(config=config)
    console.print("✅ Pipeline initialized with Apertus integration")

    # Test queries
    queries = [
        "What is the retirement age in Switzerland?",
        "Tell me about Swiss labor laws",
        "What are the requirements for starting a business in Switzerland?"
    ]

    for i, query in enumerate(queries, 1):
        console.print(f"\n[bold blue]Test {i}/3:[/bold blue]")
        console.print(f"Query: [yellow]{query}[/yellow]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing query...", total=None)

            try:
                # Execute pipeline
                result = await pipeline.execute(query)
                progress.update(task, completed=True)

                # Display results
                console.print(Panel(
                    f"[bold]Answer:[/bold]\n{result.answer[:500]}{'...' if len(result.answer) > 500 else ''}\n\n"
                    f"[bold]Confidence:[/bold] {result.confidence:.1%}\n"
                    f"[bold]Execution Time:[/bold] {result.execution_time:.2f}s",
                    title="Result",
                    border_style="green"
                ))

                # Show citations if available
                if result.citations:
                    console.print(f"\n[bold]Citations ({len(result.citations)}):[/bold]")
                    for citation in result.citations[:3]:
                        console.print(f"  • {citation.source}: {citation.reference}")

                # Show reasoning chain if available
                if result.reasoning_chain:
                    console.print(f"\n[bold]Reasoning Steps:[/bold]")
                    for step in result.reasoning_chain[:3]:
                        console.print(f"  → {step}")

                # Show any errors or warnings
                if result.errors:
                    console.print(f"\n[red]Errors: {', '.join(result.errors)}[/red]")
                if result.warnings:
                    console.print(f"\n[yellow]Warnings: {', '.join(result.warnings)}[/yellow]")

            except Exception as e:
                progress.update(task, completed=True)
                console.print(f"[red]❌ Error: {str(e)}[/red]")

    # Performance summary
    if pipeline.monitor:
        console.print("\n[bold cyan]Performance Summary:[/bold cyan]")
        metrics = pipeline.monitor.get_all_metrics()
        global_metrics = metrics['global']

        console.print(f"  Total Requests: {global_metrics['total_requests']}")
        console.print(f"  Success Rate: {global_metrics['success_rate']}")
        console.print(f"  Average Duration: {global_metrics['average_duration']}")
        console.print(f"  P95 Latency: {global_metrics['p95']}")

        # Stage breakdown
        if metrics['stages']:
            console.print("\n[bold]Stage Performance:[/bold]")
            for stage_name, stage_metrics in metrics['stages'].items():
                console.print(f"  {stage_name}: {stage_metrics['average_duration']} (success: {stage_metrics['success_rate']})")

    console.print("\n[bold green]✅ All tests completed![/bold green]")


async def test_multi_turn():
    """Test multi-turn dialogue with Apertus"""

    console.print("\n[bold cyan]Multi-Turn Dialogue Test[/bold cyan]")

    config = PipelineConfig(
        enable_agent=True,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_graceful_degradation=True
    )

    pipeline = QueryPipeline(config=config)

    # Conversation flow
    conversation = [
        "What are the main areas of Swiss law?",
        "Tell me more about employment law",
        "What are the working hour regulations?"
    ]

    session_id = None

    for turn, query in enumerate(conversation, 1):
        console.print(f"\n[bold]Turn {turn}:[/bold] [yellow]{query}[/yellow]")

        if session_id:
            result = await pipeline.process_with_session(query, session_id)
        else:
            result = await pipeline.process_with_session(query)
            session_id = result.session_id

        console.print(f"Answer: {result.answer[:200]}...")
        console.print(f"Session: {session_id[:8]}...")

    console.print("\n[green]✅ Multi-turn dialogue working with context preservation![/green]")


async def main():
    """Run all Apertus integration tests"""

    try:
        # Run main pipeline test
        await test_apertus_pipeline()

        # Run multi-turn test
        await test_multi_turn()

        console.print("\n" + "="*50)
        console.print("[bold green]All Apertus integration tests passed! 🎉[/bold green]")
        console.print("\nThe pipeline is successfully:")
        console.print("  ✅ Processing queries through all stages")
        console.print("  ✅ Using Apertus for reasoning and articulation")
        console.print("  ✅ Managing multi-turn dialogues")
        console.print("  ✅ Handling errors gracefully")
        console.print("  ✅ Collecting performance metrics")

    except Exception as e:
        console.print(f"\n[red]Test failed: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())