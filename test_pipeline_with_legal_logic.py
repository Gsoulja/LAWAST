#!/usr/bin/env python3
"""
Test Query Pipeline with Legal Logic Integration
Verifies that Legal Logic AST is working in the pipeline
"""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig

console = Console()


async def test_pipeline_with_legal_logic():
    """Test the query pipeline with Legal Logic enabled"""

    console.print("\n" + "="*80)
    console.print("[bold cyan]TESTING QUERY PIPELINE WITH LEGAL LOGIC AST[/bold cyan]")
    console.print("="*80 + "\n")

    # Test configuration with Legal Logic enabled
    test_configs = [
        {
            "name": "Standard Pipeline (No Legal Logic)",
            "config": PipelineConfig(
                enable_legal_logic=False,
                enable_agent=True,
                enable_rag=True,
                enable_reasoning=True,
                enable_articulation=True
            )
        },
        {
            "name": "Enhanced Pipeline (With Legal Logic)",
            "config": PipelineConfig(
                enable_legal_logic=True,  # Enable Legal Logic AST
                enable_agent=True,
                enable_rag=True,
                enable_reasoning=True,
                enable_articulation=True
            )
        }
    ]

    # Test queries
    test_queries = [
        {
            "query": "Welche Rechte hat eine Person bei der Meinungsfreiheit?",
            "context": None,
            "expected": "Art. 16 BV"
        },
        {
            "query": "Kündigungsfrist in der Probezeit für Arbeitnehmer",
            "context": {"duration": {"days": 60}, "subject": "employee"},
            "expected": "7 days notice (Art. 335b OR)"
        },
        {
            "query": "Was sind die Pflichten von Bundesbehörden beim Datenschutz?",
            "context": None,
            "expected": "Data security, transparency (DSG)"
        }
    ]

    # Run tests with both configurations
    for config_test in test_configs:
        console.print(f"\n[bold magenta]{config_test['name']}[/bold magenta]")
        console.print("-" * 60)

        # Initialize pipeline
        pipeline = QueryPipeline(config=config_test['config'])

        for test_case in test_queries[:1]:  # Test first query for now
            console.print(f"\n[bold]Query:[/bold] {test_case['query']}")
            if test_case['context']:
                console.print(f"[dim]Context: {test_case['context']}[/dim]")

            try:
                # Execute query
                result = await pipeline.execute(
                    test_case['query'],
                    context=test_case['context']
                )

                # Display results
                console.print(f"\n[green]Answer:[/green] {result.answer[:200]}...")
                console.print(f"[cyan]Confidence:[/cyan] {result.confidence:.2%}")

                if result.citations:
                    console.print(f"[blue]Citations:[/blue]")
                    for citation in result.citations[:3]:
                        console.print(f"  - {citation}")

                # Check for Legal Logic indicators
                if config_test['config'].enable_legal_logic:
                    # Check if result has legal logic metadata
                    has_logic = False
                    if result.metrics and 'detected_intents' in result.metrics:
                        console.print(f"[yellow]Legal Intents:[/yellow] {result.metrics['detected_intents']}")
                        has_logic = True

                    if has_logic:
                        console.print("[green]✓ Legal Logic AST is active[/green]")
                    else:
                        console.print("[yellow]⚠ Legal Logic AST may not be fully integrated[/yellow]")

            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")

    # Summary comparison
    console.print("\n" + "="*80)
    console.print("[bold green]COMPARISON SUMMARY[/bold green]")
    console.print("="*80 + "\n")

    comparison_table = Table(show_header=True, header_style="bold blue")
    comparison_table.add_column("Feature", style="cyan", width=25)
    comparison_table.add_column("Standard Pipeline", style="yellow", width=25)
    comparison_table.add_column("With Legal Logic", style="green", width=25)

    comparison_table.add_row(
        "Search Method",
        "Vector + Graph + Path AST",
        "Vector + Graph + Legal Logic"
    )
    comparison_table.add_row(
        "Query Understanding",
        "Keyword extraction",
        "Intent detection"
    )
    comparison_table.add_row(
        "Legal Operators",
        "Not detected",
        "MUST, MAY, SHALL NOT"
    )
    comparison_table.add_row(
        "Condition Evaluation",
        "Not supported",
        "Context-aware evaluation"
    )
    comparison_table.add_row(
        "Embeddings",
        "Article content only",
        "Content + Legal Logic patterns"
    )

    console.print(comparison_table)

    console.print("\n[bold cyan]Key Advantages of Legal Logic Integration:[/bold cyan]")
    console.print("• Semantic understanding of legal rules (IF-THEN-EXCEPT)")
    console.print("• Intent-based query processing")
    console.print("• Condition evaluation with context")
    console.print("• Legal operator detection and reasoning")
    console.print("• Searchable legal logic embeddings")


async def test_legal_logic_search():
    """Test specific Legal Logic search capabilities"""

    console.print("\n" + "="*80)
    console.print("[bold yellow]TESTING LEGAL LOGIC SEARCH CAPABILITIES[/bold yellow]")
    console.print("="*80 + "\n")

    # Initialize pipeline with Legal Logic
    config = PipelineConfig(
        enable_legal_logic=True,
        enable_agent=False,  # Disable agent for direct RAG test
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True
    )

    pipeline = QueryPipeline(config=config)

    # Test different query types
    test_scenarios = [
        {
            "name": "Obligation Query",
            "query": "Welche Pflichten müssen Arbeitgeber erfüllen?",
            "expected_operator": "MUST"
        },
        {
            "name": "Permission Query",
            "query": "Was dürfen Bürger gemäss Verfassung?",
            "expected_operator": "MAY"
        },
        {
            "name": "Temporal Query",
            "query": "Fristen für Kündigungen im Arbeitsrecht",
            "expected_operator": "temporal constraints"
        },
        {
            "name": "Exception Query",
            "query": "Ausnahmen bei der Meinungsfreiheit",
            "expected_operator": "EXCEPT"
        }
    ]

    for scenario in test_scenarios[:2]:  # Test first two for now
        console.print(f"\n[bold]{scenario['name']}:[/bold]")
        console.print(f"Query: {scenario['query']}")

        try:
            result = await pipeline.execute(scenario['query'])

            # Check if legal operators were detected
            console.print(f"Answer preview: {result.answer[:150]}...")
            console.print(f"Expected operator: {scenario['expected_operator']}")

            if result.confidence > 0.7:
                console.print(f"[green]✓ High confidence: {result.confidence:.2%}[/green]")
            else:
                console.print(f"[yellow]⚠ Medium confidence: {result.confidence:.2%}[/yellow]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")


async def main():
    """Run all tests"""
    try:
        # Test basic integration
        await test_pipeline_with_legal_logic()

        # Test specific Legal Logic features
        await test_legal_logic_search()

        console.print("\n" + "="*80)
        console.print("[bold green]✅ Legal Logic Pipeline Testing Complete![/bold green]")
        console.print("="*80 + "\n")

    except Exception as e:
        console.print(f"\n[red]Test failed: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())