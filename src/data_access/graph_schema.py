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
    ARTICLE = "Article"
    LANGUAGE = "Language"
    MANIFESTATION = "Manifestation"


class RelationshipTypes(Enum):
    """Relationship types in the graph"""
    HAS_VERSION = "HAS_VERSION"
    SUPERSEDES = "SUPERSEDES"
    EXPRESSED_IN = "EXPRESSED_IN"
    MANIFESTED_AS = "MANIFESTED_AS"
    AMENDS = "AMENDS"
    REFERENCES = "REFERENCES"
    CONTAINS = "CONTAINS"


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
    Represents a Law node in the graph
    """
    uri: str
    sr_number: str
    title_de: Optional[str] = None
    title_fr: Optional[str] = None
    title_it: Optional[str] = None
    title_rm: Optional[str] = None
    title_en: Optional[str] = None
    date_enacted: Optional[datetime] = None
    date_modified: Optional[datetime] = None
    type: Optional[str] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "sr_number": self.sr_number
        }

        # Add optional properties
        for lang in ["de", "fr", "it", "rm", "en"]:
            title_attr = f"title_{lang}"
            if hasattr(self, title_attr) and getattr(self, title_attr):
                props[title_attr] = getattr(self, title_attr)

        if self.date_enacted:
            props["date_enacted"] = self.date_enacted.isoformat()
        if self.date_modified:
            props["date_modified"] = self.date_modified.isoformat()
        if self.type:
            props["type"] = self.type
        if self.status:
            props["status"] = self.status

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
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_cypher_properties(self) -> Dict[str, Any]:
        """Convert to properties for Cypher query"""
        props = {
            "uri": self.uri,
            "law_uri": self.law_uri,
            "number": self.number
        }

        if self.title:
            props["title"] = self.title
        if self.content_uri:
            props["content_uri"] = self.content_uri
        if self.section:
            props["section"] = self.section
        if self.chapter:
            props["chapter"] = self.chapter

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