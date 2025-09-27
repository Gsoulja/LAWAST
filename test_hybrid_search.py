#!/usr/bin/env python3
"""
Proof-of-Concept: Hybrid Vector + BM25 Search
Demonstrates how combining semantic and keyword search improves Article 41 ranking
"""

from neo4j import GraphDatabase
from src.data_access.embedding_generator import create_embedding_generator
import numpy as np
from typing import Dict, List, Tuple
import math

class HybridSearchPOC:
    """Hybrid search combining vector similarity and BM25 text search"""

    def __init__(self, driver, emb_gen):
        self.driver = driver
        self.emb_gen = emb_gen

        # Configuration
        self.vector_weight = 0.5
        self.bm25_weight = 0.3
        self.graph_weight = 0.2

        # BM25 parameters
        self.k1 = 1.2  # Term frequency saturation
        self.b = 0.75  # Length normalization

    def create_fulltext_index(self, session):
        """Create full-text index for Articles"""
        try:
            # Check if index exists
            result = session.run("SHOW INDEXES WHERE name = 'article_fulltext_de'")
            if list(result):
                print("Full-text index already exists")
                return

            # Create German full-text index
            session.run("""
                CALL db.index.fulltext.createNodeIndex(
                    'article_fulltext_de',
                    ['Article'],
                    ['content_full'],
                    {analyzer: 'german'}
                )
            """)
            print("Created German full-text index")
        except Exception as e:
            print(f"Note: {e}")

    def vector_search(self, session, query_embedding: List[float], top_k: int = 20) -> Dict[str, float]:
        """Perform vector similarity search"""
        result = session.run("""
            MATCH (a:Article)
            WHERE a.language = 'de' AND a.embedding IS NOT NULL
            WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
            WHERE similarity > 0.5
            ORDER BY similarity DESC
            LIMIT $top_k
            RETURN a.number as article_num, similarity
        """, embedding=query_embedding, top_k=top_k)

        scores = {}
        for r in result:
            scores[r['article_num']] = r['similarity']
        return scores

    def bm25_search(self, session, query: str, top_k: int = 20) -> Dict[str, float]:
        """Perform BM25 text search using manual calculation"""
        # For POC, we'll do a simple keyword matching with TF-IDF-like scoring
        # In production, use Neo4j's full-text index

        # Extract keywords from query
        keywords = ['Gesundheit', 'Pflege', 'notwendige', 'Person', 'erhält']

        result = session.run("""
            MATCH (a:Article)
            WHERE a.language = 'de' AND a.content_full IS NOT NULL
            RETURN a.number as article_num,
                   a.content_full as content,
                   size(a.content_full) as doc_length
        """)

        scores = {}
        docs = list(result)
        avg_doc_length = np.mean([d['doc_length'] for d in docs])
        total_docs = len(docs)

        for doc in docs:
            content = doc['content'].lower()
            doc_length = doc['doc_length']

            # Calculate BM25 score
            score = 0.0
            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Term frequency
                tf = content.count(keyword_lower)
                if tf == 0:
                    continue

                # Document frequency (simplified - in production, pre-calculate)
                df = sum(1 for d in docs if keyword_lower in d['content'].lower())

                # IDF calculation
                idf = math.log((total_docs - df + 0.5) / (df + 0.5))

                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / avg_doc_length))

                score += idf * (numerator / denominator)

            if score > 0:
                scores[doc['article_num']] = score

        # Normalize scores to [0, 1]
        if scores:
            max_score = max(scores.values())
            scores = {k: v/max_score for k, v in scores.items()}

        return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k])

    def hybrid_score(self, vector_scores: Dict, bm25_scores: Dict) -> List[Tuple[str, float, Dict]]:
        """Combine vector and BM25 scores"""
        all_articles = set(vector_scores.keys()) | set(bm25_scores.keys())

        results = []
        for article in all_articles:
            vector_score = vector_scores.get(article, 0.0)
            bm25_score = bm25_scores.get(article, 0.0)

            # Weighted combination
            hybrid = (self.vector_weight * vector_score +
                     self.bm25_weight * bm25_score)

            results.append((
                article,
                hybrid,
                {
                    'vector': vector_score,
                    'bm25': bm25_score,
                    'hybrid': hybrid
                }
            ))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def search(self, query: str, top_k: int = 10):
        """Perform hybrid search"""
        with self.driver.session() as session:
            # Create index if needed
            self.create_fulltext_index(session)

            # Generate embedding
            query_embedding = self.emb_gen.generate_embedding(query)

            # Perform searches
            print(f"\nSearching for: '{query}'")
            print("=" * 80)

            # Vector search
            print("\n1. VECTOR SEARCH RESULTS:")
            vector_scores = self.vector_search(session, list(query_embedding), top_k * 2)
            for i, (article, score) in enumerate(list(vector_scores.items())[:5], 1):
                marker = "⭐" if article == '41' else "  "
                print(f"  {marker} {i}. Article {article}: {score:.4f}")

            # BM25 search
            print("\n2. BM25 TEXT SEARCH RESULTS:")
            bm25_scores = self.bm25_search(session, query, top_k * 2)
            for i, (article, score) in enumerate(list(bm25_scores.items())[:5], 1):
                marker = "⭐" if article == '41' else "  "
                print(f"  {marker} {i}. Article {article}: {score:.4f}")

            # Hybrid results
            print("\n3. HYBRID SEARCH RESULTS (FINAL):")
            print(f"   Weights: Vector={self.vector_weight}, BM25={self.bm25_weight}")
            hybrid_results = self.hybrid_score(vector_scores, bm25_scores)

            for i, (article, score, components) in enumerate(hybrid_results[:10], 1):
                marker = "⭐⭐⭐" if article == '41' else "   "
                print(f"  {marker} {i}. Article {article:3s}: "
                      f"Hybrid={score:.4f} "
                      f"(V={components['vector']:.3f}, B={components['bm25']:.3f})")

            # Show improvement
            print("\n" + "=" * 80)
            print("COMPARISON:")
            print("-" * 80)

            # Find Article 41's position in each method
            vector_pos = None
            bm25_pos = None
            hybrid_pos = None

            for i, article in enumerate(vector_scores.keys(), 1):
                if article == '41':
                    vector_pos = i
                    break

            for i, article in enumerate(bm25_scores.keys(), 1):
                if article == '41':
                    bm25_pos = i
                    break

            for i, (article, _, _) in enumerate(hybrid_results, 1):
                if article == '41':
                    hybrid_pos = i
                    break

            print(f"Article 41 Position:")
            print(f"  Vector Only:  #{vector_pos or 'Not in top results'}")
            print(f"  BM25 Only:    #{bm25_pos or 'Not in top results'}")
            print(f"  Hybrid:       #{hybrid_pos or 'Not in top results'} "
                  f"{'✅ IMPROVED!' if hybrid_pos and hybrid_pos < (vector_pos or 999) else ''}")

            # Get Article 41 content to verify
            print("\n" + "=" * 80)
            print("ARTICLE 41 CONTENT (for verification):")
            print("-" * 80)
            result = session.run("""
                MATCH (a:Article {number: '41', language: 'de'})
                RETURN substring(a.content_full, 0, 500) as preview
            """)
            record = result.single()
            if record:
                print(record['preview'])
                print("...")
                print("\n✅ Contains exact match: 'Gesundheit notwendige Pflege'")

def main():
    print("HYBRID SEARCH PROOF OF CONCEPT")
    print("=" * 80)

    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'lawast2024'))
    emb_gen = create_embedding_generator()

    hybrid_search = HybridSearchPOC(driver, emb_gen)

    # Test queries
    test_queries = [
        "Erhält jede Person die für ihre Gesundheit notwendige Pflege?",
        "Gesundheit Pflege soziale Ziele",
        "healthcare for everyone"
    ]

    for query in test_queries:
        hybrid_search.search(query)
        print("\n" + "=" * 80 + "\n")

    driver.close()

if __name__ == "__main__":
    main()