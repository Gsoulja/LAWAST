"""
Unified data structure for extracted content from LAWAST modules.

This module provides a standardized format for passing extracted data
between the extraction modules (TASK-008.1-4) and the storage pipeline
(TASK-008.5).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .taxonomy_extractor import TaxonomyResult
from .article_extractor import Article
from .reference_patterns import ReferenceMatch


# Create Reference alias for compatibility
Reference = ReferenceMatch


@dataclass
class ExtractedContent:
    """
    Container for all extracted content from a legal document.

    This class aggregates the output from all extraction modules:
    - Taxonomy (hierarchical structure and classification)
    - Articles (full content with paragraphs and metadata)
    - References (cross-references and citations)

    Attributes:
        taxonomy: Hierarchical document structure and metadata
        articles: List of extracted articles with full content
        references: List of extracted references and citations
        metadata: Additional document-level metadata
        source_file: Path to the source HTML file
        law_uri: URI of the parent law document
    """
    taxonomy: TaxonomyResult
    articles: List[Article] = field(default_factory=list)
    references: List[Reference] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_file: Optional[str] = None
    law_uri: Optional[str] = None

    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the extracted content.

        Returns:
            Dictionary with counts of various elements
        """
        stats = {
            'articles_count': len(self.articles),
            'references_count': len(self.references),
            'hierarchy_levels': len(self.taxonomy.hierarchy) if self.taxonomy.hierarchy else 0,
            'languages': len(self.taxonomy.title) if self.taxonomy.title else 0,
        }

        # Count paragraphs and subpoints
        total_paragraphs = 0
        total_subpoints = 0
        for article in self.articles:
            if article.content:
                total_paragraphs += len(article.content.paragraphs)
                for para in article.content.paragraphs:
                    total_subpoints += len(para.subpoints)

        stats['paragraphs_count'] = total_paragraphs
        stats['subpoints_count'] = total_subpoints

        return stats

    def validate(self) -> List[str]:
        """
        Validate the extracted content for completeness and consistency.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check taxonomy
        if not self.taxonomy:
            errors.append("Missing taxonomy data")
        elif not self.taxonomy.sr_number:
            errors.append("Missing SR number in taxonomy")

        # Check articles
        if not self.articles:
            errors.append("No articles extracted")
        else:
            # Check for duplicate article numbers
            article_numbers = [a.number_normalized for a in self.articles]
            if len(article_numbers) != len(set(article_numbers)):
                errors.append("Duplicate article numbers found")

            # Check article URIs
            for i, article in enumerate(self.articles):
                if not article.uri:
                    errors.append(f"Article {i} missing URI")
                if not article.number:
                    errors.append(f"Article {i} missing number")

        # Check references consistency
        article_uris = {a.uri for a in self.articles}
        for ref in self.references:
            if ref.source_uri not in article_uris and ref.source_uri != self.law_uri:
                errors.append(f"Reference source URI not found: {ref.source_uri}")

        return errors