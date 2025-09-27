"""
SR Number Resolver for Swiss Legal System

Handles extraction and resolution of SR (Systematische Rechtssammlung) numbers
from various sources including Fedlex URIs, taxonomy references, and historical formats.
"""

import re
import logging
from typing import Optional, Dict, List
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class SRNumberResolver:
    """Resolves and validates SR numbers from various sources"""

    def __init__(self, mapping_file: Optional[Path] = None):
        """
        Initialize SR resolver with optional mapping file.

        Args:
            mapping_file: Path to JSON file with URI to SR mappings
        """
        self.mappings = self._load_default_mappings()

        # Load custom mappings if provided
        if mapping_file and mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    custom_mappings = json.load(f)
                    self.mappings.update(custom_mappings)
            except Exception as e:
                logger.warning(f"Could not load custom SR mappings: {e}")

    def _load_default_mappings(self) -> Dict[str, str]:
        """Load default known SR number mappings"""
        return {
            # URI patterns to SR numbers
            '/1999/404': '101',  # Bundesverfassung / Constitution
            '/1907/252': '210',  # Zivilgesetzbuch / Code civil
            '/1911/281': '220',  # Obligationenrecht / Code des obligations
            '/1937/799': '311.0',  # Strafgesetzbuch / Code pénal
            '/2016/322': '272',  # Zivilprozessordnung / Code de procédure civile
            '/2010/267': '312.0',  # Strafprozessordnung / Code de procédure pénale

            # Taxonomy IDs to SR numbers
            'taxonomy/4715': '101',  # Bundesverfassung
            'taxonomy/5274': '210',  # ZGB
            'taxonomy/5275': '220',  # OR
            'taxonomy/9268': '311.0',  # StGB
            'taxonomy/4894': '272',  # ZPO
            'taxonomy/4895': '312.0',  # StPO

            # Historical format mappings (Roman numerals)
            'I/1': '101',
            'II/1': '210',
            'II/2': '220',
            'III/1': '311.0',

            # Common laws by year/number pattern
            '/2008/5225': '142.20',  # Ausländer- und Integrationsgesetz
            '/1998/3033': '412.10',  # Hochschulförderungs- und -koordinationsgesetz
            '/1991/362': '414.20',  # Berufsbildungsgesetz
            '/1999/2250': '510.10',  # Militärgesetz
            '/1969/737': '641.20',  # Mehrwertsteuergesetz
            '/1990/2260': '642.11',  # Direkte Bundessteuer
            '/2004/1985': '730.0',  # Energiegesetz
            '/2000/948': '780.1',  # Eisenbahngesetz
            '/1998/2549': '810.1',  # Heilmittelgesetz
            '/2004/4719': '813.1',  # Gentechnikgesetz
            '/2014/4410': '814.01',  # Umweltschutzgesetz
            '/1981/1330': '831.10',  # AHVG
            '/1969/2034': '831.20',  # IVG
            '/1982/668': '831.30',  # BVG
            '/1994/2165': '832.10',  # Krankenversicherungsgesetz
            '/2003/4557': '834.1',  # Familienzulagengesetz
            '/1984/517': '837.0',  # Arbeitslosenversicherungsgesetz
        }

    def resolve(self, uri: str = None, taxonomy_ref: str = None,
                title: str = None) -> Optional[str]:
        """
        Main resolution method that tries multiple strategies.

        Args:
            uri: Fedlex URI
            taxonomy_ref: Taxonomy reference URI
            title: Law title for fallback extraction

        Returns:
            SR number or None if not found
        """
        # Strategy 1: Direct URI mapping
        if uri:
            sr = self.extract_from_uri(uri)
            if sr:
                return sr

        # Strategy 2: Taxonomy reference
        if taxonomy_ref:
            sr = self.extract_from_taxonomy(taxonomy_ref)
            if sr:
                return sr

        # Strategy 3: Extract from title
        if title:
            sr = self.extract_from_title(title)
            if sr:
                return sr

        # Strategy 4: Parse historical format
        if uri and '/cc/I/' in uri or '/cc/II/' in uri or '/cc/III/' in uri:
            return self.extract_historical_format(uri)

        return None

    def extract_from_uri(self, uri: str) -> Optional[str]:
        """
        Extract SR number from Fedlex URI.

        Args:
            uri: Fedlex URI like /eli/cc/1999/404

        Returns:
            SR number or None
        """
        # Check direct mapping
        for pattern, sr_number in self.mappings.items():
            if pattern in uri and '/' in pattern:
                return sr_number

        # Try to extract year/number pattern
        match = re.search(r'/cc/(\d{4})/(\d+)', uri)
        if match:
            year, number = match.groups()
            mapping_key = f'/{year}/{number}'
            if mapping_key in self.mappings:
                return self.mappings[mapping_key]

        # Extract from /eli/oc/ pattern (ordinances)
        match = re.search(r'/eli/oc/(\d{4})/(\d+)', uri)
        if match:
            year, number = match.groups()
            # Ordinances often have .1, .2 suffixes
            # This would need a more comprehensive mapping
            pass

        return None

    def extract_from_taxonomy(self, taxonomy_uri: str) -> Optional[str]:
        """
        Extract SR number from taxonomy reference.

        Args:
            taxonomy_uri: Taxonomy URI like https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4715

        Returns:
            SR number or None
        """
        # Extract taxonomy ID
        match = re.search(r'/legal-taxonomy/(\d+)', taxonomy_uri)
        if match:
            taxonomy_id = match.group(1)
            mapping_key = f'taxonomy/{taxonomy_id}'
            if mapping_key in self.mappings:
                return self.mappings[mapping_key]

        return None

    def extract_from_title(self, title: str) -> Optional[str]:
        """
        Extract SR number from law title.

        Args:
            title: Law title in any language

        Returns:
            SR number or None
        """
        # Common pattern: "SR 123.45" or "RS 123.45"
        match = re.search(r'(?:SR|RS)\s+(\d+(?:\.\d+)*)', title)
        if match:
            return match.group(1)

        # Known title patterns
        title_lower = title.lower()
        if 'bundesverfassung' in title_lower or 'constitution' in title_lower:
            return '101'
        elif 'zivilgesetzbuch' in title_lower or 'code civil' in title_lower and 'prozess' not in title_lower:
            return '210'
        elif 'obligationenrecht' in title_lower or 'code des obligations' in title_lower:
            return '220'
        elif 'strafgesetzbuch' in title_lower or 'code pénal' in title_lower:
            return '311.0'
        elif 'zivilprozess' in title_lower or 'procédure civile' in title_lower:
            return '272'
        elif 'strafprozess' in title_lower or 'procédure pénale' in title_lower:
            return '312.0'

        return None

    def extract_historical_format(self, uri: str) -> Optional[str]:
        """
        Extract SR from historical format URIs.

        Args:
            uri: Historical format URI like /eli/cc/I/271_271_445

        Returns:
            SR number or None
        """
        # Pattern: /cc/[Roman]/[numbers]
        match = re.search(r'/cc/([IVX]+)/(\d+(?:_\d+)*)', uri)
        if match:
            roman, numbers = match.groups()
            # Map Roman numerals to SR domains
            roman_to_domain = {
                'I': '1',    # Staat - Volk - Behörden
                'II': '2',   # Privatrecht
                'III': '3',  # Strafrecht
                'IV': '4',   # Schule - Wissenschaft - Kultur
                'V': '5',    # Landesverteidigung
                'VI': '6',   # Finanzen
                'VII': '7',  # Öffentliche Werke - Energie - Verkehr
                'VIII': '8', # Gesundheit - Arbeit - Soziale Sicherheit
                'IX': '9',   # Wirtschaft
            }

            domain = roman_to_domain.get(roman, '')
            if domain:
                # Convert underscores to dots
                sr_suffix = numbers.replace('_', '.')
                return f"{domain}.{sr_suffix}"

        return None

    def validate_sr_number(self, sr_number: str) -> bool:
        """
        Validate SR number format.

        Args:
            sr_number: SR number to validate

        Returns:
            True if valid format
        """
        if not sr_number:
            return False

        # Valid patterns:
        # - Simple: 101, 210, 311
        # - Dotted: 142.20, 311.0, 831.10
        # - Historical: 1.271.271.445
        patterns = [
            r'^\d{3}$',  # Three digits
            r'^\d{3}\.\d+$',  # Three digits dot digits
            r'^\d{1}\.\d+(?:\.\d+)*$',  # Domain with subsections
            r'^\d{1,3}(?:\.\d+)*$',  # General format
        ]

        return any(re.match(pattern, sr_number) for pattern in patterns)

    def normalize_sr_number(self, sr_number: str) -> str:
        """
        Normalize SR number to consistent format.

        Args:
            sr_number: SR number to normalize

        Returns:
            Normalized SR number
        """
        if not sr_number:
            return ''

        # Remove leading zeros except for domain numbers
        parts = sr_number.split('.')
        normalized_parts = []

        for i, part in enumerate(parts):
            # Keep three digits for main SR (like 101, 011)
            if i == 0 and len(part) <= 3:
                normalized_parts.append(part.lstrip('0') or '0')
            else:
                normalized_parts.append(part.lstrip('0') or '0')

        return '.'.join(normalized_parts)

    def get_sr_domain(self, sr_number: str) -> Optional[str]:
        """
        Get the domain (first digit) of an SR number.

        Args:
            sr_number: SR number

        Returns:
            Domain number (1-9) or None
        """
        if not sr_number:
            return None

        # Extract first digit
        match = re.match(r'^(\d)', sr_number)
        if match:
            return match.group(1)

        return None

    def get_sr_hierarchy(self, sr_number: str) -> List[str]:
        """
        Get hierarchical SR numbers for a given SR.

        For example: 142.20 -> ['1', '142', '142.20']

        Args:
            sr_number: SR number

        Returns:
            List of hierarchical SR numbers
        """
        if not sr_number:
            return []

        parts = sr_number.split('.')
        hierarchy = []

        # Add domain
        if parts[0]:
            domain = parts[0][0] if len(parts[0]) > 1 else parts[0]
            hierarchy.append(domain)

        # Add main number
        if parts[0] and len(parts[0]) >= 3:
            hierarchy.append(parts[0])

        # Add full number if it has subsections
        if len(parts) > 1:
            hierarchy.append(sr_number)

        return hierarchy

    def add_mapping(self, pattern: str, sr_number: str):
        """
        Add a new mapping to the resolver.

        Args:
            pattern: URI pattern or taxonomy ID
            sr_number: SR number
        """
        self.mappings[pattern] = sr_number

    def export_mappings(self, output_file: Path):
        """
        Export current mappings to JSON file.

        Args:
            output_file: Path to output JSON file
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.mappings, f, indent=2, ensure_ascii=False)


# Convenience functions for backward compatibility
_resolver = SRNumberResolver()

def resolve_sr_number(uri: str = None, taxonomy_ref: str = None,
                      title: str = None) -> Optional[str]:
    """Resolve SR number from various sources"""
    return _resolver.resolve(uri, taxonomy_ref, title)

def validate_sr_number(sr_number: str) -> bool:
    """Validate SR number format"""
    return _resolver.validate_sr_number(sr_number)

def normalize_sr_number(sr_number: str) -> str:
    """Normalize SR number to consistent format"""
    return _resolver.normalize_sr_number(sr_number)