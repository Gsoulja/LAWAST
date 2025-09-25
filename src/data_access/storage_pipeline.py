"""
Neo4j Storage Pipeline for LAWAST

Efficient batch storage pipeline for Neo4j that creates nodes and relationships
for taxonomy, articles, and references. Handles 500K+ articles with proper
indexing, deduplication, and transaction management.

Features:
- Batch processing with UNWIND operations
- Checkpoint/resume capability
- Transaction management with rollback
- Memory-efficient streaming
- Progress tracking and reporting
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Generator, Tuple

from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from .batch_processor import BatchProcessor, ProcessingCheckpoint
from .graph_builder import GraphBuilder
from .neo4j_connection import Neo4jConnectionManager, get_connection
from .graph_schema import (
    NodeLabels, RelationshipTypes,
    ArticleNode, DomainNode, BookNode, ChapterNode, SectionNode
)
from ..extractors.extracted_content import ExtractedContent
from ..extractors.taxonomy_extractor import HierarchyLevel
from ..extractors.article_extractor import Article

logger = logging.getLogger(__name__)


@dataclass
class StorageStatistics:
    """Statistics for storage pipeline operations"""
    taxonomy_nodes_created: int = 0
    articles_created: int = 0
    relationships_created: int = 0
    duplicates_skipped: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def get_throughput(self) -> float:
        """Calculate nodes per second throughput"""
        if not self.start_time or not self.end_time:
            return 0.0
        duration = (self.end_time - self.start_time).total_seconds()
        if duration == 0:
            return 0.0
        total_nodes = self.taxonomy_nodes_created + self.articles_created
        return total_nodes / duration


class Neo4jStoragePipeline(BatchProcessor):
    """
    Storage pipeline for persisting extracted content to Neo4j.

    Extends BatchProcessor to leverage checkpoint/resume capabilities
    and batch processing infrastructure.
    """

    def __init__(
        self,
        connection: Optional[Neo4jConnectionManager] = None,
        batch_size: int = 1000,
        checkpoint_file: str = "storage_pipeline_checkpoint.json",
        max_workers: int = 1
    ):
        """
        Initialize the storage pipeline.

        Args:
            connection: Neo4j connection manager
            batch_size: Number of nodes to process per batch
            checkpoint_file: Path to checkpoint file for recovery
            max_workers: Number of parallel workers (set to 1 for Neo4j transactions)
        """
        super().__init__(
            graph_builder=GraphBuilder(connection or get_connection()),
            batch_size=batch_size,
            checkpoint_file=checkpoint_file,
            max_workers=max_workers
        )
        self.connection = connection or get_connection()
        self.statistics = StorageStatistics()

    def store_extracted_content(
        self,
        content: ExtractedContent,
        resume: bool = True
    ) -> StorageStatistics:
        """
        Store extracted content to Neo4j.

        Processes content in three phases:
        1. Create taxonomy hierarchy nodes
        2. Create article nodes
        3. Create all relationships

        Args:
            content: Extracted content from HTML processing
            resume: Whether to resume from checkpoint if available

        Returns:
            Storage statistics with counts and performance metrics
        """
        self.statistics = StorageStatistics(start_time=datetime.now())

        # Validate content
        validation_errors = content.validate()
        if validation_errors:
            logger.warning(f"Validation issues found: {validation_errors}")
            for error in validation_errors:
                self.statistics.errors.append({
                    "type": "validation",
                    "message": error,
                    "timestamp": datetime.now().isoformat()
                })

        try:
            # Load checkpoint if resuming
            if resume and self.load_checkpoint():
                logger.info(f"Resuming from checkpoint: {self.checkpoint.last_processed_file}")
                phase = self.checkpoint.statistics.get("current_phase", "taxonomy")
            else:
                phase = "taxonomy"
                self.checkpoint = ProcessingCheckpoint(
                    total_files=1,
                    start_time=datetime.now()
                )

            # Phase 1: Create taxonomy nodes
            if phase == "taxonomy":
                logger.info("Phase 1: Creating taxonomy nodes...")
                self._store_taxonomy(content.taxonomy)
                self.checkpoint.statistics["current_phase"] = "articles"
                self.save_checkpoint()
                phase = "articles"

            # Phase 2: Create article nodes
            if phase == "articles":
                logger.info("Phase 2: Creating article nodes...")
                self._store_articles(content.articles, content.law_uri)
                self.checkpoint.statistics["current_phase"] = "relationships"
                self.save_checkpoint()
                phase = "relationships"

            # Phase 3: Create relationships
            if phase == "relationships":
                logger.info("Phase 3: Creating relationships...")
                self._create_relationships(content)
                self.checkpoint.statistics["current_phase"] = "completed"
                self.save_checkpoint()

            # Mark as completed
            self.checkpoint.processed_files = 1
            self.save_checkpoint()

        except Exception as e:
            logger.error(f"Storage pipeline failed: {e}")
            self.statistics.errors.append({
                "type": "pipeline_error",
                "message": str(e),
                "phase": phase,
                "timestamp": datetime.now().isoformat()
            })
            raise

        finally:
            self.statistics.end_time = datetime.now()
            self._report_statistics()

        return self.statistics

    def _store_taxonomy(self, taxonomy):
        """Store taxonomy hierarchy nodes"""
        if not taxonomy or not taxonomy.hierarchy:
            logger.warning("No taxonomy hierarchy to store")
            return

        nodes_to_create = []

        # Process hierarchy levels
        for level in taxonomy.hierarchy:
            nodes_to_create.extend(self._process_hierarchy_level(level))

        # Batch create taxonomy nodes
        if nodes_to_create:
            created = self._batch_create_taxonomy_nodes(nodes_to_create)
            self.statistics.taxonomy_nodes_created += created
            logger.info(f"Created {created} taxonomy nodes")

    def _process_hierarchy_level(self, level: HierarchyLevel) -> List[Dict[str, Any]]:
        """Process a hierarchy level and its children recursively"""
        nodes = []

        # Create node data for this level
        node_data = {
            "uri": level.uri or f"taxonomy/{level.type}/{level.number}",
            "type": level.type,
            "number": level.number,
            "name": level.title.get("de", level.title.get("fr", level.title.get("it", "")))
        }

        # Add multi-language titles
        for lang, title in level.title.items():
            node_data[f"title_{lang}"] = title

        if level.parent_uri:
            node_data["parent_uri"] = level.parent_uri

        nodes.append(node_data)

        # Process children recursively
        for child in level.children:
            # Set parent URI for child if not set
            if not child.parent_uri:
                child.parent_uri = node_data["uri"]
            nodes.extend(self._process_hierarchy_level(child))

        return nodes

    def _batch_create_taxonomy_nodes(self, nodes: List[Dict[str, Any]]) -> int:
        """Create taxonomy nodes in batches using UNWIND"""
        if not nodes:
            return 0

        # Group nodes by type
        nodes_by_type = {}
        for node in nodes:
            node_type = node.get("type", "Section")
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node)

        total_created = 0

        for node_type, type_nodes in nodes_by_type.items():
            # Map type to label
            label_map = {
                "Domain": NodeLabels.DOMAIN.value,
                "Book": NodeLabels.BOOK.value,
                "Chapter": NodeLabels.CHAPTER.value,
                "Section": NodeLabels.SECTION.value
            }
            label = label_map.get(node_type, NodeLabels.SECTION.value)

            # Process in batches
            for i in range(0, len(type_nodes), self.batch_size):
                batch = type_nodes[i:i + self.batch_size]

                query = f"""
                UNWIND $batch AS node
                MERGE (n:{label} {{uri: node.uri}})
                SET n += node
                RETURN count(n) AS created
                """

                try:
                    result = self.connection.execute_write(query, {"batch": batch})
                    if result:
                        created = result[0]["created"]
                        total_created += created
                        logger.debug(f"Created {created} {label} nodes")
                except Exception as e:
                    logger.error(f"Failed to create {label} nodes: {e}")
                    self.statistics.errors.append({
                        "type": "node_creation",
                        "label": label,
                        "error": str(e)
                    })

        return total_created

    def _store_articles(self, articles: List[Article], law_uri: Optional[str]):
        """Store article nodes in batches"""
        if not articles:
            logger.warning("No articles to store")
            return

        # Process articles in batches
        for i in range(0, len(articles), self.batch_size):
            batch = articles[i:i + self.batch_size]

            # Convert articles to node data
            nodes_data = []
            for article in batch:
                node_data = {
                    "uri": article.uri,
                    "number": article.number,
                    "number_normalized": article.number_normalized,
                    "law_uri": law_uri or article.metadata.get("law_uri")
                }

                # Add titles
                for lang, title in article.titles.items():
                    node_data[f"title_{lang}"] = title

                # Add content summary
                if article.content:
                    paragraphs_count = len(article.content.paragraphs)
                    node_data["paragraphs_count"] = paragraphs_count

                    # Store first paragraph as preview
                    if article.content.paragraphs:
                        node_data["content_preview"] = article.content.paragraphs[0].text[:500]

                # Add metadata - filter out complex objects
                for key, value in article.metadata.items():
                    # Only add primitive types (str, int, float, bool) or lists of primitives
                    if isinstance(value, (str, int, float, bool)):
                        node_data[key] = value
                    elif isinstance(value, list) and all(isinstance(v, (str, int, float, bool)) for v in value):
                        node_data[key] = value
                    # Skip complex objects like dicts that Neo4j can't store as properties
                nodes_data.append(node_data)

            # Create article nodes
            query = f"""
            UNWIND $batch AS article
            MERGE (a:{NodeLabels.ARTICLE.value} {{uri: article.uri}})
            SET a += article
            RETURN count(a) AS created
            """

            try:
                result = self.connection.execute_write(query, {"batch": nodes_data})
                if result:
                    created = result[0]["created"]
                    self.statistics.articles_created += created
                    logger.info(f"Created {created} article nodes (batch {i//self.batch_size + 1})")

                    # Update checkpoint
                    self.checkpoint.statistics["articles_processed"] = i + len(batch)
                    if i % (self.batch_size * 10) == 0:  # Save every 10 batches
                        self.save_checkpoint()

            except Exception as e:
                logger.error(f"Failed to create article batch: {e}")
                self.statistics.errors.append({
                    "type": "article_creation",
                    "batch_start": i,
                    "error": str(e)
                })

    def _create_relationships(self, content: ExtractedContent):
        """Create all relationships between nodes"""
        relationships_created = 0

        # 1. Create taxonomy CONTAINS relationships
        if content.taxonomy and content.taxonomy.hierarchy:
            rels = self._create_taxonomy_relationships(content.taxonomy.hierarchy)
            relationships_created += rels
            logger.info(f"Created {rels} taxonomy relationships")

        # 2. Create HAS_ARTICLE relationships (Law -> Article)
        if content.law_uri and content.articles:
            rels = self._create_law_article_relationships(content.law_uri, content.articles)
            relationships_created += rels
            logger.info(f"Created {rels} law-article relationships")

        # 3. Create REFERENCES relationships between articles
        if content.references:
            rels = self._create_reference_relationships(content.references)
            relationships_created += rels
            logger.info(f"Created {rels} reference relationships")

        # 4. Create FOLLOWS relationships (sequential articles)
        if content.articles:
            rels = self._create_follows_relationships(content.articles)
            relationships_created += rels
            logger.info(f"Created {rels} follows relationships")

        self.statistics.relationships_created = relationships_created

    def _create_taxonomy_relationships(self, hierarchy: List[HierarchyLevel]) -> int:
        """Create CONTAINS relationships for taxonomy hierarchy"""
        relationships = []

        for level in hierarchy:
            # Create relationships to children
            for child in level.children:
                relationships.append({
                    "from_uri": level.uri or f"taxonomy/{level.type}/{level.number}",
                    "to_uri": child.uri or f"taxonomy/{child.type}/{child.number}",
                    "type": RelationshipTypes.CONTAINS.value
                })
                # Recursively process children
                self._collect_hierarchy_relationships(child, relationships)

        return self._batch_create_relationships(relationships)

    def _collect_hierarchy_relationships(self, level: HierarchyLevel, relationships: List[Dict]):
        """Recursively collect hierarchy relationships"""
        for child in level.children:
            relationships.append({
                "from_uri": level.uri or f"taxonomy/{level.type}/{level.number}",
                "to_uri": child.uri or f"taxonomy/{child.type}/{child.number}",
                "type": RelationshipTypes.CONTAINS.value
            })
            self._collect_hierarchy_relationships(child, relationships)

    def _create_law_article_relationships(self, law_uri: str, articles: List[Article]) -> int:
        """Create HAS_ARTICLE relationships"""
        relationships = [
            {
                "from_uri": law_uri,
                "to_uri": article.uri,
                "type": RelationshipTypes.HAS_ARTICLE.value
            }
            for article in articles
        ]
        return self._batch_create_relationships(relationships)

    def _create_reference_relationships(self, references) -> int:
        """Create REFERENCES and CITES relationships"""
        relationships = []

        for ref in references:
            # Check if reference is external based on target
            is_external = hasattr(ref, 'is_external') and ref.is_external

            rel_type = (RelationshipTypes.CITES.value
                       if is_external
                       else RelationshipTypes.REFERENCES.value)

            # Handle different reference object structures
            from_uri = getattr(ref, 'source_uri', None) or getattr(ref, 'source', None)
            to_uri = getattr(ref, 'target_uri', None) or getattr(ref, 'target', None)

            if from_uri and to_uri:
                relationships.append({
                    "from_uri": from_uri,
                    "to_uri": to_uri,
                    "type": rel_type,
                    "properties": {
                        "text": getattr(ref, 'text', '')[:500] if hasattr(ref, 'text') else None,
                        "context": getattr(ref, 'context', '')[:500] if hasattr(ref, 'context') else None
                    }
                })

        return self._batch_create_relationships(relationships)

    def _create_follows_relationships(self, articles: List[Article]) -> int:
        """Create FOLLOWS relationships between sequential articles"""
        if len(articles) < 2:
            return 0

        # Sort articles by normalized number
        sorted_articles = sorted(articles, key=lambda a: a.number_normalized)

        relationships = []
        for i in range(len(sorted_articles) - 1):
            relationships.append({
                "from_uri": sorted_articles[i].uri,
                "to_uri": sorted_articles[i + 1].uri,
                "type": RelationshipTypes.FOLLOWS.value
            })

        return self._batch_create_relationships(relationships)

    def _batch_create_relationships(self, relationships: List[Dict[str, Any]]) -> int:
        """Create relationships in batches using UNWIND"""
        if not relationships:
            return 0

        total_created = 0

        for i in range(0, len(relationships), self.batch_size):
            batch = relationships[i:i + self.batch_size]

            query = f"""
            UNWIND $batch AS rel
            MATCH (a {{uri: rel.from_uri}})
            MATCH (b {{uri: rel.to_uri}})
            MERGE (a)-[r:RELATIONSHIP_TYPE]->(b)
            RETURN count(r) AS created
            """

            # Group by relationship type for efficiency
            rels_by_type = {}
            for rel in batch:
                rel_type = rel["type"]
                if rel_type not in rels_by_type:
                    rels_by_type[rel_type] = []
                rels_by_type[rel_type].append(rel)

            for rel_type, typed_rels in rels_by_type.items():
                typed_query = query.replace("RELATIONSHIP_TYPE", rel_type)

                try:
                    result = self.connection.execute_write(typed_query, {"batch": typed_rels})
                    if result:
                        created = result[0]["created"]
                        total_created += created
                        logger.debug(f"Created {created} {rel_type} relationships")
                except Exception as e:
                    logger.error(f"Failed to create {rel_type} relationships: {e}")
                    self.statistics.errors.append({
                        "type": "relationship_creation",
                        "rel_type": rel_type,
                        "error": str(e)
                    })

        return total_created

    def _report_statistics(self):
        """Report storage pipeline statistics"""
        logger.info("=" * 60)
        logger.info("Storage Pipeline Statistics:")
        logger.info(f"  Taxonomy nodes created: {self.statistics.taxonomy_nodes_created}")
        logger.info(f"  Articles created: {self.statistics.articles_created}")
        logger.info(f"  Relationships created: {self.statistics.relationships_created}")
        logger.info(f"  Duplicates skipped: {self.statistics.duplicates_skipped}")
        logger.info(f"  Errors encountered: {len(self.statistics.errors)}")

        throughput = self.statistics.get_throughput()
        logger.info(f"  Throughput: {throughput:.1f} nodes/second")

        if self.statistics.start_time and self.statistics.end_time:
            duration = (self.statistics.end_time - self.statistics.start_time).total_seconds()
            logger.info(f"  Total time: {duration:.1f} seconds")

        if self.statistics.errors:
            logger.warning("Errors encountered during storage:")
            for error in self.statistics.errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error['type']}: {error.get('message', error.get('error'))}")

        logger.info("=" * 60)