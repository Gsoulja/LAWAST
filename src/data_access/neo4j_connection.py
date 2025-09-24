"""
Neo4j connection manager with pooling and retry logic
"""
import os
import time
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Neo4jConnectionManager:
    """
    Manages Neo4j database connections with pooling and retry logic
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        connection_timeout: int = 30
    ):
        """
        Initialize the connection manager

        Args:
            uri: Neo4j URI (default: from environment)
            user: Neo4j username (default: from environment)
            password: Neo4j password (default: from environment)
            database: Database name (default: from environment or 'neo4j')
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            connection_timeout: Connection timeout in seconds
        """
        self.uri = uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.user = user or os.getenv('NEO4J_USER', 'neo4j')
        self.password = password or os.getenv('NEO4J_PASSWORD', 'lawast2024')
        self.database = database or os.getenv('NEO4J_DATABASE', 'neo4j')

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_timeout = connection_timeout

        self._driver: Optional[Driver] = None
        self._initialize_driver()

    def _initialize_driver(self):
        """Initialize the Neo4j driver with connection pooling"""
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=50,
                connection_acquisition_timeout=self.connection_timeout,
                connection_timeout=self.connection_timeout,
                keep_alive=True
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    @property
    def driver(self) -> Driver:
        """Get the Neo4j driver instance"""
        if not self._driver:
            self._initialize_driver()
        return self._driver

    @contextmanager
    def get_session(self, **kwargs) -> Session:
        """
        Get a Neo4j session with automatic cleanup

        Args:
            **kwargs: Additional session configuration

        Yields:
            Neo4j session
        """
        session = self.driver.session(database=self.database, **kwargs)
        try:
            yield session
        finally:
            session.close()

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Execute a read query with retry logic

        Args:
            query: Cypher query string
            parameters: Query parameters
            **kwargs: Additional session configuration

        Returns:
            List of result records as dictionaries
        """
        for attempt in range(self.max_retries):
            try:
                with self.get_session(**kwargs) as session:
                    result = session.run(query, parameters or {})
                    return [record.data() for record in result]
            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Query failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"Query failed after {self.max_retries} attempts: {e}")
                    raise

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Execute a write query with retry logic

        Args:
            query: Cypher query string
            parameters: Query parameters
            **kwargs: Additional session configuration

        Returns:
            List of result records as dictionaries
        """
        def work(tx):
            result = tx.run(query, parameters or {})
            return [record.data() for record in result]

        for attempt in range(self.max_retries):
            try:
                with self.get_session(**kwargs) as session:
                    return session.execute_write(work)
            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Write failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Write failed after {self.max_retries} attempts: {e}")
                    raise

    def batch_write(
        self,
        queries: List[tuple[str, Dict[str, Any]]],
        batch_size: int = 1000
    ) -> int:
        """
        Execute multiple write queries in batches

        Args:
            queries: List of (query, parameters) tuples
            batch_size: Number of queries per batch

        Returns:
            Total number of affected records
        """
        total_affected = 0

        for i in range(0, len(queries), batch_size):
            batch = queries[i:i + batch_size]

            def work(tx):
                affected = 0
                for query, params in batch:
                    result = tx.run(query, params)
                    summary = result.consume()
                    if summary.counters:
                        affected += (
                            summary.counters.nodes_created +
                            summary.counters.nodes_deleted +
                            summary.counters.relationships_created +
                            summary.counters.relationships_deleted +
                            summary.counters.properties_set
                        )
                return affected

            with self.get_session() as session:
                total_affected += session.execute_write(work)

            logger.info(f"Processed batch {i // batch_size + 1}, total affected: {total_affected}")

        return total_affected

    def health_check(self) -> bool:
        """
        Check if the Neo4j connection is healthy

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            self.execute_query("RETURN 1 AS health")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the Neo4j database

        Returns:
            Dictionary with database information
        """
        try:
            # Get database version and edition
            version_result = self.execute_query(
                "CALL dbms.components() YIELD name, versions, edition "
                "WHERE name = 'Neo4j Kernel' "
                "RETURN versions[0] AS version, edition"
            )

            # Get node and relationship counts
            counts_result = self.execute_query(
                """
                MATCH (n)
                WITH count(n) AS node_count
                MATCH ()-[r]->()
                RETURN node_count, count(r) AS relationship_count
                """
            )

            # Get database size
            size_result = self.execute_query(
                "CALL apoc.meta.stats() YIELD nodeCount, relCount, "
                "propertyKeyCount, labelCount, relTypeCount"
            )

            info = {
                "uri": self.uri,
                "database": self.database,
                "connected": True,
            }

            if version_result:
                info.update(version_result[0])
            if counts_result:
                info.update(counts_result[0])
            if size_result:
                info.update(size_result[0])

            return info
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "uri": self.uri,
                "database": self.database,
                "connected": False,
                "error": str(e)
            }

    def close(self):
        """Close the driver connection"""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __del__(self):
        """Destructor to ensure connection is closed"""
        self.close()


# Singleton instance
_connection_manager: Optional[Neo4jConnectionManager] = None


def get_connection() -> Neo4jConnectionManager:
    """
    Get the global Neo4j connection manager instance

    Returns:
        Neo4jConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = Neo4jConnectionManager()
    return _connection_manager


def close_connection():
    """Close the global Neo4j connection"""
    global _connection_manager
    if _connection_manager:
        _connection_manager.close()
        _connection_manager = None