#!/usr/bin/env python3
"""
Initialize Neo4j database schema with constraints, indexes, and base data
"""
import sys
import os
import time
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import Neo4jConnectionManager, get_connection
from src.data_access.graph_schema import GraphSchema
from src.data_access.graph_builder import GraphBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Neo4jSchemaInitializer:
    """
    Initializes the Neo4j database schema and base data
    """

    def __init__(self, connection: Neo4jConnectionManager = None):
        """
        Initialize the schema initializer

        Args:
            connection: Neo4j connection manager
        """
        self.connection = connection or get_connection()
        self.graph_builder = GraphBuilder(self.connection)

    def check_connection(self) -> bool:
        """
        Check if Neo4j is accessible

        Returns:
            True if connected, False otherwise
        """
        logger.info("Checking Neo4j connection...")
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                if self.connection.health_check():
                    logger.info("✅ Successfully connected to Neo4j")
                    return True
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

        logger.error("❌ Failed to connect to Neo4j after multiple attempts")
        return False

    def create_constraints(self) -> int:
        """
        Create unique constraints on the database

        Returns:
            Number of constraints created
        """
        logger.info("Creating unique constraints...")
        constraints = GraphSchema.get_all_constraints()
        created = 0

        for constraint_query in constraints:
            try:
                self.connection.execute_write(constraint_query)
                created += 1
                logger.info(f"  ✅ Created constraint: {constraint_query.split('REQUIRE')[1].strip()}")
            except Exception as e:
                # Constraint might already exist
                if "already exists" in str(e).lower():
                    logger.debug(f"  ℹ️ Constraint already exists: {constraint_query.split('REQUIRE')[1].strip()}")
                else:
                    logger.error(f"  ❌ Failed to create constraint: {e}")

        logger.info(f"Created {created} new constraints")
        return created

    def create_indexes(self) -> int:
        """
        Create indexes for query performance

        Returns:
            Number of indexes created
        """
        logger.info("Creating indexes...")
        indexes = GraphSchema.get_all_indexes()
        created = 0

        for index_query in indexes:
            try:
                self.connection.execute_write(index_query)
                created += 1
                # Extract index name from query
                index_name = index_query.split("CREATE INDEX")[1].split("IF NOT EXISTS")[0].strip()
                logger.info(f"  ✅ Created index: {index_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    index_name = index_query.split("CREATE INDEX")[1].split("IF NOT EXISTS")[0].strip()
                    logger.debug(f"  ℹ️ Index already exists: {index_name}")
                else:
                    logger.error(f"  ❌ Failed to create index: {e}")

        logger.info(f"Created {created} new indexes")
        return created

    def initialize_base_data(self) -> int:
        """
        Initialize base data (languages, etc.)

        Returns:
            Number of nodes created
        """
        logger.info("Initializing base data...")
        queries = GraphSchema.get_initialization_queries()
        created = 0

        for query, params in queries:
            try:
                result = self.connection.execute_write(query, params)
                created += 1
                logger.info(f"  ✅ Initialized: {params}")
            except Exception as e:
                logger.error(f"  ❌ Failed to initialize data: {e}")

        logger.info(f"Initialized {created} base data nodes")
        return created

    def verify_schema(self) -> bool:
        """
        Verify that the schema is properly set up

        Returns:
            True if schema is valid, False otherwise
        """
        logger.info("Verifying schema...")

        try:
            # Check constraints
            constraints_query = """
            SHOW CONSTRAINTS
            YIELD name, type, entityType, labelsOrTypes, properties
            RETURN count(*) AS constraint_count
            """
            constraints_result = self.connection.execute_query(constraints_query)
            constraint_count = constraints_result[0]['constraint_count'] if constraints_result else 0
            logger.info(f"  ✅ Found {constraint_count} constraints")

            # Check indexes
            indexes_query = """
            SHOW INDEXES
            YIELD name, type, entityType, labelsOrTypes, properties
            WHERE type <> 'LOOKUP'
            RETURN count(*) AS index_count
            """
            indexes_result = self.connection.execute_query(indexes_query)
            index_count = indexes_result[0]['index_count'] if indexes_result else 0
            logger.info(f"  ✅ Found {index_count} indexes")

            # Check language nodes
            languages_query = """
            MATCH (l:Language)
            RETURN count(l) AS language_count
            """
            languages_result = self.connection.execute_query(languages_query)
            language_count = languages_result[0]['language_count'] if languages_result else 0
            logger.info(f"  ✅ Found {language_count} language nodes")

            # Get database info
            db_info = self.connection.get_database_info()
            if db_info.get("connected"):
                logger.info(f"  ✅ Database info: {db_info}")

            return constraint_count > 0 and index_count > 0 and language_count > 0

        except Exception as e:
            logger.error(f"Failed to verify schema: {e}")
            return False

    def get_schema_report(self) -> str:
        """
        Generate a detailed schema report

        Returns:
            Schema report as string
        """
        report = []
        report.append("=" * 60)
        report.append("NEO4J SCHEMA REPORT")
        report.append("=" * 60)

        try:
            # Database info
            db_info = self.connection.get_database_info()
            report.append("\n📊 DATABASE INFO:")
            report.append(f"  URI: {db_info.get('uri', 'N/A')}")
            report.append(f"  Database: {db_info.get('database', 'N/A')}")
            report.append(f"  Connected: {db_info.get('connected', False)}")
            if 'version' in db_info:
                report.append(f"  Version: {db_info.get('version', 'N/A')}")
            if 'edition' in db_info:
                report.append(f"  Edition: {db_info.get('edition', 'N/A')}")

            # Node counts
            node_query = """
            MATCH (n)
            WITH labels(n)[0] AS label, count(n) AS count
            WHERE label IS NOT NULL
            RETURN label, count
            ORDER BY label
            """
            node_results = self.connection.execute_query(node_query)

            report.append("\n📦 NODE COUNTS:")
            if node_results:
                for result in node_results:
                    report.append(f"  {result['label']}: {result['count']}")
            else:
                report.append("  No nodes found")

            # Relationship counts
            rel_query = """
            MATCH ()-[r]->()
            WITH type(r) AS type, count(r) AS count
            RETURN type, count
            ORDER BY type
            """
            rel_results = self.connection.execute_query(rel_query)

            report.append("\n🔗 RELATIONSHIP COUNTS:")
            if rel_results:
                for result in rel_results:
                    report.append(f"  {result['type']}: {result['count']}")
            else:
                report.append("  No relationships found")

            # Constraints
            constraints_query = """
            SHOW CONSTRAINTS
            YIELD name, labelsOrTypes, properties
            RETURN name, labelsOrTypes[0] AS label, properties[0] AS property
            """
            constraints_results = self.connection.execute_query(constraints_query)

            report.append("\n🔒 CONSTRAINTS:")
            if constraints_results:
                for result in constraints_results:
                    report.append(f"  {result['label']}.{result['property']} (UNIQUE)")
            else:
                report.append("  No constraints found")

            # Indexes
            indexes_query = """
            SHOW INDEXES
            YIELD name, labelsOrTypes, properties, type
            WHERE type <> 'LOOKUP'
            RETURN name, labelsOrTypes[0] AS label, properties AS props
            """
            indexes_results = self.connection.execute_query(indexes_query)

            report.append("\n🔍 INDEXES:")
            if indexes_results:
                for result in indexes_results:
                    props = ", ".join(result['props']) if result['props'] else "N/A"
                    report.append(f"  {result['label']}: {props}")
            else:
                report.append("  No indexes found")

            # Schema info
            schema_info = GraphSchema.get_schema_info()
            report.append("\n📋 SCHEMA DEFINITION:")
            report.append(f"  Node Labels: {', '.join(schema_info['node_labels'])}")
            report.append(f"  Relationship Types: {', '.join(schema_info['relationship_types'])}")
            report.append(f"  Language Codes: {', '.join(schema_info['language_codes'])}")
            report.append(f"  Manifestation Formats: {', '.join(schema_info['manifestation_formats'])}")

        except Exception as e:
            report.append(f"\n❌ ERROR generating report: {e}")

        report.append("\n" + "=" * 60)
        return "\n".join(report)

    def initialize(self, force: bool = False) -> bool:
        """
        Initialize the complete schema

        Args:
            force: Force re-initialization even if schema exists

        Returns:
            True if successful, False otherwise
        """
        logger.info("🚀 Starting Neo4j schema initialization...")

        # Check connection
        if not self.check_connection():
            return False

        # Check if already initialized
        if not force:
            if self.verify_schema():
                logger.info("ℹ️ Schema already initialized. Use --force to re-initialize.")
                print("\n" + self.get_schema_report())
                return True

        # Create constraints
        self.create_constraints()

        # Create indexes
        self.create_indexes()

        # Initialize base data
        self.initialize_base_data()

        # Verify schema
        if self.verify_schema():
            logger.info("✅ Schema initialization completed successfully!")
            print("\n" + self.get_schema_report())
            return True
        else:
            logger.error("❌ Schema initialization failed verification")
            return False


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Neo4j database schema")
    parser.add_argument("--force", action="store_true", help="Force re-initialization")
    parser.add_argument("--report-only", action="store_true", help="Only show schema report")
    args = parser.parse_args()

    try:
        initializer = Neo4jSchemaInitializer()

        if args.report_only:
            if initializer.check_connection():
                print(initializer.get_schema_report())
            return 0

        success = initializer.initialize(force=args.force)
        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("\n⚠️ Initialization interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())