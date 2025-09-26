"""
AST Search component for Triple RAG
Uses hierarchical path patterns for structural document search
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..data_access.neo4j_connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class ASTLevel(Enum):
    """AST hierarchy levels"""
    CORPUS = 0
    DOMAIN = 1
    BOOK = 2
    CHAPTER = 3
    SECTION = 4
    LAW = 5
    ARTICLE = 6
    PARAGRAPH = 7
    SUBPOINT = 8


@dataclass
class ASTSearchResult:
    """Result from AST structural search"""
    node_id: str
    uri: str
    node_type: str
    ast_path: str
    level: int
    score: float  # Based on path match relevance
    title: Optional[str] = None
    content: Optional[str] = None
    parent_path: Optional[str] = None
    child_paths: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.child_paths is None:
            self.child_paths = []
        if self.metadata is None:
            self.metadata = {}


class ASTSearch:
    """
    AST (Abstract Syntax Tree) path-based search.

    Searches legal documents using their hierarchical structure:
    /domain_X/section_X/law_X/art_X/para_X/subpoint_X
    """

    def __init__(self, connection: Optional[Neo4jConnectionManager] = None):
        """
        Initialize AST search component.

        Args:
            connection: Neo4j connection manager
        """
        self.connection = connection or Neo4jConnectionManager()
        logger.info("AST search initialized")

    def parse_query_for_structure(self, query: str) -> Dict[str, Any]:
        """
        Parse query for structural hints.

        Args:
            query: Search query text

        Returns:
            Dictionary with detected structural elements
        """
        patterns = {
            "sr_number": r"\b(\d{3}(?:\.\d+)*)\b",  # e.g., 101.1, 232.112
            "article": r"\b(?:art(?:icle)?\.?\s*|artikel\s*)(\d+[a-z]?)\b",
            "paragraph": r"\b(?:para(?:graph)?\.?\s*|abs(?:atz)?\.?\s*)(\d+)\b",
            "section": r"\b(?:section|titel|kapitel)\s*(\d+)\b",
            "domain": r"\b(?:domain|bereich)\s*(\d+)\b"
        }

        extracted = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                extracted[key] = match.group(1)

        # Also check for legal terms that suggest hierarchy
        if "law" in query.lower() or "gesetz" in query.lower():
            extracted["search_level"] = "LAW"
        elif "article" in query.lower() or "artikel" in query.lower():
            extracted["search_level"] = "ARTICLE"
        elif "paragraph" in query.lower() or "absatz" in query.lower():
            extracted["search_level"] = "PARAGRAPH"

        return extracted

    def search_by_path_pattern(self,
                               path_pattern: str,
                               limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search nodes by AST path pattern.

        Args:
            path_pattern: Path pattern (supports wildcards)
            limit: Maximum results

        Returns:
            List of matching nodes
        """
        # Convert wildcards to Cypher pattern
        # e.g., "/domain_1/*/law_101*" -> WHERE n.ast_path STARTS WITH '/domain_1/' AND n.ast_path CONTAINS '/law_101'

        cypher_conditions = []

        if "*" in path_pattern:
            parts = path_pattern.split("*")
            if parts[0]:
                cypher_conditions.append(f"n.ast_path STARTS WITH '{parts[0]}'")
            for part in parts[1:]:
                if part:
                    cypher_conditions.append(f"n.ast_path CONTAINS '{part}'")
        else:
            cypher_conditions.append(f"n.ast_path = '{path_pattern}'")

        where_clause = " AND ".join(cypher_conditions) if cypher_conditions else "TRUE"

        cypher_query = f"""
        MATCH (n)
        WHERE n.ast_path IS NOT NULL
        AND ({where_clause})
        WITH n, labels(n)[0] as node_type
        RETURN
            elementId(n) as node_id,
            n.uri as uri,
            node_type,
            n.ast_path as ast_path,
            n.ast_level as level,
            CASE node_type
                WHEN 'Law' THEN COALESCE(n.title_de, n.title_fr, n.title_it, 'SR ' + n.sr_number)
                WHEN 'Article' THEN 'Art. ' + n.number
                WHEN 'Paragraph' THEN 'Para ' + n.number
                ELSE n.uri
            END as title,
            CASE node_type
                WHEN 'Article' THEN n.content_full
                WHEN 'Paragraph' THEN n.text
                ELSE null
            END as content,
            n.sr_number as sr_number
        ORDER BY n.ast_level, n.ast_path
        LIMIT $limit
        """

        params = {"limit": limit}

        try:
            results = self.connection.execute_query(cypher_query, params)
            return results
        except Exception as e:
            logger.error(f"Error searching by path pattern {path_pattern}: {e}")
            return []

    def search_by_level(self,
                       level: int,
                       parent_path: Optional[str] = None,
                       limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search nodes at a specific AST level.

        Args:
            level: AST level (0-8)
            parent_path: Optional parent path to filter by
            limit: Maximum results

        Returns:
            List of nodes at the specified level
        """
        cypher_query = """
        MATCH (n)
        WHERE n.ast_level = $level
        """

        if parent_path:
            cypher_query += """
            AND n.ast_path STARTS WITH $parent_path
            """

        cypher_query += """
        RETURN
            elementId(n) as node_id,
            n.uri as uri,
            labels(n)[0] as node_type,
            n.ast_path as ast_path,
            n.ast_level as level,
            n.title as title,
            n.sr_number as sr_number
        ORDER BY n.ast_path
        LIMIT $limit
        """

        params = {
            "level": level,
            "limit": limit
        }
        if parent_path:
            params["parent_path"] = parent_path

        try:
            results = self.connection.execute_query(cypher_query, params)
            return results
        except Exception as e:
            logger.error(f"Error searching level {level}: {e}")
            return []

    def find_siblings(self, node_uri: str) -> List[Dict[str, Any]]:
        """
        Find sibling nodes (same parent, same level).

        Args:
            node_uri: URI of the node

        Returns:
            List of sibling nodes
        """
        cypher_query = """
        MATCH (n {uri: $uri})
        WHERE n.ast_path IS NOT NULL
        WITH n, n.ast_level as level,
             substring(n.ast_path, 0, size(n.ast_path) - size(split(n.ast_path, '/')[-1]) - 1) as parent_path
        MATCH (sibling)
        WHERE sibling.ast_level = level
        AND sibling.ast_path STARTS WITH parent_path
        AND sibling.uri <> n.uri
        RETURN
            elementId(sibling) as node_id,
            sibling.uri as uri,
            labels(sibling)[0] as node_type,
            sibling.ast_path as ast_path,
            sibling.title as title
        ORDER BY sibling.ast_path
        LIMIT 20
        """

        params = {"uri": node_uri}

        try:
            results = self.connection.execute_query(cypher_query, params)
            return results
        except Exception as e:
            logger.error(f"Error finding siblings for {node_uri}: {e}")
            return []

    def find_ancestors(self, node_uri: str) -> List[Dict[str, Any]]:
        """
        Find all ancestor nodes in the AST hierarchy.

        Args:
            node_uri: URI of the node

        Returns:
            List of ancestor nodes ordered from immediate parent to root
        """
        cypher_query = """
        MATCH (n {uri: $uri})
        WHERE n.ast_path IS NOT NULL
        WITH n.ast_path as path
        UNWIND range(0, n.ast_level - 1) as ancestor_level
        MATCH (ancestor)
        WHERE ancestor.ast_level = ancestor_level
        AND path STARTS WITH ancestor.ast_path
        RETURN
            elementId(ancestor) as node_id,
            ancestor.uri as uri,
            labels(ancestor)[0] as node_type,
            ancestor.ast_path as ast_path,
            ancestor.ast_level as level,
            ancestor.title as title
        ORDER BY ancestor.ast_level DESC
        """

        params = {"uri": node_uri}

        try:
            results = self.connection.execute_query(cypher_query, params)
            return results
        except Exception as e:
            logger.error(f"Error finding ancestors for {node_uri}: {e}")
            return []

    def find_descendants(self,
                        node_uri: str,
                        max_depth: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Find descendant nodes in the AST hierarchy.

        Args:
            node_uri: URI of the node
            max_depth: Maximum depth to traverse (None for all)

        Returns:
            List of descendant nodes
        """
        base_query = """
        MATCH (n {uri: $uri})
        WHERE n.ast_path IS NOT NULL
        WITH n.ast_path as parent_path, n.ast_level as parent_level
        MATCH (descendant)
        WHERE descendant.ast_path STARTS WITH parent_path
        AND descendant.ast_level > parent_level
        """

        if max_depth is not None:
            base_query += """
            AND descendant.ast_level <= parent_level + $max_depth
            """

        base_query += """
        RETURN
            elementId(descendant) as node_id,
            descendant.uri as uri,
            labels(descendant)[0] as node_type,
            descendant.ast_path as ast_path,
            descendant.ast_level as level,
            descendant.title as title
        ORDER BY descendant.ast_level, descendant.ast_path
        LIMIT 100
        """

        params = {"uri": node_uri}
        if max_depth is not None:
            params["max_depth"] = max_depth

        try:
            results = self.connection.execute_query(base_query, params)
            return results
        except Exception as e:
            logger.error(f"Error finding descendants for {node_uri}: {e}")
            return []

    def search(self,
               query: str,
               max_results: int = 20) -> List[ASTSearchResult]:
        """
        Perform AST-based structural search.

        Args:
            query: Search query text
            max_results: Maximum number of results

        Returns:
            List of AST search results
        """
        # Parse query for structural hints
        structure_hints = self.parse_query_for_structure(query)
        logger.debug(f"Extracted structure hints: {structure_hints}")

        results = []

        # Build path pattern from hints
        if structure_hints:
            path_patterns = self._build_path_patterns(structure_hints)

            for pattern in path_patterns:
                logger.debug(f"Searching with pattern: {pattern}")
                pattern_results = self.search_by_path_pattern(pattern, limit=max_results)

                for result in pattern_results:
                    # Calculate relevance score
                    score = self._calculate_ast_score(
                        result.get("ast_path", ""),
                        result.get("level", 0),
                        structure_hints
                    )

                    ast_result = ASTSearchResult(
                        node_id=result["node_id"],
                        uri=result["uri"],
                        node_type=result["node_type"],
                        ast_path=result.get("ast_path", ""),
                        level=result.get("level", 0),
                        score=score,
                        title=result.get("title"),
                        content=result.get("content"),
                        metadata={
                            "sr_number": result.get("sr_number"),
                            "matched_pattern": pattern
                        }
                    )

                    results.append(ast_result)

        # Also do a text search on nodes with AST paths
        text_results = self._text_search_with_ast(query, limit=10)
        for result in text_results:
            score = 0.5  # Lower score for text-only matches

            ast_result = ASTSearchResult(
                node_id=result["node_id"],
                uri=result["uri"],
                node_type=result["node_type"],
                ast_path=result.get("ast_path", ""),
                level=result.get("level", 0),
                score=score,
                title=result.get("title"),
                content=result.get("content")
            )

            # Avoid duplicates
            if not any(r.uri == ast_result.uri for r in results):
                results.append(ast_result)

        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:max_results]

    def _build_path_patterns(self, structure_hints: Dict[str, Any]) -> List[str]:
        """
        Build AST path patterns from structure hints.

        Args:
            structure_hints: Extracted structure hints

        Returns:
            List of path patterns to search
        """
        patterns = []

        # Build specific pattern from SR number
        if "sr_number" in structure_hints:
            sr = structure_hints["sr_number"]
            # Extract domain from first digit
            domain = sr.split('.')[0][0] if '.' in sr else sr[0]
            sr_clean = sr.replace('.', '_')

            # Pattern for the law itself
            patterns.append(f"/domain_{domain}/*/law_{sr_clean}*")

            # If article is specified, add more specific pattern
            if "article" in structure_hints:
                art = structure_hints["article"]
                patterns.append(f"/domain_{domain}/*/law_{sr_clean}/art_{art}*")

                # If paragraph is specified, be even more specific
                if "paragraph" in structure_hints:
                    para = structure_hints["paragraph"]
                    patterns.append(f"/domain_{domain}/*/law_{sr_clean}/art_{art}/para_{para}*")

        # Build pattern from individual components
        elif any(k in structure_hints for k in ["domain", "section", "article"]):
            pattern_parts = []

            if "domain" in structure_hints:
                pattern_parts.append(f"/domain_{structure_hints['domain']}")
            else:
                pattern_parts.append("/*")

            if "section" in structure_hints:
                pattern_parts.append(f"/section_{structure_hints['section']}")
            else:
                pattern_parts.append("/*")

            if "article" in structure_hints:
                pattern_parts.append(f"*/art_{structure_hints['article']}*")

            patterns.append("".join(pattern_parts))

        return patterns if patterns else ["*"]

    def _text_search_with_ast(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Text search on nodes that have AST paths.

        Args:
            query: Search text
            limit: Maximum results

        Returns:
            List of matching nodes
        """
        cypher_query = """
        MATCH (n)
        WHERE n.ast_path IS NOT NULL
        AND (
            toLower(COALESCE(n.title_de, n.title_fr, n.title_it, '')) CONTAINS toLower($query)
            OR toLower(COALESCE(n.content_full, n.content_preview, n.text, '')) CONTAINS toLower($query)
        )
        WITH n, labels(n)[0] as node_type
        RETURN
            elementId(n) as node_id,
            n.uri as uri,
            node_type,
            n.ast_path as ast_path,
            n.ast_level as level,
            CASE node_type
                WHEN 'Law' THEN COALESCE(n.title_de, n.title_fr, n.title_it, 'SR ' + n.sr_number)
                WHEN 'Article' THEN 'Art. ' + n.number
                WHEN 'Paragraph' THEN 'Para ' + n.number
                ELSE n.uri
            END as title,
            CASE node_type
                WHEN 'Article' THEN n.content_full
                WHEN 'Paragraph' THEN n.text
                ELSE null
            END as content
        ORDER BY n.ast_level
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
            logger.error(f"Error in text search with AST: {e}")
            return []

    def _calculate_ast_score(self,
                            ast_path: str,
                            level: int,
                            structure_hints: Dict[str, Any]) -> float:
        """
        Calculate relevance score for AST search result.

        Args:
            ast_path: AST path of the node
            level: AST level of the node
            structure_hints: Query structure hints

        Returns:
            Relevance score (0-1)
        """
        score = 0.5  # Base score

        # Boost if level matches expected level
        if "search_level" in structure_hints:
            expected_level = ASTLevel[structure_hints["search_level"]].value
            if level == expected_level:
                score += 0.3
            elif abs(level - expected_level) == 1:
                score += 0.1

        # Boost for specific matches
        if "sr_number" in structure_hints:
            sr_clean = structure_hints["sr_number"].replace('.', '_')
            if f"law_{sr_clean}" in ast_path:
                score += 0.2

        if "article" in structure_hints:
            if f"art_{structure_hints['article']}" in ast_path:
                score += 0.1

        # Prefer higher-level nodes (laws over subpoints)
        score += (8 - level) * 0.02

        return min(score, 1.0)  # Cap at 1.0

    def get_ast_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about AST structure.

        Returns:
            Dictionary with AST statistics
        """
        stats = {}

        # Count nodes at each level
        for level in range(9):
            query = """
            MATCH (n)
            WHERE n.ast_level = $level
            RETURN count(n) as count
            """
            try:
                result = self.connection.execute_query(query, {"level": level})
                if result:
                    level_name = ASTLevel(level).name.lower()
                    stats[f"{level_name}_count"] = result[0]["count"]
            except Exception as e:
                logger.error(f"Error counting level {level}: {e}")

        # Count nodes with AST paths
        query = """
        MATCH (n)
        WHERE n.ast_path IS NOT NULL
        RETURN count(n) as count
        """
        try:
            result = self.connection.execute_query(query)
            if result:
                stats["nodes_with_ast_path"] = result[0]["count"]
        except Exception as e:
            logger.error(f"Error counting AST paths: {e}")

        return stats