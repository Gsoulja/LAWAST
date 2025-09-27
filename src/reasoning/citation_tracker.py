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

    def __init__(self, neo4j_connection=None):
        """Initialize the citation tracker"""
        self.citations = []
        self.citation_map = defaultdict(list)  # fact_id -> citations
        self.neo4j_connection = neo4j_connection  # For graph lookups

    def track_citations(self,
                       reasoning_steps: List[ReasoningStep],
                       evidence: List[Dict[str, Any]] = None,
                       answer_text: str = None) -> List[Citation]:
        """
        Track all citations from reasoning steps and evidence.

        Args:
            reasoning_steps: List of reasoning steps
            evidence: Optional evidence to extract citations from
            answer_text: Optional answer text to filter relevant citations

        Returns:
            List of unique citations
        """
        all_citations = []
        high_priority_citations = []  # Citations explicitly mentioned

        # PRIORITY 1: Extract citations directly from the answer text
        if answer_text:
            answer_citations = self.extract_citations_from_text(answer_text)
            if answer_citations:
                # These are the most important - they're actually in the answer
                high_priority_citations.extend(answer_citations)

        # Extract citations from reasoning steps
        for step in reasoning_steps:
            if step.citations:
                high_priority_citations.extend(step.citations)

            # Also extract from step evidence
            for fact in step.evidence:
                citation = self.extract_citation(fact)
                if citation:
                    # Check if this citation is mentioned in the step conclusion
                    if step.conclusion and citation.article and f"Art. {citation.article}" in step.conclusion:
                        high_priority_citations.append(citation)
                    else:
                        all_citations.append(citation)

        # Extract citations from raw evidence if provided
        if evidence:
            for fact in evidence:
                citation = self.extract_citation(fact)
                if citation:
                    # Check if citation is mentioned in answer
                    if answer_text and citation.article and f"Art. {citation.article}" in answer_text:
                        high_priority_citations.append(citation)
                    else:
                        all_citations.append(citation)

        # Prioritize high priority citations
        # If we have high priority citations, primarily use those
        if high_priority_citations:
            # Only use citations that are explicitly mentioned in the answer
            final_citations = high_priority_citations

            # Don't add adjacent articles unless they're also mentioned
            # This prevents Art. 15 from being included when only Art. 16 is discussed
        else:
            # If no high priority citations, filter all citations to only relevant ones
            relevant_citations = []
            for citation in all_citations:
                # Check if the article number appears anywhere in the reasoning or answer
                if citation.article:
                    article_ref = f"Art. {citation.article}"
                    # Check if mentioned in answer or any reasoning step
                    is_mentioned = False
                    if answer_text and article_ref in answer_text:
                        is_mentioned = True
                    else:
                        for step in reasoning_steps:
                            if step.conclusion and article_ref in step.conclusion:
                                is_mentioned = True
                                break

                    if is_mentioned:
                        relevant_citations.append(citation)

            final_citations = relevant_citations if relevant_citations else all_citations[:3]

        # Deduplicate citations
        unique_citations = self._deduplicate_citations(final_citations)

        # Sort by SR number and article
        sorted_citations = self._sort_citations(unique_citations)

        # Limit final citations to most relevant
        if len(sorted_citations) > 5:
            # Keep only the most relevant ones (those with article numbers)
            with_articles = [c for c in sorted_citations if c.article]
            sorted_citations = with_articles[:5] if with_articles else sorted_citations[:5]

        self.citations = sorted_citations
        return sorted_citations

    def extract_citations_from_text(self, text: str) -> List[Citation]:
        """
        Extract citations directly from text (like answer text).

        Args:
            text: Text to extract citations from

        Returns:
            List of citations found in the text
        """
        citations = []
        if not text:
            return citations

        # Pattern for articles with law abbreviations
        # e.g., "Artikel 16 der Datenschutzverordnung", "Art. 16 DSV", "Art. 33 BV"
        patterns = [
            # With "Abs" (paragraph): Art. X Abs. Y LAW
            r'Art(?:ikel|\.)?\s+(\d+[a-z]?)\s+Abs\.\s*(\d+)\s+([A-Z]{2,})',
            # Full form with abbreviation in parentheses: Artikel X der/des [Law Name]... (ABBREV)
            r'Art(?:ikel)?\s+(\d+[a-z]?)\s+(?:der|des)\s+([A-Z][a-zäöü]+(?:gesetz|verordnung|verfassung))[^(]*\(([A-Z]{2,})\)',
            # Full form without abbreviation: Artikel X der/des [Law Name]
            r'Art(?:ikel)?\s+(\d+[a-z]?)\s+(?:der|des)\s+([A-Z][a-zäöü]+(?:gesetz|verordnung|verfassung))',
            # Abbreviation form: Art. X LAW (must be 2+ capital letters)
            r'Art(?:ikel|\.)?\s+(\d+[a-z]?)\s+([A-Z]{2,})\b',
            # Just article number when law is mentioned nearby
            r'Art(?:ikel|\.)?\s+(\d+[a-z]?)\b',
        ]

        # Map of law names to abbreviations
        law_map = {
            'Datenschutzverordnung': 'DSV',
            'Datenschutzgesetz': 'DSG',
            'Bundesverfassung': 'BV',
            'Obligationenrecht': 'OR',
            'Zivilgesetzbuch': 'ZGB',
            'Strafgesetzbuch': 'StGB',
            'DSV': 'DSV',
            'DSG': 'DSG',
            'BV': 'BV',
            'OR': 'OR',
            'ZGB': 'ZGB',
            'StGB': 'StGB',
        }

        # Track which articles we've already found to avoid duplicates
        found_articles = set()

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()

                if len(groups) == 2 and groups[1]:  # Pattern with law
                    article_num = groups[0]
                    law = groups[1]

                    # Get abbreviation
                    law_abbrev = law_map.get(law, law) if law else None

                    # Create unique key to avoid duplicates
                    key = f"{article_num}_{law_abbrev}"
                    if key not in found_articles:
                        found_articles.add(key)
                        citation = Citation(
                            article=article_num,
                            law_abbreviation=law_abbrev,
                            source=match.group(0),
                            reference=f"Art. {article_num} {law_abbrev}" if law_abbrev else f"Art. {article_num}"
                        )
                        citations.append(citation)

                elif len(groups) == 3 and groups[2]:  # Pattern with Abs and law
                    article_num = groups[0]
                    paragraph = groups[1]
                    law = groups[2]

                    law_abbrev = law_map.get(law, law) if law else None
                    key = f"{article_num}_{paragraph}_{law_abbrev}"

                    if key not in found_articles:
                        found_articles.add(key)
                        citation = Citation(
                            article=article_num,
                            paragraph=paragraph,
                            law_abbreviation=law_abbrev,
                            source=match.group(0),
                            reference=f"Art. {article_num} Abs. {paragraph} {law_abbrev}" if law_abbrev else f"Art. {article_num} Abs. {paragraph}"
                        )
                        citations.append(citation)

                elif len(groups) == 1:  # Just article number
                    article_num = groups[0]

                    # Try to find law context nearby (within 50 chars)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]

                    law_abbrev = None
                    for law_name, abbrev in law_map.items():
                        if law_name in context:
                            law_abbrev = abbrev
                            break

                    # Only add if we haven't seen this article yet
                    key = f"{article_num}_{law_abbrev if law_abbrev else 'unknown'}"
                    if key not in found_articles:
                        found_articles.add(key)
                        citation = Citation(
                            article=article_num,
                            law_abbreviation=law_abbrev,
                            source=match.group(0),
                            reference=f"Art. {article_num} {law_abbrev}" if law_abbrev else f"Art. {article_num}"
                        )
                        citations.append(citation)

        return citations

    def get_article_from_paragraph(self, uri: str) -> Optional[Dict[str, Any]]:
        """
        Query the graph to find the parent article of a paragraph.

        Args:
            uri: URI of the paragraph node

        Returns:
            Dictionary with article information or None
        """
        if not self.neo4j_connection:
            return None

        try:
            # Query to find parent article
            # Note: Using 'number' property as per graph schema
            query = """
            MATCH (para:Paragraph {uri: $uri})<-[:HAS_PARAGRAPH]-(art:Article)
            RETURN art.uri as article_uri,
                   art.number as article_number,
                   art.title_de as title_de,
                   art.title_fr as title_fr,
                   art.sr_number as sr_number
            UNION
            MATCH (para {uri: $uri})<-[:HAS_PARAGRAPH]-(art)
            WHERE art.number IS NOT NULL
            RETURN art.uri as article_uri,
                   art.number as article_number,
                   COALESCE(art.title_de, art.title_fr, art.title_it) as title_de,
                   null as title_fr,
                   art.sr_number as sr_number
            LIMIT 1
            """

            with self.neo4j_connection.get_session() as session:
                result = session.run(query, uri=uri)
                record = result.single()

                if record:
                    return {
                        'article_uri': record['article_uri'],
                        'article_number': record['article_number'],
                        'title': record['title_de'] or record['title_fr'],
                        'sr_number': record['sr_number']
                    }

        except Exception as e:
            logger.debug(f"Error querying graph for article: {e}")

        return None

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

        # Try to extract from title (often contains "Art. X")
        if not citation and fact.get("title"):
            citation = self._parse_title_citation(fact["title"])

        # Try to extract from content
        if not citation and fact.get("content"):
            citation = self._parse_content_citation(fact["content"])

        # If this is a paragraph node without article info, query graph for parent article
        if not citation or not citation.article:
            node_type = fact.get("type", "") or fact.get("node_type", "")
            title = fact.get("title", "")

            # Check if this is likely a paragraph node
            is_paragraph = (
                "paragraph" in node_type.lower() or
                "para" in title.lower() or
                title.startswith("Para ") or
                (title and "Person" in title and "Recht" in title) or  # Common in paragraph content
                (len(title) > 50 and "Art." not in title)  # Long text without article reference
            )

            if is_paragraph:
                # Try to get article from graph
                if uri and self.neo4j_connection:
                    article_info = self.get_article_from_paragraph(uri)
                    if article_info and article_info.get('article_number'):
                        citation = Citation(
                            sr_number=article_info.get('sr_number'),
                            article=article_info.get('article_number'),
                            title=article_info.get('title'),
                            source=f"Art. {article_info.get('article_number')}"
                        )

        # If we found article info from title/content but no SR number, create simple citation
        if not citation:
            # Check if title or content has article reference
            title = fact.get("title", "")
            content = fact.get("content", "")

            # Look for article patterns in title or content
            for text in [title, content[:200] if content else ""]:
                if text:  # Only process if text is not empty
                    art_match = re.search(r'Art\.?\s*(\d+[a-z]?)', text, re.IGNORECASE)
                    if art_match:
                        citation = Citation(
                            article=art_match.group(1),
                            title=title if title else None,
                            source=text[:100] if text else None
                        )
                        break

        # If still no citation but we have a title, use it as a basic citation
        if not citation and fact.get("title"):
            # Create a basic citation from the title
            title = fact.get("title", "")
            if title and title.strip():
                citation = Citation(
                    source=title,
                    title=title
                )

        # Add additional info if citation found
        if citation:
            if not citation.title and fact.get("title"):
                citation.title = fact["title"]
            if not citation.ast_path and fact.get("metadata", {}).get("ast_path"):
                citation.ast_path = fact["metadata"]["ast_path"]
            if not citation.source and fact.get("title"):
                citation.source = fact.get("title", "")

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

            # Get law abbreviation for the SR number
            law_abbrev = self.get_law_abbreviation(sr_number) if sr_number else None

            return Citation(
                sr_number=sr_number,
                article=article,
                paragraph=paragraph,
                subpoint=subpoint,
                law_abbreviation=law_abbrev
            )

        return None

    def _parse_metadata_citation(self, metadata: Dict[str, Any]) -> Optional[Citation]:
        """Parse citation from metadata"""
        sr_number = metadata.get("sr_number")
        if not sr_number:
            # Try other fields
            sr_number = metadata.get("law_sr") or metadata.get("sr")

        if sr_number:
            # Get law abbreviation for the SR number
            law_abbrev = self.get_law_abbreviation(str(sr_number)) if sr_number else None

            return Citation(
                sr_number=str(sr_number),
                article=metadata.get("article_number") or metadata.get("article"),
                paragraph=metadata.get("paragraph_number") or metadata.get("paragraph"),
                subpoint=metadata.get("subpoint"),
                law_abbreviation=law_abbrev,
                ast_path=metadata.get("ast_path")
            )

        return None

    def _parse_title_citation(self, title: str) -> Optional[Citation]:
        """Parse citation from title text"""
        # Common patterns in document titles
        # Example: "Art. 16 Meinungs- und Informationsfreiheit"
        # Also handle: "Art. 16 BV", "Art. 335b OR", "Art. 4-7 DSG"

        # Enhanced patterns for Swiss law citations
        patterns = [
            # Art. X LAW_ABBREV pattern (e.g., "Art. 16 BV")
            (r'Art\.?\s*(\d+[a-z]?)\s+(BV|OR|DSG|ZGB|StGB|StPO|ZPO|SchKG|AIG|RVOG|BGG|VwVG|KVG|UVG|ArG)\b', 'article_with_law'),
            # Art. X-Y LAW_ABBREV pattern (range)
            (r'Art\.?\s*(\d+[a-z]?)\s*[-–]\s*(\d+[a-z]?)\s+(BV|OR|DSG|ZGB|StGB|StPO|ZPO|SchKG|AIG|RVOG|BGG|VwVG|KVG|UVG|ArG)\b', 'article_range_with_law'),
            # Art. X Abs. Y pattern
            (r'Art\.?\s*(\d+[a-z]?)\s+Abs\.?\s*(\d+)', 'article_with_paragraph'),
            # Standard Art. X pattern
            (r'Art\.?\s*(\d+[a-z]?)\b', 'article_only'),
        ]

        for pattern, pattern_type in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                if pattern_type == 'article_with_law':
                    article = match.group(1)
                    law_abbrev = match.group(2).upper()
                    # Try to find SR number for this law
                    sr_number = self._get_sr_from_abbreviation(law_abbrev)
                    return Citation(
                        sr_number=sr_number,
                        article=article,
                        law_abbreviation=law_abbrev,
                        title=title,
                        source=title
                    )
                elif pattern_type == 'article_range_with_law':
                    # For article ranges, return the range as a string
                    start_article = match.group(1)
                    end_article = match.group(2)
                    law_abbrev = match.group(3).upper()
                    sr_number = self._get_sr_from_abbreviation(law_abbrev)
                    return Citation(
                        sr_number=sr_number,
                        article=f"{start_article}-{end_article}",
                        law_abbreviation=law_abbrev,
                        title=title,
                        source=title
                    )
                elif pattern_type == 'article_with_paragraph':
                    article = match.group(1)
                    paragraph = match.group(2)
                    # Try to find SR number in title
                    sr_pattern = r'SR\s*(\d{3}(?:\.\d+)*)'
                    sr_match = re.search(sr_pattern, title, re.IGNORECASE)
                    return Citation(
                        sr_number=sr_match.group(1) if sr_match else None,
                        article=article,
                        paragraph=paragraph,
                        title=title,
                        source=title
                    )
                elif pattern_type == 'article_only':
                    article = match.group(1)
                    # Try to find SR number in title
                    sr_pattern = r'SR\s*(\d{3}(?:\.\d+)*)'
                    sr_match = re.search(sr_pattern, title, re.IGNORECASE)
                    sr_number = sr_match.group(1) if sr_match else None

                    # If SR 101, add BV abbreviation
                    law_abbrev = None
                    if sr_number == '101':
                        law_abbrev = 'BV'

                    return Citation(
                        sr_number=sr_number,
                        article=article,
                        law_abbreviation=law_abbrev,
                        title=title,
                        source=title
                    )

        return None

    def _get_sr_from_abbreviation(self, law_abbrev: str) -> Optional[str]:
        """Get SR number from law abbreviation (reverse mapping)"""
        reverse_mappings = {
            "BV": "101",
            "ZGB": "210",
            "OR": "220",
            "DSG": "235.1",
            "StGB": "311.0",
            "StPO": "312.0",
            "ZPO": "272",
            "SchKG": "281.1",
            "AIG": "142.20",
            "RVOG": "172.021",
            "ParlG": "152.1",
            "BPG": "152.3",
            "BGG": "173.71",
            "VwVG": "173.110",
            "FMG": "784.10",
            "LwG": "810.1",
            "HMG": "812.21",
            "ArG": "813.0",
            "AHV": "822.11",
            "IV": "831.10",
            "KVG": "832.10",
            "UVG": "837.0",
            "FIDLEG": "935.52",
            "FINIG": "935.521",
            "USG": "941.20",
        }
        return reverse_mappings.get(law_abbrev.upper())

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

    def get_law_abbreviation(self, sr_number: str) -> str:
        """
        Map SR numbers to common Swiss law abbreviations.
        Essential for challenge format compliance.
        """
        # Core Swiss Federal Laws
        mappings = {
            "101": "BV",           # Bundesverfassung (Federal Constitution)
            "210": "ZGB",          # Zivilgesetzbuch (Civil Code)
            "220": "OR",           # Obligationenrecht (Code of Obligations)
            "235.1": "DSG",        # Datenschutzgesetz (Data Protection Act)
            "311.0": "StGB",       # Strafgesetzbuch (Criminal Code)
            "312.0": "StPO",       # Strafprozessordnung (Criminal Procedure Code)
            "272": "ZPO",          # Zivilprozessordnung (Civil Procedure Code)
            "281.1": "SchKG",      # Schuldbetreibungs- und Konkursgesetz
            "142.20": "AIG",       # Ausländer- und Integrationsgesetz
            "172.021": "RVOG",     # Regierungs- und Verwaltungsorganisationsgesetz
            "152.1": "ParlG",      # Parlamentsgesetz
            "152.3": "BPG",        # Bundespersonalgesetz
            "173.71": "BGG",       # Bundesgerichtsgesetz
            "173.110": "VwVG",     # Verwaltungsverfahrensgesetz
            "235": "DSG_alt",      # Old Data Protection Act (before 2023)
            "784.10": "FMG",       # Fernmeldegesetz
            "810.1": "LwG",        # Landwirtschaftsgesetz
            "812.21": "HMG",       # Heilmittelgesetz
            "813.0": "ArG",        # Arbeitsgesetz
            "822.11": "AHV",       # AHV-Gesetz
            "831.10": "IV",        # IV-Gesetz
            "832.10": "KVG",       # Krankenversicherungsgesetz
            "837.0": "UVG",        # Unfallversicherungsgesetz
            "935.52": "FIDLEG",    # Finanzdienstleistungsgesetz
            "935.521": "FINIG",    # Finanzinstitutsgesetz
            "941.20": "USG",       # Umweltschutzgesetz
            "958": "GmbHG",        # GmbH-Recht (part of OR)
        }

        # Check if SR number starts with known mapping
        for sr_prefix, abbrev in mappings.items():
            if sr_number.startswith(sr_prefix):
                return abbrev

        # Check for partial matches (e.g., 235.11 should match 235.1)
        sr_parts = sr_number.split(".")
        if len(sr_parts) > 1:
            base_with_first = f"{sr_parts[0]}.{sr_parts[1][0]}"  # e.g., 235.1 from 235.11
            for sr_prefix, abbrev in mappings.items():
                if base_with_first.startswith(sr_prefix):
                    return abbrev

        return None

    def _get_citation_key(self, citation: Citation) -> str:
        """Get unique key for a citation"""
        parts = []

        # Add SR number if present
        if citation.sr_number:
            parts.append(citation.sr_number)

        # Add article if present
        if citation.article:
            parts.append(f"art{citation.article}")

        # Add paragraph if present
        if citation.paragraph:
            parts.append(f"para{citation.paragraph}")

        # Add subpoint if present
        if citation.subpoint:
            parts.append(f"lit{citation.subpoint}")

        # If no parts, use source or title as key
        if not parts:
            if citation.source:
                parts.append(citation.source[:50])  # Use first 50 chars of source
            elif citation.title:
                parts.append(citation.title[:50])  # Use first 50 chars of title
            else:
                parts.append("unknown")

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
            sr_main = 999  # Default for citations without SR number
            sr_sub = 0

            if citation.sr_number:
                sr_parts = citation.sr_number.split(".")
                sr_main = int(sr_parts[0]) if sr_parts[0].isdigit() else 999
                sr_sub = int(sr_parts[1]) if len(sr_parts) > 1 and sr_parts[1].isdigit() else 0

            # Parse article for sorting
            art_num = 0
            if citation.article:
                # Extract numeric part
                art_match = re.match(r'(\d+)', str(citation.article))
                if art_match:
                    art_num = int(art_match.group(1))

            # Use title as fallback for sorting if no SR/article
            title_sort = citation.title[:20] if citation.title else ""

            return (sr_main, sr_sub, art_num, title_sort)

        return sorted(citations, key=sort_key)

    def format_citations(self,
                        citations: List[Citation] = None,
                        style: str = "standard") -> List[str]:
        """
        Format citations for display.

        Args:
            citations: Citations to format (uses tracked if None)
            style: Citation style ("standard", "full", "compact", "challenge")

        Returns:
            List of formatted citation strings
        """
        citations = citations or self.citations

        formatted = []
        for citation in citations:
            if style == "challenge":
                formatted.append(self._format_challenge_citation(citation))
            elif style == "full":
                formatted.append(self._format_full_citation(citation))
            elif style == "compact":
                formatted.append(self._format_compact_citation(citation))
            else:
                formatted.append(str(citation))

        return formatted

    def _format_challenge_citation(self, citation: Citation) -> str:
        """Format citation for Swiss Law RAG Challenge"""
        # Try to get law abbreviation from SR number
        if citation.sr_number:
            law_abbrev = self.get_law_abbreviation(citation.sr_number)
            if law_abbrev and citation.article:
                # Format as "Art. X LAW_ABBREV"
                if citation.paragraph:
                    return f"Art. {citation.article} Abs. {citation.paragraph} {law_abbrev}"
                else:
                    return f"Art. {citation.article} {law_abbrev}"
            elif law_abbrev:
                return law_abbrev

        # Fallback to standard format
        return str(citation)

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

        # Group by SR number (or use "no_sr" for citations without SR)
        by_sr = defaultdict(list)
        for citation in citations:
            key = citation.sr_number if citation.sr_number else "no_sr"
            by_sr[key].append(citation)

        # Format each SR group
        for sr_number in sorted(by_sr.keys()):
            sr_citations = by_sr[sr_number]

            # Get title from first citation with title
            title = next((c.title for c in sr_citations if c.title), None)

            if sr_number == "no_sr":
                # Handle citations without SR numbers
                for citation in sr_citations:
                    bibliography.append(f"- {citation}")
            elif len(sr_citations) == 1:
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