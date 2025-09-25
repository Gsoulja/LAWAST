"""
Base extractor classes and utilities for JSON entity extraction
"""
import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of entity extraction from JSON data"""
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[tuple] = field(default_factory=list)
    statistics: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    data: Any = None  # Store the extracted data object (e.g., TaxonomyResult, Article list)

    def add_node(self, node: Dict[str, Any]):
        """Add a node to the extraction result"""
        self.nodes.append(node)
        node_type = node.get('type', 'Unknown')
        self.statistics[f"{node_type}_nodes"] = self.statistics.get(f"{node_type}_nodes", 0) + 1

    def add_relationship(self, from_uri: str, to_uri: str, rel_type: str, properties: Optional[Dict] = None):
        """Add a relationship to the extraction result"""
        self.relationships.append((from_uri, to_uri, rel_type, properties))
        self.statistics[f"{rel_type}_relationships"] = self.statistics.get(f"{rel_type}_relationships", 0) + 1

    def add_error(self, error: str):
        """Add an error to the extraction result"""
        self.errors.append(error)
        logger.warning(f"Extraction error: {error}")


class BaseExtractor(ABC):
    """Abstract base class for all JSON extractors"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def extract(self, json_data: Dict[str, Any], file_path: str) -> ExtractionResult:
        """
        Extract entities from JSON data
        
        Args:
            json_data: Parsed JSON content
            file_path: Path to the source file for context
            
        Returns:
            ExtractionResult with nodes, relationships, and statistics
        """
        pass

    def _extract_sr_number(self, uri: str) -> str:
        """
        Extract SR number from URI with comprehensive edge case handling
        
        Examples:
        - https://fedlex.data.admin.ch/eli/cc/1999/404 → "SR 1999.404"
        - https://fedlex.data.admin.ch/eli/cc/I/271_271_445 → "SR I 271"
        - https://fedlex.data.admin.ch/eli/cc/1959/__1811 → "Special 1811"
        """
        try:
            # Extract path component after /eli/cc/
            if '/eli/cc/' not in uri:
                return f"SR {uri.split('/')[-1]}"
            
            path = uri.split('/eli/cc/')[-1]
            
            # Handle Roman numerals (I/, II/, III/, etc.)
            roman_match = re.match(r'^([IVX]+)/', path)
            if roman_match:
                roman = roman_match.group(1)
                remainder = path[len(roman) + 1:]
                if '_' in remainder:
                    # Handle multi-part numbers like 271_271_445
                    parts = remainder.split('_')
                    return f"SR {roman} {parts[0]}"
                else:
                    return f"SR {roman} {remainder}"
            
            # Handle double underscores (__1811)
            if '__' in path:
                number = path.replace('__', '')
                return f"Special {number}"
            
            # Handle multi-part numbers (271_271_445)
            if '_' in path and '/' not in path:
                parts = path.split('_')
                return f"SR {parts[0]}.{parts[1]}"
            
            # Handle year/number format (1999/404)
            if '/' in path:
                year, number = path.split('/', 1)
                # Remove any date extensions
                number = number.split('/')[0]
                return f"SR {year}.{number}"
            
            # Standard format
            return f"SR {path}"
            
        except Exception as e:
            self.logger.warning(f"Failed to extract SR number from {uri}: {e}")
            return f"SR {uri.split('/')[-1]}"

    def _parse_fedlex_date(self, date_obj: Union[Dict[str, str], str, None]) -> Optional[datetime]:
        """
        Parse Fedlex date format with error handling
        
        Args:
            date_obj: Date object from JSON (can be dict with 'xsd:date' or string)
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        if not date_obj:
            return None
            
        try:
            if isinstance(date_obj, dict) and 'xsd:date' in date_obj:
                date_str = date_obj['xsd:date']
            elif isinstance(date_obj, str):
                date_str = date_obj
            else:
                return None
                
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
        except (ValueError, KeyError, AttributeError) as e:
            self.logger.warning(f"Failed to parse date {date_obj}: {e}")
            return None

    def _handle_language_placeholder(self, title: str) -> Optional[str]:
        """
        Handle language-specific placeholders
        
        Args:
            title: Title string that might be a placeholder
            
        Returns:
            None if it's a placeholder, original title otherwise
        """
        if not title or not isinstance(title, str):
            return None
            
        title_lower = title.lower().strip()
        
        placeholders = [
            "nur ital.",
            "seulement en italien", 
            "solo italiano",
            "nur deutsch",
            "seulement en allemand",
            "nur französisch",
            "seulement en français",
            "nur rätoromanisch",
            "nur englisch"
        ]
        
        if title_lower in [p.lower() for p in placeholders]:
            return None
            
        return title.strip()

    def _extract_multilingual_titles(self, included_data: List[Dict]) -> Dict[str, str]:
        """
        Extract titles in all languages from included Expression data
        
        Args:
            included_data: List of included Expression objects
            
        Returns:
            Dictionary mapping language codes to titles
        """
        titles = {}
        
        # Language code mapping
        language_mapping = {
            'http://publications.europa.eu/resource/authority/language/DEU': 'de',
            'http://publications.europa.eu/resource/authority/language/FRA': 'fr',
            'http://publications.europa.eu/resource/authority/language/ITA': 'it',
            'http://publications.europa.eu/resource/authority/language/ROH': 'rm',
            'http://publications.europa.eu/resource/authority/language/ENG': 'en'
        }
        
        for item in included_data:
            if item.get('type') == 'Expression':
                # Get language
                language_uri = item.get('references', {}).get('language')
                if language_uri in language_mapping:
                    lang_code = language_mapping[language_uri]
                    
                    # Get title
                    title_obj = item.get('attributes', {}).get('title', {})
                    if isinstance(title_obj, dict) and 'xsd:string' in title_obj:
                        title = self._handle_language_placeholder(title_obj['xsd:string'])
                        if title:
                            titles[lang_code] = title
                    elif isinstance(title_obj, str):
                        title = self._handle_language_placeholder(title_obj)
                        if title:
                            titles[lang_code] = title
        
        return titles

    def _determine_in_force_status(self, attributes: Dict) -> bool:
        """
        Determine if a law is still in force
        
        Args:
            attributes: Attributes from JSON data
            
        Returns:
            True if law is in force, False otherwise
        """
        # Check for explicit no-longer-in-force date
        if 'dateNoLongerInForce' in attributes:
            return False
            
        # Check enforcement status
        references = attributes.get('references', {})
        if isinstance(references, dict):
            in_force_status = references.get('inForceStatus', '')
            # Status 3 typically means "no longer in force"
            if 'enforcement-status/3' in str(in_force_status):
                return False
        
        return True

    def _extract_manifestations(self, references: Dict) -> List[Dict[str, Any]]:
        """
        Extract manifestation nodes from references
        
        Args:
            references: References section from JSON
            
        Returns:
            List of manifestation node dictionaries
        """
        manifestations = []
        
        # Look for isEmbodiedBy references
        embodied_by = references.get('isEmbodiedBy', [])
        if not isinstance(embodied_by, list):
            embodied_by = [embodied_by] if embodied_by else []
        
        for manifestation_uri in embodied_by:
            if isinstance(manifestation_uri, str):
                # Extract format from URI
                format_type = 'unknown'
                if '/html' in manifestation_uri:
                    format_type = 'html'
                elif '/pdf' in manifestation_uri:
                    format_type = 'pdf'
                elif '/xml' in manifestation_uri:
                    format_type = 'xml'
                elif '/docx' in manifestation_uri:
                    format_type = 'docx'
                
                manifestation = {
                    'uri': manifestation_uri,
                    'format': format_type,
                    'type': 'Manifestation'
                }
                manifestations.append(manifestation)
        
        return manifestations

    def _safe_get_nested(self, data: Dict, *keys, default=None):
        """Safely get nested dictionary values"""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
