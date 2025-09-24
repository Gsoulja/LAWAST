#!/usr/bin/env python3
"""
LAWAST Quick Start Script
Run this FIRST to set up everything for the hackathon
"""

import os
import json
import shutil
from pathlib import Path

def create_project_structure():
    """Create the folder structure"""
    print("📁 Creating project structure...")

    directories = [
        "src/reasoning",
        "src/ast",
        "src/classification",
        "src/articulation",
        "src/retrieval",
        "src/context",
        "src/data_access",
        "src/core/entities",
        "src/core/use_cases",
        "src/interfaces/cli",
        "data/laws/employment",
        "data/laws/rental",
        "data/laws/credit",
        "data/ast/parsed_trees",
        "data/graph",
        "data/embeddings",
        "data/cache",
        "scripts",
        "tests/scenarios",
        "docs/references"
    ]

    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

        # Create __init__.py for Python packages
        if dir_path.startswith("src/"):
            (Path(dir_path) / "__init__.py").touch()

    print("✅ Project structure created")

def organize_existing_files():
    """Move existing files to proper locations"""
    print("📦 Organizing existing files...")

    moves = {
        "apertus_chat.py": "src/articulation/apertus_client.py",
        "LAW_CLASSIFICATION_SYSTEM.md": "docs/references/",
        "ARTIFICIAL_REASONING_ARCHITECTURE.md": "docs/references/",
        "test_*.py": "tests/"
    }

    for source, dest in moves.items():
        if "*" in source:
            # Handle wildcards
            for file in Path(".").glob(source):
                if file.exists():
                    dest_path = Path(dest) / file.name
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(file), str(dest_path))
                    print(f"  Moved {file} → {dest_path}")
        else:
            if Path(source).exists():
                dest_path = Path(dest)
                if dest.endswith("/"):
                    dest_path = dest_path / source
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(source, str(dest_path))
                print(f"  Moved {source} → {dest_path}")

def create_starter_files():
    """Create essential starter files"""
    print("🚀 Creating starter files...")

    # 1. Main entry point
    main_cli = '''#!/usr/bin/env python3
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
'''

    with open("src/interfaces/cli/main.py", "w") as f:
        f.write(main_cli)

    # 2. Simple Vector RAG
    vector_rag = '''"""Simple Vector RAG for quick start"""

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Tuple

class SimpleVectorRAG:
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.documents = []
        self.embeddings = []

    def index_documents(self, documents: List[dict]):
        """Index documents for retrieval"""
        self.documents = documents
        texts = [doc.get('content', '') for doc in documents]
        self.embeddings = self.embedder.encode(texts)
        print(f"Indexed {len(documents)} documents")

    def search(self, query: str, k: int = 5) -> List[dict]:
        """Search for relevant documents"""
        if not self.documents:
            return []

        query_embedding = self.embedder.encode([query])[0]

        # Compute similarities
        similarities = np.dot(self.embeddings, query_embedding)
        top_k = np.argsort(similarities)[::-1][:k]

        return [self.documents[i] for i in top_k]
'''

    with open("src/retrieval/vector_rag.py", "w") as f:
        f.write(vector_rag)

    # 3. Law classifier
    classifier = '''"""Swiss law classification system"""

LAW_RANGES = {
    "employment": {
        "law": "OR",
        "articles": range(319, 363),
        "title": "Employment Contract"
    },
    "rental": {
        "law": "OR",
        "articles": range(253, 305),
        "title": "Rental and Lease"
    },
    "credit": {
        "law": "OR",
        "articles": range(312, 319),
        "title": "Loan and Credit"
    }
}

def classify_article(law: str, article_num: int) -> str:
    """Classify which domain an article belongs to"""
    if law != "OR":
        return "other"

    for domain, info in LAW_RANGES.items():
        if article_num in info["articles"]:
            return domain

    return "other"

def get_domain_articles(domain: str) -> range:
    """Get article range for a domain"""
    if domain in LAW_RANGES:
        return LAW_RANGES[domain]["articles"]
    return range(0)
'''

    with open("src/classification/sr_classifier.py", "w") as f:
        f.write(classifier)

    print("✅ Starter files created")

def create_makefile():
    """Create Makefile for easy commands"""
    makefile_content = '''# LAWAST Makefile
.PHONY: help setup run test demo clean

help:
	@echo "LAWAST - Swiss Legal AI Assistant"
	@echo "================================="
	@echo "make setup  - Initial setup"
	@echo "make run    - Run CLI"
	@echo "make demo   - Run demo"
	@echo "make test   - Run tests"
	@echo "make clean  - Clean cache"

setup:
	python quick_start.py
	pip install -r requirements.txt

run:
	python -m src.interfaces.cli.main

demo:
	@echo "Demo: Employment termination question"
	python -m src.interfaces.cli.main "Can I fire an employee for theft?"

extract:
	python scripts/extract_target_laws.py

test:
	python -m pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf data/cache/*
'''

    with open("Makefile", "w") as f:
        f.write(makefile_content)

    print("✅ Makefile created")

def create_demo_script():
    """Create a demo script for quick testing"""
    demo = '''#!/usr/bin/env python3
"""Quick demo for hackathon judges"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import track
import time

console = Console()

def demo():
    console.print(Panel.fit(
        "[bold cyan]LAWAST[/bold cyan] - Swiss Legal AI Assistant\\n"
        "Powered by Graph RAG + AST + Apertus",
        border_style="cyan"
    ))

    demos = [
        ("🏢 Employment", "Can I terminate an employee who leaked confidential data?"),
        ("🏠 Rental", "How much can my landlord increase the rent?"),
        ("💳 Credit", "What is the maximum interest rate for consumer loans?")
    ]

    for category, question in demos:
        console.print(f"\\n{category} [bold]Question:[/bold] {question}")

        # Simulate processing
        for step in track(["Analyzing", "Retrieving", "Reasoning"], description="Processing..."):
            time.sleep(0.5)

        console.print("[green]✓[/green] Answer generated (placeholder)\\n")
        console.print("-" * 50)

if __name__ == "__main__":
    demo()
'''

    with open("scripts/demo.py", "w") as f:
        f.write(demo)
    os.chmod("scripts/demo.py", 0o755)

    print("✅ Demo script created")

def main():
    """Run all setup steps"""
    from rich.console import Console
    console = Console()

    console.print("[bold cyan]LAWAST Quick Start Setup[/bold cyan]\n")

    # Run setup steps
    create_project_structure()
    organize_existing_files()
    create_starter_files()
    create_makefile()
    create_demo_script()

    console.print("\n[bold green]✨ Setup complete![/bold green]")
    console.print("\nNext steps:")
    console.print("1. Run: [cyan]make extract[/cyan] - Extract target laws")
    console.print("2. Run: [cyan]make demo[/cyan] - Test demo")
    console.print("3. Start coding in [cyan]src/[/cyan]")

    console.print("\n[yellow]Good luck at the hackathon! 🚀[/yellow]")

if __name__ == "__main__":
    main()