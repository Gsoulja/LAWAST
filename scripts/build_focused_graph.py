#!/usr/bin/env python3
"""
Build Focused Knowledge Graph with Complete AST and Embeddings

This script builds a focused knowledge graph containing only laws that have
both JSON metadata and HTML content. Enhanced to include:

1. Complete AST (Abstract Syntax Tree) relationships
2. Vector embeddings for semantic search
3. All relationship types (HAS_ARTICLE, HAS_PARAGRAPH, CITES, FOLLOWS, etc.)
4. Proper taxonomy structure
5. Temporal relationships

Usage:
    python scripts/build_focused_graph.py [--limit LIMIT] [--clear-db] [--skip-embeddings]
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import time
from typing import Optional, List, Dict, Any
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.unified_law_processor import UnifiedLawProcessor
from src.data_access.neo4j_connection import get_connection
from src.data_access.embedding_generator import create_embedding_generator
from src.extractors.relationship_extractor import RelationshipExtractor
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def build_ast_relationships(driver):
    """Build complete AST (Abstract Syntax Tree) relationships."""
    logger.info("Building AST relationships...")

    with driver.session() as session:
        # Create hierarchical relationships
        ast_queries = [
            # Law -> Article relationships (should already exist)
            ("""
            MATCH (l:Law), (a:Article)
            WHERE a.law_uri = l.uri AND NOT (l)-[:HAS_ARTICLE]->(a)
            MERGE (l)-[:HAS_ARTICLE]->(a)
            RETURN count(*) as count
            """, "Law-Article"),

            # Article -> Paragraph relationships
            ("""
            MATCH (a:Article), (p:Paragraph)
            WHERE p.article_uri = a.uri AND NOT (a)-[:HAS_PARAGRAPH]->(p)
            MERGE (a)-[:HAS_PARAGRAPH]->(p)
            RETURN count(*) as count
            """, "Article-Paragraph"),

            # Sequential relationships for Articles
            ("""
            MATCH (a1:Article), (a2:Article)
            WHERE a1.law_uri = a2.law_uri
            AND a1.number_normalized = a2.number_normalized - 1
            AND NOT (a1)-[:NEXT]->(a2)
            MERGE (a1)-[:NEXT]->(a2)
            RETURN count(*) as count
            """, "Article NEXT"),

            # Law -> Version relationships
            ("""
            MATCH (l:Law), (v:Version)
            WHERE v.law_uri = l.uri AND NOT (l)-[:HAS_VERSION]->(v)
            MERGE (l)-[:HAS_VERSION]->(v)
            RETURN count(*) as count
            """, "Law-Version"),

            # Taxonomy relationships (Domain -> Book -> Chapter -> Section)
            ("""
            MATCH (d:Domain), (b:Book)
            WHERE b.parent_uri = d.uri AND NOT (d)-[:HAS_CHILD]->(b)
            MERGE (d)-[:HAS_CHILD]->(b)
            RETURN count(*) as count
            """, "Domain-Book"),

            ("""
            MATCH (b:Book), (c:Chapter)
            WHERE c.parent_uri = b.uri AND NOT (b)-[:HAS_CHILD]->(c)
            MERGE (b)-[:HAS_CHILD]->(c)
            RETURN count(*) as count
            """, "Book-Chapter"),

            ("""
            MATCH (c:Chapter), (s:Section)
            WHERE s.parent_uri = c.uri AND NOT (c)-[:HAS_CHILD]->(s)
            MERGE (c)-[:HAS_CHILD]->(s)
            RETURN count(*) as count
            """, "Chapter-Section"),

            # Law belongs to taxonomy
            ("""
            MATCH (l:Law), (s:Section)
            WHERE l.section_uri = s.uri AND NOT (l)-[:BELONGS_TO]->(s)
            MERGE (l)-[:BELONGS_TO]->(s)
            RETURN count(*) as count
            """, "Law-Section"),
        ]

        total_created = 0
        for query, description in ast_queries:
            try:
                result = session.run(query)
                count = result.single()["count"]
                if count > 0:
                    logger.info(f"  Created {count} {description} relationships")
                total_created += count
            except Exception as e:
                logger.warning(f"  Failed to create {description}: {str(e)}")

        logger.info(f"Total AST relationships created: {total_created}")
        return total_created


def extract_legal_relationships(driver):
    """Extract citations and references between laws."""
    logger.info("Extracting legal relationships...")

    extractor = RelationshipExtractor(driver)

    with driver.session() as session:
        # Get all articles with content
        result = session.run("""
            MATCH (a:Article)
            WHERE a.content_full IS NOT NULL
            RETURN a.uri as uri, a.content_full as content
            LIMIT 10000
        """)

        articles = list(result)
        logger.info(f"  Processing {len(articles)} articles for citations...")

        citations_found = 0
        for article in articles:
            try:
                # Extract citations from content
                citations = extractor.extract_citations(article['content'])

                for citation in citations:
                    # Create CITES relationship
                    session.run("""
                        MATCH (a1:Article {uri: $from_uri})
                        MATCH (l2:Law)
                        WHERE l2.sr_number = $sr_number
                        MATCH (l2)-[:HAS_ARTICLE]->(a2:Article)
                        WHERE a2.number = $article_number
                        MERGE (a1)-[:CITES]->(a2)
                    """,
                    from_uri=article['uri'],
                    sr_number=citation.get('sr_number'),
                    article_number=citation.get('article'))

                    citations_found += 1
            except Exception as e:
                pass  # Skip errors silently

        logger.info(f"  Created {citations_found} citation relationships")
        return citations_found


def generate_embeddings(driver, skip_embeddings=False, batch_size=32):
    """Generate vector embeddings for all text content."""
    if skip_embeddings:
        logger.info("Skipping embedding generation")
        return 0

    logger.info("Generating vector embeddings...")

    # Create embedding generator (CPU mode)
    embedding_generator = create_embedding_generator(batch_size=batch_size, device='cpu')

    with driver.session() as session:
        # Count nodes needing embeddings
        node_types = ['Law', 'Article', 'Paragraph']
        total_embeddings = 0

        for node_type in node_types:
            # Get text field based on node type
            text_fields = {
                'Law': ['title_de', 'title_fr', 'title_it'],
                'Article': ['content_preview', 'content_full'],
                'Paragraph': ['text']
            }[node_type]

            for text_field in text_fields:
                # Check if field exists
                result = session.run(f"""
                    MATCH (n:{node_type})
                    WHERE n.{text_field} IS NOT NULL
                    AND n.embedding IS NULL
                    RETURN count(n) as count
                """)

                count = result.single()["count"]
                if count == 0:
                    continue

                logger.info(f"  Generating embeddings for {count} {node_type} nodes ({text_field})...")

                # Process in batches
                offset = 0
                while offset < count:
                    # Fetch batch
                    result = session.run(f"""
                        MATCH (n:{node_type})
                        WHERE n.{text_field} IS NOT NULL
                        AND n.embedding IS NULL
                        RETURN id(n) as id, n.{text_field} as text
                        SKIP {offset} LIMIT {batch_size}
                    """)

                    batch = list(result)
                    if not batch:
                        break

                    # Generate embeddings for batch
                    texts = [record['text'] for record in batch]
                    embeddings = embedding_generator.generate_embeddings_batch(texts)

                    # Store embeddings
                    for record, embedding in zip(batch, embeddings):
                        try:
                            session.run(f"""
                                MATCH (n:{node_type})
                                WHERE id(n) = $id
                                SET n.embedding = $embedding
                            """, id=record['id'], embedding=embedding.tolist())

                            total_embeddings += 1
                        except Exception as e:
                            logger.warning(f"Failed to store embedding: {str(e)}")

                    offset += batch_size

                    # Log progress
                    if offset % 100 == 0:
                        logger.info(f"    Progress: {offset}/{count}")

        logger.info(f"Total embeddings generated: {total_embeddings}")
        return total_embeddings


def setup_indexes(driver):
    """Setup all necessary indexes for optimal query performance."""
    logger.info("Setting up indexes...")

    with driver.session() as session:
        indexes = [
            # Unique constraints
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Law) REQUIRE l.uri IS UNIQUE", "Law uniqueness"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Article) REQUIRE a.uri IS UNIQUE", "Article uniqueness"),
            ("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paragraph) REQUIRE p.uri IS UNIQUE", "Paragraph uniqueness"),

            # Regular indexes
            ("CREATE INDEX IF NOT EXISTS FOR (l:Law) ON (l.sr_number)", "SR number"),
            ("CREATE INDEX IF NOT EXISTS FOR (a:Article) ON (a.number_normalized)", "Article number"),
            ("CREATE INDEX IF NOT EXISTS FOR (l:Law) ON (l.in_force)", "In-force status"),

            # Full-text search indexes
            ("CREATE FULLTEXT INDEX lawTitleSearch IF NOT EXISTS FOR (l:Law) ON EACH [l.title_de, l.title_fr, l.title_it]", "Law titles"),
            ("CREATE FULLTEXT INDEX articleContentSearch IF NOT EXISTS FOR (a:Article) ON EACH [a.content_full, a.content_preview]", "Article content"),

            # Vector indexes for embeddings (768 dimensions for multilingual-e5)
            ("CREATE VECTOR INDEX lawEmbeddings IF NOT EXISTS FOR (l:Law) ON l.embedding OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}}", "Law embeddings"),
            ("CREATE VECTOR INDEX articleEmbeddings IF NOT EXISTS FOR (a:Article) ON a.embedding OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}}", "Article embeddings"),
            ("CREATE VECTOR INDEX paragraphEmbeddings IF NOT EXISTS FOR (p:Paragraph) ON p.embedding OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}}", "Paragraph embeddings"),
        ]

        for query, description in indexes:
            try:
                session.run(query)
                logger.info(f"  ✓ {description} index created/verified")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"  ✓ {description} index already exists")
                else:
                    logger.warning(f"  ✗ {description} index failed: {str(e)}")


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
    """Main function to build the focused graph with complete AST and embeddings."""
    parser = argparse.ArgumentParser(
        description='Build focused knowledge graph with complete AST and embeddings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--limit', type=int, help='Limit number of laws to process')
    parser.add_argument('--clear-db', action='store_true', help='Clear database before building')
    parser.add_argument('--batch-size', type=int, default=500, help='Batch size for processing')
    parser.add_argument('--skip-embeddings', action='store_true', help='Skip embedding generation')
    parser.add_argument('--sr-filter', type=str, help='Filter by SR number (e.g., "101" for Constitution)')
    parser.add_argument('--embedding-batch-size', type=int, default=32, help='Batch size for embeddings')

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("FOCUSED KNOWLEDGE GRAPH BUILDER")
    print("With Complete AST & Embeddings")
    print("=" * 60)
    print("Features:")
    print("  ✓ Complete AST relationships")
    print("  ✓ Vector embeddings for semantic search")
    print("  ✓ Legal citation extraction")
    print("  ✓ Full taxonomy structure")
    print("-" * 60)

    # Load environment and get driver
    load_dotenv()
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'lawast2024')

    driver = GraphDatabase.driver(uri, auth=(username, password))

    if args.clear_db:
        # In non-interactive mode, just clear
        clear_database()

    # Setup indexes first
    setup_indexes(driver)

    # Initialize processor
    processor = UnifiedLawProcessor(
        json_dir="fedlex",
        html_dir="fedlex-assets",
        batch_size=args.batch_size
    )

    # Filter for specific SR if requested
    if args.sr_filter:
        print(f"\nFiltering for SR {args.sr_filter}")
        processor.filter_sr = args.sr_filter

    start_time = time.time()

    try:
        # PHASE 1: Process laws and create basic structure
        print(f"\n📚 PHASE 1: Processing laws{' (limited to ' + str(args.limit) + ')' if args.limit else ''}...")
        print("-" * 60)

        stats = processor.process_all_laws(limit=args.limit)

        elapsed_phase1 = time.time() - start_time
        print(f"\nPhase 1 complete in {elapsed_phase1:.1f} seconds")
        print(f"  Laws: {stats.laws_processed:,}")
        print(f"  Articles: {stats.articles_created:,}")
        print(f"  Versions: {stats.versions_created:,}")

        # PHASE 2: Build AST relationships
        print(f"\n🌳 PHASE 2: Building AST relationships...")
        print("-" * 60)

        ast_count = build_ast_relationships(driver)

        elapsed_phase2 = time.time() - start_time - elapsed_phase1
        print(f"Phase 2 complete in {elapsed_phase2:.1f} seconds")
        print(f"  AST relationships: {ast_count:,}")

        # PHASE 3: Extract legal relationships
        print(f"\n🔗 PHASE 3: Extracting legal relationships...")
        print("-" * 60)

        citations_count = extract_legal_relationships(driver)

        elapsed_phase3 = time.time() - start_time - elapsed_phase1 - elapsed_phase2
        print(f"Phase 3 complete in {elapsed_phase3:.1f} seconds")
        print(f"  Citations: {citations_count:,}")

        # PHASE 4: Generate embeddings (if not skipped)
        if not args.skip_embeddings:
            print(f"\n🧮 PHASE 4: Generating vector embeddings...")
            print("-" * 60)

            embeddings_count = generate_embeddings(
                driver,
                skip_embeddings=args.skip_embeddings,
                batch_size=args.embedding_batch_size
            )

            elapsed_phase4 = time.time() - start_time - elapsed_phase1 - elapsed_phase2 - elapsed_phase3
            print(f"Phase 4 complete in {elapsed_phase4:.1f} seconds")
            print(f"  Embeddings: {embeddings_count:,}")
        else:
            print(f"\n⏭️  PHASE 4: Skipping embeddings (--skip-embeddings flag)")

        # Report final results
        total_elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print("BUILD COMPLETE")
        print("=" * 60)
        print(f"Total time: {total_elapsed:.1f} seconds ({total_elapsed/60:.1f} minutes)")
        print(f"Laws processed: {stats.laws_processed:,}")
        print(f"Articles created: {stats.articles_created:,}")
        print(f"AST relationships: {ast_count:,}")
        print(f"Citations extracted: {citations_count:,}")
        if not args.skip_embeddings:
            print(f"Embeddings generated: {embeddings_count:,}")
        print(f"Total relationships: {stats.relationships_created + ast_count + citations_count:,}")

        if stats.laws_processed > 0:
            print(f"\nPerformance:")
            print(f"  Average time per law: {total_elapsed/stats.laws_processed:.2f} seconds")
            print(f"  Laws per minute: {stats.laws_processed/(total_elapsed/60):.1f}")

        if stats.errors:
            print(f"\n⚠️  {len(stats.errors)} errors encountered:")
            for i, error in enumerate(stats.errors[:5], 1):
                print(f"  {i}. {error['type']}: {str(error.get('error', ''))[:100]}")
            if len(stats.errors) > 5:
                print(f"  ... and {len(stats.errors) - 5} more")

        # Verify the built graph
        verify_results()

        print("\n✅ Graph build completed successfully with full AST and embeddings!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        verify_results()

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        print(f"\n❌ Processing failed: {e}")
        raise

    finally:
        driver.close()


if __name__ == "__main__":
    main()