"""
Graph schema definitions for the LAWAST Neo4j database
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class NodeLabels(Enum):
    """Node type labels in the graph"""
    LAW = "Law"
    VERSION = "Version"
    ACT = "Act"
    ARTICLE = "Article"
    PARAGRAPH = "Paragraph"
    SUBPOINT = "Subpoint"
    LANGUAGE = "Language"
    MANIFESTATION = "Manifestation"
    DOMAIN = "Domain"
    BOOK = "Book"
    CHAPTER = "Chapter"
    SECTION = "Section"


class RelationshipTypes(Enum):
    """Relationship types in the graph"""
    HAS_VERSION = "HAS_VERSION"
    SUPERSEDES = "SUPERSEDES"
    EXPRESSED_IN = "EXPRESSED_IN"
    MANIFESTED_AS = "MANIFESTED_AS"
    AMENDS = "AMENDS"
    REFERENCES = "REFERENCES"
    CONTAINS = "CONTAINS"
    HAS_ARTICLE = "HAS_ARTICLE"
    HAS_PARAGRAPH = "HAS_PARAGRAPH"
    HAS_SUBPOINT = "HAS_SUBPOINT"
    HAS_CHILD = "HAS_CHILD"
    CITES = "CITES"
    FOLLOWS = "FOLLOWS"
    NEXT = "NEXT"
    BELONGS_TO = "BELONGS_TO"


class LanguageCodes(Enum):
    """Supported language codes"""
    GERMAN = "DE"
    FRENCH = "FR"
    ITALIAN = "IT"
    ROMANSH = "RM"
    ENGLISH = "EN"


class ManifestationFormats(Enum):
    """Document format types"""
    HTML = "html"
    PDF = "pdf"
    XML = "xml"
    DOCX = "docx"
    JSON = "json"


@dataclass
class LawNode:
    """
    Represents a Law node in the graph with complete legal metadata
    """
    # Required fields
    uri: str
    sr_number: str

    # Multilingual titles
    title_de: Optional[str] = None
    title_fr: Optional[str] = None
    title_it: Optional[str] = None
    title_rm: Optional[str] = None
    title_en: Optional[str] = None

    # Date fields
    date_document: Optional[str] = None  # Original document date
    date_entry_in_force: Optional[str] = None  # When law became active
    date_no_longer_in_force: Optional[str] = None  # When law was repealed
    date_modified: Optional[datetime] = None  # Last modification date

    # Legal status fields
    in_force: Optional[bool] = None  # Boolean flag for quick filtering
    in_force_status: Optional[str] = None  # URI to enforcement status vocabulary
    status: Optional[str] = None  # General status

    # Legal references
    basic_act: Optional[str] = None  # URI to the original act
    classified_by_taxonomy: Optional[str] = None  # URI to taxonomy classification
    type_document: Optional[str] = None  # URI to document type vocabulary

    # Additional metadata
    type: Optional[str] = None  # Document type
    language: Optional[str] = None  # Primary language
    parent_uri: Optional[str] = None  # For hierarchical laws

    # AST properties
    ast_path: Optional[str] = None  # "/domain_1/section_101/law_101"
    ast_level: int = 5  # Law is level 5
    parent_id: Optional[str] = None  # Section ID

    # RAG properties
    embedding: Optional[List[float]] = None  # For RAG (title embedding)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "sr_number": self.sr_number
        }

        # Add all optional string/bool fields
        optional_fields = [
            'date_document', 'date_entry_in_force', 'date_no_longer_in_force',
            'in_force', 'in_force_status', 'status', 'basic_act',
            'classified_by_taxonomy', 'type_document', 'type',
            'language', 'parent_uri'
        ]

        for field in optional_fields:
            if hasattr(self, field) and getattr(self, field) is not None:
                props[field] = getattr(self, field)

        # Add multilingual titles
        for lang in ["de", "fr", "it", "rm", "en"]:
            title_attr = f"title_{lang}"
            if hasattr(self, title_attr) and getattr(self, title_attr):
                props[title_attr] = getattr(self, title_attr)

        # Add AST properties
        props["ast_level"] = self.ast_level
        if self.ast_path:
            props["ast_path"] = self.ast_path
        if self.parent_id:
            props["parent_id"] = self.parent_id
        if self.embedding:
            props["embedding"] = self.embedding

        # Handle datetime fields
        if self.date_modified:
            props["date_modified"] = self.date_modified.isoformat()

        # Add metadata as individual properties
        for key, value in self.metadata.items():
            if key not in props:
                props[key] = value

        return props


@dataclass
class VersionNode:
    """
    Represents a Version node in the graph
    """
    uri: str
    law_uri: str
    date_applicable: datetime
    date_end_applicable: Optional[datetime] = None
    version_number: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "law_uri": self.law_uri,
            "date_applicable": self.date_applicable.isoformat()
        }

        if self.date_end_applicable:
            props["date_end_applicable"] = self.date_end_applicable.isoformat()
        if self.version_number:
            props["version_number"] = self.version_number

        # Add metadata
        for key, value in self.metadata.items():
            if key not in props:
                props[key] = value

        return props


@dataclass
class ArticleNode:
    """
    Represents an Article node in the graph
    """
    uri: str
    law_uri: str
    number: str  # Can be like "1", "1a", "335b"
    title: Optional[str] = None
    content_uri: Optional[str] = None
    section: Optional[str] = None
    chapter: Optional[str] = None

    # AST properties
    ast_path: Optional[str] = None  # "/law_101/art_10"
    ast_level: int = 6  # Article is level 6
    parent_id: Optional[str] = None  # Law ID
    position: Optional[int] = None  # Order within law

    # RAG properties
    content_full: Optional[str] = None  # Full article text
    embedding: Optional[List[float]] = None  # For RAG

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "law_uri": self.law_uri,
            "number": self.number,
            "ast_level": self.ast_level
        }

        if self.title:
            props["title"] = self.title
        if self.content_uri:
            props["content_uri"] = self.content_uri
        if self.section:
            props["section"] = self.section
        if self.chapter:
            props["chapter"] = self.chapter
        if self.ast_path:
            props["ast_path"] = self.ast_path
        if self.parent_id:
            props["parent_id"] = self.parent_id
        if self.position is not None:
            props["position"] = self.position
        if self.content_full:
            props["content_full"] = self.content_full
        if self.embedding:
            props["embedding"] = self.embedding

        # Add metadata
        for key, value in self.metadata.items():
            if key not in props:
                props[key] = value

        return props


@dataclass
class ActNode:
    """
    Represents an Act (OC/AS/RO publication) node in the graph
    """
    uri: str
    type_document: str  # 'OC', 'AS', 'RO', 'FGA', 'FF', 'FogF'
    number: Optional[str] = None  # Publication number

    # Multilingual titles
    title_de: Optional[str] = None
    title_fr: Optional[str] = None
    title_it: Optional[str] = None
    title_rm: Optional[str] = None
    title_en: Optional[str] = None

    # Date fields
    date_document: Optional[str] = None
    date_publication: Optional[str] = None
    date_entry_in_force: Optional[str] = None

    # Legal references
    amends: Optional[str] = None  # URI of law being amended
    basic_act: Optional[str] = None  # URI of basic act

    # Additional metadata
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "type_document": self.type_document
        }

        # Add optional fields
        optional_fields = [
            'number', 'date_document', 'date_publication', 'date_entry_in_force',
            'amends', 'basic_act', 'language'
        ]

        for field in optional_fields:
            if hasattr(self, field) and getattr(self, field) is not None:
                props[field] = getattr(self, field)

        # Add multilingual titles
        for lang in ["de", "fr", "it", "rm", "en"]:
            title_attr = f"title_{lang}"
            if hasattr(self, title_attr) and getattr(self, title_attr):
                props[title_attr] = getattr(self, title_attr)

        # Add metadata
        for key, value in self.metadata.items():
            if key not in props:
                props[key] = value

        return props


@dataclass
class LanguageNode:
    """
    Represents a Language node in the graph
    """
    code: str  # DE, FR, IT, RM, EN
    name: str  # Full language name

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        return {
            "code": self.code,
            "name": self.name
        }


@dataclass
class ManifestationNode:
    """
    Represents a Manifestation (document format) node
    """
    uri: str
    format: str  # html, pdf, xml, docx, json
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "format": self.format
        }

        if self.file_path:
            props["file_path"] = self.file_path
        if self.file_size:
            props["file_size"] = self.file_size
        if self.checksum:
            props["checksum"] = self.checksum

        # Add metadata
        for key, value in self.metadata.items():
            if key not in props:
                props[key] = value

        return props


class GraphSchema:
    """
    Manages the graph schema definitions and constraints
    """

    # Cypher statements for creating constraints and indexes
    CONSTRAINTS = [
        # Unique constraints (also create indexes)
        f"CREATE CONSTRAINT law_uri_unique IF NOT EXISTS FOR (l:{NodeLabels.LAW.value}) REQUIRE l.uri IS UNIQUE",
        f"CREATE CONSTRAINT version_uri_unique IF NOT EXISTS FOR (v:{NodeLabels.VERSION.value}) REQUIRE v.uri IS UNIQUE",
        f"CREATE CONSTRAINT article_uri_unique IF NOT EXISTS FOR (a:{NodeLabels.ARTICLE.value}) REQUIRE a.uri IS UNIQUE",
        f"CREATE CONSTRAINT language_code_unique IF NOT EXISTS FOR (l:{NodeLabels.LANGUAGE.value}) REQUIRE l.code IS UNIQUE",
        f"CREATE CONSTRAINT manifestation_uri_unique IF NOT EXISTS FOR (m:{NodeLabels.MANIFESTATION.value}) REQUIRE m.uri IS UNIQUE",
    ]

    INDEXES = [
        # Additional indexes for query performance
        f"CREATE INDEX law_sr_number IF NOT EXISTS FOR (l:{NodeLabels.LAW.value}) ON (l.sr_number)",
        f"CREATE INDEX law_date_enacted IF NOT EXISTS FOR (l:{NodeLabels.LAW.value}) ON (l.date_enacted)",
        f"CREATE INDEX law_status IF NOT EXISTS FOR (l:{NodeLabels.LAW.value}) ON (l.status)",
        f"CREATE INDEX version_date_applicable IF NOT EXISTS FOR (v:{NodeLabels.VERSION.value}) ON (v.date_applicable)",
        f"CREATE INDEX version_law_uri IF NOT EXISTS FOR (v:{NodeLabels.VERSION.value}) ON (v.law_uri)",
        f"CREATE INDEX article_law_uri IF NOT EXISTS FOR (a:{NodeLabels.ARTICLE.value}) ON (a.law_uri)",
        f"CREATE INDEX article_number IF NOT EXISTS FOR (a:{NodeLabels.ARTICLE.value}) ON (a.number)",
        f"CREATE INDEX manifestation_format IF NOT EXISTS FOR (m:{NodeLabels.MANIFESTATION.value}) ON (m.format)",
        # Composite indexes
        f"CREATE INDEX article_law_number IF NOT EXISTS FOR (a:{NodeLabels.ARTICLE.value}) ON (a.law_uri, a.number)",
        f"CREATE INDEX version_law_date IF NOT EXISTS FOR (v:{NodeLabels.VERSION.value}) ON (v.law_uri, v.date_applicable)",
        # Temporal optimization indexes (TASK-006)
        f"CREATE INDEX version_date_range IF NOT EXISTS FOR (v:{NodeLabels.VERSION.value}) ON (v.date_applicable, v.date_end_applicable)",
        f"CREATE INDEX version_date_end IF NOT EXISTS FOR (v:{NodeLabels.VERSION.value}) ON (v.date_end_applicable)",
        f"CREATE INDEX current_version IF NOT EXISTS FOR (v:{NodeLabels.VERSION.value}) ON (v.is_current)",
    ]

    # Language initialization data
    LANGUAGES = [
        LanguageNode(LanguageCodes.GERMAN.value, "Deutsch"),
        LanguageNode(LanguageCodes.FRENCH.value, "Français"),
        LanguageNode(LanguageCodes.ITALIAN.value, "Italiano"),
        LanguageNode(LanguageCodes.ROMANSH.value, "Rumantsch"),
        LanguageNode(LanguageCodes.ENGLISH.value, "English"),
    ]

    @classmethod
    def get_all_constraints(cls) -> List[str]:
        """Get all constraint creation statements"""
        return cls.CONSTRAINTS

    @classmethod
    def get_all_indexes(cls) -> List[str]:
        """Get all index creation statements"""
        return cls.INDEXES

    @classmethod
    def get_initialization_queries(cls) -> List[tuple[str, Dict[str, Any]]]:
        """
        Get queries to initialize the database with base data

        Returns:
            List of (query, parameters) tuples
        """
        queries = []

        # Create language nodes
        for language in cls.LANGUAGES:
            query = f"""
            MERGE (l:{NodeLabels.LANGUAGE.value} {{code: $code}})
            SET l.name = $name
            """
            params = language.to_cypher_properties()
            queries.append((query, params))

        return queries


@dataclass
class TaxonomyNode:
    """Base class for taxonomy hierarchy nodes"""
    uri: str
    name: str
    number: Optional[str] = None
    title_de: Optional[str] = None
    title_fr: Optional[str] = None
    title_it: Optional[str] = None
    parent_uri: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "name": self.name
        }
        if self.number:
            props["number"] = self.number
        for lang in ["de", "fr", "it"]:
            title_attr = f"title_{lang}"
            if hasattr(self, title_attr) and getattr(self, title_attr):
                props[title_attr] = getattr(self, title_attr)
        if self.parent_uri:
            props["parent_uri"] = self.parent_uri
        props.update(self.metadata)
        return props


@dataclass
class DomainNode(TaxonomyNode):
    """Represents a legal domain (top level of hierarchy)"""
    pass


@dataclass
class BookNode(TaxonomyNode):
    """Represents a book in the legal document"""
    domain_uri: Optional[str] = None


@dataclass
class ChapterNode(TaxonomyNode):
    """Represents a chapter in a book"""
    book_uri: Optional[str] = None


@dataclass
class SectionNode(TaxonomyNode):
    """Represents a section in a chapter"""
    chapter_uri: Optional[str] = None


@dataclass
class ParagraphNode:
    """
    Represents a paragraph within an article (AST level 7)
    """
    uri: str
    article_uri: str
    number: str  # "1", "2", "3", etc.
    text: str  # Full paragraph text

    # AST properties
    ast_path: Optional[str] = None  # "/law_101/art_10/para_1"
    ast_level: int = 7
    parent_id: Optional[str] = None  # Article ID
    position: Optional[int] = None  # Order within article

    # Content properties
    word_count: Optional[int] = None
    has_subpoints: bool = False
    embedding: Optional[List[float]] = None  # For RAG

    # Metadata
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "article_uri": self.article_uri,
            "number": self.number,
            "text": self.text,
            "ast_level": self.ast_level,
            "has_subpoints": self.has_subpoints
        }

        if self.ast_path:
            props["ast_path"] = self.ast_path
        if self.parent_id:
            props["parent_id"] = self.parent_id
        if self.position is not None:
            props["position"] = self.position
        if self.word_count:
            props["word_count"] = self.word_count
        if self.embedding:
            props["embedding"] = self.embedding
        if self.language:
            props["language"] = self.language

        # Add metadata
        for key, value in self.metadata.items():
            if key not in props:
                props[key] = value

        return props


@dataclass
class SubpointNode:
    """
    Represents a lettered subpoint within a paragraph (AST level 8)
    """
    uri: str
    paragraph_uri: str
    letter: str  # "a", "b", "c", etc.
    text: str  # Subpoint text

    # AST properties
    ast_path: Optional[str] = None  # "/law_101/art_10/para_1/subpoint_a"
    ast_level: int = 8
    parent_id: Optional[str] = None  # Paragraph ID
    position: Optional[int] = None  # Order within paragraph

    # Content properties
    embedding: Optional[List[float]] = None  # For RAG

    # Metadata
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "paragraph_uri": self.paragraph_uri,
            "letter": self.letter,
            "text": self.text,
            "ast_level": self.ast_level
        }

        if self.ast_path:
            props["ast_path"] = self.ast_path
        if self.parent_id:
            props["parent_id"] = self.parent_id
        if self.position is not None:
            props["position"] = self.position
        if self.embedding:
            props["embedding"] = self.embedding
        if self.language:
            props["language"] = self.language

        # Add metadata
        for key, value in self.metadata.items():
            if key not in props:
                props[key] = value

        return props


    @classmethod
    def validate_node_label(cls, label: str) -> bool:
        """
        Validate if a label is a valid node type

        Args:
            label: Node label to validate

        Returns:
            True if valid, False otherwise
        """
        valid_labels = [nl.value for nl in NodeLabels]
        return label in valid_labels

    @classmethod
    def validate_relationship_type(cls, rel_type: str) -> bool:
        """
        Validate if a relationship type is valid

        Args:
            rel_type: Relationship type to validate

        Returns:
            True if valid, False otherwise
        """
        valid_types = [rt.value for rt in RelationshipTypes]
        return rel_type in valid_types

    @classmethod
    def get_schema_info(cls) -> Dict[str, Any]:
        """
        Get information about the graph schema

        Returns:
            Dictionary with schema information
        """
        return {
            "node_labels": [nl.value for nl in NodeLabels],
            "relationship_types": [rt.value for rt in RelationshipTypes],
            "language_codes": [lc.value for lc in LanguageCodes],
            "manifestation_formats": [mf.value for mf in ManifestationFormats],
            "constraints_count": len(cls.CONSTRAINTS),
            "indexes_count": len(cls.INDEXES),
            "languages_count": len(cls.LANGUAGES)
        }