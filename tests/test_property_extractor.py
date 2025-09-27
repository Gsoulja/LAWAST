"""
Test Property Extractor Module

Tests for the FedlexPropertyExtractor class to ensure proper
extraction of all schema-required properties.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.property_extractor import (
    FedlexPropertyExtractor,
    extract_law_properties,
    extract_sr_from_taxonomy,
    extract_sr_from_uri
)


class TestFedlexPropertyExtractor:
    """Test the property extractor with real and mock Fedlex data"""

    @pytest.fixture
    def extractor(self):
        """Create an extractor instance"""
        return FedlexPropertyExtractor()

    @pytest.fixture
    def sr_101_data(self):
        """Load SR 101 (Bundesverfassung) test data"""
        json_path = Path('fedlex/eli/cc/1999/404.json')
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Minimal mock data if file doesn't exist
            return {
                "data": {
                    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404",
                    "type": ["ConsolidationAbstract", "Work"],
                    "attributes": {
                        "dateDocument": {"xsd:date": "1999-04-18"},
                        "dateEntryInForce": {"xsd:date": "2000-01-01"},
                        "basicAct": {"rdfs:Resource": "https://fedlex.data.admin.ch/eli/oc/1999/404"},
                        "typeDocument": {"rdfs:Resource": "https://fedlex.data.admin.ch/vocabulary/resource-type/10"}
                    },
                    "references": {
                        "isRealizedBy": [
                            "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
                            "https://fedlex.data.admin.ch/eli/cc/1999/404/fr"
                        ],
                        "inForceStatus": "https://fedlex.data.admin.ch/vocabulary/enforcement-status/0",
                        "classifiedByTaxonomyEntry": "https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4715"
                    }
                },
                "included": [
                    {
                        "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
                        "type": "Expression",
                        "attributes": {
                            "title": {"xsd:string": "Bundesverfassung der Schweizerischen Eidgenossenschaft"},
                            "titleShort": {"xsd:string": "BV"}
                        },
                        "references": {
                            "language": "http://publications.europa.eu/resource/authority/language/DEU"
                        }
                    },
                    {
                        "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/fr",
                        "type": "Expression",
                        "attributes": {
                            "title": {"xsd:string": "Constitution fédérale de la Confédération suisse"},
                            "titleShort": {"xsd:string": "Cst."}
                        },
                        "references": {
                            "language": "http://publications.europa.eu/resource/authority/language/FRA"
                        }
                    }
                ]
            }

    @pytest.fixture
    def historical_law_data(self):
        """Mock data for a historical (no longer in force) law"""
        return {
            "data": {
                "uri": "https://fedlex.data.admin.ch/eli/cc/I/271_271_445",
                "type": ["ConsolidationAbstract", "Work"],
                "attributes": {
                    "dateDocument": {"xsd:date": "1849-12-10"},
                    "dateEntryInForce": {"xsd:date": "1850-01-01"},
                    "dateNoLongerInForce": {"xsd:date": "1979-01-01"},
                    "basicAct": {"rdfs:Resource": "https://fedlex.data.admin.ch/eli/oc/I/271_271_445"},
                    "typeDocument": {"rdfs:Resource": "https://fedlex.data.admin.ch/vocabulary/resource-type/21"}
                },
                "references": {
                    "isRealizedBy": [
                        "https://fedlex.data.admin.ch/eli/cc/I/271_271_445/de",
                        "https://fedlex.data.admin.ch/eli/cc/I/271_271_445/fr",
                        "https://fedlex.data.admin.ch/eli/cc/I/271_271_445/it"
                    ],
                    "inForceStatus": "https://fedlex.data.admin.ch/vocabulary/enforcement-status/3",
                    "classifiedByTaxonomyEntry": "https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4849"
                }
            },
            "included": [
                {
                    "uri": "https://fedlex.data.admin.ch/eli/cc/I/271_271_445/de",
                    "type": "Expression",
                    "attributes": {
                        "title": {"xsd:string": "Bundesgesetz über die Niederlassungsbewilligung"}
                    },
                    "references": {
                        "language": "http://publications.europa.eu/resource/authority/language/DEU"
                    }
                }
            ]
        }

    def test_extract_law_properties_complete(self, extractor, sr_101_data):
        """Test extraction of all law properties"""
        props = extractor.extract_law_properties(sr_101_data)

        # Check required fields
        assert props['uri'] == "https://fedlex.data.admin.ch/eli/cc/1999/404"
        assert props['sr_number'] == '101'  # Should be extracted from taxonomy

        # Check multilingual titles
        assert props['title_de'] == "Bundesverfassung der Schweizerischen Eidgenossenschaft"
        assert props['title_fr'] == "Constitution fédérale de la Confédération suisse"

        # Check abbreviations
        assert props['abbreviation_de'] == "BV"
        assert props['abbreviation_fr'] == "Cst."

        # Check dates
        assert props['date_document'] == "1999-04-18"
        assert props['date_entry_in_force'] == "2000-01-01"
        assert props['date_no_longer_in_force'] is None  # Still in force
        assert props['date_modified'] is not None  # Should be generated

        # Check status
        assert props['in_force'] is True
        assert props['status'] == 'in_force'
        assert '/0' in props['in_force_status']

        # Check metadata
        assert props['type'] == 'Law'
        assert props['language'] == 'de'  # Primary language

        # Check AST properties
        assert props['ast_path'] == '/sr_101'
        assert props['ast_level'] == 5
        assert props['parent_id'] is None

    def test_extract_historical_law(self, extractor, historical_law_data):
        """Test extraction of historical law with dateNoLongerInForce"""
        props = extractor.extract_law_properties(historical_law_data)

        # Check dates
        assert props['date_document'] == "1849-12-10"
        assert props['date_entry_in_force'] == "1850-01-01"
        assert props['date_no_longer_in_force'] == "1979-01-01"

        # Check status
        assert props['in_force'] is False
        assert props['status'] == 'repealed'
        assert '/3' in props['in_force_status']

        # Check SR number extraction for historical format
        assert 'I/271_271_445' in props['sr_number'] or props['sr_number'] == ''

    def test_extract_multilingual_titles(self, extractor, sr_101_data):
        """Test extraction of titles in multiple languages"""
        included = sr_101_data.get('included', [])
        titles, abbreviations = extractor._extract_multilingual_titles(included)

        assert 'de' in titles
        assert 'fr' in titles
        assert titles['de'] == "Bundesverfassung der Schweizerischen Eidgenossenschaft"
        assert titles['fr'] == "Constitution fédérale de la Confédération suisse"

        assert abbreviations['de'] == "BV"
        assert abbreviations['fr'] == "Cst."

    def test_extract_dates(self, extractor, sr_101_data):
        """Test date extraction"""
        attrs = sr_101_data['data']['attributes']
        dates = extractor._extract_dates(attrs)

        assert dates['date_document'] == "1999-04-18"
        assert dates['date_entry_in_force'] == "2000-01-01"
        assert dates['date_no_longer_in_force'] is None

    def test_extract_status(self, extractor):
        """Test enforcement status extraction"""
        # Test in force
        refs = {'inForceStatus': 'https://fedlex.data.admin.ch/vocabulary/enforcement-status/0'}
        status = extractor._extract_status(refs)
        assert status['in_force'] is True
        assert status['status'] == 'in_force'

        # Test repealed
        refs = {'inForceStatus': 'https://fedlex.data.admin.ch/vocabulary/enforcement-status/3'}
        status = extractor._extract_status(refs)
        assert status['in_force'] is False
        assert status['status'] == 'repealed'

    def test_extract_sr_from_taxonomy(self, extractor):
        """Test SR number extraction from taxonomy URI"""
        # Known mapping
        sr = extractor.extract_sr_from_taxonomy(
            'https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4715'
        )
        assert sr == '101'

        # Unknown taxonomy
        sr = extractor.extract_sr_from_taxonomy(
            'https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/9999'
        )
        assert sr is None

    def test_detect_primary_language(self, extractor):
        """Test primary language detection"""
        # All languages present
        titles = {'de': 'German', 'fr': 'French', 'it': 'Italian'}
        lang = extractor._detect_primary_language(titles)
        assert lang == 'de'

        # Only French and Italian
        titles = {'fr': 'French', 'it': 'Italian'}
        lang = extractor._detect_primary_language(titles)
        assert lang == 'fr'

        # Only English
        titles = {'en': 'English'}
        lang = extractor._detect_primary_language(titles)
        assert lang == 'en'

    def test_generate_ast_properties(self, extractor):
        """Test AST property generation"""
        ast = extractor._generate_ast_properties('101', 'law')
        assert ast['ast_path'] == '/sr_101'
        assert ast['ast_level'] == 5
        assert ast['parent_id'] is None

        ast = extractor._generate_ast_properties('101', 'article')
        assert ast['ast_level'] == 6

        ast = extractor._generate_ast_properties('101', 'paragraph')
        assert ast['ast_level'] == 7


if __name__ == '__main__':
    pytest.main([__file__, '-v'])