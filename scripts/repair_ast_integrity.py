#!/usr/bin/env python3
"""
AST Integrity Repair Script

Fixes critical data integrity issues:
1. Creates missing Article-[:BELONGS_TO]->Law relationships
2. Creates missing Paragraph-[:BELONGS_TO]->Article relationships
3. Generates missing AST paths for articles

Usage:
    python scripts/repair_ast_integrity.py [--dry-run] [--batch-size 1000]
"""

import os
import sys
import logging
import argparse
from typing import Dict, Any
from neo4j import GraphDatabase
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data_access.ast_path_builder import ASTPathBuilder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ASTIntegrityRepairer:
    def __init__(self, uri: str, user: str, password: str, batch_size: int = 1000):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.path_builder = ASTPathBuilder()
        self.batch_size = batch_size
        self.stats = {
            'belongs_to_article_law_created': 0,
            'belongs_to_paragraph_article_created': 0,
            'ast_paths_created': 0,
            'errors': 0
        }

    def close(self):
        self.driver.close()

    def get_current_stats(self) -> Dict[str, Any]:
        """Get current database statistics"""
        with self.driver.session() as session:
            stats = {}

            result = session.run('MATCH (a:Article) RETURN count(a) as total')
            stats['total_articles'] = result.single()['total']

            result = session.run('MATCH (a:Article) WHERE a.ast_path IS NOT NULL AND a.ast_path <> "" RETURN count(a) as count')
            stats['articles_with_path'] = result.single()['count']

            result = session.run('MATCH (p:Paragraph) RETURN count(p) as total')
            stats['total_paragraphs'] = result.single()['total']

            result = session.run('MATCH (p:Paragraph) WHERE p.ast_path IS NOT NULL AND p.ast_path <> "" RETURN count(p) as count')
            stats['paragraphs_with_path'] = result.single()['count']

            result = session.run('MATCH (a:Article)-[:BELONGS_TO]->(:Law) RETURN count(a) as count')
            stats['article_law_belongs'] = result.single()['count']

            result = session.run('MATCH (p:Paragraph)-[:BELONGS_TO]->(:Article) RETURN count(p) as count')
            stats['paragraph_article_belongs'] = result.single()['count']

            return stats

    def create_article_law_belongs_to(self, dry_run: bool = False) -> int:
        """Create missing Article-[:BELONGS_TO]->Law relationships"""
        logger.info("Creating Article-[:BELONGS_TO]->Law relationships...")

        with self.driver.session() as session:
            if dry_run:
                result = session.run('''
                    MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
                    WHERE NOT (a)-[:BELONGS_TO]->(l)
                    RETURN count(a) as missing_count
                ''')
                count = result.single()['missing_count']
                logger.info(f"[DRY RUN] Would create {count:,} Article->Law BELONGS_TO relationships")
                return count

            result = session.run('''
                MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
                WHERE NOT (a)-[:BELONGS_TO]->(l)
                WITH l, a
                CALL {
                    WITH l, a
                    MERGE (a)-[:BELONGS_TO]->(l)
                } IN TRANSACTIONS OF $batch_size ROWS
                RETURN count(*) as created
            ''', batch_size=self.batch_size)

            count = result.single()['created']
            self.stats['belongs_to_article_law_created'] = count
            logger.info(f"Created {count:,} Article->Law BELONGS_TO relationships")
            return count

    def create_paragraph_article_belongs_to(self, dry_run: bool = False) -> int:
        """Create missing Paragraph-[:BELONGS_TO]->Article relationships"""
        logger.info("Creating Paragraph-[:BELONGS_TO]->Article relationships...")

        with self.driver.session() as session:
            if dry_run:
                result = session.run('''
                    MATCH (a:Article)-[:HAS_PARAGRAPH]->(p:Paragraph)
                    WHERE NOT (p)-[:BELONGS_TO]->(a)
                    RETURN count(p) as missing_count
                ''')
                count = result.single()['missing_count']
                logger.info(f"[DRY RUN] Would create {count:,} Paragraph->Article BELONGS_TO relationships")
                return count

            result = session.run('''
                MATCH (a:Article)-[:HAS_PARAGRAPH]->(p:Paragraph)
                WHERE NOT (p)-[:BELONGS_TO]->(a)
                WITH a, p
                CALL {
                    WITH a, p
                    MERGE (p)-[:BELONGS_TO]->(a)
                } IN TRANSACTIONS OF $batch_size ROWS
                RETURN count(*) as created
            ''', batch_size=self.batch_size)

            count = result.single()['created']
            self.stats['belongs_to_paragraph_article_created'] = count
            logger.info(f"Created {count:,} Paragraph->Article BELONGS_TO relationships")
            return count

    def generate_missing_article_ast_paths(self, dry_run: bool = False) -> int:
        """Generate AST paths for articles missing them"""
        logger.info("Generating missing Article AST paths...")

        with self.driver.session() as session:
            # Get articles without AST paths
            result = session.run('''
                MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
                WHERE a.ast_path IS NULL OR a.ast_path = ''
                RETURN
                    l.sr_number as sr_number,
                    l.ast_path as law_ast_path,
                    a.number as article_number,
                    id(a) as article_id
                ORDER BY l.sr_number, a.number
            ''')

            articles = list(result)
            total = len(articles)

            if dry_run:
                logger.info(f"[DRY RUN] Would generate {total:,} Article AST paths")
                return total

            logger.info(f"Generating AST paths for {total:,} articles...")

            batch = []
            processed = 0

            for record in articles:
                law_ast_path = record['law_ast_path']
                article_number = record['article_number']
                article_id = record['article_id']

                if not law_ast_path:
                    logger.warning(f"Skipping article {article_number} - law has no AST path")
                    self.stats['errors'] += 1
                    continue

                # Build article AST path
                article_ast_path = self.path_builder.build_article_path(
                    law_ast_path,
                    article_number
                )

                batch.append({
                    'article_id': article_id,
                    'ast_path': article_ast_path
                })

                # Process batch
                if len(batch) >= self.batch_size:
                    self._update_article_ast_paths_batch(session, batch)
                    processed += len(batch)
                    logger.info(f"Progress: {processed:,}/{total:,} articles ({100*processed/total:.1f}%)")
                    batch = []

            # Process remaining
            if batch:
                self._update_article_ast_paths_batch(session, batch)
                processed += len(batch)

            self.stats['ast_paths_created'] = processed
            logger.info(f"Generated {processed:,} Article AST paths")
            return processed

    def _update_article_ast_paths_batch(self, session, batch):
        """Update AST paths for a batch of articles"""
        session.run('''
            UNWIND $batch as item
            MATCH (a:Article)
            WHERE id(a) = item.article_id
            SET a.ast_path = item.ast_path
        ''', batch=batch)

    def validate_repairs(self) -> Dict[str, Any]:
        """Validate that repairs were successful"""
        logger.info("Validating repairs...")

        with self.driver.session() as session:
            validation = {}

            # Check Article->Law BELONGS_TO coverage
            result = session.run('''
                MATCH (a:Article)
                WITH count(a) as total
                MATCH (a:Article)-[:BELONGS_TO]->(:Law)
                RETURN total, count(a) as with_belongs_to,
                       round(100.0 * count(a) / total, 2) as percentage
            ''')
            record = result.single()
            validation['article_belongs_to'] = {
                'total': record['total'],
                'with_belongs_to': record['with_belongs_to'],
                'percentage': record['percentage']
            }

            # Check Paragraph->Article BELONGS_TO coverage
            result = session.run('''
                MATCH (p:Paragraph)
                WITH count(p) as total
                MATCH (p:Paragraph)-[:BELONGS_TO]->(:Article)
                RETURN total, count(p) as with_belongs_to,
                       round(100.0 * count(p) / total, 2) as percentage
            ''')
            record = result.single()
            validation['paragraph_belongs_to'] = {
                'total': record['total'],
                'with_belongs_to': record['with_belongs_to'],
                'percentage': record['percentage']
            }

            # Check Article AST path coverage
            result = session.run('''
                MATCH (a:Article)
                WITH count(a) as total
                MATCH (a:Article)
                WHERE a.ast_path IS NOT NULL AND a.ast_path <> ''
                RETURN total, count(a) as with_path,
                       round(100.0 * count(a) / total, 2) as percentage
            ''')
            record = result.single()
            validation['article_ast_path'] = {
                'total': record['total'],
                'with_path': record['with_path'],
                'percentage': record['percentage']
            }

            return validation

    def repair(self, dry_run: bool = False):
        """Run all repairs"""
        logger.info("=" * 60)
        logger.info("AST Integrity Repair - Starting")
        logger.info("=" * 60)

        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")

        # Show current stats
        logger.info("\nCurrent Database State:")
        stats = self.get_current_stats()
        logger.info(f"  Articles with AST path: {stats['articles_with_path']:,}/{stats['total_articles']:,}")
        logger.info(f"  Paragraphs with AST path: {stats['paragraphs_with_path']:,}/{stats['total_paragraphs']:,}")
        logger.info(f"  Article->Law BELONGS_TO: {stats['article_law_belongs']:,}")
        logger.info(f"  Paragraph->Article BELONGS_TO: {stats['paragraph_article_belongs']:,}")

        # Step 1: Create Article->Law BELONGS_TO relationships
        logger.info("\n" + "=" * 60)
        logger.info("Step 1/3: Create Article->Law BELONGS_TO relationships")
        logger.info("=" * 60)
        self.create_article_law_belongs_to(dry_run)

        # Step 2: Create Paragraph->Article BELONGS_TO relationships
        logger.info("\n" + "=" * 60)
        logger.info("Step 2/3: Create Paragraph->Article BELONGS_TO relationships")
        logger.info("=" * 60)
        self.create_paragraph_article_belongs_to(dry_run)

        # Step 3: Generate missing Article AST paths
        logger.info("\n" + "=" * 60)
        logger.info("Step 3/3: Generate missing Article AST paths")
        logger.info("=" * 60)
        self.generate_missing_article_ast_paths(dry_run)

        if not dry_run:
            # Validate
            logger.info("\n" + "=" * 60)
            logger.info("Validation Results")
            logger.info("=" * 60)
            validation = self.validate_repairs()

            logger.info(f"\nArticle->Law BELONGS_TO: {validation['article_belongs_to']['with_belongs_to']:,}/{validation['article_belongs_to']['total']:,} ({validation['article_belongs_to']['percentage']}%)")
            logger.info(f"Paragraph->Article BELONGS_TO: {validation['paragraph_belongs_to']['with_belongs_to']:,}/{validation['paragraph_belongs_to']['total']:,} ({validation['paragraph_belongs_to']['percentage']}%)")
            logger.info(f"Article AST paths: {validation['article_ast_path']['with_path']:,}/{validation['article_ast_path']['total']:,} ({validation['article_ast_path']['percentage']}%)")

            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("Repair Summary")
            logger.info("=" * 60)
            logger.info(f"Article->Law BELONGS_TO created: {self.stats['belongs_to_article_law_created']:,}")
            logger.info(f"Paragraph->Article BELONGS_TO created: {self.stats['belongs_to_paragraph_article_created']:,}")
            logger.info(f"Article AST paths generated: {self.stats['ast_paths_created']:,}")
            logger.info(f"Errors: {self.stats['errors']}")

            # Check success
            success = (
                validation['article_belongs_to']['percentage'] >= 99.0 and
                validation['paragraph_belongs_to']['percentage'] >= 99.0 and
                validation['article_ast_path']['percentage'] >= 99.0
            )

            if success:
                logger.info("\n✓ AST integrity repair completed successfully!")
            else:
                logger.warning("\n⚠ Some issues remain. Review validation results above.")

        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Repair AST integrity issues in Neo4j')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for operations (default: 1000)')
    args = parser.parse_args()

    # Get Neo4j credentials from environment
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'lawast2024')

    repairer = ASTIntegrityRepairer(uri, user, password, batch_size=args.batch_size)

    try:
        repairer.repair(dry_run=args.dry_run)
    finally:
        repairer.close()


if __name__ == '__main__':
    main()