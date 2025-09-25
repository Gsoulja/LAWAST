"""
Unit tests for Neo4j Storage Pipeline
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from pathlib import Path

from src.data_access.storage_pipeline import Neo4jStoragePipeline, StorageStatistics
from src.extractors.extracted_content import ExtractedContent
from src.extractors.taxonomy_extractor import TaxonomyResult, HierarchyLevel
from src.extractors.article_extractor import Article, ArticleContent, Paragraph


class TestStorageStatistics(unittest.TestCase):
    """Test StorageStatistics class"""

    def test_throughput_calculation(self):
        """Test throughput calculation"""
        stats = StorageStatistics(
            taxonomy_nodes_created=100,
            articles_created=900,
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 12, 0, 1)  # 1 second later
        )

        throughput = stats.get_throughput()
        self.assertEqual(throughput, 1000.0)  # 1000 nodes/second

    def test_throughput_no_time(self):
        """Test throughput when times not set"""
        stats = StorageStatistics()
        self.assertEqual(stats.get_throughput(), 0.0)


class TestNeo4jStoragePipeline(unittest.TestCase):
    """Test Neo4jStoragePipeline class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_connection = Mock()
        self.mock_connection.health_check.return_value = True
        self.mock_connection.execute_write.return_value = [{"created": 10}]

        with patch('src.data_access.storage_pipeline.get_connection', return_value=self.mock_connection):
            with patch('src.data_access.storage_pipeline.GraphBuilder'):
                self.pipeline = Neo4jStoragePipeline(
                    connection=self.mock_connection,
                    batch_size=100,
                    checkpoint_file="test_checkpoint.json"
                )

    def test_initialization(self):
        """Test pipeline initialization"""
        self.assertEqual(self.pipeline.batch_size, 100)
        self.assertEqual(self.pipeline.checkpoint_file, "test_checkpoint.json")
        self.assertIsNotNone(self.pipeline.statistics)

    def test_store_empty_content(self):
        """Test storing empty content"""
        content = ExtractedContent(
            taxonomy=None,
            articles=[],
            references=[]
        )

        with patch.object(self.pipeline, 'load_checkpoint', return_value=False):
            with patch.object(self.pipeline, 'save_checkpoint'):
                stats = self.pipeline.store_extracted_content(content, resume=False)

        self.assertEqual(stats.taxonomy_nodes_created, 0)
        self.assertEqual(stats.articles_created, 0)
        self.assertEqual(stats.relationships_created, 0)

    def test_store_taxonomy(self):
        """Test taxonomy storage"""
        hierarchy = HierarchyLevel(
            type="Book",
            number="1",
            title={"de": "Buch 1", "fr": "Livre 1"},
            uri="book/1",
            children=[
                HierarchyLevel(
                    type="Chapter",
                    number="1.1",
                    title={"de": "Kapitel 1", "fr": "Chapitre 1"},
                    uri="chapter/1.1",
                    children=[]
                )
            ]
        )

        taxonomy = TaxonomyResult(
            sr_number="SR 101",
            title={"de": "Test", "fr": "Test"},
            hierarchy=[hierarchy]
        )

        with patch.object(self.pipeline, '_batch_create_taxonomy_nodes', return_value=2):
            self.pipeline._store_taxonomy(taxonomy)

        self.assertEqual(self.pipeline.statistics.taxonomy_nodes_created, 2)

    def test_store_articles(self):
        """Test article storage"""
        articles = [
            Article(
                uri="article/1",
                number="1",
                number_normalized="001",
                titles={"de": "Artikel 1"},
                content=ArticleContent(
                    paragraphs=[
                        Paragraph(number="1", text="Test paragraph")
                    ]
                )
            ),
            Article(
                uri="article/2",
                number="2",
                number_normalized="002",
                titles={"de": "Artikel 2"}
            )
        ]

        self.pipeline._store_articles(articles, "law/1")

        # Check execute_write was called
        self.mock_connection.execute_write.assert_called()
        call_args = self.mock_connection.execute_write.call_args
        self.assertIn("UNWIND", call_args[0][0])
        self.assertIn("batch", call_args[0][1])
        self.assertEqual(len(call_args[0][1]["batch"]), 2)

    def test_create_relationships(self):
        """Test relationship creation"""
        content = ExtractedContent(
            taxonomy=TaxonomyResult(
                hierarchy=[
                    HierarchyLevel(
                        type="Book",
                        number="1",
                        title={"de": "Buch 1"},
                        uri="book/1",
                        children=[]
                    )
                ]
            ),
            articles=[
                Article(uri="article/1", number="1", number_normalized="001"),
                Article(uri="article/2", number="2", number_normalized="002")
            ],
            references=[],
            law_uri="law/1"
        )

        with patch.object(self.pipeline, '_batch_create_relationships', return_value=5):
            self.pipeline._create_relationships(content)

        self.assertGreater(self.pipeline.statistics.relationships_created, 0)

    def test_batch_create_taxonomy_nodes(self):
        """Test batch creation of taxonomy nodes"""
        nodes = [
            {"uri": "book/1", "type": "Book", "name": "Book 1"},
            {"uri": "chapter/1", "type": "Chapter", "name": "Chapter 1"},
            {"uri": "chapter/2", "type": "Chapter", "name": "Chapter 2"}
        ]

        created = self.pipeline._batch_create_taxonomy_nodes(nodes)

        # Should group by type and call execute_write
        self.mock_connection.execute_write.assert_called()
        self.assertEqual(created, 30)  # 3 calls * 10 (mock return value)

    def test_create_follows_relationships(self):
        """Test creation of FOLLOWS relationships"""
        articles = [
            Article(uri="article/2", number="2", number_normalized="002"),
            Article(uri="article/1", number="1", number_normalized="001"),
            Article(uri="article/3", number="3", number_normalized="003")
        ]

        with patch.object(self.pipeline, '_batch_create_relationships') as mock_batch:
            mock_batch.return_value = 2
            result = self.pipeline._create_follows_relationships(articles)

        # Should create 2 FOLLOWS relationships (1->2, 2->3)
        self.assertEqual(result, 2)
        mock_batch.assert_called_once()
        relationships = mock_batch.call_args[0][0]
        self.assertEqual(len(relationships), 2)
        self.assertEqual(relationships[0]["from_uri"], "article/1")
        self.assertEqual(relationships[0]["to_uri"], "article/2")
        self.assertEqual(relationships[1]["from_uri"], "article/2")
        self.assertEqual(relationships[1]["to_uri"], "article/3")

    def test_validation_errors_logged(self):
        """Test that validation errors are logged"""
        content = ExtractedContent(
            taxonomy=None,  # Missing taxonomy
            articles=[]  # No articles
        )

        with patch.object(self.pipeline, 'load_checkpoint', return_value=False):
            with patch.object(self.pipeline, 'save_checkpoint'):
                stats = self.pipeline.store_extracted_content(content, resume=False)

        # Should have validation errors
        self.assertGreater(len(stats.errors), 0)
        validation_errors = [e for e in stats.errors if e["type"] == "validation"]
        self.assertGreater(len(validation_errors), 0)

    def test_checkpoint_resume(self):
        """Test checkpoint resume functionality"""
        content = ExtractedContent(
            taxonomy=TaxonomyResult(hierarchy=[]),
            articles=[],
            references=[]
        )

        # Mock checkpoint with articles phase completed
        mock_checkpoint = Mock()
        mock_checkpoint.statistics = {"current_phase": "relationships"}

        with patch.object(self.pipeline, 'load_checkpoint', return_value=True):
            with patch.object(self.pipeline, 'checkpoint', mock_checkpoint):
                with patch.object(self.pipeline, 'save_checkpoint'):
                    with patch.object(self.pipeline, '_store_taxonomy') as mock_taxonomy:
                        with patch.object(self.pipeline, '_store_articles') as mock_articles:
                            stats = self.pipeline.store_extracted_content(content, resume=True)

        # Should skip taxonomy and articles phases
        mock_taxonomy.assert_not_called()
        mock_articles.assert_not_called()

    def test_error_handling(self):
        """Test error handling during storage"""
        content = ExtractedContent(
            taxonomy=TaxonomyResult(hierarchy=[]),
            articles=[Article(uri="test", number="1", number_normalized="001")]
        )

        # Make execute_write raise an exception
        self.mock_connection.execute_write.side_effect = Exception("Database error")

        with patch.object(self.pipeline, 'load_checkpoint', return_value=False):
            with patch.object(self.pipeline, 'save_checkpoint'):
                with self.assertRaises(Exception):
                    self.pipeline.store_extracted_content(content, resume=False)

        # Should have error in statistics
        self.assertGreater(len(self.pipeline.statistics.errors), 0)


class TestExtractedContent(unittest.TestCase):
    """Test ExtractedContent class"""

    def test_get_statistics(self):
        """Test statistics calculation"""
        content = ExtractedContent(
            taxonomy=TaxonomyResult(
                hierarchy=[Mock(), Mock()],
                title={"de": "Test", "fr": "Test"}
            ),
            articles=[
                Article(
                    uri="a1",
                    number="1",
                    number_normalized="001",
                    content=ArticleContent(
                        paragraphs=[
                            Paragraph(number="1", text="Test", subpoints=[Mock(), Mock()])
                        ]
                    )
                ),
                Article(uri="a2", number="2", number_normalized="002")
            ],
            references=[Mock(), Mock(), Mock()]
        )

        stats = content.get_statistics()

        self.assertEqual(stats["articles_count"], 2)
        self.assertEqual(stats["references_count"], 3)
        self.assertEqual(stats["hierarchy_levels"], 2)
        self.assertEqual(stats["languages"], 2)
        self.assertEqual(stats["paragraphs_count"], 1)
        self.assertEqual(stats["subpoints_count"], 2)

    def test_validation(self):
        """Test content validation"""
        # Valid content
        content = ExtractedContent(
            taxonomy=TaxonomyResult(sr_number="SR 101"),
            articles=[
                Article(uri="a1", number="1", number_normalized="001")
            ]
        )
        errors = content.validate()
        self.assertEqual(len(errors), 0)

        # Missing taxonomy
        content = ExtractedContent(taxonomy=None, articles=[])
        errors = content.validate()
        self.assertIn("Missing taxonomy data", errors)

        # Duplicate articles
        content = ExtractedContent(
            taxonomy=TaxonomyResult(sr_number="SR 101"),
            articles=[
                Article(uri="a1", number="1", number_normalized="001"),
                Article(uri="a2", number="1", number_normalized="001")
            ]
        )
        errors = content.validate()
        self.assertIn("Duplicate article numbers found", errors)


if __name__ == "__main__":
    unittest.main()