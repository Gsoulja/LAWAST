"""
Version chain builder for temporal relationships
Creates SUPERSEDES relationships between consecutive law versions
"""
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

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
            laws = self.connection.execute_query(query)

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

            versions = self.connection.execute_query(
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

        broken = self.connection.execute_query(broken_chain_query)
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

        circular = self.connection.execute_query(circular_query)
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

        inconsistent = self.connection.execute_query(date_inconsistency_query)
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

        stats = self.connection.execute_query(stats_query)
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

        broken_laws = self.connection.execute_query(broken_laws_query)

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

        timeline = self.connection.execute_query(query, {"law_uri": law_uri})

        return timeline

    # ============= Temporal Query Methods =============

    def get_version_at_date(self, law_uri: str, query_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Get the version of a law that was valid at a specific date
        
        Args:
            law_uri: URI of the law
            query_date: Date to query for (datetime object)
            
        Returns:
            Version information valid at the query date, or None if no version found
        """
        try:
            # Convert datetime to ISO string for Cypher query
            query_date_str = query_date.isoformat()
            
            query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            WHERE v.date_applicable <= datetime($query_date)
              AND (v.date_end_applicable IS NULL 
                   OR v.date_end_applicable > datetime($query_date))
            RETURN v.uri AS uri,
                   v.date_applicable AS date_applicable,
                   v.date_end_applicable AS date_end_applicable,
                   v.version_number AS version_number,
                   v.parent_law_uri AS parent_law_uri
            ORDER BY v.date_applicable DESC
            LIMIT 1
            """
            
            result = self.connection.execute_query(
                query, 
                {"law_uri": law_uri, "query_date": query_date_str}
            )
            
            if result:
                version = result[0]
                logger.debug(f"Found version {version['uri']} for {law_uri} at {query_date_str}")
                return version
            else:
                logger.info(f"No version found for {law_uri} at {query_date_str}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting version for {law_uri} at {query_date}: {e}")
            return None

    def get_changes_between_dates(self, start_date: datetime, end_date: datetime, 
                                law_uris: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Find all law changes that occurred between two dates
        
        Args:
            start_date: Start of date range (exclusive)
            end_date: End of date range (inclusive)
            law_uris: Optional list of specific laws to check (None = all laws)
            
        Returns:
            List of changes with version and change type information
        """
        try:
            start_date_str = start_date.isoformat()
            end_date_str = end_date.isoformat()
            
            # Base query for version changes
            law_filter = ""
            if law_uris:
                law_filter = "AND l.uri IN $law_uris"
            
            query = f"""
            // New versions that became active in date range
            MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
            WHERE v.date_applicable > datetime($start_date)
              AND v.date_applicable <= datetime($end_date)
              {law_filter}
            RETURN l.uri AS law_uri,
                   l.sr_number AS sr_number,
                   v.uri AS version_uri,
                   v.date_applicable AS change_date,
                   'VERSION_ACTIVATED' AS change_type,
                   v.version_number AS version_number
            
            UNION
            
            // Versions that ended in date range
            MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
            WHERE v.date_end_applicable IS NOT NULL
              AND v.date_end_applicable > datetime($start_date)
              AND v.date_end_applicable <= datetime($end_date)
              {law_filter}
            RETURN l.uri AS law_uri,
                   l.sr_number AS sr_number,
                   v.uri AS version_uri,
                   v.date_end_applicable AS change_date,
                   'VERSION_ENDED' AS change_type,
                   v.version_number AS version_number
            
            ORDER BY change_date, law_uri
            """
            
            params = {"start_date": start_date_str, "end_date": end_date_str}
            if law_uris:
                params["law_uris"] = law_uris
            
            changes = self.connection.execute_query(query, params)
            
            logger.info(f"Found {len(changes)} changes between {start_date_str} and {end_date_str}")
            return changes
            
        except Exception as e:
            logger.error(f"Error getting changes between {start_date} and {end_date}: {e}")
            return []

    def get_legal_state_at_date(self, query_date: datetime, 
                              law_uris: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Reconstruct the complete legal system state at a specific date
        
        Args:
            query_date: Date to reconstruct state for
            law_uris: Optional list of specific laws (None = all laws)
            
        Returns:
            List of active versions at the specified date
        """
        try:
            query_date_str = query_date.isoformat()
            
            law_filter = ""
            if law_uris:
                law_filter = "AND l.uri IN $law_uris"
            
            query = f"""
            MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
            WHERE v.date_applicable <= datetime($query_date)
              AND (v.date_end_applicable IS NULL 
                   OR v.date_end_applicable > datetime($query_date))
              {law_filter}
            RETURN l.uri AS law_uri,
                   l.sr_number AS sr_number,
                   l.title_de AS law_title,
                   v.uri AS version_uri,
                   v.date_applicable AS version_start,
                   v.date_end_applicable AS version_end,
                   v.version_number AS version_number
            ORDER BY l.sr_number
            """
            
            params = {"query_date": query_date_str}
            if law_uris:
                params["law_uris"] = law_uris
            
            state = self.connection.execute_query(query, params)
            
            logger.info(f"Reconstructed legal state for {query_date_str}: {len(state)} active versions")
            return state
            
        except Exception as e:
            logger.error(f"Error reconstructing legal state at {query_date}: {e}")
            return []

    # ============= Date Validation Utilities =============

    def validate_date_range(self, start_date: datetime, end_date: datetime) -> bool:
        """
        Validate that a date range is logical and within reasonable bounds
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check basic ordering
            if start_date >= end_date:
                logger.warning(f"Invalid date range: start_date {start_date} >= end_date {end_date}")
                return False
            
            # Check reasonable bounds (Swiss legal system context)
            min_date = datetime(1848, 1, 1)  # Swiss federal constitution
            max_date = datetime.now() + timedelta(days=365 * 10)  # 10 years future
            
            if start_date < min_date:
                logger.warning(f"Start date {start_date} before Swiss federal system (1848)")
                return False
                
            if end_date > max_date:
                logger.warning(f"End date {end_date} too far in future")
                return False
            
            # Check maximum range (prevent overly broad queries)
            max_range = timedelta(days=365 * 50)  # 50 years maximum
            if end_date - start_date > max_range:
                logger.warning(f"Date range too large: {end_date - start_date} > {max_range}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating date range {start_date} to {end_date}: {e}")
            return False

    def parse_query_date(self, date_input: Union[str, datetime]) -> datetime:
        """
        Parse various date input formats into datetime object
        
        Args:
            date_input: Date as string (ISO format, YYYY-MM-DD) or datetime object
            
        Returns:
            Parsed datetime object
            
        Raises:
            ValueError: If date cannot be parsed
        """
        try:
            if isinstance(date_input, datetime):
                return date_input
            
            if isinstance(date_input, str):
                # Try ISO format first (YYYY-MM-DDTHH:MM:SS)
                try:
                    return datetime.fromisoformat(date_input.replace('Z', '+00:00'))
                except ValueError:
                    pass
                
                # Try date only format (YYYY-MM-DD)
                try:
                    return datetime.strptime(date_input, '%Y-%m-%d')
                except ValueError:
                    pass
                
                # Try Swiss date format (DD.MM.YYYY)
                try:
                    return datetime.strptime(date_input, '%d.%m.%Y')
                except ValueError:
                    pass
            
            raise ValueError(f"Unable to parse date: {date_input}")
            
        except Exception as e:
            logger.error(f"Error parsing date {date_input}: {e}")
            raise ValueError(f"Invalid date format: {date_input}")

    def get_date_boundaries(self, law_uri: str) -> Dict[str, Optional[datetime]]:
        """
        Get the earliest and latest version dates for a law
        
        Args:
            law_uri: URI of the law
            
        Returns:
            Dictionary with 'earliest' and 'latest' datetime values
        """
        try:
            query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            RETURN min(v.date_applicable) AS earliest,
                   max(CASE 
                       WHEN v.date_end_applicable IS NOT NULL 
                       THEN v.date_end_applicable 
                       ELSE v.date_applicable 
                   END) AS latest
            """
            
            result = self.connection.execute_query(query, {"law_uri": law_uri})
            
            if result and result[0]['earliest']:
                boundaries = {
                    'earliest': datetime.fromisoformat(result[0]['earliest'].replace('Z', '+00:00')),
                    'latest': datetime.fromisoformat(result[0]['latest'].replace('Z', '+00:00')) if result[0]['latest'] else None
                }
                logger.debug(f"Date boundaries for {law_uri}: {boundaries}")
                return boundaries
            else:
                logger.info(f"No version dates found for {law_uri}")
                return {'earliest': None, 'latest': None}
                
        except Exception as e:
            logger.error(f"Error getting date boundaries for {law_uri}: {e}")
            return {'earliest': None, 'latest': None}

    # ============= Temporal Validation Methods =============

    def validate_temporal_integrity(self, law_uri: str) -> Dict[str, Any]:
        """
        Comprehensive validation of temporal integrity for a law
        
        Args:
            law_uri: URI of the law to validate
            
        Returns:
            Dictionary with validation results and detected issues
        """
        validation = {
            'law_uri': law_uri,
            'valid': True,
            'issues': [],
            'statistics': {}
        }
        
        try:
            # Run all validation checks
            validation['gap_check'] = self.detect_timeline_gaps(law_uri)
            validation['overlap_check'] = self.check_date_overlaps(law_uri)
            validation['chain_check'] = self.verify_version_chain_integrity(law_uri)
            validation['current_check'] = self.verify_current_version_marking(law_uri)
            
            # Aggregate issues
            all_checks = [
                validation['gap_check'],
                validation['overlap_check'], 
                validation['chain_check'],
                validation['current_check']
            ]
            
            for check in all_checks:
                if not check['valid']:
                    validation['valid'] = False
                    validation['issues'].extend(check.get('issues', []))
            
            # Get statistics
            validation['statistics'] = self.get_temporal_statistics(law_uri)
            
            logger.info(f"Temporal validation for {law_uri}: {'VALID' if validation['valid'] else 'INVALID'}")
            return validation
            
        except Exception as e:
            logger.error(f"Error validating temporal integrity for {law_uri}: {e}")
            return {
                'law_uri': law_uri,
                'valid': False,
                'issues': [{'type': 'validation_error', 'message': str(e)}],
                'statistics': {}
            }

    def detect_timeline_gaps(self, law_uri: str) -> Dict[str, Any]:
        """
        Detect gaps in version timeline coverage
        
        Args:
            law_uri: URI of the law
            
        Returns:
            Dictionary with gap detection results
        """
        result = {
            'valid': True,
            'gaps': [],
            'issues': []
        }
        
        try:
            query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            WITH v ORDER BY v.date_applicable
            WITH collect(v) AS versions
            UNWIND range(0, size(versions)-2) AS i
            WITH versions[i] AS current_v, versions[i+1] AS next_v
            WHERE current_v.date_end_applicable IS NOT NULL
              AND current_v.date_end_applicable < next_v.date_applicable
            RETURN current_v.uri AS current_version,
                   current_v.date_end_applicable AS gap_start,
                   next_v.uri AS next_version,
                   next_v.date_applicable AS gap_end,
                   duration.between(
                       datetime(current_v.date_end_applicable),
                       datetime(next_v.date_applicable)
                   ).days AS gap_days
            """
            
            gaps = self.connection.execute_query(query, {"law_uri": law_uri})
            
            if gaps:
                result['valid'] = False
                result['gaps'] = gaps
                result['issues'].append({
                    'type': 'timeline_gaps',
                    'count': len(gaps),
                    'message': f"Found {len(gaps)} timeline gaps"
                })
                
            logger.debug(f"Gap detection for {law_uri}: {len(gaps)} gaps found")
            return result
            
        except Exception as e:
            logger.error(f"Error detecting timeline gaps for {law_uri}: {e}")
            return {
                'valid': False,
                'gaps': [],
                'issues': [{'type': 'gap_detection_error', 'message': str(e)}]
            }

    def check_date_overlaps(self, law_uri: str) -> Dict[str, Any]:
        """
        Check for overlapping date ranges between versions
        
        Args:
            law_uri: URI of the law
            
        Returns:
            Dictionary with overlap detection results
        """
        result = {
            'valid': True,
            'overlaps': [],
            'issues': []
        }
        
        try:
            query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v1:Version)
            MATCH (l)-[:HAS_VERSION]->(v2:Version)
            WHERE v1.uri <> v2.uri
              AND v1.date_applicable < v2.date_applicable
              AND (v1.date_end_applicable IS NULL OR v1.date_end_applicable > v2.date_applicable)
            RETURN v1.uri AS earlier_version,
                   v1.date_applicable AS earlier_start,
                   v1.date_end_applicable AS earlier_end,
                   v2.uri AS later_version,
                   v2.date_applicable AS later_start,
                   v2.date_end_applicable AS later_end
            """
            
            overlaps = self.connection.execute_query(query, {"law_uri": law_uri})
            
            if overlaps:
                result['valid'] = False
                result['overlaps'] = overlaps
                result['issues'].append({
                    'type': 'date_overlaps',
                    'count': len(overlaps),
                    'message': f"Found {len(overlaps)} overlapping date ranges"
                })
                
            logger.debug(f"Overlap detection for {law_uri}: {len(overlaps)} overlaps found")
            return result
            
        except Exception as e:
            logger.error(f"Error checking date overlaps for {law_uri}: {e}")
            return {
                'valid': False,
                'overlaps': [],
                'issues': [{'type': 'overlap_detection_error', 'message': str(e)}]
            }

    def verify_version_chain_integrity(self, law_uri: str) -> Dict[str, Any]:
        """
        Verify that SUPERSEDES relationships form a valid chain
        
        Args:
            law_uri: URI of the law
            
        Returns:
            Dictionary with chain integrity results
        """
        result = {
            'valid': True,
            'issues': [],
            'chain_info': {}
        }
        
        try:
            # Check for broken chains
            broken_query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            WHERE v.date_end_applicable IS NOT NULL
              AND NOT EXISTS((v)<-[:SUPERSEDES]-())
            RETURN v.uri AS version, v.date_end_applicable AS end_date
            """
            
            broken = self.connection.execute_query(broken_query, {"law_uri": law_uri})
            
            if broken:
                result['valid'] = False
                result['issues'].append({
                    'type': 'broken_supersedes_chain',
                    'count': len(broken),
                    'versions': broken,
                    'message': f"Found {len(broken)} versions with end dates but no superseding version"
                })
            
            # Check for circular references
            circular_query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            MATCH path = (v)-[:SUPERSEDES*]->(v)
            RETURN v.uri AS version, length(path) AS cycle_length
            """
            
            circular = self.connection.execute_query(circular_query, {"law_uri": law_uri})
            
            if circular:
                result['valid'] = False
                result['issues'].append({
                    'type': 'circular_supersedes',
                    'count': len(circular),
                    'cycles': circular,
                    'message': f"Found {len(circular)} circular SUPERSEDES relationships"
                })
            
            # Get chain statistics
            stats_query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            OPTIONAL MATCH (v)-[:SUPERSEDES]->()
            RETURN count(v) AS total_versions,
                   count(CASE WHEN exists((v)-[:SUPERSEDES]->()) THEN 1 END) AS versions_with_successors,
                   count(CASE WHEN NOT exists((v)-[:SUPERSEDES]->()) 
                             AND NOT exists(()-[:SUPERSEDES]->(v)) THEN 1 END) AS isolated_versions
            """
            
            stats = self.connection.execute_query(stats_query, {"law_uri": law_uri})
            if stats:
                result['chain_info'] = stats[0]
            
            logger.debug(f"Chain integrity for {law_uri}: {'VALID' if result['valid'] else 'INVALID'}")
            return result
            
        except Exception as e:
            logger.error(f"Error verifying chain integrity for {law_uri}: {e}")
            return {
                'valid': False,
                'issues': [{'type': 'chain_verification_error', 'message': str(e)}],
                'chain_info': {}
            }

    def verify_current_version_marking(self, law_uri: str) -> Dict[str, Any]:
        """
        Verify that exactly one version is marked as current
        
        Args:
            law_uri: URI of the law
            
        Returns:
            Dictionary with current version validation results
        """
        result = {
            'valid': True,
            'issues': [],
            'current_versions': []
        }
        
        try:
            query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            WHERE v.date_end_applicable IS NULL
            RETURN v.uri AS version,
                   v.date_applicable AS start_date,
                   v.is_current AS is_current
            ORDER BY v.date_applicable DESC
            """
            
            current_candidates = self.connection.execute_query(query, {"law_uri": law_uri})
            
            # Check for multiple current versions
            current_versions = [v for v in current_candidates if v.get('is_current', False)]
            active_versions = [v for v in current_candidates if v['date_end_applicable'] is None]
            
            if len(current_versions) > 1:
                result['valid'] = False
                result['issues'].append({
                    'type': 'multiple_current_versions',
                    'count': len(current_versions),
                    'versions': current_versions,
                    'message': f"Found {len(current_versions)} versions marked as current"
                })
            
            if len(active_versions) > 1:
                result['valid'] = False
                result['issues'].append({
                    'type': 'multiple_active_versions',
                    'count': len(active_versions),
                    'versions': active_versions,
                    'message': f"Found {len(active_versions)} versions without end dates"
                })
            
            result['current_versions'] = current_candidates
            
            logger.debug(f"Current version check for {law_uri}: {'VALID' if result['valid'] else 'INVALID'}")
            return result
            
        except Exception as e:
            logger.error(f"Error verifying current version for {law_uri}: {e}")
            return {
                'valid': False,
                'issues': [{'type': 'current_version_error', 'message': str(e)}],
                'current_versions': []
            }

    def get_temporal_statistics(self, law_uri: str) -> Dict[str, Any]:
        """
        Get comprehensive temporal statistics for a law
        
        Args:
            law_uri: URI of the law
            
        Returns:
            Dictionary with temporal statistics
        """
        try:
            query = """
            MATCH (l:Law {uri: $law_uri})-[:HAS_VERSION]->(v:Version)
            RETURN count(v) AS total_versions,
                   min(v.date_applicable) AS earliest_version,
                   max(v.date_applicable) AS latest_version,
                   count(CASE WHEN v.date_end_applicable IS NULL THEN 1 END) AS active_versions,
                   count(CASE WHEN exists((v)-[:SUPERSEDES]->()) THEN 1 END) AS versions_with_successors,
                   avg(duration.between(
                       datetime(v.date_applicable),
                       datetime(CASE WHEN v.date_end_applicable IS NOT NULL 
                               THEN v.date_end_applicable 
                               ELSE datetime() END)
                   ).days) AS avg_version_duration_days
            """
            
            result = self.connection.execute_query(query, {"law_uri": law_uri})
            
            if result:
                stats = result[0]
                # Calculate additional metrics
                if stats['total_versions'] > 1:
                    stats['chain_completeness'] = (stats['versions_with_successors'] / 
                                                 (stats['total_versions'] - 1)) * 100
                else:
                    stats['chain_completeness'] = 100.0
                
                return stats
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error getting temporal statistics for {law_uri}: {e}")
            return {}