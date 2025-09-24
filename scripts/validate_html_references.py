#!/usr/bin/env python3
"""
HTML Reference Validation Script

Quick validation of reference detection without database dependencies.
Shows what references are found in HTML files.
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.html_reference_extractor import HTMLReferenceExtractor

console = Console()

def validate_references(html_file: str):
    """Validate references in a single HTML file"""
    console.print(f"\n🔍 [bold]Analyzing: {html_file}[/bold]")
    
    extractor = HTMLReferenceExtractor(use_cache=False)
    result = extractor.extract_from_html_file(html_file)
    
    if result.relationships:
        table = Table(title=f"References Found ({len(result.relationships)})")
        table.add_column("Source", style="cyan")
        table.add_column("Target", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Details", style="blue")
        
        for rel in result.relationships:
            source, target, rel_type, props = rel
            details = f"Lang: {props.get('language', 'N/A')}, Conf: {props.get('confidence', 'N/A'):.2f}"
            table.add_row(
                source.split('/')[-1],  # Just the end part
                target,
                rel_type,
                details
            )
        
        console.print(table)
        
        # Show raw text samples
        console.print("\n📝 [bold]Raw Reference Text:[/bold]")
        for rel in result.relationships[:3]:  # Show first 3
            props = rel[3]
            console.print(f"  • '{props.get('raw_text', 'N/A')}' → {rel[1]}")
    
    else:
        console.print("❌ No references found")
    
    if result.errors:
        console.print(f"\n⚠️  [yellow]Errors ({len(result.errors)}):[/yellow]")
        for error in result.errors:
            console.print(f"  • {error}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        console.print("Usage: python validate_html_references.py <html_file>")
        sys.exit(1)
    
    html_file = sys.argv[1]
    validate_references(html_file)
