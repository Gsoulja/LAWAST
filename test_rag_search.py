#!/usr/bin/env python3
"""
Test RAG search to see why Article 114 is always returned
"""

import sys
from rich.console import Console
from rich.table import Table

console = Console()


def test_simple_search():
    """Test basic search without full pipeline"""

    console.print("\n" + "="*80)
    console.print("[bold red]Testing RAG Search Issue[/bold red]")
    console.print("="*80)

    # Try to load minimal components
    try:
        from src.data_access.embedding_generator import EmbeddingGenerator

        embedder = EmbeddingGenerator()

        # Test query embeddings
        queries = [
            "Entstehen mir Nachteile wenn ich eine Petition einreiche?",
            "Was regelt die Meinungsfreiheit?",
            "Was ist Arbeitslosenversicherung?"
        ]

        console.print("\n[cyan]Testing query embeddings:[/cyan]")
        for query in queries:
            embedding = embedder.generate_embedding(query)
            console.print(f"Query: {query[:50]}...")
            console.print(f"Embedding shape: {len(embedding)}")
            console.print(f"First 5 values: {embedding[:5]}")
            console.print()

    except ImportError as e:
        console.print(f"[yellow]Could not load embedding generator: {e}[/yellow]")

    # Check if there's a cached or default result
    console.print("\n[magenta]Checking for hardcoded values:[/magenta]")

    # Check environment variables
    import os
    env_vars = os.environ
    for key in env_vars:
        if "114" in str(env_vars[key]) or "ARTICLE" in key:
            console.print(f"[red]Found env var with 114: {key}={env_vars[key][:100]}[/red]")

    # Check for any config files
    import glob
    config_files = glob.glob("**/*.json", recursive=True) + glob.glob("**/*.yaml", recursive=True)
    for config_file in config_files[:10]:  # Check first 10 config files
        try:
            with open(config_file, 'r') as f:
                content = f.read()
                if "114" in content and "Art" in content:
                    console.print(f"[yellow]Found '114' in config: {config_file}[/yellow]")
                    # Show context
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if "114" in line:
                            start = max(0, i-1)
                            end = min(len(lines), i+2)
                            console.print("  Context:")
                            for j in range(start, end):
                                console.print(f"    {lines[j][:100]}")
                            break
        except:
            pass

    # Check if there's a default or fallback article
    console.print("\n[cyan]Checking for default/fallback patterns:[/cyan]")

    # Search for any default article patterns
    patterns_to_check = [
        "default.*article",
        "fallback.*article",
        "DEFAULT_ARTICLE",
        "FALLBACK_ARTICLE"
    ]

    try:
        import re
        import os
        for root, dirs, files in os.walk("src"):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r') as f:
                            content = f.read()
                            for pattern in patterns_to_check:
                                if re.search(pattern, content, re.IGNORECASE):
                                    console.print(f"[yellow]Found pattern '{pattern}' in {filepath}[/yellow]")
                                    # Find the line
                                    for i, line in enumerate(content.split('\n'), 1):
                                        if re.search(pattern, line, re.IGNORECASE):
                                            console.print(f"  Line {i}: {line[:100]}")
                    except:
                        pass
    except Exception as e:
        console.print(f"[red]Error searching files: {e}[/red]")

    console.print("\n" + "="*80)
    console.print("[green]Search complete[/green]")
    console.print("="*80)


if __name__ == "__main__":
    test_simple_search()