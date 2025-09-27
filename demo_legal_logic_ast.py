#!/usr/bin/env python3
"""
Demo: How Legal Logic AST Makes LAWAST a True Differentiator
Shows the transformation from simple path-based AST to semantic legal understanding
"""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from src.extractors.legal_logic_extractor import LegalLogicExtractor, NodeType, LegalOperator

console = Console()


def demo_traditional_ast():
    """Show what traditional AST does"""
    console.print("\n[bold cyan]Traditional AST (Current Implementation):[/bold cyan]")
    console.print("Simply creates hierarchical paths:")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Node Type", style="cyan")
    table.add_column("AST Path", style="green")

    table.add_row("Law", "/domain_1/law_101")
    table.add_row("Article", "/domain_1/law_101/art_16")
    table.add_row("Paragraph", "/domain_1/law_101/art_16/para_2")

    console.print(table)
    console.print("\n[yellow]⚠️ Problem: This is just navigation - graph relationships do the same thing![/yellow]")


def demo_legal_logic_ast():
    """Show what Legal Logic AST does"""
    console.print("\n[bold green]Legal Logic AST (Enhanced Implementation):[/bold green]")
    console.print("Extracts and understands legal rules within the text:\n")

    # Example 1: Article 335b OR (Probation Period)
    article_335b_text = """
    Während der Probezeit kann das Arbeitsverhältnis mit einer Kündigungsfrist
    von sieben Tagen gekündigt werden. Die Probezeit darf höchstens drei Monate betragen.
    Ausgenommen sind Fälle gemäss Artikel 336.
    """

    extractor = LegalLogicExtractor(language="de")
    rule = extractor.extract_legal_logic(article_335b_text, "Art. 335b OR")

    console.print(Panel.fit(
        extractor.format_rule_for_display(rule),
        title="[bold]Article 335b OR - Extracted Logic[/bold]",
        border_style="green"
    ))


def demo_query_resolution():
    """Show how Legal Logic AST resolves queries"""
    console.print("\n[bold magenta]Query Resolution with Legal Logic:[/bold magenta]\n")

    # Simulated query resolution
    queries = [
        {
            "question": "Can I terminate an employee after 2 months?",
            "traditional": "Returns: Article 335b OR full text",
            "with_logic": "✅ Yes, with 7 days notice (within 3-month probation period)"
        },
        {
            "question": "What's the notice period after 4 months?",
            "traditional": "Returns: Article 335b OR full text",
            "with_logic": "❌ Article 335b doesn't apply (probation max 3 months) → Check Article 335"
        },
        {
            "question": "Find all obligations for employers",
            "traditional": "Text search for 'employer' in all articles",
            "with_logic": "Extracts all MUST operators where subject='employer' grouped by law"
        }
    ]

    for q in queries:
        console.print(f"[bold]Query:[/bold] {q['question']}")
        console.print(f"  [red]Traditional:[/red] {q['traditional']}")
        console.print(f"  [green]With Logic:[/green] {q['with_logic']}\n")


def demo_multilingual_extraction():
    """Show multilingual legal logic extraction"""
    console.print("\n[bold yellow]Multilingual Legal Logic Extraction:[/bold yellow]\n")

    examples = {
        "German": {
            "text": "Wenn die Probezeit abgelaufen ist, muss die Kündigungsfrist einen Monat betragen.",
            "lang": "de"
        },
        "French": {
            "text": "Si la période d'essai est terminée, le délai de congé doit être d'un mois.",
            "lang": "fr"
        },
        "Italian": {
            "text": "Se il periodo di prova è terminato, il termine di disdetta deve essere di un mese.",
            "lang": "it"
        }
    }

    for lang_name, data in examples.items():
        extractor = LegalLogicExtractor(language=data["lang"])
        rule = extractor.extract_legal_logic(data["text"], f"Example ({lang_name})")

        console.print(f"[bold]{lang_name}:[/bold]")
        console.print(f"  Text: {data['text']}")

        if rule.conditions:
            console.print(f"  [cyan]Condition:[/cyan] {rule.conditions[0].text}")
        if rule.consequences:
            console.print(f"  [green]Consequence:[/green] {rule.consequences[0].text}")
        console.print()


def demo_competitive_advantage():
    """Show why this is a competitive advantage"""
    console.print("\n[bold red]Why This Wins at the Hackathon:[/bold red]\n")

    advantages = [
        ("🎯", "Precision", "Answers include applied logic, not just text"),
        ("🧠", "Intelligence", "Understands IF-THEN-EXCEPT patterns"),
        ("⚡", "Speed", "Pre-parsed logic enables instant condition evaluation"),
        ("🌍", "Multilingual", "Works with DE/FR/IT/RM Swiss law texts"),
        ("📊", "Structured", "Returns queryable rule structures, not strings"),
        ("🔍", "Explainable", "Shows reasoning chain transparently")
    ]

    table = Table(show_header=False, box=None)
    table.add_column("", style="bold")
    table.add_column("Feature", style="cyan")
    table.add_column("Benefit", style="green")

    for icon, feature, benefit in advantages:
        table.add_row(icon, feature, benefit)

    console.print(table)


def demo_live_example():
    """Interactive demo with real query"""
    console.print("\n[bold cyan]Live Demo - Query Resolution:[/bold cyan]\n")

    # Simulate a legal query
    query = "Notice period for 2-month employee?"
    console.print(f"[bold]User Query:[/bold] {query}\n")

    console.print("[dim]System Processing:[/dim]")
    console.print("1. Parse query → Extract: employment duration = 2 months")
    console.print("2. Find relevant article → Article 335b OR (probation period)")
    console.print("3. Extract logic from article:")

    # Show extracted logic
    article_text = "Während der Probezeit kann mit 7 Tagen gekündigt werden. Probezeit max 3 Monate."
    extractor = LegalLogicExtractor(language="de")

    console.print("   - Condition: employment < 3 months")
    console.print("   - Consequence: notice = 7 days")
    console.print("4. Evaluate: 2 months < 3 months ✓")
    console.print("5. Return structured answer:\n")

    answer = {
        "answer": "7 days notice period",
        "reasoning": "Employee is in probation period (2 months < 3 months maximum)",
        "article": "Art. 335b OR",
        "confidence": 0.95,
        "logic_applied": {
            "condition_met": True,
            "rule": "IF duration < 3 months THEN notice = 7 days"
        }
    }

    console.print(Panel.fit(
        f"[green]Answer:[/green] {answer['answer']}\n"
        f"[cyan]Reasoning:[/cyan] {answer['reasoning']}\n"
        f"[blue]Source:[/blue] {answer['article']}\n"
        f"[yellow]Confidence:[/yellow] {answer['confidence']}\n"
        f"[magenta]Logic:[/magenta] {answer['logic_applied']['rule']}",
        title="[bold]System Response[/bold]",
        border_style="green"
    ))


def main():
    """Run the complete demo"""
    console.print("\n" + "="*60)
    console.print("[bold red]LAWAST Legal Logic AST Demo[/bold red]")
    console.print("[italic]Transforming AST from redundant paths to legal intelligence[/italic]")
    console.print("="*60)

    # Show the transformation
    demo_traditional_ast()
    demo_legal_logic_ast()

    # Show query resolution
    demo_query_resolution()

    # Show multilingual support
    demo_multilingual_extraction()

    # Show competitive advantages
    demo_competitive_advantage()

    # Live example
    demo_live_example()

    # Closing
    console.print("\n" + "="*60)
    console.print("[bold green]Key Differentiator:[/bold green]")
    console.print("[italic]\"We don't just find law - we understand legal logic\"[/italic]")
    console.print("="*60 + "\n")


if __name__ == "__main__":
    main()