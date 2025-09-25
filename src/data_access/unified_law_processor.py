"""
Unified Law Processor for LAWAST

This module processes laws by combining JSON metadata with HTML content,
ensuring that Law nodes are only created when there's actual content to store.
It processes each law completely before moving to the next one.

Architecture:
1. Process each law with its JSON + HTML together
2. Extract and store taxonomy once at the end
3. Create all relationships properly
4. Add Language and Manifestation nodes
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime

from .neo4j_connection import Neo4jConnectionManager, get_connection
from .graph_schema import (
    LawNode, ArticleNode, VersionNode, ActNode,
    LanguageNode, ManifestationNode,
    NodeLabels, RelationshipTypes,
    TaxonomyNode, DomainNode, BookNode, ChapterNode, SectionNode
)
from ..parsers.unified_html_parser import UnifiedHtmlParser
from ..extractors.article_extractor import ArticleExtractor, Article
from ..extractors.taxonomy_extractor import TaxonomyExtractor
from ..extractors.reference_patterns import ReferencePatternDetector
from ..extractors.extracted_content import ExtractedContent
from ..extractors.sr_taxonomy_generator import SRTaxonomyGenerator

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Statistics for the unified processing pipeline"""
    laws_processed: int = 0
    articles_created: int = 0
    versions_created: int = 0
    acts_created: int = 0
    taxonomy_nodes_created: int = 0
    relationships_created: int = 0
    languages_created: int = 0
    manifestations_created: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class UnifiedLawProcessor:
    """
    Processes laws by combining JSON metadata with HTML content.
    Ensures data integrity by processing each law completely before moving on.
    """

    def __init__(
        self,
        json_dir: str = "fedlex",
        html_dir: str = "fedlex-assets",
        connection: Optional[Neo4jConnectionManager] = None,
        batch_size: int = 1000
    ):
        """
        Initialize the unified processor.

        Args:
            json_dir: Directory containing JSON files
            html_dir: Directory containing HTML files
            connection: Neo4j connection manager
            batch_size: Batch size for Neo4j operations
        """
        self.json_dir = Path(json_dir)
        self.html_dir = Path(html_dir)
        self.connection = connection or get_connection()
        self.batch_size = batch_size

        # Initialize extractors
        self.html_parser = UnifiedHtmlParser()
        self.article_extractor = ArticleExtractor()
        self.taxonomy_extractor = TaxonomyExtractor()
        self.reference_detector = ReferencePatternDetector()
        self.sr_taxonomy_generator = SRTaxonomyGenerator()

        self.stats = ProcessingStats(start_time=datetime.now())

        # Collections for deferred processing
        self.all_references = []
        self.taxonomy_data = None
        self.processed_law_uris = set()
        self.collected_sr_numbers = set()  # Collect SR numbers for taxonomy generation

    def process_all_laws(self, limit: Optional[int] = None) -> ProcessingStats:
        """
        Main entry point to process all laws.

        Args:
            limit: Maximum number of laws to process (for testing)

        Returns:
            Processing statistics
        """
        try:
            logger.info("Starting unified law processing pipeline")

            # Phase 1: Process laws with their content
            self._process_laws_with_content(limit)

            # Phase 2: Extract and store taxonomy (once)
            self._process_taxonomy()

            # Phase 3: Connect articles to taxonomy
            self._connect_articles_to_taxonomy()

            # Phase 4: Process all references
            self._process_references()

            # Phase 5: Create language and manifestation nodes
            self._create_language_manifestation_nodes()

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.stats.errors.append({
                "type": "pipeline_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            raise
        finally:
            self.stats.end_time = datetime.now()
            self._report_statistics()

        return self.stats

    def _process_laws_with_content(self, limit: Optional[int] = None):
        """Process each law with its JSON metadata and HTML content together."""
        logger.info("Phase 1: Processing laws with content")

        # ONLY process laws that have BOTH JSON and HTML
        # This avoids creating orphaned nodes and focuses on the ~5,700 active laws
        laws_with_both = []

        logger.info("Finding laws with both JSON and HTML content...")

        # Optimize: First find HTML directories, then check for JSON
        # This is faster since there are fewer HTML directories (~5,700) than JSON files (~17,000)
        html_law_dirs = set()
        for html_file in self.html_dir.glob("eli/cc/**/html/*.html"):
            # Extract law directory path
            parts = html_file.parts
            if 'eli' in parts and 'cc' in parts:
                eli_idx = parts.index('eli')
                cc_idx = parts.index('cc')

                # Find where version/date starts
                law_parts = ['eli', 'cc']
                for i in range(cc_idx + 1, len(parts)):
                    if parts[i] in ['de', 'fr', 'it', 'rm', 'html'] or (parts[i].isdigit() and len(parts[i]) == 8):
                        break
                    law_parts.append(parts[i])

                if len(law_parts) > 2:  # Has actual law identifier
                    html_law_dirs.add('/'.join(law_parts))

        logger.info(f"Found {len(html_law_dirs)} law directories with HTML")

        # Now check which have JSON
        for law_path in html_law_dirs:
            # The main JSON file might be at parent level or in the directory
            json_found = False

            # First check in the law directory itself
            json_path = self.json_dir / law_path
            if json_path.exists():
                json_files = [f for f in json_path.glob("*.json")
                             if not (f.stem.isdigit() and len(f.stem) == 8)]
                if json_files:
                    laws_with_both.append(json_files[0])
                    json_found = True
                    logger.debug(f"Found law with both (in dir): {law_path}")

            # If not found, check parent directory for a JSON file with the law name
            if not json_found:
                # Extract law identifier (last part of path)
                law_parts = law_path.split('/')
                if len(law_parts) > 2:  # eli/cc/something
                    law_id = law_parts[-1]  # e.g., "35_37_37" or "754"
                    parent_path = '/'.join(law_parts[:-1])  # e.g., "eli/cc/X" or "eli/cc/2023"

                    parent_dir = self.json_dir / parent_path
                    if parent_dir.exists():
                        json_file = parent_dir / f"{law_id}.json"
                        if json_file.exists():
                            laws_with_both.append(json_file)
                            logger.debug(f"Found law with both (at parent): {law_path}")

        logger.info(f"Found {len(laws_with_both)} laws with both JSON and HTML")

        if limit:
            laws_with_both = laws_with_both[:limit]
            logger.info(f"Limited to {limit} laws for processing")

        logger.info(f"Processing {len(laws_with_both)} laws with complete data")

        for law_file in laws_with_both:
            try:
                # Load law metadata from JSON
                with open(law_file, 'r', encoding='utf-8') as f:
                    law_data = json.load(f)

                # Check for URI in different possible locations
                law_uri = None
                if 'data' in law_data:
                    if isinstance(law_data['data'], dict):
                        law_uri = law_data['data'].get('uri')
                        if not law_uri and 'attributes' in law_data['data']:
                            law_uri = law_data['data']['attributes'].get('eli')

                if not law_uri:
                    logger.warning(f"No URI found in {law_file}")
                    continue

                if law_uri in self.processed_law_uris:
                    logger.debug(f"Skipping already processed law: {law_uri}")
                    continue

                # Find corresponding HTML files
                html_files = self._find_html_files_for_law(law_uri)

                if not html_files:
                    logger.debug(f"No HTML files found for {law_uri}, skipping")
                    continue

                # Process this law completely
                self._process_single_law(law_data, html_files, law_file)

                self.processed_law_uris.add(law_uri)
                self.stats.laws_processed += 1

                if self.stats.laws_processed % 100 == 0:
                    logger.info(f"Processed {self.stats.laws_processed} laws")

            except Exception as e:
                logger.error(f"Failed to process law {law_file}: {e}")
                self.stats.errors.append({
                    "type": "law_processing",
                    "file": str(law_file),
                    "error": str(e)
                })

    def _find_html_files_for_law(self, law_uri: str) -> List[Path]:
        """
        Find HTML files corresponding to a law URI.

        Args:
            law_uri: The law's Fedlex URI

        Returns:
            List of HTML file paths
        """
        # Convert URI to file path pattern
        # e.g., https://fedlex.data.admin.ch/eli/cc/2001/78 -> eli/cc/2001/78
        uri_parts = law_uri.replace("https://fedlex.data.admin.ch/", "").split("/")

        # Look for HTML files in the expected directory structure
        search_pattern = self.html_dir / Path(*uri_parts)

        html_files = []
        if search_pattern.exists():
            # Find all HTML files in version directories
            html_files = list(search_pattern.glob("**/html/*.html"))

        return html_files

    def _process_single_law(self, law_data: Dict[str, Any], html_files: List[Path], law_file: Path):
        """
        Process a single law with all its data.

        Args:
            law_data: JSON data for the law
            html_files: List of HTML files for this law
            law_file: Path to the law JSON file
        """
        # Extract law URI first
        data = law_data.get('data', {})
        if isinstance(data, dict):
            law_uri = data.get('uri')
            if not law_uri and 'attributes' in data:
                law_uri = data['attributes'].get('eli')
        else:
            logger.warning("No valid data structure in law JSON")
            return

        if not law_uri:
            logger.warning("No URI found in law data")
            return

        # Extract law metadata
        attrs = data.get('attributes', {}) if isinstance(data, dict) else {}

        # Helper to extract value from dict properties
        def extract_value(prop):
            if isinstance(prop, dict):
                # Extract from {'xsd:string': 'text'}, {'xsd:date': '2023-01-01'} or {'rdfs:Resource': 'uri'}
                return prop.get('xsd:string') or prop.get('xsd:date') or prop.get('rdfs:Resource') or prop.get('value')
            return prop

        # Extract SR number from taxonomy classification
        sr_number = None
        if 'references' in data:
            classified = data['references'].get('classifiedByTaxonomyEntry')
            if classified and isinstance(classified, str) and 'legal-taxonomy' in classified:
                # Extract taxonomy ID from URL: https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/4849
                taxonomy_id = classified.split('/')[-1]
                if taxonomy_id and taxonomy_id.isdigit():
                    # Convert taxonomy ID to SR format (e.g., 4849 -> 4.8.4.9)
                    sr_number = '.'.join(taxonomy_id)
                    self.collected_sr_numbers.add(sr_number)
                    logger.debug(f"Extracted SR {sr_number} from taxonomy {taxonomy_id}")

        # Extract titles from Expression in included section
        titles = {'de': None, 'fr': None, 'it': None, 'rm': None}
        included = law_data.get('included', [])
        for item in included:
            if item.get('type') == 'Expression':
                expr_attrs = item.get('attributes', {})
                # Try to get title from various fields
                title = extract_value(expr_attrs.get('title')) or \
                        extract_value(expr_attrs.get('titleShort')) or \
                        extract_value(expr_attrs.get('titleAlternative'))

                if title:
                    # Extract language from references.language field
                    lang_ref = item.get('references', {}).get('language', '')

                    # Map language URI to language code
                    if 'DEU' in lang_ref:
                        titles['de'] = title
                    elif 'FRA' in lang_ref:
                        titles['fr'] = title
                    elif 'ITA' in lang_ref:
                        titles['it'] = title
                    elif 'ROH' in lang_ref:
                        titles['rm'] = title
                    else:
                        # Fallback: Try to detect language from title content if no explicit language
                        # German indicators
                        if not titles['de'] and any(word in title.lower() for word in ['verordnung', 'gesetz', 'vom', 'über', 'des', 'der']):
                            titles['de'] = title
                        # French indicators
                        elif not titles['fr'] and any(word in title.lower() for word in ['ordonnance', 'loi', 'du', 'sur', 'des', 'concernant']):
                            titles['fr'] = title
                        # Italian indicators
                        elif not titles['it'] and any(word in title.lower() for word in ['ordinanza', 'legge', 'del', 'sui', 'sulla', 'dei', 'concernente']):
                            titles['it'] = title

        # Determine in_force status based on dates
        date_no_longer = extract_value(attrs.get('dateNoLongerInForce'))
        in_force_status = date_no_longer is None  # If no end date, it's in force

        # Create Law node
        law_node = LawNode(
            uri=law_uri,
            sr_number=sr_number,
            title_de=titles['de'],
            title_fr=titles['fr'],
            title_it=titles['it'],
            title_rm=titles.get('rm'),  # Add Romansh title if available
            date_document=extract_value(attrs.get('dateDocument')),
            date_entry_in_force=extract_value(attrs.get('dateEntryInForce')),
            date_no_longer_in_force=date_no_longer,
            in_force=in_force_status,
            type_document=extract_value(attrs.get('typeDocument'))
        )

        # Store law node
        self._create_law_node(law_node)

        # Process versions from JSON
        self._process_versions_for_law(law_file, law_uri)

        # Process acts from JSON
        self._process_acts_for_law(law_data, law_uri)

        # Process HTML files to extract articles
        # Use a dict to deduplicate articles by number while merging titles
        articles_dict = {}
        for html_file in html_files:
            extracted_articles = self._extract_articles_from_html(html_file, law_uri)
            for article in extracted_articles:
                if article.number_normalized not in articles_dict:
                    # First occurrence - store the article
                    articles_dict[article.number_normalized] = article
                else:
                    # Merge titles from different language versions
                    existing = articles_dict[article.number_normalized]
                    for lang, title in article.titles.items():
                        if lang not in existing.titles:
                            existing.titles[lang] = title

        articles = list(articles_dict.values())

        if articles:
            # Store articles and create relationships
            self._store_articles_with_relationships(articles, law_uri)
            self.stats.articles_created += len(articles)

            # Collect references for later processing
            for article in articles:
                # Check in metadata for references
                if hasattr(article, 'metadata') and article.metadata.get('references'):
                    for ref in article.metadata['references']:
                        ref['source_uri'] = article.uri
                        ref['law_uri'] = law_uri
                        self.all_references.append(ref)

    def _create_law_node(self, law: LawNode):
        """Create a Law node in Neo4j."""
        query = f"""
        MERGE (l:{NodeLabels.LAW.value} {{uri: $uri}})
        SET l += $properties
        """
        properties = law.to_cypher_properties()
        self.connection.execute_write(query, {"uri": law.uri, "properties": properties})

    def _process_versions_for_law(self, law_file: Path, law_uri: str):
        """Process and store version nodes for a law."""
        # Version files are in a subdirectory named after the law
        # e.g., law file: fedlex/eli/cc/1979/2598_2603_2603.json
        #       versions: fedlex/eli/cc/1979/2598_2603_2603/19800101.json
        law_version_dir = law_file.parent / law_file.stem

        version_files = []
        if law_version_dir.exists():
            # Look for date-named JSON files like 20230101.json
            for json_file in law_version_dir.glob("*.json"):
                if json_file.stem.isdigit() and len(json_file.stem) == 8:
                    version_files.append(json_file)

        if version_files:
            logger.info(f"Found {len(version_files)} version files for {law_uri}")

        for version_file in version_files:
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    version_data = json.load(f)

                # Extract version URI
                version_uri = None
                if 'data' in version_data and isinstance(version_data['data'], dict):
                    version_uri = version_data['data'].get('uri')
                    attrs = version_data['data'].get('attributes', {})
                else:
                    attrs = {}

                if version_uri:
                    # Create version node
                    query = f"""
                    MERGE (v:{NodeLabels.VERSION.value} {{uri: $uri}})
                    SET v += $properties
                    WITH v
                    MATCH (l:{NodeLabels.LAW.value} {{uri: $law_uri}})
                    MERGE (l)-[:{RelationshipTypes.HAS_VERSION.value}]->(v)
                    """
                    # Extract date values properly
                    def extract_date(date_prop):
                        if isinstance(date_prop, dict) and 'xsd:date' in date_prop:
                            return date_prop['xsd:date']
                        return date_prop

                    properties = {
                        "uri": version_uri,
                        "law_uri": law_uri,
                        "date_applicable": extract_date(attrs.get('dateApplicability')),
                        "date_end_applicable": extract_date(attrs.get('dateEndApplicability'))
                    }
                    self.connection.execute_write(query, {
                        "uri": version_uri,
                        "law_uri": law_uri,
                        "properties": properties
                    })
                    self.stats.versions_created += 1

            except Exception as e:
                logger.error(f"Failed to process version {version_file}: {e}")

    def _process_acts_for_law(self, law_data: Dict[str, Any], law_uri: str):
        """Process and store act nodes for a law."""
        # Implementation would process OC/AS/RO files
        # Similar to versions but for legislative acts
        pass

    def _extract_articles_from_html(self, html_file: Path, law_uri: str) -> List[Article]:
        """
        Extract articles from an HTML file.

        Args:
            html_file: Path to HTML file
            law_uri: URI of the parent law

        Returns:
            List of extracted articles
        """
        try:
            # Parse HTML
            parsed = self.html_parser.parse(str(html_file))

            # Extract articles with file path for language detection
            result = self.article_extractor.extract(parsed, file_path=str(html_file))

            if result and result.data:
                articles = result.data
                # Set law_uri and generate proper URIs for all articles
                for article in articles:
                    article.metadata['law_uri'] = law_uri
                    # Generate proper article URI based on law URI
                    if not article.uri.startswith('http'):
                        article.uri = f"{law_uri}/art_{article.number_normalized}"
                return articles

        except Exception as e:
            logger.error(f"Failed to extract articles from {html_file}: {e}")

        return []

    def _store_articles_with_relationships(self, articles: List[Article], law_uri: str):
        """Store articles and create HAS_ARTICLE relationships."""
        if not articles:
            return

        # Batch create articles
        article_data = []
        for article in articles:
            node_data = {
                "uri": article.uri,
                "number": article.number,
                "number_normalized": article.number_normalized,
                "law_uri": law_uri
            }

            # Add titles
            for lang, title in article.titles.items():
                node_data[f"title_{lang}"] = title

            # Add content summary
            if article.content and article.content.paragraphs:
                node_data["paragraphs_count"] = len(article.content.paragraphs)
                node_data["content_preview"] = article.content.paragraphs[0].text[:500]

            article_data.append(node_data)

        # Create articles and relationships in one query
        query = f"""
        UNWIND $articles AS article
        MERGE (a:{NodeLabels.ARTICLE.value} {{uri: article.uri}})
        SET a += article
        WITH a, article
        MATCH (l:{NodeLabels.LAW.value} {{uri: $law_uri}})
        MERGE (l)-[:{RelationshipTypes.HAS_ARTICLE.value}]->(a)
        """

        self.connection.execute_write(query, {
            "articles": article_data,
            "law_uri": law_uri
        })

        # Create FOLLOWS relationships between sequential articles
        if len(articles) > 1:
            sorted_articles = sorted(articles, key=lambda a: a.number_normalized)

            follows_data = []
            for i in range(len(sorted_articles) - 1):
                follows_data.append({
                    "from_uri": sorted_articles[i].uri,
                    "to_uri": sorted_articles[i + 1].uri
                })

            if follows_data:
                query = f"""
                UNWIND $rels AS rel
                MATCH (a1:{NodeLabels.ARTICLE.value} {{uri: rel.from_uri}})
                MATCH (a2:{NodeLabels.ARTICLE.value} {{uri: rel.to_uri}})
                MERGE (a1)-[:{RelationshipTypes.FOLLOWS.value}]->(a2)
                """
                self.connection.execute_write(query, {"rels": follows_data})

    def _process_taxonomy(self):
        """Generate and store SR taxonomy from collected SR numbers."""
        logger.info("Phase 2: Processing taxonomy")

        if not self.collected_sr_numbers:
            logger.warning("No SR numbers collected to generate taxonomy")
            return

        logger.info(f"Generating taxonomy from {len(self.collected_sr_numbers)} SR numbers")

        try:
            # Generate complete taxonomy structure from SR numbers
            taxonomy_nodes = {}
            taxonomy_relationships = []

            for sr_number in self.collected_sr_numbers:
                # Parse SR number to get hierarchical components
                parsed = self.sr_taxonomy_generator.parse_sr_number(sr_number)

                if not parsed or not parsed.get('domain'):
                    continue

                # Create domain node
                domain = parsed['domain']
                domain_uri = f"taxonomy/domain/{domain}"
                if domain_uri not in taxonomy_nodes:
                    domain_name = (self.sr_taxonomy_generator.DOMAIN_MAPPING.get(domain) or
                                  self.sr_taxonomy_generator.ROMAN_DOMAIN_MAPPING.get(domain, f"Domain {domain}"))
                    taxonomy_nodes[domain_uri] = {
                        'type': 'Domain',
                        'uri': domain_uri,
                        'number': domain,
                        'name': domain_name,
                        'title_de': domain_name,
                        'title_fr': domain_name,
                        'title_it': domain_name
                    }

                # Create book node if exists
                if parsed.get('book'):
                    book = parsed['book']
                    book_uri = f"taxonomy/book/{domain}.{book}"
                    if book_uri not in taxonomy_nodes:
                        taxonomy_nodes[book_uri] = {
                            'type': 'Book',
                            'uri': book_uri,
                            'number': f"{domain}.{book}",
                            'name': f"Book {domain}.{book}",
                            'title_de': f"Titel {domain}.{book}",
                            'title_fr': f"Titre {domain}.{book}",
                            'title_it': f"Titolo {domain}.{book}",
                            'parent_uri': domain_uri
                        }
                        # Add relationship
                        taxonomy_relationships.append({
                            'from_uri': domain_uri,
                            'to_uri': book_uri
                        })

                # Create chapter node if exists
                if parsed.get('chapter'):
                    chapter = parsed['chapter']
                    chapter_uri = f"taxonomy/chapter/{domain}.{book}.{chapter}"
                    if chapter_uri not in taxonomy_nodes:
                        taxonomy_nodes[chapter_uri] = {
                            'type': 'Chapter',
                            'uri': chapter_uri,
                            'number': f"{domain}.{book}.{chapter}",
                            'name': f"Chapter {domain}.{book}.{chapter}",
                            'title_de': f"Kapitel {domain}.{book}.{chapter}",
                            'title_fr': f"Chapitre {domain}.{book}.{chapter}",
                            'title_it': f"Capitolo {domain}.{book}.{chapter}",
                            'parent_uri': book_uri
                        }
                        # Add relationship
                        taxonomy_relationships.append({
                            'from_uri': book_uri,
                            'to_uri': chapter_uri
                        })

                # Create section node if exists
                if parsed.get('section'):
                    section = parsed['section']
                    parent_uri = chapter_uri if parsed.get('chapter') else book_uri if parsed.get('book') else domain_uri
                    section_uri = f"taxonomy/section/{sr_number.replace(' ', '_')}"
                    if section_uri not in taxonomy_nodes:
                        taxonomy_nodes[section_uri] = {
                            'type': 'Section',
                            'uri': section_uri,
                            'number': sr_number,
                            'name': f"Section {sr_number}",
                            'title_de': f"Abschnitt {sr_number}",
                            'title_fr': f"Section {sr_number}",
                            'title_it': f"Sezione {sr_number}",
                            'parent_uri': parent_uri
                        }
                        # Add relationship
                        taxonomy_relationships.append({
                            'from_uri': parent_uri,
                            'to_uri': section_uri
                        })

            # Store taxonomy nodes and relationships
            self._store_generated_taxonomy(taxonomy_nodes, taxonomy_relationships)

        except Exception as e:
            logger.error(f"Failed to generate taxonomy: {e}")
            self.stats.errors.append({
                "type": "taxonomy_generation",
                "error": str(e)
            })

    def _store_generated_taxonomy(self, taxonomy_nodes: Dict[str, Any], taxonomy_relationships: List[Dict[str, Any]]):
        """Store the generated taxonomy nodes and relationships."""
        if not taxonomy_nodes:
            logger.warning("No taxonomy nodes to store")
            return

        # Group nodes by type
        nodes_by_type = {}
        for node_data in taxonomy_nodes.values():
            node_type = node_data['type']
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node_data)

        # Store nodes by type
        for node_type, nodes in nodes_by_type.items():
            label = self._get_taxonomy_label(node_type)

            query = f"""
            UNWIND $nodes AS node
            MERGE (n:{label} {{uri: node.uri}})
            SET n += node
            RETURN count(n) as created
            """

            try:
                result = self.connection.execute_write(query, {"nodes": nodes})
                if result:
                    created = result[0]['created']
                    self.stats.taxonomy_nodes_created += created
                    logger.info(f"Created {created} {node_type} nodes")
            except Exception as e:
                logger.error(f"Failed to create {node_type} nodes: {e}")

        # Create CONTAINS relationships
        if taxonomy_relationships:
            query = f"""
            UNWIND $rels AS rel
            MATCH (parent {{uri: rel.from_uri}})
            MATCH (child {{uri: rel.to_uri}})
            MERGE (parent)-[:{RelationshipTypes.CONTAINS.value}]->(child)
            RETURN count(*) as created
            """

            try:
                result = self.connection.execute_write(query, {"rels": taxonomy_relationships})
                if result:
                    created = result[0]['created']
                    self.stats.relationships_created += created
                    logger.info(f"Created {created} CONTAINS relationships")
            except Exception as e:
                logger.error(f"Failed to create taxonomy relationships: {e}")

    def _store_taxonomy_hierarchy(self, taxonomy):
        """Store the complete taxonomy hierarchy."""
        if not taxonomy or not hasattr(taxonomy, 'hierarchy'):
            return

        nodes_to_create = []
        relationships_to_create = []

        # Process hierarchy recursively
        def process_level(level, parent_uri=None):
            # Create node data
            node_uri = level.uri or f"taxonomy/{level.type}/{level.number}"
            node_data = {
                "uri": node_uri,
                "type": level.type,
                "number": level.number,
                "name": level.title.get("de", level.title.get("fr", level.title.get("it", "")))
            }

            # Add multi-language titles
            for lang, title in level.title.items():
                node_data[f"title_{lang}"] = title

            nodes_to_create.append((level.type, node_data))

            # Create relationship to parent
            if parent_uri:
                relationships_to_create.append({
                    "from_uri": parent_uri,
                    "to_uri": node_uri,
                    "type": RelationshipTypes.CONTAINS.value
                })

            # Process children
            for child in level.children:
                process_level(child, node_uri)

        # Process all hierarchy levels
        for level in taxonomy.hierarchy:
            process_level(level)

        # Create nodes by type
        nodes_by_type = {}
        for node_type, node_data in nodes_to_create:
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node_data)

        # Store nodes
        for node_type, nodes in nodes_by_type.items():
            label = self._get_taxonomy_label(node_type)

            query = f"""
            UNWIND $nodes AS node
            MERGE (n:{label} {{uri: node.uri}})
            SET n += node
            """

            self.connection.execute_write(query, {"nodes": nodes})
            self.stats.taxonomy_nodes_created += len(nodes)

        # Create relationships
        if relationships_to_create:
            query = f"""
            UNWIND $rels AS rel
            MATCH (parent {{uri: rel.from_uri}})
            MATCH (child {{uri: rel.to_uri}})
            MERGE (parent)-[:{RelationshipTypes.CONTAINS.value}]->(child)
            """
            self.connection.execute_write(query, {"rels": relationships_to_create})
            self.stats.relationships_created += len(relationships_to_create)

    def _get_taxonomy_label(self, node_type: str) -> str:
        """Get the Neo4j label for a taxonomy type."""
        label_map = {
            "Domain": NodeLabels.DOMAIN.value,
            "Book": NodeLabels.BOOK.value,
            "Chapter": NodeLabels.CHAPTER.value,
            "Section": NodeLabels.SECTION.value
        }
        return label_map.get(node_type, NodeLabels.SECTION.value)

    def _connect_articles_to_taxonomy(self):
        """Connect laws to their taxonomy sections based on SR numbers."""
        logger.info("Phase 3: Connecting laws to taxonomy sections")

        # Connect each law to its section based on SR number
        query = f"""
        MATCH (l:{NodeLabels.LAW.value})
        WHERE l.sr_number IS NOT NULL
        MATCH (s:{NodeLabels.SECTION.value})
        WHERE s.number = l.sr_number
        MERGE (l)-[:{RelationshipTypes.BELONGS_TO.value}]->(s)
        """

        result = self.connection.execute_write(query, {})
        logger.info(f"Connected laws to taxonomy sections")

    def _process_references(self):
        """Process all collected references."""
        logger.info("Phase 4: Processing references")

        if not self.all_references:
            logger.info("No references to process")
            return

        logger.info(f"Processing {len(self.all_references)} references")

        # Debug: Check what's in references
        if self.all_references and len(self.all_references) > 0:
            sample_ref = self.all_references[0]
            logger.debug(f"Sample reference: {sample_ref}")

        # Process references - these are dictionaries from article metadata
        valid_refs = []
        for ref in self.all_references:
            if isinstance(ref, dict):
                # Handle link-based references (with target_uri)
                if ref.get('target_uri'):
                    valid_refs.append({
                        "source_uri": ref.get('source_uri'),
                        "target_uri": ref.get('target_uri'),
                        "type": ref.get('type', 'link')
                    })
                # Handle text-based references (with law/article components)
                elif ref.get('target_law') and ref.get('target_article'):
                    # Internal reference to another article
                    # Normalize article number to match our URI format
                    article_num = str(ref['target_article']).zfill(3)
                    target_uri = f"{ref['target_law']}/art_{article_num}"
                    valid_refs.append({
                        "source_uri": ref.get('source_uri'),
                        "target_uri": target_uri,
                        "type": ref.get('type', 'text')
                    })

        logger.info(f"Found {len(valid_refs)} valid references to create")

        # Create reference relationships (only where both nodes exist)
        if valid_refs:
            created_count = 0
            skipped_count = 0

            for ref in valid_refs:
                try:
                    # Check if both nodes exist before creating relationship
                    check_query = """
                    MATCH (from:Article {uri: $source_uri})
                    MATCH (to:Article {uri: $target_uri})
                    RETURN count(*) as exists
                    """
                    result = self.connection.execute_write(check_query, {
                        "source_uri": ref['source_uri'],
                        "target_uri": ref['target_uri']
                    })

                    if result and result[0]['exists'] > 0:
                        # Both nodes exist, create the relationship
                        create_query = f"""
                        MATCH (from:Article {{uri: $source_uri}})
                        MATCH (to:Article {{uri: $target_uri}})
                        MERGE (from)-[r:{RelationshipTypes.REFERENCES.value}]->(to)
                        SET r.type = $type
                        """
                        self.connection.execute_write(create_query, {
                            "source_uri": ref['source_uri'],
                            "target_uri": ref['target_uri'],
                            "type": ref['type']
                        })
                        created_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.debug(f"Could not create reference: {e}")
                    skipped_count += 1

            self.stats.relationships_created += created_count
            logger.info(f"Created {created_count} reference relationships ({skipped_count} skipped due to missing nodes)")

    def _create_language_manifestation_nodes(self):
        """Create Language and Manifestation nodes."""
        logger.info("Phase 5: Creating Language and Manifestation nodes")

        # Create language nodes
        languages = [
            {"code": "DE", "name": "Deutsch"},
            {"code": "FR", "name": "Français"},
            {"code": "IT", "name": "Italiano"},
            {"code": "RM", "name": "Rumantsch"},
            {"code": "EN", "name": "English"}
        ]

        query = f"""
        UNWIND $languages AS lang
        MERGE (l:{NodeLabels.LANGUAGE.value} {{code: lang.code}})
        SET l.name = lang.name
        """

        self.connection.execute_write(query, {"languages": languages})
        self.stats.languages_created = len(languages)

        # Create manifestation nodes for each law
        # This would track different formats (HTML, PDF, XML) available
        logger.info("Manifestation node creation would be implemented based on available formats")

    def _report_statistics(self):
        """Report processing statistics."""
        logger.info("=" * 60)
        logger.info("Unified Processing Pipeline Statistics:")
        logger.info(f"  Laws processed: {self.stats.laws_processed}")
        logger.info(f"  Articles created: {self.stats.articles_created}")
        logger.info(f"  Versions created: {self.stats.versions_created}")
        logger.info(f"  Acts created: {self.stats.acts_created}")
        logger.info(f"  Taxonomy nodes created: {self.stats.taxonomy_nodes_created}")
        logger.info(f"  Relationships created: {self.stats.relationships_created}")
        logger.info(f"  Languages created: {self.stats.languages_created}")
        logger.info(f"  Manifestations created: {self.stats.manifestations_created}")
        logger.info(f"  Errors encountered: {len(self.stats.errors)}")

        if self.stats.start_time and self.stats.end_time:
            duration = (self.stats.end_time - self.stats.start_time).total_seconds()
            logger.info(f"  Total time: {duration:.1f} seconds")

            if self.stats.laws_processed > 0:
                logger.info(f"  Average time per law: {duration/self.stats.laws_processed:.2f} seconds")

        if self.stats.errors:
            logger.warning("Errors encountered during processing:")
            for error in self.stats.errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error['type']}: {error.get('error')}")

        logger.info("=" * 60)