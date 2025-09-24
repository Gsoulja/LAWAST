#!/usr/bin/env python3
"""Quick demo for hackathon judges"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import track
import time

console = Console()

def demo():
    console.print(Panel.fit(
        "[bold cyan]LAWAST[/bold cyan] - Swiss Legal AI Assistant\n"
        "Powered by Graph RAG + AST + Apertus",
        border_style="cyan"
    ))

    demos = [
        ("🏢 Employment", "Can I terminate an employee who leaked confidential data?"),
        ("🏠 Rental", "How much can my landlord increase the rent?"),
        ("💳 Credit", "What is the maximum interest rate for consumer loans?")
    ]

    for category, question in demos:
        console.print(f"\n{category} [bold]Question:[/bold] {question}")

        # Simulate processing
        for step in track(["Analyzing", "Retrieving", "Reasoning"], description="Processing..."):
            time.sleep(0.5)

        console.print("[green]✓[/green] Answer generated (placeholder)\n")
        console.print("-" * 50)

if __name__ == "__main__":
    demo()
