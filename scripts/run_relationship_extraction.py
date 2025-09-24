#!/usr/bin/env python3
"""
Script to run relationship extraction from Fedlex JSON files
Creates relationships between legal entities in Neo4j graph
"""
import sys
import os
import logging
import time
from pathlib import Path
from typing import Dict, Any
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from src.data_access.graph_builder import GraphBuilder
from src.data_access.neo4j_connection import get_connection
from src.extractors.relationship_extractor import RelationshipExtractor
from src.extractors.version_chain_builder import VersionChainBuilder
from src.extractors.uri_resolver import URIResolver
from src.config.extractor_config import ExtractorConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()


def validate_prerequisites() -> bool:
    """
    Validate that nodes exist in Neo4j before extracting relationships

    Returns:
        True if prerequisites are met
    """
    try:
        connection = get_connection()

        # Check for existing nodes
        query = """
        MATCH (l:Law) WITH count(l) AS laws
        MATCH (v:Version) WITH laws, count(v) AS versions
        RETURN laws, versions
        """

        result = connection.execute_query(query)

        if result and len(result) > 0 and result[0]['laws'] > 0:
            console.print(f"[green]✓[/green] Found {result[0]['laws']:,} Law nodes and {result[0]['versions']:,} Version nodes")
            return True
        else:
            console.print("[red]✗[/red] No Law nodes found. Please run TASK-003 first to create nodes.")
            return False

    except Exception as e:
        console.print(f"[red]✗[/red] Error checking prerequisites: {e}")
        return False


def extract_relationships(
    directory: str,
    batch_size: int = 5000,
    limit: int = None
) -> Dict[str, Any]:
    """
    Extract relationships from Fedlex JSON files

    Args:
        directory: Path to fedlex directory
        batch_size: Number of relationships per batch
        limit: Optional limit on files to process

    Returns:
        Statistics dictionary
    """
    stats = {
        "files_processed": 0,
        "relationships_created": {},
        "errors": 0,
        "time_elapsed": 0
    }

    start_time = time.time()

    # Initialize components with configuration
    config = ExtractorConfig.from_env()
    config.batch_size = batch_size
    config.buffer_size = batch_size

    builder = GraphBuilder()
    resolver = URIResolver()
    extractor = RelationshipExtractor(builder, resolver, config)

    # Get JSON files
    fedlex_path = Path(directory)

    # Priority processing order
    directories = [
        ("eli/cc", "Classified compilation"),
        ("eli/oc", "Official compilation"),
        ("eli/fga", "Federal gazette"),
        ("eli/treaty", "Treaties")
    ]

    total_files = 0
    all_files = []

    for subdir, description in directories:
        dir_path = fedlex_path / subdir
        if dir_path.exists():
            files = list(dir_path.rglob("*.json"))
            all_files.extend(files)
            console.print(f"Found {len(files):,} files in {subdir} ({description})")
            total_files += len(files)

    if limit:
        all_files = all_files[:limit]
        total_files = len(all_files)

    console.print(f"\n[bold]Processing {total_files:,} files total[/bold]")

    # Process files with progress bar
    with Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Extracting relationships...", total=total_files)

        for file_path in all_files:
            try:
                relationships = extractor.extract_from_file(str(file_path))

                # Add to buffer
                for rel in relationships:
                    extractor.add_relationship(*rel)

                stats['files_processed'] += 1
                progress.update(task, advance=1)

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats['errors'] += 1

        # Final flush
        progress.update(task, description="Flushing final batch...")
        extractor.flush_relationships()

    stats['relationships_created'] = extractor.get_statistics()
    stats['time_elapsed'] = time.time() - start_time

    return stats


def build_version_chains() -> Dict[str, int]:
    """
    Build SUPERSEDES relationships between consecutive versions

    Returns:
        Statistics dictionary
    """
    console.print("\n[bold]Building version chains...[/bold]")

    chain_builder = VersionChainBuilder()
    stats = chain_builder.build_all_chains()

    return stats


def validate_relationships() -> Dict[str, Any]:
    """
    Run validation queries to check relationship integrity

    Returns:
        Validation results
    """
    console.print("\n[bold]Validating relationships...[/bold]")

    connection = get_connection()
    validation = {
        "valid": True,
        "issues": []
    }

    # Validation queries
    queries = {
        "Laws without versions": """
            MATCH (l:Law)
            WHERE NOT (l)-[:HAS_VERSION]->()
            RETURN count(l) AS count
        """,
        "Versions without parent law": """
            MATCH (v:Version)
            WHERE NOT (v)<-[:HAS_VERSION]-()
            RETURN count(v) AS count
        """,
        "Broken version chains": """
            MATCH (v:Version)
            WHERE v.date_end_applicable IS NOT NULL
              AND NOT EXISTS((v)<-[:SUPERSEDES]-())
            RETURN count(v) AS count
        """,
        "Orphaned nodes": """
            MATCH (n)
            WHERE NOT (n)-[]-()
            RETURN labels(n)[0] AS type, count(n) AS count
        """
    }

    for description, query in queries.items():
        result = connection.execute_read(query)
        if result:
            if isinstance(result[0], dict) and result[0].get('count', 0) > 0:
                validation['valid'] = False
                validation['issues'].append({
                    "description": description,
                    "count": result[0]['count']
                })
            elif len(result) > 0:  # For orphaned nodes query
                validation['valid'] = False
                validation['issues'].append({
                    "description": description,
                    "details": result
                })

    return validation


def display_statistics(stats: Dict[str, Any], chain_stats: Dict[str, int], validation: Dict[str, Any]):
    """
    Display extraction statistics in a formatted table

    Args:
        stats: Extraction statistics
        chain_stats: Version chain statistics
        validation: Validation results
    """
    # Relationship statistics table
    table = Table(title="Relationship Extraction Results", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Files Processed", f"{stats['files_processed']:,}")
    table.add_row("Processing Errors", f"{stats['errors']:,}")
    table.add_row("Time Elapsed", f"{stats['time_elapsed']:.2f} seconds")

    if stats['relationships_created']:
        table.add_section()
        for rel_type, count in stats['relationships_created'].items():
            table.add_row(f"{rel_type} relationships", f"{count:,}")

    console.print(table)

    # Version chain statistics
    if chain_stats:
        chain_table = Table(title="Version Chain Results", show_header=True)
        chain_table.add_column("Metric", style="cyan")
        chain_table.add_column("Value", justify="right", style="green")

        for key, value in chain_stats.items():
            chain_table.add_row(key.replace('_', ' ').title(), f"{value:,}")

        console.print(chain_table)

    # Validation results
    if validation['valid']:
        console.print(Panel("[green]✓ All validation checks passed![/green]", title="Validation"))
    else:
        console.print(Panel("[red]✗ Validation issues found:[/red]", title="Validation"))
        for issue in validation['issues']:
            console.print(f"  - {issue['description']}: {issue.get('count', 'See details')}")
            if 'details' in issue:
                for detail in issue['details']:
                    console.print(f"    • {detail}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Extract relationships from Fedlex JSON files")
    parser.add_argument(
        "--directory",
        default="fedlex",
        help="Path to fedlex directory (default: fedlex)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Batch size for relationship creation (default: 5000)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of files to process (for testing)"
    )
    parser.add_argument(
        "--skip-chains",
        action="store_true",
        help="Skip building version chains"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation queries"
    )

    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]Fedlex Relationship Extractor[/bold cyan]\n"
        "Extracts and creates relationships between legal entities",
        border_style="cyan"
    ))

    # Check prerequisites
    if not validate_prerequisites():
        sys.exit(1)

    # Extract relationships
    console.print("\n[bold]Phase 1: Extracting relationships from JSON files[/bold]")
    stats = extract_relationships(args.directory, args.batch_size, args.limit)

    # Build version chains
    chain_stats = {}
    if not args.skip_chains:
        console.print("\n[bold]Phase 2: Building version chains[/bold]")
        chain_stats = build_version_chains()

    # Validate
    validation = {"valid": True, "issues": []}
    if not args.skip_validation:
        console.print("\n[bold]Phase 3: Validating relationships[/bold]")
        validation = validate_relationships()

    # Display results
    console.print("\n" + "="*50)
    display_statistics(stats, chain_stats, validation)

    # Summary
    total_relationships = sum(stats['relationships_created'].values())
    if chain_stats:
        total_relationships += chain_stats.get('supersedes_created', 0)

    console.print(f"\n[bold green]✓ Complete![/bold green] Created {total_relationships:,} relationships in {stats['time_elapsed']:.2f} seconds")

    if validation['issues']:
        console.print(f"[yellow]⚠ {len(validation['issues'])} validation issues need attention[/yellow]")


if __name__ == "__main__":
    main()