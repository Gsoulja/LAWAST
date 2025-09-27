#!/usr/bin/env python3
"""
Analyze search behavior across languages to understand the problem
"""

from neo4j import GraphDatabase
from src.data_access.embedding_generator import create_embedding_generator
import numpy as np
from typing import Dict, List

def analyze_search_behavior():
    print("ANALYZING MULTILINGUAL SEARCH BEHAVIOR")
    print("=" * 80)

    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'lawast2024'))
    emb_gen = create_embedding_generator()

    # Test queries in different languages - all asking about health care
    test_queries = {
        'de': "Erhält jede Person die für ihre Gesundheit notwendige Pflege?",
        'fr': "Chaque personne reçoit-elle les soins nécessaires à sa santé?",
        'it': "Ogni persona riceve le cure necessarie per la sua salute?",
        'en': "Does every person receive the care necessary for their health?",
        'rm': "Survegn mintga persuna la tgira necessaria per sia sanadad?"
    }

    with driver.session() as session:
        # First, check embedding coverage by language
        print("1. EMBEDDING COVERAGE BY LANGUAGE")
        print("-" * 80)
        result = session.run("""
            MATCH (a:Article)
            WITH a.language as lang,
                 count(a) as total,
                 sum(CASE WHEN a.embedding IS NOT NULL THEN 1 ELSE 0 END) as with_emb
            RETURN lang, total, with_emb,
                   toFloat(with_emb) / toFloat(total) * 100 as percentage
            ORDER BY percentage DESC
        """)

        coverage = {}
        for r in result:
            lang = r['lang']
            pct = r['percentage']
            coverage[lang] = pct
            status = "✅" if pct == 100 else "⚠️" if pct > 50 else "❌"
            print(f"  {status} {lang:3s}: {r['with_emb']:3d}/{r['total']:3d} ({pct:6.1f}%)")

        # Now test each query
        print("\n2. QUERY RESULTS BY LANGUAGE")
        print("-" * 80)

        all_results = {}

        for query_lang, query_text in test_queries.items():
            print(f"\n{query_lang.upper()} Query: '{query_text[:50]}...'")

            # Generate embedding for this query
            query_embedding = emb_gen.generate_embedding(query_text)

            # Search in each language
            for search_lang in ['de', 'fr', 'it', 'en', 'rm']:
                result = session.run("""
                    MATCH (a:Article)
                    WHERE a.language = $lang AND a.embedding IS NOT NULL
                    WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
                    ORDER BY similarity DESC
                    LIMIT 5
                    RETURN a.number, a.language, similarity,
                           substring(a.content_full, 0, 100) as preview
                """, lang=search_lang, embedding=list(query_embedding))

                results = list(result)
                if not results:
                    print(f"  Search in {search_lang}: No results (no embeddings)")
                else:
                    top = results[0]
                    is_correct = "⭐" if top['a.number'] == '41' else "❌"
                    print(f"  Search in {search_lang}: {is_correct} Art {top['a.number']} (sim={top['similarity']:.4f})")

                    # Store for comparison
                    key = f"{query_lang}_to_{search_lang}"
                    all_results[key] = {
                        'top_article': top['a.number'],
                        'similarity': top['similarity'],
                        'is_correct': top['a.number'] == '41'
                    }

        # Analyze German-only search strategy
        print("\n3. GERMAN-ONLY SEARCH STRATEGY ANALYSIS")
        print("-" * 80)
        print("Testing: Search always in German, regardless of query language")
        print()

        for query_lang, query_text in test_queries.items():
            query_embedding = emb_gen.generate_embedding(query_text)

            # Search ONLY in German
            result = session.run("""
                MATCH (a:Article)
                WHERE a.language = 'de' AND a.embedding IS NOT NULL
                WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
                ORDER BY similarity DESC
                LIMIT 10
                RETURN a.number, similarity
            """, embedding=list(query_embedding))

            results = list(result)
            print(f"{query_lang.upper()} query → German articles:")
            for i, r in enumerate(results[:5], 1):
                is_correct = "⭐" if r['a.number'] == '41' else "  "
                print(f"  {is_correct} {i}. Article {r['a.number']:3s}: {r['similarity']:.4f}")

            # Find Article 41's position
            art_41_pos = None
            art_41_sim = None
            for i, r in enumerate(results, 1):
                if r['a.number'] == '41':
                    art_41_pos = i
                    art_41_sim = r['similarity']
                    break

            if art_41_pos:
                print(f"  → Article 41 is at position {art_41_pos} with similarity {art_41_sim:.4f}")
            else:
                print(f"  → Article 41 not in top 10!")

        # Test cross-language retrieval
        print("\n4. CROSS-LANGUAGE RETRIEVAL TEST")
        print("-" * 80)
        print("Can we find other language versions after German search?")

        result = session.run("""
            MATCH (a_de:Article {number: '41', language: 'de'})
            MATCH (a_other:Article {number: '41'})
            WHERE a_other.language <> 'de'
            RETURN a_other.language as lang,
                   a_other.content_full IS NOT NULL as has_content,
                   a_other.embedding IS NOT NULL as has_embedding
            ORDER BY lang
        """)

        print("\nArticle 41 availability in other languages:")
        for r in result:
            content = "✅" if r['has_content'] else "❌"
            embedding = "✅" if r['has_embedding'] else "❌"
            print(f"  {r['lang']}: content={content}, embedding={embedding}")

        # Compare similarity scores
        print("\n5. SIMILARITY SCORE COMPARISON")
        print("-" * 80)
        print("Article 41 similarity scores when searching with German query:")

        de_query_embedding = emb_gen.generate_embedding(test_queries['de'])

        result = session.run("""
            MATCH (a:Article)
            WHERE a.number = '41' AND a.embedding IS NOT NULL
            WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
            ORDER BY similarity DESC
            RETURN a.language, similarity
        """, embedding=list(de_query_embedding))

        for r in result:
            print(f"  Article 41 ({r['a.language']}): {r['similarity']:.4f}")

        # Analyze why Article 9 ranks higher
        print("\n6. WHY DOES ARTICLE 9 RANK HIGHER?")
        print("-" * 80)

        result = session.run("""
            MATCH (a:Article)
            WHERE a.number IN ['9', '41'] AND a.language = 'de'
            RETURN a.number,
                   substring(a.content_full, 0, 300) as content,
                   size(a.content_full) as length
            ORDER BY a.number
        """)

        for r in result:
            print(f"\nArticle {r['a.number']} (first 300 chars):")
            print(f"  Length: {r['length']} characters")
            print(f"  Content: {r['content']}")
            if 'Gesundheit' in r['content']:
                print("  ⭐ Contains 'Gesundheit' in first 300 chars")
            if 'Pflege' in r['content']:
                print("  ⭐ Contains 'Pflege' in first 300 chars")

    driver.close()

if __name__ == "__main__":
    analyze_search_behavior()