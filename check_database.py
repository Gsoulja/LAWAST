#!/usr/bin/env python3
"""
Check Neo4j database contents and statistics
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

from src.data_access.neo4j_connection import Neo4jConnectionManager
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def check_database():
    """Check database connectivity and contents"""

    console.print(Panel.fit(
        "[bold cyan]Neo4j Database Status Check[/bold cyan]",
        border_style="cyan"
    ))

    # Connect to Neo4j
    neo4j = Neo4jConnectionManager()

    try:
        # Test connection
        with neo4j.get_session() as session:
            result = session.run("RETURN 1 as test")
            test = result.single()["test"]
            console.print(f"✅ Connected to Neo4j at {neo4j.uri}")
    except Exception as e:
        console.print(f"❌ Failed to connect: {e}", style="red")
        return

    # Check database statistics
    with neo4j.get_session() as session:
        # Count nodes by type
        console.print("\n[bold]Node Statistics:[/bold]")

        node_counts = {}
        labels_result = session.run("CALL db.labels()")

        for record in labels_result:
            label = record["label"]
            count_result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            count = count_result.single()["count"]
            node_counts[label] = count

        # Display node counts
        table = Table(title="Nodes in Database")
        table.add_column("Node Type", style="cyan")
        table.add_column("Count", style="green")

        total = 0
        for label, count in sorted(node_counts.items()):
            table.add_row(label, str(count))
            total += count

        table.add_row("─" * 10, "─" * 10)
        table.add_row("TOTAL", str(total), style="bold")

        console.print(table)

        # Check relationships
        console.print("\n[bold]Relationship Statistics:[/bold]")

        rel_result = session.run("""
            CALL db.relationshipTypes() YIELD relationshipType
            RETURN relationshipType
        """)

        rel_table = Table(title="Relationships in Database")
        rel_table.add_column("Relationship Type", style="cyan")
        rel_table.add_column("Count", style="green")

        for record in rel_result:
            rel_type = record["relationshipType"]
            count_result = session.run(f"""
                MATCH ()-[r:{rel_type}]->()
                RETURN count(r) as count
            """)
            count = count_result.single()["count"]
            rel_table.add_row(rel_type, str(count))

        console.print(rel_table)

        # Sample some Law nodes
        console.print("\n[bold]Sample Law Nodes:[/bold]")

        sample_laws = session.run("""
            MATCH (l:Law)
            WHERE l.sr_number IS NOT NULL
            RETURN l.sr_number as sr,
                   l.title_de as title,
                   l.uri as uri
            LIMIT 5
        """)

        laws_table = Table(title="Sample Laws")
        laws_table.add_column("SR Number", style="cyan")
        laws_table.add_column("Title", style="yellow")

        for record in sample_laws:
            sr = record["sr"] or "N/A"
            title = record["title"] or "N/A"
            if len(title) > 50:
                title = title[:50] + "..."
            laws_table.add_row(sr, title)

        console.print(laws_table)

        # Check for embeddings
        console.print("\n[bold]Embedding Status:[/bold]")

        embedding_result = session.run("""
            MATCH (n)
            WHERE n.embedding IS NOT NULL
            RETURN labels(n)[0] as label, count(n) as count
        """)

        has_embeddings = False
        for record in embedding_result:
            has_embeddings = True
            console.print(f"  {record['label']}: {record['count']} nodes with embeddings")

        if not has_embeddings:
            console.print("  ⚠️  No embeddings found in database", style="yellow")

        # Check Articles with content
        console.print("\n[bold]Article Content Status:[/bold]")

        article_result = session.run("""
            MATCH (a:Article)
            RETURN
                count(a) as total,
                count(a.content_full) as with_content,
                count(a.title_de) + count(a.title_fr) + count(a.title_it) as with_title
        """)

        article_stats = article_result.single()
        console.print(f"  Total Articles: {article_stats['total']}")
        console.print(f"  With Content: {article_stats['with_content']}")
        console.print(f"  With Title: {article_stats['with_title']}")

        # Sample Article with content
        console.print("\n[bold]Sample Article with Content:[/bold]")

        sample_article = session.run("""
            MATCH (a:Article)
            WHERE a.content_full IS NOT NULL
            RETURN a.number as num,
                   a.title_de as title,
                   a.content_full as content
            LIMIT 1
        """)

        for record in sample_article:
            console.print(f"  Article {record['num']}: {record['title'] or 'No title'}")
            content = record['content'] or ""
            if content:
                console.print(f"  Content preview: {content[:200]}...")

        # Check relationships between Laws and Articles
        console.print("\n[bold]Law-Article Relationships:[/bold]")

        rel_stats = session.run("""
            MATCH (l:Law)-[r:HAS_ARTICLE]->(a:Article)
            RETURN count(DISTINCT l) as laws_with_articles,
                   count(DISTINCT a) as articles_with_laws,
                   count(r) as total_relationships
        """)

        rel_data = rel_stats.single()
        console.print(f"  Laws with Articles: {rel_data['laws_with_articles']}")
        console.print(f"  Articles linked to Laws: {rel_data['articles_with_laws']}")
        console.print(f"  Total HAS_ARTICLE relationships: {rel_data['total_relationships']}")

    neo4j.close()

    console.print("\n[bold green]Database check complete![/bold green]")


if __name__ == "__main__":
    check_database()