"""
SR Taxonomy Generator - Creates Domain/Book/Chapter/Section hierarchy from SR numbers

The Swiss SR (Systematische Rechtssammlung) numbering system encodes a hierarchical
classification that we can extract to build the taxonomy tree.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.data_access.graph_schema import DomainNode, BookNode, ChapterNode, SectionNode

logger = logging.getLogger(__name__)


@dataclass
class TaxonomyLevel:
    """Represents a level in the SR taxonomy hierarchy"""
    type: str  # 'domain', 'book', 'chapter', 'section'
    number: str
    name: str
    uri: str
    parent_uri: Optional[str] = None


class SRTaxonomyGenerator:
    """Generate taxonomy hierarchy from Swiss SR numbers"""

    # Domain mapping - first digit to domain name
    DOMAIN_MAPPING = {
        '0': 'International Law - Treaties',
        '1': 'State - People - Authorities',
        '2': 'Private Law - Civil Procedure - Enforcement',
        '3': 'Criminal Law - Criminal Procedure - Execution',
        '4': 'Education - Science - Culture',
        '5': 'National Defence',
        '6': 'Finance',
        '7': 'Public Works - Energy - Transport',
        '8': 'Health - Employment - Social Security',
        '9': 'Economy - Technical Cooperation'
    }

    # Old Roman numeral domains (historical)
    ROMAN_DOMAIN_MAPPING = {
        'I': 'Historical International Law',
        'II': 'Historical State Law',
        'III': 'Historical Private Law',
        'IV': 'Historical Criminal Law',
        'V': 'Historical Education',
        'VI': 'Historical Defence',
        'VII': 'Historical Finance',
        'VIII': 'Historical Public Works',
        'IX': 'Historical Health',
        'X': 'Historical Various'
    }

    def __init__(self):
        """Initialize the SR taxonomy generator"""
        self.logger = logger

    def parse_sr_number(self, sr_number: str) -> Dict[str, Any]:
        """
        Parse an SR number to extract its hierarchical components

        Args:
            sr_number: SR number string (e.g., "SR 741.01", "SR X 35", "SR 0.362.381.026")

        Returns:
            Dictionary with parsed components:
            {
                'domain': '7',
                'book': '41',
                'chapter': None,
                'section': '01',
                'original': 'SR 741.01'
            }
        """
        if not sr_number:
            return {}

        # Clean the SR number
        sr_clean = sr_number.strip()
        if sr_clean.upper().startswith('SR '):
            sr_clean = sr_clean[3:].strip()

        parsed = {
            'original': sr_number,
            'domain': None,
            'book': None,
            'chapter': None,
            'section': None
        }

        # Handle Roman numeral format (e.g., "X 35")
        if re.match(r'^[IVX]+\s+\d+', sr_clean):
            parts = sr_clean.split()
            parsed['domain'] = parts[0]  # Roman numeral domain
            if len(parts) > 1:
                parsed['book'] = parts[1]
            return parsed

        # Handle modern decimal format
        # Patterns:
        # - "741.01" -> domain 7, book 41, section 01
        # - "0.362.381.026" -> domain 0, book 362, chapter 381, section 026
        # - "101" -> domain 1, book 01

        # Split by dots
        parts = sr_clean.split('.')

        if not parts or not parts[0]:
            return parsed

        first_part = parts[0]

        # Extract domain (first digit)
        if first_part:
            parsed['domain'] = first_part[0]

            # Extract book (remaining digits of first part)
            if len(first_part) > 1:
                parsed['book'] = first_part[1:]
            elif len(first_part) == 1 and len(parts) > 1:
                # Domain is standalone, next part is book
                parsed['book'] = parts[1] if len(parts) > 1 else None

                # Handle additional parts
                if len(parts) > 2:
                    parsed['chapter'] = parts[2]
                if len(parts) > 3:
                    parsed['section'] = parts[3]
            else:
                # Single digit domain, check for more parts
                if len(parts) > 1:
                    parsed['book'] = parts[1][:2] if len(parts[1]) >= 2 else parts[1]
                    if len(parts[1]) > 2:
                        parsed['chapter'] = parts[1][2:]
                    elif len(parts) > 2:
                        parsed['chapter'] = parts[2]
                    if len(parts) > 3:
                        parsed['section'] = parts[3]

        # Handle two-part format like "741.01"
        if len(parts) == 2 and len(first_part) > 1:
            parsed['section'] = parts[1]

        return parsed

    def generate_hierarchy(self, sr_number: str) -> List[TaxonomyLevel]:
        """
        Generate complete taxonomy hierarchy from an SR number

        Args:
            sr_number: SR number to parse

        Returns:
            List of TaxonomyLevel objects representing the hierarchy
        """
        parsed = self.parse_sr_number(sr_number)

        if not parsed.get('domain'):
            logger.warning(f"Could not parse domain from SR number: {sr_number}")
            return []

        hierarchy = []

        # Generate Domain level
        domain_num = parsed['domain']
        if domain_num in self.ROMAN_DOMAIN_MAPPING:
            domain_name = self.ROMAN_DOMAIN_MAPPING[domain_num]
            domain_uri = f"sr://domain/roman/{domain_num}"
        elif domain_num in self.DOMAIN_MAPPING:
            domain_name = self.DOMAIN_MAPPING[domain_num]
            domain_uri = f"sr://domain/{domain_num}"
        else:
            domain_name = f"Domain {domain_num}"
            domain_uri = f"sr://domain/{domain_num}"

        domain = TaxonomyLevel(
            type='domain',
            number=domain_num,
            name=domain_name,
            uri=domain_uri,
            parent_uri=None
        )
        hierarchy.append(domain)

        # Generate Book level
        if parsed.get('book'):
            book_num = parsed['book']
            book_uri = f"{domain_uri}/book/{book_num}"
            book = TaxonomyLevel(
                type='book',
                number=book_num,
                name=f"Book {book_num}",
                uri=book_uri,
                parent_uri=domain_uri
            )
            hierarchy.append(book)

            # Generate Chapter level
            if parsed.get('chapter'):
                chapter_num = parsed['chapter']
                chapter_uri = f"{book_uri}/chapter/{chapter_num}"
                chapter = TaxonomyLevel(
                    type='chapter',
                    number=chapter_num,
                    name=f"Chapter {chapter_num}",
                    uri=chapter_uri,
                    parent_uri=book_uri
                )
                hierarchy.append(chapter)

                # Generate Section level
                if parsed.get('section'):
                    section_num = parsed['section']
                    section_uri = f"{chapter_uri}/section/{section_num}"
                    section = TaxonomyLevel(
                        type='section',
                        number=section_num,
                        name=f"Section {section_num}",
                        uri=section_uri,
                        parent_uri=chapter_uri
                    )
                    hierarchy.append(section)
            elif parsed.get('section'):
                # Section directly under book (no chapter)
                section_num = parsed['section']
                section_uri = f"{book_uri}/section/{section_num}"
                section = TaxonomyLevel(
                    type='section',
                    number=section_num,
                    name=f"Section {section_num}",
                    uri=section_uri,
                    parent_uri=book_uri
                )
                hierarchy.append(section)

        return hierarchy

    def hierarchy_to_nodes(self, hierarchy: List[TaxonomyLevel]) -> Dict[str, Any]:
        """
        Convert TaxonomyLevel hierarchy to graph node objects

        Args:
            hierarchy: List of TaxonomyLevel objects

        Returns:
            Dictionary with node objects by type
        """
        nodes = {
            'domain': None,
            'book': None,
            'chapter': None,
            'section': None
        }

        for level in hierarchy:
            if level.type == 'domain':
                nodes['domain'] = DomainNode(
                    uri=level.uri,
                    name=level.name,
                    number=level.number,
                    parent_uri=level.parent_uri
                )
            elif level.type == 'book':
                nodes['book'] = BookNode(
                    uri=level.uri,
                    name=level.name,
                    number=level.number,
                    parent_uri=level.parent_uri,
                    domain_uri=level.parent_uri
                )
            elif level.type == 'chapter':
                nodes['chapter'] = ChapterNode(
                    uri=level.uri,
                    name=level.name,
                    number=level.number,
                    parent_uri=level.parent_uri,
                    book_uri=level.parent_uri
                )
            elif level.type == 'section':
                nodes['section'] = SectionNode(
                    uri=level.uri,
                    name=level.name,
                    number=level.number,
                    parent_uri=level.parent_uri,
                    chapter_uri=level.parent_uri if level.parent_uri and '/chapter/' in level.parent_uri else None
                )

        return nodes

    def extract_all_taxonomies(self, sr_numbers: List[str]) -> Dict[str, List[Any]]:
        """
        Extract unique taxonomy nodes from a list of SR numbers

        Args:
            sr_numbers: List of SR numbers to process

        Returns:
            Dictionary with unique nodes by type
        """
        unique_nodes = {
            'domains': {},
            'books': {},
            'chapters': {},
            'sections': {}
        }

        for sr_number in sr_numbers:
            if not sr_number:
                continue

            hierarchy = self.generate_hierarchy(sr_number)
            nodes = self.hierarchy_to_nodes(hierarchy)

            # Add unique nodes
            if nodes['domain']:
                unique_nodes['domains'][nodes['domain'].uri] = nodes['domain']
            if nodes['book']:
                unique_nodes['books'][nodes['book'].uri] = nodes['book']
            if nodes['chapter']:
                unique_nodes['chapters'][nodes['chapter'].uri] = nodes['chapter']
            if nodes['section']:
                unique_nodes['sections'][nodes['section'].uri] = nodes['section']

        return {
            'domains': list(unique_nodes['domains'].values()),
            'books': list(unique_nodes['books'].values()),
            'chapters': list(unique_nodes['chapters'].values()),
            'sections': list(unique_nodes['sections'].values())
        }