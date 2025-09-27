"""
Comprehensive tests for LAWAST Graph Builder

Tests all improvements made in TASK-014.1:
- Subpoint node creation
- Property alignment fixes
- SR number resolution
- Hierarchical structure nodes
- Version relationships
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
from datetime import datetime

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.property_extractor import FedlexPropertyExtractor
from src.extractors.sr_resolver import SRNumberResolver
from src.data_access.schema_mapper import SchemaPropertyMapper, validate_node


class TestSRNumberResolver(unittest.TestCase):
    """Test SR number resolution functionality"""

    def setUp(self):
        self.resolver = SRNumberResolver()

    def test_extract_from_uri(self):
        """Test SR extraction from various URI formats"""
        # Known mappings
        self.assertEqual(self.resolver.extract_from_uri('/eli/cc/1999/404'), '101')
        self.assertEqual(self.resolver.extract_from_uri('/eli/cc/1907/252'), '210')

        # Unknown URIs
        self.assertIsNone(self.resolver.extract_from_uri('/eli/cc/2099/999'))

    def test_extract_from_taxonomy(self):
        """Test SR extraction from taxonomy references"""
        self.assertEqual(
            self.resolver.extract_from_taxonomy('https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4715'),
            '101'
        )
        self.assertEqual(
            self.resolver.extract_from_taxonomy('https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/5274'),
            '210'
        )

    def test_extract_from_title(self):
        """Test SR extraction from law titles"""
        # Direct SR mention
        self.assertEqual(self.resolver.extract_from_title('SR 142.20 Ausländergesetz'), '142.20')
        self.assertEqual(self.resolver.extract_from_title('RS 311.0 Code pénal'), '311.0')

        # Known titles
        self.assertEqual(self.resolver.extract_from_title('Bundesverfassung der Schweizerischen Eidgenossenschaft'), '101')
        self.assertEqual(self.resolver.extract_from_title('Code civil suisse'), '210')

    def test_extract_historical_format(self):
        """Test extraction from historical URI format"""
        self.assertEqual(self.resolver.extract_historical_format('/eli/cc/I/271_271_445'), '1.271.271.445')
        self.assertEqual(self.resolver.extract_historical_format('/eli/cc/III/500_1_2'), '3.500.1.2')

    def test_validate_sr_number(self):
        """Test SR number format validation"""
        # Valid formats
        self.assertTrue(self.resolver.validate_sr_number('101'))
        self.assertTrue(self.resolver.validate_sr_number('142.20'))
        self.assertTrue(self.resolver.validate_sr_number('311.0'))
        self.assertTrue(self.resolver.validate_sr_number('1.271.271.445'))

        # Invalid formats
        self.assertFalse(self.resolver.validate_sr_number(''))
        self.assertFalse(self.resolver.validate_sr_number('ABC'))

    def test_normalize_sr_number(self):
        """Test SR number normalization"""
        self.assertEqual(self.resolver.normalize_sr_number('0101'), '101')
        self.assertEqual(self.resolver.normalize_sr_number('142.020'), '142.20')
        self.assertEqual(self.resolver.normalize_sr_number('001.002.003'), '1.2.3')

    def test_get_sr_domain(self):
        """Test SR domain extraction"""
        self.assertEqual(self.resolver.get_sr_domain('101'), '1')
        self.assertEqual(self.resolver.get_sr_domain('210'), '2')
        self.assertEqual(self.resolver.get_sr_domain('311.0'), '3')
        self.assertEqual(self.resolver.get_sr_domain('8.456.789'), '8')

    def test_get_sr_hierarchy(self):
        """Test SR hierarchy extraction"""
        self.assertEqual(self.resolver.get_sr_hierarchy('142.20'), ['1', '142', '142.20'])
        self.assertEqual(self.resolver.get_sr_hierarchy('311.0'), ['3', '311', '311.0'])
        self.assertEqual(self.resolver.get_sr_hierarchy('101'), ['1', '101'])


class TestPropertyExtractor(unittest.TestCase):
    """Test property extraction enhancements"""

    def setUp(self):
        self.extractor = FedlexPropertyExtractor()
        self.sample_data = self._load_sample_data()

    def _load_sample_data(self):
        """Create sample Fedlex data for testing"""
        return {
            'data': {
                'uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404',
                'type': 'ConsolidationAbstract',
                'attributes': {
                    'dateDocument': {'xsd:date': '1999-04-18'},
                    'dateEntryInForce': {'xsd:date': '2000-01-01'},
                    'basicAct': {'rdfs:Resource': 'https://fedlex.data.admin.ch/eli/oc/1999/404'},
                    'typeDocument': {'rdfs:Resource': 'https://fedlex.data.admin.ch/vocabulary/resource-type/28'}
                },
                'references': {
                    'inForceStatus': 'https://fedlex.data.admin.ch/vocabulary/enforcement-status/0',
                    'classifiedByTaxonomyEntry': 'https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4715'
                }
            },
            'included': [
                {
                    'type': 'Expression',
                    'attributes': {
                        'title': {'xsd:string': 'Bundesverfassung der Schweizerischen Eidgenossenschaft'},
                        'titleShort': {'xsd:string': 'BV'}
                    },
                    'references': {
                        'language': 'https://fedlex.data.admin.ch/vocabulary/language/deu'
                    }
                },
                {
                    'type': 'Expression',
                    'attributes': {
                        'title': {'xsd:string': 'Constitution fédérale de la Confédération suisse'},
                        'titleShort': {'xsd:string': 'Cst.'}
                    },
                    'references': {
                        'language': 'https://fedlex.data.admin.ch/vocabulary/language/fra'
                    }
                }
            ]
        }

    def test_extract_multilingual_titles(self):
        """Test extraction of titles in multiple languages"""
        titles, abbreviations = self.extractor._extract_multilingual_titles(self.sample_data['included'])

        self.assertEqual(titles['de'], 'Bundesverfassung der Schweizerischen Eidgenossenschaft')
        self.assertEqual(titles['fr'], 'Constitution fédérale de la Confédération suisse')
        self.assertEqual(abbreviations['de'], 'BV')
        self.assertEqual(abbreviations['fr'], 'Cst.')

    def test_extract_dates(self):
        """Test date extraction from attributes"""
        attrs = self.sample_data['data']['attributes']
        dates = self.extractor._extract_dates(attrs)

        self.assertEqual(dates['date_document'], '1999-04-18')
        self.assertEqual(dates['date_entry_in_force'], '2000-01-01')
        self.assertIsNone(dates['date_no_longer_in_force'])

    def test_extract_status(self):
        """Test enforcement status extraction"""
        refs = self.sample_data['data']['references']
        status = self.extractor._extract_status(refs)

        self.assertTrue(status['in_force'])
        self.assertEqual(status['status'], 'in_force')
        self.assertIn('/0', status['in_force_status'])

    def test_truncate_at_word_boundary(self):
        """Test word-boundary aware text truncation"""
        text = "This is a very long text that needs to be truncated at a word boundary not in the middle of a word"

        # Should truncate at word boundary
        truncated = self.extractor._truncate_at_word_boundary(text, 30)
        self.assertTrue(truncated.endswith('...'))
        self.assertLessEqual(len(truncated), 33)  # 30 + '...'
        self.assertNotIn('midd', truncated)  # Should not break 'middle'

    def test_check_for_subpoints(self):
        """Test subpoint detection in paragraph text"""
        text_with_subpoints = """
        1 Main paragraph text
        a. First subpoint
        b. Second subpoint
        c. Third subpoint
        """

        text_without = "Simple paragraph without any subpoints"

        self.assertTrue(self.extractor._check_for_subpoints(text_with_subpoints))
        self.assertFalse(self.extractor._check_for_subpoints(text_without))

    def test_count_subpoints(self):
        """Test counting subpoints in paragraph"""
        text = """
        Main paragraph:
        a. First subpoint
        b. Second subpoint
        c. Third subpoint
        """

        count = self.extractor._count_subpoints(text)
        self.assertEqual(count, 3)

    def test_extract_subpoints_from_paragraph(self):
        """Test extraction of subpoints as separate entities"""
        paragraph_uri = '/law/1/article/1/para/1'
        text = """
        Main paragraph text
        a. First subpoint with text
        b. Second subpoint with more text
        c. Third subpoint
        """

        subpoints = self.extractor.extract_subpoints_from_paragraph(paragraph_uri, text, 'de')

        self.assertEqual(len(subpoints), 3)
        self.assertEqual(subpoints[0]['letter'], 'a')
        self.assertEqual(subpoints[0]['position'], 1)
        self.assertEqual(subpoints[0]['language'], 'de')
        self.assertIn('First subpoint', subpoints[0]['text'])

    def test_extract_hierarchical_structure(self):
        """Test extraction of domain, book, chapter, section"""
        sr_number = '142.20'
        structure = self.extractor.extract_hierarchical_structure(sr_number, self.sample_data)

        # Should extract domain
        self.assertIsNotNone(structure['domain'])
        self.assertEqual(structure['domain']['sr_number'], '1')
        self.assertEqual(structure['domain']['type'], 'Domain')

        # Should extract act if basic_act exists
        self.assertIsNotNone(structure['act'])
        self.assertEqual(structure['act']['type'], 'Act')

    def test_extract_law_with_versions_and_languages(self):
        """Test complete law extraction with versions and language variants"""
        result = self.extractor.extract_law_with_versions_and_languages(self.sample_data)

        # Should have law node
        self.assertIsNotNone(result['law_node'])
        self.assertEqual(result['law_node']['uri'], 'https://fedlex.data.admin.ch/eli/cc/1999/404')
        self.assertEqual(result['law_node']['sr_number'], '101')

        # Should have at least one version
        self.assertGreater(len(result['versions']), 0)

        # Should have language variants
        self.assertGreater(len(result['language_variants']), 0)

        # Should have hierarchical structure
        self.assertIn('hierarchical_structure', result)
        self.assertIsNotNone(result['hierarchical_structure'].get('domain'))


class TestSchemaMapper(unittest.TestCase):
    """Test schema validation and property mapping"""

    def setUp(self):
        self.mapper = SchemaPropertyMapper(strict_mode=False)

    def test_validate_law_node(self):
        """Test Law node validation"""
        properties = {
            'uri': 'https://fedlex.data.admin.ch/eli/cc/1999/404',
            'sr_number': '101',
            'title_de': 'Bundesverfassung',
            'in_force': True,
            'nested_object': {'should': 'be_removed'},  # Should be filtered
            'list_of_objects': [{'also': 'removed'}]    # Should be filtered
        }

        result = self.mapper.validate_and_map('Law', properties)

        self.assertTrue(result.valid)
        self.assertNotIn('nested_object', result.mapped_properties)
        self.assertNotIn('list_of_objects', result.mapped_properties)
        self.assertEqual(result.mapped_properties['ast_level'], 5)  # Default

    def test_validate_article_node(self):
        """Test Article node validation"""
        properties = {
            'uri': '/law/1/article/1',
            'law_uri': '/law/1',
            'number': '1',
            'content_full': 'Article content',
            'content_preview': 'Article...'
        }

        result = self.mapper.validate_and_map('Article', properties)

        self.assertTrue(result.valid)
        self.assertEqual(result.mapped_properties['ast_level'], 6)

    def test_validate_paragraph_node(self):
        """Test Paragraph node validation with subpoint_count"""
        properties = {
            'uri': '/law/1/article/1/para/1',
            'article_uri': '/law/1/article/1',
            'number': '1',
            'text': 'Paragraph text',
            'has_subpoints': True,
            'subpoint_count': 3,
            'language': 'de'
        }

        result = self.mapper.validate_and_map('Paragraph', properties)

        self.assertTrue(result.valid)
        self.assertEqual(result.mapped_properties['ast_level'], 7)
        self.assertTrue(result.mapped_properties['has_subpoints'])

    def test_strict_mode_validation(self):
        """Test strict mode fails on missing required fields"""
        strict_mapper = SchemaPropertyMapper(strict_mode=True)

        # Missing required 'text' field
        properties = {
            'uri': '/para/1',
            'article_uri': '/article/1',
            'number': '1'
        }

        result = strict_mapper.validate_and_map('Paragraph', properties)

        self.assertFalse(result.valid)
        self.assertIn('Missing required field: text', result.errors[0])

    def test_property_name_mapping(self):
        """Test backward compatibility property name mappings"""
        properties = {
            'uri': '/law/1',
            'sr_number': '101',
            'dateDocument': '1999-04-18',  # Old name
            'inForce': True                # Old name
        }

        result = self.mapper.validate_and_map('Law', properties)

        # Should map old names to new
        self.assertEqual(result.mapped_properties['date_document'], '1999-04-18')
        self.assertEqual(result.mapped_properties['in_force'], True)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete pipeline"""

    def test_complete_extraction_pipeline(self):
        """Test the complete extraction pipeline from JSON to graph nodes"""
        extractor = FedlexPropertyExtractor()
        mapper = SchemaPropertyMapper()

        # Create comprehensive test data
        test_data = {
            'data': {
                'uri': 'https://fedlex.data.admin.ch/eli/cc/2020/123',
                'attributes': {
                    'dateDocument': {'xsd:date': '2020-01-01'},
                    'dateEntryInForce': {'xsd:date': '2020-06-01'}
                },
                'references': {
                    'inForceStatus': 'https://fedlex.data.admin.ch/vocabulary/enforcement-status/0',
                    'classifiedByTaxonomyEntry': 'https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/5274'
                }
            },
            'included': [
                {
                    'type': 'Expression',
                    'attributes': {
                        'title': {'xsd:string': 'Test Law Title'}
                    },
                    'references': {
                        'language': 'https://fedlex.data.admin.ch/vocabulary/language/deu'
                    }
                }
            ]
        }

        # Extract law data
        result = extractor.extract_law_with_versions_and_languages(test_data)

        # Validate law node
        law_validation = mapper.validate_and_map('Law', result['law_node'])

        self.assertTrue(law_validation.valid)
        self.assertIn('uri', law_validation.mapped_properties)
        self.assertIn('sr_number', law_validation.mapped_properties)

        # Check hierarchical structure was extracted
        self.assertIn('hierarchical_structure', result)
        if result['hierarchical_structure'].get('domain'):
            domain = result['hierarchical_structure']['domain']
            self.assertEqual(domain['type'], 'Domain')
            self.assertIn('title_de', domain)


if __name__ == '__main__':
    unittest.main()