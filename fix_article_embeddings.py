#!/usr/bin/env python3
"""
Fix Article embeddings by regenerating them from content_full instead of content_preview
"""

from neo4j import GraphDatabase
from src.data_access.embedding_generator import create_embedding_generator
import time

def fix_article_embeddings():
    print("Fixing Article embeddings...")
    print("=" * 80)

    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'lawast2024'))
    emb_gen = create_embedding_generator()

    with driver.session() as session:
        # Count articles that need fixing
        result = session.run("""
            MATCH (a:Article)
            WHERE a.content_full IS NOT NULL
            RETURN count(a) as total
        """)
        total = result.single()['total']
        print(f"Found {total} Articles to process")

        # Process in batches
        batch_size = 50
        offset = 0
        fixed = 0

        while offset < total:
            # Fetch batch
            result = session.run("""
                MATCH (a:Article)
                WHERE a.content_full IS NOT NULL
                RETURN id(a) as id, a.content_full as content, a.number as num, a.language as lang
                SKIP $offset LIMIT $batch_size
            """, offset=offset, batch_size=batch_size)

            batch = list(result)
            if not batch:
                break

            for record in batch:
                try:
                    # Generate new embedding from FULL content
                    embedding = emb_gen.generate_embedding(record['content'])

                    # Update the embedding
                    session.run("""
                        MATCH (a:Article)
                        WHERE id(a) = $id
                        SET a.embedding = $embedding
                    """, id=record['id'], embedding=embedding)

                    fixed += 1
                    if fixed % 10 == 0:
                        print(f"  Fixed {fixed}/{total} articles...")

                except Exception as e:
                    print(f"  Error with Article {record['num']} ({record['lang']}): {e}")

            offset += batch_size

        print(f"\n✅ Fixed {fixed} Article embeddings")

        # Test the fix with our health query
        print("\nTesting with health query...")
        query_embedding = emb_gen.generate_embedding("Erhält jede Person die für ihre Gesundheit notwendige Pflege?")

        result = session.run("""
            MATCH (a:Article)
            WHERE a.number IN ['9', '41', '12', '117', '118']
              AND a.language = 'de'
              AND a.embedding IS NOT NULL
            WITH a, vector.similarity.cosine(a.embedding, $embedding) AS similarity
            ORDER BY similarity DESC
            RETURN a.number, similarity
        """, embedding=list(query_embedding))

        print("\nNew similarity scores:")
        for r in result:
            marker = "⭐" if r['a.number'] == '41' else "  "
            print(f"{marker} Article {r['a.number']}: {r['similarity']:.4f}")

    driver.close()

if __name__ == "__main__":
    start = time.time()
    fix_article_embeddings()
    print(f"\nCompleted in {time.time() - start:.1f} seconds")