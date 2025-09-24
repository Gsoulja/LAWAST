"""
Test suite for Neo4j graph operations
"""
import unittest
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import Neo4jConnectionManager
from src.data_access.graph_schema import (
    GraphSchema, NodeLabels, RelationshipTypes,
    LawNode, VersionNode, ArticleNode, LanguageNode, ManifestationNode
)
from src.data_access.graph_builder import GraphBuilder
from src.data_access.batch_processor import BatchProcessor, ProcessingCheckpoint


class TestNeo4jConnection(unittest.TestCase):
    """Test Neo4j connection manager"""

    def setUp(self):
        """Set up test fixtures"""
        self.connection = None

    def tearDown(self):
        """Clean up after tests"""
        if self.connection:
            self.connection.close()

    @patch('src.data_access.neo4j_connection.GraphDatabase')
    def test_connection_initialization(self, mock_graph_db):
        """Test connection manager initialization"""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver

        connection = Neo4jConnectionManager(
            uri="bolt://localhost:7687",
            user="test_user",
            password="test_pass"
        )

        mock_graph_db.driver.assert_called_once()
        self.assertEqual(connection.uri, "bolt://localhost:7687")
        self.assertEqual(connection.user, "test_user")

    @patch('src.data_access.neo4j_connection.GraphDatabase')
    def test_health_check(self, mock_graph_db):
        """Test health check functionality"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        # Mock successful query
        mock_result = [{"health": 1}]
        mock_session.run.return_value = mock_result

        connection = Neo4jConnectionManager()
        connection._driver = mock_driver

        # Health check should return True
        health = connection.health_check()
        self.assertTrue(health)

    @patch('src.data_access.neo4j_connection.GraphDatabase')
    def test_retry_logic(self, mock_graph_db):
        """Test retry logic on transient errors"""
        from neo4j.exceptions import TransientError

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        # Mock transient error then success
        mock_session.run.side_effect = [
            TransientError("Connection lost"),
            [{"result": "success"}]
        ]

        connection = Neo4jConnectionManager(max_retries=2, retry_delay=0.1)
        connection._driver = mock_driver

        result = connection.execute_query("RETURN 1")
        self.assertEqual(result, [{"result": "success"}])
        self.assertEqual(mock_session.run.call_count, 2)


class TestGraphSchema(unittest.TestCase):
    """Test graph schema definitions"""

    def test_law_node_creation(self):
        """Test LawNode creation and serialization"""
        law = LawNode(
            uri="https://fedlex.data.admin.ch/eli/cc/1999/404",
            sr_number="101",
            title_de="Bundesverfassung",
            title_fr="Constitution fédérale",
            date_enacted=datetime(1999, 4, 18)
        )

        props = law.to_cypher_properties()
        self.assertEqual(props["uri"], "https://fedlex.data.admin.ch/eli/cc/1999/404")
        self.assertEqual(props["sr_number"], "101")
        self.assertEqual(props["title_de"], "Bundesverfassung")
        self.assertEqual(props["title_fr"], "Constitution fédérale")
        self.assertIn("date_enacted", props)

    def test_version_node_creation(self):
        """Test VersionNode creation and serialization"""
        version = VersionNode(
            uri="https://fedlex.data.admin.ch/eli/cc/1999/404/20240101",
            law_uri="https://fedlex.data.admin.ch/eli/cc/1999/404",
            date_applicable=datetime(2024, 1, 1),
            date_end_applicable=datetime(2024, 3, 1)
        )

        props = version.to_cypher_properties()
        self.assertEqual(props["uri"], "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101")
        self.assertEqual(props["law_uri"], "https://fedlex.data.admin.ch/eli/cc/1999/404")
        self.assertIn("date_applicable", props)
        self.assertIn("date_end_applicable", props)

    def test_article_node_creation(self):
        """Test ArticleNode creation and serialization"""
        article = ArticleNode(
            uri="https://fedlex.data.admin.ch/eli/cc/1999/404/art_1",
            law_uri="https://fedlex.data.admin.ch/eli/cc/1999/404",
            number="1",
            title="Schweizerische Eidgenossenschaft"
        )

        props = article.to_cypher_properties()
        self.assertEqual(props["number"], "1")
        self.assertEqual(props["title"], "Schweizerische Eidgenossenschaft")

    def test_schema_validation(self):
        """Test schema validation methods"""
        # Test valid node labels
        self.assertTrue(GraphSchema.validate_node_label("Law"))
        self.assertTrue(GraphSchema.validate_node_label("Version"))
        self.assertFalse(GraphSchema.validate_node_label("InvalidLabel"))

        # Test valid relationship types
        self.assertTrue(GraphSchema.validate_relationship_type("HAS_VERSION"))
        self.assertTrue(GraphSchema.validate_relationship_type("SUPERSEDES"))
        self.assertFalse(GraphSchema.validate_relationship_type("INVALID_REL"))

    def test_schema_info(self):
        """Test schema information retrieval"""
        info = GraphSchema.get_schema_info()
        self.assertIn("node_labels", info)
        self.assertIn("relationship_types", info)
        self.assertIn("Law", info["node_labels"])
        self.assertIn("HAS_VERSION", info["relationship_types"])


class TestGraphBuilder(unittest.TestCase):
    """Test graph builder operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_connection = MagicMock(spec=Neo4jConnectionManager)
        self.graph_builder = GraphBuilder(self.mock_connection)

    def test_create_law_node(self):
        """Test creating a law node"""
        law = LawNode(
            uri="test_uri",
            sr_number="123",
            title_de="Test Law"
        )

        self.mock_connection.execute_write.return_value = [{"l": {"uri": "test_uri"}}]

        result = self.graph_builder.create_law_node(law)
        self.assertEqual(result["uri"], "test_uri")
        self.mock_connection.execute_write.assert_called_once()

    def test_batch_create_nodes(self):
        """Test batch node creation"""
        nodes = [
            LawNode(uri=f"law_{i}", sr_number=str(i))
            for i in range(5)
        ]

        self.mock_connection.execute_write.return_value = [{"created": 5}]

        count = self.graph_builder.batch_create_nodes(nodes, batch_size=10)
        self.assertEqual(count, 5)

    def test_create_relationship(self):
        """Test relationship creation"""
        self.mock_connection.execute_write.return_value = []

        success = self.graph_builder.create_relationship(
            "uri1", "uri2", "HAS_VERSION"
        )
        self.assertTrue(success)

        # Test invalid relationship type
        success = self.graph_builder.create_relationship(
            "uri1", "uri2", "INVALID_TYPE"
        )
        self.assertFalse(success)

    def test_build_version_chains(self):
        """Test version chain building"""
        self.mock_connection.execute_write.return_value = [{"created": 3}]

        count = self.graph_builder.build_version_chains("law_uri")
        self.assertEqual(count, 3)

    def test_query_operations(self):
        """Test various query operations"""
        # Test get_law_by_uri
        self.mock_connection.execute_query.return_value = [{"l": {"uri": "test"}}]
        law = self.graph_builder.get_law_by_uri("test")
        self.assertEqual(law["uri"], "test")

        # Test get_law_versions
        self.mock_connection.execute_query.return_value = [
            {"v": {"uri": "v1"}},
            {"v": {"uri": "v2"}}
        ]
        versions = self.graph_builder.get_law_versions("law_uri")
        self.assertEqual(len(versions), 2)

        # Test get_statistics
        self.mock_connection.execute_query.return_value = [
            {"label": "Law", "count": 100},
            {"label": "Version", "count": 500}
        ]
        stats = self.graph_builder.get_statistics()
        self.assertEqual(stats["Law"], 100)
        self.assertEqual(stats["Version"], 500)


class TestBatchProcessor(unittest.TestCase):
    """Test batch processing utilities"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_graph_builder = MagicMock(spec=GraphBuilder)
        self.processor = BatchProcessor(
            graph_builder=self.mock_graph_builder,
            checkpoint_file="test_checkpoint.json"
        )

    def tearDown(self):
        """Clean up test files"""
        if os.path.exists("test_checkpoint.json"):
            os.remove("test_checkpoint.json")

    def test_checkpoint_save_load(self):
        """Test checkpoint saving and loading"""
        checkpoint = ProcessingCheckpoint(
            total_files=100,
            processed_files=50,
            failed_files=2,
            last_processed_file="test.json"
        )
        self.processor.checkpoint = checkpoint
        self.processor.save_checkpoint()

        # Load checkpoint
        new_processor = BatchProcessor(checkpoint_file="test_checkpoint.json")
        loaded = new_processor.load_checkpoint()
        self.assertTrue(loaded)
        self.assertEqual(new_processor.checkpoint.total_files, 100)
        self.assertEqual(new_processor.checkpoint.processed_files, 50)

    def test_process_in_batches(self):
        """Test batch processing"""
        items = list(range(100))

        def batch_func(batch):
            return len(batch)

        total = self.processor.process_in_batches(
            items, batch_func, item_name="numbers"
        )
        self.assertEqual(total, 100)

    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_parallel_process(self, mock_executor):
        """Test parallel processing"""
        items = [1, 2, 3, 4, 5]

        def processor_func(item):
            return item * 2

        # Mock the executor
        mock_executor_instance = MagicMock()
        mock_executor.return_value.__enter__.return_value = mock_executor_instance

        # Mock futures
        mock_futures = []
        for item in items:
            mock_future = MagicMock()
            mock_future.result.return_value = item * 2
            mock_futures.append(mock_future)

        mock_executor_instance.submit.side_effect = mock_futures

        # Mock as_completed
        with patch('src.data_access.batch_processor.as_completed') as mock_completed:
            mock_completed.return_value = mock_futures

            results = self.processor.parallel_process(
                items, processor_func, item_name="numbers"
            )

            # Check results
            self.assertEqual(len(results), 5)


class TestIntegration(unittest.TestCase):
    """Integration tests (requires Neo4j running)"""

    @classmethod
    def setUpClass(cls):
        """Set up class fixtures"""
        cls.skip_integration = os.getenv("SKIP_INTEGRATION_TESTS", "true").lower() == "true"
        if not cls.skip_integration:
            try:
                cls.connection = Neo4jConnectionManager()
                cls.graph_builder = GraphBuilder(cls.connection)
            except Exception as e:
                print(f"Skipping integration tests: {e}")
                cls.skip_integration = True

    @classmethod
    def tearDownClass(cls):
        """Clean up class fixtures"""
        if not cls.skip_integration:
            # Clean up test data
            try:
                cls.connection.execute_write(
                    "MATCH (n) WHERE n.uri STARTS WITH 'test_' DETACH DELETE n"
                )
                cls.connection.close()
            except:
                pass

    def setUp(self):
        """Set up test fixtures"""
        if self.skip_integration:
            self.skipTest("Integration tests skipped (Neo4j not available)")

    def test_end_to_end_workflow(self):
        """Test complete workflow from node creation to querying"""
        # Create a law node
        law = LawNode(
            uri="test_law_001",
            sr_number="999.99",
            title_de="Test Gesetz"
        )
        law_result = self.graph_builder.create_law_node(law)
        self.assertIsNotNone(law_result)

        # Create version nodes
        version1 = VersionNode(
            uri="test_version_001",
            law_uri="test_law_001",
            date_applicable=datetime(2023, 1, 1)
        )
        version2 = VersionNode(
            uri="test_version_002",
            law_uri="test_law_001",
            date_applicable=datetime(2024, 1, 1)
        )

        self.graph_builder.create_version_node(version1)
        self.graph_builder.create_version_node(version2)

        # Create relationships
        self.graph_builder.create_has_version("test_law_001", "test_version_001")
        self.graph_builder.create_has_version("test_law_001", "test_version_002")
        self.graph_builder.create_supersedes("test_version_002", "test_version_001")

        # Query the graph
        versions = self.graph_builder.get_law_versions("test_law_001")
        self.assertEqual(len(versions), 2)

        # Get statistics
        stats = self.graph_builder.get_statistics()
        self.assertIn("Law", stats)
        self.assertIn("Version", stats)


if __name__ == "__main__":
    unittest.main()