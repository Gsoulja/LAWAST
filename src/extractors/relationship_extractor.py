"""
Relationship extractor for Fedlex legal graph
Extracts and creates relationships between legal entities from JSON metadata
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from contextlib import contextmanager

from src.data_access.graph_builder import GraphBuilder
from src.extractors.uri_resolver import URIResolver
from src.extractors.relationship_buffer import RelationshipBuffer
from src.extractors.version_chain_builder import VersionChainBuilder
from src.config.extractor_config import ExtractorConfig

logger = logging.getLogger(__name__)


class RelationshipExtractor:
    """
    Extracts relationships from Fedlex JSON files and creates them in Neo4j
    """

    def __init__(
        self,
        graph_builder: Optional[GraphBuilder] = None,
        uri_resolver: Optional[URIResolver] = None,
        config: Optional[ExtractorConfig] = None
    ):
        """
        Initialize the relationship extractor

        Args:
            graph_builder: GraphBuilder instance for creating relationships
            uri_resolver: URIResolver for URI normalization and extraction
            config: Configuration for extraction behavior
        """
        self.builder = graph_builder or GraphBuilder()
        self.resolver = uri_resolver or URIResolver()
        self.config = config or ExtractorConfig.from_env()

        # Use the new RelationshipBuffer for buffering
        self.buffer = RelationshipBuffer(self.builder, self.config)

        # Version chain builder for SUPERSEDES relationships
        self.version_chain_builder = VersionChainBuilder(self.builder)

        # Statistics
        self.stats = defaultdict(int)
        self.transaction_active = False

    def extract_from_file(self, file_path: str) -> List[Tuple[str, str, str, Optional[Dict]]]:
        """
        Extract relationships from a single JSON file

        Args:
            file_path: Path to JSON file

        Returns:
            List of (from_uri, to_uri, rel_type, properties) tuples
        """
        relationships = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict) or 'data' not in data:
                logger.warning(f"Invalid JSON structure in {file_path}")
                return relationships

            json_data = data['data']
            doc_type = json_data.get('type', [])

            # Determine document type and extract accordingly
            if "ConsolidationAbstract" in doc_type:
                relationships.extend(self.extract_from_consolidation_abstract(json_data, data))
            elif "Consolidation" in doc_type and self.resolver.is_version_uri(json_data.get('uri', '')):
                relationships.extend(self.extract_from_version(json_data, data))
            elif "Act" in doc_type:
                relationships.extend(self.extract_from_act(json_data, data))

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

        return relationships

    def extract_from_consolidation_abstract(
        self,
        json_data: Dict[str, Any],
        full_data: Dict[str, Any]
    ) -> List[Tuple[str, str, str, Optional[Dict]]]:
        """
        Extract relationships from ConsolidationAbstract (main law)

        Extracts:
        - EXPRESSED_IN relationships to language expressions
        """
        relationships = []
        law_uri = self.resolver.normalize_uri(json_data.get('uri', ''))

        if not law_uri:
            return relationships

        # Extract language expressions from isRealizedBy
        references = json_data.get('references', {})
        is_realized_by = references.get('isRealizedBy', [])

        for lang_uri in is_realized_by:
            lang_uri = self.resolver.normalize_uri(lang_uri)
            lang_code = self.resolver.extract_language_code(lang_uri)

            if lang_code:
                # Law -> EXPRESSED_IN -> Language Expression
                relationships.append((law_uri, lang_uri, "EXPRESSED_IN", None))
                self.stats['EXPRESSED_IN'] += 1

        # Process included section for additional language data
        included = full_data.get('included', [])
        for item in included:
            if item.get('type') == 'Expression':
                expr_uri = self.resolver.normalize_uri(item.get('uri', ''))
                if expr_uri and expr_uri.startswith(law_uri):
                    # Additional language expressions
                    if (law_uri, expr_uri, "EXPRESSED_IN", None) not in relationships:
                        relationships.append((law_uri, expr_uri, "EXPRESSED_IN", None))
                        self.stats['EXPRESSED_IN'] += 1

        return relationships

    def extract_from_version(
        self,
        json_data: Dict[str, Any],
        full_data: Dict[str, Any]
    ) -> List[Tuple[str, str, str, Optional[Dict]]]:
        """
        Extract relationships from Consolidation version

        Extracts:
        - HAS_VERSION relationship to parent law
        - EXPRESSED_IN relationships to language variants
        - MANIFESTED_AS relationships to formats (HTML, PDF, etc.)
        """
        relationships = []
        version_uri = self.resolver.normalize_uri(json_data.get('uri', ''))

        if not version_uri:
            return relationships

        # 1. Link to parent law (HAS_VERSION)
        parent_law_uri = self.resolver.get_parent_law_uri(version_uri)
        if parent_law_uri:
            # Law -> HAS_VERSION -> Version
            relationships.append((parent_law_uri, version_uri, "HAS_VERSION", None))
            self.stats['HAS_VERSION'] += 1

        # Alternative: Check isMemberOf attribute
        attributes = json_data.get('attributes', {})
        is_member_of = attributes.get('isMemberOf', {}).get('rdfs:Resource')
        if is_member_of:
            parent_uri = self.resolver.normalize_uri(is_member_of)
            if parent_uri and parent_uri != parent_law_uri:
                relationships.append((parent_uri, version_uri, "HAS_VERSION", None))
                self.stats['HAS_VERSION'] += 1

        # 2. Language expressions (EXPRESSED_IN)
        references = json_data.get('references', {})
        is_realized_by = references.get('isRealizedBy', [])

        for lang_expr_uri in is_realized_by:
            lang_expr_uri = self.resolver.normalize_uri(lang_expr_uri)
            # Version -> EXPRESSED_IN -> Language Expression
            relationships.append((version_uri, lang_expr_uri, "EXPRESSED_IN", None))
            self.stats['EXPRESSED_IN'] += 1

        # 3. Format manifestations from included section
        included = full_data.get('included', [])
        for item in included:
            if item.get('type') == 'Expression':
                expr_uri = self.resolver.normalize_uri(item.get('uri', ''))
                expr_refs = item.get('references', {})

                # Extract manifestations (formats)
                is_embodied_by = expr_refs.get('isEmbodiedBy', [])
                for manifest_uri in is_embodied_by:
                    manifest_uri = self.resolver.normalize_uri(manifest_uri)
                    format_type = self.resolver.extract_format(manifest_uri)

                    if expr_uri and manifest_uri:
                        # Language Expression -> MANIFESTED_AS -> Format
                        properties = {"format": format_type} if format_type else None
                        relationships.append((expr_uri, manifest_uri, "MANIFESTED_AS", properties))
                        self.stats['MANIFESTED_AS'] += 1

        return relationships

    def extract_from_act(
        self,
        json_data: Dict[str, Any],
        full_data: Dict[str, Any]
    ) -> List[Tuple[str, str, str, Optional[Dict]]]:
        """
        Extract relationships from Act (official compilation)

        Extracts:
        - AMENDS relationships from impacted resources
        - Language and format relationships
        """
        relationships = []
        act_uri = self.resolver.normalize_uri(json_data.get('uri', ''))

        if not act_uri:
            return relationships

        # 1. Extract AMENDS relationships from facets
        facets = full_data.get('facets', {})
        impacts = facets.get('impacts', [])

        for impacted_uri in impacts:
            if isinstance(impacted_uri, str):
                impacted_uri = self.resolver.normalize_uri(impacted_uri)
                # Act -> AMENDS -> Impacted Law
                relationships.append((act_uri, impacted_uri, "AMENDS", None))
                self.stats['AMENDS'] += 1
            elif isinstance(impacted_uri, dict):
                # Sometimes impacts are objects with URI
                uri = impacted_uri.get('uri') or impacted_uri.get('rdfs:Resource')
                if uri:
                    uri = self.resolver.normalize_uri(uri)
                    relationships.append((act_uri, uri, "AMENDS", None))
                    self.stats['AMENDS'] += 1

        # 2. Language expressions (similar to consolidation)
        references = json_data.get('references', {})
        is_realized_by = references.get('isRealizedBy', [])

        for lang_uri in is_realized_by:
            lang_uri = self.resolver.normalize_uri(lang_uri)
            relationships.append((act_uri, lang_uri, "EXPRESSED_IN", None))
            self.stats['EXPRESSED_IN'] += 1

        return relationships

    def build_version_chains(self, law_uris: Optional[List[str]] = None) -> int:
        """
        Build SUPERSEDES relationships between consecutive versions
        Delegates to VersionChainBuilder to avoid duplication

        Args:
            law_uris: Optional list of law URIs to process (None = all)

        Returns:
            Number of SUPERSEDES relationships created
        """
        # Delegate to VersionChainBuilder to avoid duplication
        if law_uris:
            total = 0
            for law_uri in law_uris:
                result = self.version_chain_builder.build_chain_for_law(law_uri)
                if result['success']:
                    total += result['relationships_created']
                    self.stats['SUPERSEDES'] += result['relationships_created']
            return total
        else:
            # Build all chains
            stats = self.version_chain_builder.build_all_chains()
            self.stats['SUPERSEDES'] += stats.get('supersedes_created', 0)
            return stats.get('supersedes_created', 0)

    def add_relationship(
        self,
        from_uri: str,
        to_uri: str,
        rel_type: str,
        properties: Optional[Dict] = None
    ):
        """
        Add relationship to buffer and flush if needed

        Args:
            from_uri: Source node URI
            to_uri: Target node URI
            rel_type: Relationship type
            properties: Optional relationship properties
        """
        self.buffer.add(from_uri, to_uri, rel_type, properties)
        self.stats[rel_type] += 1

    def flush_relationships(self) -> int:
        """
        Flush buffered relationships to Neo4j

        Returns:
            Number of relationships created
        """
        return self.buffer.flush(force=True)

    @contextmanager
    def _transaction_context(self):
        """
        Context manager for transaction handling
        """
        if not self.config.enable_transactions:
            yield
            return

        try:
            self.transaction_active = True
            logger.info("Starting transaction for relationship extraction")
            yield
            logger.info("Transaction completed successfully")
        except Exception as e:
            logger.error(f"Transaction failed, attempting rollback: {e}")
            # Clear any unflushed relationships
            self.buffer.clear()
            raise
        finally:
            self.transaction_active = False

    def process_directory(
        self,
        directory: str,
        pattern: str = "*.json",
        recursive: bool = True
    ) -> Dict[str, int]:
        """
        Process all JSON files in a directory for relationships
        Now with transaction management and better error handling

        Args:
            directory: Directory path
            pattern: File pattern to match
            recursive: Process subdirectories

        Returns:
            Statistics dictionary
        """
        path = Path(directory)

        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))

        logger.info(f"Processing {len(files)} files for relationships")

        # Use transaction context for atomic operations
        with self._transaction_context():
            try:
                # Process files
                for i, file_path in enumerate(files):
                    try:
                        relationships = self.extract_from_file(str(file_path))

                        # Add to buffer
                        for rel in relationships:
                            self.add_relationship(*rel)

                        # Log progress
                        if (i + 1) % 100 == 0:
                            logger.info(f"Processed {i + 1}/{len(files)} files")

                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        self.stats['errors'] += 1
                        if not self.config.skip_missing_nodes:
                            raise

                # Final flush
                self.flush_relationships()

                # Build version chains
                logger.info("Building version chains...")
                self.build_version_chains()

                # Get final statistics
                buffer_stats = self.buffer.get_statistics()
                self.stats.update(buffer_stats)

                # Log failed relationships if any
                failed = self.buffer.get_failed_relationships()
                if failed:
                    logger.warning(f"Found {len(failed)} failed relationships")
                    if self.config.log_failed_relationships:
                        for from_uri, to_uri, rel_type, _, reason in failed[:10]:
                            logger.warning(f"  {from_uri} -> {to_uri} ({rel_type}): {reason}")

            except Exception as e:
                logger.error(f"Fatal error during processing: {e}")
                raise

        return dict(self.stats)

    def get_statistics(self) -> Dict[str, int]:
        """Get extraction statistics"""
        return dict(self.stats)

    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats.clear()