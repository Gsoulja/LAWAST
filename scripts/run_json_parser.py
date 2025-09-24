#!/usr/bin/env python3
"""
LAWAST Fedlex JSON Parser CLI

Process Fedlex JSON files and create Neo4j nodes for legal entities.
"""
import sys
import os
import click
import logging
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data_access.fedlex_parser import FedlexParser
from src.data_access.neo4j_connection import get_connection

console = Console()


def setup_logging(level: str = 'INFO'):
    """Setup logging configuration"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('fedlex_parser.log'),
            logging.StreamHandler()
        ]
    )


def verify_neo4j_connection():
    """Verify Neo4j database connection"""
    try:
        connection = get_connection()
        if connection.health_check():
            console.print("✅ Neo4j connection verified", style="green")
            return True
        else:
            console.print("❌ Neo4j connection failed", style="red")
            return False
    except Exception as e:
        console.print(f"❌ Neo4j connection error: {e}", style="red")
        return False


def display_directory_info(directory: Path):
    """Display information about the directory to be processed"""
    if not directory.exists():
        console.print(f"❌ Directory not found: {directory}", style="red")
        return False
    
    # Count JSON files
    json_count = sum(1 for f in directory.rglob("*.json"))
    
    # Get directory size
    total_size = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
    size_mb = total_size / (1024 * 1024)
    
    table = Table(title="Directory Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Directory", str(directory))
    table.add_row("JSON Files", f"{json_count:,}")
    table.add_row("Total Size", f"{size_mb:.1f} MB")
    
    console.print(table)
    return True


def display_progress(parser: FedlexParser, checkpoint_file: str):
    """Display processing progress with Rich"""
    
    # Check if there's an existing checkpoint
    if os.path.exists(checkpoint_file):
        console.print("📄 Found existing checkpoint - processing will resume", style="yellow")
    
    console.print("\n🚀 Starting Fedlex JSON processing...\n")


def display_final_results(summary: dict):
    """Display final processing results"""
    
    # Create results table
    results_table = Table(title="📊 Processing Results", show_header=True)
    results_table.add_column("Metric", style="cyan")
    results_table.add_column("Value", style="green")
    
    results_table.add_row("Files Processed", f"{summary['files_processed']:,}")
    results_table.add_row("Files Failed", f"{summary['files_failed']:,}")
    results_table.add_row("Success Rate", f"{summary['success_rate']:.1f}%")
    results_table.add_row("Processing Time", f"{summary['processing_time_seconds']:.1f} seconds")
    results_table.add_row("Files/Second", f"{summary['files_per_second']:.1f}")
    
    console.print(results_table)
    
    # Display node statistics if available
    if summary.get('statistics'):
        stats_table = Table(title="📈 Node Creation Statistics", show_header=True)
        stats_table.add_column("Node Type", style="cyan")
        stats_table.add_column("Count", style="green")
        
        for key, value in summary['statistics'].items():
            if 'nodes' in key.lower():
                node_type = key.replace('_nodes', '').replace('_', ' ').title()
                stats_table.add_row(node_type, f"{value:,}")
        
        console.print(stats_table)
    
    # Display errors summary
    if summary['files_failed'] > 0:
        console.print(f"\n⚠️  {summary['files_failed']} files failed processing", style="yellow")
        if summary.get('errors'):
            console.print("First few errors:")
            for error in summary['errors'][:3]:
                console.print(f"  • {error}", style="red")


@click.command()
@click.option(
    '--directory', '-d', 
    default='fedlex/eli/cc',
    help='Directory to process (relative to project root)',
    show_default=True
)
@click.option(
    '--limit', '-l', 
    type=int,
    help='Limit number of files to process (for testing)'
)
@click.option(
    '--batch-size', '-b', 
    default=1000,
    help='Batch size for Neo4j operations',
    show_default=True
)
@click.option(
    '--resume/--no-resume', 
    default=True,
    help='Resume from checkpoint if available',
    show_default=True
)
@click.option(
    '--clear-checkpoint', 
    is_flag=True,
    help='Clear existing checkpoint before starting'
)
@click.option(
    '--log-level', 
    default='INFO',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    help='Logging level',
    show_default=True
)
@click.option(
    '--dry-run', 
    is_flag=True,
    help='Parse files but do not create nodes in Neo4j'
)
def main(directory, limit, batch_size, resume, clear_checkpoint, log_level, dry_run):
    """
    🏛️  LAWAST Fedlex JSON Parser
    
    Process Fedlex JSON files and create Neo4j nodes for legal entities.
    
    Examples:
    
      # Process all CC files
      python scripts/run_json_parser.py
      
      # Process first 100 files only
      python scripts/run_json_parser.py --limit 100
      
      # Process OC directory
      python scripts/run_json_parser.py -d fedlex/eli/oc
      
      # Clear checkpoint and start fresh
      python scripts/run_json_parser.py --clear-checkpoint
    """
    
    # Setup
    setup_logging(log_level)
    
    # Display header
    console.print(Panel.fit(
        Text("🏛️  LAWAST Fedlex JSON Parser", style="bold blue", justify="center"),
        border_style="blue"
    ))
    
    # Verify Neo4j connection
    if not verify_neo4j_connection():
        console.print("❌ Cannot proceed without Neo4j connection", style="red")
        sys.exit(1)
    
    # Setup directory path
    project_root = Path(__file__).parent.parent
    target_directory = project_root / directory
    
    # Display directory info
    if not display_directory_info(target_directory):
        sys.exit(1)
    
    # Initialize parser
    try:
        parser = FedlexParser(
            batch_size=batch_size,
            checkpoint_file=f"checkpoint_{directory.replace('/', '_')}.json"
        )
        
        if clear_checkpoint:
            parser.batch_processor.clear_checkpoint()
            console.print("🧹 Cleared checkpoint", style="yellow")
        
        # Display configuration
        config_table = Table(title="⚙️  Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")
        
        config_table.add_row("Target Directory", str(target_directory))
        config_table.add_row("File Limit", str(limit) if limit else "None")
        config_table.add_row("Batch Size", str(batch_size))
        config_table.add_row("Resume Mode", "Yes" if resume else "No")
        config_table.add_row("Dry Run", "Yes" if dry_run else "No")
        config_table.add_row("Log Level", log_level)
        
        console.print(config_table)
        
        if dry_run:
            console.print("\n🧪 DRY RUN MODE - No data will be written to Neo4j", style="yellow")
        
        # Confirm before processing
        if not click.confirm("\nProceed with processing?"):
            console.print("Operation cancelled.", style="yellow")
            sys.exit(0)
        
        # Start processing with progress tracking
        console.print("\n🚀 Starting processing...\n")
        
        start_time = datetime.now()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Processing files...", total=None)
            
            # Process directory
            summary = parser.process_directory(
                target_directory,
                limit=limit,
                resume=resume
            )
            
            progress.update(task, completed=summary['files_processed'], total=summary['total_files'])
        
        # Display results
        console.print(f"\n✅ Processing completed in {(datetime.now() - start_time).total_seconds():.1f} seconds!\n")
        display_final_results(summary)
        
        # Suggest next steps
        console.print("\n💡 Next Steps:", style="cyan")
        console.print("  • Run relationship extraction (TASK-004)")
        console.print("  • Query the graph database to verify nodes")
        console.print("  • Check processing logs for any issues")
        
    except KeyboardInterrupt:
        console.print("\n⏹️  Processing interrupted by user", style="yellow")
        console.print("💾 Progress has been saved. Use --resume to continue later.")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ Error during processing: {e}", style="red")
        logging.exception("Processing failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
