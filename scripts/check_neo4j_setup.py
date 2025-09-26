#!/usr/bin/env python3
"""
Check Neo4j setup for Triple RAG implementation
Verifies:
- Neo4j connection
- APOC procedures availability
- Vector index support
- Existing embeddings
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data_access.neo4j_connection import Neo4jConnectionManager
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def get_neo4j_connection():
    """Get Neo4j connection manager"""
    return Neo4jConnectionManager()


def check_neo4j_connection():
    """Check basic Neo4j connectivity"""
    try:
        conn = get_neo4j_connection()
        result = conn.execute_query("RETURN 1 as test")
        logger.info("✅ Neo4j connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Neo4j connection failed: {e}")
        return False


def check_apoc_procedures():
    """Check if APOC procedures are installed"""
    try:
        conn = get_neo4j_connection()
        query = """
        CALL dbms.procedures()
        YIELD name
        WHERE name STARTS WITH 'apoc.'
        RETURN count(name) as apoc_count
        """
        result = conn.execute_query(query)
        apoc_count = result[0]['apoc_count'] if result else 0

        if apoc_count > 0:
            logger.info(f"✅ APOC procedures available: {apoc_count} procedures found")

            # Check specific procedures we need
            required_procs = ['apoc.path.subgraphAll', 'apoc.path.expandConfig']
            query = """
            CALL dbms.procedures()
            YIELD name
            WHERE name IN $procs
            RETURN collect(name) as found_procs
            """
            result = conn.execute_query(query, {"procs": required_procs})
            found = result[0]['found_procs'] if result else []

            for proc in required_procs:
                if proc in found:
                    logger.info(f"  ✅ {proc} available")
                else:
                    logger.warning(f"  ⚠️ {proc} NOT found")

            return len(found) == len(required_procs)
        else:
            logger.warning("⚠️ APOC procedures NOT installed")
            logger.info("   Install APOC: https://neo4j.com/docs/apoc/current/installation/")
            return False

    except Exception as e:
        logger.error(f"❌ Error checking APOC: {e}")
        return False


def check_vector_index_support():
    """Check if Neo4j supports vector indexes"""
    try:
        conn = get_neo4j_connection()
        # Check Neo4j version
        query = "CALL dbms.components() YIELD name, versions RETURN name, versions[0] as version"
        result = conn.execute_query(query)

        for component in result:
            if component['name'] == 'Neo4j Kernel':
                version = component['version']
                logger.info(f"✅ Neo4j version: {version}")

                # Check if version supports vector indexes (5.11+)
                major, minor = map(int, version.split('.')[:2])
                if major >= 5 and minor >= 11:
                    logger.info("✅ Vector index support available (Neo4j 5.11+)")
                    return True
                else:
                    logger.warning(f"⚠️ Vector indexes require Neo4j 5.11+, found {version}")
                    return False

        return False

    except Exception as e:
        logger.error(f"❌ Error checking vector support: {e}")
        return False


def check_existing_embeddings():
    """Check existing embeddings in the database"""
    try:
        conn = get_neo4j_connection()

        # Count nodes with embeddings
        queries = [
            ("Law", "MATCH (n:Law) WHERE n.embedding IS NOT NULL RETURN count(n) as count"),
            ("Article", "MATCH (n:Article) WHERE n.embedding IS NOT NULL RETURN count(n) as count"),
            ("Paragraph", "MATCH (n:Paragraph) WHERE n.embedding IS NOT NULL RETURN count(n) as count")
        ]

        total_embeddings = 0
        logger.info("\n📊 Existing embeddings:")

        for label, query in queries:
            result = conn.execute_query(query)
            count = result[0]['count'] if result else 0
            total_embeddings += count
            if count > 0:
                logger.info(f"  ✅ {label}: {count:,} embeddings")
            else:
                logger.info(f"  ⚠️ {label}: No embeddings found")

        logger.info(f"\n  Total: {total_embeddings:,} embeddings")

        # Check embedding dimensions
        query = """
        MATCH (n)
        WHERE n.embedding IS NOT NULL
        WITH n LIMIT 1
        RETURN size(n.embedding) as dimensions
        """
        result = conn.execute_query(query)
        if result:
            dims = result[0]['dimensions']
            expected = 384  # all-MiniLM-L6-v2
            if dims == expected:
                logger.info(f"  ✅ Embedding dimensions: {dims} (correct)")
            else:
                logger.warning(f"  ⚠️ Embedding dimensions: {dims} (expected {expected})")

        return total_embeddings > 0

    except Exception as e:
        logger.error(f"❌ Error checking embeddings: {e}")
        return False


def check_existing_indexes():
    """Check existing indexes in the database"""
    try:
        conn = get_neo4j_connection()
        query = "SHOW INDEXES"
        result = conn.execute_query(query)

        logger.info("\n📑 Existing indexes:")
        vector_indexes = []

        for index in result:
            index_type = index.get('type', 'UNKNOWN')
            name = index.get('name', 'unnamed')
            state = index.get('state', 'UNKNOWN')

            if 'vector' in index_type.lower():
                vector_indexes.append(name)
                logger.info(f"  ✅ Vector Index: {name} ({state})")
            elif index_type == 'BTREE':
                logger.info(f"  📍 B-Tree Index: {name} ({state})")

        if not vector_indexes:
            logger.info("  ⚠️ No vector indexes found (will create them)")

        return True

    except Exception as e:
        logger.error(f"❌ Error checking indexes: {e}")
        return False


def main():
    """Run all checks"""
    logger.info("🔍 Checking Neo4j setup for Triple RAG...\n")

    checks = [
        ("Neo4j Connection", check_neo4j_connection),
        ("APOC Procedures", check_apoc_procedures),
        ("Vector Index Support", check_vector_index_support),
        ("Existing Embeddings", check_existing_embeddings),
        ("Existing Indexes", check_existing_indexes)
    ]

    results = {}
    for name, check_func in checks:
        logger.info(f"\nChecking {name}...")
        results[name] = check_func()

    # Summary
    logger.info("\n" + "="*50)
    logger.info("📋 SUMMARY")
    logger.info("="*50)

    all_passed = True
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        logger.info(f"{status} {name}: {'PASSED' if passed else 'FAILED'}")
        if not passed and name != "APOC Procedures":  # APOC is optional
            all_passed = False

    if all_passed:
        logger.info("\n🎉 System ready for Triple RAG implementation!")
    else:
        logger.info("\n⚠️ Some checks failed. Please address the issues above.")
        if not results["APOC Procedures"]:
            logger.info("\n📌 Note: APOC is optional but recommended for graph traversal.")
            logger.info("   The system will use fallback Cypher queries if APOC is unavailable.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())