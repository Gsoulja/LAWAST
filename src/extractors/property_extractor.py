"""
Property Extractor for LAWAST Schema Alignment

Centralized extraction functions for complete schema compliance.
Handles multilingual content, edge cases, and Fedlex data variations.
"""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
from .sr_resolver import SRNumberResolver

logger = logging.getLogger(__name__)


class FedlexPropertyExtractor:
    """Extract all properties required by LAWAST schema from Fedlex data"""

    # Language mappings
    LANG_MAP = {
        'deu': 'de', 'ger': 'de',
        'fra': 'fr', 'fre': 'fr',
        'ita': 'it',
        'roh': 'rm', 'rme': 'rm',
        'eng': 'en'
    }

    # Enforcement status mappings
    ENFORCEMENT_STATUS = {
        '/0': {'in_force': True, 'status': 'in_force'},
        '/1': {'in_force': True, 'status': 'in_force_partially'},
        '/2': {'in_force': False, 'status': 'not_yet_in_force'},
        '/3': {'in_force': False, 'status': 'repealed'},
        '/4': {'in_force': False, 'status': 'suspended'}
    }

    def __init__(self):
        """Initialize the property extractor with SR resolver"""
        self.sr_resolver = SRNumberResolver()

    def extract_hierarchical_structure(self, sr_number: str, data: Dict) -> Dict[str, List[Dict]]:
        """
        Extract hierarchical structure nodes (Domain, Book, Chapter, Section) from SR number and metadata.

        Args:
            sr_number: SR number of the law
            data: Fedlex JSON data

        Returns:
            Dictionary with lists of Domain, Book, Chapter, Section nodes
        """
        structure = {
            'domain': None,
            'book': None,
            'chapter': None,
            'section': None,
            'act': None
        }

        if not sr_number:
            return structure

        # Extract domain from SR number (first digit)
        domain_num = self.sr_resolver.get_sr_domain(sr_number)
        if domain_num:
            structure['domain'] = self._create_domain_node(domain_num)

        # Extract book/chapter/section from law metadata if available
        attrs = data.get('data', {}).get('attributes', {})
        refs = data.get('data', {}).get('references', {})

        # Try to extract structural information from title or classification
        included = data.get('included', [])
        for item in included:
            if item.get('type') == 'Expression':
                title = item.get('attributes', {}).get('title', {})
                if isinstance(title, dict):
                    title_text = title.get('xsd:string', '')
                else:
                    title_text = str(title)

                # Extract book/chapter/section from title patterns
                book_info = self._extract_book_from_title(title_text)
                if book_info:
                    structure['book'] = book_info

                chapter_info = self._extract_chapter_from_title(title_text)
                if chapter_info:
                    structure['chapter'] = chapter_info

                section_info = self._extract_section_from_title(title_text)
                if section_info:
                    structure['section'] = section_info

        # Extract Act information if available
        if attrs.get('basicAct'):
            structure['act'] = self._create_act_node(attrs, refs)

        return structure

    def _create_domain_node(self, domain_num: str) -> Dict[str, Any]:
        """Create a Domain node from domain number"""
        domain_titles = {
            '1': {
                'de': 'Staat - Volk - Behörden',
                'fr': 'État - Peuple - Autorités',
                'it': 'Stato - Popolo - Autorità',
                'en': 'State - People - Authorities'
            },
            '2': {
                'de': 'Privatrecht - Zivilrechtspflege - Vollstreckung',
                'fr': 'Droit privé - Procédure civile - Exécution',
                'it': 'Diritto privato - Procedura civile - Esecuzione',
                'en': 'Private Law - Civil Procedure - Enforcement'
            },
            '3': {
                'de': 'Strafrecht - Strafrechtspflege - Strafvollzug',
                'fr': 'Droit pénal - Procédure pénale - Exécution',
                'it': 'Diritto penale - Procedura penale - Esecuzione',
                'en': 'Criminal Law - Criminal Procedure - Execution'
            },
            '4': {
                'de': 'Schule - Wissenschaft - Kultur',
                'fr': 'École - Science - Culture',
                'it': 'Scuola - Scienza - Cultura',
                'en': 'Education - Science - Culture'
            },
            '5': {
                'de': 'Landesverteidigung',
                'fr': 'Défense nationale',
                'it': 'Difesa nazionale',
                'en': 'National Defense'
            },
            '6': {
                'de': 'Finanzen',
                'fr': 'Finances',
                'it': 'Finanze',
                'en': 'Finance'
            },
            '7': {
                'de': 'Öffentliche Werke - Energie - Verkehr',
                'fr': 'Travaux publics - Énergie - Transports',
                'it': 'Lavori pubblici - Energia - Trasporti',
                'en': 'Public Works - Energy - Transport'
            },
            '8': {
                'de': 'Gesundheit - Arbeit - Soziale Sicherheit',
                'fr': 'Santé - Travail - Sécurité sociale',
                'it': 'Sanità - Lavoro - Sicurezza sociale',
                'en': 'Health - Labor - Social Security'
            },
            '9': {
                'de': 'Wirtschaft - Technische Zusammenarbeit',
                'fr': 'Économie - Coopération technique',
                'it': 'Economia - Cooperazione tecnica',
                'en': 'Economy - Technical Cooperation'
            }
        }

        titles = domain_titles.get(domain_num, {})

        return {
            'uri': f'/sr/domain/{domain_num}',
            'sr_number': domain_num,
            'type': 'Domain',
            'title_de': titles.get('de'),
            'title_fr': titles.get('fr'),
            'title_it': titles.get('it'),
            'title_en': titles.get('en'),
            'ast_level': 1,
            'ast_path': f'/domain_{domain_num}'
        }

    def _create_act_node(self, attrs: Dict, refs: Dict) -> Dict[str, Any]:
        """Create an Act node from basic act information"""
        basic_act = attrs.get('basicAct', {})
        if not basic_act:
            return None

        act_uri = basic_act.get('rdfs:Resource') if isinstance(basic_act, dict) else str(basic_act)

        # Extract Act date and type
        type_document = attrs.get('typeDocument', {})
        type_doc_uri = type_document.get('rdfs:Resource') if isinstance(type_document, dict) else str(type_document)

        return {
            'uri': act_uri,
            'type': 'Act',
            'type_document': type_doc_uri,
            'date_document': attrs.get('dateDocument', {}).get('xsd:date') if isinstance(attrs.get('dateDocument'), dict) else attrs.get('dateDocument'),
            'ast_level': 4,
            'ast_path': f'/act/{act_uri.split("/")[-1] if act_uri else "unknown"}'
        }

    def _extract_book_from_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Extract Book information from title"""
        # Patterns for books (Buch, Livre, Libro, Book)
        patterns = [
            r'(?:Erstes|Zweites|Drittes|Viertes|Fünftes)\s+Buch[:]*\s*(.+?)(?:\n|$)',
            r'(?:Premier|Deuxième|Troisième|Quatrième|Cinquième)\s+Livre[:]*\s*(.+?)(?:\n|$)',
            r'(?:Primo|Secondo|Terzo|Quarto|Quinto)\s+Libro[:]*\s*(.+?)(?:\n|$)',
            r'(?:First|Second|Third|Fourth|Fifth)\s+Book[:]*\s*(.+?)(?:\n|$)',
            r'Buch\s+([IVX]+)[:]*\s*(.+?)(?:\n|$)',
            r'Livre\s+([IVX]+)[:]*\s*(.+?)(?:\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return {
                    'type': 'Book',
                    'title': match.group(0).strip(),
                    'ast_level': 2
                }
        return None

    def _extract_chapter_from_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Extract Chapter information from title - enhanced version"""
        patterns = [
            r'Kapitel\s+([IVX\d]+)[:]?\s*(.+?)(?:\n|$)',
            r'Chapitre\s+([IVX\d]+)[:]?\s*(.+?)(?:\n|$)',
            r'Capitolo\s+([IVX\d]+)[:]?\s*(.+?)(?:\n|$)',
            r'Chapter\s+([IVX\d]+)[:]?\s*(.+?)(?:\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return {
                    'type': 'Chapter',
                    'number': match.group(1),
                    'title': match.group(2).strip() if match.group(2) else '',
                    'ast_level': 3
                }
        return None

    def _extract_section_from_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Extract Section information from title - enhanced version"""
        patterns = [
            r'Abschnitt\s+([IVX\d]+)[:]?\s*(.+?)(?:\n|$)',
            r'Section\s+([IVX\d]+)[:]?\s*(.+?)(?:\n|$)',
            r'Sezione\s+([IVX\d]+)[:]?\s*(.+?)(?:\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return {
                    'type': 'Section',
                    'number': match.group(1),
                    'title': match.group(2).strip() if match.group(2) else '',
                    'ast_level': 4
                }
        return None

    def extract_law_with_versions_and_languages(self, data: Dict, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Extract law with all its versions and language variants.

        Returns:
            Dictionary with:
            - law_node: Base law node (language-neutral)
            - versions: List of version nodes
            - language_variants: List of language-specific law nodes per version
        """
        result = {
            'law_node': None,
            'versions': [],
            'language_variants': [],
            'hierarchical_structure': {}
        }

        # Extract base law properties (language-neutral)
        law_data = data.get('data', {})
        base_uri = law_data.get('uri', '')

        if not base_uri:
            logger.error("No URI found in data")
            return result

        # Extract SR number
        refs = law_data.get('references', {})
        sr_number = self._extract_sr_number(law_data, refs)

        # Extract hierarchical structure
        result['hierarchical_structure'] = self.extract_hierarchical_structure(sr_number, data)

        # Extract dates for version tracking
        attrs = law_data.get('attributes', {})
        dates = self._extract_dates(attrs)

        # Create base law node (language-neutral)
        result['law_node'] = {
            'uri': base_uri,
            'sr_number': sr_number,
            'type': 'Law',
            'date_document': dates.get('date_document'),
            'date_entry_in_force': dates.get('date_entry_in_force'),
            'date_no_longer_in_force': dates.get('date_no_longer_in_force'),
            'ast_level': 5,
            'ast_path': f'/sr_{sr_number}' if sr_number else '/law'
        }

        # Extract version information
        version_date = dates.get('date_entry_in_force', '20240101')
        version_node = {
            'uri': f"{base_uri}/version/{version_date}",
            'law_uri': base_uri,
            'version_date': version_date,
            'date_applicable': version_date,
            'is_current': True,  # Mark as current for now
            'type': 'Version'
        }
        result['versions'].append(version_node)

        # Extract language variants for this version
        included = data.get('included', [])
        titles, abbreviations = self._extract_multilingual_titles(included)
        status_info = self._extract_status(refs)
        references = self._extract_references(attrs, refs)

        for lang in ['de', 'fr', 'it', 'rm', 'en']:
            if titles.get(lang):  # Only create if title exists for this language
                lang_variant = {
                    'uri': f"{base_uri}/version/{version_date}/{lang}",
                    'law_uri': base_uri,
                    'version_uri': f"{base_uri}/version/{version_date}",
                    'sr_number': sr_number,
                    'language': lang,
                    'title': titles.get(lang),
                    'abbreviation': abbreviations.get(lang),
                    'type': 'LawLanguageVariant',
                    'in_force': status_info['in_force'],
                    'status': status_info['status'],
                    'basic_act': references.get('basic_act'),
                    'classified_by_taxonomy': references.get('classified_by_taxonomy'),
                    'type_document': references.get('type_document'),
                    'ast_level': 5,
                    'ast_path': f'/sr_{sr_number}/{lang}' if sr_number else f'/law/{lang}',
                    'date_modified': datetime.now().isoformat()
                }
                result['language_variants'].append(lang_variant)

        return result

    def extract_law_properties(self, data: Dict, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Extract all LawNode properties from Fedlex ConsolidationAbstract JSON.

        Args:
            data: Fedlex JSON data
            file_path: Optional path to JSON file

        Returns:
            Dict with all 24 LawNode properties
        """
        # Extract core sections
        data_section = data.get('data', {})
        attrs = data_section.get('attributes', {})
        refs = data_section.get('references', {})
        included = data.get('included', [])

        # Extract multilingual titles and abbreviations
        titles, abbreviations = self._extract_multilingual_titles(included)

        # Extract dates
        dates = self._extract_dates(attrs)

        # Extract status information
        status_info = self._extract_status(refs)

        # Extract SR number
        sr_number = self._extract_sr_number(data_section, refs)

        # Extract references
        references = self._extract_references(attrs, refs)

        # Detect primary language
        primary_language = self._detect_primary_language(titles)

        # Generate AST properties
        ast_props = self._generate_ast_properties(sr_number, 'law')

        return {
            # Required fields
            'uri': data_section.get('uri', ''),
            'sr_number': sr_number,

            # Multilingual titles
            'title_de': titles.get('de'),
            'title_fr': titles.get('fr'),
            'title_it': titles.get('it'),
            'title_rm': titles.get('rm'),
            'title_en': titles.get('en'),

            # Abbreviations (not in schema but in current implementation)
            'abbreviation_de': abbreviations.get('de'),
            'abbreviation_fr': abbreviations.get('fr'),
            'abbreviation_it': abbreviations.get('it'),

            # Date fields
            'date_document': dates.get('date_document'),
            'date_entry_in_force': dates.get('date_entry_in_force'),
            'date_no_longer_in_force': dates.get('date_no_longer_in_force'),
            'date_modified': datetime.now().isoformat(),

            # Status fields
            'in_force': status_info['in_force'],
            'in_force_status': status_info['in_force_status'],
            'status': status_info['status'],

            # References
            'basic_act': references.get('basic_act'),
            'classified_by_taxonomy': references.get('classified_by_taxonomy'),
            'type_document': references.get('type_document'),

            # Metadata
            'type': 'Law',
            'language': primary_language,
            'parent_uri': None,  # Rarely present in Fedlex

            # AST properties
            'ast_path': ast_props['ast_path'],
            'ast_level': ast_props['ast_level'],
            'parent_id': ast_props['parent_id']
        }

    def _extract_multilingual_titles(self, included: List[Dict]) -> Tuple[Dict, Dict]:
        """Extract titles and abbreviations in all languages"""
        titles = {}
        abbreviations = {}

        for item in included:
            if item.get('type') == 'Expression':
                # Extract language code
                lang_uri = item.get('references', {}).get('language', '')
                lang_code = lang_uri.split('/')[-1].lower() if lang_uri else ''

                # Map to our standard language codes
                lang = self.LANG_MAP.get(lang_code)
                if lang:
                    # Extract title
                    title = item.get('attributes', {}).get('title', {})
                    if isinstance(title, dict):
                        titles[lang] = title.get('xsd:string')
                    elif isinstance(title, str):
                        titles[lang] = title

                    # Extract abbreviation
                    abbrev = item.get('attributes', {}).get('titleShort', {})
                    if isinstance(abbrev, dict):
                        abbreviations[lang] = abbrev.get('xsd:string')
                    elif isinstance(abbrev, str):
                        abbreviations[lang] = abbrev

        return titles, abbreviations

    def _extract_dates(self, attrs: Dict) -> Dict[str, Optional[str]]:
        """Extract all date fields"""
        dates = {}

        date_fields = [
            ('dateDocument', 'date_document'),
            ('dateEntryInForce', 'date_entry_in_force'),
            ('dateNoLongerInForce', 'date_no_longer_in_force')
        ]

        for fedlex_field, our_field in date_fields:
            date_value = attrs.get(fedlex_field, {})
            if isinstance(date_value, dict):
                dates[our_field] = date_value.get('xsd:date')
            elif isinstance(date_value, str):
                dates[our_field] = date_value
            else:
                dates[our_field] = None

        return dates

    def _extract_status(self, refs: Dict) -> Dict[str, Any]:
        """Extract enforcement status information"""
        status_uri = refs.get('inForceStatus', '')

        # Check which status it is
        for suffix, status_info in self.ENFORCEMENT_STATUS.items():
            if status_uri.endswith(suffix):
                return {
                    'in_force': status_info['in_force'],
                    'in_force_status': status_uri,
                    'status': status_info['status']
                }

        # Default to in force if unknown
        return {
            'in_force': True,
            'in_force_status': status_uri,
            'status': 'unknown'
        }

    def _extract_sr_number(self, data_section: Dict, refs: Dict) -> str:
        """Extract SR number using the SR resolver"""
        uri = data_section.get('uri', '')
        taxonomy_uri = refs.get('classifiedByTaxonomyEntry', '')

        # Get titles for fallback extraction
        titles = []
        if 'attributes' in data_section:
            attrs = data_section['attributes']
            for key in ['title_de', 'title_fr', 'title_it']:
                if key in attrs:
                    titles.append(attrs[key])

        # Use the resolver
        sr_number = self.sr_resolver.resolve(
            uri=uri,
            taxonomy_ref=taxonomy_uri,
            title=' '.join(titles) if titles else None
        )

        # Normalize if found
        if sr_number:
            return self.sr_resolver.normalize_sr_number(sr_number)

        return ''

    def extract_sr_from_taxonomy(self, taxonomy_uri: str) -> Optional[str]:
        """Extract SR number from taxonomy URI - uses SR resolver"""
        return self.sr_resolver.extract_from_taxonomy(taxonomy_uri)

    def extract_sr_from_uri(self, uri: str) -> Optional[str]:
        """Extract SR number from law URI - uses SR resolver"""
        return self.sr_resolver.extract_from_uri(uri)

    def _extract_historical_sr(self, uri: str) -> str:
        """Extract SR from historical format - uses SR resolver"""
        return self.sr_resolver.extract_historical_format(uri) or ''

    def _extract_references(self, attrs: Dict, refs: Dict) -> Dict[str, Optional[str]]:
        """Extract reference URIs"""
        references = {}

        # Basic act
        basic_act = attrs.get('basicAct', {})
        if isinstance(basic_act, dict):
            references['basic_act'] = basic_act.get('rdfs:Resource')
        else:
            references['basic_act'] = None

        # Taxonomy classification
        references['classified_by_taxonomy'] = refs.get('classifiedByTaxonomyEntry')

        # Document type
        type_doc = attrs.get('typeDocument', {})
        if isinstance(type_doc, dict):
            references['type_document'] = type_doc.get('rdfs:Resource')
        else:
            references['type_document'] = None

        return references

    def _detect_primary_language(self, titles: Dict) -> str:
        """Detect primary language based on available titles"""
        # Priority order: DE, FR, IT, EN, RM
        priority = ['de', 'fr', 'it', 'en', 'rm']

        for lang in priority:
            if titles.get(lang):
                return lang

        return 'de'  # Default to German

    def _generate_ast_properties(self, sr_number: str, node_type: str) -> Dict[str, Any]:
        """Generate AST (Abstract Syntax Tree) properties"""
        ast_levels = {
            'domain': 1,
            'book': 2,
            'chapter': 3,
            'section': 4,
            'law': 5,
            'article': 6,
            'paragraph': 7,
            'subpoint': 8
        }

        return {
            'ast_path': f'/sr_{sr_number}' if sr_number else f'/{node_type}',
            'ast_level': ast_levels.get(node_type, 5),
            'parent_id': None  # Will be set if part of hierarchy
        }

    def extract_articles_for_language_variant(self, article_num: int, lang_variant_uri: str,
                                             language: str, fedlex_path: Path) -> Dict[str, Any]:
        """
        Extract article for a specific language variant.

        Args:
            article_num: Article number
            lang_variant_uri: URI of the language variant
            language: Language code (de, fr, it, rm, en)
            fedlex_path: Path to fedlex-assets directory

        Returns:
            Article data for the specified language
        """
        # Parse law URI from lang_variant_uri
        # Format: /eli/cc/1999/404/version/20240101/de -> /eli/cc/1999/404
        uri_parts = lang_variant_uri.split('/version/')
        law_uri = uri_parts[0] if uri_parts else lang_variant_uri

        # Handle different URI formats
        sr_match = re.search(r'/cc/(\d+)/(\d+(?:_\d+)*)', law_uri)
        if not sr_match:
            logger.warning(f"Could not extract SR from law_uri: {law_uri}")
            return {}

        year, number = sr_match.groups()

        # Find HTML file for this language
        html_dir = fedlex_path / 'eli' / 'cc' / year / number / '20240101' / language / 'html'
        if not html_dir.exists():
            return {}

        html_files = list(html_dir.glob(f'*-{language}-html.html'))
        if not html_files:
            return {}

        content = self._extract_article_from_html(html_files[0], article_num, language)
        if not content:
            return {}

        return {
            'uri': f"{lang_variant_uri}/art_{article_num}",
            'law_language_variant_uri': lang_variant_uri,
            'law_uri': law_uri,
            'number': str(article_num),
            'number_normalized': article_num,
            'position': article_num,
            'language': language,
            'content_full': content['text'],
            'title': content.get('title', ''),
            'content_preview': self._truncate_at_word_boundary(content['text'], 500) if content['text'] else '',
            'word_count': len(content['text'].split()) if content['text'] else 0,
            'ast_level': 6,
            'ast_path': f"{lang_variant_uri}/art_{article_num}",
            'type': 'Article'
        }

    def extract_article_multilingual(self, article_num: int, law_uri: str,
                                    fedlex_path: Path) -> List[Dict[str, Any]]:
        """
        Extract article from all available language versions.
        Creates separate article nodes for each language.
        DEPRECATED: Use extract_articles_for_language_variant instead

        Args:
            article_num: Article number
            law_uri: Law URI
            fedlex_path: Path to fedlex-assets directory

        Returns:
            List of article data dictionaries, one per language
        """
        # Extract SR number from law URI for path construction
        # Handle different URI formats
        sr_match = re.search(r'/cc/(\d+)/(\d+(?:_\d+)*)', law_uri)
        if not sr_match:
            logger.warning(f"Could not extract SR from law_uri: {law_uri}")
            return []

        year, number = sr_match.groups()

        # Check for HTML files in different languages
        article_nodes = []
        languages = ['de', 'fr', 'it', 'rm', 'en']

        for lang in languages:
            html_dir = fedlex_path / 'eli' / 'cc' / year / number / '20240101' / lang / 'html'
            if html_dir.exists():
                # Find main HTML file
                html_files = list(html_dir.glob(f'*-{lang}-html.html'))
                if html_files:
                    content = self._extract_article_from_html(
                        html_files[0], article_num, lang
                    )
                    if content:
                        # Create article node for this language
                        article_data = {
                            'uri': f'{law_uri}/art_{article_num}/{lang}',
                            'law_uri': law_uri,
                            'number': str(article_num),
                            'number_normalized': article_num,
                            'position': article_num,
                            'parent_id': law_uri,
                            'content_uri': f'{law_uri}/art_{article_num}/content/{lang}',
                            'ast_level': 6,
                            'ast_path': f'/sr_{law_uri.split("/")[-1]}/art_{article_num}/{lang}',
                            'language': lang,
                            'content_full': content['text'],
                            'title': content.get('title', ''),
                            'content_preview': content['text'][:500] if content['text'] else '',
                            'word_count': len(content['text'].split()) if content['text'] else 0
                        }

                        # Extract section/chapter if present in title
                        if article_data.get('title'):
                            article_data['section'] = self._extract_section_from_title(article_data['title'])
                            article_data['chapter'] = self._extract_chapter_from_title(article_data['title'])
                        else:
                            article_data['section'] = None
                            article_data['chapter'] = None

                        article_nodes.append(article_data)

        return article_nodes

    def _extract_article_from_html(self, html_path: Path, article_num: int,
                                   lang: str) -> Optional[Dict]:
        """Extract specific article from HTML file"""
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'lxml')

            # Find all article elements
            articles = soup.find_all('article')

            for article in articles:
                # Check if this is the article we're looking for
                article_text = article.get_text()
                if re.search(rf'Art\.\s+{article_num}\b', article_text):
                    # Extract title (first line with Art.)
                    lines = article_text.strip().split('\n')
                    title = ''
                    content_lines = []

                    for line in lines:
                        line = line.strip()
                        if line:
                            if f'Art. {article_num}' in line:
                                title = line
                            else:
                                content_lines.append(line)

                    return {
                        'title': title,
                        'text': '\n'.join(content_lines),
                        'language': lang
                    }

        except Exception as e:
            logger.error(f"Error extracting article from {html_path}: {e}")

        return None

    def _extract_section_from_title(self, title: str) -> Optional[str]:
        """Extract section information from article title"""
        # Look for patterns like "Abschnitt:" or "Section:"
        section_patterns = [
            r'Abschnitt:\s*(.+?)(?:\s|$)',
            r'Section:\s*(.+?)(?:\s|$)',
            r'Sezione:\s*(.+?)(?:\s|$)'
        ]

        for pattern in section_patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1).strip()

        return None

    def _extract_chapter_from_title(self, title: str) -> Optional[str]:
        """Extract chapter information from article title"""
        # Look for patterns like "Kapitel:" or "Chapter:"
        chapter_patterns = [
            r'Kapitel:\s*(.+?)(?:\s|$)',
            r'Chapter:\s*(.+?)(?:\s|$)',
            r'Chapitre:\s*(.+?)(?:\s|$)',
            r'Capitolo:\s*(.+?)(?:\s|$)'
        ]

        for pattern in chapter_patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1).strip()

        return None

    def extract_paragraphs_for_article(self, article_uri: str, article_text: str,
                                      language: str) -> List[Dict]:
        """
        Extract paragraphs from article text in a specific language.

        Args:
            article_uri: Article URI
            article_text: Article text content
            language: Language code

        Returns:
            List of paragraph dictionaries for this language
        """
        paragraphs = []

        if not article_text:
            return paragraphs

        # Parse numbered paragraphs
        para_pattern = r'^(\d+)\s+(.+?)(?=^\d+\s+|\Z)'
        matches = re.findall(para_pattern, article_text, re.MULTILINE | re.DOTALL)

        if not matches:
            # No numbered paragraphs, treat whole content as single paragraph
            para_text = article_text.strip()
            if para_text:
                has_subpoints = self._check_for_subpoints(para_text)
                subpoint_count = self._count_subpoints(para_text) if has_subpoints else 0

                paragraphs.append({
                    'uri': f"{article_uri}/para_1",
                    'article_uri': article_uri,
                    'number': '1',
                    'position': 1,
                    'text': para_text,
                    'language': language,
                    'word_count': len(para_text.split()),
                    'has_subpoints': has_subpoints,
                    'subpoint_count': subpoint_count,
                    'ast_level': 7,
                    'ast_path': f"{article_uri}/para_1",
                    'type': 'Paragraph'
                })
        else:
            # Process each numbered paragraph
            for para_num, para_text in matches:
                para_text = para_text.strip()
                if para_text:
                    has_subpoints = self._check_for_subpoints(para_text)
                    subpoint_count = self._count_subpoints(para_text) if has_subpoints else 0

                    paragraphs.append({
                        'uri': f"{article_uri}/para_{para_num}",
                        'article_uri': article_uri,
                        'number': para_num,
                        'position': int(para_num),
                        'text': para_text,
                        'language': language,
                        'word_count': len(para_text.split()),
                        'has_subpoints': has_subpoints,
                        'subpoint_count': subpoint_count,
                        'ast_level': 7,
                        'ast_path': f"{article_uri}/para_{para_num}",
                        'type': 'Paragraph'
                    })

        return paragraphs

    def _truncate_at_word_boundary(self, text: str, max_length: int) -> str:
        """
        Truncate text at word boundary, not breaking words.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text ending at word boundary
        """
        if len(text) <= max_length:
            return text

        # Find the last space before max_length
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')

        if last_space > 0:
            # Truncate at word boundary
            return truncated[:last_space] + '...'
        else:
            # No space found, truncate at max_length
            return truncated + '...'

    def _check_for_subpoints(self, text: str) -> bool:
        """Check if paragraph text contains subpoints"""
        subpoint_pattern = r'^\s*[a-z]\.\s+'
        return bool(re.search(subpoint_pattern, text, re.MULTILINE))

    def _count_subpoints(self, text: str) -> int:
        """Count the number of subpoints in paragraph text"""
        subpoint_pattern = r'^\s*([a-z])\.\s+(.+?)(?=^\s*[a-z]\.\s+|^\s*\d+\s+|\Z)'
        matches = re.findall(subpoint_pattern, text, re.MULTILINE | re.DOTALL)
        return len(matches)

    def extract_subpoints_from_paragraph(self, paragraph_uri: str, paragraph_text: str,
                                        language: str) -> List[Dict]:
        """
        Extract subpoints from a paragraph that has lettered items (a., b., c., etc.).

        Args:
            paragraph_uri: Paragraph URI
            paragraph_text: Paragraph text content
            language: Language code

        Returns:
            List of subpoint dictionaries
        """
        subpoints = []

        if not self._check_for_subpoints(paragraph_text):
            return subpoints

        # Extract lettered subpoints
        subpoint_pattern = r'^\s*([a-z])\.\s+(.+?)(?=^\s*[a-z]\.\s+|^\s*\d+\s+|\Z)'
        matches = re.findall(subpoint_pattern, paragraph_text, re.MULTILINE | re.DOTALL)

        for letter, text in matches:
            text = text.strip()
            if text:
                subpoints.append({
                    'uri': f"{paragraph_uri}/subpoint_{letter}",
                    'paragraph_uri': paragraph_uri,
                    'letter': letter,
                    'text': text,
                    'language': language,
                    'position': ord(letter) - ord('a') + 1,  # a=1, b=2, etc.
                    'word_count': len(text.split()),
                    'ast_level': 8,
                    'ast_path': f"{paragraph_uri}/subpoint_{letter}",
                    'type': 'Subpoint'
                })

        return subpoints

    def extract_paragraphs_multilingual(self, article_uri: str,
                                       article_content_by_lang: Dict) -> List[Dict]:
        """
        Extract paragraphs from article in all languages.
        DEPRECATED: Use extract_paragraphs_for_article instead

        Args:
            article_uri: Article URI
            article_content_by_lang: Content by language from extract_article_multilingual

        Returns:
            List of paragraph dictionaries with language tags
        """
        paragraphs = []

        for lang, content in article_content_by_lang.items():
            if not content or not content.get('text'):
                continue

            # Parse numbered paragraphs
            para_pattern = r'^(\d+)\s+(.+?)(?=^\d+\s+|\Z)'
            matches = re.findall(para_pattern, content['text'],
                               re.MULTILINE | re.DOTALL)

            if not matches:
                # No numbered paragraphs, treat whole content as single paragraph
                para_text = content['text'].strip()
                if para_text:
                    paragraphs.append(self._create_paragraph_node(
                        article_uri, '1', para_text, lang, 1
                    ))
            else:
                # Process each numbered paragraph
                for para_num, para_text in matches:
                    para_text = para_text.strip()
                    if para_text:
                        paragraphs.append(self._create_paragraph_node(
                            article_uri, para_num, para_text, lang, int(para_num)
                        ))

        return paragraphs

    def _create_paragraph_node(self, article_uri: str, para_num: str,
                              para_text: str, lang: str, position: int) -> Dict:
        """Create a paragraph node with all required properties"""
        # Check for subpoints
        subpoint_pattern = r'^[a-z]\.\s+'
        has_subpoints = bool(re.search(subpoint_pattern, para_text, re.MULTILINE))

        # Count subpoints if present
        subpoint_count = 0
        if has_subpoints:
            subpoints = re.findall(r'^([a-z])\.\s+(.+?)(?=^[a-z]\.\s+|^\d+\s+|\Z)',
                                 para_text, re.MULTILINE | re.DOTALL)
            subpoint_count = len(subpoints)

        return {
            'uri': f'{article_uri}/para_{para_num}/{lang}',
            'article_uri': article_uri,
            'number': para_num,
            'text': para_text,
            'language': lang,
            'position': position,
            'parent_id': article_uri,
            'word_count': len(para_text.split()),
            'has_subpoints': has_subpoints,
            'subpoint_count': subpoint_count,
            'ast_level': 7,
            'ast_path': f'{article_uri}/para_{para_num}'
        }


# Convenience functions for backward compatibility
_extractor = FedlexPropertyExtractor()

def extract_law_properties(data: Dict, file_path: Optional[Path] = None) -> Dict[str, Any]:
    """Extract all LawNode properties from Fedlex data"""
    return _extractor.extract_law_properties(data, file_path)

def extract_article_multilingual(article_num: int, law_uri: str,
                                fedlex_path: Path) -> Dict[str, Any]:
    """Extract article from all available language versions"""
    return _extractor.extract_article_multilingual(article_num, law_uri, fedlex_path)

def extract_paragraphs_multilingual(article_uri: str,
                                   article_content_by_lang: Dict) -> List[Dict]:
    """Extract paragraphs from article in all languages"""
    return _extractor.extract_paragraphs_multilingual(article_uri, article_content_by_lang)

def extract_sr_from_taxonomy(taxonomy_uri: str) -> Optional[str]:
    """Extract SR number from taxonomy URI"""
    return _extractor.extract_sr_from_taxonomy(taxonomy_uri)

def extract_sr_from_uri(uri: str) -> Optional[str]:
    """Extract SR number from law URI"""
    return _extractor.extract_sr_from_uri(uri)