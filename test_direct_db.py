#!/usr/bin/env python3
"""
Direct database query test to see what data is actually available
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

from src.data_access.neo4j_connection import Neo4jConnectionManager
from rich.console import Console
from rich.table import Table

console = Console()


def test_direct_queries():
    """Test direct queries to see what's in the database"""

    neo4j = Neo4jConnectionManager()

    console.print("[bold cyan]Direct Database Query Test[/bold cyan]\n")

    with neo4j.get_session() as session:
        # 1. Search for content containing "Rente" or "Alter"
        console.print("[bold]1. Searching for 'Rente' or 'Alter' in content:[/bold]")

        result = session.run("""
            MATCH (n)
            WHERE (n.content_full CONTAINS 'Rente' OR
                   n.content_full CONTAINS 'Alter' OR
                   n.text CONTAINS 'Rente' OR
                   n.text CONTAINS 'Alter')
            RETURN labels(n)[0] as type,
                   n.uri as uri,
                   CASE
                       WHEN n.content_full IS NOT NULL THEN n.content_full
                       WHEN n.text IS NOT NULL THEN n.text
                       ELSE 'No content'
                   END as content
            LIMIT 5
        """)

        count = 0
        for record in result:
            count += 1
            console.print(f"\n{record['type']}: {record['uri']}")
            console.print(f"Content: {record['content'][:200]}...")

        console.print(f"\nTotal found: {count}")

        # 2. Search in titles
        console.print("\n[bold]2. Searching for 'Rente' or 'Alter' in titles:[/bold]")

        result = session.run("""
            MATCH (n)
            WHERE (n.title_de CONTAINS 'Rente' OR
                   n.title_de CONTAINS 'Alter' OR
                   n.title_fr CONTAINS 'Rente' OR
                   n.title_fr CONTAINS 'retraite')
            RETURN labels(n)[0] as type,
                   n.uri as uri,
                   COALESCE(n.title_de, n.title_fr, n.title_it) as title
            LIMIT 10
        """)

        table = Table(title="Results with 'Rente'/'Alter' in title")
        table.add_column("Type", style="cyan")
        table.add_column("Title", style="yellow")

        for record in result:
            table.add_row(
                record['type'],
                (record['title'] or 'No title')[:60] + "..."
            )

        console.print(table)

        # 3. Check AST paths
        console.print("\n[bold]3. Checking AST paths in database:[/bold]")

        result = session.run("""
            MATCH (n)
            WHERE n.ast_path IS NOT NULL
            RETURN labels(n)[0] as type,
                   n.ast_path as path,
                   n.uri as uri
            LIMIT 5
        """)

        for record in result:
            console.print(f"{record['type']}: {record['path']} -> {record['uri']}")

        # 4. Search using full-text (if available)
        console.print("\n[bold]4. Testing text search capabilities:[/bold]")

        # Check if any nodes have searchable text
        result = session.run("""
            MATCH (n:Article)
            WHERE n.content_full IS NOT NULL
            WITH n
            WHERE toLower(n.content_full) CONTAINS 'rentenalter'
               OR toLower(n.content_full) CONTAINS 'pensionsalter'
               OR toLower(n.content_full) CONTAINS 'ruhestand'
            RETURN n.uri as uri,
                   n.number as article_number,
                   n.content_full as content
            LIMIT 5
        """)

        console.print("\nArticles mentioning retirement age:")
        for record in result:
            console.print(f"\nArticle {record['article_number']}: {record['uri']}")
            console.print(f"Content: {record['content'][:200]}...")

        # 5. Check what's actually indexed
        console.print("\n[bold]5. Checking indexed content:[/bold]")

        result = session.run("""
            MATCH (n)
            WHERE n.embedding IS NOT NULL
            RETURN labels(n)[0] as type,
                   count(n) as count
            ORDER BY count DESC
        """)

        console.print("Nodes with embeddings:")
        for record in result:
            console.print(f"  {record['type']}: {record['count']}")

    neo4j.close()
    console.print("\n[bold green]Direct database test complete![/bold green]")


if __name__ == "__main__":
    test_direct_queries()