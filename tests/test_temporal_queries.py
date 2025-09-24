"""
Test suite for temporal query functionality in VersionChainBuilder
"""
import unittest
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.version_chain_builder import VersionChainBuilder
from src.data_access.neo4j_connection import Neo4jConnectionManager


class TestTemporalQueries(unittest.TestCase):
    """Test temporal query methods in VersionChainBuilder"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_connection = MagicMock(spec=Neo4jConnectionManager)
        self.version_builder = VersionChainBuilder()
        self.version_builder.connection = self.mock_connection

    def test_get_version_at_date_basic(self):
        """Test basic version lookup at specific date"""
        # Mock response
        mock_version = {
            'uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404/20240101',
            'date_applicable': '2024-01-01T00:00:00',
            'date_end_applicable': None,
            'version_number': '20240101',
            'parent_law_uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404'
        }
        self.mock_connection.execute_query.return_value = [mock_version]

        # Test query
        law_uri = 'https://fedlex.data.admin.ch/eli/cc/1999/404'
        query_date = datetime(2024, 6, 15)
        
        result = self.version_builder.get_version_at_date(law_uri, query_date)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['uri'], mock_version['uri'])
        self.assertEqual(result['version_number'], '20240101')
        
        # Verify query was called correctly
        self.mock_connection.execute_query.assert_called_once()

    def test_get_version_at_date_no_version_found(self):
        """Test when no version is found for the date"""
        self.mock_connection.execute_query.return_value = []

        law_uri = 'https://fedlex.data.admin.ch/eli/cc/1999/404'
        query_date = datetime(1800, 1, 1)  # Before any versions
        
        result = self.version_builder.get_version_at_date(law_uri, query_date)
        
        self.assertIsNone(result)

    def test_get_changes_between_dates(self):
        """Test change detection between two dates"""
        # Mock response with changes
        mock_changes = [
            {
                'law_uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404',
                'sr_number': '101',
                'version_uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404/20240101',
                'change_date': '2024-01-01T00:00:00',
                'change_type': 'VERSION_ACTIVATED',
                'version_number': '20240101'
            },
            {
                'law_uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404',
                'sr_number': '101',
                'version_uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404/20231201',
                'change_date': '2024-01-01T00:00:00',
                'change_type': 'VERSION_ENDED',
                'version_number': '20231201'
            }
        ]
        self.mock_connection.execute_query.return_value = mock_changes

        start_date = datetime(2023, 12, 31)
        end_date = datetime(2024, 1, 31)
        
        result = self.version_builder.get_changes_between_dates(start_date, end_date)
        
        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['change_type'], 'VERSION_ACTIVATED')
        self.assertEqual(result[1]['change_type'], 'VERSION_ENDED')

    def test_get_legal_state_at_date(self):
        """Test reconstruction of legal state at specific date"""
        # Mock response with active versions
        mock_state = [
            {
                'law_uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404',
                'sr_number': '101',
                'law_title': 'Bundesverfassung',
                'version_uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404/20240101',
                'version_start': '2024-01-01T00:00:00',
                'version_end': None,
                'version_number': '20240101'
            }
        ]
        self.mock_connection.execute_query.return_value = mock_state

        query_date = datetime(2024, 6, 15)
        
        result = self.version_builder.get_legal_state_at_date(query_date)
        
        # Assertions
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['sr_number'], '101')
        self.assertEqual(result[0]['law_title'], 'Bundesverfassung')

    def test_validate_date_range_valid(self):
        """Test date range validation with valid range"""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2024, 1, 1)
        
        result = self.version_builder.validate_date_range(start_date, end_date)
        
        self.assertTrue(result)

    def test_validate_date_range_invalid_order(self):
        """Test date range validation with invalid order"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2020, 1, 1)  # Before start date
        
        result = self.version_builder.validate_date_range(start_date, end_date)
        
        self.assertFalse(result)

    def test_validate_date_range_too_early(self):
        """Test date range validation with date before Swiss federal system"""
        start_date = datetime(1800, 1, 1)  # Before 1848
        end_date = datetime(2024, 1, 1)
        
        result = self.version_builder.validate_date_range(start_date, end_date)
        
        self.assertFalse(result)

    def test_validate_date_range_too_large(self):
        """Test date range validation with overly large range"""
        start_date = datetime(1900, 1, 1)
        end_date = datetime(2100, 1, 1)  # 200 years > 50 year limit
        
        result = self.version_builder.validate_date_range(start_date, end_date)
        
        self.assertFalse(result)

    def test_parse_query_date_datetime(self):
        """Test date parsing with datetime input"""
        input_date = datetime(2024, 1, 1)
        
        result = self.version_builder.parse_query_date(input_date)
        
        self.assertEqual(result, input_date)

    def test_parse_query_date_iso_string(self):
        """Test date parsing with ISO string"""
        input_date = "2024-01-01T00:00:00"
        expected = datetime(2024, 1, 1)
        
        result = self.version_builder.parse_query_date(input_date)
        
        self.assertEqual(result, expected)

    def test_parse_query_date_simple_string(self):
        """Test date parsing with simple date string"""
        input_date = "2024-01-01"
        expected = datetime(2024, 1, 1)
        
        result = self.version_builder.parse_query_date(input_date)
        
        self.assertEqual(result, expected)

    def test_parse_query_date_swiss_format(self):
        """Test date parsing with Swiss date format"""
        input_date = "01.01.2024"
        expected = datetime(2024, 1, 1)
        
        result = self.version_builder.parse_query_date(input_date)
        
        self.assertEqual(result, expected)

    def test_parse_query_date_invalid(self):
        """Test date parsing with invalid input"""
        input_date = "invalid-date"
        
        with self.assertRaises(ValueError):
            self.version_builder.parse_query_date(input_date)

    def test_get_date_boundaries(self):
        """Test getting date boundaries for a law"""
        # Mock response
        mock_boundaries = {
            'earliest': '2020-01-01T00:00:00Z',
            'latest': '2024-01-01T00:00:00Z'
        }
        self.mock_connection.execute_query.return_value = [mock_boundaries]

        law_uri = 'https://fedlex.data.admin.ch/eli/cc/1999/404'
        
        result = self.version_builder.get_date_boundaries(law_uri)
        
        # Assertions
        self.assertIsNotNone(result['earliest'])
        self.assertIsNotNone(result['latest'])
        self.assertEqual(result['earliest'].year, 2020)
        self.assertEqual(result['latest'].year, 2024)

    def test_error_handling_database_exception(self):
        """Test error handling when database query fails"""
        self.mock_connection.execute_query.side_effect = Exception("Database error")

        law_uri = 'https://fedlex.data.admin.ch/eli/cc/1999/404'
        query_date = datetime(2024, 1, 1)
        
        # Should return None/empty list gracefully
        result = self.version_builder.get_version_at_date(law_uri, query_date)
        self.assertIsNone(result)
        
        changes = self.version_builder.get_changes_between_dates(query_date, query_date)
        self.assertEqual(changes, [])
        
        state = self.version_builder.get_legal_state_at_date(query_date)
        self.assertEqual(state, [])


if __name__ == "__main__":
    unittest.main()
