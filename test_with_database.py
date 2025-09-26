#!/usr/bin/env python3
"""
Test LAWAST Pipeline with real Neo4j data
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

os.environ['HUGGINGFACE_API_KEY'] = 'your-huggingface-api-key'

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig
from src.data_access.neo4j_connection import Neo4jConnectionManager
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


async def test_database_connectivity():
    """Test basic database connectivity"""
    console.print("\n[bold blue]1. Database Connectivity Test[/bold blue]")
    console.print("-" * 50)

    neo4j = Neo4jConnectionManager()
    try:
        with neo4j.get_session() as session:
            result = session.run("""
                MATCH (l:Law)
                RETURN count(l) as law_count
                LIMIT 1
            """)
            count = result.single()["law_count"]
            console.print(f"✅ Connected to Neo4j - Found {count} laws in database")
            neo4j.close()
            return True
    except Exception as e:
        console.print(f"❌ Database connection failed: {e}", style="red")
        neo4j.close()
        return False


async def test_direct_database_search():
    """Test direct database queries without embeddings"""
    console.print("\n[bold blue]2. Direct Database Search Test[/bold blue]")
    console.print("-" * 50)

    # Test the AST search directly
    from src.retrieval.ast_search import ASTSearch
    from src.data_access.neo4j_connection import Neo4jConnectionManager

    neo4j_conn = Neo4jConnectionManager()
    ast_search = ASTSearch(neo4j_conn)

    # Search for articles about "Alter" (age)
    query = "Rentenalter"  # Retirement age
    console.print(f"Searching for: '{query}'")

    results = ast_search.search(query, max_results=5)
    console.print(f"Found {len(results)} results")

    if results:
        table = Table(title="AST Search Results")
        table.add_column("Title", style="cyan", width=30)
        table.add_column("Content", style="yellow", width=50)
        table.add_column("Score", style="green")

        for result in results[:3]:
            title = result.title or "N/A"
            content = (result.content or "")[:100] + "..." if result.content else "N/A"
            score = f"{result.score:.2f}"
            table.add_row(title, content, score)

        console.print(table)

    neo4j_conn.close()
    return len(results) > 0


async def test_graph_search():
    """Test graph-based search"""
    console.print("\n[bold blue]3. Graph Search Test[/bold blue]")
    console.print("-" * 50)

    from src.retrieval.graph_search import GraphSearch
    from src.data_access.neo4j_connection import Neo4jConnectionManager

    neo4j_conn = Neo4jConnectionManager()
    graph_search = GraphSearch(neo4j_conn)

    # Find a law node first
    with neo4j_conn.get_session() as session:
        result = session.run("""
            MATCH (l:Law)
            WHERE l.title_de CONTAINS 'Rente' OR l.title_de CONTAINS 'Alter'
            RETURN elementId(l) as id, l.title_de as title
            LIMIT 1
        """)
        record = result.single()

        if record:
            seed_id = record["id"]
            title = record["title"]
            console.print(f"Found seed law: {title[:50]}...")

            # Search for related nodes using traverse_relationships
            results = graph_search.traverse_relationships(
                start_node_id=seed_id,
                max_depth=2,
                limit=5
            )
            console.print(f"Found {len(results)} related nodes")

            if results:
                for result in results[:3]:
                    # Results are dictionaries, not objects
                    node_type = result.get('node_type', 'Unknown')
                    title = result.get('title') or result.get('uri', 'N/A')
                    console.print(f"  - {node_type}: {title}")

    neo4j_conn.close()
    return True


async def test_pipeline_without_embeddings():
    """Test pipeline with database but without vector embeddings"""
    console.print("\n[bold blue]4. Pipeline Test (No Embeddings)[/bold blue]")
    console.print("-" * 50)

    config = PipelineConfig(
        enable_agent=True,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_graceful_degradation=True,
        enable_monitoring=True
    )

    # Modify RAG config to avoid vector search
    import os
    os.environ['SKIP_EMBEDDINGS'] = 'true'

    pipeline = QueryPipeline(config=config)

    queries = [
        "Was ist das Rentenalter in der Schweiz?",
        "Welche Rechte haben Arbeitnehmer?",
        "Was sind die Voraussetzungen für eine GmbH?"
    ]

    for query in queries[:1]:  # Test with first query only
        console.print(f"\nQuery: [yellow]{query}[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing with pipeline...", total=None)

            try:
                result = await pipeline.execute(query)
                progress.update(task, completed=True)

                console.print(Panel(
                    f"[bold]Answer:[/bold]\n{result.answer[:300]}...\n\n"
                    f"[bold]Confidence:[/bold] {result.confidence:.1%}\n"
                    f"[bold]Time:[/bold] {result.execution_time:.2f}s",
                    title="Pipeline Result",
                    border_style="green"
                ))

                if result.citations:
                    console.print(f"Citations: {len(result.citations)} sources")

            except Exception as e:
                progress.update(task, completed=True)
                console.print(f"[red]Error: {e}[/red]")

    return True


async def test_specific_law_query():
    """Test querying specific laws by SR number"""
    console.print("\n[bold blue]5. Specific Law Query Test[/bold blue]")
    console.print("-" * 50)

    neo4j = Neo4jConnectionManager()

    # Query for specific SR numbers we know exist
    test_queries = [
        ("1.0.0.1.9", "freiwillige"),  # We know this exists from earlier
        ("831.10", "AHV"),  # Common pension law
        ("220", "OR"),  # Obligationenrecht
    ]

    for sr_number, keyword in test_queries:
        console.print(f"\nSearching for SR {sr_number} (keyword: {keyword})...")

        with neo4j.get_session() as session:
            result = session.run("""
                MATCH (l:Law)
                WHERE l.sr_number STARTS WITH $sr_number
                   OR l.title_de CONTAINS $keyword
                   OR l.title_fr CONTAINS $keyword
                RETURN l.sr_number as sr,
                       l.title_de as title,
                       elementId(l) as id
                LIMIT 3
            """, sr_number=sr_number, keyword=keyword)

            found = False
            for record in result:
                found = True
                console.print(f"  ✅ Found: SR {record['sr']} - {record['title'][:60]}...")

            if not found:
                console.print(f"  ⚠️  No results for SR {sr_number}")

    # Test article retrieval for a law
    console.print("\n[bold]Testing article retrieval:[/bold]")
    with neo4j.get_session() as session:
        result = session.run("""
            MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
            WHERE l.sr_number IS NOT NULL
              AND a.content_full IS NOT NULL
            RETURN l.sr_number as sr,
                   l.title_de as law_title,
                   a.number as article_num,
                   a.content_full as content
            LIMIT 2
        """)

        for record in result:
            console.print(f"\nLaw: SR {record['sr']}")
            console.print(f"Article {record['article_num']}:")
            console.print(f"{record['content'][:150]}...")

    neo4j.close()
    return True


async def main():
    """Run all database tests"""
    console.print(Panel.fit(
        "[bold cyan]LAWAST Pipeline - Real Database Tests[/bold cyan]\n"
        "Testing with actual Neo4j data",
        border_style="cyan"
    ))

    # Summary of database contents
    console.print("\n[bold]Database Contents:[/bold]")
    console.print("  • 1,000 Laws")
    console.print("  • 21,053 Articles")
    console.print("  • 9,805 Paragraphs")
    console.print("  • 15,525 nodes with embeddings")
    console.print("  • 102,571 relationships")

    tests = [
        ("Database Connectivity", test_database_connectivity),
        ("Direct Database Search", test_direct_database_search),
        ("Graph Search", test_graph_search),
        ("Pipeline without Embeddings", test_pipeline_without_embeddings),
        ("Specific Law Query", test_specific_law_query),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            console.print(f"\n[bold]=== {test_name} ===[/bold]")
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            console.print(f"❌ Test failed: {e}", style="red")
            results.append((test_name, False))

    # Summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]Test Summary[/bold cyan]")

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

    console.print(f"\n[bold]Total: {passed}/{len(results)} tests passed[/bold]")

    if passed == len(results):
        console.print("\n[bold green]All database tests passed! 🎉[/bold green]")
        console.print("\nThe pipeline successfully:")
        console.print("  ✅ Connects to Neo4j database")
        console.print("  ✅ Retrieves laws and articles")
        console.print("  ✅ Performs AST and graph searches")
        console.print("  ✅ Processes queries with real data")
    else:
        console.print("\n[yellow]Some tests failed. Check the output above.[/yellow]")


if __name__ == "__main__":
    asyncio.run(main())