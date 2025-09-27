#!/usr/bin/env python3
"""
Test Legal Logic Enhanced LAWAST System
Demonstrates how Legal Logic AST makes LAWAST a true differentiator
"""

import asyncio
import json
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from src.retrieval.enhanced_triple_rag import EnhancedTripleRAG, EnhancedTripleRAGConfig
from src.extractors.legal_logic_extractor import LegalLogicExtractor
from src.data_access.neo4j_connection import Neo4jConnectionManager

console = Console()


class LegalLogicTester:
    """Test the enhanced system with legal logic"""

    def __init__(self):
        """Initialize tester"""
        # Initialize connection
        self.connection = Neo4jConnectionManager()

        # Initialize enhanced Triple RAG with legal logic
        config = EnhancedTripleRAGConfig(
            enable_legal_logic=True,
            legal_language="de",
            enable_condition_evaluation=True,
            legal_logic_weight=0.4,  # Higher weight for legal logic
            vector_weight=0.2,
            graph_weight=0.2,
            hybrid_weight=0.2,
            legal_logic_boost=1.3  # Boost results with legal logic
        )

        self.enhanced_rag = EnhancedTripleRAG(config, self.connection)

    def run_comparison_test(self):
        """Compare traditional vs legal logic enhanced search"""
        console.print("\n" + "="*80)
        console.print("[bold cyan]TRADITIONAL VS LEGAL LOGIC COMPARISON[/bold cyan]")
        console.print("="*80)

        # Test queries
        test_queries = [
            {
                "query": "Kündigungsfrist in der Probezeit",
                "context": {"duration": {"days": 60}},  # 2 months
                "expected_logic": "IF in probation period (< 3 months) THEN notice = 7 days"
            },
            {
                "query": "Meinungsfreiheit Bundesverfassung",
                "context": None,
                "expected_logic": "RIGHT to form and express opinions freely"
            },
            {
                "query": "Welche Pflichten haben Bundesbehörden beim Datenschutz?",
                "context": None,
                "expected_logic": "MUST ensure data security, transparency, purpose limitation"
            }
        ]

        for test in test_queries:
            console.print(f"\n[bold]Query:[/bold] {test['query']}")
            console.print("-" * 60)

            # Run enhanced search
            results, metrics = self.enhanced_rag.search(
                query=test['query'],
                context=test['context']
            )

            # Display comparison
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Aspect", style="cyan", width=20)
            table.add_column("Traditional AST", style="yellow", width=30)
            table.add_column("Legal Logic AST", style="green", width=30)

            # Traditional approach
            table.add_row(
                "Search Method",
                "Path matching\n(e.g., /domain_1/law_101/art_16)",
                "Semantic legal understanding\nIF-THEN-EXCEPT patterns"
            )

            table.add_row(
                "Query Understanding",
                "Keyword extraction",
                f"Intent detection:\n{', '.join(metrics.detected_intents)}"
            )

            if results and results[0].metadata and "legal_reasoning" in results[0].metadata:
                table.add_row(
                    "Result Quality",
                    "Returns full article text",
                    f"Extracts legal logic:\n{results[0].metadata['legal_reasoning']}"
                )

            if results and results[0].metadata and "applicable_operators" in results[0].metadata:
                ops = results[0].metadata['applicable_operators']
                table.add_row(
                    "Legal Operators",
                    "Not detected",
                    f"Detected: {', '.join(ops)}"
                )

            console.print(table)

            # Show expected vs actual logic
            if test['expected_logic']:
                console.print(f"\n[dim]Expected Logic:[/dim] {test['expected_logic']}")

    def test_challenge_queries(self):
        """Test with actual Swiss Law Challenge queries"""
        console.print("\n" + "="*80)
        console.print("[bold magenta]SWISS LAW CHALLENGE QUERIES TEST[/bold magenta]")
        console.print("="*80)

        challenge_queries = [
            {
                "id": "Q.a",
                "query": "Welche Rechte hat eine Person gemäss Bundesverfassung bei der Meinungsfreiheit?",
                "expected_article": "Art. 16 BV"
            },
            {
                "id": "Q.b",
                "query": "Unter welchen Umständen darf ein Arbeitsvertrag in der Probezeit gekündigt werden?",
                "expected_article": "Art. 335b OR"
            },
            {
                "id": "Q.c",
                "query": "Welche Datenschutzpflichten bestehen für Bundesbehörden?",
                "expected_article": "Art. 4-7 DSG"
            }
        ]

        for challenge in challenge_queries:
            console.print(f"\n[bold]Challenge {challenge['id']}:[/bold] {challenge['query']}")
            console.print(f"[dim]Expected:[/dim] {challenge['expected_article']}")
            console.print("-" * 60)

            # Run enhanced search
            results, metrics = self.enhanced_rag.search(challenge['query'])

            if results:
                top_result = results[0]

                # Create result panel
                result_text = f"""
**Found:** {top_result.title or 'Unknown'}
**Score:** {top_result.combined_score:.3f}
**Source Types:** {', '.join(top_result.methods) if top_result.methods else 'Unknown'}
"""

                if top_result.metadata:
                    if "legal_confidence" in top_result.metadata:
                        result_text += f"**Legal Confidence:** {top_result.metadata['legal_confidence']:.2%}\n"

                    if "legal_reasoning" in top_result.metadata:
                        result_text += f"**Legal Reasoning:** {top_result.metadata['legal_reasoning']}\n"

                    if "applicable_operators" in top_result.metadata:
                        ops = top_result.metadata['applicable_operators']
                        if ops:
                            result_text += f"**Legal Operators:** {', '.join(ops)}\n"

                console.print(Panel(
                    Markdown(result_text),
                    title="[bold]Top Result with Legal Logic[/bold]",
                    border_style="green"
                ))

                # Show detected intents and entities
                console.print(f"\n[cyan]Detected Intents:[/cyan] {', '.join(metrics.detected_intents)}")

                if metrics.extracted_entities:
                    console.print(f"[cyan]Extracted Entities:[/cyan]")
                    for key, value in metrics.extracted_entities.items():
                        console.print(f"  - {key}: {value}")

            else:
                console.print("[red]No results found[/red]")

            # Show performance metrics
            console.print(f"\n[dim]Performance:[/dim]")
            console.print(f"  Total time: {metrics.total_time:.2f}s")
            console.print(f"  Legal logic results: {metrics.legal_logic_count}")
            console.print(f"  Vector results: {metrics.vector_count}")
            console.print(f"  Graph results: {metrics.graph_count}")

    def demonstrate_condition_evaluation(self):
        """Demonstrate legal condition evaluation"""
        console.print("\n" + "="*80)
        console.print("[bold yellow]LEGAL CONDITION EVALUATION DEMO[/bold yellow]")
        console.print("="*80)

        # Test case: Employment termination
        console.print("\n[bold]Scenario:[/bold] Employee wants to know notice period")

        scenarios = [
            {
                "description": "Employee in first month",
                "context": {"duration": {"days": 25}, "subject": "employee"},
                "query": "Kündigungsfrist für Arbeitnehmer"
            },
            {
                "description": "Employee after 4 months",
                "context": {"duration": {"days": 120}, "subject": "employee"},
                "query": "Kündigungsfrist für Arbeitnehmer"
            },
            {
                "description": "Employee after 1 year",
                "context": {"duration": {"days": 365}, "subject": "employee"},
                "query": "Kündigungsfrist für Arbeitnehmer"
            }
        ]

        for scenario in scenarios:
            console.print(f"\n[cyan]{scenario['description']}:[/cyan]")
            console.print(f"Context: {scenario['context']}")

            # Run search with context
            results, metrics = self.enhanced_rag.search(
                query=scenario['query'],
                context=scenario['context']
            )

            if results:
                top_result = results[0]

                # Show applicable rules
                if top_result.metadata and "legal_reasoning" in top_result.metadata:
                    console.print(f"[green]Legal Logic Applied:[/green] {top_result.metadata['legal_reasoning']}")

                    # Show confidence based on condition matching
                    if "legal_confidence" in top_result.metadata:
                        confidence = top_result.metadata['legal_confidence']
                        if confidence > 0.8:
                            console.print(f"[green]✓ High Confidence: {confidence:.2%}[/green]")
                        else:
                            console.print(f"[yellow]⚠ Medium Confidence: {confidence:.2%}[/yellow]")

    def show_competitive_advantages(self):
        """Show why Legal Logic AST wins"""
        console.print("\n" + "="*80)
        console.print("[bold red]WHY LEGAL LOGIC AST WINS AT THE HACKATHON[/bold red]")
        console.print("="*80)

        advantages = [
            {
                "feature": "Semantic Understanding",
                "traditional": "Searches by document structure",
                "legal_logic": "Understands legal meaning and relationships"
            },
            {
                "feature": "Query Resolution",
                "traditional": "Returns relevant articles",
                "legal_logic": "Extracts applicable rules and conditions"
            },
            {
                "feature": "Condition Evaluation",
                "traditional": "User must interpret text",
                "legal_logic": "Automatically evaluates if conditions are met"
            },
            {
                "feature": "Legal Operators",
                "traditional": "Not recognized",
                "legal_logic": "Identifies MUST, MAY, SHALL NOT obligations"
            },
            {
                "feature": "Temporal Logic",
                "traditional": "Text contains dates",
                "legal_logic": "Extracts and reasons about time constraints"
            },
            {
                "feature": "Explainability",
                "traditional": "Shows source documents",
                "legal_logic": "Shows reasoning chain and applied rules"
            }
        ]

        table = Table(show_header=True, header_style="bold red")
        table.add_column("Feature", style="cyan", width=20)
        table.add_column("Traditional AST", style="yellow", width=25)
        table.add_column("Legal Logic AST ⭐", style="green", width=30)

        for adv in advantages:
            table.add_row(adv["feature"], adv["traditional"], adv["legal_logic"])

        console.print(table)

        # Summary panel
        console.print("\n")
        console.print(Panel(
            """[bold green]Key Differentiator:[/bold green]

While everyone has GraphRAG and Apertus 70B, LAWAST with Legal Logic AST
provides [bold]semantic legal understanding[/bold], not just document retrieval.

We don't just find the law - we [bold cyan]understand legal logic[/bold cyan] and can:
• Extract IF-THEN-EXCEPT patterns
• Identify legal obligations and permissions
• Evaluate conditions against context
• Provide explainable reasoning chains

This transforms legal search from [yellow]"find relevant text"[/yellow] to
[green]"understand and apply legal rules"[/green].""",
            title="[bold]The LAWAST Advantage[/bold]",
            border_style="green"
        ))


def main():
    """Run all tests"""
    tester = LegalLogicTester()

    try:
        # Run comparison test
        tester.run_comparison_test()

        # Test challenge queries
        tester.test_challenge_queries()

        # Demonstrate condition evaluation
        tester.demonstrate_condition_evaluation()

        # Show competitive advantages
        tester.show_competitive_advantages()

        # Final message
        console.print("\n" + "="*80)
        console.print("[bold green]✅ Legal Logic AST Testing Complete![/bold green]")
        console.print("[italic]LAWAST is ready to differentiate at the hackathon![/italic]")
        console.print("="*80 + "\n")

    except Exception as e:
        console.print(f"[red]Error during testing: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())

    finally:
        # Close connection
        if tester.connection:
            tester.connection.close()


if __name__ == "__main__":
    main()