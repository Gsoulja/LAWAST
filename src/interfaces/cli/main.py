#!/usr/bin/env python3
"""LAWAST CLI - Swiss Legal AI Assistant"""

import click
from rich.console import Console

console = Console()

@click.command()
@click.argument('question')
def query(question):
    """Query Swiss law"""
    console.print(f"[bold cyan]Question:[/bold cyan] {question}")

    # TODO: Implement RAG pipeline
    # 1. Classify question domain
    # 2. Retrieve relevant articles
    # 3. Generate answer with Apertus

    console.print("[yellow]RAG pipeline not yet implemented[/yellow]")

if __name__ == "__main__":
    query()
