"""
Law extractor for ConsolidationAbstract JSON files
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .base_extractor import BaseExtractor, ExtractionResult
from ..data_access.graph_schema import LawNode

logger = logging.getLogger(__name__)


class LawExtractor(BaseExtractor):
    """Extract Law nodes from ConsolidationAbstract JSON files"""

    def extract(self, json_data: Dict[str, Any], file_path: str) -> ExtractionResult:
        """
        Extract Law node from ConsolidationAbstract JSON
        
        Handles:
        - Roman numeral directories (I/, II/, III/)
        - Special formats (__1811, 271_271_445)
        - Language placeholders ("nur ital.")
        - Historical laws (dateNoLongerInForce)
        - Multilingual titles from Expression data
        """
        result = ExtractionResult()
        
        try:
            data_section = json_data.get('data', {})
            if not data_section:
                result.add_error(f"No data section found in {file_path}")
                return result
            
            # Check if this is a ConsolidationAbstract
            types = data_section.get('type', [])
            if not isinstance(types, list):
                types = [types] if types else []
            
            if 'ConsolidationAbstract' not in types:
                # This is not a ConsolidationAbstract, skip
                return result
            
            # Extract basic information
            uri = data_section.get('uri')
            if not uri:
                result.add_error(f"No URI found in ConsolidationAbstract in {file_path}")
                return result
            
            attributes = data_section.get('attributes', {})
            references = data_section.get('references', {})
            included = json_data.get('included', [])
            
            # Extract SR number
            sr_number = self._extract_sr_number(uri)
            
            # Extract multilingual titles
            titles = self._extract_multilingual_titles(included)
            
            # Extract dates
            date_document = self._parse_fedlex_date(attributes.get('dateDocument'))
            date_entry_in_force = self._parse_fedlex_date(attributes.get('dateEntryInForce'))
            date_no_longer_in_force = self._parse_fedlex_date(attributes.get('dateNoLongerInForce'))
            
            # Determine in-force status
            in_force = self._determine_in_force_status(attributes)
            if date_no_longer_in_force:
                in_force = False
            
            # Extract document type
            type_document = self._safe_get_nested(attributes, 'typeDocument', 'rdfs:Resource')
            
            # Create Law node
            law_node = {
                'uri': uri,
                'sr_number': sr_number,
                'type': 'Law',
                'date_document': date_document.isoformat() if date_document else None,
                'date_entry_in_force': date_entry_in_force.isoformat() if date_entry_in_force else None,
                'date_no_longer_in_force': date_no_longer_in_force.isoformat() if date_no_longer_in_force else None,
                'in_force': in_force,
                'type_document': type_document,
                'basic_act': self._safe_get_nested(attributes, 'basicAct', 'rdfs:Resource'),
                'classified_by_taxonomy': self._safe_get_nested(references, 'classifiedByTaxonomyEntry'),
                'in_force_status': self._safe_get_nested(references, 'inForceStatus')
            }
            
            # Add multilingual titles
            for lang, title in titles.items():
                law_node[f'title_{lang}'] = title
            
            result.add_node(law_node)
            
            # Extract language expressions
            for expression_uri in references.get('isRealizedBy', []):
                if isinstance(expression_uri, str):
                    # Determine language from URI
                    language = None
                    if expression_uri.endswith('/de'):
                        language = 'DE'
                    elif expression_uri.endswith('/fr'):
                        language = 'FR'
                    elif expression_uri.endswith('/it'):
                        language = 'IT'
                    elif expression_uri.endswith('/rm'):
                        language = 'RM'
                    elif expression_uri.endswith('/en'):
                        language = 'EN'
                    
                    if language:
                        expression_node = {
                            'uri': expression_uri,
                            'type': 'Expression',
                            'language': language,
                            'parent_uri': uri
                        }
                        result.add_node(expression_node)
                        
                        # Add relationship
                        result.add_relationship(uri, expression_uri, 'EXPRESSED_IN')
            
            # Extract manifestations from included data
            manifestations = self._extract_manifestations(references)
            for manifestation in manifestations:
                result.add_node(manifestation)
                # Add relationship from law to manifestation
                result.add_relationship(uri, manifestation['uri'], 'MANIFESTED_AS')
            
            self.logger.info(f"Extracted Law node: {sr_number} from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to extract Law from {file_path}: {str(e)}"
            result.add_error(error_msg)
            self.logger.error(error_msg, exc_info=True)
        
        return result

    def _extract_classification_info(self, references: Dict) -> Dict[str, Any]:
        """Extract classification and taxonomy information"""
        classification = {}
        
        # Get taxonomy entry
        taxonomy_entry = references.get('classifiedByTaxonomyEntry')
        if taxonomy_entry:
            classification['taxonomy_entry'] = taxonomy_entry
        
        # Get enforcement status
        enforcement_status = references.get('inForceStatus')
        if enforcement_status:
            classification['enforcement_status'] = enforcement_status
        
        return classification

    def _extract_basic_act_info(self, attributes: Dict) -> Optional[str]:
        """Extract basic act reference"""
        basic_act = attributes.get('basicAct')
        if isinstance(basic_act, dict) and 'rdfs:Resource' in basic_act:
            return basic_act['rdfs:Resource']
        elif isinstance(basic_act, str):
            return basic_act
        return None
