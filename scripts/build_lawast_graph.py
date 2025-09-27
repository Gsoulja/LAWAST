#!/usr/bin/env python3
"""
LAWAST Unified Graph Builder
============================

Consolidated script for building the complete LAWAST knowledge graph including:
- Graph structure (Laws, Articles, Paragraphs)
- AST relationships (Abstract Syntax Tree)
- Vector embeddings for semantic search
- Temporal relationships (versions, validity)
- Legal relationships (references, citations)

Usage:
    python scripts/build_lawast_graph.py [options]

Options:
    --clean              Clean existing data before building
    --skip-download      Skip downloading new data
    --skip-embeddings    Skip generating embeddings
    --workers N          Number of parallel workers (default: 8)
    --batch-size N       Batch size for processing (default: 100)
    --checkpoint         Enable checkpointing for resume capability
    --verbose           Enable verbose output

Example:
    python scripts/build_lawast_graph.py --clean --workers 16
"""

import os
import sys
import time
import json
import argparse
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection, Neo4jConnectionManager
from src.data_access.graph_schema import GraphSchema
from src.data_access.batch_processor import BatchProcessor
from src.data_access.storage_pipeline import Neo4jStoragePipeline, StorageStatistics
from src.data_access.embedding_generator import create_embedding_generator
from src.data_access.schema_mapper import SchemaPropertyMapper, validate_node
from src.parsers.unified_html_parser import UnifiedHtmlParser
from src.extractors.article_extractor import ArticleExtractor
from src.extractors.relationship_extractor import RelationshipExtractor
from src.extractors.property_extractor import (
    FedlexPropertyExtractor,
    extract_law_properties,
    extract_article_multilingual,
    extract_paragraphs_multilingual
)
from src.extractors.legal_logic_extractor import LegalLogicExtractor

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize console for pretty output
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BuildStatistics:
    """Track statistics for the build process"""
    start_time: datetime
    end_time: Optional[datetime] = None
    laws_processed: int = 0
    articles_created: int = 0
    paragraphs_created: int = 0
    subpoints_created: int = 0
    relationships_created: int = 0
    embeddings_generated: int = 0
    legal_logic_extracted: int = 0
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    @property
    def duration(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()


class UnifiedGraphBuilder:
    """Unified builder for complete LAWAST knowledge graph"""

    def __init__(self,
                 workers: int = 8,
                 batch_size: int = 100,
                 checkpoint_enabled: bool = False,
                 verbose: bool = False,
                 strict_schema: bool = False):
        """
        Initialize the unified graph builder.

        Args:
            workers: Number of parallel workers
            batch_size: Batch size for processing
            checkpoint_enabled: Enable checkpointing
            verbose: Enable verbose output
        """
        self.workers = workers
        self.batch_size = batch_size
        self.checkpoint_enabled = checkpoint_enabled
        self.verbose = verbose
        self.strict_schema = strict_schema

        self.connection = None
        self.storage_pipeline = None
        self.embedding_generator = None
        self.property_extractor = FedlexPropertyExtractor()
        self.schema_mapper = SchemaPropertyMapper(strict_mode=strict_schema)
        self.stats = BuildStatistics(start_time=datetime.now())

        # Checkpoint file
        self.checkpoint_file = Path("build_checkpoint.json")
        self.processed_files = set()

    def initialize(self) -> bool:
        """Initialize all required components"""
        console.print("\n[bold cyan]🚀 Initializing LAWAST Graph Builder[/bold cyan]")

        try:
            # 1. Check Neo4j connection
            console.print("  📡 Connecting to Neo4j...", end="")
            self.connection = get_connection()
            if not self.connection.health_check():
                console.print(" [red]✗[/red]")
                return False
            console.print(" [green]✓[/green]")

            # 2. Initialize storage pipeline
            console.print("  📦 Initializing storage pipeline...", end="")
            self.storage_pipeline = Neo4jStoragePipeline(self.connection.driver)
            console.print(" [green]✓[/green]")

            # 3. Initialize embedding generator
            console.print("  🧮 Initializing embedding generator...", end="")
            self.embedding_generator = create_embedding_generator()
            console.print(" [green]✓[/green]")

            # 4. Load checkpoint if exists
            if self.checkpoint_enabled and self.checkpoint_file.exists():
                console.print("  📂 Loading checkpoint...", end="")
                self.load_checkpoint()
                console.print(f" [green]✓[/green] ({len(self.processed_files)} files already processed)")

            console.print("[green]✅ Initialization complete![/green]\n")
            return True

        except Exception as e:
            console.print(f"\n[red]❌ Initialization failed: {str(e)}[/red]")
            return False

    def clean_database(self):
        """Clean existing data from Neo4j"""
        console.print("\n[bold yellow]🧹 Cleaning existing data...[/bold yellow]")

        if not Confirm.ask("  ⚠️  This will delete ALL data in Neo4j. Continue?", default=False):
            console.print("  [cyan]Skipping cleanup[/cyan]")
            return

        try:
            with self.connection.driver.session() as session:
                # Delete all nodes and relationships
                session.run("MATCH (n) DETACH DELETE n")

                # Get counts to verify
                result = session.run("MATCH (n) RETURN count(n) as count")
                count = result.single()["count"]

                if count == 0:
                    console.print("  [green]✓ Database cleaned successfully[/green]")
                else:
                    console.print(f"  [yellow]⚠ {count} nodes still remain[/yellow]")

        except Exception as e:
            console.print(f"  [red]✗ Cleanup failed: {str(e)}[/red]")
            self.stats.errors.append(f"Cleanup error: {str(e)}")

    def setup_taxonomy(self):
        """Setup Swiss legal taxonomy structure"""
        console.print("\n[bold cyan]🏛️ Setting up Swiss Legal Taxonomy...[/bold cyan]")

        try:
            with self.connection.driver.session() as session:
                # Create SR taxonomy domains
                sr_domains = [
                    ("1", "Staat - Volk - Behörden", "État - Peuple - Autorités"),
                    ("1.0", "Bundesverfassung", "Constitution fédérale"),
                    ("1.0.1", "Bundesverfassung der Schweizerischen Eidgenossenschaft", "Constitution fédérale de la Confédération suisse"),
                    ("2", "Privatrecht - Zivilrechtspflege - Vollstreckung", "Droit privé - Procédure civile - Exécution"),
                    ("3", "Strafrecht - Strafrechtspflege - Strafvollzug", "Droit pénal - Procédure pénale - Exécution"),
                    ("4", "Schule - Wissenschaft - Kultur", "École - Science - Culture"),
                    ("5", "Landesverteidigung", "Défense nationale"),
                    ("6", "Finanzen", "Finances"),
                    ("7", "Öffentliche Werke - Energie - Verkehr", "Travaux publics - Énergie - Transports"),
                    ("8", "Gesundheit - Arbeit - Soziale Sicherheit", "Santé - Travail - Sécurité sociale"),
                    ("9", "Wirtschaft - Technische Zusammenarbeit", "Économie - Coopération technique"),
                ]

                for sr_num, title_de, title_fr in sr_domains:
                    session.run("""
                        MERGE (d:Domain {sr_number: $sr})
                        SET d.title_de = $title_de,
                            d.title_fr = $title_fr,
                            d.type = 'domain'
                    """, sr=sr_num, title_de=title_de, title_fr=title_fr)

                console.print("  ✓ Created SR taxonomy domains")

                # Special handling for SR 101 (Bundesverfassung)
                session.run("""
                    MERGE (bv:Law {sr_number: '101'})
                    SET bv.title_de = 'Bundesverfassung der Schweizerischen Eidgenossenschaft',
                        bv.title_fr = 'Constitution fédérale de la Confédération suisse',
                        bv.title_it = 'Costituzione federale della Confederazione Svizzera',
                        bv.abbreviation_de = 'BV',
                        bv.abbreviation_fr = 'Cst.',
                        bv.abbreviation_it = 'Cost.',
                        bv.date_document = '1999-04-18',
                        bv.date_entry_in_force = '2000-01-01',
                        bv.in_force = true,
                        bv.uri = 'https://fedlex.data.admin.ch/eli/cc/1999/404'
                """)
                console.print("  ✓ Created SR 101 (Bundesverfassung) entry")

        except Exception as e:
            console.print(f"  [yellow]⚠ Taxonomy setup warning: {str(e)}[/yellow]")
            self.stats.warnings.append(f"Taxonomy setup: {str(e)}")

    def setup_schema(self):
        """Setup Neo4j schema with indexes and constraints"""
        console.print("\n[bold cyan]📋 Setting up database schema...[/bold cyan]")

        schema_queries = [
            # Constraints
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Law) REQUIRE l.uri IS UNIQUE", "Law uniqueness"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Article) REQUIRE a.uri IS UNIQUE", "Article uniqueness"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paragraph) REQUIRE p.uri IS UNIQUE", "Paragraph uniqueness"),

            # Indexes for search
            ("CREATE INDEX IF NOT EXISTS FOR (l:Law) ON (l.sr_number)", "SR number index"),
            ("CREATE INDEX IF NOT EXISTS FOR (a:Article) ON (a.number_normalized)", "Article number index"),
            ("CREATE INDEX IF NOT EXISTS FOR (l:Law) ON (l.in_force)", "In-force index"),

            # Full-text search indexes
            ("CREATE FULLTEXT INDEX lawTitleSearch IF NOT EXISTS FOR (l:Law) ON EACH [l.title_de, l.title_fr, l.title_it]", "Law title search"),
            ("CREATE FULLTEXT INDEX articleContentSearch IF NOT EXISTS FOR (a:Article) ON EACH [a.content_full, a.content_preview]", "Article content search"),

            # Vector indexes for embeddings
            ("CREATE VECTOR INDEX lawEmbeddings IF NOT EXISTS FOR (l:Law) ON l.embedding OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}", "Law embeddings"),
            ("CREATE VECTOR INDEX articleEmbeddings IF NOT EXISTS FOR (a:Article) ON a.embedding OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}", "Article embeddings"),
            ("CREATE VECTOR INDEX paragraphEmbeddings IF NOT EXISTS FOR (p:Paragraph) ON p.embedding OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}", "Paragraph embeddings"),
            ("CREATE VECTOR INDEX legalLogicEmbeddings IF NOT EXISTS FOR (ll:LegalLogic) ON ll.embedding OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}", "Legal Logic embeddings"),
        ]

        with self.connection.driver.session() as session:
            for query, description in schema_queries:
                try:
                    console.print(f"  📌 {description}...", end="")
                    session.run(query)
                    console.print(" [green]✓[/green]")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        console.print(" [yellow]exists[/yellow]")
                    else:
                        console.print(f" [red]✗ {str(e)}[/red]")
                        self.stats.warnings.append(f"Schema setup: {description} - {str(e)}")

    def download_data(self, sr_filter: str = None) -> List[Path]:
        """Download or locate Fedlex data files

        Args:
            sr_filter: Optional SR number filter (e.g., "101" for Bundesverfassung)
        """
        console.print("\n[bold cyan]📥 Locating data files...[/bold cyan]")

        # Check both possible locations for fedlex data
        data_dirs = [
            Path("fedlex/eli/cc"),  # Local fedlex repo
            Path("data/fedlex"),     # Alternative location
            Path("fedlex-assets")    # Fedlex assets
        ]

        json_files = []
        for data_dir in data_dirs:
            if data_dir.exists():
                found = list(data_dir.glob("**/*.json"))
                json_files.extend(found)
                if found:
                    console.print(f"  Found {len(found)} JSON files in {data_dir}")

        # For SR 101 specifically, look for the Constitution
        if sr_filter == "101":
            constitution_paths = [
                Path("fedlex/eli/cc/1999/404.json"),  # Main Constitution file
                Path("fedlex/eli/cc/1999/404/20240101.json"),  # Latest version
                Path("fedlex/eli/cc/1999/404/20240303.json"),  # Most recent update
            ]

            json_files = []
            for path in constitution_paths:
                if path.exists():
                    json_files.append(path)
                    console.print(f"  ✓ Found Constitution at: {path}")

            if not json_files:
                console.print("  [yellow]SR 101 (Bundesverfassung) not found in local data[/yellow]")

        # Filter by SR number if specified
        if sr_filter and sr_filter != "101":
            # For non-101 SR numbers, do the regular filtering
            filtered_files = []
            for f in json_files:
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        sr_num = self.extract_sr_number(data)
                        if sr_num and sr_num.startswith(sr_filter):
                            filtered_files.append(f)
                except:
                    pass

            console.print(f"  Filtered to {len(filtered_files)} files matching SR {sr_filter}")
            json_files = filtered_files
        elif sr_filter == "101":
            # For SR 101, we already have the correct files
            console.print(f"  Using {len(json_files)} Constitution files")

        # Filter out already processed files if checkpoint enabled
        if self.checkpoint_enabled and self.processed_files:
            json_files = [f for f in json_files if str(f) not in self.processed_files]
            console.print(f"  Filtering to {len(json_files)} unprocessed files")

        return json_files

    def download_sr_101(self):
        """Download Swiss Federal Constitution (SR 101) from Fedlex"""
        console.print("  📥 Downloading SR 101 (Bundesverfassung)...")

        import requests
        from pathlib import Path

        # Fedlex API endpoints for SR 101
        base_url = "https://fedlex.data.admin.ch/eli/cc/1999/404"

        # Create data directory
        data_dir = Path("data/fedlex/sr_101")
        data_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Download main document
            response = requests.get(f"{base_url}/data.json")
            if response.status_code == 200:
                with open(data_dir / "sr_101.json", 'w', encoding='utf-8') as f:
                    json.dump(response.json(), f, indent=2, ensure_ascii=False)
                console.print("    ✓ Downloaded SR 101 main document")

                # Try to get all versions and articles
                data = response.json()

                # Download current consolidated version
                cons_url = f"{base_url}/20240101/data.json"  # Latest version
                response = requests.get(cons_url)
                if response.status_code == 200:
                    with open(data_dir / "sr_101_current.json", 'w', encoding='utf-8') as f:
                        json.dump(response.json(), f, indent=2, ensure_ascii=False)
                    console.print("    ✓ Downloaded current consolidated version")

            else:
                console.print(f"    ✗ Failed to download SR 101: {response.status_code}")

        except Exception as e:
            console.print(f"    ✗ Download error: {str(e)}")

    def extract_sr_number(self, data: Dict) -> Optional[str]:
        """Extract SR number from JSON data"""
        try:
            import re

            # Try different paths where SR number might be
            paths = [
                ['data', 'attributes', 'eli'],
                ['included', 0, 'attributes', 'eli'],
                ['data', 'attributes', 'classified_by_taxonomic_plan_text']
            ]

            for path in paths:
                value = data
                for key in path:
                    if isinstance(value, dict):
                        value = value.get(key)
                    elif isinstance(value, list) and isinstance(key, int):
                        if key < len(value):
                            value = value[key]
                    else:
                        break

                if value and isinstance(value, str):
                    # Extract SR number from various formats
                    match = re.search(r'SR\s*(\d+(?:\.\d+)*)', value)
                    if not match:
                        match = re.search(r'/(\d+(?:\.\d+)*)', value)
                    if match:
                        return match.group(1)

            # Search in included items for classified_by_taxonomic_plan_text
            for item in data.get('included', []):
                if isinstance(item, dict) and 'attributes' in item:
                    attrs = item['attributes']

                    # Check classified_by_taxonomic_plan_text
                    class_text = attrs.get('classified_by_taxonomic_plan_text', '')
                    if class_text:
                        match = re.search(r'SR\s+(\d+(?:\.\d+)*)', class_text)
                        if match:
                            return match.group(1)

                    # Check classifiedByTaxonomyEntryLabel
                    label = attrs.get('classifiedByTaxonomyEntryLabel', {})
                    if isinstance(label, dict):
                        for lang in ['de', 'fr', 'it']:
                            if lang in label:
                                match = re.search(r'S[R|S]\s+(\d+(?:\.\d+)*)', str(label[lang]))
                                if match:
                                    return match.group(1)

                    # Check title for Obligationenrecht
                    title = attrs.get('title', {})
                    if isinstance(title, dict) and 'xsd:string' in title:
                        title_str = title['xsd:string']
                        if 'Obligationenrecht' in title_str:
                            return '220'
                    elif isinstance(title, str) and 'Obligationenrecht' in title:
                        return '220'

            # Try to get from title
            title = data.get('data', {}).get('attributes', {}).get('title_de', '')
            if 'Bundesverfassung' in title:
                return '101'

            # Check for Obligationenrecht (SR 220)
            if 'Obligationenrecht' in title or 'Code des obligations' in data.get('data', {}).get('attributes', {}).get('title_fr', ''):
                return '220'

            # Last resort: search entire JSON for SR number
            json_str = str(data)
            if 'Obligationenrecht' in json_str and 'SR 220' in json_str:
                return '220'
            if 'Bundesverfassung' in json_str and 'SR 101' in json_str:
                return '101'

        except:
            pass
        return None

    def process_law_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single law JSON file with complete article extraction"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract law metadata
            law_uri = data.get('data', {}).get('uri', '')
            if not law_uri:
                # Try alternative location
                law_uri = data.get('data', {}).get('attributes', {}).get('eli', '')
            if not law_uri:
                return {'status': 'skipped', 'reason': 'No URI found'}

            # Get SR number
            sr_number = self.extract_sr_number(data)

            # Special handling for SR 101 to ensure complete extraction
            if sr_number and sr_number.startswith('101'):
                return self.process_bundesverfassung(data, file_path)

            # For now, process all laws with the bundesverfassung method
            # TODO: Implement general law processing
            return self.process_bundesverfassung(data, file_path)

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'file': str(file_path)
            }

    def process_bundesverfassung(self, data: Dict, file_path: Path) -> Dict[str, Any]:
        """Process law with full language and version support"""
        console.print("    [cyan]📜 Processing law with versions and language variants...[/cyan]")

        stats = {
            'laws_created': 0,
            'versions_created': 0,
            'language_variants_created': 0,
            'articles_created': 0,
            'paragraphs_created': 0,
            'subpoints_created': 0,
            'relationships_created': 0
        }

        try:
            # Use the new extraction method that handles versions and languages
            extractor = FedlexPropertyExtractor()
            law_data = extractor.extract_law_with_versions_and_languages(data, file_path)

            if not law_data['law_node']:
                console.print("      [red]Failed to extract law data[/red]")
                return {'status': 'error', 'error': 'No law data extracted'}

            law_uri = law_data['law_node']['uri']

            with self.connection.driver.session() as session:
                # Step 0: Create hierarchical structure nodes (Domain, Book, Chapter, Section, Act)
                hierarchy = law_data.get('hierarchical_structure', {})

                # Create Domain node if exists
                if hierarchy.get('domain'):
                    domain_props = hierarchy['domain']
                    session.run("""
                        MERGE (d:Domain {uri: $uri})
                        SET d += $props
                    """, uri=domain_props['uri'], props=domain_props)
                    stats['relationships_created'] += 1

                # Create Book node if exists
                if hierarchy.get('book'):
                    book_props = hierarchy['book']
                    book_uri = f"{law_uri}/book"
                    book_props['uri'] = book_uri
                    session.run("""
                        MERGE (b:Book {uri: $uri})
                        SET b += $props
                    """, uri=book_uri, props=book_props)

                    # Link Book to Domain if domain exists
                    if hierarchy.get('domain'):
                        session.run("""
                            MATCH (d:Domain {uri: $domain_uri})
                            MATCH (b:Book {uri: $book_uri})
                            MERGE (d)-[:HAS_CHILD]->(b)
                        """, domain_uri=hierarchy['domain']['uri'], book_uri=book_uri)
                        stats['relationships_created'] += 1

                # Create Chapter node if exists
                if hierarchy.get('chapter'):
                    chapter_props = hierarchy['chapter']
                    chapter_uri = f"{law_uri}/chapter_{chapter_props.get('number', '1')}"
                    chapter_props['uri'] = chapter_uri
                    session.run("""
                        MERGE (c:Chapter {uri: $uri})
                        SET c += $props
                    """, uri=chapter_uri, props=chapter_props)

                    # Link Chapter to Book or Law
                    if hierarchy.get('book'):
                        session.run("""
                            MATCH (b:Book {uri: $book_uri})
                            MATCH (c:Chapter {uri: $chapter_uri})
                            MERGE (b)-[:HAS_CHILD]->(c)
                        """, book_uri=f"{law_uri}/book", chapter_uri=chapter_uri)
                    else:
                        session.run("""
                            MATCH (l:Law {uri: $law_uri})
                            MATCH (c:Chapter {uri: $chapter_uri})
                            MERGE (l)-[:HAS_CHILD]->(c)
                        """, law_uri=law_uri, chapter_uri=chapter_uri)
                    stats['relationships_created'] += 1

                # Create Section node if exists
                if hierarchy.get('section'):
                    section_props = hierarchy['section']
                    section_uri = f"{law_uri}/section_{section_props.get('number', '1')}"
                    section_props['uri'] = section_uri
                    session.run("""
                        MERGE (s:Section {uri: $uri})
                        SET s += $props
                    """, uri=section_uri, props=section_props)

                    # Link Section to Chapter or Law
                    if hierarchy.get('chapter'):
                        session.run("""
                            MATCH (c:Chapter {uri: $chapter_uri})
                            MATCH (s:Section {uri: $section_uri})
                            MERGE (c)-[:HAS_CHILD]->(s)
                        """, chapter_uri=f"{law_uri}/chapter_{hierarchy['chapter'].get('number', '1')}",
                            section_uri=section_uri)
                    else:
                        session.run("""
                            MATCH (l:Law {uri: $law_uri})
                            MATCH (s:Section {uri: $section_uri})
                            MERGE (l)-[:HAS_CHILD]->(s)
                        """, law_uri=law_uri, section_uri=section_uri)
                    stats['relationships_created'] += 1

                # Create Act node if exists
                if hierarchy.get('act'):
                    act_props = hierarchy['act']
                    session.run("""
                        MERGE (a:Act {uri: $uri})
                        SET a += $props
                    """, uri=act_props['uri'], props=act_props)

                    # Link Act to Law with AMENDS relationship
                    session.run("""
                        MATCH (a:Act {uri: $act_uri})
                        MATCH (l:Law {uri: $law_uri})
                        MERGE (a)-[:AMENDS]->(l)
                    """, act_uri=act_props['uri'], law_uri=law_uri)
                    stats['relationships_created'] += 1

                # Step 1: Create base Law node with multilingual titles
                # Aggregate titles from all language variants
                law_node_props = law_data['law_node'].copy()
                for lang_variant in law_data['language_variants']:
                    lang = lang_variant['language']
                    if lang_variant.get('title'):
                        law_node_props[f'title_{lang}'] = lang_variant['title']
                    if lang_variant.get('abbreviation'):
                        law_node_props[f'abbreviation_{lang}'] = lang_variant['abbreviation']

                # Also preserve enforcement status on Law node
                if law_data['language_variants']:
                    first_variant = law_data['language_variants'][0]
                    law_node_props['in_force'] = first_variant.get('in_force', True)
                    law_node_props['status'] = first_variant.get('status', 'unknown')
                    law_node_props['basic_act'] = first_variant.get('basic_act')
                    law_node_props['classified_by_taxonomy'] = first_variant.get('classified_by_taxonomy')
                    law_node_props['type_document'] = first_variant.get('type_document')

                session.run("""
                    MERGE (l:Law {uri: $uri})
                    SET l += $props
                """, uri=law_uri, props=law_node_props)
                stats['laws_created'] += 1

                # Link Law to Domain if domain exists
                if hierarchy.get('domain'):
                    session.run("""
                        MATCH (d:Domain {uri: $domain_uri})
                        MATCH (l:Law {uri: $law_uri})
                        MERGE (d)-[:HAS_CHILD]->(l)
                    """, domain_uri=hierarchy['domain']['uri'], law_uri=law_uri)
                    stats['relationships_created'] += 1

                # Link Law to Section if section exists (Law belongs to section)
                if hierarchy.get('section'):
                    session.run("""
                        MATCH (s:Section {uri: $section_uri})
                        MATCH (l:Law {uri: $law_uri})
                        MERGE (s)-[:HAS_CHILD]->(l)
                    """, section_uri=f"{law_uri}/section_{hierarchy['section'].get('number', '1')}",
                        law_uri=law_uri)
                    stats['relationships_created'] += 1

                # Step 2: Create Version nodes
                for version in law_data['versions']:
                    session.run("""
                        MERGE (v:Version {uri: $uri})
                        SET v += $props
                    """, uri=version['uri'], props=version)

                    # Link version to law
                    session.run("""
                        MATCH (l:Law {uri: $law_uri})
                        MATCH (v:Version {uri: $version_uri})
                        MERGE (l)-[:HAS_VERSION]->(v)
                    """, law_uri=law_uri, version_uri=version['uri'])

                    stats['versions_created'] += 1
                    stats['relationships_created'] += 1

                # Step 3: Create Language Variant nodes
                for lang_variant in law_data['language_variants']:
                    session.run("""
                        MERGE (lv:LawLanguageVariant {uri: $uri})
                        SET lv += $props
                    """, uri=lang_variant['uri'], props=lang_variant)

                    # Link language variant to version
                    session.run("""
                        MATCH (v:Version {uri: $version_uri})
                        MATCH (lv:LawLanguageVariant {uri: $lv_uri})
                        MERGE (v)-[:HAS_LANGUAGE {language: $lang}]->(lv)
                    """, version_uri=lang_variant['version_uri'],
                        lv_uri=lang_variant['uri'],
                        lang=lang_variant['language'])

                    stats['language_variants_created'] += 1
                    stats['relationships_created'] += 1

                # Find fedlex-assets path
                fedlex_path = Path('fedlex-assets')
                if not fedlex_path.exists():
                    fedlex_path = Path('fedlex')

                # Step 4: Process articles for each language variant
                articles_to_process = self.extract_bv_articles(data)

                for lang_variant in law_data['language_variants']:
                    lang = lang_variant['language']

                    for article_data in articles_to_process:
                        article_num = article_data.get('number')

                        # Extract article for this specific language
                        article_props = extractor.extract_articles_for_language_variant(
                            int(article_num) if article_num and article_num.isdigit() else 1,
                            lang_variant['uri'],
                            lang,
                            fedlex_path
                        )

                        # Skip if no article data for this language
                        if not article_props or not article_props.get('uri'):
                            continue

                        # Validate article properties
                        article_validation = self.schema_mapper.validate_and_map('Article', article_props)
                        if not article_validation.valid and self.strict_schema:
                            console.print(f"      [yellow]Article {article_num} ({lang}) validation warning: {article_validation.errors}[/yellow]")

                        # Create article node
                        session.run("""
                            MERGE (a:Article {uri: $uri})
                            SET a += $props
                        """, uri=article_props['uri'], props=article_validation.mapped_properties)

                        # Link article to language variant (not directly to law!)
                        session.run("""
                            MATCH (lv:LawLanguageVariant {uri: $lv_uri})
                            MATCH (a:Article {uri: $article_uri})
                            MERGE (lv)-[:HAS_ARTICLE]->(a)
                        """, lv_uri=lang_variant['uri'], article_uri=article_props['uri'])

                        stats['articles_created'] += 1
                        stats['relationships_created'] += 1

                        # Step 4.5: Extract Legal Logic for SR 101 articles
                        # Get SR number from law data
                        law_sr_number = law_data['law_node'].get('sr_number', '')
                        if law_sr_number and law_sr_number.startswith('101') and article_props.get('content_full'):
                            console.print(f"        [cyan]⚖️ Extracting legal logic for Art. {article_num} ({lang})...[/cyan]")

                            # Initialize legal logic extractor for this language
                            logic_extractor = LegalLogicExtractor(language=lang if lang in ['de', 'fr', 'it'] else 'de')

                            # Extract legal logic from article content
                            article_ref = f"Art. {article_num} BV"
                            legal_rule = logic_extractor.extract_legal_logic(
                                article_props['content_full'],
                                article_ref
                            )

                            # Store legal logic in Neo4j
                            if legal_rule.conditions or legal_rule.consequences or legal_rule.exceptions:
                                # Create LegalLogic node
                                logic_props = {
                                    'uri': f"{article_props['uri']}/logic",
                                    'article_ref': article_ref,
                                    'language': lang,
                                    'condition_count': len(legal_rule.conditions),
                                    'consequence_count': len(legal_rule.consequences),
                                    'exception_count': len(legal_rule.exceptions)
                                }

                                # Store conditions as array
                                if legal_rule.conditions:
                                    logic_props['conditions'] = [c.text for c in legal_rule.conditions]
                                    logic_props['condition_types'] = [c.node_type.value for c in legal_rule.conditions]

                                # Store consequences with operators
                                if legal_rule.consequences:
                                    logic_props['consequences'] = [c.text for c in legal_rule.consequences]
                                    logic_props['operators'] = [c.operator.value if c.operator else 'NONE' for c in legal_rule.consequences]

                                    # Extract temporal constraints if any
                                    temporal_constraints = []
                                    for c in legal_rule.consequences:
                                        if c.temporal:
                                            temporal_constraints.append(f"{c.temporal['value']} {c.temporal['unit']}")
                                    if temporal_constraints:
                                        logic_props['temporal_constraints'] = temporal_constraints

                                # Store exceptions
                                if legal_rule.exceptions:
                                    logic_props['exceptions'] = [e.text for e in legal_rule.exceptions]

                                # Generate embedding for legal logic
                                # Create a text representation for embedding
                                logic_text_parts = []
                                if legal_rule.conditions:
                                    logic_text_parts.append(f"IF: {'; '.join([c.text for c in legal_rule.conditions])}")
                                if legal_rule.consequences:
                                    logic_text_parts.append(f"THEN: {'; '.join([c.text for c in legal_rule.consequences])}")
                                if legal_rule.exceptions:
                                    logic_text_parts.append(f"EXCEPT: {'; '.join([e.text for e in legal_rule.exceptions])}")

                                logic_text = " ".join(logic_text_parts)

                                # Generate embedding if we have content
                                if logic_text and self.embedding_generator:
                                    try:
                                        logic_embedding = self.embedding_generator.generate_embedding(logic_text)
                                        logic_props['embedding'] = logic_embedding
                                        console.print(f"          ✓ Generated embedding for legal logic")
                                    except Exception as e:
                                        console.print(f"          [yellow]⚠ Could not generate embedding: {str(e)}[/yellow]")

                                # Create the LegalLogic node
                                session.run("""
                                    MERGE (ll:LegalLogic {uri: $uri})
                                    SET ll += $props
                                """, uri=logic_props['uri'], props=logic_props)

                                # Link LegalLogic to Article
                                session.run("""
                                    MATCH (a:Article {uri: $article_uri})
                                    MATCH (ll:LegalLogic {uri: $logic_uri})
                                    MERGE (a)-[:HAS_LEGAL_LOGIC]->(ll)
                                """, article_uri=article_props['uri'], logic_uri=logic_props['uri'])

                                stats['relationships_created'] += 1
                                self.stats.legal_logic_extracted += 1

                                # Log extraction summary
                                console.print(f"          ✓ Extracted: {logic_props['condition_count']} conditions, "
                                            f"{logic_props['consequence_count']} consequences, "
                                            f"{logic_props['exception_count']} exceptions")

                        # Step 5: Extract paragraphs for this article
                        if article_props.get('content_full'):
                            paragraphs = extractor.extract_paragraphs_for_article(
                                article_props['uri'],
                                article_props['content_full'],
                                lang
                            )

                            for para_props in paragraphs:
                                # Validate paragraph properties
                                para_validation = self.schema_mapper.validate_and_map('Paragraph', para_props)
                                if not para_validation.valid and self.strict_schema:
                                    console.print(f"      [yellow]Paragraph validation warning: {para_validation.errors}[/yellow]")

                                # Create paragraph node
                                session.run("""
                                    MERGE (p:Paragraph {uri: $uri})
                                    SET p += $props
                                """, uri=para_props['uri'], props=para_validation.mapped_properties)

                                # Link paragraph to article
                                session.run("""
                                    MATCH (a:Article {uri: $article_uri})
                                    MATCH (p:Paragraph {uri: $para_uri})
                                    MERGE (a)-[:HAS_PARAGRAPH]->(p)
                                """, article_uri=article_props['uri'], para_uri=para_props['uri'])

                                stats['paragraphs_created'] += 1
                                stats['relationships_created'] += 1

                                # Step 6: Extract subpoints if paragraph has them
                                if para_props.get('has_subpoints', False):
                                    subpoints = extractor.extract_subpoints_from_paragraph(
                                        para_props['uri'],
                                        para_props['text'],
                                        lang
                                    )

                                    for subpoint_props in subpoints:
                                        # Create subpoint node
                                        session.run("""
                                            MERGE (s:Subpoint {uri: $uri})
                                            SET s += $props
                                        """, uri=subpoint_props['uri'], props=subpoint_props)

                                        # Link subpoint to paragraph
                                        session.run("""
                                            MATCH (p:Paragraph {uri: $para_uri})
                                            MATCH (s:Subpoint {uri: $subpoint_uri})
                                            MERGE (p)-[:HAS_SUBPOINT]->(s)
                                        """, para_uri=para_props['uri'], subpoint_uri=subpoint_props['uri'])

                                        stats['subpoints_created'] += 1
                                        stats['relationships_created'] += 1


        except Exception as e:
            console.print(f"      [red]Error processing law: {str(e)}[/red]")
            self.stats.errors.append(f"Law processing: {str(e)}")
            return {'status': 'error', 'error': str(e)}

        return {
            'status': 'success',
            'uri': law_uri,
            'sr_number': law_data['law_node'].get('sr_number', ''),
            'laws': stats['laws_created'],
            'versions': stats['versions_created'],
            'language_variants': stats['language_variants_created'],
            'articles': stats['articles_created'],
            'paragraphs': stats['paragraphs_created'],
            'subpoints': stats['subpoints_created'],
            'relationships': stats['relationships_created']
        }

    def extract_bv_articles(self, data: Dict) -> List[Dict]:
        """Extract all articles from Bundesverfassung HTML files"""
        import re
        from bs4 import BeautifulSoup

        # Find the HTML file for Constitution
        html_paths = [
            Path("fedlex-assets/eli/cc/1999/404/20240101/de/html/fedlex-data-admin-ch-eli-cc-1999-404-20240101-de-html.html"),
            Path("fedlex-assets/eli/cc/1999/404/20220213/de/html/fedlex-data-admin-ch-eli-cc-1999-404-20220213-de-html.html"),
        ]

        # Find first existing HTML file
        html_file = None
        for path in html_paths:
            if path.exists():
                html_file = path
                break

        if not html_file:
            # Try to find any German HTML file
            html_files = list(Path("fedlex-assets/eli/cc/1999/404").glob("*/de/html/*-de-html.html"))
            if html_files:
                html_file = html_files[0]

        if not html_file or not html_file.exists():
            console.print("      [yellow]No HTML file found for BV, using minimal articles[/yellow]")
            return self.get_minimal_bv_articles()

        console.print(f"      [cyan]Extracting BV from HTML: {html_file.name}[/cyan]")

        articles = []

        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'lxml')

            article_elements = soup.find_all('article')

            for article_elem in article_elements:
                # Extract article number and title
                art_pattern = re.compile(r'Art\.\s+(\d+[a-z]?)', re.I)

                # Find article number
                for elem in article_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div']):
                    text = elem.get_text()
                    match = art_pattern.search(text)
                    if match:
                        article_num = match.group(1)

                        # Skip if not in valid range (1-197 + some with suffixes)
                        base_num = int(article_num.rstrip('abcd')) if article_num.rstrip('abcd').isdigit() else 999
                        if base_num > 200:
                            break

                        # Extract title
                        title_text = text[match.end():].strip()
                        title_text = re.sub(r'\d+$', '', title_text).strip()  # Remove footnotes

                        # Extract content
                        content_parts = []
                        for p_elem in article_elem.find_all(['p', 'div']):
                            p_text = p_elem.get_text().strip()
                            if p_text and not art_pattern.match(p_text):
                                content_parts.append(p_text)

                        content = ' '.join(content_parts)

                        articles.append({
                            'number': article_num,
                            'title': title_text,
                            'content': content
                        })
                        break

            console.print(f"      [green]Extracted {len(articles)} articles from HTML[/green]")

        except Exception as e:
            console.print(f"      [yellow]HTML parsing failed: {e}, using minimal articles[/yellow]")
            return self.get_minimal_bv_articles()

        return articles if articles else self.get_minimal_bv_articles()

    def get_minimal_bv_articles(self) -> List[Dict]:
        """Get minimal set of BV articles for fallback"""
        return [
            {'number': '1', 'title': 'Schweizerische Eidgenossenschaft',
             'content': 'Das Schweizervolk und die Kantone, in Verantwortung gegenüber der Schöpfung...'},
            {'number': '16', 'title': 'Meinungs- und Informationsfreiheit',
             'content': '1. Die Meinungs- und Informationsfreiheit ist gewährleistet. 2. Jede Person hat das Recht, ihre Meinung frei zu bilden und sie ungehindert zu äussern und zu verbreiten. 3. Jede Person hat das Recht, Informationen frei zu empfangen, aus allgemein zugänglichen Quellen zu beschaffen und zu verbreiten.'},
        ]

    def extract_paragraphs(self, content: str) -> List[str]:
        """Extract paragraphs from article content"""
        if not content:
            return []

        # Split by numbered paragraphs (1. 2. 3. etc)
        import re
        paragraphs = re.split(r'\d+\.\s+', content)

        # Clean and filter
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # If no numbered paragraphs, treat whole content as one paragraph
        if not paragraphs:
            paragraphs = [content.strip()]

        return paragraphs

    def build_graph_structure(self, json_files: List[Path]):
        """Build the basic graph structure from JSON files"""
        console.print("\n[bold cyan]🏗️  Building Graph Structure[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:

            task = progress.add_task(
                f"Processing {len(json_files)} files...",
                total=len(json_files)
            )

            # Process files in batches
            batch_results = []
            for i in range(0, len(json_files), self.batch_size):
                batch = json_files[i:i+self.batch_size]

                # Process batch in parallel
                with ThreadPoolExecutor(max_workers=self.workers) as executor:
                    futures = [executor.submit(self.process_law_file, f) for f in batch]

                    for future in as_completed(futures):
                        result = future.result()
                        batch_results.append(result)

                        if result['status'] == 'success':
                            self.stats.laws_processed += 1
                            self.stats.articles_created += result.get('articles', 0)
                            self.stats.paragraphs_created += result.get('paragraphs', 0)
                            self.stats.subpoints_created += result.get('subpoints', 0)
                            self.stats.relationships_created += result.get('relationships', 0)

                            # Mark file as processed
                            if self.checkpoint_enabled:
                                self.processed_files.add(str(result.get('file', '')))

                        elif result['status'] == 'error':
                            self.stats.errors.append(result['error'])

                        progress.advance(task)

                # Save checkpoint after each batch
                if self.checkpoint_enabled:
                    self.save_checkpoint()

        # Print summary
        console.print(f"\n  📊 Graph Structure Summary:")
        console.print(f"     Laws: {self.stats.laws_processed}")
        console.print(f"     Articles: {self.stats.articles_created}")
        console.print(f"     Paragraphs: {self.stats.paragraphs_created}")
        console.print(f"     Subpoints: {self.stats.subpoints_created}")
        console.print(f"     Legal Logic: {self.stats.legal_logic_extracted}")
        console.print(f"     Relationships: {self.stats.relationships_created}")

    def build_ast_relationships(self):
        """Build Abstract Syntax Tree relationships"""
        console.print("\n[bold cyan]🌳 Building AST Relationships[/bold cyan]")

        try:
            with self.connection.driver.session() as session:
                # Create hierarchical relationships
                queries = [
                    # Law -> Version relationships
                    ("""
                    MATCH (l:Law), (v:Version)
                    WHERE v.law_uri = l.uri
                    MERGE (l)-[:HAS_VERSION]->(v)
                    RETURN count(*) as count
                    """, "Law-Version"),

                    # Version REPLACES relationships (temporal ordering)
                    ("""
                    MATCH (v1:Version), (v2:Version)
                    WHERE v1.law_uri = v2.law_uri
                    AND v1.version_date < v2.version_date
                    WITH v1, v2
                    ORDER BY v1.version_date DESC, v2.version_date
                    WITH v1.law_uri as law_uri, collect({older: v1, newer: v2}) as pairs
                    UNWIND pairs as pair
                    WITH pair.older as v1, pair.newer as v2
                    WHERE NOT exists((v1)<-[:REPLACES]-(:Version)-[:REPLACES]->(v2))
                    MERGE (v2)-[:REPLACES]->(v1)
                    RETURN count(*) as count
                    """, "Version REPLACES"),

                    # Law -> Article relationships
                    ("""
                    MATCH (l:Law), (a:Article)
                    WHERE a.law_uri = l.uri
                    MERGE (l)-[:HAS_ARTICLE]->(a)
                    RETURN count(*) as count
                    """, "Law-Article"),

                    # Article -> Paragraph relationships
                    ("""
                    MATCH (a:Article), (p:Paragraph)
                    WHERE p.article_uri = a.uri
                    MERGE (a)-[:HAS_PARAGRAPH]->(p)
                    RETURN count(*) as count
                    """, "Article-Paragraph"),

                    # Sequential relationships (with proper type handling)
                    ("""
                    MATCH (a1:Article), (a2:Article)
                    WHERE a1.law_uri = a2.law_uri
                    AND toInteger(a1.number_normalized) = toInteger(a2.number_normalized) - 1
                    MERGE (a1)-[:NEXT]->(a2)
                    RETURN count(*) as count
                    """, "Article sequence"),

                    # Domain hierarchy
                    ("""
                    MATCH (d:Domain), (b:Book)
                    WHERE b.parent_uri = d.uri
                    MERGE (d)-[:HAS_CHILD]->(b)
                    RETURN count(*) as count
                    """, "Domain-Book"),

                    # Book -> Chapter
                    ("""
                    MATCH (b:Book), (c:Chapter)
                    WHERE c.parent_uri = b.uri
                    MERGE (b)-[:HAS_CHILD]->(c)
                    RETURN count(*) as count
                    """, "Book-Chapter"),

                    # Chapter -> Section
                    ("""
                    MATCH (c:Chapter), (s:Section)
                    WHERE s.parent_uri = c.uri
                    MERGE (c)-[:HAS_CHILD]->(s)
                    RETURN count(*) as count
                    """, "Chapter-Section"),
                ]

                for query, description in queries:
                    console.print(f"  🔗 Creating {description} relationships...", end="")
                    result = session.run(query)
                    count = result.single()["count"]
                    console.print(f" [green]✓[/green] ({count} created)")
                    self.stats.relationships_created += count

        except Exception as e:
            console.print(f"  [red]✗ AST building failed: {str(e)}[/red]")
            self.stats.errors.append(f"AST building: {str(e)}")

    def generate_embeddings(self, skip_embeddings: bool = False):
        """Generate vector embeddings for all text content"""
        if skip_embeddings:
            console.print("\n[yellow]⏭️  Skipping embedding generation[/yellow]")
            return

        console.print("\n[bold cyan]🧮 Generating Vector Embeddings[/bold cyan]")

        try:
            with self.connection.driver.session() as session:
                # Count nodes needing embeddings
                counts = {}
                for node_type in ['Law', 'Article', 'Paragraph', 'LegalLogic']:
                    result = session.run(
                        f"MATCH (n:{node_type}) WHERE n.embedding IS NULL RETURN count(n) as count"
                    )
                    counts[node_type] = result.single()["count"]

                total = sum(counts.values())
                if total == 0:
                    console.print("  [green]All embeddings already generated![/green]")
                    return

                console.print(f"  Nodes needing embeddings:")
                for node_type, count in counts.items():
                    if count > 0:
                        console.print(f"    {node_type}: {count}")

                # Generate embeddings in batches
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
                ) as progress:

                    for node_type in ['Law', 'Article', 'Paragraph', 'LegalLogic']:
                        if counts[node_type] == 0:
                            continue

                        task = progress.add_task(
                            f"Generating {node_type} embeddings...",
                            total=counts[node_type]
                        )

                        # Get text field based on node type
                        text_field = {
                            'Law': 'title_de',
                            'Article': 'content_full',  # Use FULL content for better embeddings
                            'Paragraph': 'text',
                            'LegalLogic': None  # Special handling for LegalLogic
                        }[node_type]

                        # Process in batches
                        offset = 0
                        while offset < counts[node_type]:
                            # Fetch batch - special handling for LegalLogic
                            if node_type == 'LegalLogic':
                                result = session.run(f"""
                                    MATCH (n:LegalLogic)
                                    WHERE n.embedding IS NULL
                                    RETURN id(n) as id,
                                           n.conditions as conditions,
                                           n.consequences as consequences,
                                           n.exceptions as exceptions
                                    SKIP {offset} LIMIT {self.batch_size}
                                """)
                            else:
                                result = session.run(f"""
                                    MATCH (n:{node_type})
                                    WHERE n.embedding IS NULL AND n.{text_field} IS NOT NULL
                                    RETURN id(n) as id, n.{text_field} as text
                                    SKIP {offset} LIMIT {self.batch_size}
                                """)

                            batch = list(result)
                            if not batch:
                                break

                            # Generate embeddings
                            for record in batch:
                                try:
                                    # Handle LegalLogic nodes differently
                                    if node_type == 'LegalLogic':
                                        # Reconstruct text from logic components
                                        text_parts = []
                                        if record.get('conditions'):
                                            text_parts.append(f"IF: {'; '.join(record['conditions'])}")
                                        if record.get('consequences'):
                                            text_parts.append(f"THEN: {'; '.join(record['consequences'])}")
                                        if record.get('exceptions'):
                                            text_parts.append(f"EXCEPT: {'; '.join(record['exceptions'])}")

                                        text = " ".join(text_parts)
                                    else:
                                        text = record['text']

                                    if text and len(text) > 10:  # Skip very short texts
                                        embedding = self.embedding_generator.generate_embedding(text)

                                        # Store embedding
                                        session.run(f"""
                                            MATCH (n:{node_type})
                                            WHERE id(n) = $id
                                            SET n.embedding = $embedding
                                        """, id=record['id'], embedding=embedding)

                                        self.stats.embeddings_generated += 1

                                except Exception as e:
                                    self.stats.warnings.append(f"Embedding error: {str(e)}")

                                progress.advance(task)

                            offset += self.batch_size

                console.print(f"\n  [green]✓ Generated {self.stats.embeddings_generated} embeddings[/green]")

        except Exception as e:
            console.print(f"  [red]✗ Embedding generation failed: {str(e)}[/red]")
            self.stats.errors.append(f"Embedding generation: {str(e)}")

    def extract_relationships(self):
        """Extract legal relationships and citations"""
        console.print("\n[bold cyan]🔍 Extracting Legal Relationships[/bold cyan]")

        try:
            extractor = RelationshipExtractor(self.connection.driver)

            with self.connection.driver.session() as session:
                # Count articles to process
                result = session.run("MATCH (a:Article) RETURN count(a) as count")
                total = result.single()["count"]

                console.print(f"  Processing {total} articles for relationships...")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
                ) as progress:

                    task = progress.add_task("Extracting citations...", total=total)

                    # Process articles in batches
                    offset = 0
                    citations_found = 0

                    while offset < total:
                        # Fetch batch
                        result = session.run("""
                            MATCH (a:Article)
                            WHERE a.content_full IS NOT NULL
                            RETURN a.uri as uri, a.content_full as content
                            SKIP $offset LIMIT $limit
                        """, offset=offset, limit=self.batch_size)

                        batch = list(result)
                        if not batch:
                            break

                        for record in batch:
                            try:
                                # Extract citations from content
                                citations = extractor.extract_citations(record['content'])

                                for citation in citations:
                                    # Create CITES relationship
                                    session.run("""
                                        MATCH (a1:Article {uri: $from_uri})
                                        MATCH (a2:Article)
                                        WHERE a2.law_uri CONTAINS $sr_number
                                        AND a2.number = $article_number
                                        MERGE (a1)-[:CITES]->(a2)
                                    """, from_uri=record['uri'],
                                        sr_number=citation['sr_number'],
                                        article_number=citation['article'])

                                    citations_found += 1

                            except Exception as e:
                                self.stats.warnings.append(f"Citation extraction: {str(e)}")

                            progress.advance(task)

                        offset += self.batch_size

                console.print(f"  [green]✓ Found {citations_found} citations[/green]")
                self.stats.relationships_created += citations_found

        except Exception as e:
            console.print(f"  [red]✗ Relationship extraction failed: {str(e)}[/red]")
            self.stats.errors.append(f"Relationship extraction: {str(e)}")

    def validate_graph(self):
        """Validate the built graph"""
        console.print("\n[bold cyan]✅ Validating Graph[/bold cyan]")

        validation_queries = [
            ("MATCH (l:Law) WHERE NOT (l)-[:HAS_ARTICLE]->() RETURN count(l) as count",
             "Laws without articles"),
            ("MATCH (a:Article) WHERE NOT (l:Law)-[:HAS_ARTICLE]->(a) RETURN count(a) as count",
             "Orphaned articles"),
            ("MATCH (p:Paragraph) WHERE NOT (a:Article)-[:HAS_PARAGRAPH]->(p) RETURN count(p) as count",
             "Orphaned paragraphs"),
            ("MATCH (n) WHERE n.embedding IS NULL RETURN labels(n)[0] as type, count(n) as count",
             "Nodes without embeddings"),
            ("MATCH (ll:LegalLogic) RETURN count(ll) as count",
             "Legal logic nodes created"),
            ("MATCH (a:Article) WHERE a.uri CONTAINS '/101/' AND NOT (a)-[:HAS_LEGAL_LOGIC]->() RETURN count(a) as count",
             "SR 101 articles without legal logic"),
        ]

        issues = []
        with self.connection.driver.session() as session:
            for query, description in validation_queries:
                try:
                    result = session.run(query)
                    for record in result:
                        count = record.get('count', 0)
                        if count > 0:
                            # Special handling for positive metrics (Legal logic nodes created)
                            if "Legal logic nodes created" in description:
                                console.print(f"  [green]✓ {description}: {count}[/green]")
                            elif "without" in description or "Orphaned" in description:
                                issue = f"{description}: {count}"
                                issues.append(issue)
                                console.print(f"  [yellow]⚠ {issue}[/yellow]")
                            else:
                                console.print(f"  [blue]ℹ {description}: {count}[/blue]")
                except:
                    pass

        if not issues:
            console.print("  [green]✓ Graph validation passed![/green]")
        else:
            console.print(f"  [yellow]Found {len(issues)} potential issues[/yellow]")
            self.stats.warnings.extend(issues)

    def save_checkpoint(self):
        """Save checkpoint for resume capability"""
        if not self.checkpoint_enabled:
            return

        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'processed_files': list(self.processed_files),
            'stats': {
                'laws_processed': self.stats.laws_processed,
                'articles_created': self.stats.articles_created,
                'paragraphs_created': self.stats.paragraphs_created,
                'relationships_created': self.stats.relationships_created,
                'embeddings_generated': self.stats.embeddings_generated
            }
        }

        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self):
        """Load checkpoint to resume from previous run"""
        if not self.checkpoint_file.exists():
            return

        try:
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)

            self.processed_files = set(checkpoint.get('processed_files', []))

            # Restore stats
            stats = checkpoint.get('stats', {})
            self.stats.laws_processed = stats.get('laws_processed', 0)
            self.stats.articles_created = stats.get('articles_created', 0)
            self.stats.paragraphs_created = stats.get('paragraphs_created', 0)
            self.stats.relationships_created = stats.get('relationships_created', 0)
            self.stats.embeddings_generated = stats.get('embeddings_generated', 0)

        except Exception as e:
            console.print(f"  [yellow]Warning: Could not load checkpoint: {str(e)}[/yellow]")

    def print_summary(self):
        """Print build summary"""
        self.stats.end_time = datetime.now()

        # Create summary table
        table = Table(title="Build Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Duration", f"{self.stats.duration:.2f} seconds")
        table.add_row("Laws Processed", str(self.stats.laws_processed))
        table.add_row("Articles Created", str(self.stats.articles_created))
        table.add_row("Paragraphs Created", str(self.stats.paragraphs_created))
        table.add_row("Subpoints Created", str(self.stats.subpoints_created))
        table.add_row("Legal Logic Extracted", str(self.stats.legal_logic_extracted))
        table.add_row("Relationships Created", str(self.stats.relationships_created))
        table.add_row("Embeddings Generated", str(self.stats.embeddings_generated))
        table.add_row("Errors", str(len(self.stats.errors)))
        table.add_row("Warnings", str(len(self.stats.warnings)))

        console.print("\n")
        console.print(table)

        # Print errors if any
        if self.stats.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in self.stats.errors[:10]:  # Show first 10 errors
                console.print(f"  • {error}")
            if len(self.stats.errors) > 10:
                console.print(f"  ... and {len(self.stats.errors) - 10} more")

        # Save detailed report
        report_file = Path(f"build_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w') as f:
            json.dump(asdict(self.stats), f, indent=2, default=str)
        console.print(f"\n[cyan]Detailed report saved to: {report_file}[/cyan]")

    def run(self, args: argparse.Namespace):
        """Run the complete build process"""
        try:
            # Initialize
            if not self.initialize():
                return False

            # Clean if requested
            if args.clean:
                self.clean_database()

            # Setup schema with complete taxonomy support
            self.setup_schema()
            self.setup_taxonomy()

            # Download/locate data with SR filter
            sr_filter = getattr(args, 'sr_filter', None)
            if not args.skip_download:
                json_files = self.download_data(sr_filter=sr_filter)
                if not json_files:
                    console.print("[red]No data files to process![/red]")
                    return False
            else:
                json_files = self.download_data(sr_filter=sr_filter)

            # Build graph structure
            self.build_graph_structure(json_files)

            # Build AST relationships
            self.build_ast_relationships()

            # Extract legal relationships
            self.extract_relationships()

            # Generate embeddings
            self.generate_embeddings(args.skip_embeddings)

            # Validate
            self.validate_graph()

            # Print summary
            self.print_summary()

            # Clean checkpoint if successful
            if self.checkpoint_enabled and self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                console.print("\n[green]✓ Checkpoint cleaned up[/green]")

            return True

        except KeyboardInterrupt:
            console.print("\n[yellow]Build interrupted by user[/yellow]")
            if self.checkpoint_enabled:
                self.save_checkpoint()
                console.print(f"[cyan]Progress saved. Run again to resume.[/cyan]")
            return False

        except Exception as e:
            console.print(f"\n[red]Build failed: {str(e)}[/red]")
            logger.exception("Build failed")
            return False

        finally:
            # Close connections
            if self.connection:
                self.connection.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="LAWAST Unified Graph Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean existing data before building"
    )

    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading new data"
    )

    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip generating embeddings"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel workers (default: 8)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing (default: 100)"
    )

    parser.add_argument(
        "--checkpoint",
        action="store_true",
        help="Enable checkpointing for resume capability"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--sr-filter",
        type=str,
        default=None,
        help="Filter to specific SR number (e.g., '101' for Bundesverfassung)"
    )

    parser.add_argument(
        "--strict-schema",
        action="store_true",
        help="Enable strict schema validation (fail on missing required fields)"
    )

    args = parser.parse_args()

    # Print banner
    console.print(Panel.fit(
        "[bold cyan]LAWAST Unified Graph Builder[/bold cyan]\n"
        "Building complete knowledge graph with:\n"
        "• Graph structure (Laws, Articles, Paragraphs)\n"
        "• Legal Logic extraction (IF-THEN-EXCEPT patterns)\n"
        "• AST relationships\n"
        "• Vector embeddings\n"
        "• Legal citations",
        border_style="cyan"
    ))

    # Create and run builder
    builder = UnifiedGraphBuilder(
        workers=args.workers,
        batch_size=args.batch_size,
        checkpoint_enabled=args.checkpoint,
        verbose=args.verbose,
        strict_schema=args.strict_schema
    )

    success = builder.run(args)

    if success:
        console.print("\n[bold green]✅ Build completed successfully![/bold green]")
        sys.exit(0)
    else:
        console.print("\n[bold red]❌ Build failed![/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()