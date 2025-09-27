#!/usr/bin/env python3
"""
Generate embeddings for ALL language versions of ALL articles
"""

from neo4j import GraphDatabase
from src.data_access.embedding_generator import create_embedding_generator
import time

def generate_all_embeddings():
    print("Generating embeddings for ALL language versions...")
    print("=" * 80)

    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'lawast2024'))
    emb_gen = create_embedding_generator()

    with driver.session() as session:
        # Count articles that need embeddings
        result = session.run("""
            MATCH (a:Article)
            WHERE a.content_full IS NOT NULL AND a.embedding IS NULL
            RETURN count(a) as total, collect(DISTINCT a.language) as languages
        """)
        record = result.single()
        total = record['total']
        languages = record['languages']

        print(f"Found {total} Articles without embeddings")
        print(f"Languages needing embeddings: {', '.join(languages)}")
        print()

        # Process in batches
        batch_size = 50
        offset = 0
        generated = 0
        errors = 0

        start_time = time.time()

        while offset < total:
            # Fetch batch - use elementId() instead of deprecated id()
            result = session.run("""
                MATCH (a:Article)
                WHERE a.content_full IS NOT NULL AND a.embedding IS NULL
                RETURN elementId(a) as element_id,
                       a.content_full as content,
                       a.number as num,
                       a.language as lang
                SKIP $offset LIMIT $batch_size
            """, offset=offset, batch_size=batch_size)

            batch = list(result)
            if not batch:
                break

            for record in batch:
                try:
                    # Generate embedding from FULL content
                    embedding = emb_gen.generate_embedding(record['content'])

                    # Update the embedding using elementId
                    session.run("""
                        MATCH (a:Article)
                        WHERE elementId(a) = $element_id
                        SET a.embedding = $embedding
                    """, element_id=record['element_id'], embedding=embedding)

                    generated += 1
                    if generated % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = generated / elapsed
                        remaining = (total - generated) / rate
                        print(f"  Generated {generated}/{total} embeddings ({generated/total*100:.1f}%) - {remaining:.0f}s remaining")

                except Exception as e:
                    errors += 1
                    print(f"  Error with Article {record['num']} ({record['lang']}): {e}")

            offset += batch_size

        print(f"\n✅ Generated {generated} embeddings")
        if errors > 0:
            print(f"⚠️  {errors} errors occurred")

        # Verify all languages now have embeddings
        print("\nVerifying embeddings by language:")
        result = session.run("""
            MATCH (a:Article)
            RETURN a.language as lang,
                   count(a) as total,
                   sum(CASE WHEN a.embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding
            ORDER BY lang
        """)

        for r in result:
            lang = r['lang']
            total = r['total']
            with_emb = r['with_embedding']
            pct = (with_emb/total*100) if total > 0 else 0
            status = "✅" if pct == 100 else "⚠️"
            print(f"  {status} {lang}: {with_emb}/{total} ({pct:.1f}%)")

        # Test with health query in multiple languages
        print("\nTesting health query in multiple languages:")
        print("-" * 60)

        test_queries = {
            'de': "Erhält jede Person die für ihre Gesundheit notwendige Pflege?",
            'fr': "Chaque personne reçoit-elle les soins nécessaires à sa santé?",
            'it': "Ogni persona riceve le cure necessarie per la sua salute?",
            'en': "Does every person receive the care necessary for their health?"
        }

        for lang, query in test_queries.items():
            query_embedding = emb_gen.generate_embedding(query)

            result = session.run("""
                MATCH (a:Article)
                WHERE a.number IN ['9', '41', '12', '117', '118']
                  AND a.language = $lang
                  AND a.embedding IS NOT NULL
                WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
                ORDER BY similarity DESC
                LIMIT 3
                RETURN a.number, similarity
            """, lang=lang, embedding=list(query_embedding))

            print(f"\n{lang.upper()} query: Top 3 results")
            for i, r in enumerate(result, 1):
                marker = "⭐" if r['a.number'] == '41' else "  "
                print(f"  {marker} {i}. Article {r['a.number']}: {r['similarity']:.4f}")

    driver.close()

if __name__ == "__main__":
    generate_all_embeddings()