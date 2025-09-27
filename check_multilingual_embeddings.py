#!/usr/bin/env python3
"""
Check which language versions have content and embeddings
"""

from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'lawast2024'))

with driver.session() as session:
    # Check overall statistics
    result = session.run("""
        MATCH (a:Article)
        RETURN a.language as lang,
               count(a) as total,
               sum(CASE WHEN a.content_full IS NOT NULL THEN 1 ELSE 0 END) as with_content,
               sum(CASE WHEN a.embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding
        ORDER BY lang
    """)

    print("Overall statistics by language:")
    print("=" * 70)
    print(f"{'Language':<10} {'Total':<10} {'Has Content':<15} {'Has Embedding':<15}")
    print("-" * 70)

    for r in result:
        lang = r['lang'] if r['lang'] else 'None'
        total = r['total']
        with_content = r['with_content']
        with_embedding = r['with_embedding']

        content_pct = (with_content/total*100) if total > 0 else 0
        embedding_pct = (with_embedding/total*100) if total > 0 else 0

        print(f"{lang:<10} {total:<10} {with_content:<6} ({content_pct:5.1f}%) {with_embedding:<6} ({embedding_pct:5.1f}%)")

    print("\n\nDetailed check for Articles 9, 12, 41, 117, 118:")
    print("=" * 70)

    result = session.run("""
        MATCH (a:Article)
        WHERE a.number IN ['9', '12', '41', '117', '118']
        RETURN a.number as num,
               a.language as lang,
               a.content_full IS NOT NULL as has_content,
               a.content_preview IS NOT NULL as has_preview,
               a.embedding IS NOT NULL as has_embedding,
               size(coalesce(a.content_full, '')) as content_length
        ORDER BY toInteger(a.number), a.language
    """)

    current_num = None
    for r in result:
        if r['num'] != current_num:
            print(f"\nArticle {r['num']}:")
            current_num = r['num']

        status = []
        if r['has_content']:
            status.append(f"✓ content ({r['content_length']} chars)")
        else:
            status.append('✗ NO content')

        if r['has_preview']:
            status.append('✓ preview')
        else:
            status.append('✗ NO preview')

        if r['has_embedding']:
            status.append('✓ embedding')
        else:
            status.append('✗ NO embedding')

        print(f"  {r['lang']:2s}: {' | '.join(status)}")

driver.close()