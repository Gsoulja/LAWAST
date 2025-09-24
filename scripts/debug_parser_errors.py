#!/usr/bin/env python3
"""
Debug parser errors - Show detailed error messages for failed files
"""
import sys
import json
import traceback
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.fedlex_parser import FedlexParser

console = Console()


def analyze_json_file(file_path: Path):
    """Analyze a single JSON file and show detailed error information"""
    console.print(f"\n[bold cyan]📄 Analyzing: {file_path.name}[/bold cyan]")
    console.print(f"Full path: {file_path}")

    try:
        # First, check if file can be opened and parsed as JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        console.print("[green]✅ JSON parsing successful[/green]")

        # Show JSON structure
        console.print("\n[bold]JSON Structure:[/bold]")

        # Top-level keys
        if isinstance(data, dict):
            console.print(f"Top-level keys: {list(data.keys())}")

            # Check for expected structure
            if 'data' in data:
                console.print("  'data' keys:", list(data['data'].keys()) if isinstance(data['data'], dict) else type(data['data']))

                if 'attributes' in data.get('data', {}):
                    attrs = data['data']['attributes']
                    console.print("  'attributes' keys:", list(attrs.keys())[:5], "..." if len(attrs) > 5 else "")

                if 'references' in data.get('data', {}):
                    refs = data['data']['references']
                    console.print("  'references' keys:", list(refs.keys())[:5], "..." if len(refs) > 5 else "")

            if 'included' in data:
                console.print(f"  'included' items: {len(data['included'])} items")

        # Now try to parse with FedlexParser
        console.print("\n[bold]Parser Test:[/bold]")
        parser = FedlexParser()

        # Try parsing
        result = parser.parse_file(file_path)

        if result['status'] == 'success':
            console.print("[green]✅ Parser successful![/green]")
            console.print(f"Nodes created: {result.get('nodes_created', {})}")
        else:
            console.print(f"[red]❌ Parser failed: {result.get('error', 'Unknown error')}[/red]")

            # Show the full error with traceback
            if 'error' in result:
                console.print("\n[bold red]Full Error:[/bold red]")
                console.print(Panel(str(result['error']), border_style="red"))

    except json.JSONDecodeError as e:
        console.print(f"[red]❌ JSON decode error: {e}[/red]")
        console.print(f"  Error at line {e.lineno}, column {e.colno}")

        # Show the problematic part of the file
        with open(file_path, 'r') as f:
            lines = f.readlines()
            if e.lineno <= len(lines):
                console.print("\n[bold]Problematic section:[/bold]")
                start = max(0, e.lineno - 3)
                end = min(len(lines), e.lineno + 2)
                for i in range(start, end):
                    prefix = ">>>" if i == e.lineno - 1 else "   "
                    console.print(f"{prefix} {i+1}: {lines[i].rstrip()}")

    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {type(e).__name__}: {e}[/red]")
        console.print("\n[bold red]Full Traceback:[/bold red]")
        console.print(Panel(traceback.format_exc(), border_style="red"))


def test_parser_directly():
    """Test the parser with a simple example"""
    console.print("\n[bold yellow]🧪 Direct Parser Test[/bold yellow]")

    # Create a minimal valid JSON structure
    test_data = {
        "data": {
            "uri": "https://fedlex.data.admin.ch/eli/cc/test/123",
            "type": ["ConsolidationAbstract", "Work"],
            "attributes": {
                "dateDocument": {"xsd:date": "2024-01-01"}
            },
            "references": {}
        }
    }

    # Save to temp file
    temp_path = Path("test_parse.json")
    with open(temp_path, 'w') as f:
        json.dump(test_data, f)

    try:
        parser = FedlexParser()
        result = parser.parse_file(temp_path)

        if result['status'] == 'success':
            console.print("[green]✅ Parser works with minimal data[/green]")
        else:
            console.print(f"[red]❌ Parser failed even with minimal data: {result.get('error')}[/red]")

    finally:
        if temp_path.exists():
            temp_path.unlink()


def check_parser_components():
    """Check if all parser components are available"""
    console.print("\n[bold cyan]🔍 Checking Parser Components[/bold cyan]")

    components = {
        'FedlexParser': 'src.data_access.fedlex_parser',
        'LawExtractor': 'src.extractors.law_extractor',
        'VersionExtractor': 'src.extractors.version_extractor',
        'ActExtractor': 'src.extractors.act_extractor',
        'GraphBuilder': 'src.data_access.graph_builder',
        'BatchProcessor': 'src.data_access.batch_processor'
    }

    table = Table(title="Component Status")
    table.add_column("Component", style="cyan")
    table.add_column("Module", style="white")
    table.add_column("Status", style="green")

    for comp_name, module_path in components.items():
        try:
            module = __import__(module_path, fromlist=[comp_name])
            if hasattr(module, comp_name):
                table.add_row(comp_name, module_path, "✅ Available")
            else:
                table.add_row(comp_name, module_path, "⚠️ Class not found")
        except ImportError as e:
            table.add_row(comp_name, module_path, f"❌ Import error: {e}")

    console.print(table)


def main():
    console.print(Panel.fit(
        "🔍 LAWAST Parser Error Debugger",
        border_style="bold blue"
    ))

    # Check components first
    check_parser_components()

    # Test with minimal data
    test_parser_directly()

    # Get sample of problematic files
    problem_files = [
        'fedlex/eli/cc/I/271_271_445.json',  # Roman numeral
        'fedlex/eli/cc/1959/__1811.json',     # Double underscore
        'fedlex/eli/cc/1999/404.json',        # Should work
        'fedlex/eli/cc/60/679_676_661.json',  # From errors
    ]

    console.print("\n[bold]Analyzing Sample Files:[/bold]")

    for file_path_str in problem_files:
        file_path = Path(file_path_str)
        if file_path.exists():
            analyze_json_file(file_path)
        else:
            console.print(f"\n[yellow]⚠️ File not found: {file_path}[/yellow]")

    # Also check first few files in directory
    console.print("\n[bold]Checking first 3 files in fedlex/eli/cc:[/bold]")
    cc_dir = Path('fedlex/eli/cc')
    json_files = list(cc_dir.rglob("*.json"))[:3]

    for file_path in json_files:
        analyze_json_file(file_path)


if __name__ == "__main__":
    main()