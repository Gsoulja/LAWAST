"""
Vector Search component for Triple RAG
Uses Neo4j's native vector search capabilities with existing indexes
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer

from ..data_access.neo4j_connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Result from vector similarity search"""
    node_id: str
    uri: str
    node_type: str
    score: float
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VectorSearch:
    """
    Vector similarity search using Neo4j vector indexes.

    Leverages existing vector indexes:
    - law_embedding_index
    - article_embedding_index
    - paragraph_embedding_index
    - subpoint_embedding_index
    """

    def __init__(self,
                 connection: Optional[Neo4jConnectionManager] = None,
                 model_name: str = "intfloat/multilingual-e5-large",
                 device: Optional[str] = "cpu"):
        """
        Initialize vector search component.

        Args:
            connection: Neo4j connection manager
            model_name: Embedding model name (must match indexed embeddings)
            device: Device for model (default: 'cpu' to avoid memory issues)
        """
        self.connection = connection or Neo4jConnectionManager()
        self.model_name = model_name

        # Initialize embedding model
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        # Verify dimension matches database
        if self.embedding_dim != 1024:
            logger.warning(
                f"Model dimension {self.embedding_dim} may not match "
                f"database embeddings (expected 1024)"
            )

        logger.info(f"Vector search initialized with {self.embedding_dim}-dim embeddings")

    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for search query.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        # E5 models require "query: " prefix for queries
        prefixed_query = f"query: {query}"
        embedding = self.model.encode(
            prefixed_query,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embedding.tolist()

    def search_single_index(self,
                           query_embedding: List[float],
                           index_name: str,
                           top_k: int = 10,
                           min_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        Search a single vector index.

        Args:
            query_embedding: Query vector
            index_name: Name of the vector index
            top_k: Number of results to return
            min_score: Minimum similarity score threshold

        Returns:
            List of matching nodes with scores
        """
        cypher_query = """
        CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector)
        YIELD node, score
        WHERE score >= $min_score
        WITH node, score, labels(node)[0] as node_type
        RETURN
            elementId(node) as node_id,
            node.uri as uri,
            node_type,
            score,
            CASE node_type
                WHEN 'Law' THEN COALESCE(node.title_de, node.title_fr, node.title_it, 'SR ' + node.sr_number)
                WHEN 'Article' THEN CASE
                    WHEN node.number IS NOT NULL AND node.content_preview IS NOT NULL
                    THEN 'Art. ' + node.number + ': ' + substring(node.content_preview, 0, 80)
                    WHEN node.number IS NOT NULL
                    THEN 'Art. ' + node.number
                    WHEN node.content_preview IS NOT NULL
                    THEN substring(node.content_preview, 0, 100)
                    ELSE 'Article'
                END
                WHEN 'Paragraph' THEN CASE
                    WHEN node.number IS NOT NULL AND node.text IS NOT NULL
                    THEN 'Para ' + node.number + ': ' + substring(node.text, 0, 80)
                    WHEN node.text IS NOT NULL
                    THEN substring(node.text, 0, 100)
                    ELSE 'Paragraph'
                END
                WHEN 'Subpoint' THEN COALESCE(substring(node.text, 0, 100), 'Subpoint')
                ELSE node.uri
            END as title,
            CASE node_type
                WHEN 'Law' THEN COALESCE(node.title_de, node.title_fr, node.title_it)
                WHEN 'Article' THEN node.content_full
                WHEN 'Paragraph' THEN node.text
                WHEN 'Subpoint' THEN node.text
                ELSE null
            END as content,
            node.sr_number as sr_number,
            node.number as article_number,
            node.ast_path as ast_path
        ORDER BY score DESC
        """

        params = {
            "index_name": index_name,
            "top_k": top_k,
            "query_vector": query_embedding,
            "min_score": min_score
        }

        try:
            results = self.connection.execute_query(cypher_query, params)
            return results
        except Exception as e:
            logger.error(f"Error searching index {index_name}: {e}")
            return []

    def search(self,
               query: str,
               node_types: Optional[List[str]] = None,
               top_k: int = 10,
               min_score: float = 0.5) -> List[VectorSearchResult]:
        """
        Perform vector similarity search across specified node types.

        Args:
            query: Search query text
            node_types: List of node types to search (default: all)
            top_k: Number of results per index
            min_score: Minimum similarity score

        Returns:
            List of search results sorted by score
        """
        # Default to all available indexes
        if node_types is None:
            node_types = ["Law", "Article", "Paragraph", "Subpoint"]

        # Map node types to index names
        index_mapping = {
            "Law": "law_embedding_index",
            "Article": "article_embedding_index",
            "Paragraph": "paragraph_embedding_index",
            "Subpoint": "subpoint_embedding_index"
        }

        # Generate query embedding once
        query_embedding = self.generate_query_embedding(query)

        # Search each requested index
        all_results = []
        for node_type in node_types:
            if node_type not in index_mapping:
                logger.warning(f"Unknown node type: {node_type}")
                continue

            index_name = index_mapping[node_type]
            logger.debug(f"Searching {index_name} for query: {query[:50]}...")

            raw_results = self.search_single_index(
                query_embedding,
                index_name,
                top_k,
                min_score
            )

            # Convert to VectorSearchResult objects
            for result in raw_results:
                metadata = {
                    k: v for k, v in result.items()
                    if k not in ["node_id", "uri", "node_type", "score", "title", "content"]
                    and v is not None
                }

                all_results.append(VectorSearchResult(
                    node_id=result["node_id"],
                    uri=result["uri"],
                    node_type=result["node_type"],
                    score=result["score"],
                    title=result.get("title"),
                    content=result.get("content"),
                    metadata=metadata
                ))

        # Sort by score descending and limit total results
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:top_k]

    def search_with_context(self,
                           query: str,
                           node_types: Optional[List[str]] = None,
                           top_k: int = 10,
                           min_score: float = 0.5,
                           expand_context: bool = True) -> List[VectorSearchResult]:
        """
        Search with optional context expansion.

        Args:
            query: Search query text
            node_types: Node types to search
            top_k: Number of results
            min_score: Minimum similarity score
            expand_context: Whether to fetch parent/child nodes

        Returns:
            Search results with expanded context
        """
        # Get initial results
        results = self.search(query, node_types, top_k, min_score)

        if not expand_context or not results:
            return results

        # Expand context for each result
        for result in results:
            self._expand_result_context(result)

        return results

    def _expand_result_context(self, result: VectorSearchResult):
        """
        Expand context for a single result by fetching related nodes.

        Args:
            result: Search result to expand
        """
        # Query to get parent and child nodes
        cypher_query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        OPTIONAL MATCH (parent)-[:HAS_ARTICLE|HAS_PARAGRAPH|HAS_SUBPOINT]->(n)
        OPTIONAL MATCH (n)-[:HAS_ARTICLE|HAS_PARAGRAPH|HAS_SUBPOINT]->(child)
        RETURN
            parent.uri as parent_uri,
            parent.title as parent_title,
            collect(DISTINCT child.uri) as child_uris
        """

        params = {"node_id": result.node_id}

        try:
            context_results = self.connection.execute_query(cypher_query, params)
            if context_results:
                context = context_results[0]
                result.metadata.update({
                    "parent_uri": context.get("parent_uri"),
                    "parent_title": context.get("parent_title"),
                    "child_uris": context.get("child_uris", [])
                })
        except Exception as e:
            logger.debug(f"Could not expand context for {result.uri}: {e}")

    def get_index_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about vector indexes.

        Returns:
            Dictionary with index statistics
        """
        stats = {}

        # Query to check index status
        cypher_query = """
        SHOW INDEXES
        WHERE type = 'VECTOR'
        """

        try:
            indexes = self.connection.execute_query(cypher_query)
            for idx in indexes:
                name = idx.get("name", "unknown")
                stats[name] = {
                    "state": idx.get("state", "UNKNOWN"),
                    "entity_type": idx.get("entityType", "NODE"),
                    "label": idx.get("labelsOrTypes", [""])[0] if idx.get("labelsOrTypes") else "",
                    "property": idx.get("properties", [""])[0] if idx.get("properties") else ""
                }

            # Count embeddings per type
            for label in ["Law", "Article", "Paragraph", "Subpoint"]:
                count_query = f"""
                MATCH (n:{label})
                WHERE n.embedding IS NOT NULL
                RETURN count(n) as count
                """
                result = self.connection.execute_query(count_query)
                if result:
                    stats[f"{label.lower()}_count"] = result[0]["count"]

        except Exception as e:
            logger.error(f"Error getting index statistics: {e}")

        return stats