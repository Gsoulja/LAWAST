#!/usr/bin/env python3
"""
Test vector search to see why Article 9 is returned instead of Article 41
"""

from neo4j import GraphDatabase
from src.data_access.embedding_generator import create_embedding_generator
import numpy as np

def test_vector_search():
    # Generate embedding for the query
    emb_gen = create_embedding_generator()
    query_text = "Erhält jede Person die für ihre Gesundheit notwendige Pflege?"
    query_embedding = emb_gen.generate_embedding(query_text)

    print(f"Query: {query_text}")
    print(f"Embedding generated: {len(query_embedding)} dimensions")
    print("=" * 80)

    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'lawast2024'))

    with driver.session() as session:
        # Vector similarity search
        result = session.run("""
            MATCH (a:Article)
            WHERE a.embedding IS NOT NULL
            WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
            ORDER BY similarity DESC
            LIMIT 15
            RETURN a.number, a.language, a.content_preview, similarity
        """, embedding=list(query_embedding))  # Convert to list for Neo4j

        print('\nTop 15 vector search results:')
        print('=' * 80)
        for i, r in enumerate(result, 1):
            num = r['a.number']
            lang = r['a.language']
            sim = r['similarity']
            preview = r['a.content_preview'][:80] if r['a.content_preview'] else 'No preview'

            # Highlight health-related articles
            marker = "⭐" if num in ['41', '117', '118', '12'] else "  "
            print(f"{marker} {i:2d}. Art {num:3s} ({lang}): similarity = {sim:.4f}")
            print(f"      {preview}...")

        # Now check specific articles
        print("\n\nDirect similarity check for key articles:")
        print("=" * 80)

        for article_num in ['9', '12', '41', '117', '118']:
            result = session.run("""
                MATCH (a:Article)
                WHERE a.number = $num AND a.language = 'de' AND a.embedding IS NOT NULL
                WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
                RETURN a.number, similarity, a.content_preview
                LIMIT 1
            """, num=article_num, embedding=list(query_embedding))

            record = result.single()
            if record:
                print(f"Art {article_num}: similarity = {record['similarity']:.4f}")
                preview = record['a.content_preview'][:100] if record['a.content_preview'] else ''
                if 'Gesundheit' in preview or 'Pflege' in preview:
                    print(f"  ✅ Contains health keywords: {preview[:80]}...")
                else:
                    print(f"  ❌ No health keywords: {preview[:80]}...")

    driver.close()

if __name__ == "__main__":
    test_vector_search()