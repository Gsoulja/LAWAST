"""
Version extractor for Consolidation JSON files
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .base_extractor import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class VersionExtractor(BaseExtractor):
    """Extract Version nodes from Consolidation JSON files"""

    def extract(self, json_data: Dict[str, Any], file_path: str) -> ExtractionResult:
        """
        Extract Version node from Consolidation JSON
        
        Handles:
        - Missing dateEndApplicability
        - Language expressions
        - Manifestation references
        - Temporal validity periods
        """
        result = ExtractionResult()
        
        try:
            data_section = json_data.get('data', {})
            if not data_section:
                result.add_error(f"No data section found in {file_path}")
                return result
            
            # Check if this is a Consolidation (version file)
            types = data_section.get('type', [])
            if not isinstance(types, list):
                types = [types] if types else []
            
            # Version files typically have "Consolidation" type or are version-specific
            is_version = any(t in ['Consolidation', 'Expression'] for t in types)
            
            # Also check if URI contains a date pattern (version indicator)
            uri = data_section.get('uri', '')
            has_date_pattern = len(uri.split('/')) > 5 and uri.split('/')[-1].isdigit() and len(uri.split('/')[-1]) == 8
            
            if not (is_version or has_date_pattern):
                # This is not a version file, skip
                return result
            
            attributes = data_section.get('attributes', {})
            references = data_section.get('references', {})
            included = json_data.get('included', [])
            
            if not uri:
                result.add_error(f"No URI found in version data in {file_path}")
                return result
            
            # Extract parent law URI (remove date suffix if present)
            parent_law_uri = self._extract_parent_law_uri(uri)
            
            # Extract dates
            date_applicable = self._parse_fedlex_date(attributes.get('dateApplicability'))
            date_end_applicable = self._parse_fedlex_date(attributes.get('dateEndApplicability'))
            
            # If no explicit dateApplicability, try to extract from URI
            if not date_applicable:
                date_applicable = self._extract_date_from_uri(uri)
            
            # Extract version number if available
            version_number = attributes.get('versionNumber') or self._extract_version_from_uri(uri)
            
            # Create Version node
            version_node = {
                'uri': uri,
                'type': 'Version',
                'parent_law_uri': parent_law_uri,
                'date_applicable': date_applicable.isoformat() if date_applicable else None,
                'date_end_applicable': date_end_applicable.isoformat() if date_end_applicable else None,
                'version_number': version_number
            }
            
            # Add any additional metadata
            for key in ['dateDocument', 'dateEntryInForce', 'datePublication']:
                if key in attributes:
                    date_val = self._parse_fedlex_date(attributes[key])
                    if date_val:
                        version_node[f'date_{key.lower()[4:]}'] = date_val.isoformat()
            
            result.add_node(version_node)
            
            # Add relationship to parent law
            if parent_law_uri:
                result.add_relationship(parent_law_uri, uri, 'HAS_VERSION')
            
            # Extract language expressions for this version
            for expression_uri in references.get('isRealizedBy', []):
                if isinstance(expression_uri, str):
                    # Determine language from URI
                    language = self._extract_language_from_uri(expression_uri)
                    
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
            
            # Extract manifestations from references
            manifestations = self._extract_manifestations(references)
            for manifestation in manifestations:
                result.add_node(manifestation)
                # Add relationship from version to manifestation
                result.add_relationship(uri, manifestation['uri'], 'MANIFESTED_AS')
            
            # Also extract manifestations from included data
            included_manifestations = self._extract_manifestations_from_included(included)
            for manifestation in included_manifestations:
                result.add_node(manifestation)
                # Try to link to appropriate parent (expression or version)
                parent_uri = manifestation.get('parent_uri', uri)
                result.add_relationship(parent_uri, manifestation['uri'], 'MANIFESTED_AS')
            
            self.logger.info(f"Extracted Version node: {uri} from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to extract Version from {file_path}: {str(e)}"
            result.add_error(error_msg)
            self.logger.error(error_msg, exc_info=True)
        
        return result

    def _extract_parent_law_uri(self, version_uri: str) -> str:
        """
        Extract parent law URI from version URI
        
        Examples:
        - https://fedlex.data.admin.ch/eli/cc/1999/404/20240101 → https://fedlex.data.admin.ch/eli/cc/1999/404
        - https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de → https://fedlex.data.admin.ch/eli/cc/1999/404
        """
        parts = version_uri.split('/')
        
        # Remove date and language parts
        filtered_parts = []
        for part in parts:
            # Skip date-like parts (8 digits) and language codes
            if not (part.isdigit() and len(part) == 8) and part not in ['de', 'fr', 'it', 'rm', 'en']:
                filtered_parts.append(part)
            else:
                break  # Stop at first date or language code
        
        return '/'.join(filtered_parts)

    def _extract_date_from_uri(self, uri: str) -> Optional[datetime]:
        """Extract date from URI if it contains a date pattern"""
        parts = uri.split('/')
        for part in parts:
            if part.isdigit() and len(part) == 8:
                try:
                    year = int(part[:4])
                    month = int(part[4:6])
                    day = int(part[6:8])
                    return datetime(year, month, day)
                except ValueError:
                    continue
        return None

    def _extract_version_from_uri(self, uri: str) -> Optional[str]:
        """Extract version identifier from URI"""
        parts = uri.split('/')
        for part in parts:
            if part.isdigit() and len(part) == 8:
                return part
        return None

    def _extract_language_from_uri(self, uri: str) -> Optional[str]:
        """Extract language code from URI"""
        if uri.endswith('/de'):
            return 'DE'
        elif uri.endswith('/fr'):
            return 'FR'
        elif uri.endswith('/it'):
            return 'IT'
        elif uri.endswith('/rm'):
            return 'RM'
        elif uri.endswith('/en'):
            return 'EN'
        return None

    def _extract_manifestations_from_included(self, included: list) -> list:
        """Extract manifestation nodes from included data"""
        manifestations = []
        
        for item in included:
            if not isinstance(item, dict):
                continue
                
            item_type = item.get('type')
            if item_type == 'Manifestation':
                uri = item.get('uri')
                if uri:
                    # Extract format from URI or attributes
                    format_type = 'unknown'
                    if '/html' in uri:
                        format_type = 'html'
                    elif '/pdf' in uri:
                        format_type = 'pdf'
                    elif '/xml' in uri:
                        format_type = 'xml'
                    elif '/docx' in uri:
                        format_type = 'docx'
                    
                    # Get format from attributes if available
                    attributes = item.get('attributes', {})
                    if 'format' in attributes:
                        format_obj = attributes['format']
                        if isinstance(format_obj, dict) and 'rdfs:Resource' in format_obj:
                            format_uri = format_obj['rdfs:Resource']
                            if 'html' in format_uri.lower():
                                format_type = 'html'
                            elif 'pdf' in format_uri.lower():
                                format_type = 'pdf'
                            elif 'xml' in format_uri.lower():
                                format_type = 'xml'
                            elif 'docx' in format_uri.lower():
                                format_type = 'docx'
                    
                    manifestation = {
                        'uri': uri,
                        'type': 'Manifestation',
                        'format': format_type
                    }
                    
                    # Try to determine parent from references
                    references = item.get('references', {})
                    if 'isEmbodimentOf' in references:
                        manifestation['parent_uri'] = references['isEmbodimentOf']
                    
                    manifestations.append(manifestation)
        
        return manifestations
