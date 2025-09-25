#!/usr/bin/env python3
"""
Create optimized indexes for Neo4j Storage Pipeline

This script creates the necessary indexes and constraints to optimize
the storage pipeline performance for 500K+ articles.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_indexes():
    """Create all necessary indexes for optimal performance"""

    connection = get_connection()

    # Check connection
    if not connection.health_check():
        logger.error("Neo4j connection failed")
        return False

    logger.info("Creating Neo4j indexes for storage pipeline...")

    # Define indexes to create
    indexes = [
        # Article indexes for fast lookups
        ("Article URI Index",
         "CREATE INDEX article_uri IF NOT EXISTS FOR (a:Article) ON (a.uri)"),

        ("Article Number Index",
         "CREATE INDEX article_number IF NOT EXISTS FOR (a:Article) ON (a.number_normalized)"),

        ("Article Law URI Index",
         "CREATE INDEX article_law_uri IF NOT EXISTS FOR (a:Article) ON (a.law_uri)"),

        # Taxonomy indexes
        ("Domain Name Index",
         "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)"),

        ("Book URI Index",
         "CREATE INDEX book_uri IF NOT EXISTS FOR (b:Book) ON (b.uri)"),

        ("Chapter URI Index",
         "CREATE INDEX chapter_uri IF NOT EXISTS FOR (c:Chapter) ON (c.uri)"),

        ("Section URI Index",
         "CREATE INDEX section_uri IF NOT EXISTS FOR (s:Section) ON (s.uri)"),

        # Law indexes
        ("Law URI Index",
         "CREATE INDEX law_uri IF NOT EXISTS FOR (l:Law) ON (l.uri)"),

        ("Law SR Number Index",
         "CREATE INDEX law_sr_number IF NOT EXISTS FOR (l:Law) ON (l.sr_number)"),

        # Composite indexes for common queries
        ("Article Composite Index",
         "CREATE INDEX article_composite IF NOT EXISTS FOR (a:Article) ON (a.law_uri, a.number_normalized)"),
    ]

    # Define constraints (ensure uniqueness)
    constraints = [
        ("Article URI Constraint",
         "CREATE CONSTRAINT article_uri_unique IF NOT EXISTS FOR (a:Article) REQUIRE a.uri IS UNIQUE"),

        ("Law URI Constraint",
         "CREATE CONSTRAINT law_uri_unique IF NOT EXISTS FOR (l:Law) REQUIRE l.uri IS UNIQUE"),

        ("Domain URI Constraint",
         "CREATE CONSTRAINT domain_uri_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.uri IS UNIQUE"),

        ("Book URI Constraint",
         "CREATE CONSTRAINT book_uri_unique IF NOT EXISTS FOR (b:Book) REQUIRE b.uri IS UNIQUE"),

        ("Chapter URI Constraint",
         "CREATE CONSTRAINT chapter_uri_unique IF NOT EXISTS FOR (c:Chapter) REQUIRE c.uri IS UNIQUE"),

        ("Section URI Constraint",
         "CREATE CONSTRAINT section_uri_unique IF NOT EXISTS FOR (s:Section) REQUIRE s.uri IS UNIQUE"),
    ]

    success_count = 0
    error_count = 0

    # Create constraints first (they automatically create indexes)
    logger.info("Creating constraints...")
    for name, query in constraints:
        try:
            connection.execute_write(query)
            logger.info(f"  ✅ Created: {name}")
            success_count += 1
        except Exception as e:
            if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                logger.debug(f"  ℹ️ Already exists: {name}")
            else:
                logger.error(f"  ❌ Failed to create {name}: {e}")
                error_count += 1

    # Create additional indexes
    logger.info("Creating indexes...")
    for name, query in indexes:
        try:
            connection.execute_write(query)
            logger.info(f"  ✅ Created: {name}")
            success_count += 1
        except Exception as e:
            if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                logger.debug(f"  ℹ️ Already exists: {name}")
            else:
                logger.error(f"  ❌ Failed to create {name}: {e}")
                error_count += 1

    # Create text indexes for full-text search (if needed)
    logger.info("Creating full-text indexes...")
    fulltext_indexes = [
        ("Article Content Search",
         """CREATE FULLTEXT INDEX article_content_search IF NOT EXISTS
            FOR (a:Article)
            ON EACH [a.content_preview, a.title_de, a.title_fr, a.title_it]"""),
    ]

    for name, query in fulltext_indexes:
        try:
            connection.execute_write(query)
            logger.info(f"  ✅ Created: {name}")
            success_count += 1
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"  ℹ️ Already exists: {name}")
            else:
                logger.error(f"  ❌ Failed to create {name}: {e}")
                error_count += 1

    # Report results
    logger.info("=" * 60)
    logger.info("Index Creation Complete")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Errors: {error_count}")

    # Verify indexes
    logger.info("Verifying indexes...")
    try:
        result = connection.execute_query("SHOW INDEXES")
        logger.info(f"  Total indexes in database: {len(result)}")

        # Show index details
        for index in result[:5]:  # Show first 5
            logger.debug(f"    - {index.get('name', 'unnamed')}: {index.get('state', 'unknown')}")
    except Exception as e:
        logger.warning(f"Could not verify indexes: {e}")

    logger.info("=" * 60)

    return error_count == 0


def analyze_statistics():
    """Update statistics for query optimization"""
    logger.info("Updating database statistics...")

    connection = get_connection()

    try:
        # Analyze the database for query optimization
        connection.execute_write("CALL db.analyze()")
        logger.info("✅ Database statistics updated")
    except Exception as e:
        logger.warning(f"Could not update statistics: {e}")


def main():
    """Main entry point"""
    logger.info("Neo4j Index Optimization for Storage Pipeline")
    logger.info("=" * 60)

    # Create indexes
    success = create_indexes()

    if success:
        # Update statistics
        analyze_statistics()
        logger.info("✅ Index optimization complete")
    else:
        logger.error("❌ Some indexes failed to create")
        sys.exit(1)


if __name__ == "__main__":
    main()