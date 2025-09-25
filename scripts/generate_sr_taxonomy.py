#!/usr/bin/env python3
"""
Generate SR Taxonomy from existing Law nodes

This script:
1. Queries all Law nodes from Neo4j
2. Parses their SR numbers to extract hierarchy
3. Creates Domain/Book/Chapter/Section nodes
4. Creates CONTAINS relationships between levels
5. Links Laws to their taxonomy via CLASSIFIED_BY relationships
"""
import sys
import os
import argparse
import logging
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection
from src.data_access.graph_builder import GraphBuilder
from src.extractors.sr_taxonomy_generator import SRTaxonomyGenerator
from src.data_access.graph_schema import RelationshipTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaxonomyBuilder:
    """Build taxonomy hierarchy in Neo4j from SR numbers"""

    def __init__(self):
        """Initialize the taxonomy builder"""
        self.connection = get_connection()
        self.graph_builder = GraphBuilder()
        self.generator = SRTaxonomyGenerator()
        self.stats = {
            'laws_processed': 0,
            'domains_created': 0,
            'books_created': 0,
            'chapters_created': 0,
            'sections_created': 0,
            'contains_relationships': 0,
            'classified_by_relationships': 0,
            'errors': 0
        }

    def fetch_sr_numbers(self) -> List[Tuple[str, str]]:
        """
        Fetch all SR numbers and URIs from Law nodes

        Returns:
            List of (uri, sr_number) tuples
        """
        query = """
        MATCH (l:Law)
        WHERE l.sr_number IS NOT NULL
        RETURN l.uri as uri, l.sr_number as sr_number
        ORDER BY l.sr_number
        """

        results = self.connection.execute_query(query)
        laws = [(r['uri'], r['sr_number']) for r in results]

        logger.info(f"Found {len(laws)} laws with SR numbers")
        return laws

    def create_taxonomy_nodes(self, sr_numbers: List[str]) -> None:
        """
        Create all taxonomy nodes from SR numbers

        Args:
            sr_numbers: List of SR numbers to process
        """
        # Extract all unique taxonomy nodes
        logger.info("Extracting taxonomy from SR numbers...")
        taxonomy = self.generator.extract_all_taxonomies(sr_numbers)

        # Create Domain nodes
        logger.info(f"Creating {len(taxonomy['domains'])} domain nodes...")
        for domain in taxonomy['domains']:
            try:
                self.graph_builder.create_domain_node(domain)
                self.stats['domains_created'] += 1
            except Exception as e:
                logger.error(f"Error creating domain {domain.uri}: {e}")
                self.stats['errors'] += 1

        # Create Book nodes
        logger.info(f"Creating {len(taxonomy['books'])} book nodes...")
        for book in taxonomy['books']:
            try:
                self.graph_builder.create_book_node(book)
                self.stats['books_created'] += 1
            except Exception as e:
                logger.error(f"Error creating book {book.uri}: {e}")
                self.stats['errors'] += 1

        # Create Chapter nodes
        logger.info(f"Creating {len(taxonomy['chapters'])} chapter nodes...")
        for chapter in taxonomy['chapters']:
            try:
                self.graph_builder.create_chapter_node(chapter)
                self.stats['chapters_created'] += 1
            except Exception as e:
                logger.error(f"Error creating chapter {chapter.uri}: {e}")
                self.stats['errors'] += 1

        # Create Section nodes
        logger.info(f"Creating {len(taxonomy['sections'])} section nodes...")
        for section in taxonomy['sections']:
            try:
                self.graph_builder.create_section_node(section)
                self.stats['sections_created'] += 1
            except Exception as e:
                logger.error(f"Error creating section {section.uri}: {e}")
                self.stats['errors'] += 1

    def create_contains_relationships(self) -> None:
        """Create CONTAINS relationships between taxonomy levels"""

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
            count = result[0]['count']
            logger.info(f"Created {count} Domain->Book CONTAINS relationships")
            self.stats['contains_relationships'] += count

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
            count = result[0]['count']
            logger.info(f"Created {count} Book->Chapter CONTAINS relationships")
            self.stats['contains_relationships'] += count

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
            count = result[0]['count']
            logger.info(f"Created {count} Chapter->Section CONTAINS relationships")
            self.stats['contains_relationships'] += count

        # Book -> Section (when no chapter)
        query = """
        MATCH (b:Book)
        MATCH (s:Section)
        WHERE s.parent_uri = b.uri AND s.chapter_uri IS NULL
        MERGE (b)-[r:CONTAINS]->(s)
        RETURN count(r) as count
        """
        result = self.connection.execute_query(query)
        if result:
            count = result[0]['count']
            logger.info(f"Created {count} Book->Section CONTAINS relationships (no chapter)")
            self.stats['contains_relationships'] += count

    def link_laws_to_taxonomy(self, laws: List[Tuple[str, str]]) -> None:
        """
        Link Law nodes to their taxonomy classification

        Args:
            laws: List of (law_uri, sr_number) tuples
        """
        logger.info(f"Linking {len(laws)} laws to taxonomy...")

        for law_uri, sr_number in laws:
            try:
                # Generate hierarchy for this SR number
                hierarchy = self.generator.generate_hierarchy(sr_number)

                if not hierarchy:
                    logger.warning(f"Could not generate hierarchy for {sr_number}")
                    continue

                # Find the most specific taxonomy level to link to
                taxonomy_uri = None
                for level in reversed(hierarchy):  # Start from most specific
                    taxonomy_uri = level.uri
                    break

                if taxonomy_uri:
                    # Create CLASSIFIED_BY relationship
                    query = """
                    MATCH (l:Law {uri: $law_uri})
                    MATCH (t)
                    WHERE t.uri = $taxonomy_uri
                    MERGE (l)-[r:CLASSIFIED_BY]->(t)
                    RETURN l.sr_number as sr_number
                    """
                    params = {
                        'law_uri': law_uri,
                        'taxonomy_uri': taxonomy_uri
                    }

                    result = self.connection.execute_write(query, params)
                    if result:
                        self.stats['classified_by_relationships'] += 1
                        self.stats['laws_processed'] += 1

            except Exception as e:
                logger.error(f"Error linking law {law_uri}: {e}")
                self.stats['errors'] += 1

    def generate_report(self) -> None:
        """Generate and print final report"""
        logger.info("=" * 60)
        logger.info("SR TAXONOMY GENERATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Laws processed: {self.stats['laws_processed']}")
        logger.info(f"Domains created: {self.stats['domains_created']}")
        logger.info(f"Books created: {self.stats['books_created']}")
        logger.info(f"Chapters created: {self.stats['chapters_created']}")
        logger.info(f"Sections created: {self.stats['sections_created']}")
        logger.info(f"CONTAINS relationships: {self.stats['contains_relationships']}")
        logger.info(f"CLASSIFIED_BY relationships: {self.stats['classified_by_relationships']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 60)

    def run(self) -> None:
        """Execute the complete taxonomy generation process"""
        try:
            # Step 1: Fetch all SR numbers
            laws = self.fetch_sr_numbers()
            if not laws:
                logger.warning("No laws with SR numbers found")
                return

            sr_numbers = [sr for _, sr in laws]

            # Step 2: Create taxonomy nodes
            self.create_taxonomy_nodes(sr_numbers)

            # Step 3: Create CONTAINS relationships
            logger.info("Creating CONTAINS relationships...")
            self.create_contains_relationships()

            # Step 4: Link laws to taxonomy
            self.link_laws_to_taxonomy(laws)

            # Step 5: Generate report
            self.generate_report()

        except Exception as e:
            logger.error(f"Taxonomy generation failed: {e}", exc_info=True)
            raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate SR taxonomy from existing Law nodes"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    builder = TaxonomyBuilder()
    builder.run()


if __name__ == "__main__":
    main()