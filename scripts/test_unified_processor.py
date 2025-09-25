#!/usr/bin/env python3
"""
Test script for the Unified Law Processor

This script tests the new unified processing pipeline that:
1. Processes laws with their JSON + HTML content together
2. Extracts taxonomy once at the end
3. Creates proper relationships
4. Avoids creating orphaned Law nodes
"""

import sys
import logging
from pathlib import Path

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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_database():
    """Clear existing data from the database for clean testing."""
    load_dotenv()

    uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')

    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        # Delete all nodes and relationships
        logger.info("Clearing existing database...")
        session.run("MATCH (n) DETACH DELETE n")

        # Verify cleanup
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()['count']
        logger.info(f"Database cleared. Node count: {count}")

    driver.close()


def verify_results():
    """Verify the results of the processing."""
    load_dotenv()

    uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')

    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        queries = {
            'Total nodes': 'MATCH (n) RETURN count(n) as count',
            'Law nodes': 'MATCH (l:Law) RETURN count(l) as count',
            'Laws WITH articles': '''
                MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
                RETURN count(DISTINCT l) as count
            ''',
            'Laws WITHOUT articles': '''
                MATCH (l:Law)
                WHERE NOT (l)-[:HAS_ARTICLE]->()
                RETURN count(l) as count
            ''',
            'Article nodes': 'MATCH (a:Article) RETURN count(a) as count',
            'Version nodes': 'MATCH (v:Version) RETURN count(v) as count',
            'Taxonomy nodes': '''
                MATCH (n)
                WHERE n:Domain OR n:Book OR n:Chapter OR n:Section
                RETURN count(n) as count
            ''',
            'Language nodes': 'MATCH (l:Language) RETURN count(l) as count',
            'HAS_ARTICLE relationships': '''
                MATCH ()-[r:HAS_ARTICLE]->()
                RETURN count(r) as count
            ''',
            'CONTAINS relationships': '''
                MATCH ()-[r:CONTAINS]->()
                RETURN count(r) as count
            ''',
            'FOLLOWS relationships': '''
                MATCH ()-[r:FOLLOWS]->()
                RETURN count(r) as count
            '''
        }

        print("\n" + "=" * 60)
        print("VERIFICATION RESULTS:")
        print("=" * 60)

        for label, query in queries.items():
            result = session.run(query)
            count = result.single()['count']
            print(f"{label:30}: {count:,}")

        # Check for orphaned articles
        result = session.run('''
            MATCH (a:Article)
            WHERE NOT ()<-[:HAS_ARTICLE]-(a)
            RETURN count(a) as count
        ''')
        orphaned = result.single()['count']
        print(f"{'Orphaned articles':30}: {orphaned:,}")

        # Sample data
        print("\n" + "-" * 60)
        print("SAMPLE DATA:")
        print("-" * 60)

        result = session.run('''
            MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
            RETURN l.uri as law_uri, count(a) as article_count
            ORDER BY article_count DESC
            LIMIT 5
        ''')

        print("\nTop 5 laws by article count:")
        for record in result:
            print(f"  {record['law_uri']}: {record['article_count']} articles")

    driver.close()


def main():
    """Main test function."""
    print("Testing Unified Law Processor")
    print("=" * 60)

    # Option to clear database
    response = input("Clear database before testing? (y/n): ")
    if response.lower() == 'y':
        clear_database()

    # Initialize processor
    processor = UnifiedLawProcessor(
        json_dir="fedlex",
        html_dir="fedlex-assets",
        batch_size=500
    )

    # Test with limited number of laws
    limit = 10  # Process only 10 laws for testing

    print(f"\nProcessing {limit} laws for testing...")
    print("-" * 60)

    try:
        # Process laws
        stats = processor.process_all_laws(limit=limit)

        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Laws processed: {stats.laws_processed}")
        print(f"Articles created: {stats.articles_created}")
        print(f"Versions created: {stats.versions_created}")
        print(f"Taxonomy nodes: {stats.taxonomy_nodes_created}")
        print(f"Relationships: {stats.relationships_created}")
        print(f"Languages: {stats.languages_created}")
        print(f"Errors: {len(stats.errors)}")

        if stats.errors:
            print("\nErrors encountered:")
            for error in stats.errors[:5]:
                print(f"  - {error['type']}: {error.get('error', '')[:100]}")

        # Verify results
        verify_results()

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    main()