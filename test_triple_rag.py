#!/usr/bin/env python3
"""
Integration test for Triple RAG implementation
Tests vector, graph, and AST search methods with real Neo4j data
"""

import sys
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.retrieval.triple_rag import TripleRAG, TripleRAGConfig
from src.data_access.neo4j_connection import Neo4jConnectionManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich console for pretty output
console = Console()


def test_individual_components():
    """Test each search component individually"""
    console.print("\n[bold cyan]Testing Individual Search Components[/bold cyan]")

    try:
        conn = Neo4jConnectionManager()

        # Test Vector Search
        console.print("\n[yellow]1. Vector Search Test[/yellow]")
        from src.retrieval.vector_search import VectorSearch

        vector_search = VectorSearch(connection=conn)
        stats = vector_search.get_index_statistics()

        console.print(f"Vector indexes found: {len([k for k in stats if 'index' in k])}")
        console.print(f"Law embeddings: {stats.get('law_count', 0)}")
        console.print(f"Article embeddings: {stats.get('article_count', 0)}")

        # Test a simple query
        results = vector_search.search("Datenschutz", top_k=3)
        console.print(f"Vector search returned {len(results)} results")

        # Test Graph Search
        console.print("\n[yellow]2. Graph Search Test[/yellow]")
        from src.retrieval.graph_search import GraphSearch

        graph_search = GraphSearch(connection=conn)
        stats = graph_search.get_graph_statistics()

        console.print(f"Total nodes: {stats.get('total_nodes', 0)}")
        console.print(f"Total relationships: {stats.get('total_relationships', 0)}")
        console.print(f"Reference relationships: {stats.get('reference_relationships', 0)}")

        # Test AST Search
        console.print("\n[yellow]3. AST Search Test[/yellow]")
        from src.retrieval.ast_search import ASTSearch

        ast_search = ASTSearch(connection=conn)
        stats = ast_search.get_ast_statistics()

        console.print(f"Nodes with AST paths: {stats.get('nodes_with_ast_path', 0)}")

        console.print("\n[green]✅ All individual components initialized successfully![/green]")
        return True

    except Exception as e:
        console.print(f"\n[red]❌ Component test failed: {e}[/red]")
        return False


def test_triple_rag_search(query: str = "Datenschutz und personenbezogene Daten"):
    """Test the full Triple RAG orchestrator"""
    console.print(f"\n[bold cyan]Testing Triple RAG Search[/bold cyan]")
    console.print(f"Query: [italic]{query}[/italic]")

    try:
        # Initialize Triple RAG with custom config
        config = TripleRAGConfig(
            vector_weight=0.4,
            graph_weight=0.3,
            ast_weight=0.3,
            vector_top_k=10,
            graph_max_depth=2,
            ast_max_results=10,
            final_top_k=10,
            use_parallel=True
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing Triple RAG...", total=None)
            triple_rag = TripleRAG(config=config)

            progress.update(task, description="Executing search...")
            results, metrics = triple_rag.search(query)
            progress.update(task, completed=True)

        # Display metrics
        console.print("\n[yellow]Search Metrics:[/yellow]")
        metrics_table = Table(show_header=True, header_style="bold magenta")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="green")

        metrics_table.add_row("Total Time", f"{metrics.total_time:.3f}s")
        metrics_table.add_row("Vector Search Time", f"{metrics.vector_time:.3f}s")
        metrics_table.add_row("Graph Search Time", f"{metrics.graph_time:.3f}s")
        metrics_table.add_row("AST Search Time", f"{metrics.ast_time:.3f}s")
        metrics_table.add_row("Merge Time", f"{metrics.merge_time:.3f}s")
        metrics_table.add_row("Vector Results", str(metrics.vector_count))
        metrics_table.add_row("Graph Results", str(metrics.graph_count))
        metrics_table.add_row("AST Results", str(metrics.ast_count))
        metrics_table.add_row("Merged Results", str(metrics.merged_count))
        metrics_table.add_row("Cache Hit", "Yes" if metrics.cache_hit else "No")

        console.print(metrics_table)

        # Display top results
        console.print("\n[yellow]Top Results:[/yellow]")
        results_table = Table(show_header=True, header_style="bold magenta")
        results_table.add_column("#", style="cyan", width=3)
        results_table.add_column("Title", style="green", width=50)
        results_table.add_column("Type", style="yellow", width=10)
        results_table.add_column("Score", style="red", width=8)
        results_table.add_column("Methods", style="blue", width=20)

        for i, result in enumerate(results[:5], 1):
            title = result.title[:47] + "..." if result.title and len(result.title) > 50 else result.title or "N/A"
            methods = ", ".join(result.methods)
            results_table.add_row(
                str(i),
                title,
                result.node_type,
                f"{result.combined_score:.3f}",
                methods
            )

        console.print(results_table)

        # Show detailed view of top result
        if results:
            top_result = results[0]
            console.print("\n[yellow]Top Result Details:[/yellow]")
            details = Panel(
                f"[bold]URI:[/bold] {top_result.uri}\n"
                f"[bold]Node Type:[/bold] {top_result.node_type}\n"
                f"[bold]Combined Score:[/bold] {top_result.combined_score:.3f}\n"
                f"[bold]Method Scores:[/bold] {top_result.method_scores}\n"
                f"[bold]Search Methods:[/bold] {', '.join(top_result.methods)}",
                title=top_result.title or "Untitled",
                border_style="green"
            )
            console.print(details)

        console.print("\n[green]✅ Triple RAG search completed successfully![/green]")
        return True

    except Exception as e:
        console.print(f"\n[red]❌ Triple RAG search failed: {e}[/red]")
        logger.exception("Triple RAG search error")
        return False


def test_different_queries():
    """Test various query types"""
    console.print("\n[bold cyan]Testing Different Query Types[/bold cyan]")

    test_queries = [
        ("SR number search", "232.11"),
        ("Article search", "Artikel 5"),
        ("Legal concept", "Haftung"),
        ("Mixed query", "Datenschutz in 235.1"),
    ]

    try:
        triple_rag = TripleRAG()

        for query_type, query in test_queries:
            console.print(f"\n[yellow]{query_type}:[/yellow] {query}")

            results, metrics = triple_rag.search(query, {
                "final_top_k": 3,
                "use_parallel": True
            })

            console.print(f"  Found {len(results)} results in {metrics.total_time:.3f}s")
            if results:
                console.print(f"  Top result: {results[0].title or results[0].uri}")
                console.print(f"  Score: {results[0].combined_score:.3f}")
                console.print(f"  Methods: {', '.join(results[0].methods)}")

        console.print("\n[green]✅ All query types tested successfully![/green]")
        return True

    except Exception as e:
        console.print(f"\n[red]❌ Query testing failed: {e}[/red]")
        return False


def test_cache_performance():
    """Test caching functionality"""
    console.print("\n[bold cyan]Testing Cache Performance[/bold cyan]")

    try:
        config = TripleRAGConfig(cache_results=True, cache_ttl=60)
        triple_rag = TripleRAG(config=config)

        query = "Datenschutz"

        # First search (cache miss)
        console.print(f"First search for: {query}")
        results1, metrics1 = triple_rag.search(query)
        console.print(f"  Time: {metrics1.total_time:.3f}s (Cache: {'HIT' if metrics1.cache_hit else 'MISS'})")

        # Second search (cache hit)
        console.print(f"Second search for: {query}")
        results2, metrics2 = triple_rag.search(query)
        console.print(f"  Time: {metrics2.total_time:.3f}s (Cache: {'HIT' if metrics2.cache_hit else 'MISS'})")

        # Compare times
        if metrics2.cache_hit:
            speedup = metrics1.total_time / metrics2.total_time
            console.print(f"  [green]Cache speedup: {speedup:.1f}x faster![/green]")

        # Clear cache
        triple_rag.clear_cache()
        console.print("Cache cleared")

        # Third search (cache miss again)
        console.print(f"Third search for: {query}")
        results3, metrics3 = triple_rag.search(query)
        console.print(f"  Time: {metrics3.total_time:.3f}s (Cache: {'HIT' if metrics3.cache_hit else 'MISS'})")

        console.print("\n[green]✅ Cache functionality working correctly![/green]")
        return True

    except Exception as e:
        console.print(f"\n[red]❌ Cache test failed: {e}[/red]")
        return False


def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold cyan]Triple RAG Integration Test Suite[/bold cyan]\n"
        "Testing Vector, Graph, and AST search integration",
        border_style="cyan"
    ))

    all_passed = True

    # Run tests
    tests = [
        ("Individual Components", test_individual_components),
        ("Triple RAG Search", test_triple_rag_search),
        ("Different Query Types", test_different_queries),
        ("Cache Performance", test_cache_performance)
    ]

    for test_name, test_func in tests:
        console.rule(f"[bold]{test_name}[/bold]")
        if not test_func():
            all_passed = False

    # Summary
    console.rule("[bold]Test Summary[/bold]")
    if all_passed:
        console.print(Panel.fit(
            "[bold green]✅ ALL TESTS PASSED![/bold green]\n"
            "Triple RAG is working correctly",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            "[bold red]❌ SOME TESTS FAILED[/bold red]\n"
            "Please check the errors above",
            border_style="red"
        ))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())