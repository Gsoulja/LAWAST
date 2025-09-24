#!/usr/bin/env python3
"""
HTML Cross-Reference Extraction Script for LAWAST

Processes HTML files from fedlex-assets/ to extract legal cross-references
and create REFERENCES relationships in the Neo4j graph database.

Usage:
    python scripts/run_html_reference_extraction.py [OPTIONS]

Examples:
    # Test with limited files
    python scripts/run_html_reference_extraction.py --limit 100
    
    # Full extraction with 8 workers
    python scripts/run_html_reference_extraction.py --workers 8
    
    # Process specific directory
    python scripts/run_html_reference_extraction.py --path fedlex-assets/eli/cc/2023
    
    # Resume from checkpoint
    python scripts/run_html_reference_extraction.py --resume
"""
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.logging import RichHandler

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.html_reference_extractor import HTMLReferenceExtractor, HTMLPaginationHandler
from src.extractors.relationship_extractor import RelationshipExtractor
from src.data_access.graph_builder import GraphBuilder
from src.data_access.batch_processor import BatchProcessor
from src.config.extractor_config import ExtractorConfig

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Setup logging with Rich handler"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )
    
    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('neo4j').setLevel(logging.WARNING)


class HTMLExtractionProcessor:
    """
    Main processor for HTML reference extraction
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        batch_size: int = 1000,
        memory_limit_mb: int = 1024,
        use_cache: bool = True
    ):
        """
        Initialize processor
        
        Args:
            max_workers: Number of parallel workers
            batch_size: Batch size for relationship creation
            memory_limit_mb: Memory limit per worker
            use_cache: Whether to use caching
        """
        self.max_workers = max_workers
        self.batch_size = batch_size
        
        # Initialize components
        self.graph_builder = GraphBuilder()
        self.relationship_extractor = RelationshipExtractor(self.graph_builder)
        self.html_extractor = HTMLReferenceExtractor(
            memory_limit_mb=memory_limit_mb,
            use_cache=use_cache
        )
        self.pagination_handler = HTMLPaginationHandler()
        self.batch_processor = BatchProcessor(
            self.graph_builder,
            batch_size=batch_size,
            max_workers=max_workers
        )
        
        # Statistics
        self.stats = {
            'files_processed': 0,
            'references_extracted': 0,
            'relationships_created': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def process_html_directory(
        self,
        html_dir: Path,
        limit: int = None,
        resume: bool = False
    ) -> Dict[str, Any]:
        """
        Process HTML files in directory
        
        Args:
            html_dir: Directory containing HTML files
            limit: Maximum number of files to process
            resume: Whether to resume from checkpoint
            
        Returns:
            Processing statistics
        """
        console.print(f"\n🔍 [bold]Scanning HTML files in {html_dir}[/bold]")
        
        # Find all HTML files
        html_files = list(html_dir.rglob("*.html"))
        
        if limit:
            html_files = html_files[:limit]
            console.print(f"📋 Limited to {limit} files")
        
        console.print(f"📄 Found {len(html_files)} HTML files")
        
        if not html_files:
            console.print("❌ No HTML files found")
            return self.stats
        
        # Group paginated files
        console.print("📑 Grouping paginated documents...")
        file_groups = self.pagination_handler.group_paginated_files(html_files)
        
        console.print(f"📚 Grouped into {len(file_groups)} document sets")
        
        # Process file groups
        self.stats['start_time'] = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            # Main processing task
            task = progress.add_task(
                "Processing HTML documents...", 
                total=len(file_groups)
            )
            
            for i, (base_name, file_group) in enumerate(file_groups.items()):
                try:
                    if len(file_group) == 1:
                        # Single file
                        result = self.html_extractor.extract_from_html_file(str(file_group[0]))
                    else:
                        # Paginated document
                        result = self.html_extractor.process_paginated_document(file_group)
                    
                    # Create relationships in batches
                    if result.relationships:
                        for rel in result.relationships:
                            self.relationship_extractor.add_relationship(*rel)
                        
                        # Flush periodically
                        if (i + 1) % self.batch_size == 0:
                            created = self.relationship_extractor.flush_relationships()
                            self.stats['relationships_created'] += created
                    
                    # Update statistics
                    self.stats['files_processed'] += len(file_group)
                    self.stats['references_extracted'] += len(result.relationships)
                    self.stats['errors'] += len(result.errors)
                    
                    # Update progress
                    progress.update(task, advance=1)
                    
                    # Log errors if any
                    if result.errors:
                        for error in result.errors:
                            logger.warning(f"Error: {error}")
                
                except Exception as e:
                    logger.error(f"Failed to process {base_name}: {e}")
                    self.stats['errors'] += 1
                    progress.update(task, advance=1)
                    continue
            
            # Final flush
            console.print("\n💾 Flushing remaining relationships...")
            created = self.relationship_extractor.flush_relationships()
            self.stats['relationships_created'] += created
        
        self.stats['end_time'] = time.time()
        
        return self.stats
    
    def print_statistics(self):
        """Print processing statistics"""
        if not self.stats['start_time']:
            return
        
        duration = self.stats['end_time'] - self.stats['start_time']
        
        # Create statistics table
        table = Table(title="HTML Reference Extraction Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Files Processed", str(self.stats['files_processed']))
        table.add_row("References Extracted", str(self.stats['references_extracted']))
        table.add_row("Relationships Created", str(self.stats['relationships_created']))
        table.add_row("Errors", str(self.stats['errors']))
        table.add_row("Duration", f"{duration:.1f} seconds")
        
        if duration > 0:
            rate = self.stats['files_processed'] / duration
            table.add_row("Processing Rate", f"{rate:.1f} files/sec")
        
        console.print(table)
        
        # Print extractor statistics
        html_stats = self.html_extractor.get_statistics()
        if html_stats:
            console.print("\n📊 [bold]HTML Extractor Statistics:[/bold]")
            for key, value in html_stats.items():
                console.print(f"  {key}: {value}")


@click.command()
@click.option(
    '--path', '-p',
    type=click.Path(exists=True, path_type=Path),
    default=Path('fedlex-assets'),
    help='Path to HTML directory (default: fedlex-assets)'
)
@click.option(
    '--limit', '-l',
    type=int,
    help='Limit number of files to process (for testing)'
)
@click.option(
    '--workers', '-w',
    type=int,
    default=4,
    help='Number of parallel workers (default: 4)'
)
@click.option(
    '--batch-size', '-b',
    type=int,
    default=1000,
    help='Batch size for relationship creation (default: 1000)'
)
@click.option(
    '--memory-limit',
    type=int,
    default=1024,
    help='Memory limit per worker in MB (default: 1024)'
)
@click.option(
    '--no-cache',
    is_flag=True,
    help='Disable reference caching'
)
@click.option(
    '--resume',
    is_flag=True,
    help='Resume from checkpoint'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def main(
    path: Path,
    limit: int,
    workers: int,
    batch_size: int,
    memory_limit: int,
    no_cache: bool,
    resume: bool,
    verbose: bool
):
    """
    Extract legal cross-references from HTML documents
    """
    setup_logging(verbose)
    
    console.print("🏛️  [bold blue]LAWAST HTML Cross-Reference Extraction[/bold blue]")
    console.print(f"📂 Processing directory: {path}")
    console.print(f"⚙️  Workers: {workers}, Batch size: {batch_size}")
    console.print(f"💾 Memory limit: {memory_limit}MB per worker")
    console.print(f"🗄️  Cache: {'Disabled' if no_cache else 'Enabled'}")
    
    if limit:
        console.print(f"🔢 Limited to {limit} files")
    
    try:
        # Initialize processor
        processor = HTMLExtractionProcessor(
            max_workers=workers,
            batch_size=batch_size,
            memory_limit_mb=memory_limit,
            use_cache=not no_cache
        )
        
        # Process HTML files
        stats = processor.process_html_directory(
            path,
            limit=limit,
            resume=resume
        )
        
        # Print results
        processor.print_statistics()
        
        # Success message
        if stats['errors'] == 0:
            console.print("\n✅ [bold green]Processing completed successfully![/bold green]")
        else:
            console.print(f"\n⚠️  [bold yellow]Processing completed with {stats['errors']} errors[/bold yellow]")
        
    except KeyboardInterrupt:
        console.print("\n❌ [bold red]Processing interrupted by user[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ [bold red]Processing failed: {e}[/bold red]")
        logger.exception("Processing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
