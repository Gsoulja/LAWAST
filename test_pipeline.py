#!/usr/bin/env python3
"""
Test script for LAWAST Query Pipeline
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

console = Console()


async def test_basic_pipeline():
    """Test basic pipeline functionality"""
    console.print("\n[bold blue]Testing Basic Pipeline Setup[/bold blue]")
    console.print("-" * 50)

    try:
        # Create pipeline with minimal config
        config = PipelineConfig(
            enable_agent=False,  # Start simple without agent
            enable_rag=False,     # No RAG for basic test
            enable_reasoning=False,  # No reasoning
            enable_articulation=False,  # No articulation
            enable_monitoring=True
        )

        pipeline = QueryPipeline(config=config)
        console.print("✅ Pipeline created successfully")

        # Test health check
        health = await pipeline.health_check()
        console.print(f"✅ Health check: {health['status']}")

        # Show component status
        table = Table(title="Component Status")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")

        for component, status in health['components'].items():
            table.add_row(component, status['status'])

        console.print(table)

        return True

    except Exception as e:
        console.print(f"❌ Basic test failed: {str(e)}", style="red")
        return False


async def test_simple_query():
    """Test with a simple query (no external dependencies)"""
    console.print("\n[bold blue]Testing Simple Query Processing[/bold blue]")
    console.print("-" * 50)

    try:
        # Create pipeline with graceful degradation
        config = PipelineConfig(
            enable_agent=True,
            enable_rag=True,
            enable_reasoning=True,
            enable_articulation=True,
            enable_graceful_degradation=True,
            enable_monitoring=True
        )

        pipeline = QueryPipeline(config=config)

        # Test query
        query = "What is the retirement age in Switzerland?"
        console.print(f"Query: [yellow]{query}[/yellow]")

        # Execute pipeline
        result = await pipeline.execute(query)

        # Display results
        console.print("\n[bold green]Pipeline Result:[/bold green]")

        panel_content = f"""
[bold]Answer:[/bold] {result.answer[:200]}{'...' if len(result.answer) > 200 else ''}

[bold]Confidence:[/bold] {result.confidence:.2%}
[bold]Execution Time:[/bold] {result.execution_time:.2f}s
[bold]Trace ID:[/bold] {result.trace_id[:8]}...
        """

        if result.errors:
            panel_content += f"\n[bold red]Errors:[/bold red] {', '.join(result.errors)}"
        if result.warnings:
            panel_content += f"\n[bold yellow]Warnings:[/bold yellow] {', '.join(result.warnings)}"

        console.print(Panel(panel_content, title="Query Result", border_style="green"))

        # Show metrics if available
        if result.metrics:
            console.print("\n[bold]Performance Metrics:[/bold]")
            for key, value in result.metrics.items():
                console.print(f"  {key}: {value}")

        return True

    except Exception as e:
        console.print(f"❌ Query test failed: {str(e)}", style="red")
        import traceback
        console.print(traceback.format_exc(), style="dim")
        return False


async def test_multi_turn_dialogue():
    """Test multi-turn dialogue with session management"""
    console.print("\n[bold blue]Testing Multi-Turn Dialogue[/bold blue]")
    console.print("-" * 50)

    try:
        config = PipelineConfig(
            enable_agent=True,
            enable_rag=True,
            enable_reasoning=True,
            enable_articulation=True,
            enable_graceful_degradation=True
        )

        pipeline = QueryPipeline(config=config)

        # First turn
        query1 = "What are the main Swiss federal laws?"
        console.print(f"Turn 1: [yellow]{query1}[/yellow]")
        result1 = await pipeline.process_with_session(query1)
        console.print(f"Session ID: {result1.session_id[:8]}...")
        console.print(f"Answer preview: {result1.answer[:100]}...")

        # Second turn using same session
        query2 = "Tell me more about the first one"
        console.print(f"\nTurn 2: [yellow]{query2}[/yellow]")
        result2 = await pipeline.process_with_session(query2, session_id=result1.session_id)
        console.print(f"Answer preview: {result2.answer[:100]}...")

        console.print("✅ Multi-turn dialogue test passed")
        return True

    except Exception as e:
        console.print(f"❌ Multi-turn test failed: {str(e)}", style="red")
        return False


async def test_error_handling():
    """Test error handling and graceful degradation"""
    console.print("\n[bold blue]Testing Error Handling[/bold blue]")
    console.print("-" * 50)

    try:
        # Create pipeline with monitoring
        config = PipelineConfig(
            enable_agent=True,
            enable_rag=True,
            enable_reasoning=True,
            enable_articulation=True,
            enable_graceful_degradation=True,
            enable_monitoring=True
        )

        pipeline = QueryPipeline(config=config)

        # Test with empty query
        console.print("Testing empty query...")
        result = await pipeline.execute("")
        if result.errors or result.warnings:
            console.print("✅ Empty query handled gracefully")

        # Test very long query
        console.print("Testing very long query...")
        long_query = "test " * 1000
        result = await pipeline.execute(long_query)
        if result:
            console.print("✅ Long query handled")

        # Get performance report
        if pipeline.monitor:
            report = pipeline.monitor.get_performance_report()
            console.print("\n[bold]Performance Report:[/bold]")
            console.print(report)

        return True

    except Exception as e:
        console.print(f"❌ Error handling test failed: {str(e)}", style="red")
        return False


async def test_performance_monitoring():
    """Test performance monitoring capabilities"""
    console.print("\n[bold blue]Testing Performance Monitoring[/bold blue]")
    console.print("-" * 50)

    try:
        config = PipelineConfig(
            enable_agent=False,  # Disable to test faster
            enable_rag=False,
            enable_reasoning=False,
            enable_articulation=False,
            enable_monitoring=True
        )

        pipeline = QueryPipeline(config=config)

        # Run multiple queries
        queries = [
            "What is Swiss law?",
            "Tell me about taxes",
            "Employment regulations"
        ]

        for query in queries:
            await pipeline.execute(query)

        # Get metrics
        if pipeline.monitor:
            metrics = pipeline.monitor.get_all_metrics()

            # Display global metrics
            global_metrics = metrics['global']
            console.print("\n[bold]Global Metrics:[/bold]")
            console.print(f"  Total Requests: {global_metrics['total_requests']}")
            console.print(f"  Success Rate: {global_metrics['success_rate']}")
            console.print(f"  P50 Latency: {global_metrics['p50']}")
            console.print(f"  P95 Latency: {global_metrics['p95']}")

            console.print("✅ Performance monitoring working")

        return True

    except Exception as e:
        console.print(f"❌ Performance monitoring test failed: {str(e)}", style="red")
        return False


async def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold cyan]LAWAST Pipeline Test Suite[/bold cyan]\n"
        "Testing the query pipeline components",
        border_style="cyan"
    ))

    tests = [
        ("Basic Pipeline", test_basic_pipeline),
        ("Simple Query", test_simple_query),
        ("Multi-turn Dialogue", test_multi_turn_dialogue),
        ("Error Handling", test_error_handling),
        ("Performance Monitoring", test_performance_monitoring)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            console.print(f"\n[bold]=== Running: {test_name} ===[/bold]")
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            console.print(f"❌ Test '{test_name}' crashed: {str(e)}", style="red")
            results.append((test_name, False))

    # Summary
    console.print("\n" + "=" * 50)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    console.print("=" * 50)

    table = Table()
    table.add_column("Test", style="cyan")
    table.add_column("Result", style="bold")

    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        style = "green" if success else "red"
        table.add_row(test_name, f"[{style}]{status}[/{style}]")
        if success:
            passed += 1

    console.print(table)

    total = len(results)
    console.print(f"\n[bold]Total: {passed}/{total} tests passed[/bold]")

    if passed == total:
        console.print("[bold green]All tests passed! 🎉[/bold green]")
    else:
        console.print("[bold yellow]Some tests failed. Check the output above.[/bold yellow]")


if __name__ == "__main__":
    asyncio.run(main())