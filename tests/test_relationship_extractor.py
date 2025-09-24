"""
Tests for relationship extraction components
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path

# Add project to path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extractors.uri_resolver import URIResolver
from src.extractors.relationship_extractor import RelationshipExtractor
from src.extractors.version_chain_builder import VersionChainBuilder
from src.extractors.relationship_buffer import RelationshipBuffer
from src.config.extractor_config import ExtractorConfig


class TestURIResolver(unittest.TestCase):
    """Test URI resolver functionality"""

    def setUp(self):
        self.resolver = URIResolver()

    def test_normalize_uri(self):
        """Test URI normalization"""
        # Test removing trailing slashes
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/"
        normalized = self.resolver.normalize_uri(uri)
        self.assertEqual(normalized, "https://fedlex.data.admin.ch/eli/cc/1999/404")

        # Test protocol normalization
        uri = "http://fedlex.data.admin.ch/eli/cc/1999/404"
        normalized = self.resolver.normalize_uri(uri)
        self.assertEqual(normalized, "https://fedlex.data.admin.ch/eli/cc/1999/404")

    def test_extract_language_code(self):
        """Test language code extraction"""
        # From path
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/de"
        lang = self.resolver.extract_language_code(uri)
        self.assertEqual(lang, "de")

        # From version URI
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/fr"
        lang = self.resolver.extract_language_code(uri)
        self.assertEqual(lang, "fr")

        # From authority URI
        uri = "http://publications.europa.eu/resource/authority/language/ITA"
        lang = self.resolver.extract_language_code(uri)
        self.assertEqual(lang, "it")

    def test_extract_format(self):
        """Test format extraction"""
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/html"
        fmt = self.resolver.extract_format(uri)
        self.assertEqual(fmt, "html")

        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/fr/pdf-a"
        fmt = self.resolver.extract_format(uri)
        self.assertEqual(fmt, "pdf-a")

    def test_get_parent_law_uri(self):
        """Test parent law extraction from version URI"""
        version_uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101"
        parent = self.resolver.get_parent_law_uri(version_uri)
        self.assertEqual(parent, "https://fedlex.data.admin.ch/eli/cc/1999/404")

        # With language
        version_uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de"
        parent = self.resolver.get_parent_law_uri(version_uri)
        self.assertEqual(parent, "https://fedlex.data.admin.ch/eli/cc/1999/404")

    def test_extract_sr_number(self):
        """Test SR number extraction"""
        # Standard format
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404"
        sr = self.resolver.extract_sr_number(uri)
        self.assertEqual(sr, "SR 1999.404")

        # Roman numerals
        uri = "https://fedlex.data.admin.ch/eli/cc/I/271_271_445"
        sr = self.resolver.extract_sr_number(uri)
        self.assertEqual(sr, "SR I 271")

        # Double underscore
        uri = "https://fedlex.data.admin.ch/eli/cc/1959/__1811"
        sr = self.resolver.extract_sr_number(uri)
        self.assertEqual(sr, "Special 1811")

    def test_is_version_uri(self):
        """Test version URI detection"""
        # Version URI
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101"
        self.assertTrue(self.resolver.is_version_uri(uri))

        # Law URI (not a version)
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404"
        self.assertFalse(self.resolver.is_version_uri(uri))

    def test_extract_date_from_version(self):
        """Test date extraction from version URI"""
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101"
        date = self.resolver.extract_date_from_version(uri)
        self.assertEqual(date, "2024-01-01")

    def test_get_law_type(self):
        """Test law type detection"""
        test_cases = [
            ("https://fedlex.data.admin.ch/eli/cc/1999/404", "cc"),
            ("https://fedlex.data.admin.ch/eli/oc/1999/404", "oc"),
            ("https://fedlex.data.admin.ch/eli/fga/1999/404", "fga"),
            ("https://fedlex.data.admin.ch/eli/treaty/1999/404", "treaty"),
        ]

        for uri, expected_type in test_cases:
            law_type = self.resolver.get_law_type(uri)
            self.assertEqual(law_type, expected_type)


class TestRelationshipExtractor(unittest.TestCase):
    """Test relationship extraction"""

    def setUp(self):
        self.mock_builder = Mock()
        self.resolver = URIResolver()
        self.extractor = RelationshipExtractor(self.mock_builder, self.resolver)

    def test_extract_from_consolidation_abstract(self):
        """Test extraction from ConsolidationAbstract"""
        json_data = {
            "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404",
            "type": ["ConsolidationAbstract", "Work"],
            "references": {
                "isRealizedBy": [
                    "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
                    "https://fedlex.data.admin.ch/eli/cc/1999/404/fr",
                    "https://fedlex.data.admin.ch/eli/cc/1999/404/it"
                ]
            }
        }

        full_data = {"data": json_data, "included": []}

        relationships = self.extractor.extract_from_consolidation_abstract(json_data, full_data)

        # Should create EXPRESSED_IN relationships
        self.assertEqual(len(relationships), 3)
        for rel in relationships:
            self.assertEqual(rel[2], "EXPRESSED_IN")  # Relationship type
            self.assertTrue(rel[0].endswith("/404"))  # From URI (law)
            self.assertIn("/404/", rel[1])  # To URI (language expression)

    def test_extract_from_version(self):
        """Test extraction from Consolidation version"""
        json_data = {
            "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101",
            "type": ["Consolidation", "Work"],
            "attributes": {
                "isMemberOf": {
                    "rdfs:Resource": "https://fedlex.data.admin.ch/eli/cc/1999/404"
                }
            },
            "references": {
                "isRealizedBy": [
                    "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de",
                    "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/fr"
                ]
            }
        }

        full_data = {
            "data": json_data,
            "included": [
                {
                    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de",
                    "type": "Expression",
                    "references": {
                        "isEmbodiedBy": [
                            "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/html",
                            "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de/pdf"
                        ]
                    }
                }
            ]
        }

        relationships = self.extractor.extract_from_version(json_data, full_data)

        # Should create HAS_VERSION, EXPRESSED_IN, and MANIFESTED_AS relationships
        rel_types = [rel[2] for rel in relationships]
        self.assertIn("HAS_VERSION", rel_types)
        self.assertIn("EXPRESSED_IN", rel_types)
        self.assertIn("MANIFESTED_AS", rel_types)

    def test_extract_from_act(self):
        """Test extraction from Act"""
        json_data = {
            "uri": "https://fedlex.data.admin.ch/eli/oc/1999/500",
            "type": ["Act", "Work"],
            "references": {
                "isRealizedBy": [
                    "https://fedlex.data.admin.ch/eli/oc/1999/500/de"
                ]
            }
        }

        full_data = {
            "data": json_data,
            "facets": {
                "impacts": [
                    "https://fedlex.data.admin.ch/eli/cc/1999/404",
                    "https://fedlex.data.admin.ch/eli/cc/1999/405"
                ]
            }
        }

        relationships = self.extractor.extract_from_act(json_data, full_data)

        # Should create AMENDS and EXPRESSED_IN relationships
        rel_types = [rel[2] for rel in relationships]
        self.assertIn("AMENDS", rel_types)
        self.assertIn("EXPRESSED_IN", rel_types)

        # Check AMENDS relationships
        amends_rels = [rel for rel in relationships if rel[2] == "AMENDS"]
        self.assertEqual(len(amends_rels), 2)  # Two impacted laws

    def test_buffer_and_flush(self):
        """Test relationship buffering and flushing"""
        # Create config with node validation disabled
        config = ExtractorConfig(validate_nodes=False, buffer_size=10)
        self.extractor = RelationshipExtractor(self.mock_builder, self.resolver, config)

        # Mock the batch_create_relationships method
        self.mock_builder.batch_create_relationships.return_value = 3

        # Add relationships to buffer
        self.extractor.add_relationship("uri1", "uri2", "TEST_REL", None)
        self.extractor.add_relationship("uri3", "uri4", "TEST_REL", None)
        self.extractor.add_relationship("uri5", "uri6", "TEST_REL", None)

        # Buffer should have relationships
        self.assertEqual(self.extractor.stats["TEST_REL"], 3)

        # Flush buffer
        count = self.extractor.flush_relationships()
        self.assertEqual(count, 3)

        # Mock method should have been called
        self.mock_builder.batch_create_relationships.assert_called_once()


class TestVersionChainBuilder(unittest.TestCase):
    """Test version chain building"""

    def setUp(self):
        self.mock_builder = Mock()
        self.mock_connection = Mock()

        with patch('src.extractors.version_chain_builder.get_connection', return_value=self.mock_connection):
            self.chain_builder = VersionChainBuilder(self.mock_builder)

    def test_build_chain_for_law(self):
        """Test building version chain for a single law"""
        # Mock version data
        mock_versions = [
            {"uri": "uri/20200101", "date_start": "2020-01-01", "date_end": "2020-12-31"},
            {"uri": "uri/20210101", "date_start": "2021-01-01", "date_end": "2021-12-31"},
            {"uri": "uri/20220101", "date_start": "2022-01-01", "date_end": None}
        ]

        self.mock_connection.execute_read.return_value = mock_versions
        self.mock_connection.execute_write.return_value = [{"s": {}}]

        result = self.chain_builder.build_chain_for_law("test_law_uri")

        self.assertTrue(result['success'])
        self.assertEqual(result['versions_found'], 3)
        self.assertEqual(result['relationships_created'], 2)  # 3 versions = 2 SUPERSEDES

    def test_validate_chains(self):
        """Test chain validation"""
        # Mock no issues
        self.mock_connection.execute_read.return_value = []

        validation = self.chain_builder.validate_chains()

        self.assertTrue(validation['valid'])
        self.assertEqual(len(validation['issues']), 0)


class TestRelationshipBuffer(unittest.TestCase):
    """Test RelationshipBuffer class"""

    def setUp(self):
        self.mock_builder = Mock()
        self.mock_builder.connection = Mock()
        self.config = ExtractorConfig(buffer_size=3, validate_nodes=False)
        self.buffer = RelationshipBuffer(self.mock_builder, self.config)

    def test_add_and_auto_flush(self):
        """Test that buffer auto-flushes when reaching size limit"""
        self.mock_builder.batch_create_relationships.return_value = 3

        # Add relationships up to buffer size
        self.buffer.add("uri1", "uri2", "TEST", None)
        self.buffer.add("uri3", "uri4", "TEST", None)

        # Should not flush yet
        self.mock_builder.batch_create_relationships.assert_not_called()

        # This should trigger auto-flush
        self.buffer.add("uri5", "uri6", "TEST", None)
        self.mock_builder.batch_create_relationships.assert_called_once()

    def test_node_validation(self):
        """Test node existence validation"""
        self.config.validate_nodes = True
        self.config.skip_missing_nodes = True
        self.config.buffer_size = 10  # Increase buffer size to avoid auto-flush
        buffer = RelationshipBuffer(self.mock_builder, self.config)

        # Mock node existence check
        buffer._check_nodes_exist = Mock(return_value={"uri1", "uri2"})

        # Add relationships
        buffer.add("uri1", "uri2", "TEST", None)  # Valid
        buffer.add("uri1", "uri3", "TEST", None)  # Invalid - uri3 missing
        buffer.add("uri4", "uri5", "TEST", None)  # Invalid - both missing

        # Force flush - mock should return an integer
        self.mock_builder.batch_create_relationships = Mock(return_value=1)
        count = buffer.flush(force=True)

        # Only 1 valid relationship should be created
        self.assertEqual(count, 1)
        self.assertEqual(len(buffer.failed_relationships), 2)

    def test_retry_logic(self):
        """Test retry logic on flush failure"""
        self.config.max_retries = 3
        self.config.retry_delay = 0.01
        buffer = RelationshipBuffer(self.mock_builder, self.config)

        # Mock failure then success
        self.mock_builder.batch_create_relationships.side_effect = [
            Exception("Failed"),
            Exception("Failed again"),
            2  # Success on third try
        ]

        buffer.add("uri1", "uri2", "TEST", None)
        buffer.add("uri3", "uri4", "TEST", None)

        count = buffer.flush(force=True)
        self.assertEqual(count, 2)
        self.assertEqual(self.mock_builder.batch_create_relationships.call_count, 3)


class TestExtractorConfig(unittest.TestCase):
    """Test configuration management"""

    def test_default_config(self):
        """Test default configuration values"""
        config = ExtractorConfig()
        self.assertEqual(config.batch_size, 5000)
        self.assertEqual(config.buffer_size, 5000)
        self.assertEqual(config.max_buffer_size, 10000)
        self.assertTrue(config.enable_transactions)
        self.assertTrue(config.validate_nodes)

    def test_from_env(self):
        """Test loading configuration from environment"""
        with patch.dict('os.environ', {
            'EXTRACTOR_BATCH_SIZE': '1000',
            'EXTRACTOR_VALIDATE_NODES': 'false',
            'EXTRACTOR_MAX_RETRIES': '5'
        }):
            config = ExtractorConfig.from_env()
            self.assertEqual(config.batch_size, 1000)
            self.assertFalse(config.validate_nodes)
            self.assertEqual(config.max_retries, 5)


class TestTransactionManagement(unittest.TestCase):
    """Test transaction handling in RelationshipExtractor"""

    def setUp(self):
        self.mock_builder = Mock()
        self.config = ExtractorConfig(enable_transactions=True)
        self.extractor = RelationshipExtractor(self.mock_builder, None, self.config)

    @patch('src.extractors.relationship_extractor.Path')
    def test_transaction_rollback_on_error(self, mock_path):
        """Test that transaction rolls back on error"""
        # Setup mock files
        mock_path.return_value.rglob.return_value = ['file1.json', 'file2.json']

        # Mock extract_from_file to raise error on second file
        self.extractor.extract_from_file = Mock(side_effect=[
            [("uri1", "uri2", "TEST", None)],
            Exception("Processing failed")
        ])

        # Should raise exception and clear buffer
        with self.assertRaises(Exception):
            self.extractor.process_directory("/test")

        # Buffer should be cleared
        self.assertEqual(len(self.extractor.buffer.buffer), 0)


if __name__ == "__main__":
    unittest.main()