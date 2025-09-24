"""
Tests for the Fedlex JSON Parser
"""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.data_access.fedlex_parser import FedlexParser
from src.extractors.law_extractor import LawExtractor
from src.extractors.version_extractor import VersionExtractor
from src.extractors.act_extractor import ActExtractor
from src.extractors.base_extractor import ExtractionResult


class TestFedlexParser:
    """Test the main FedlexParser class"""

    @pytest.fixture
    def parser(self):
        """Create a FedlexParser instance for testing"""
        with patch('src.data_access.fedlex_parser.GraphBuilder'):
            with patch('src.data_access.fedlex_parser.BatchProcessor'):
                return FedlexParser(batch_size=10)

    @pytest.fixture
    def sample_law_json(self):
        """Sample ConsolidationAbstract JSON data"""
        return {
            "data": {
                "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404",
                "type": ["ConsolidationAbstract", "Work"],
                "attributes": {
                    "dateDocument": {"xsd:date": "1999-04-18"},
                    "dateEntryInForce": {"xsd:date": "2000-01-01"}
                },
                "references": {
                    "isRealizedBy": [
                        "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
                        "https://fedlex.data.admin.ch/eli/cc/1999/404/fr"
                    ]
                }
            },
            "included": [
                {
                    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
                    "type": "Expression",
                    "attributes": {
                        "title": {"xsd:string": "Bundesverfassung"}
                    },
                    "references": {
                        "language": "http://publications.europa.eu/resource/authority/language/DEU"
                    }
                }
            ]
        }

    @pytest.fixture
    def sample_version_json(self):
        """Sample Version JSON data"""
        return {
            "data": {
                "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101",
                "type": ["Consolidation"],
                "attributes": {
                    "dateApplicability": {"xsd:date": "2024-01-01"},
                    "dateEndApplicability": {"xsd:date": "2024-03-02"}
                },
                "references": {
                    "isRealizedBy": [
                        "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de"
                    ]
                }
            }
        }

    @pytest.fixture
    def sample_act_json(self):
        """Sample Act JSON data"""
        return {
            "data": {
                "uri": "https://fedlex.data.admin.ch/eli/oc/2024/500",
                "type": ["Act"],
                "attributes": {
                    "datePublication": {"xsd:date": "2024-09-15"}
                },
                "references": {
                    "consolidationAbstract": [
                        "https://fedlex.data.admin.ch/eli/cc/1999/404"
                    ]
                }
            }
        }

    def test_initialization(self, parser):
        """Test parser initialization"""
        assert parser.batch_size == 10
        assert parser.extractors is not None
        assert 'law' in parser.extractors
        assert 'version' in parser.extractors
        assert 'act' in parser.extractors

    def test_stream_json_file_small(self, parser, sample_law_json):
        """Test streaming small JSON files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_law_json, f)
            temp_path = Path(f.name)
        
        try:
            result = parser._stream_json_file(temp_path)
            assert result is not None
            assert result['data']['uri'] == sample_law_json['data']['uri']
        finally:
            temp_path.unlink()

    def test_extract_entities_law(self, parser, sample_law_json):
        """Test entity extraction for ConsolidationAbstract"""
        with patch.object(parser.extractors['law'], 'extract') as mock_extract:
            mock_result = ExtractionResult()
            mock_result.nodes = [{'type': 'Law', 'uri': 'test'}]
            mock_extract.return_value = mock_result
            
            results = parser._extract_entities(sample_law_json, 'test.json')
            
            assert len(results) == 1
            mock_extract.assert_called_once()

    def test_extract_entities_version(self, parser, sample_version_json):
        """Test entity extraction for Version"""
        with patch.object(parser.extractors['version'], 'extract') as mock_extract:
            mock_result = ExtractionResult()
            mock_result.nodes = [{'type': 'Version', 'uri': 'test'}]
            mock_extract.return_value = mock_result
            
            results = parser._extract_entities(sample_version_json, 'test.json')
            
            assert len(results) == 1
            mock_extract.assert_called_once()

    def test_extract_entities_act(self, parser, sample_act_json):
        """Test entity extraction for Act"""
        with patch.object(parser.extractors['act'], 'extract') as mock_extract:
            mock_result = ExtractionResult()
            mock_result.nodes = [{'type': 'Act', 'uri': 'test'}]
            mock_extract.return_value = mock_result
            
            results = parser._extract_entities(sample_act_json, 'test.json')
            
            assert len(results) == 1
            mock_extract.assert_called_once()

    def test_parse_file_success(self, parser, sample_law_json):
        """Test successful file parsing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_law_json, f)
            temp_path = Path(f.name)
        
        try:
            with patch.object(parser, '_create_nodes', return_value=1):
                with patch.object(parser, '_create_relationships', return_value=0):
                    result = parser.parse_file(temp_path)
                    
                    assert result['success'] is True
                    assert result['nodes_created'] == 1
                    assert result['relationships_created'] == 0
        finally:
            temp_path.unlink()

    def test_parse_file_invalid_json(self, parser):
        """Test parsing invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = Path(f.name)
        
        try:
            result = parser.parse_file(temp_path)
            assert result['success'] is False
            assert len(result['errors']) > 0
        finally:
            temp_path.unlink()

    def test_find_json_files(self, parser):
        """Test finding JSON files in directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "test1.json").touch()
            (temp_path / "test2.json").touch()
            (temp_path / "test.txt").touch()  # Should be ignored
            
            # Create subdirectory with JSON
            subdir = temp_path / "subdir"
            subdir.mkdir()
            (subdir / "test3.json").touch()
            
            files = parser._find_json_files(temp_path)
            
            assert len(files) == 3
            assert all(f.suffix == '.json' for f in files)

    @patch('src.data_access.fedlex_parser.os.walk')
    def test_process_directory(self, mock_walk, parser):
        """Test directory processing"""
        # Mock os.walk to return test files
        mock_walk.return_value = [
            ('/test', [], ['file1.json', 'file2.json'])
        ]
        
        with patch.object(parser.batch_processor, 'process_files') as mock_process:
            mock_checkpoint = Mock()
            mock_checkpoint.processed_files = 2
            mock_checkpoint.failed_files = 0
            mock_checkpoint.total_files = 2
            mock_checkpoint.statistics = {}
            mock_checkpoint.errors = []
            mock_process.return_value = mock_checkpoint
            
            result = parser.process_directory(Path('/test'))
            
            assert result['files_processed'] == 2
            assert result['files_failed'] == 0
            mock_process.assert_called_once()


class TestLawExtractor:
    """Test the LawExtractor class"""

    @pytest.fixture
    def extractor(self):
        return LawExtractor()

    def test_sr_number_extraction_standard(self, extractor):
        """Test SR number extraction for standard format"""
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404"
        sr_number = extractor._extract_sr_number(uri)
        assert sr_number == "SR 1999.404"

    def test_sr_number_extraction_roman(self, extractor):
        """Test SR number extraction for Roman numerals"""
        uri = "https://fedlex.data.admin.ch/eli/cc/I/271_271_445"
        sr_number = extractor._extract_sr_number(uri)
        assert sr_number == "SR I 271"

    def test_sr_number_extraction_double_underscore(self, extractor):
        """Test SR number extraction for double underscore format"""
        uri = "https://fedlex.data.admin.ch/eli/cc/1959/__1811"
        sr_number = extractor._extract_sr_number(uri)
        assert sr_number == "Special 1811"

    def test_sr_number_extraction_multi_part(self, extractor):
        """Test SR number extraction for multi-part numbers"""
        uri = "https://fedlex.data.admin.ch/eli/cc/271_271_445"
        sr_number = extractor._extract_sr_number(uri)
        assert sr_number == "SR 271.271"

    def test_language_placeholder_handling(self, extractor):
        """Test language placeholder detection"""
        assert extractor._handle_language_placeholder("nur ital.") is None
        assert extractor._handle_language_placeholder("seulement en italien") is None
        assert extractor._handle_language_placeholder("Normal title") == "Normal title"
        assert extractor._handle_language_placeholder("") is None

    def test_date_parsing(self, extractor):
        """Test Fedlex date parsing"""
        # Test dict format
        date_obj = {"xsd:date": "2024-01-01"}
        result = extractor._parse_fedlex_date(date_obj)
        assert result == datetime(2024, 1, 1)
        
        # Test string format
        result = extractor._parse_fedlex_date("2024-01-01")
        assert result == datetime(2024, 1, 1)
        
        # Test invalid format
        result = extractor._parse_fedlex_date("invalid")
        assert result is None

    def test_in_force_status_determination(self, extractor):
        """Test in-force status determination"""
        # Test with dateNoLongerInForce
        attrs_not_in_force = {"dateNoLongerInForce": {"xsd:date": "2020-01-01"}}
        assert extractor._determine_in_force_status(attrs_not_in_force) is False
        
        # Test with enforcement status
        attrs_status = {
            "references": {
                "inForceStatus": "https://fedlex.data.admin.ch/vocabulary/enforcement-status/3"
            }
        }
        assert extractor._determine_in_force_status(attrs_status) is False
        
        # Test normal case
        attrs_normal = {"dateDocument": {"xsd:date": "2024-01-01"}}
        assert extractor._determine_in_force_status(attrs_normal) is True

    def test_extract_consolidation_abstract(self, extractor):
        """Test extraction of ConsolidationAbstract"""
        json_data = {
            "data": {
                "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404",
                "type": ["ConsolidationAbstract", "Work"],
                "attributes": {
                    "dateDocument": {"xsd:date": "1999-04-18"},
                    "dateEntryInForce": {"xsd:date": "2000-01-01"}
                },
                "references": {
                    "isRealizedBy": [
                        "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
                        "https://fedlex.data.admin.ch/eli/cc/1999/404/fr"
                    ]
                }
            },
            "included": [
                {
                    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
                    "type": "Expression",
                    "attributes": {
                        "title": {"xsd:string": "Bundesverfassung"}
                    },
                    "references": {
                        "language": "http://publications.europa.eu/resource/authority/language/DEU"
                    }
                }
            ]
        }
        
        result = extractor.extract(json_data, "test.json")
        
        assert len(result.nodes) > 0
        law_node = next((n for n in result.nodes if n['type'] == 'Law'), None)
        assert law_node is not None
        assert law_node['uri'] == "https://fedlex.data.admin.ch/eli/cc/1999/404"
        assert law_node['sr_number'] == "SR 1999.404"
        assert law_node['title_de'] == "Bundesverfassung"


class TestVersionExtractor:
    """Test the VersionExtractor class"""

    @pytest.fixture
    def extractor(self):
        return VersionExtractor()

    def test_parent_law_uri_extraction(self, extractor):
        """Test parent law URI extraction from version URI"""
        version_uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101"
        parent_uri = extractor._extract_parent_law_uri(version_uri)
        assert parent_uri == "https://fedlex.data.admin.ch/eli/cc/1999/404"
        
        # Test with language suffix
        version_uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de"
        parent_uri = extractor._extract_parent_law_uri(version_uri)
        assert parent_uri == "https://fedlex.data.admin.ch/eli/cc/1999/404"

    def test_date_extraction_from_uri(self, extractor):
        """Test date extraction from URI"""
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101"
        date = extractor._extract_date_from_uri(uri)
        assert date == datetime(2024, 1, 1)
        
        # Test invalid date
        uri = "https://fedlex.data.admin.ch/eli/cc/1999/404/invalid"
        date = extractor._extract_date_from_uri(uri)
        assert date is None

    def test_language_extraction_from_uri(self, extractor):
        """Test language code extraction from URI"""
        assert extractor._extract_language_from_uri("test/de") == "DE"
        assert extractor._extract_language_from_uri("test/fr") == "FR"
        assert extractor._extract_language_from_uri("test/it") == "IT"
        assert extractor._extract_language_from_uri("test/rm") == "RM"
        assert extractor._extract_language_from_uri("test/en") == "EN"
        assert extractor._extract_language_from_uri("test/xx") is None


class TestActExtractor:
    """Test the ActExtractor class"""

    @pytest.fixture
    def extractor(self):
        return ActExtractor()

    def test_memorial_information_extraction(self, extractor):
        """Test memorial information extraction"""
        attributes = {
            "memorialNumber": "2024-500",
            "memorialPage": "123",
            "memorialYear": "2024",
            "volume": "Vol. 1"
        }
        
        memorial_info = extractor._extract_memorial_information(attributes)
        
        assert memorial_info["memorial_number"] == "2024-500"
        assert memorial_info["memorial_page"] == "123"
        assert memorial_info["memorial_year"] == "2024"
        assert memorial_info["volume"] == "Vol. 1"

    def test_impacted_laws_extraction(self, extractor):
        """Test extraction of impacted laws"""
        references = {
            "consolidationAbstract": [
                "https://fedlex.data.admin.ch/eli/cc/1999/404",
                "https://fedlex.data.admin.ch/eli/cc/2000/500"
            ]
        }
        
        included = []
        
        impacted_laws = extractor._extract_impacted_laws(references, included)
        
        assert len(impacted_laws) == 2
        assert "https://fedlex.data.admin.ch/eli/cc/1999/404" in impacted_laws
        assert "https://fedlex.data.admin.ch/eli/cc/2000/500" in impacted_laws

    def test_publication_series_determination(self, extractor):
        """Test publication series determination"""
        # Test OC
        oc_uri = "https://fedlex.data.admin.ch/eli/oc/2024/500"
        series = extractor._determine_publication_series(oc_uri, {})
        assert series == "AS"
        
        # Test FGA
        fga_uri = "https://fedlex.data.admin.ch/eli/fga/2024/500"
        series = extractor._determine_publication_series(fga_uri, {})
        assert series == "FF"
        
        # Test unknown
        unknown_uri = "https://fedlex.data.admin.ch/eli/other/2024/500"
        series = extractor._determine_publication_series(unknown_uri, {})
        assert series == "Unknown"


class TestExtractionResult:
    """Test the ExtractionResult class"""

    def test_add_node(self):
        """Test adding nodes to extraction result"""
        result = ExtractionResult()
        
        node = {'type': 'Law', 'uri': 'test'}
        result.add_node(node)
        
        assert len(result.nodes) == 1
        assert result.statistics['Law_nodes'] == 1

    def test_add_relationship(self):
        """Test adding relationships to extraction result"""
        result = ExtractionResult()
        
        result.add_relationship('uri1', 'uri2', 'HAS_VERSION')
        
        assert len(result.relationships) == 1
        assert result.statistics['HAS_VERSION_relationships'] == 1

    def test_add_error(self):
        """Test adding errors to extraction result"""
        result = ExtractionResult()
        
        result.add_error("Test error")
        
        assert len(result.errors) == 1
        assert "Test error" in result.errors
