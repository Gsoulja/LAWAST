"""
Buffered relationship writer for Neo4j
Handles buffering, flushing, and retry logic for relationship creation
"""
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from src.data_access.graph_builder import GraphBuilder
from src.config.extractor_config import ExtractorConfig

logger = logging.getLogger(__name__)


class RelationshipBuffer:
    """
    Manages buffered writing of relationships to Neo4j with retry logic
    """

    def __init__(
        self,
        graph_builder: GraphBuilder,
        config: Optional[ExtractorConfig] = None
    ):
        """
        Initialize the relationship buffer

        Args:
            graph_builder: GraphBuilder instance for database operations
            config: Configuration for buffer behavior
        """
        self.builder = graph_builder
        self.config = config or ExtractorConfig()

        # Buffer for relationships
        self.buffer: List[Tuple[str, str, str, Optional[Dict]]] = []
        self.failed_relationships: List[Tuple[str, str, str, Optional[Dict], str]] = []

        # Statistics
        self.stats = defaultdict(int)
        self.checkpoint_counter = 0

    def add(
        self,
        from_uri: str,
        to_uri: str,
        rel_type: str,
        properties: Optional[Dict] = None
    ) -> None:
        """
        Add a relationship to the buffer

        Args:
            from_uri: Source node URI
            to_uri: Target node URI
            rel_type: Relationship type
            properties: Optional relationship properties
        """
        self.buffer.append((from_uri, to_uri, rel_type, properties))
        self.stats[f"buffered_{rel_type}"] += 1

        # Check if we should flush
        if len(self.buffer) >= self.config.buffer_size:
            self.flush()
        elif len(self.buffer) >= self.config.max_buffer_size:
            logger.warning(f"Buffer size exceeded max ({self.config.max_buffer_size}), forcing flush")
            self.flush(force=True)

    def flush(self, force: bool = False) -> int:
        """
        Flush buffered relationships to Neo4j

        Args:
            force: Force flush even if buffer is small

        Returns:
            Number of relationships created
        """
        if not self.buffer and not force:
            return 0

        if len(self.buffer) < self.config.buffer_size and not force:
            logger.debug(f"Buffer has {len(self.buffer)} items, waiting for {self.config.buffer_size}")
            return 0

        created = 0
        retries = 0

        while retries < self.config.max_retries:
            try:
                # Validate nodes if configured
                if self.config.validate_nodes:
                    valid_relationships = self._validate_relationships()
                else:
                    valid_relationships = self.buffer

                if not valid_relationships:
                    logger.warning("No valid relationships to flush")
                    self.buffer.clear()
                    return 0

                # Create relationships in batch
                created = self.builder.batch_create_relationships(
                    valid_relationships,
                    batch_size=self.config.batch_size
                )

                # Update statistics
                for _, _, rel_type, _ in valid_relationships:
                    self.stats[f"created_{rel_type}"] += 1

                self.stats["total_created"] += created
                self.stats["flushes"] += 1

                logger.info(f"Flushed {created} relationships to Neo4j")
                self.buffer.clear()

                # Check checkpoint
                self._check_checkpoint(created)

                return created

            except Exception as e:
                retries += 1
                logger.error(f"Failed to flush relationships (attempt {retries}/{self.config.max_retries}): {e}")

                if retries < self.config.max_retries:
                    time.sleep(self.config.retry_delay * retries)
                else:
                    # Save failed relationships
                    self._save_failed_relationships(str(e))
                    self.buffer.clear()
                    raise

        return created

    def _validate_relationships(self) -> List[Tuple[str, str, str, Optional[Dict]]]:
        """
        Validate that nodes exist for all relationships

        Returns:
            List of valid relationships
        """
        valid = []
        invalid_count = 0

        # Group by URIs for efficient validation
        all_uris = set()
        for from_uri, to_uri, _, _ in self.buffer:
            all_uris.add(from_uri)
            all_uris.add(to_uri)

        # Check which nodes exist
        existing_uris = self._check_nodes_exist(list(all_uris))

        # Filter relationships
        for from_uri, to_uri, rel_type, props in self.buffer:
            if from_uri in existing_uris and to_uri in existing_uris:
                valid.append((from_uri, to_uri, rel_type, props))
            else:
                invalid_count += 1
                if self.config.log_failed_relationships:
                    missing = []
                    if from_uri not in existing_uris:
                        missing.append(f"from: {from_uri}")
                    if to_uri not in existing_uris:
                        missing.append(f"to: {to_uri}")

                    reason = f"Missing nodes: {', '.join(missing)}"
                    self.failed_relationships.append((from_uri, to_uri, rel_type, props, reason))

                if not self.config.skip_missing_nodes:
                    # If not skipping, this is an error
                    logger.error(f"Missing nodes for relationship {from_uri} -> {to_uri}")

        if invalid_count > 0:
            logger.warning(f"Found {invalid_count} relationships with missing nodes")
            self.stats["invalid_relationships"] += invalid_count

        return valid

    def _check_nodes_exist(self, uris: List[str]) -> set:
        """
        Check which nodes exist in the database

        Args:
            uris: List of URIs to check

        Returns:
            Set of existing URIs
        """
        if not uris:
            return set()

        query = """
        UNWIND $uris AS uri
        MATCH (n {uri: uri})
        RETURN collect(DISTINCT n.uri) AS existing_uris
        """

        try:
            result = self.builder.connection.execute_read(query, {"uris": uris})
            if result and result[0]['existing_uris']:
                return set(result[0]['existing_uris'])
        except Exception as e:
            logger.error(f"Failed to validate nodes: {e}")

        return set()

    def _check_checkpoint(self, created: int):
        """
        Check if we should create a checkpoint

        Args:
            created: Number of relationships just created
        """
        self.checkpoint_counter += created

        if self.checkpoint_counter >= self.config.checkpoint_interval:
            self._create_checkpoint()
            self.checkpoint_counter = 0

    def _create_checkpoint(self):
        """Create a checkpoint for recovery"""
        checkpoint_data = {
            "timestamp": time.time(),
            "stats": dict(self.stats),
            "failed_count": len(self.failed_relationships)
        }
        logger.info(f"Checkpoint created: {checkpoint_data}")

    def _save_failed_relationships(self, error: str):
        """
        Save failed relationships for manual review

        Args:
            error: Error message that caused the failure
        """
        for rel in self.buffer:
            self.failed_relationships.append(rel + (error,))

        self.stats["failed_relationships"] += len(self.buffer)
        logger.error(f"Saved {len(self.buffer)} failed relationships for review")

    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        return {
            **dict(self.stats),
            "buffer_size": len(self.buffer),
            "failed_count": len(self.failed_relationships),
            "checkpoint_counter": self.checkpoint_counter
        }

    def get_failed_relationships(self) -> List[Tuple[str, str, str, Optional[Dict], str]]:
        """Get list of failed relationships with reasons"""
        return self.failed_relationships.copy()

    def clear(self):
        """Clear all buffers and reset statistics"""
        self.buffer.clear()
        self.failed_relationships.clear()
        self.stats.clear()
        self.checkpoint_counter = 0