#!/usr/bin/env python3
"""
Court Decision API Client for entscheidsuche.ch
Queries court decisions on-demand based on article citations
"""

import re
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger(__name__)


@dataclass
class CourtDecisionSummary:
    """Lightweight court decision summary"""
    decision_id: str
    court: str
    date: str
    title: str
    excerpt: str  # Relevant excerpt mentioning the article
    relevance_score: float
    url: str


class EntscheidSucheClient:
    """
    Client for querying entscheidsuche.ch API
    Fetches court decisions on-demand based on article citations
    """

    BASE_URL = "https://entscheidsuche.ch"
    SEARCH_ENDPOINT = "https://entscheidsuche.ch/_search.php"
    DOCS_BASE = "https://entscheidsuche.ch/docs"

    def __init__(self):
        """Initialize the API client"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LAWAST/1.0 (Legal Assistant; +https://github.com/LAWAST)'
        })

    def search_by_article(self,
                         article_num: str,
                         law_abbrev: str,
                         limit: int = 5) -> List[CourtDecisionSummary]:
        """
        Search for court decisions that cite a specific article.

        Args:
            article_num: Article number (e.g., "16", "335b")
            law_abbrev: Law abbreviation (e.g., "BV", "OR")
            limit: Maximum number of results

        Returns:
            List of court decision summaries
        """
        decisions = []

        try:
            # Build search query
            # Format: "Art. 16 BV" or "Art. 335b OR"
            search_query = f"Art. {article_num} {law_abbrev}"

            # Use Elasticsearch query syntax
            # This is a hypothetical API endpoint structure based on common patterns
            params = {
                'q': search_query,
                'size': limit,
                'sort': 'relevance',
                'fields': 'id,court,date,title,excerpt'
            }

            # Try different search strategies
            decisions = self._search_with_elasticsearch(search_query, limit)

            if not decisions:
                # Fallback to simple text search
                decisions = self._search_with_text(search_query, limit)

        except Exception as e:
            logger.error(f"Error searching for decisions on Art. {article_num} {law_abbrev}: {e}")

        return decisions

    def _search_with_elasticsearch(self, query: str, limit: int) -> List[CourtDecisionSummary]:
        """
        Search using Elasticsearch-style API.

        Args:
            query: Search query
            limit: Result limit

        Returns:
            List of decisions
        """
        decisions = []

        try:
            # Use query_string which works with the API
            # Don't specify _source to get all fields
            es_query = {
                "query": {
                    "query_string": {
                        "query": query,
                        "default_operator": "AND"
                    }
                },
                "size": limit,
                "highlight": {
                    "fields": {
                        "attachment.content": {
                            "fragment_size": 200,
                            "number_of_fragments": 1
                        }
                    }
                },
                "sort": [
                    {"_score": {"order": "desc"}}
                ]
            }

            # Use the documented search endpoint
            response = self.session.post(
                self.SEARCH_ENDPOINT,
                json=es_query,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                for hit in data.get('hits', {}).get('hits', []):
                    source = hit.get('_source', {})

                    # Extract decision ID and court from hierarchy/id
                    decision_id = source.get('id', '')
                    reference = source.get('reference', [])
                    hierarchy = source.get('hierarchy', [])

                    # Determine court from hierarchy
                    if 'CH_BGer' in hierarchy or 'BGer' in decision_id:
                        court = 'Bundesgericht'
                    elif 'CH_BVGer' in hierarchy:
                        court = 'Bundesverwaltungsgericht'
                    else:
                        court = hierarchy[1] if len(hierarchy) > 1 else 'Court'

                    # Get title and abstract
                    title_obj = source.get('title', {})
                    title = title_obj.get('de', title_obj.get('fr', title_obj.get('it', '')))

                    abstract_obj = source.get('abstract', {})
                    abstract = abstract_obj.get('de', abstract_obj.get('fr', abstract_obj.get('it', '')))

                    # Build URL from attachment info
                    attachment = source.get('attachment', {})
                    content_url = attachment.get('content_url', '')
                    if not content_url and decision_id:
                        content_url = f"{self.DOCS_BASE}/{decision_id}.html"

                    # Get excerpt from highlight or abstract
                    highlights = hit.get('highlight', {})
                    excerpt = ''
                    if highlights:
                        # Get first highlight from any field
                        for field, values in highlights.items():
                            if values:
                                excerpt = values[0]
                                break
                    if not excerpt:
                        excerpt = abstract[:200] if abstract else ''

                    decision = CourtDecisionSummary(
                        decision_id=reference[0] if reference else decision_id,
                        court=court,
                        date=source.get('date', ''),
                        title=title[:200] if title else abstract[:200],
                        excerpt=excerpt,
                        relevance_score=hit.get('_score', 0.5),
                        url=content_url
                    )
                    decisions.append(decision)

        except requests.exceptions.RequestException:
            # API might not be available or different structure
            pass
        except Exception as e:
            logger.debug(f"Elasticsearch search failed: {e}")

        return decisions

    def _search_with_text(self, query: str, limit: int) -> List[CourtDecisionSummary]:
        """
        Fallback to simpler query if Elasticsearch fails.

        Args:
            query: Search query
            limit: Result limit

        Returns:
            List of decisions
        """
        decisions = []

        try:
            # Try with simpler query
            simple_query = {
                "query": {
                    "query_string": {
                        "query": query.replace("Art.", "").replace("BV", "").replace("OR", ""),
                        "default_operator": "OR"
                    }
                },
                "size": limit * 2,  # Get more results to filter
                "_source": ["signatur", "datum", "num", "kopfzeile_de"]
            }

            response = self.session.post(
                self.SEARCH_ENDPOINT,
                json=simple_query,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                for hit in data.get('hits', {}).get('hits', [])[:limit]:
                    source = hit.get('_source', {})
                    signatur = source.get('signatur', '')

                    decisions.append(CourtDecisionSummary(
                        decision_id=source.get('num', signatur),
                        court='Bundesgericht' if 'BGer' in signatur else 'Court',
                        date=source.get('datum', ''),
                        title=source.get('kopfzeile_de', ''),
                        excerpt='',
                        relevance_score=hit.get('_score', 0.5),
                        url=f"{self.DOCS_BASE}/{signatur}.html"
                    ))

        except Exception:
            pass

        return decisions

    def get_decision_details(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details of a specific court decision.

        Args:
            decision_id: Decision identifier

        Returns:
            Decision details or None
        """
        try:
            # Fetch JSON metadata
            response = self.session.get(
                f"{self.DOCS_BASE}/{decision_id}.json",
                timeout=10
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.error(f"Error fetching decision {decision_id}: {e}")

        return None

    def enrich_citations_with_decisions(self, citations: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Enrich a list of article citations with related court decisions.

        Args:
            citations: List of citations with 'article' and 'law' keys

        Returns:
            Enriched citations with court decisions
        """
        enriched = []

        for citation in citations:
            article = citation.get('article', '')
            law = citation.get('law', '')

            if article and law:
                # Search for decisions
                decisions = self.search_by_article(article, law, limit=3)

                enriched_citation = {
                    **citation,
                    'court_decisions': [
                        {
                            'id': d.decision_id,
                            'court': d.court,
                            'date': d.date,
                            'title': d.title,
                            'excerpt': d.excerpt,
                            'url': d.url,
                            'relevance': d.relevance_score
                        }
                        for d in decisions
                    ]
                }
                enriched.append(enriched_citation)
            else:
                enriched.append(citation)

        return enriched


class CourtDecisionEnricher:
    """
    Enriches legal answers with relevant court decisions.
    Used at the end of the pipeline to add court decision context.
    """

    def __init__(self, client: Optional[EntscheidSucheClient] = None):
        """
        Initialize the enricher.

        Args:
            client: EntscheidSuche API client
        """
        self.client = client or EntscheidSucheClient()

    def enrich_answer(self, answer: str, citations: List[Any]) -> Dict[str, Any]:
        """
        Enrich an answer with court decisions based on citations.

        Args:
            answer: The legal answer text
            citations: List of citations from the answer

        Returns:
            Enriched answer with court decisions
        """
        # Extract article citations from the answer
        article_citations = self._extract_article_citations(citations)

        # Search for court decisions for each citation
        court_decisions = {}
        for citation in article_citations:
            key = f"Art. {citation['article']} {citation['law']}"
            decisions = self.client.search_by_article(
                citation['article'],
                citation['law'],
                limit=2  # Just top 2 most relevant
            )
            if decisions:
                court_decisions[key] = decisions

        # Build enriched response
        enriched_answer = {
            'answer': answer,
            'citations': citations,
            'court_decisions': {}
        }

        # Add court decisions with formatting
        if court_decisions:
            enriched_answer['court_decisions_text'] = self._format_court_decisions(court_decisions)
            enriched_answer['court_decisions'] = {
                key: [
                    {
                        'id': d.decision_id,
                        'title': d.title,
                        'excerpt': d.excerpt,
                        'url': d.url
                    }
                    for d in decisions
                ]
                for key, decisions in court_decisions.items()
            }

        return enriched_answer

    def _extract_article_citations(self, citations: List[Any]) -> List[Dict[str, str]]:
        """
        Extract article and law information from citations.

        Args:
            citations: Raw citations from the pipeline

        Returns:
            List of structured citations
        """
        structured = []

        for citation in citations:
            if hasattr(citation, 'article') and hasattr(citation, 'law_abbreviation'):
                structured.append({
                    'article': citation.article,
                    'law': citation.law_abbreviation
                })
            elif isinstance(citation, str):
                # Parse string citation like "Art. 16 BV"
                match = re.search(r"Art\.\s*(\d+[a-z]?)\s+([A-Z]+)", citation)
                if match:
                    structured.append({
                        'article': match.group(1),
                        'law': match.group(2)
                    })

        return structured

    def _format_court_decisions(self, court_decisions: Dict[str, List[CourtDecisionSummary]]) -> str:
        """
        Format court decisions for display.

        Args:
            court_decisions: Dictionary of court decisions by article

        Returns:
            Formatted text
        """
        lines = ["\n**Relevant Court Decisions:**\n"]

        for article_ref, decisions in court_decisions.items():
            lines.append(f"\n*{article_ref}:*")
            for decision in decisions[:2]:  # Show max 2 per article
                lines.append(f"• {decision.court}, {decision.date} ({decision.decision_id})")
                lines.append(f"  {decision.title}")
                if decision.excerpt:
                    lines.append(f"  \"{decision.excerpt[:150]}...\"")

        return "\n".join(lines)