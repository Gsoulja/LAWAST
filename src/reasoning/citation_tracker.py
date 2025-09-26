"""
Citation tracker for legal source attribution
"""

import logging
import re
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

from .models import Citation, ReasoningStep

logger = logging.getLogger(__name__)


class CitationTracker:
    """
    Tracks and manages citations throughout the reasoning process.
    Ensures proper source attribution for Swiss legal references.
    """

    def __init__(self):
        """Initialize the citation tracker"""
        self.citations = []
        self.citation_map = defaultdict(list)  # fact_id -> citations

    def track_citations(self,
                       reasoning_steps: List[ReasoningStep],
                       evidence: List[Dict[str, Any]] = None) -> List[Citation]:
        """
        Track all citations from reasoning steps and evidence.

        Args:
            reasoning_steps: List of reasoning steps
            evidence: Optional evidence to extract citations from

        Returns:
            List of unique citations
        """
        all_citations = []

        # Extract citations from reasoning steps
        for step in reasoning_steps:
            if step.citations:
                all_citations.extend(step.citations)

            # Also extract from step evidence
            for fact in step.evidence:
                citation = self.extract_citation(fact)
                if citation:
                    all_citations.append(citation)

        # Extract citations from raw evidence if provided
        if evidence:
            for fact in evidence:
                citation = self.extract_citation(fact)
                if citation:
                    all_citations.append(citation)

        # Deduplicate citations
        unique_citations = self._deduplicate_citations(all_citations)

        # Sort by SR number and article
        sorted_citations = self._sort_citations(unique_citations)

        self.citations = sorted_citations
        return sorted_citations

    def extract_citation(self, fact: Dict[str, Any]) -> Optional[Citation]:
        """
        Extract citation from a fact or evidence item.

        Args:
            fact: Fact dictionary

        Returns:
            Citation object or None
        """
        citation = None

        # Try to extract from URI
        uri = fact.get("uri", "")
        if uri:
            citation = self._parse_uri_citation(uri)

        # Try to extract from metadata
        if not citation and fact.get("metadata"):
            citation = self._parse_metadata_citation(fact["metadata"])

        # Try to extract from content
        if not citation and fact.get("content"):
            citation = self._parse_content_citation(fact["content"])

        # Add additional info if citation found
        if citation:
            if not citation.title and fact.get("title"):
                citation.title = fact["title"]
            if not citation.ast_path and fact.get("metadata", {}).get("ast_path"):
                citation.ast_path = fact["metadata"]["ast_path"]

        return citation

    def _parse_uri_citation(self, uri: str) -> Optional[Citation]:
        """Parse citation from URI string"""
        # Pattern for SR numbers
        sr_pattern = r'SR\s*(\d{3}(?:\.\d+)*)'
        sr_match = re.search(sr_pattern, uri, re.IGNORECASE)

        if not sr_match:
            # Also check without SR prefix
            sr_pattern2 = r'\b(\d{3}(?:\.\d+)+)\b'
            sr_match = re.search(sr_pattern2, uri)

        if sr_match:
            sr_number = sr_match.group(1)

            # Extract article
            article = None
            art_patterns = [
                r'[Aa]rt(?:icle)?\.?\s*(\d+[a-z]?)',
                r'[Aa]rt\.?\s*(\d+[a-z]?)',
                r'/art_(\d+[a-z]?)'
            ]
            for pattern in art_patterns:
                art_match = re.search(pattern, uri)
                if art_match:
                    article = art_match.group(1)
                    break

            # Extract paragraph
            paragraph = None
            para_patterns = [
                r'[Pp]ara(?:graph)?\.?\s*(\d+)',
                r'[Aa]bs(?:atz)?\.?\s*(\d+)',
                r'/para_(\d+)'
            ]
            for pattern in para_patterns:
                para_match = re.search(pattern, uri)
                if para_match:
                    paragraph = para_match.group(1)
                    break

            # Extract subpoint
            subpoint = None
            sub_patterns = [
                r'lit\.?\s*([a-z])',
                r'[Bb]uchstabe\s*([a-z])',
                r'/subpoint_([a-z])'
            ]
            for pattern in sub_patterns:
                sub_match = re.search(pattern, uri)
                if sub_match:
                    subpoint = sub_match.group(1)
                    break

            return Citation(
                sr_number=sr_number,
                article=article,
                paragraph=paragraph,
                subpoint=subpoint
            )

        return None

    def _parse_metadata_citation(self, metadata: Dict[str, Any]) -> Optional[Citation]:
        """Parse citation from metadata"""
        sr_number = metadata.get("sr_number")
        if not sr_number:
            # Try other fields
            sr_number = metadata.get("law_sr") or metadata.get("sr")

        if sr_number:
            return Citation(
                sr_number=str(sr_number),
                article=metadata.get("article_number") or metadata.get("article"),
                paragraph=metadata.get("paragraph_number") or metadata.get("paragraph"),
                subpoint=metadata.get("subpoint"),
                ast_path=metadata.get("ast_path")
            )

        return None

    def _parse_content_citation(self, content: str) -> Optional[Citation]:
        """Parse citation from content text"""
        # Look for explicit SR references in content
        sr_pattern = r'SR\s*(\d{3}(?:\.\d+)*)'
        sr_match = re.search(sr_pattern, content, re.IGNORECASE)

        if sr_match:
            return Citation(sr_number=sr_match.group(1))

        return None

    def _deduplicate_citations(self, citations: List[Citation]) -> List[Citation]:
        """Remove duplicate citations"""
        unique = {}
        for citation in citations:
            # Create a unique key for the citation
            key = self._get_citation_key(citation)
            if key not in unique or self._is_more_complete(citation, unique[key]):
                unique[key] = citation

        return list(unique.values())

    def _get_citation_key(self, citation: Citation) -> str:
        """Get unique key for a citation"""
        parts = [citation.sr_number]
        if citation.article:
            parts.append(f"art{citation.article}")
        if citation.paragraph:
            parts.append(f"para{citation.paragraph}")
        if citation.subpoint:
            parts.append(f"lit{citation.subpoint}")
        return "_".join(parts)

    def _is_more_complete(self, citation1: Citation, citation2: Citation) -> bool:
        """Check if citation1 is more complete than citation2"""
        score1 = sum([
            bool(citation1.sr_number),
            bool(citation1.article),
            bool(citation1.paragraph),
            bool(citation1.subpoint),
            bool(citation1.title),
            bool(citation1.ast_path)
        ])
        score2 = sum([
            bool(citation2.sr_number),
            bool(citation2.article),
            bool(citation2.paragraph),
            bool(citation2.subpoint),
            bool(citation2.title),
            bool(citation2.ast_path)
        ])
        return score1 > score2

    def _sort_citations(self, citations: List[Citation]) -> List[Citation]:
        """Sort citations by SR number and article"""
        def sort_key(citation):
            # Parse SR number for sorting
            sr_parts = citation.sr_number.split(".")
            sr_main = int(sr_parts[0]) if sr_parts[0].isdigit() else 999
            sr_sub = int(sr_parts[1]) if len(sr_parts) > 1 and sr_parts[1].isdigit() else 0

            # Parse article for sorting
            art_num = 0
            if citation.article:
                # Extract numeric part
                art_match = re.match(r'(\d+)', citation.article)
                if art_match:
                    art_num = int(art_match.group(1))

            return (sr_main, sr_sub, art_num)

        return sorted(citations, key=sort_key)

    def format_citations(self,
                        citations: List[Citation] = None,
                        style: str = "standard") -> List[str]:
        """
        Format citations for display.

        Args:
            citations: Citations to format (uses tracked if None)
            style: Citation style ("standard", "full", "compact")

        Returns:
            List of formatted citation strings
        """
        citations = citations or self.citations

        formatted = []
        for citation in citations:
            if style == "full":
                formatted.append(self._format_full_citation(citation))
            elif style == "compact":
                formatted.append(self._format_compact_citation(citation))
            else:
                formatted.append(str(citation))

        return formatted

    def _format_full_citation(self, citation: Citation) -> str:
        """Format full citation with title"""
        parts = [str(citation)]
        if citation.title:
            parts.append(f"({citation.title})")
        if citation.ast_path:
            parts.append(f"[{citation.ast_path}]")
        return " ".join(parts)

    def _format_compact_citation(self, citation: Citation) -> str:
        """Format compact citation"""
        parts = [citation.sr_number]
        if citation.article:
            parts.append(f":{citation.article}")
        return "".join(parts)

    def generate_bibliography(self, citations: List[Citation] = None) -> str:
        """
        Generate a formatted bibliography.

        Args:
            citations: Citations to include (uses tracked if None)

        Returns:
            Formatted bibliography string
        """
        citations = citations or self.citations

        if not citations:
            return "No sources cited."

        bibliography = ["Sources:"]

        # Group by SR number
        by_sr = defaultdict(list)
        for citation in citations:
            by_sr[citation.sr_number].append(citation)

        # Format each SR group
        for sr_number in sorted(by_sr.keys()):
            sr_citations = by_sr[sr_number]

            # Get title from first citation with title
            title = next((c.title for c in sr_citations if c.title), None)

            if len(sr_citations) == 1:
                bibliography.append(f"- {sr_citations[0]}")
                if title:
                    bibliography[-1] += f" - {title}"
            else:
                # Multiple articles from same SR
                articles = sorted(set(c.article for c in sr_citations if c.article))
                if articles:
                    articles_str = ", ".join(f"Art. {a}" for a in articles)
                    bibliography.append(f"- SR {sr_number}: {articles_str}")
                    if title:
                        bibliography[-1] += f" - {title}"
                else:
                    bibliography.append(f"- SR {sr_number}")
                    if title:
                        bibliography[-1] += f" - {title}"

        return "\n".join(bibliography)