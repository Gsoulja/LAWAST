"""
Graph Search component for Triple RAG
Uses Neo4j graph traversal without APOC procedures
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

from ..data_access.neo4j_connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class RelationshipType(Enum):
    """Supported relationship types for traversal"""
    REFERENCES = "REFERENCES"
    CITES = "CITES"
    AMENDS = "AMENDS"
    HAS_VERSION = "HAS_VERSION"
    HAS_ACT = "HAS_ACT"
    HAS_ARTICLE = "HAS_ARTICLE"
    HAS_PARAGRAPH = "HAS_PARAGRAPH"
    HAS_SUBPOINT = "HAS_SUBPOINT"
    REPLACES = "REPLACES"
    REPLACED_BY = "REPLACED_BY"


@dataclass
class GraphSearchResult:
    """Result from graph traversal search"""
    node_id: str
    uri: str
    node_type: str
    path_length: int
    relationship_types: List[str]
    score: float  # Based on path length and relationship relevance
    title: Optional[str] = None
    content: Optional[str] = None
    path_nodes: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.path_nodes is None:
            self.path_nodes = []
        if self.metadata is None:
            self.metadata = {}


class GraphSearch:
    """
    Graph relationship traversal search using pure Cypher.

    Finds related nodes through relationship patterns without APOC.
    """

    # Relationship weights for scoring (lower is better)
    RELATIONSHIP_WEIGHTS = {
        "REFERENCES": 1.0,
        "CITES": 1.0,
        "AMENDS": 1.2,
        "HAS_ARTICLE": 0.8,
        "HAS_PARAGRAPH": 0.9,
        "HAS_SUBPOINT": 0.95,
        "HAS_VERSION": 1.5,
        "HAS_ACT": 1.3,
        "REPLACES": 1.1,
        "REPLACED_BY": 1.1,
    }

    def __init__(self, connection: Optional[Neo4jConnectionManager] = None):
        """
        Initialize graph search component.

        Args:
            connection: Neo4j connection manager
        """
        self.connection = connection or Neo4jConnectionManager()
        logger.info("Graph search initialized (using pure Cypher)")

    def find_seed_nodes(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find seed nodes for graph traversal based on text search.

        Args:
            query: Search query text
            limit: Maximum number of seed nodes

        Returns:
            List of seed nodes with basic info
        """
        # Use text search on indexed properties
        cypher_query = """
        MATCH (n)
        WHERE (n:Law OR n:Article OR n:Paragraph)
        AND (
            toLower(COALESCE(n.title_de, n.title_fr, n.title_it, '')) CONTAINS toLower($query)
            OR toLower(COALESCE(n.content_full, n.content_preview, n.text, '')) CONTAINS toLower($query)
            OR n.sr_number CONTAINS $query
        )
        WITH n, labels(n)[0] as node_type
        RETURN
            elementId(n) as node_id,
            n.uri as uri,
            node_type,
            CASE node_type
                WHEN 'Law' THEN COALESCE(n.title_de, n.title_fr, n.title_it, 'SR ' + n.sr_number)
                WHEN 'Article' THEN CASE
                    WHEN n.number IS NOT NULL THEN 'Art. ' + n.number + COALESCE(': ' + substring(n.content_preview, 0, 60), '')
                    WHEN n.content_preview IS NOT NULL THEN substring(n.content_preview, 0, 100)
                    ELSE 'Article'
                END
                WHEN 'Paragraph' THEN CASE
                    WHEN n.number IS NOT NULL THEN 'Para ' + n.number + COALESCE(': ' + substring(n.text, 0, 60), '')
                    ELSE COALESCE(substring(n.text, 0, 100), 'Paragraph')
                END
                ELSE n.uri
            END as title,
            n.sr_number as sr_number,
            n.number as article_number
        LIMIT $limit
        """

        params = {
            "query": query,
            "limit": limit
        }

        try:
            results = self.connection.execute_query(cypher_query, params)
            return results
        except Exception as e:
            logger.error(f"Error finding seed nodes: {e}")
            return []

    def traverse_relationships(self,
                              start_node_id: str,
                              relationship_types: Optional[List[str]] = None,
                              max_depth: int = 3,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """
        Traverse relationships from a starting node.

        Args:
            start_node_id: Starting node element ID
            relationship_types: Relationship types to follow
            max_depth: Maximum traversal depth
            limit: Maximum number of results

        Returns:
            List of traversed paths with nodes and relationships
        """
        # Default relationship types for legal document traversal
        if relationship_types is None:
            relationship_types = ["REFERENCES", "CITES", "AMENDS", "HAS_ARTICLE"]

        # Build relationship pattern
        rel_pattern = "|".join(relationship_types)

        # Cypher query for path traversal
        cypher_query = f"""
        MATCH path = (start)-[:{rel_pattern}*1..{max_depth}]-(end)
        WHERE elementId(start) = $start_id
        AND (end:Law OR end:Article OR end:Paragraph)
        AND start <> end
        WITH path, end, length(path) as path_length
        ORDER BY path_length
        LIMIT $limit
        WITH path, end, labels(end)[0] as end_type, path_length
        RETURN
            elementId(end) as node_id,
            end.uri as uri,
            end_type as node_type,
            CASE end_type
                WHEN 'Law' THEN COALESCE(end.title_de, end.title_fr, end.title_it, 'SR ' + end.sr_number)
                WHEN 'Article' THEN 'Art. ' + end.number
                WHEN 'Paragraph' THEN 'Para ' + end.number
                ELSE end.uri
            END as title,
            CASE end_type
                WHEN 'Article' THEN end.content_full
                WHEN 'Paragraph' THEN end.text
                ELSE null
            END as content,
            path_length,
            [rel in relationships(path) | type(rel)] as rel_types,
            [node in nodes(path) | elementId(node)] as path_node_ids,
            [node in nodes(path) | node.uri] as path_node_uris
        """

        params = {
            "start_id": start_node_id,
            "limit": limit
        }

        try:
            results = self.connection.execute_query(cypher_query, params)
            return results
        except Exception as e:
            logger.error(f"Error traversing from {start_node_id}: {e}")
            return []

    def search(self,
               query: str,
               relationship_types: Optional[List[str]] = None,
               max_depth: int = 3,
               max_results: int = 20) -> List[GraphSearchResult]:
        """
        Perform graph-based search starting from query-relevant nodes.

        Args:
            query: Search query text
            relationship_types: Types of relationships to traverse
            max_depth: Maximum traversal depth
            max_results: Maximum total results

        Returns:
            List of graph search results
        """
        # Find seed nodes
        seed_nodes = self.find_seed_nodes(query, limit=5)
        if not seed_nodes:
            logger.info(f"No seed nodes found for query: {query}")
            return []

        logger.debug(f"Found {len(seed_nodes)} seed nodes for graph traversal")

        # Traverse from each seed node
        all_results = []
        seen_uris = set()

        for seed in seed_nodes:
            seed_id = seed["node_id"]
            logger.debug(f"Traversing from {seed['uri']}")

            traversal_results = self.traverse_relationships(
                seed_id,
                relationship_types,
                max_depth,
                limit=max_results
            )

            for result in traversal_results:
                # Skip duplicates
                uri = result["uri"]
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)

                # Calculate score based on path length and relationship types
                score = self._calculate_path_score(
                    result["path_length"],
                    result["rel_types"]
                )

                # Create result object
                graph_result = GraphSearchResult(
                    node_id=result["node_id"],
                    uri=uri,
                    node_type=result["node_type"],
                    path_length=result["path_length"],
                    relationship_types=result["rel_types"],
                    score=score,
                    title=result.get("title"),
                    content=result.get("content"),
                    path_nodes=result.get("path_node_uris", []),
                    metadata={
                        "seed_uri": seed["uri"],
                        "path_node_ids": result.get("path_node_ids", [])
                    }
                )

                all_results.append(graph_result)

        # Sort by score (higher is better) and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:max_results]

    def find_related_by_references(self,
                                   node_uri: str,
                                   depth: int = 2) -> List[GraphSearchResult]:
        """
        Find nodes related through REFERENCES relationships.

        Args:
            node_uri: URI of the starting node
            depth: Maximum depth to traverse

        Returns:
            List of related nodes
        """
        cypher_query = f"""
        MATCH (start {{uri: $uri}})
        MATCH path = (start)-[:REFERENCES*1..{depth}]-(related)
        WHERE start <> related
        RETURN DISTINCT
            elementId(related) as node_id,
            related.uri as uri,
            labels(related)[0] as node_type,
            related.title as title,
            length(path) as path_length,
            [rel in relationships(path) | type(rel)] as rel_types
        ORDER BY path_length
        LIMIT 20
        """

        params = {"uri": node_uri}

        try:
            results = self.connection.execute_query(cypher_query, params)

            return [
                GraphSearchResult(
                    node_id=r["node_id"],
                    uri=r["uri"],
                    node_type=r["node_type"],
                    path_length=r["path_length"],
                    relationship_types=r["rel_types"],
                    score=1.0 / (1 + r["path_length"]),  # Simple inverse distance score
                    title=r.get("title")
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Error finding references for {node_uri}: {e}")
            return []

    def find_hierarchical_context(self, node_uri: str) -> Dict[str, Any]:
        """
        Find hierarchical context (parents and children) of a node.

        Args:
            node_uri: URI of the node

        Returns:
            Dictionary with parent and children information
        """
        cypher_query = """
        MATCH (n {uri: $uri})
        OPTIONAL MATCH (parent)-[:HAS_ARTICLE|HAS_PARAGRAPH|HAS_SUBPOINT]->(n)
        OPTIONAL MATCH (n)-[:HAS_ARTICLE|HAS_PARAGRAPH|HAS_SUBPOINT]->(child)
        OPTIONAL MATCH (law:Law)-[:HAS_ACT]->(:Act)-[:HAS_ARTICLE]->(n)
        RETURN
            n.uri as uri,
            labels(n)[0] as node_type,
            n.title as title,
            parent.uri as parent_uri,
            parent.title as parent_title,
            labels(parent)[0] as parent_type,
            collect(DISTINCT {
                uri: child.uri,
                title: child.title,
                type: labels(child)[0]
            }) as children,
            law.uri as law_uri,
            law.title as law_title
        """

        params = {"uri": node_uri}

        try:
            results = self.connection.execute_query(cypher_query, params)
            if results:
                return results[0]
            return {}
        except Exception as e:
            logger.error(f"Error finding context for {node_uri}: {e}")
            return {}

    def _calculate_path_score(self,
                             path_length: int,
                             relationship_types: List[str]) -> float:
        """
        Calculate score based on path characteristics.

        Args:
            path_length: Length of the path
            relationship_types: Types of relationships in the path

        Returns:
            Score (higher is better)
        """
        # Base score inversely proportional to path length
        base_score = 1.0 / (1 + path_length)

        # Adjust based on relationship types
        rel_weight = 1.0
        for rel_type in relationship_types:
            rel_weight *= self.RELATIONSHIP_WEIGHTS.get(rel_type, 1.5)

        # Normalize relationship weight
        rel_weight = 1.0 / (rel_weight ** (1.0 / len(relationship_types)))

        return base_score * rel_weight

    def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the graph structure.

        Returns:
            Dictionary with graph statistics
        """
        stats = {}

        queries = [
            ("total_nodes", "MATCH (n) RETURN count(n) as count"),
            ("total_relationships", "MATCH ()-[r]->() RETURN count(r) as count"),
            ("law_nodes", "MATCH (n:Law) RETURN count(n) as count"),
            ("article_nodes", "MATCH (n:Article) RETURN count(n) as count"),
            ("reference_relationships", "MATCH ()-[r:REFERENCES]->() RETURN count(r) as count"),
            ("citation_relationships", "MATCH ()-[r:CITES]->() RETURN count(r) as count"),
        ]

        for stat_name, query in queries:
            try:
                result = self.connection.execute_query(query)
                if result:
                    stats[stat_name] = result[0]["count"]
            except Exception as e:
                logger.error(f"Error getting {stat_name}: {e}")
                stats[stat_name] = 0

        return stats