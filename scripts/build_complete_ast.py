#!/usr/bin/env python3
"""
Build Complete AST for LAWAST

Creates a full Abstract Syntax Tree with paragraph-level granularity
and generates embeddings for all nodes. Optimized for parallel processing.

Usage:
    python scripts/build_complete_ast.py [--workers 16] [--batch-size 32]
"""

import sys
import os
import time
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection
from src.data_access.graph_builder import GraphBuilder
from src.data_access.graph_schema import ArticleNode, ParagraphNode, SubpointNode
from src.data_access.ast_path_builder import ASTPathBuilder
from src.data_access.embedding_generator import create_embedding_generator
from src.extractors.article_extractor import ArticleExtractor
from src.parsers.unified_html_parser import UnifiedHtmlParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ASTBuilder:
    """Builds complete AST with embeddings for all nodes"""

    def __init__(self, workers: int = 16, batch_size: int = 32,
                 checkpoint_file: str = "ast_build_checkpoint.json"):
        """
        Initialize AST builder.

        Args:
            workers: Number of parallel workers
            batch_size: Batch size for embeddings
            checkpoint_file: File for checkpointing progress
        """
        self.workers = workers
        self.batch_size = batch_size
        self.checkpoint_file = checkpoint_file

        self.connection = get_connection()
        self.graph_builder = GraphBuilder(self.connection)
        self.path_builder = ASTPathBuilder()
        self.embedding_generator = create_embedding_generator(batch_size=batch_size)

        self.processed_laws = set()
        self.stats = {
            "laws_processed": 0,
            "articles_updated": 0,
            "paragraphs_created": 0,
            "subpoints_created": 0,
            "embeddings_generated": 0,
            "errors": 0
        }

        self._load_checkpoint()

    def _load_checkpoint(self):
        """Load checkpoint from file if exists"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    self.processed_laws = set(data.get('processed_laws', []))
                    self.stats = data.get('stats', self.stats)
                logger.info(f"Loaded checkpoint: {len(self.processed_laws)} laws already processed")
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")

    def _save_checkpoint(self):
        """Save current progress to checkpoint file"""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump({
                    'processed_laws': list(self.processed_laws),
                    'stats': self.stats,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def get_all_laws(self) -> List[Dict[str, Any]]:
        """Retrieve all laws from Neo4j"""
        query = """
        MATCH (l:Law)
        RETURN l.uri as uri, l.sr_number as sr_number,
               l.title_de as title, l.short_title_de as short_title
        ORDER BY l.sr_number
        """
        results = self.connection.execute_query(query)
        logger.info(f"Found {len(results)} laws in database")
        return results

    def get_law_articles(self, law_uri: str) -> List[Dict[str, Any]]:
        """Get all articles for a specific law"""
        query = """
        MATCH (l:Law {uri: $law_uri})-[:HAS_ARTICLE]->(a:Article)
        RETURN a.uri as uri, a.number as number,
               a.title_de as title, a.content_preview as preview
        ORDER BY a.number
        """
        params = {"law_uri": law_uri}
        return self.connection.execute_query(query, params)

    def update_law_ast(self, law_data: Dict[str, Any]) -> bool:
        """Update law node with AST path and embedding"""
        try:
            sr_number = law_data.get('sr_number')
            if not sr_number:
                return False

            ast_path = self.path_builder.build_law_path(sr_number)

            embedding = self.embedding_generator.generate_law_embedding({
                'title': law_data.get('title'),
                'short_title': law_data.get('short_title')
            })

            query = """
            MATCH (l:Law {uri: $uri})
            SET l.ast_path = $ast_path,
                l.ast_level = 5,
                l.embedding = $embedding
            RETURN l
            """

            params = {
                "uri": law_data['uri'],
                "ast_path": ast_path,
                "embedding": embedding
            }

            result = self.connection.execute_write(query, params)
            return result is not None

        except Exception as e:
            logger.error(f"Failed to update law AST: {e}")
            return False

    def find_html_file(self, sr_number: str) -> Optional[Path]:
        """Find HTML file for a law using fedlex ELI structure"""
        base_path = Path("fedlex-assets/eli/cc")

        sr_parts = sr_number.split('.')
        sr_main = sr_parts[0] if sr_parts else sr_number

        law_dir = base_path / sr_main
        if not law_dir.exists():
            return None

        html_files = list(law_dir.rglob("*de/html/*.html"))
        if html_files:
            return html_files[0]

        return None

    def process_article_with_paragraphs(self, article_data: Dict[str, Any],
                                       law_path: str, html_file: Path) -> Dict[str, int]:
        """Process a single article, extracting paragraphs and creating AST"""
        stats = {"paragraphs": 0, "subpoints": 0, "embeddings": 0}

        try:
            article_uri = article_data['uri']
            article_number = article_data['number']

            article_path = self.path_builder.build_article_path(law_path, article_number)

            extractor = ArticleExtractor()
            extraction_result = extractor.extract(str(html_file))

            if not extraction_result or not extraction_result.data:
                logger.warning(f"No articles extracted from {html_file}")
                return stats

            articles_list = extraction_result.data if isinstance(extraction_result.data, list) else []
            if not articles_list:
                logger.warning(f"No articles in extraction result for {html_file}")
                return stats

            matching_article = None
            for art in articles_list:
                if art.number == article_number:
                    matching_article = art
                    break

            if not matching_article:
                logger.warning(f"Article {article_number} not found in HTML")
                return stats

            article_embedding = self.embedding_generator.generate_article_embedding({
                'title': article_data.get('title'),
                'content_preview': article_data.get('preview')
            })

            full_text_parts = []
            if matching_article.content and matching_article.content.paragraphs:
                for para in matching_article.content.paragraphs:
                    if para.text:
                        full_text_parts.append(para.text)
            content_full = "\n\n".join(full_text_parts) if full_text_parts else ""

            update_query = """
            MATCH (a:Article {uri: $uri})
            SET a.ast_path = $ast_path,
                a.ast_level = 6,
                a.embedding = $embedding,
                a.content_full = $content_full
            RETURN a
            """

            update_params = {
                "uri": article_uri,
                "ast_path": article_path,
                "embedding": article_embedding,
                "content_full": content_full
            }

            self.connection.execute_write(update_query, update_params)
            stats["embeddings"] += 1

            if matching_article.content and matching_article.content.paragraphs:
                for para_idx, paragraph in enumerate(matching_article.content.paragraphs, 1):
                    para_uri = f"{article_uri}/paragraph/{para_idx}"
                    para_path = self.path_builder.build_paragraph_path(article_path, str(para_idx))

                    para_embedding = self.embedding_generator.generate_paragraph_embedding({
                        'text': paragraph.text
                    })

                    paragraph_node = ParagraphNode(
                        uri=para_uri,
                        article_uri=article_uri,
                        number=str(para_idx),
                        text=paragraph.text,
                        ast_path=para_path,
                        ast_level=7,
                        parent_id=article_uri,
                        position=para_idx,
                        word_count=len(paragraph.text.split()) if paragraph.text else 0,
                        has_subpoints=bool(paragraph.subpoints),
                        embedding=para_embedding,
                        language="de"
                    )

                    self.graph_builder.create_paragraph_node(paragraph_node)
                    self.graph_builder.create_has_paragraph(article_uri, para_uri, para_idx)
                    self.graph_builder.create_has_child(article_uri, para_uri)

                    stats["paragraphs"] += 1
                    stats["embeddings"] += 1

                    if paragraph.subpoints:
                        for subpoint_idx, subpoint in enumerate(paragraph.subpoints):
                            subpoint_uri = f"{para_uri}/subpoint/{subpoint.letter}"
                            subpoint_path = self.path_builder.build_subpoint_path(para_path, subpoint.letter)

                            subpoint_embedding = self.embedding_generator.generate_subpoint_embedding({
                                'text': subpoint.text
                            })

                            subpoint_node = SubpointNode(
                                uri=subpoint_uri,
                                paragraph_uri=para_uri,
                                letter=subpoint.letter,
                                text=subpoint.text,
                                ast_path=subpoint_path,
                                ast_level=8,
                                parent_id=para_uri,
                                position=subpoint_idx,
                                word_count=len(subpoint.text.split()) if subpoint.text else 0,
                                embedding=subpoint_embedding,
                                language="de"
                            )

                            self.graph_builder.create_subpoint_node(subpoint_node)
                            self.graph_builder.create_has_subpoint(para_uri, subpoint_uri, subpoint_idx)
                            self.graph_builder.create_has_child(para_uri, subpoint_uri)

                            stats["subpoints"] += 1
                            stats["embeddings"] += 1

            if stats["paragraphs"] > 1:
                for i in range(1, stats["paragraphs"]):
                    prev_uri = f"{article_uri}/paragraph/{i}"
                    next_uri = f"{article_uri}/paragraph/{i+1}"
                    self.graph_builder.create_relationship(prev_uri, next_uri, "NEXT")

        except Exception as e:
            logger.error(f"Failed to process article {article_data.get('number')}: {e}")

        return stats

    def process_law(self, law_data: Dict[str, Any]) -> Dict[str, int]:
        """Process a single law with all its articles"""
        law_uri = law_data['uri']
        sr_number = law_data.get('sr_number')

        logger.info(f"Processing law: SR {sr_number}")

        stats = {"articles": 0, "paragraphs": 0, "subpoints": 0, "embeddings": 0}

        try:
            if not self.update_law_ast(law_data):
                logger.error(f"Failed to update law AST for {sr_number}")
                return stats

            stats["embeddings"] += 1

            law_path = self.path_builder.build_law_path(sr_number)

            html_file = self.find_html_file(sr_number)
            if not html_file:
                logger.warning(f"HTML file not found for SR {sr_number}")
                return stats

            articles = self.get_law_articles(law_uri)
            logger.info(f"Found {len(articles)} articles for SR {sr_number}")

            for article in articles:
                article_stats = self.process_article_with_paragraphs(
                    article, law_path, html_file
                )
                stats["articles"] += 1
                stats["paragraphs"] += article_stats["paragraphs"]
                stats["subpoints"] += article_stats["subpoints"]
                stats["embeddings"] += article_stats["embeddings"]

        except Exception as e:
            logger.error(f"Failed to process law {sr_number}: {e}")

        return stats

    def build_complete_ast(self):
        """Build complete AST for all laws"""
        laws = self.get_all_laws()

        laws_to_process = [law for law in laws if law['uri'] not in self.processed_laws]
        logger.info(f"Processing {len(laws_to_process)} laws (skipping {len(self.processed_laws)} already done)")

        start_time = time.time()

        for i, law in enumerate(laws_to_process, 1):
            try:
                logger.info(f"Processing law {i}/{len(laws_to_process)}")

                law_stats = self.process_law(law)

                self.stats["laws_processed"] += 1
                self.stats["articles_updated"] += law_stats["articles"]
                self.stats["paragraphs_created"] += law_stats["paragraphs"]
                self.stats["subpoints_created"] += law_stats["subpoints"]
                self.stats["embeddings_generated"] += law_stats["embeddings"]

                self.processed_laws.add(law['uri'])

                if i % 10 == 0:
                    self._save_checkpoint()
                    elapsed = time.time() - start_time
                    rate = i / elapsed
                    remaining = (len(laws_to_process) - i) / rate if rate > 0 else 0
                    logger.info(f"Progress: {i}/{len(laws_to_process)} "
                              f"({100*i/len(laws_to_process):.1f}%) - "
                              f"ETA: {remaining/60:.1f} minutes")

            except Exception as e:
                logger.error(f"Failed to process law: {e}")
                self.stats["errors"] += 1

        self._save_checkpoint()

        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("AST Build Complete")
        logger.info(f"  Laws processed: {self.stats['laws_processed']}")
        logger.info(f"  Articles updated: {self.stats['articles_updated']}")
        logger.info(f"  Paragraphs created: {self.stats['paragraphs_created']}")
        logger.info(f"  Subpoints created: {self.stats['subpoints_created']}")
        logger.info(f"  Embeddings generated: {self.stats['embeddings_generated']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"  Total time: {elapsed/60:.1f} minutes")
        logger.info("=" * 60)

    def create_vector_indexes(self):
        """Create Neo4j vector indexes for embeddings"""
        logger.info("Creating vector indexes...")
        self.embedding_generator.create_vector_indexes(self.graph_builder)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Build complete AST with embeddings for all laws"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Number of parallel workers (default: 16)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embeddings (default: 32)"
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="ast_build_checkpoint.json",
        help="Checkpoint file for resume capability"
    )
    parser.add_argument(
        "--create-indexes",
        action="store_true",
        help="Create vector indexes after building AST"
    )

    args = parser.parse_args()

    try:
        builder = ASTBuilder(
            workers=args.workers,
            batch_size=args.batch_size,
            checkpoint_file=args.checkpoint
        )

        builder.build_complete_ast()

        if args.create_indexes:
            builder.create_vector_indexes()

    except KeyboardInterrupt:
        logger.info("AST build interrupted by user")
    except Exception as e:
        logger.error(f"AST build failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()