"""
Version chain builder for temporal relationships
Creates SUPERSEDES relationships between consecutive law versions
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.data_access.graph_builder import GraphBuilder
from src.data_access.neo4j_connection import get_connection

logger = logging.getLogger(__name__)


class VersionChainBuilder:
    """
    Builds temporal chains between law versions using SUPERSEDES relationships
    """

    def __init__(self, graph_builder: Optional[GraphBuilder] = None):
        """
        Initialize the version chain builder

        Args:
            graph_builder: GraphBuilder instance
        """
        self.builder = graph_builder or GraphBuilder()
        self.connection = get_connection()

    def build_all_chains(self) -> Dict[str, int]:
        """
        Build version chains for all laws in the database

        Returns:
            Statistics dictionary
        """
        stats = {
            "laws_processed": 0,
            "chains_created": 0,
            "supersedes_created": 0,
            "errors": 0
        }

        # Get all laws
        query = """
        MATCH (l:Law)
        RETURN l.uri AS uri, l.sr_number AS sr_number
        ORDER BY l.sr_number
        """

        try:
            laws = self.connection.execute_read(query)

            for law in laws:
                law_uri = law['uri']
                result = self.build_chain_for_law(law_uri)

                if result['success']:
                    stats['laws_processed'] += 1
                    stats['supersedes_created'] += result['relationships_created']
                    if result['relationships_created'] > 0:
                        stats['chains_created'] += 1
                else:
                    stats['errors'] += 1

            logger.info(f"Built version chains: {stats}")

        except Exception as e:
            logger.error(f"Error building all chains: {e}")
            stats['errors'] += 1

        return stats

    def build_chain_for_law(self, law_uri: str) -> Dict[str, Any]:
        """
        Build version chain for a specific law

        Args:
            law_uri: URI of the law

        Returns:
            Result dictionary with success status and count
        """
        result = {
            "success": False,
            "law_uri": law_uri,
            "relationships_created": 0,
            "versions_found": 0
        }

        try:
            # Get all versions for this law, sorted by date
            versions_query = """
            MATCH (l:Law {uri: $law_uri})
            MATCH (l)-[:HAS_VERSION]->(v:Version)
            RETURN v.uri AS uri,
                   v.date_applicable AS date_start,
                   v.date_end_applicable AS date_end
            ORDER BY v.date_applicable
            """

            versions = self.connection.execute_read(
                versions_query,
                {"law_uri": law_uri}
            )

            result['versions_found'] = len(versions)

            if len(versions) < 2:
                # Need at least 2 versions to create a chain
                result['success'] = True
                return result

            # Create SUPERSEDES relationships between consecutive versions
            relationships_created = 0

            for i in range(len(versions) - 1):
                older_version = versions[i]
                newer_version = versions[i + 1]

                # Create SUPERSEDES relationship
                create_query = """
                MATCH (newer:Version {uri: $newer_uri})
                MATCH (older:Version {uri: $older_uri})
                MERGE (newer)-[s:SUPERSEDES]->(older)
                SET s.created_at = datetime()
                RETURN s
                """

                rel_result = self.connection.execute_write(
                    create_query,
                    {
                        "newer_uri": newer_version['uri'],
                        "older_uri": older_version['uri']
                    }
                )

                if rel_result:
                    relationships_created += 1

            result['relationships_created'] = relationships_created
            result['success'] = True

            logger.debug(f"Created {relationships_created} SUPERSEDES relationships for {law_uri}")

        except Exception as e:
            logger.error(f"Error building chain for {law_uri}: {e}")
            result['error'] = str(e)

        return result

    def validate_chains(self) -> Dict[str, Any]:
        """
        Validate version chains for consistency

        Returns:
            Validation results
        """
        validation = {
            "valid": True,
            "issues": [],
            "statistics": {}
        }

        # Check for broken chains (versions without proper succession)
        broken_chain_query = """
        MATCH (v:Version)
        WHERE v.date_end_applicable IS NOT NULL
          AND NOT EXISTS((v)<-[:SUPERSEDES]-())
          AND EXISTS((v)<-[:HAS_VERSION]-())
        RETURN v.uri AS uri, v.date_end_applicable AS end_date
        LIMIT 100
        """

        broken = self.connection.execute_read(broken_chain_query)
        if broken:
            validation['valid'] = False
            validation['issues'].append({
                "type": "broken_chain",
                "count": len(broken),
                "examples": broken[:5]
            })

        # Check for circular references
        circular_query = """
        MATCH path = (v:Version)-[:SUPERSEDES*]->(v)
        RETURN v.uri AS uri
        LIMIT 10
        """

        circular = self.connection.execute_read(circular_query)
        if circular:
            validation['valid'] = False
            validation['issues'].append({
                "type": "circular_reference",
                "count": len(circular),
                "examples": circular
            })

        # Check for date inconsistencies
        date_inconsistency_query = """
        MATCH (newer:Version)-[:SUPERSEDES]->(older:Version)
        WHERE newer.date_applicable <= older.date_applicable
        RETURN newer.uri AS newer_uri,
               older.uri AS older_uri,
               newer.date_applicable AS newer_date,
               older.date_applicable AS older_date
        LIMIT 100
        """

        inconsistent = self.connection.execute_read(date_inconsistency_query)
        if inconsistent:
            validation['valid'] = False
            validation['issues'].append({
                "type": "date_inconsistency",
                "count": len(inconsistent),
                "examples": inconsistent[:5]
            })

        # Get statistics
        stats_query = """
        MATCH (l:Law)
        WITH count(l) AS total_laws
        MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
        WITH total_laws, count(DISTINCT l) AS laws_with_versions
        MATCH ()-[s:SUPERSEDES]->()
        RETURN total_laws,
               laws_with_versions,
               count(s) AS supersedes_count
        """

        stats = self.connection.execute_read(stats_query)
        if stats:
            validation['statistics'] = stats[0]

        return validation

    def repair_chains(self, dry_run: bool = True) -> Dict[str, int]:
        """
        Attempt to repair broken version chains

        Args:
            dry_run: If True, only report what would be fixed

        Returns:
            Repair statistics
        """
        stats = {
            "chains_repaired": 0,
            "relationships_added": 0,
            "errors": 0
        }

        # Find laws with broken chains
        broken_laws_query = """
        MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
        WITH l, collect(v) AS versions
        WHERE size(versions) > 1
        WITH l, versions
        UNWIND versions AS v
        WITH l, v
        WHERE NOT EXISTS((v)-[:SUPERSEDES]->())
          AND NOT EXISTS((v)<-[:SUPERSEDES]-())
        RETURN DISTINCT l.uri AS law_uri
        """

        broken_laws = self.connection.execute_read(broken_laws_query)

        for law in broken_laws:
            law_uri = law['law_uri']

            if dry_run:
                logger.info(f"Would repair chain for: {law_uri}")
                stats['chains_repaired'] += 1
            else:
                result = self.build_chain_for_law(law_uri)
                if result['success'] and result['relationships_created'] > 0:
                    stats['chains_repaired'] += 1
                    stats['relationships_added'] += result['relationships_created']
                elif not result['success']:
                    stats['errors'] += 1

        logger.info(f"Chain repair {'simulation' if dry_run else 'complete'}: {stats}")

        return stats

    def get_version_timeline(self, law_uri: str) -> List[Dict[str, Any]]:
        """
        Get the complete version timeline for a law

        Args:
            law_uri: URI of the law

        Returns:
            List of versions in chronological order
        """
        query = """
        MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
        OPTIONAL MATCH (v)-[:SUPERSEDES]->(older:Version)
        OPTIONAL MATCH (newer:Version)-[:SUPERSEDES]->(v)
        RETURN v.uri AS uri,
               v.date_applicable AS date_start,
               v.date_end_applicable AS date_end,
               older.uri AS supersedes,
               newer.uri AS superseded_by
        ORDER BY v.date_applicable
        """

        timeline = self.connection.execute_read(query, {"law_uri": law_uri})

        return timeline