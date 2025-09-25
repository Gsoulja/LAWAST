#!/usr/bin/env python3
"""
Build Focused Knowledge Graph

This script builds a focused knowledge graph containing only laws that have
both JSON metadata and HTML content (approximately 5,700 laws). This ensures:

1. No orphaned Law nodes (laws without articles)
2. Complete data for each law (metadata + articles + references)
3. Efficient processing by skipping historical/obsolete laws
4. Focus on currently relevant legal content

Usage:
    python scripts/build_focused_graph.py [--limit LIMIT] [--clear-db]
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.unified_law_processor import UnifiedLawProcessor
from src.data_access.neo4j_connection import get_connection
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('build_focused_graph.log')
    ]
)
logger = logging.getLogger(__name__)


def clear_database():
    """Clear the Neo4j database."""
    logger.info("Clearing database...")

    load_dotenv()
    uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')

    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

        # Verify
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()['count']
        logger.info(f"Database cleared. Node count: {count}")

    driver.close()


def verify_results():
    """Verify and report on the built graph."""
    load_dotenv()

    uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')

    driver = GraphDatabase.driver(uri, auth=(username, password))

    print("\n" + "=" * 60)
    print("GRAPH STATISTICS")
    print("=" * 60)

    with driver.session() as session:
        queries = {
            'Total nodes': 'MATCH (n) RETURN count(n) as count',
            'Law nodes': 'MATCH (l:Law) RETURN count(l) as count',
            'Laws WITH articles': '''
                MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
                RETURN count(DISTINCT l) as count
            ''',
            'Laws WITHOUT articles (should be 0)': '''
                MATCH (l:Law)
                WHERE NOT (l)-[:HAS_ARTICLE]->()
                RETURN count(l) as count
            ''',
            'Article nodes': 'MATCH (a:Article) RETURN count(a) as count',
            'Orphaned articles (should be 0)': '''
                MATCH (a:Article)
                WHERE NOT ()<-[:HAS_ARTICLE]-(a)
                RETURN count(a) as count
            ''',
            'Version nodes': 'MATCH (v:Version) RETURN count(v) as count',
            'Taxonomy nodes (Domain+Book+Chapter+Section)': '''
                MATCH (n)
                WHERE n:Domain OR n:Book OR n:Chapter OR n:Section
                RETURN count(n) as count
            ''',
            'Domain nodes': 'MATCH (d:Domain) RETURN count(d) as count',
            'Book nodes': 'MATCH (b:Book) RETURN count(b) as count',
            'Chapter nodes': 'MATCH (c:Chapter) RETURN count(c) as count',
            'Section nodes': 'MATCH (s:Section) RETURN count(s) as count',
            'Language nodes': 'MATCH (l:Language) RETURN count(l) as count',
            'Total relationships': 'MATCH ()-[r]->() RETURN count(r) as count',
            'HAS_ARTICLE relationships': 'MATCH ()-[r:HAS_ARTICLE]->() RETURN count(r) as count',
            'CONTAINS relationships': 'MATCH ()-[r:CONTAINS]->() RETURN count(r) as count',
            'FOLLOWS relationships': 'MATCH ()-[r:FOLLOWS]->() RETURN count(r) as count',
            'REFERENCES relationships': 'MATCH ()-[r:REFERENCES]->() RETURN count(r) as count',
            'HAS_VERSION relationships': 'MATCH ()-[r:HAS_VERSION]->() RETURN count(r) as count',
        }

        for label, query in queries.items():
            result = session.run(query)
            count = result.single()['count']
            print(f"{label:45}: {count:,}")

        # Sample data
        print("\n" + "-" * 60)
        print("SAMPLE DATA")
        print("-" * 60)

        result = session.run('''
            MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
            RETURN l.uri as law_uri, l.sr_number as sr_number, count(a) as article_count
            ORDER BY article_count DESC
            LIMIT 5
        ''')

        print("\nTop 5 laws by article count:")
        for record in result:
            print(f"  {record['sr_number'] or 'No SR'}: {record['law_uri']}")
            print(f"    Articles: {record['article_count']}")

        # Check data quality
        print("\n" + "-" * 60)
        print("DATA QUALITY CHECK")
        print("-" * 60)

        result = session.run('''
            MATCH (l:Law)
            RETURN
                sum(CASE WHEN l.title_de IS NOT NULL THEN 1 ELSE 0 END) as has_de,
                sum(CASE WHEN l.title_fr IS NOT NULL THEN 1 ELSE 0 END) as has_fr,
                sum(CASE WHEN l.title_it IS NOT NULL THEN 1 ELSE 0 END) as has_it,
                count(l) as total
        ''')

        record = result.single()
        print(f"Laws with German titles: {record['has_de']}/{record['total']}")
        print(f"Laws with French titles: {record['has_fr']}/{record['total']}")
        print(f"Laws with Italian titles: {record['has_it']}/{record['total']}")

    driver.close()


def main():
    """Main function to build the focused graph."""
    parser = argparse.ArgumentParser(description='Build focused knowledge graph')
    parser.add_argument('--limit', type=int, help='Limit number of laws to process')
    parser.add_argument('--clear-db', action='store_true', help='Clear database before building')
    parser.add_argument('--batch-size', type=int, default=500, help='Batch size for processing')

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("FOCUSED KNOWLEDGE GRAPH BUILDER")
    print("=" * 60)
    print("This will process only laws with both JSON and HTML content")
    print("Approximately 5,700 laws will be processed")
    print("-" * 60)

    if args.clear_db:
        # In non-interactive mode, just clear
        clear_database()

    # Initialize processor
    processor = UnifiedLawProcessor(
        json_dir="fedlex",
        html_dir="fedlex-assets",
        batch_size=args.batch_size
    )

    start_time = time.time()

    try:
        # Process laws
        print(f"\nStarting processing{' (limited to ' + str(args.limit) + ' laws)' if args.limit else ''}...")
        print("-" * 60)

        stats = processor.process_all_laws(limit=args.limit)

        # Report results
        elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Time elapsed: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"Laws processed: {stats.laws_processed:,}")
        print(f"Articles created: {stats.articles_created:,}")
        print(f"Versions created: {stats.versions_created:,}")
        print(f"Taxonomy nodes: {stats.taxonomy_nodes_created:,}")
        print(f"Relationships: {stats.relationships_created:,}")
        print(f"Languages: {stats.languages_created:,}")
        print(f"Errors: {len(stats.errors)}")

        if stats.laws_processed > 0:
            print(f"\nPerformance:")
            print(f"  Average time per law: {elapsed/stats.laws_processed:.2f} seconds")
            print(f"  Laws per minute: {stats.laws_processed/(elapsed/60):.1f}")

        if stats.errors:
            print(f"\n⚠️  {len(stats.errors)} errors encountered:")
            for i, error in enumerate(stats.errors[:5], 1):
                print(f"  {i}. {error['type']}: {str(error.get('error', ''))[:100]}")
            if len(stats.errors) > 5:
                print(f"  ... and {len(stats.errors) - 5} more")

        # Verify the built graph
        verify_results()

        print("\n✅ Graph build completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        verify_results()

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        print(f"\n❌ Processing failed: {e}")
        raise


if __name__ == "__main__":
    main()