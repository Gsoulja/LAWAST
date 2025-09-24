#!/usr/bin/env python3
"""
LAWAST Complete Graph Builder
Builds the full knowledge graph with all components
"""
import sys
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection
from src.data_access.fedlex_parser import FedlexParser
from src.extractors.relationship_extractor import RelationshipExtractor
from src.data_access.batch_processor import BatchProcessor

console = Console()


class CompleteGraphBuilder:
    """Orchestrates the complete graph building process"""

    def __init__(self):
        self.connection = get_connection()
        self.start_time = None
        self.stats = {
            'json_files_processed': 0,
            'nodes_created': 0,
            'relationships_created': 0,
            'errors': [],
            'phase_times': {}
        }

    def check_prerequisites(self):
        """Check that everything is ready"""
        console.print("\n[bold cyan]🔍 Checking Prerequisites...[/bold cyan]")

        checks = {
            'Neo4j Connection': self.check_neo4j(),
            'Fedlex Data': self.check_fedlex_data(),
            'Python Dependencies': self.check_dependencies(),
            'Disk Space': self.check_disk_space()
        }

        table = Table(title="System Check")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="white")

        all_ok = True
        for check, result in checks.items():
            status, details = result
            table.add_row(
                check,
                "✅ Ready" if status else "❌ Failed",
                details
            )
            if not status:
                all_ok = False

        console.print(table)
        return all_ok

    def check_neo4j(self):
        """Check Neo4j connection"""
        try:
            if self.connection.health_check():
                # Get current stats
                query = "MATCH (n) RETURN count(n) as count"
                result = self.connection.execute_query(query)
                count = result[0]['count'] if result else 0
                return True, f"{count:,} existing nodes"
            return False, "Connection failed"
        except Exception as e:
            return False, str(e)

    def check_fedlex_data(self):
        """Check data availability"""
        json_count = len(list(Path('fedlex').rglob('*.json')))
        html_count = len(list(Path('fedlex-assets').rglob('*.html'))) if Path('fedlex-assets').exists() else 0
        return True, f"{json_count:,} JSON, {html_count:,} HTML files"

    def check_dependencies(self):
        """Check Python dependencies"""
        try:
            import neo4j
            import ijson
            import rich
            return True, "All required packages installed"
        except ImportError as e:
            return False, f"Missing: {e.name}"

    def check_disk_space(self):
        """Check available disk space"""
        import shutil
        stat = shutil.disk_usage(".")
        free_gb = stat.free / (1024**3)
        return free_gb > 10, f"{free_gb:.1f} GB free"

    def clean_database(self):
        """Clean existing data if requested"""
        console.print("\n[bold yellow]⚠️  Database Cleanup[/bold yellow]")

        # Check existing data
        query = "MATCH (n) RETURN count(n) as count"
        result = self.connection.execute_query(query)
        count = result[0]['count'] if result else 0

        if count > 0:
            console.print(f"Database contains {count:,} existing nodes")
            if Confirm.ask("Do you want to clean the database first?", default=False):
                console.print("🗑️  Cleaning database...")

                # Delete in batches
                batch_size = 10000
                deleted = 0

                with Progress() as progress:
                    task = progress.add_task("[red]Deleting nodes...", total=count)

                    while True:
                        query = f"""
                        MATCH (n)
                        WITH n LIMIT {batch_size}
                        DETACH DELETE n
                        RETURN count(n) as deleted
                        """
                        result = self.connection.execute_write(query)
                        batch_deleted = result[0]['deleted'] if result else 0

                        if batch_deleted == 0:
                            break

                        deleted += batch_deleted
                        progress.update(task, completed=deleted)

                console.print(f"✅ Deleted {deleted:,} nodes")
        else:
            console.print("✅ Database is empty")

    def initialize_schema(self):
        """Initialize Neo4j schema and indexes"""
        console.print("\n[bold cyan]📐 Initializing Schema...[/bold cyan]")

        indexes = [
            ("Law", "uri"),
            ("Law", "sr_number"),
            ("Version", "uri"),
            ("Version", "date_applicable"),
            ("Expression", "uri"),
            ("Expression", "language"),
            ("Manifestation", "uri"),
            ("Article", "uri"),
            ("Article", "number")
        ]

        created = 0
        for label, property in indexes:
            try:
                query = f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.{property})"
                self.connection.execute_write(query)
                created += 1
            except:
                pass

        console.print(f"✅ Created {created} indexes")

    def process_json_files(self, limit=None, directories=None):
        """Process JSON files to create nodes"""
        phase_start = time.time()

        if directories is None:
            directories = ['fedlex/eli/cc', 'fedlex/eli/oc', 'fedlex/eli/fga', 'fedlex/eli/treaty']

        console.print(f"\n[bold cyan]📄 Phase 1: JSON Processing[/bold cyan]")

        parser = FedlexParser()
        total_processed = 0
        total_nodes = 0
        total_relationships = 0

        for dir_path in directories:
            directory = Path(dir_path)
            if not directory.exists():
                console.print(f"[yellow]⚠️  Directory not found: {dir_path}[/yellow]")
                continue

            json_files = list(directory.rglob("*.json"))
            if limit and total_processed >= limit:
                break

            files_to_process = json_files[:min(len(json_files), limit - total_processed if limit else len(json_files))]

            console.print(f"\n📁 Processing {len(files_to_process):,} files from {dir_path}")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn()
            ) as progress:

                task = progress.add_task(f"[cyan]Processing {directory.name}...", total=len(files_to_process))

                for json_file in files_to_process:
                    try:
                        result = parser.parse_file(json_file)
                        if result.get('success'):
                            total_nodes += result.get('nodes_created', 0)
                            total_relationships += result.get('relationships_created', 0)
                            total_processed += 1
                        else:
                            self.stats['errors'].append(f"JSON: {json_file.name}")
                    except Exception as e:
                        self.stats['errors'].append(f"JSON: {json_file.name}: {str(e)[:50]}")

                    progress.update(task, advance=1)

                    # Show periodic updates
                    if total_processed % 100 == 0:
                        progress.console.print(f"  [dim]Processed {total_processed:,} files, {total_nodes:,} nodes[/dim]")

        self.stats['json_files_processed'] = total_processed
        self.stats['nodes_created'] = total_nodes
        self.stats['relationships_created'] = total_relationships
        self.stats['phase_times']['json'] = time.time() - phase_start

        console.print(f"\n✅ JSON Processing Complete:")
        console.print(f"   • Files: {total_processed:,}")
        console.print(f"   • Nodes: {total_nodes:,}")
        console.print(f"   • Relationships: {total_relationships:,}")
        console.print(f"   • Time: {self.stats['phase_times']['json']:.1f} seconds")

    def extract_relationships(self, limit=None, directories=None):
        """Extract and build relationships between entities"""
        phase_start = time.time()

        console.print(f"\n[bold cyan]🔗 Phase 2: Relationship Extraction[/bold cyan]")

        # Skip if no files were processed in Phase 1
        if self.stats.get('json_files_processed', 0) == 0:
            console.print("[yellow]⚠️  No files processed in Phase 1, skipping relationship extraction[/yellow]")
            self.stats['phase_times']['relationships'] = 0
            return

        try:
            from src.extractors.relationship_extractor import RelationshipExtractor
            from src.config.extractor_config import ExtractorConfig

            # Configure extractor to skip missing nodes (important for limited runs)
            config = ExtractorConfig()
            config.skip_missing_nodes = True  # Don't fail on missing nodes
            config.log_failed_relationships = False  # Don't log every missing relationship
            extractor = RelationshipExtractor(config=config)

            # Use the same directories and limit as JSON processing
            if directories is None:
                directories = ['fedlex/eli/cc', 'fedlex/eli/oc']

            total_created = 0
            files_to_process = []

            # Collect the same files that were processed in Phase 1
            for dir_path in directories:
                directory = Path(dir_path)
                if not directory.exists():
                    continue

                json_files = list(directory.rglob("*.json"))
                if limit:
                    # Take only the files that would have been processed in Phase 1
                    files_to_process.extend(json_files[:min(len(json_files), limit - len(files_to_process))])
                    if len(files_to_process) >= limit:
                        break
                else:
                    files_to_process.extend(json_files)

            console.print(f"Extracting relationships from {len(files_to_process):,} files...")

            if limit:
                console.print("[yellow]⚠️  Limited run: Some relationships may be skipped due to missing nodes[/yellow]")

            with Progress() as progress:
                task = progress.add_task("[cyan]Extracting relationships...", total=len(files_to_process))

                for file_path in files_to_process:
                    try:
                        # Extract relationships from individual file
                        relationships = extractor.extract_from_file(str(file_path))

                        # Add relationships with error handling for missing nodes
                        for from_uri, to_uri, rel_type, properties in relationships:
                            try:
                                extractor.add_relationship(from_uri, to_uri, rel_type, properties)
                            except Exception as e:
                                # Track missing node errors but don't spam console
                                if "missing" not in str(e).lower():
                                    self.stats['errors'].append(f"Relationship: {rel_type} - {str(e)[:50]}")

                        progress.update(task, advance=1)

                    except Exception as e:
                        # Log file-level errors
                        self.stats['errors'].append(f"File: {file_path.name} - {str(e)[:50]}")

                # Flush any buffered relationships
                extractor.flush_relationships()

                # Get statistics
                stats = extractor.get_statistics()

                # Display statistics for each relationship type
                for rel_type in ['HAS_VERSION', 'SUPERSEDES', 'EXPRESSED_IN', 'MANIFESTED_AS', 'AMENDS']:
                    count = stats.get(rel_type, 0)
                    if count > 0:
                        console.print(f"   • {rel_type}: {count:,} relationships")
                        total_created += count

                self.stats['relationships_created'] += total_created

        except Exception as e:
            console.print(f"[red]❌ Relationship extraction error: {e}[/red]")

        self.stats['phase_times']['relationships'] = time.time() - phase_start
        console.print(f"   • Total: {total_created:,} relationships")
        console.print(f"   • Time: {self.stats['phase_times']['relationships']:.1f} seconds")

    def process_html_files(self, limit=None):
        """Process HTML files for article content and references"""
        phase_start = time.time()

        console.print(f"\n[bold cyan]🌐 Phase 3: Reference Extraction from HTML[/bold cyan]")

        if not Path('fedlex-assets').exists():
            console.print("[yellow]⚠️  fedlex-assets directory not found, skipping HTML[/yellow]")
            return

        # Import extractors
        from src.extractors.html_reference_extractor import HTMLReferenceExtractor, HTMLPaginationHandler
        from src.extractors.article_extractor import ArticleExtractor
        from src.data_access.batch_processor import BatchProcessor

        # Initialize components
        html_extractor = HTMLReferenceExtractor()
        article_extractor = ArticleExtractor()
        pagination_handler = HTMLPaginationHandler()
        batch_processor = BatchProcessor(self.connection)

        # Collect HTML files
        html_files = list(Path('fedlex-assets').rglob('*.html'))
        if limit:
            html_files = html_files[:limit]

        # Group paginated files
        file_groups = pagination_handler.group_paginated_files(html_files)

        console.print(f"Found {len(html_files):,} HTML files in {len(file_groups):,} documents")
        console.print("[dim]Processing with article extraction and reference detection...[/dim]")

        html_processed = 0
        articles_extracted = 0
        references_extracted = 0
        relationships_to_create = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn()
        ) as progress:
            task = progress.add_task("[cyan]Processing HTML documents...", total=len(file_groups))

            for base_doc, file_list in file_groups.items():
                try:
                    # Process paginated document or single file
                    if len(file_list) > 1:
                        # Paginated document
                        result = html_extractor.process_paginated_document(file_list)
                    else:
                        # Single file - extract both articles and references
                        file_path = str(file_list[0])

                        # Extract articles with embedded references
                        article_result = article_extractor.extract(file_path)

                        # Also run dedicated reference extraction for document-level refs
                        ref_result = html_extractor.extract_from_html_file(file_path)

                        # Combine results
                        result = article_result
                        if ref_result and ref_result.relationships:
                            for rel in ref_result.relationships:
                                result.add_relationship(rel[0], rel[1], rel[2], rel[3] if len(rel) > 3 else {})

                    # Process the extraction result
                    if result:
                        # Count statistics
                        if result.nodes:
                            articles_extracted += len(result.nodes)

                        if result.relationships:
                            refs_count = len([r for r in result.relationships if r[2] == "REFERENCES"])
                            references_extracted += refs_count
                            relationships_to_create.extend(result.relationships)

                        html_processed += 1

                        # Batch create relationships periodically
                        if len(relationships_to_create) >= 1000:
                            batch_processor.batch_create_relationships(relationships_to_create)
                            relationships_to_create = []

                except Exception as e:
                    self.stats['errors'].append(f"HTML: {base_doc}: {str(e)[:50]}")

                progress.update(task, advance=1)

        # Create remaining relationships
        if relationships_to_create:
            batch_processor.batch_create_relationships(relationships_to_create)

        self.stats['phase_times']['html'] = time.time() - phase_start
        self.stats['relationships_created'] += references_extracted

        console.print(f"\n✅ HTML & Reference Extraction Complete:")
        console.print(f"   • Documents processed: {html_processed:,}")
        console.print(f"   • Articles extracted: {articles_extracted:,}")
        console.print(f"   • References found: {references_extracted:,}")
        console.print(f"   • Time: {self.stats['phase_times']['html']:.1f} seconds")

        # Show extraction rate
        if self.stats['phase_times']['html'] > 0:
            rate = references_extracted / self.stats['phase_times']['html']
            console.print(f"   • Extraction rate: {rate:.0f} references/second")

    def verify_graph(self):
        """Verify the final graph state"""
        console.print(f"\n[bold cyan]✅ Phase 4: Verification[/bold cyan]")

        # Node counts
        node_query = """
        MATCH (n)
        RETURN labels(n)[0] as label, count(n) as count
        ORDER BY count DESC
        """
        node_results = self.connection.execute_query(node_query)

        # Relationship counts
        rel_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        ORDER BY count DESC
        """
        rel_results = self.connection.execute_query(rel_query)

        # Display results
        node_table = Table(title="📊 Nodes in Graph")
        node_table.add_column("Type", style="cyan")
        node_table.add_column("Count", style="green")

        total_nodes = 0
        for row in node_results:
            count = row['count']
            total_nodes += count
            node_table.add_row(row['label'], f"{count:,}")

        console.print(node_table)

        rel_table = Table(title="🔗 Relationships in Graph")
        rel_table.add_column("Type", style="magenta")
        rel_table.add_column("Count", style="green")

        total_rels = 0
        for row in rel_results:
            count = row['count']
            total_rels += count
            rel_table.add_row(row['type'], f"{count:,}")

        console.print(rel_table)

        # Sample queries
        console.print("\n[bold]📝 Sample Queries:[/bold]")

        sample_queries = [
            ("Laws with versions", "MATCH (l:Law)-[:HAS_VERSION]->(v:Version) RETURN count(DISTINCT l) as count"),
            ("Laws with expressions", "MATCH (l:Law)-[:EXPRESSED_IN]->(e:Expression) RETURN count(DISTINCT l) as count"),
            ("Most recent laws", "MATCH (l:Law) WHERE l.date_entry_in_force >= '2020-01-01' RETURN count(l) as count")
        ]

        for description, query in sample_queries:
            try:
                result = self.connection.execute_query(query)
                count = result[0]['count'] if result else 0
                console.print(f"   • {description}: {count:,}")
            except:
                pass

        return total_nodes, total_rels

    def show_final_summary(self):
        """Show final summary of the build"""
        total_time = sum(self.stats['phase_times'].values())

        console.print("\n" + "=" * 60)
        console.print(Panel.fit(
            Text("🎉 GRAPH BUILD COMPLETE", style="bold green", justify="center"),
            border_style="green"
        ))

        summary = Table(title="📊 Build Summary", show_header=False)
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="green")

        summary.add_row("Total Time", f"{total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        summary.add_row("JSON Files Processed", f"{self.stats['json_files_processed']:,}")
        summary.add_row("Nodes Created", f"{self.stats['nodes_created']:,}")
        summary.add_row("Relationships Created", f"{self.stats['relationships_created']:,}")
        summary.add_row("Errors Encountered", f"{len(self.stats['errors'])}")

        console.print(summary)

        if self.stats['errors']:
            console.print(f"\n[yellow]⚠️  {len(self.stats['errors'])} errors occurred[/yellow]")

            # Show first few errors as examples
            unique_errors = {}
            for error in self.stats['errors']:
                error_type = error.split(':')[0]
                if error_type not in unique_errors:
                    unique_errors[error_type] = []
                unique_errors[error_type].append(error)

            console.print("\n[dim]Error Summary:[/dim]")
            for error_type, errors in list(unique_errors.items())[:3]:
                console.print(f"  • {error_type}: {len(errors)} occurrences")
                if len(errors) > 0:
                    console.print(f"    Example: [dim]{errors[0]}[/dim]")

        console.print("\n[bold]🚀 Next Steps:[/bold]")
        console.print("1. View graph in Neo4j Browser: http://localhost:7474")
        console.print("2. Run test queries: python scripts/test_graph_queries.py")
        console.print("3. Add taxonomy: See TASK-007")


def main():
    console.print(Panel.fit(
        Text("🏛️ LAWAST COMPLETE GRAPH BUILDER", style="bold blue", justify="center"),
        border_style="blue"
    ))

    builder = CompleteGraphBuilder()

    # Check prerequisites
    if not builder.check_prerequisites():
        console.print("[red]❌ Prerequisites check failed. Please fix issues and try again.[/red]")
        sys.exit(1)

    # Choose build configuration
    console.print("\n[bold]📋 Build Configuration[/bold]")

    build_options = {
        '1': ('Quick Test', 100, ['fedlex/eli/cc'], False),
        '2': ('Small Build', 1000, ['fedlex/eli/cc'], False),
        '3': ('Standard Build', 10000, ['fedlex/eli/cc', 'fedlex/eli/oc'], False),
        '4': ('Full Build (CC+OC)', None, ['fedlex/eli/cc', 'fedlex/eli/oc'], False),
        '5': ('Complete Build (All)', None, None, True),
        '6': ('Custom', None, None, None)
    }

    console.print("\nChoose build type:")
    for key, (name, _, _, _) in build_options.items():
        console.print(f"{key}. {name}")

    choice = Prompt.ask("Enter choice", choices=list(build_options.keys()), default='1')

    name, limit, directories, include_html = build_options[choice]

    if choice == '6':
        # Custom configuration
        limit = int(Prompt.ask("File limit (0 for all)", default="1000"))
        if limit == 0:
            limit = None

        console.print("\nSelect directories to process:")
        all_dirs = ['fedlex/eli/cc', 'fedlex/eli/oc', 'fedlex/eli/fga', 'fedlex/eli/treaty']
        directories = []
        for d in all_dirs:
            if Confirm.ask(f"  Include {d}?", default=d in ['fedlex/eli/cc']):
                directories.append(d)

        include_html = Confirm.ask("Process HTML files?", default=False)

    # Show configuration
    console.print(f"\n[bold]Build Type:[/bold] {name}")
    console.print(f"[bold]File Limit:[/bold] {limit if limit else 'All files'}")
    console.print(f"[bold]Directories:[/bold] {', '.join(directories) if directories else 'All'}")
    console.print(f"[bold]Include HTML:[/bold] {'Yes' if include_html else 'No'}")

    if not Confirm.ask("\nProceed with build?", default=True):
        console.print("Build cancelled")
        sys.exit(0)

    # Start build
    builder.start_time = datetime.now()
    console.print(f"\n🚀 Starting build at {builder.start_time.strftime('%H:%M:%S')}")

    try:
        # Clean database if requested
        builder.clean_database()

        # Initialize schema
        builder.initialize_schema()

        # Process JSON files
        builder.process_json_files(limit=limit, directories=directories)

        # Extract relationships
        builder.extract_relationships(limit=limit, directories=directories)

        # Process HTML if requested
        if include_html:
            builder.process_html_files(limit=100 if limit else None)

        # Verify graph
        builder.verify_graph()

        # Show summary
        builder.show_final_summary()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Build interrupted by user[/yellow]")
        console.print("Progress has been saved. Run again to continue.")
    except Exception as e:
        console.print(f"\n[red]❌ Build failed: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()