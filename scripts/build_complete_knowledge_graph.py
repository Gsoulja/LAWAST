#!/usr/bin/env python3
"""
Complete Knowledge Graph Builder for LAWAST

This script orchestrates ALL extraction components to build a comprehensive
legal knowledge graph from both JSON and HTML sources. It processes:

1. JSON files (fedlex/):
   - Laws (ConsolidationAbstract)
   - Versions (Consolidation)
   - Acts (OC/FGA publications)
   - Relationships between entities

2. HTML files (fedlex-assets/):
   - Taxonomy hierarchy (Domain/Book/Chapter/Section)
   - Article content with paragraphs
   - References and citations

The script builds a complete graph with:
- Law nodes with temporal versions
- Article nodes with full content
- Hierarchical taxonomy structure
- All relationships (SUPERSEDES, REFERENCES, CITES, CONTAINS, etc.)

Usage:
    python scripts/build_complete_knowledge_graph.py [--json-dir JSON_DIR] [--html-dir HTML_DIR] [--limit LIMIT]
"""

import sys
import os
import json
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Neo4j components
from src.data_access.neo4j_connection import get_connection
from src.data_access.fedlex_parser import FedlexParser
from src.data_access.graph_builder import GraphBuilder
from src.data_access.storage_pipeline import Neo4jStoragePipeline
from src.data_access.graph_schema import LawNode, VersionNode

# Import JSON extractors
from src.extractors.law_extractor import LawExtractor
from src.extractors.version_extractor import VersionExtractor
from src.extractors.act_extractor import ActExtractor
from src.extractors.relationship_extractor import RelationshipExtractor
from src.extractors.uri_resolver import URIResolver
from src.extractors.version_chain_builder import VersionChainBuilder

# Import HTML extractors
from src.parsers.unified_html_parser import UnifiedHtmlParser
from src.extractors.taxonomy_extractor import TaxonomyExtractor, TaxonomyResult
from src.extractors.article_extractor import ArticleExtractor, Article
from src.extractors.reference_patterns import ReferencePatternDetector
from src.extractors.html_reference_extractor import HTMLReferenceExtractor
from src.extractors.extracted_content import ExtractedContent
from src.extractors.sr_taxonomy_generator import SRTaxonomyGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('build_complete_knowledge_graph.log')
    ]
)
logger = logging.getLogger(__name__)


class CompleteKnowledgeGraphBuilder:
    """
    Comprehensive knowledge graph builder that processes both JSON and HTML files
    to create a complete legal knowledge graph in Neo4j.
    """

    def __init__(self):
        """Initialize all components for graph building."""
        # Neo4j connection
        self.connection = get_connection()
        self.graph_builder = GraphBuilder(self.connection)

        # JSON processing components
        self.fedlex_parser = FedlexParser()
        self.law_extractor = LawExtractor()
        self.version_extractor = VersionExtractor()
        self.act_extractor = ActExtractor()
        self.relationship_extractor = RelationshipExtractor(
            graph_builder=self.graph_builder
        )
        self.uri_resolver = URIResolver()
        self.version_chain_builder = VersionChainBuilder(self.graph_builder)

        # HTML processing components
        self.html_parser = UnifiedHtmlParser(cache_size=1000)
        self.taxonomy_extractor = TaxonomyExtractor(parser=self.html_parser)
        self.article_extractor = ArticleExtractor(parser=self.html_parser)
        self.reference_detector = ReferencePatternDetector()
        self.html_reference_extractor = HTMLReferenceExtractor()
        self.storage_pipeline = Neo4jStoragePipeline(
            connection=self.connection,
            batch_size=1000,
            checkpoint_file="knowledge_graph_checkpoint.json"
        )

        # Statistics
        self.stats = defaultdict(int)
        self.start_time = None

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        logger.info("Checking prerequisites...")

        # Check Neo4j connection
        if not self.connection.health_check():
            logger.error("❌ Neo4j is not accessible")
            return False
        logger.info("✅ Neo4j is running")

        # Check for JSON directory
        if not Path("fedlex").exists():
            logger.warning("⚠️  JSON directory 'fedlex/' not found")
        else:
            json_count = len(list(Path("fedlex").rglob("*.json")))
            logger.info(f"✅ Found {json_count:,} JSON files")

        # Check for HTML directory
        if not Path("fedlex-assets").exists():
            logger.warning("⚠️  HTML directory 'fedlex-assets/' not found")
        else:
            html_count = len(list(Path("fedlex-assets").rglob("*.html")))
            logger.info(f"✅ Found {html_count:,} HTML files")

        return True

    def process_json_files(self, json_dir: Path, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Process JSON files to extract laws, versions, acts, and relationships.

        Args:
            json_dir: Directory containing JSON files
            limit: Maximum number of files to process

        Returns:
            Processing statistics
        """
        logger.info("=" * 60)
        logger.info("Phase 1: Processing JSON files")
        logger.info("=" * 60)

        json_files = list(json_dir.rglob("*.json"))
        if limit:
            json_files = json_files[:limit]

        logger.info(f"Processing {len(json_files)} JSON files...")

        for i, json_file in enumerate(json_files, 1):
            if i % 1000 == 0:
                logger.info(f"Progress: {i}/{len(json_files)} JSON files processed")

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                # Extract laws (ConsolidationAbstract)
                law_result = self.law_extractor.extract(json_data, str(json_file))
                if law_result.nodes:
                    for node_dict in law_result.nodes:
                        # Convert dict to LawNode object with all available fields
                        if isinstance(node_dict, dict) and node_dict.get('type') == 'Law':
                            law_node = LawNode(
                                uri=node_dict['uri'],
                                sr_number=node_dict.get('sr_number', ''),
                                title_de=node_dict.get('title_de'),
                                title_fr=node_dict.get('title_fr'),
                                title_it=node_dict.get('title_it'),
                                title_rm=node_dict.get('title_rm'),
                                title_en=node_dict.get('title_en'),
                                date_document=node_dict.get('date_document'),
                                date_entry_in_force=node_dict.get('date_entry_in_force'),
                                date_no_longer_in_force=node_dict.get('date_no_longer_in_force'),
                                in_force=node_dict.get('in_force'),
                                in_force_status=node_dict.get('in_force_status'),
                                status=node_dict.get('status'),
                                basic_act=node_dict.get('basic_act'),
                                classified_by_taxonomy=node_dict.get('classified_by_taxonomy'),
                                type_document=node_dict.get('type_document'),
                                type=node_dict.get('type'),
                                language=node_dict.get('language'),
                                parent_uri=node_dict.get('parent_uri'),
                                metadata={}
                            )
                            self.graph_builder.create_law_node(law_node)
                    self.stats['laws_created'] += len(law_result.nodes)

                # Extract versions
                version_result = self.version_extractor.extract(json_data, str(json_file))
                if version_result.nodes:
                    for node_dict in version_result.nodes:
                        # Convert dict to VersionNode object
                        if isinstance(node_dict, dict) and node_dict.get('type') == 'Version':
                            # Parse dates from ISO strings
                            date_applicable = None
                            if node_dict.get('date_applicable'):
                                date_applicable = datetime.fromisoformat(node_dict['date_applicable'])

                            date_end_applicable = None
                            if node_dict.get('date_end_applicable'):
                                date_end_applicable = datetime.fromisoformat(node_dict['date_end_applicable'])

                            # Only create node if we have required fields
                            if date_applicable and node_dict.get('parent_law_uri'):
                                version_node = VersionNode(
                                    uri=node_dict['uri'],
                                    law_uri=node_dict['parent_law_uri'],  # Use parent_law_uri from extractor
                                    date_applicable=date_applicable,
                                    date_end_applicable=date_end_applicable,
                                    version_number=node_dict.get('version_number'),
                                    metadata=node_dict.get('metadata', {})
                                )
                                self.graph_builder.create_version_node(version_node)
                                self.stats['versions_created'] += 1
                            else:
                                logger.debug(f"Skipping version without required fields: {node_dict.get('uri')}")

                # Extract acts
                act_result = self.act_extractor.extract(json_data, str(json_file))
                if act_result.nodes:
                    for node_dict in act_result.nodes:
                        # Convert dict to ActNode object
                        if isinstance(node_dict, dict) and node_dict.get('type') == 'Act':
                            from src.data_access.graph_schema import ActNode
                            act_node = ActNode(
                                uri=node_dict['uri'],
                                type_document=node_dict.get('type_document', ''),
                                number=node_dict.get('number'),
                                title_de=node_dict.get('title_de'),
                                title_fr=node_dict.get('title_fr'),
                                title_it=node_dict.get('title_it'),
                                title_rm=node_dict.get('title_rm'),
                                title_en=node_dict.get('title_en'),
                                date_document=node_dict.get('date_document'),
                                date_publication=node_dict.get('date_publication'),
                                date_entry_in_force=node_dict.get('date_entry_in_force'),
                                amends=node_dict.get('amends'),
                                basic_act=node_dict.get('basic_act'),
                                language=node_dict.get('language'),
                                metadata=node_dict.get('metadata', {})
                            )
                            self.graph_builder.create_act_node(act_node)
                            self.stats['acts_created'] += 1

                # Extract relationships
                self.relationship_extractor.extract_from_file(str(json_file))
                self.stats['json_files_processed'] += 1

            except Exception as e:
                logger.error(f"Failed to process {json_file}: {e}")
                self.stats['json_errors'] += 1

        # Flush any buffered relationships
        if hasattr(self.relationship_extractor, 'buffer'):
            self.relationship_extractor.buffer.flush()

        # Build version chains (SUPERSEDES relationships)
        logger.info("Building version chains...")
        self.version_chain_builder.build_all_chains()

        logger.info(f"JSON processing complete: {self.stats['json_files_processed']} files")
        return dict(self.stats)

    def process_html_files(self, html_dir: Path, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Process HTML files to extract taxonomy, articles, and references.

        Args:
            html_dir: Directory containing HTML files
            limit: Maximum number of files to process

        Returns:
            Processing statistics
        """
        logger.info("=" * 60)
        logger.info("Phase 2: Processing HTML files")
        logger.info("=" * 60)

        html_files = list(html_dir.rglob("*.html"))
        if limit:
            html_files = html_files[:limit]

        logger.info(f"Processing {len(html_files)} HTML files...")

        for i, html_file in enumerate(html_files, 1):
            if i % 100 == 0:
                logger.info(f"Progress: {i}/{len(html_files)} HTML files processed")

            try:
                # Parse HTML
                soup = self.html_parser.parse(str(html_file))
                if not soup:
                    logger.error(f"Failed to parse {html_file}")
                    self.stats['html_parse_errors'] += 1
                    continue

                # Extract all components
                content = self._extract_html_content(html_file, soup)
                if not content:
                    continue

                # Store in Neo4j using storage pipeline
                storage_stats = self.storage_pipeline.store_extracted_content(
                    content,
                    resume=(i == 1)
                )

                # Update statistics
                self.stats['html_files_processed'] += 1
                self.stats['taxonomies_extracted'] += 1 if content.taxonomy else 0
                self.stats['articles_extracted'] += len(content.articles)
                self.stats['references_extracted'] += len(content.references)
                self.stats['taxonomy_nodes_created'] += storage_stats.taxonomy_nodes_created
                self.stats['article_nodes_created'] += storage_stats.articles_created
                self.stats['relationships_created'] += storage_stats.relationships_created

            except Exception as e:
                logger.error(f"Failed to process {html_file}: {e}")
                self.stats['html_errors'] += 1

        logger.info(f"HTML processing complete: {self.stats['html_files_processed']} files")
        return dict(self.stats)

    def generate_sr_taxonomy(self) -> Dict[str, int]:
        """
        Generate SR taxonomy from existing Law nodes.

        Returns:
            Processing statistics
        """
        logger.info("=" * 60)
        logger.info("Phase 3: Generating SR Taxonomy")
        logger.info("=" * 60)

        try:
            # Query all SR numbers from Law nodes
            query = """
            MATCH (l:Law)
            WHERE l.sr_number IS NOT NULL
            RETURN l.uri as uri, l.sr_number as sr_number
            """
            results = self.connection.execute_query(query)

            if not results:
                logger.info("No laws with SR numbers found")
                return dict(self.stats)

            sr_numbers = [r['sr_number'] for r in results]
            logger.info(f"Processing taxonomy for {len(sr_numbers)} laws...")

            # Initialize SR taxonomy generator
            sr_generator = SRTaxonomyGenerator()

            # Extract all taxonomy nodes
            taxonomy = sr_generator.extract_all_taxonomies(sr_numbers)

            # Create Domain nodes
            for domain in taxonomy['domains']:
                self.graph_builder.create_domain_node(domain)
                self.stats['domains_created'] = self.stats.get('domains_created', 0) + 1

            # Create Book nodes
            for book in taxonomy['books']:
                self.graph_builder.create_book_node(book)
                self.stats['books_created'] = self.stats.get('books_created', 0) + 1

            # Create Chapter nodes
            for chapter in taxonomy['chapters']:
                self.graph_builder.create_chapter_node(chapter)
                self.stats['chapters_created'] = self.stats.get('chapters_created', 0) + 1

            # Create Section nodes
            for section in taxonomy['sections']:
                self.graph_builder.create_section_node(section)
                self.stats['sections_created'] = self.stats.get('sections_created', 0) + 1

            # Create CONTAINS relationships
            logger.info("Creating taxonomy CONTAINS relationships...")

            # Domain -> Book
            query = """
            MATCH (d:Domain)
            MATCH (b:Book)
            WHERE b.parent_uri = d.uri
            MERGE (d)-[r:CONTAINS]->(b)
            RETURN count(r) as count
            """
            result = self.connection.execute_query(query)
            if result:
                self.stats['taxonomy_contains'] = result[0]['count']

            # Book -> Chapter
            query = """
            MATCH (b:Book)
            MATCH (c:Chapter)
            WHERE c.parent_uri = b.uri
            MERGE (b)-[r:CONTAINS]->(c)
            RETURN count(r) as count
            """
            result = self.connection.execute_query(query)
            if result:
                self.stats['taxonomy_contains'] += result[0]['count']

            # Chapter -> Section
            query = """
            MATCH (c:Chapter)
            MATCH (s:Section)
            WHERE s.parent_uri = c.uri
            MERGE (c)-[r:CONTAINS]->(s)
            RETURN count(r) as count
            """
            result = self.connection.execute_query(query)
            if result:
                self.stats['taxonomy_contains'] += result[0]['count']

            # Link laws to taxonomy
            logger.info("Creating CLASSIFIED_BY relationships...")
            for result in results:
                law_uri = result['uri']
                sr_number = result['sr_number']

                # Generate hierarchy for this SR number
                hierarchy = sr_generator.generate_hierarchy(sr_number)
                if hierarchy:
                    # Link to most specific level
                    taxonomy_uri = hierarchy[-1].uri
                    query = """
                    MATCH (l:Law {uri: $law_uri})
                    MATCH (t)
                    WHERE t.uri = $taxonomy_uri
                    MERGE (l)-[r:CLASSIFIED_BY]->(t)
                    """
                    params = {'law_uri': law_uri, 'taxonomy_uri': taxonomy_uri}
                    self.connection.execute_write(query, params)
                    self.stats['laws_classified'] = self.stats.get('laws_classified', 0) + 1

            logger.info(f"SR Taxonomy generation complete")

        except Exception as e:
            logger.error(f"SR Taxonomy generation failed: {e}")
            self.stats['taxonomy_errors'] = self.stats.get('taxonomy_errors', 0) + 1

        return dict(self.stats)

    def _extract_html_content(self, html_file: Path, soup) -> Optional[ExtractedContent]:
        """
        Extract all content from parsed HTML.

        Args:
            html_file: Path to HTML file
            soup: Parsed BeautifulSoup object

        Returns:
            ExtractedContent object or None
        """
        try:
            # Extract taxonomy
            taxonomy_extraction = self.taxonomy_extractor.extract(soup, str(html_file))
            taxonomy_data = self._build_taxonomy_from_extraction(taxonomy_extraction, str(html_file))

            # Extract articles
            article_extraction = self.article_extractor.extract(soup, str(html_file))
            articles = self._build_articles_from_extraction(article_extraction, str(html_file))

            # Extract references
            references = []
            if articles:
                for article in articles:
                    # Find article element in soup
                    article_elements = soup.find_all('article')
                    for elem in article_elements:
                        marginal = elem.find(class_='marginalia')
                        if marginal and marginal.get_text(strip=True) == article.number:
                            html_content = str(elem)
                            refs = self.reference_detector.extract_references(html_content)
                            for ref in refs:
                                ref.source_uri = article.uri
                            references.extend(refs)
                            break

            # Also extract HTML references
            html_ref_result = self.html_reference_extractor.extract(soup, str(html_file))
            if html_ref_result.nodes:
                self.stats['html_references_found'] += len(html_ref_result.nodes)

            # Build ExtractedContent
            law_uri = taxonomy_data.uri if taxonomy_data else self._generate_uri(str(html_file))

            content = ExtractedContent(
                taxonomy=taxonomy_data,
                articles=articles,
                references=references,
                metadata={
                    "source_file": str(html_file),
                    "extraction_date": datetime.now().isoformat()
                },
                source_file=str(html_file),
                law_uri=law_uri
            )

            return content

        except Exception as e:
            logger.error(f"Failed to extract content from {html_file}: {e}")
            return None

    def _build_taxonomy_from_extraction(self, extraction_result, file_path: str) -> Optional[TaxonomyResult]:
        """Build TaxonomyResult from ExtractionResult."""
        # Check if the extraction result has the TaxonomyResult in data field
        if hasattr(extraction_result, 'data') and extraction_result.data:
            return extraction_result.data

        # Fallback if data is not available
        if extraction_result.errors:
            return None

        # Create a basic TaxonomyResult from nodes if needed
        return TaxonomyResult(
            sr_number=None,
            title={},
            domain=None,
            hierarchy=[],
            metadata={"source": file_path},
            language=self._extract_language_from_path(file_path),
            uri=self._generate_uri(file_path)
        )

    def _build_articles_from_extraction(self, extraction_result, file_path: str) -> List[Article]:
        """Build Article list from ExtractionResult."""
        # Check if the extraction result has the articles list in data field
        if hasattr(extraction_result, 'data') and extraction_result.data:
            return extraction_result.data

        # Fallback: Extract articles from nodes in the result
        articles = []
        for node in extraction_result.nodes:
            if node.get('type') == 'Article':
                article = Article(
                    uri=node.get('uri'),
                    number=node.get('number'),
                    number_normalized=node.get('number_normalized'),
                    titles=node.get('titles', {}),
                    content=None,  # Would need to extract full content
                    metadata=node.get('metadata', {})
                )
                articles.append(article)

        return articles

    def _extract_language_from_path(self, file_path: str) -> Optional[str]:
        """Extract language code from file path."""
        path_parts = Path(file_path).parts
        for lang in ['de', 'fr', 'it', 'rm', 'en']:
            if lang in path_parts:
                return lang
        return None

    def _generate_uri(self, file_path: str) -> str:
        """Generate URI from file path."""
        path = Path(file_path)
        parts = []

        if 'eli' in path.parts:
            eli_index = path.parts.index('eli')
            parts = path.parts[eli_index:]
            parts = [p for p in parts if p != 'html' and not p.endswith('.html')]

        return f"https://fedlex.data.admin.ch/{'/'.join(parts)}"

    def create_indexes(self):
        """Create or update Neo4j indexes for optimal performance."""
        logger.info("Creating indexes...")

        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (l:Law) ON (l.uri)",
            "CREATE INDEX IF NOT EXISTS FOR (l:Law) ON (l.sr_number)",
            "CREATE INDEX IF NOT EXISTS FOR (v:Version) ON (v.uri)",
            "CREATE INDEX IF NOT EXISTS FOR (v:Version) ON (v.date)",
            "CREATE INDEX IF NOT EXISTS FOR (a:Act) ON (a.uri)",
            "CREATE INDEX IF NOT EXISTS FOR (a:Article) ON (a.uri)",
            "CREATE INDEX IF NOT EXISTS FOR (a:Article) ON (a.number)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Domain) ON (d.uri)",
            "CREATE INDEX IF NOT EXISTS FOR (b:Book) ON (b.uri)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Chapter) ON (c.uri)",
            "CREATE INDEX IF NOT EXISTS FOR (s:Section) ON (s.uri)"
        ]

        for index_query in indexes:
            try:
                self.connection.execute_query(index_query)
                logger.debug(f"Created index: {index_query}")
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

    def generate_report(self):
        """Generate final statistics report."""
        if not self.start_time:
            return

        duration = (datetime.now() - self.start_time).total_seconds()

        logger.info("=" * 70)
        logger.info("KNOWLEDGE GRAPH BUILD COMPLETE")
        logger.info("=" * 70)
        logger.info("JSON Processing:")
        logger.info(f"  Files processed: {self.stats['json_files_processed']:,}")
        logger.info(f"  Laws created: {self.stats['laws_created']:,}")
        logger.info(f"  Versions created: {self.stats['versions_created']:,}")
        logger.info(f"  Acts created: {self.stats.get('acts_created', 0):,}")
        logger.info(f"  Errors: {self.stats['json_errors']:,}")

        logger.info("\nHTML Processing:")
        logger.info(f"  Files processed: {self.stats['html_files_processed']:,}")
        logger.info(f"  Taxonomies extracted: {self.stats['taxonomies_extracted']:,}")
        logger.info(f"  Articles extracted: {self.stats['articles_extracted']:,}")
        logger.info(f"  References extracted: {self.stats['references_extracted']:,}")
        logger.info(f"  Errors: {self.stats['html_errors']:,}")

        logger.info("\nSR Taxonomy Generation:")
        logger.info(f"  Domains created: {self.stats.get('domains_created', 0):,}")
        logger.info(f"  Books created: {self.stats.get('books_created', 0):,}")
        logger.info(f"  Chapters created: {self.stats.get('chapters_created', 0):,}")
        logger.info(f"  Sections created: {self.stats.get('sections_created', 0):,}")
        logger.info(f"  CONTAINS relationships: {self.stats.get('taxonomy_contains', 0):,}")
        logger.info(f"  CLASSIFIED_BY relationships: {self.stats.get('laws_classified', 0):,}")

        logger.info("\nGraph Statistics:")
        logger.info(f"  Taxonomy nodes: {self.stats['taxonomy_nodes_created']:,}")
        logger.info(f"  Article nodes: {self.stats['article_nodes_created']:,}")
        logger.info(f"  Relationships: {self.stats['relationships_created']:,}")

        logger.info(f"\nTotal duration: {duration/60:.1f} minutes")
        logger.info(f"Average processing rate: {(self.stats['json_files_processed'] + self.stats['html_files_processed'])/duration:.1f} files/second")
        logger.info("=" * 70)

        # Query graph for final counts
        try:
            node_count_query = "MATCH (n) RETURN count(n) as count"
            rel_count_query = "MATCH ()-[r]->() RETURN count(r) as count"

            node_result = self.connection.execute_query(node_count_query)
            rel_result = self.connection.execute_query(rel_count_query)

            if node_result and rel_result:
                logger.info(f"\nFinal Neo4j Graph Size:")
                logger.info(f"  Total nodes: {node_result[0]['count']:,}")
                logger.info(f"  Total relationships: {rel_result[0]['count']:,}")
        except Exception as e:
            logger.error(f"Could not query final graph statistics: {e}")


def main():
    """Main entry point for the complete knowledge graph builder."""
    parser = argparse.ArgumentParser(
        description="Build complete legal knowledge graph from JSON and HTML sources"
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=Path("fedlex"),
        help="Directory containing JSON files (default: fedlex)"
    )
    parser.add_argument(
        "--html-dir",
        type=Path,
        default=Path("fedlex-assets"),
        help="Directory containing HTML files (default: fedlex-assets)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of files to process per type (for testing)"
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Process only JSON files"
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="Process only HTML files"
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip index creation"
    )
    parser.add_argument(
        "--skip-taxonomy",
        action="store_true",
        help="Skip SR taxonomy generation"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize builder
    builder = CompleteKnowledgeGraphBuilder()

    # Check prerequisites
    if not builder.check_prerequisites():
        logger.error("Prerequisites not met. Exiting.")
        sys.exit(1)

    # Create indexes unless skipped
    if not args.skip_indexes:
        builder.create_indexes()

    # Start processing
    builder.start_time = datetime.now()

    try:
        # Process JSON files
        if not args.html_only and args.json_dir.exists():
            builder.process_json_files(args.json_dir, args.limit)

        # Process HTML files
        if not args.json_only and args.html_dir.exists():
            builder.process_html_files(args.html_dir, args.limit)

        # Generate SR taxonomy
        if not args.skip_taxonomy:
            builder.generate_sr_taxonomy()

        # Generate final report
        builder.generate_report()

    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        builder.generate_report()
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()