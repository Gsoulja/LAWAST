#!/usr/bin/env python3
"""
Run the Neo4j Storage Pipeline for LAWAST

This script processes extracted content from HTML files and stores it in Neo4j,
creating nodes for taxonomy, articles, and all relationships.

Usage:
    python scripts/run_storage_pipeline.py [--input INPUT_DIR] [--batch-size BATCH_SIZE]
"""

import sys
import os
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection
from src.data_access.storage_pipeline import Neo4jStoragePipeline
from src.extractors.extracted_content import ExtractedContent
from src.extractors.taxonomy_extractor import TaxonomyExtractor
from src.extractors.article_extractor import ArticleExtractor
from src.extractors.reference_patterns import ReferencePatternDetector
from src.parsers.unified_html_parser import UnifiedHtmlParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_content_from_html(html_file: Path) -> Optional[ExtractedContent]:
    """
    Extract complete content from an HTML file using all extraction modules.

    Args:
        html_file: Path to HTML file

    Returns:
        ExtractedContent or None if extraction fails
    """
    try:
        logger.info(f"Extracting content from {html_file}")

        # Initialize extractors
        parser = UnifiedHtmlParser()
        taxonomy_extractor = TaxonomyExtractor()
        article_extractor = ArticleExtractor()
        reference_detector = ReferencePatternDetector()

        # Parse HTML
        parsed_doc = parser.parse(str(html_file))
        if not parsed_doc:
            logger.error(f"Failed to parse HTML: {html_file}")
            return None

        # Extract taxonomy - returns TaxonomyResult object directly
        taxonomy_data = taxonomy_extractor.extract_from_file(str(html_file))
        if not taxonomy_data:
            logger.warning(f"Failed to extract taxonomy from {html_file}")

        # Extract articles - returns list of Article objects directly
        articles = article_extractor.extract_articles(str(html_file))
        if not articles:
            logger.warning(f"No articles extracted from {html_file}")

        # Extract references from article content
        references = []
        if articles:
            for article in articles:
                if article.content and article.content.raw_html:
                    refs = reference_detector.extract_references(article.content.raw_html)
                    # Set source URI for references
                    for ref in refs:
                        ref.source_uri = article.uri
                    references.extend(refs)

        # Build ExtractedContent
        content = ExtractedContent(
            taxonomy=taxonomy_data,
            articles=articles or [],
            references=references,
            metadata={
                "source_file": str(html_file),
                "extraction_date": datetime.now().isoformat(),
                "law_uri": taxonomy_data.uri if taxonomy_data else None
            },
            source_file=str(html_file),
            law_uri=taxonomy_data.uri if taxonomy_data else None
        )

        # Validate content
        errors = content.validate()
        if errors:
            logger.warning(f"Validation issues: {errors}")

        return content

    except Exception as e:
        logger.error(f"Failed to extract content from {html_file}: {e}")
        return None


def process_html_files(
    input_dir: Path,
    batch_size: int = 1000,
    limit: Optional[int] = None
) -> None:
    """
    Process HTML files and store content in Neo4j.

    Args:
        input_dir: Directory containing HTML files
        batch_size: Batch size for Neo4j operations
        limit: Maximum number of files to process (None for all)
    """
    # Find HTML files
    html_files = list(input_dir.rglob("*.html"))
    if limit:
        html_files = html_files[:limit]

    logger.info(f"Found {len(html_files)} HTML files to process")

    if not html_files:
        logger.warning("No HTML files found")
        return

    # Check Neo4j connection
    connection = get_connection()
    if not connection.health_check():
        logger.error("Neo4j connection failed")
        return

    # Initialize storage pipeline
    pipeline = Neo4jStoragePipeline(
        connection=connection,
        batch_size=batch_size,
        checkpoint_file="storage_pipeline_checkpoint.json"
    )

    # Process each file
    total_processed = 0
    total_errors = 0
    start_time = time.time()

    for i, html_file in enumerate(html_files, 1):
        try:
            logger.info(f"Processing file {i}/{len(html_files)}: {html_file.name}")

            # Extract content
            content = extract_content_from_html(html_file)
            if not content:
                logger.error(f"Failed to extract content from {html_file}")
                total_errors += 1
                continue

            # Store in Neo4j
            stats = pipeline.store_extracted_content(content, resume=(i == 1))

            # Report statistics
            logger.info(f"Stored: {stats.articles_created} articles, "
                       f"{stats.taxonomy_nodes_created} taxonomy nodes, "
                       f"{stats.relationships_created} relationships")

            total_processed += 1

            # Progress report every 10 files
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(html_files) - i) / rate if rate > 0 else 0
                logger.info(f"Progress: {i}/{len(html_files)} files "
                          f"({100*i/len(html_files):.1f}%) - "
                          f"ETA: {remaining:.0f} seconds")

        except Exception as e:
            logger.error(f"Failed to process {html_file}: {e}")
            total_errors += 1

    # Final report
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("Storage Pipeline Complete")
    logger.info(f"  Total files: {len(html_files)}")
    logger.info(f"  Processed: {total_processed}")
    logger.info(f"  Errors: {total_errors}")
    logger.info(f"  Total time: {elapsed:.1f} seconds")
    logger.info(f"  Average: {elapsed/len(html_files):.2f} seconds/file")
    logger.info("=" * 60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run Neo4j storage pipeline for extracted content"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("fedlex-assets"),
        help="Input directory containing HTML files (default: fedlex-assets)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for Neo4j operations (default: 1000)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of files to process (default: all)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check input directory
    if not args.input.exists():
        logger.error(f"Input directory not found: {args.input}")
        sys.exit(1)

    # Run pipeline
    try:
        process_html_files(
            input_dir=args.input,
            batch_size=args.batch_size,
            limit=args.limit
        )
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()