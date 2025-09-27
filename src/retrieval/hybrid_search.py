"""
Hybrid Search component for Triple RAG
Combines Vector similarity with BM25 text search for improved keyword matching
"""

import logging
import math
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from ..data_access.neo4j_connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Result from hybrid vector + BM25 search"""
    node_id: str
    uri: str
    node_type: str
    score: float  # Combined hybrid score
    vector_score: float
    bm25_score: float
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class HybridSearch:
    """
    Hybrid search combining vector similarity and BM25 text search.

    This component enhances the Triple RAG system by providing better
    keyword matching capabilities while maintaining semantic understanding.
    """

    def __init__(self,
                 connection: Optional[Neo4jConnectionManager] = None,
                 vector_weight: float = 0.6,
                 bm25_weight: float = 0.4):
        """
        Initialize hybrid search component.

        Args:
            connection: Neo4j connection manager
            vector_weight: Weight for vector similarity (0-1)
            bm25_weight: Weight for BM25 text search (0-1)
        """
        self.connection = connection or Neo4jConnectionManager()
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

        # Ensure weights sum to 1
        total = vector_weight + bm25_weight
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Weights don't sum to 1 ({total}), normalizing...")
            self.vector_weight = vector_weight / total
            self.bm25_weight = bm25_weight / total

        # BM25 parameters
        self.k1 = 1.2  # Term frequency saturation
        self.b = 0.75  # Document length normalization

        # Language detection patterns
        self.language_patterns = {
            'de': r'\b(der|die|das|und|oder|nicht|mit|von|zu|bei)\b',
            'fr': r'\b(le|la|les|et|ou|ne|pas|avec|de|à)\b',
            'it': r'\b(il|la|le|e|o|non|con|di|a|da)\b',
            'en': r'\b(the|and|or|not|with|from|to|at|in)\b'
        }

        # Language-specific stop words (minimal set for efficiency)
        self.stop_words = {
            'de': {'der', 'die', 'das', 'und', 'oder', 'in', 'von', 'zu', 'mit', 'ist', 'ein', 'eine'},
            'fr': {'le', 'la', 'les', 'et', 'ou', 'dans', 'de', 'à', 'avec', 'est', 'un', 'une'},
            'it': {'il', 'la', 'le', 'e', 'o', 'in', 'di', 'a', 'con', 'è', 'un', 'una'},
            'en': {'the', 'and', 'or', 'in', 'of', 'to', 'with', 'is', 'a', 'an', 'for'}
        }

        logger.info(f"Hybrid search initialized with weights: vector={self.vector_weight:.2f}, bm25={self.bm25_weight:.2f}")

    def detect_language(self, text: str) -> str:
        """
        Detect the language of the query text.

        Args:
            text: Query text

        Returns:
            Language code ('de', 'fr', 'it', 'en')
        """
        text_lower = text.lower()
        scores = {}

        for lang, pattern in self.language_patterns.items():
            matches = len(re.findall(pattern, text_lower))
            scores[lang] = matches

        # Default to German if no clear winner
        if not scores or max(scores.values()) == 0:
            return 'de'

        return max(scores, key=scores.get)

    def extract_keywords(self, text: str, language: str = 'de') -> List[str]:
        """
        Extract keywords from text, removing stop words.

        Args:
            text: Input text
            language: Language code

        Returns:
            List of keywords
        """
        # Basic tokenization
        words = re.findall(r'\b\w+\b', text.lower())

        # Remove stop words
        stop_words = self.stop_words.get(language, set())
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]

        # Also keep original case versions for exact matching
        original_words = re.findall(r'\b\w+\b', text)
        important_words = [w for w in original_words if w.lower() in keywords]

        return list(set(keywords + important_words))

    def calculate_bm25_scores(self,
                             query: str,
                             language: str = None,
                             node_type: str = 'Article',
                             top_k: int = 50) -> Dict[str, float]:
        """
        Calculate BM25 scores for documents.

        Args:
            query: Search query
            language: Language code (auto-detect if None)
            node_type: Type of nodes to search
            top_k: Maximum results to return

        Returns:
            Dictionary of node_id -> BM25 score
        """
        if language is None:
            language = self.detect_language(query)

        keywords = self.extract_keywords(query, language)

        if not keywords:
            logger.warning("No keywords extracted from query")
            return {}

        # Get documents with content
        cypher_query = f"""
        MATCH (n:{node_type})
        WHERE n.language = $language
        AND (n.content_full IS NOT NULL OR n.text IS NOT NULL)
        RETURN
            elementId(n) as node_id,
            COALESCE(n.content_full, n.text, '') as content,
            size(COALESCE(n.content_full, n.text, '')) as doc_length,
            n.number as doc_number
        """

        with self.connection.driver.session() as session:
            result = session.run(cypher_query, language=language)
            docs = list(result)

        if not docs:
            logger.warning(f"No documents found for language '{language}'")
            return {}

        # Calculate average document length
        avg_doc_length = np.mean([d['doc_length'] for d in docs])
        total_docs = len(docs)

        # Calculate document frequencies for IDF
        doc_frequencies = {}
        for keyword in keywords:
            keyword_lower = keyword.lower()
            df = sum(1 for d in docs if keyword_lower in d['content'].lower())
            doc_frequencies[keyword] = df

        # Calculate BM25 scores
        scores = {}
        for doc in docs:
            content_lower = doc['content'].lower()
            doc_length = doc['doc_length']

            score = 0.0
            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Term frequency
                tf = content_lower.count(keyword_lower)
                if tf == 0:
                    continue

                # IDF calculation
                df = doc_frequencies[keyword]
                idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)

                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / avg_doc_length))

                score += idf * (numerator / denominator)

            if score > 0:
                scores[doc['node_id']] = score

        # Normalize scores to [0, 1]
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {k: v/max_score for k, v in scores.items()}

        # Return top-k results
        sorted_scores = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k])

        logger.debug(f"BM25 search found {len(sorted_scores)} results for query: {query[:50]}...")

        return sorted_scores

    def search(self,
               query: str,
               query_embedding: Optional[List[float]] = None,
               node_types: List[str] = None,
               top_k: int = 20,
               min_score: float = 0.3,
               language: str = None) -> List[HybridSearchResult]:
        """
        Perform hybrid search combining vector and BM25.

        Args:
            query: Search query text
            query_embedding: Pre-computed query embedding (optional)
            node_types: Types of nodes to search (default: ['Article', 'Paragraph'])
            top_k: Number of results to return
            min_score: Minimum score threshold
            language: Language for search (auto-detect if None)

        Returns:
            List of hybrid search results
        """
        if node_types is None:
            node_types = ['Article', 'Paragraph']

        if language is None:
            language = self.detect_language(query)

        logger.info(f"Performing hybrid search for query in {language}: {query[:50]}...")

        # Collect results from all node types
        all_results = {}

        for node_type in node_types:
            # Get BM25 scores
            bm25_scores = self.calculate_bm25_scores(
                query, language, node_type, top_k * 2
            )

            # Get vector scores if embedding provided
            vector_scores = {}
            if query_embedding:
                vector_scores = self._get_vector_scores(
                    query_embedding, language, node_type, top_k * 2
                )

            # Combine scores
            node_results = self._combine_scores(
                vector_scores, bm25_scores, node_type
            )

            all_results.update(node_results)

        # Convert to result objects and filter by threshold
        results = []
        for node_id, data in all_results.items():
            if data['hybrid_score'] >= min_score:
                results.append(HybridSearchResult(
                    node_id=node_id,
                    uri=data.get('uri', ''),
                    node_type=data.get('node_type', ''),
                    score=data['hybrid_score'],
                    vector_score=data.get('vector_score', 0.0),
                    bm25_score=data.get('bm25_score', 0.0),
                    title=data.get('title'),
                    content=data.get('content'),
                    metadata=data.get('metadata', {})
                ))

        # Sort by score and return top-k
        results.sort(key=lambda x: x.score, reverse=True)
        final_results = results[:top_k]

        logger.info(f"Hybrid search returned {len(final_results)} results")

        # Log top results for debugging
        if final_results:
            top_3 = final_results[:3]
            for i, r in enumerate(top_3, 1):
                logger.debug(
                    f"  {i}. {r.node_type} {r.title or r.node_id}: "
                    f"score={r.score:.3f} (v={r.vector_score:.3f}, b={r.bm25_score:.3f})"
                )

        return final_results

    def _get_vector_scores(self,
                          query_embedding: List[float],
                          language: str,
                          node_type: str,
                          top_k: int) -> Dict[str, float]:
        """
        Get vector similarity scores from database.

        Args:
            query_embedding: Query embedding vector
            language: Language code
            node_type: Type of nodes to search
            top_k: Maximum results

        Returns:
            Dictionary of node_id -> vector score
        """
        cypher_query = f"""
        MATCH (n:{node_type})
        WHERE n.language = $language AND n.embedding IS NOT NULL
        WITH n, vector.similarity.cosine(n.embedding, $embedding) AS similarity
        WHERE similarity > 0.5
        ORDER BY similarity DESC
        LIMIT $top_k
        RETURN
            elementId(n) as node_id,
            similarity as score,
            n.uri as uri,
            CASE '{node_type}'
                WHEN 'Article' THEN 'Art. ' + n.number
                WHEN 'Paragraph' THEN 'Para ' + COALESCE(n.number, '')
                ELSE n.uri
            END as title,
            CASE '{node_type}'
                WHEN 'Article' THEN n.content_full
                WHEN 'Paragraph' THEN n.text
                ELSE null
            END as content
        """

        scores = {}
        with self.connection.driver.session() as session:
            result = session.run(
                cypher_query,
                language=language,
                embedding=query_embedding,
                top_k=top_k
            )

            for record in result:
                scores[record['node_id']] = {
                    'score': record['score'],
                    'uri': record['uri'],
                    'title': record['title'],
                    'content': record['content']
                }

        return scores

    def _combine_scores(self,
                       vector_scores: Dict[str, Dict],
                       bm25_scores: Dict[str, float],
                       node_type: str) -> Dict[str, Dict]:
        """
        Combine vector and BM25 scores into hybrid scores.

        Args:
            vector_scores: Dictionary of node_id -> vector data
            bm25_scores: Dictionary of node_id -> BM25 score
            node_type: Type of nodes

        Returns:
            Dictionary with combined scores and metadata
        """
        all_nodes = set()
        if vector_scores:
            all_nodes.update(vector_scores.keys())
        if bm25_scores:
            all_nodes.update(bm25_scores.keys())

        combined = {}
        for node_id in all_nodes:
            vector_data = vector_scores.get(node_id, {})
            vector_score = vector_data.get('score', 0.0)
            bm25_score = bm25_scores.get(node_id, 0.0)

            # Calculate hybrid score
            hybrid_score = (
                self.vector_weight * vector_score +
                self.bm25_weight * bm25_score
            )

            combined[node_id] = {
                'hybrid_score': hybrid_score,
                'vector_score': vector_score,
                'bm25_score': bm25_score,
                'node_type': node_type,
                'uri': vector_data.get('uri', ''),
                'title': vector_data.get('title', ''),
                'content': vector_data.get('content', ''),
                'metadata': {
                    'node_type': node_type,
                    'has_vector': node_id in vector_scores,
                    'has_bm25': node_id in bm25_scores
                }
            }

        return combined

    def create_fulltext_indexes(self):
        """
        Create full-text indexes for all languages.
        Note: Requires appropriate Neo4j configuration and permissions.
        """
        languages = {
            'de': 'german',
            'fr': 'french',
            'it': 'italian',
            'en': 'english'
        }

        with self.connection.driver.session() as session:
            for lang_code, analyzer in languages.items():
                index_name = f'articles_fulltext_{lang_code}'

                try:
                    # Check if index exists
                    result = session.run(f"SHOW INDEXES WHERE name = '{index_name}'")
                    if list(result):
                        logger.info(f"Full-text index '{index_name}' already exists")
                        continue

                    # Create index
                    session.run(f"""
                        CALL db.index.fulltext.createNodeIndex(
                            '{index_name}',
                            ['Article'],
                            ['content_full'],
                            {{analyzer: '{analyzer}'}}
                        )
                    """)
                    logger.info(f"Created full-text index '{index_name}'")

                except Exception as e:
                    logger.warning(f"Could not create full-text index '{index_name}': {e}")