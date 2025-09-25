"""
Graph builder with CRUD operations for Neo4j
"""
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from .neo4j_connection import Neo4jConnectionManager, get_connection
from .graph_schema import (
    NodeLabels, RelationshipTypes,
    LawNode, VersionNode, ActNode, ArticleNode, LanguageNode, ManifestationNode,
    DomainNode, BookNode, ChapterNode, SectionNode, ParagraphNode, SubpointNode
)

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Provides CRUD operations and graph building utilities for Neo4j
    """

    def __init__(self, connection: Optional[Neo4jConnectionManager] = None):
        """
        Initialize the graph builder

        Args:
            connection: Neo4j connection manager (uses singleton if not provided)
        """
        self.connection = connection or get_connection()

    # ============= Node Creation =============

    def create_law_node(self, law: LawNode) -> Dict[str, Any]:
        """
        Create or update a Law node

        Args:
            law: LawNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (l:{NodeLabels.LAW.value} {{uri: $uri}})
        SET l += $properties
        RETURN l
        """
        params = {"uri": law.uri, "properties": law.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Law node: {law.uri}")
            return result[0]['l']
        return {}

    def create_version_node(self, version: VersionNode) -> Dict[str, Any]:
        """
        Create or update a Version node

        Args:
            version: VersionNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (v:{NodeLabels.VERSION.value} {{uri: $uri}})
        SET v += $properties
        RETURN v
        """
        params = {"uri": version.uri, "properties": version.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Version node: {version.uri}")
            return result[0]['v']
        return {}

    def create_act_node(self, act: 'ActNode') -> Dict[str, Any]:
        """
        Create or update an Act node

        Args:
            act: ActNode instance

        Returns:
            Created/updated node properties
        """
        from .graph_schema import NodeLabels

        query = f"""
        MERGE (a:{NodeLabels.ACT.value} {{uri: $uri}})
        SET a += $properties
        RETURN a
        """
        params = {"uri": act.uri, "properties": act.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Act node: {act.uri}")
            return result[0]['a']
        return {}

    def create_article_node(self, article: ArticleNode) -> Dict[str, Any]:
        """
        Create or update an Article node

        Args:
            article: ArticleNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (a:{NodeLabels.ARTICLE.value} {{uri: $uri}})
        SET a += $properties
        RETURN a
        """
        params = {"uri": article.uri, "properties": article.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Article node: {article.uri}")
            return result[0]['a']
        return {}

    def create_manifestation_node(self, manifestation: ManifestationNode) -> Dict[str, Any]:
        """
        Create or update a Manifestation node

        Args:
            manifestation: ManifestationNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (m:{NodeLabels.MANIFESTATION.value} {{uri: $uri}})
        SET m += $properties
        RETURN m
        """
        params = {"uri": manifestation.uri, "properties": manifestation.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Manifestation node: {manifestation.uri}")
            return result[0]['m']
        return {}

    def create_domain_node(self, domain: DomainNode) -> Dict[str, Any]:
        """
        Create or update a Domain node

        Args:
            domain: DomainNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (d:{NodeLabels.DOMAIN.value} {{uri: $uri}})
        SET d += $properties
        RETURN d
        """
        params = {"uri": domain.uri, "properties": domain.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Domain node: {domain.uri}")
            return result[0]['d']
        return {}

    def create_book_node(self, book: BookNode) -> Dict[str, Any]:
        """
        Create or update a Book node

        Args:
            book: BookNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (b:{NodeLabels.BOOK.value} {{uri: $uri}})
        SET b += $properties
        RETURN b
        """
        params = {"uri": book.uri, "properties": book.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Book node: {book.uri}")
            return result[0]['b']
        return {}

    def create_chapter_node(self, chapter: ChapterNode) -> Dict[str, Any]:
        """
        Create or update a Chapter node

        Args:
            chapter: ChapterNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (c:{NodeLabels.CHAPTER.value} {{uri: $uri}})
        SET c += $properties
        RETURN c
        """
        params = {"uri": chapter.uri, "properties": chapter.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Chapter node: {chapter.uri}")
            return result[0]['c']
        return {}

    def create_section_node(self, section: SectionNode) -> Dict[str, Any]:
        """
        Create or update a Section node

        Args:
            section: SectionNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (s:{NodeLabels.SECTION.value} {{uri: $uri}})
        SET s += $properties
        RETURN s
        """
        params = {"uri": section.uri, "properties": section.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.info(f"Created/updated Section node: {section.uri}")
            return result[0]['s']
        return {}

    def create_paragraph_node(self, paragraph: 'ParagraphNode') -> Dict[str, Any]:
        """
        Create or update a Paragraph node

        Args:
            paragraph: ParagraphNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (p:{NodeLabels.PARAGRAPH.value} {{uri: $uri}})
        SET p += $properties
        RETURN p
        """
        params = {"uri": paragraph.uri, "properties": paragraph.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.debug(f"Created/updated Paragraph node: {paragraph.uri}")
            return result[0]['p']
        return {}

    def create_subpoint_node(self, subpoint: 'SubpointNode') -> Dict[str, Any]:
        """
        Create or update a Subpoint node

        Args:
            subpoint: SubpointNode instance

        Returns:
            Created/updated node properties
        """
        query = f"""
        MERGE (s:{NodeLabels.SUBPOINT.value} {{uri: $uri}})
        SET s += $properties
        RETURN s
        """
        params = {"uri": subpoint.uri, "properties": subpoint.to_cypher_properties()}
        result = self.connection.execute_write(query, params)

        if result:
            logger.debug(f"Created/updated Subpoint node: {subpoint.uri}")
            return result[0]['s']
        return {}

    # ============= Batch Node Creation =============

    def batch_create_nodes(
        self,
        nodes: List[Union[LawNode, VersionNode, ArticleNode, ManifestationNode]],
        batch_size: int = 1000
    ) -> int:
        """
        Create multiple nodes in batches

        Args:
            nodes: List of node instances
            batch_size: Number of nodes per batch

        Returns:
            Number of nodes created/updated
        """
        total_created = 0

        # Group nodes by type
        nodes_by_type = {}
        for node in nodes:
            node_type = type(node).__name__
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node)

        # Process each type
        for node_type, typed_nodes in nodes_by_type.items():
            if node_type == "LawNode":
                label = NodeLabels.LAW.value
            elif node_type == "VersionNode":
                label = NodeLabels.VERSION.value
            elif node_type == "ArticleNode":
                label = NodeLabels.ARTICLE.value
            elif node_type == "ManifestationNode":
                label = NodeLabels.MANIFESTATION.value
            else:
                logger.warning(f"Unknown node type: {node_type}")
                continue

            # Process in batches
            for i in range(0, len(typed_nodes), batch_size):
                batch = typed_nodes[i:i + batch_size]
                batch_data = [node.to_cypher_properties() for node in batch]

                query = f"""
                UNWIND $batch AS node_props
                MERGE (n:{label} {{uri: node_props.uri}})
                SET n += node_props
                RETURN count(n) AS created
                """

                result = self.connection.execute_write(query, {"batch": batch_data})
                if result:
                    count = result[0]['created']
                    total_created += count
                    logger.info(f"Created/updated {count} {label} nodes")

        return total_created

    # ============= Relationship Creation =============

    def create_relationship(
        self,
        from_uri: str,
        to_uri: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a relationship between two nodes

        Args:
            from_uri: URI of the source node
            to_uri: URI of the target node
            rel_type: Relationship type
            properties: Optional relationship properties

        Returns:
            True if created, False otherwise
        """
        # Validate relationship type
        try:
            rel_enum = RelationshipTypes[rel_type]
            rel_type = rel_enum.value
        except KeyError:
            logger.error(f"Invalid relationship type: {rel_type}")
            return False

        query = f"""
        MATCH (a {{uri: $from_uri}})
        MATCH (b {{uri: $to_uri}})
        MERGE (a)-[r:{rel_type}]->(b)
        """

        if properties:
            query += " SET r += $properties"
            params = {"from_uri": from_uri, "to_uri": to_uri, "properties": properties}
        else:
            params = {"from_uri": from_uri, "to_uri": to_uri}

        try:
            self.connection.execute_write(query, params)
            logger.info(f"Created relationship: {from_uri} -{rel_type}-> {to_uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return False

    def create_has_version(self, law_uri: str, version_uri: str) -> bool:
        """Create HAS_VERSION relationship between Law and Version"""
        return self.create_relationship(law_uri, version_uri, "HAS_VERSION")

    def create_supersedes(self, new_version_uri: str, old_version_uri: str) -> bool:
        """Create SUPERSEDES relationship between versions"""
        return self.create_relationship(new_version_uri, old_version_uri, "SUPERSEDES")

    def create_contains(self, law_uri: str, article_uri: str) -> bool:
        """Create CONTAINS relationship between Law and Article"""
        return self.create_relationship(law_uri, article_uri, "CONTAINS")

    def create_references(
        self,
        from_uri: str,
        to_uri: str,
        context: Optional[str] = None
    ) -> bool:
        """Create REFERENCES relationship with optional context"""
        props = {"context": context} if context else None
        return self.create_relationship(from_uri, to_uri, "REFERENCES", props)

    def create_amends(self, amending_law_uri: str, amended_law_uri: str) -> bool:
        """Create AMENDS relationship between laws"""
        return self.create_relationship(amending_law_uri, amended_law_uri, "AMENDS")

    def create_has_paragraph(self, article_uri: str, paragraph_uri: str, position: Optional[int] = None) -> bool:
        """Create HAS_PARAGRAPH relationship between Article and Paragraph"""
        props = {"position": position} if position is not None else None
        return self.create_relationship(article_uri, paragraph_uri, "HAS_PARAGRAPH", props)

    def create_has_subpoint(self, paragraph_uri: str, subpoint_uri: str, position: Optional[int] = None) -> bool:
        """Create HAS_SUBPOINT relationship between Paragraph and Subpoint"""
        props = {"position": position} if position is not None else None
        return self.create_relationship(paragraph_uri, subpoint_uri, "HAS_SUBPOINT", props)

    def create_has_child(self, parent_uri: str, child_uri: str, position: Optional[int] = None) -> bool:
        """Create HAS_CHILD relationship for AST hierarchy"""
        props = {"position": position} if position is not None else None
        return self.create_relationship(parent_uri, child_uri, "HAS_CHILD", props)

    # ============= Batch Relationship Creation =============

    def batch_create_relationships(
        self,
        relationships: List[tuple[str, str, str, Optional[Dict]]],
        batch_size: int = 5000
    ) -> int:
        """
        Create multiple relationships in batches

        Args:
            relationships: List of (from_uri, to_uri, rel_type, properties) tuples
            batch_size: Number of relationships per batch

        Returns:
            Number of relationships created
        """
        total_created = 0

        # Group by relationship type for efficiency
        rels_by_type = {}
        for from_uri, to_uri, rel_type, props in relationships:
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            rels_by_type[rel_type].append({
                "from": from_uri,
                "to": to_uri,
                "props": props or {}
            })

        # Process each type
        for rel_type, rels in rels_by_type.items():
            # Validate relationship type
            try:
                rel_enum = RelationshipTypes[rel_type]
                rel_type = rel_enum.value
            except KeyError:
                logger.error(f"Invalid relationship type: {rel_type}")
                continue

            # Process in batches
            for i in range(0, len(rels), batch_size):
                batch = rels[i:i + batch_size]

                query = f"""
                UNWIND $batch AS rel
                MATCH (a {{uri: rel.from}})
                MATCH (b {{uri: rel.to}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += rel.props
                RETURN count(r) AS created
                """

                result = self.connection.execute_write(query, {"batch": batch})
                if result:
                    count = result[0]['created']
                    total_created += count
                    logger.info(f"Created {count} {rel_type} relationships")

        return total_created

    # ============= Version Chain Building =============

    def build_version_chains(self, law_uri: str) -> int:
        """
        Build SUPERSEDES relationships between consecutive versions of a law

        Args:
            law_uri: URI of the law

        Returns:
            Number of SUPERSEDES relationships created
        """
        query = f"""
        MATCH (l:{NodeLabels.LAW.value} {{uri: $law_uri}})
        MATCH (l)-[:{RelationshipTypes.HAS_VERSION.value}]->(v:{NodeLabels.VERSION.value})
        WITH v ORDER BY v.date_applicable
        WITH collect(v) AS versions
        UNWIND range(0, size(versions)-2) AS i
        WITH versions[i] AS v1, versions[i+1] AS v2
        MERGE (v2)-[r:{RelationshipTypes.SUPERSEDES.value}]->(v1)
        RETURN count(r) AS created
        """

        result = self.connection.execute_write(query, {"law_uri": law_uri})
        if result:
            count = result[0]['created']
            logger.info(f"Created {count} SUPERSEDES relationships for law {law_uri}")
            return count
        return 0

    # ============= Query Operations =============

    def get_law_by_uri(self, uri: str) -> Optional[Dict[str, Any]]:
        """Get a Law node by URI"""
        query = f"""
        MATCH (l:{NodeLabels.LAW.value} {{uri: $uri}})
        RETURN l
        """
        result = self.connection.execute_query(query, {"uri": uri})
        return result[0]['l'] if result else None

    def get_law_by_sr_number(self, sr_number: str) -> Optional[Dict[str, Any]]:
        """Get a Law node by SR number"""
        query = f"""
        MATCH (l:{NodeLabels.LAW.value} {{sr_number: $sr_number}})
        RETURN l
        """
        result = self.connection.execute_query(query, {"sr_number": sr_number})
        return result[0]['l'] if result else None

    def get_law_versions(self, law_uri: str) -> List[Dict[str, Any]]:
        """Get all versions of a law"""
        query = f"""
        MATCH (l:{NodeLabels.LAW.value} {{uri: $law_uri}})
        MATCH (l)-[:{RelationshipTypes.HAS_VERSION.value}]->(v:{NodeLabels.VERSION.value})
        RETURN v ORDER BY v.date_applicable DESC
        """
        result = self.connection.execute_query(query, {"law_uri": law_uri})
        return [r['v'] for r in result]

    def get_law_articles(self, law_uri: str) -> List[Dict[str, Any]]:
        """Get all articles of a law"""
        query = f"""
        MATCH (l:{NodeLabels.LAW.value} {{uri: $law_uri}})
        MATCH (l)-[:{RelationshipTypes.CONTAINS.value}]->(a:{NodeLabels.ARTICLE.value})
        RETURN a ORDER BY a.number
        """
        result = self.connection.execute_query(query, {"law_uri": law_uri})
        return [r['a'] for r in result]

    def get_referenced_laws(self, law_uri: str) -> List[Dict[str, Any]]:
        """Get all laws referenced by a given law"""
        query = f"""
        MATCH (l:{NodeLabels.LAW.value} {{uri: $law_uri}})
        MATCH (l)-[:{RelationshipTypes.REFERENCES.value}]->(ref:{NodeLabels.LAW.value})
        RETURN DISTINCT ref
        """
        result = self.connection.execute_query(query, {"law_uri": law_uri})
        return [r['ref'] for r in result]

    def get_amending_laws(self, law_uri: str) -> List[Dict[str, Any]]:
        """Get all laws that amend a given law"""
        query = f"""
        MATCH (l:{NodeLabels.LAW.value} {{uri: $law_uri}})
        MATCH (amender:{NodeLabels.LAW.value})-[:{RelationshipTypes.AMENDS.value}]->(l)
        RETURN amender
        """
        result = self.connection.execute_query(query, {"law_uri": law_uri})
        return [r['amender'] for r in result]

    # ============= Statistics =============

    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the graph

        Returns:
            Dictionary with counts of nodes and relationships
        """
        query = """
        MATCH (n)
        WITH labels(n)[0] AS label, count(n) AS count
        RETURN label, count
        UNION ALL
        MATCH ()-[r]->()
        RETURN type(r) AS label, count(r) AS count
        """

        result = self.connection.execute_query(query)
        stats = {}
        for record in result:
            stats[record['label']] = record['count']

        return stats