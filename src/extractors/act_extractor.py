"""
Act extractor for publication JSON files (OC/FGA)
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_extractor import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class ActExtractor(BaseExtractor):
    """Extract Act nodes from publication JSON files (/eli/oc/ and /eli/fga/)"""

    def extract(self, json_data: Dict[str, Any], file_path: str) -> ExtractionResult:
        """
        Extract Act node from publication JSON
        
        Handles:
        - Official compilation (OC) publications
        - Federal gazette (FGA) publications
        - Publication metadata
        - Memorial/gazette information
        - References to impacted laws
        """
        result = ExtractionResult()
        
        try:
            data_section = json_data.get('data', {})
            if not data_section:
                result.add_error(f"No data section found in {file_path}")
                return result
            
            # Check if this is an Act/Publication
            types = data_section.get('type', [])
            if not isinstance(types, list):
                types = [types] if types else []
            
            # Acts typically have "Act" type or are in OC/FGA directories
            is_act = 'Act' in types
            is_publication = any('/eli/oc/' in file_path or '/eli/fga/' in file_path for _ in [1])
            
            if not (is_act or is_publication):
                # This is not an Act/Publication, skip
                return result
            
            uri = data_section.get('uri')
            if not uri:
                result.add_error(f"No URI found in Act data in {file_path}")
                return result
            
            attributes = data_section.get('attributes', {})
            references = data_section.get('references', {})
            included = json_data.get('included', [])
            
            # Extract publication information
            date_publication = self._parse_fedlex_date(attributes.get('datePublication'))
            date_document = self._parse_fedlex_date(attributes.get('dateDocument'))
            date_entry_in_force = self._parse_fedlex_date(attributes.get('dateEntryInForce'))
            
            # Extract titles
            titles = self._extract_multilingual_titles(included)
            
            # Extract document type
            type_document = self._safe_get_nested(attributes, 'typeDocument', 'rdfs:Resource')
            
            # Extract memorial/gazette information
            memorial_info = self._extract_memorial_information(attributes)
            
            # Determine publication type (OC vs FGA)
            publication_type = 'OC' if '/eli/oc/' in uri else 'FGA' if '/eli/fga/' in uri else 'Unknown'
            
            # Create Act node
            act_node = {
                'uri': uri,
                'type': 'Act',
                'publication_type': publication_type,
                'date_publication': date_publication.isoformat() if date_publication else None,
                'date_document': date_document.isoformat() if date_document else None,
                'date_entry_in_force': date_entry_in_force.isoformat() if date_entry_in_force else None,
                'type_document': type_document
            }
            
            # Add multilingual titles
            for lang, title in titles.items():
                act_node[f'title_{lang}'] = title
            
            # Add memorial information
            act_node.update(memorial_info)
            
            # Extract additional metadata
            if 'publicationDate' in attributes:
                pub_date = self._parse_fedlex_date(attributes['publicationDate'])
                if pub_date:
                    act_node['publication_date'] = pub_date.isoformat()
            
            result.add_node(act_node)
            
            # Extract impacted laws from references
            impacted_laws = self._extract_impacted_laws(references, included)
            for law_uri in impacted_laws:
                # Add AMENDS relationship
                result.add_relationship(uri, law_uri, 'AMENDS')
            
            # Extract language expressions
            for expression_uri in references.get('isRealizedBy', []):
                if isinstance(expression_uri, str):
                    language = self._extract_language_from_uri(expression_uri)
                    
                    if language:
                        expression_node = {
                            'uri': expression_uri,
                            'type': 'Expression',
                            'language': language,
                            'parent_uri': uri
                        }
                        result.add_node(expression_node)
                        result.add_relationship(uri, expression_uri, 'EXPRESSED_IN')
            
            # Extract manifestations
            manifestations = self._extract_manifestations(references)
            for manifestation in manifestations:
                result.add_node(manifestation)
                result.add_relationship(uri, manifestation['uri'], 'MANIFESTED_AS')
            
            self.logger.info(f"Extracted Act node: {publication_type} from {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to extract Act from {file_path}: {str(e)}"
            result.add_error(error_msg)
            self.logger.error(error_msg, exc_info=True)
        
        return result

    def _extract_memorial_information(self, attributes: Dict) -> Dict[str, Any]:
        """Extract memorial/gazette page and number information"""
        memorial_info = {}
        
        # Memorial number
        memorial_number = attributes.get('memorialNumber')
        if memorial_number:
            memorial_info['memorial_number'] = memorial_number
        
        # Memorial page
        memorial_page = attributes.get('memorialPage')
        if memorial_page:
            memorial_info['memorial_page'] = memorial_page
        
        # Memorial year
        memorial_year = attributes.get('memorialYear')
        if memorial_year:
            memorial_info['memorial_year'] = memorial_year
        
        # Volume information
        volume = attributes.get('volume')
        if volume:
            memorial_info['volume'] = volume
        
        return memorial_info

    def _extract_impacted_laws(self, references: Dict, included: List) -> List[str]:
        """
        Extract URIs of laws that this act impacts/amends
        
        Args:
            references: References section from the act
            included: Included section with additional data
            
        Returns:
            List of law URIs that are impacted by this act
        """
        impacted_laws = []
        
        # Look for consolidationAbstract references (laws being amended)
        consolidation_refs = references.get('consolidationAbstract', [])
        if not isinstance(consolidation_refs, list):
            consolidation_refs = [consolidation_refs] if consolidation_refs else []
        
        for ref in consolidation_refs:
            if isinstance(ref, str):
                impacted_laws.append(ref)
        
        # Look for isPartOf relationships (this act is part of amending a law)
        is_part_of = references.get('isPartOf', [])
        if not isinstance(is_part_of, list):
            is_part_of = [is_part_of] if is_part_of else []
        
        for ref in is_part_of:
            if isinstance(ref, str) and '/eli/cc/' in ref:
                impacted_laws.append(ref)
        
        # Look in included data for additional references
        for item in included:
            if isinstance(item, dict):
                item_refs = item.get('references', {})
                
                # Check for consolidation references
                item_consolidation = item_refs.get('consolidationAbstract')
                if item_consolidation and isinstance(item_consolidation, str):
                    if item_consolidation not in impacted_laws:
                        impacted_laws.append(item_consolidation)
        
        return list(set(impacted_laws))  # Remove duplicates

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

    def _determine_publication_series(self, uri: str, attributes: Dict) -> str:
        """
        Determine the publication series (AS, FF, RO, etc.)
        
        Args:
            uri: URI of the publication
            attributes: Attributes section
            
        Returns:
            Publication series identifier
        """
        if '/eli/oc/' in uri:
            return 'AS'  # Amtliche Sammlung / Recueil officiel
        elif '/eli/fga/' in uri:
            return 'FF'  # Bundesblatt / Feuille fédérale
        
        # Try to extract from attributes if available
        series = attributes.get('publicationSeries')
        if series:
            return str(series)
        
        return 'Unknown'
