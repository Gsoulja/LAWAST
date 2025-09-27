#!/usr/bin/env python3
"""
Debug why health-related queries return Article 9 instead of Article 41
"""

from neo4j import GraphDatabase
import sys

def check_articles():
    try:
        driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'lawast2024'))

        with driver.session() as session:
            # Check articles that should match health queries
            result = session.run("""
                MATCH (a:Article)
                WHERE a.number IN ['9', '12', '41', '117', '118']
                RETURN a.number as num,
                       substring(a.content_full, 0, 300) as content,
                       a.title as title,
                       a.embedding IS NOT NULL as has_embedding
                ORDER BY toInteger(a.number)
            """)

            print('Articles related to health/care:\n')
            print('=' * 80)

            for record in result:
                num = record['num']
                title = record['title'] if record['title'] else 'No title'
                has_emb = record['has_embedding']
                content = record['content'] if record['content'] else 'No content'

                print(f"Article {num}: {title}")
                print(f"  Has embedding: {has_emb}")
                print(f"  Content: {content[:200]}...")
                print('-' * 40)

            # Now check what Article 41 specifically contains
            result = session.run("""
                MATCH (a:Article)
                WHERE a.number = '41'
                RETURN a
                LIMIT 1
            """)

            article_41 = result.single()
            if article_41:
                print("\n\nArticle 41 Details:")
                print('=' * 80)
                node = article_41['a']
                for key, value in node.items():
                    if key != 'embedding' and value:
                        print(f"{key}: {str(value)[:200]}")
            else:
                print("\n❌ Article 41 NOT FOUND in database!")

            # Check if we have the correct text about health
            result = session.run("""
                MATCH (a:Article)
                WHERE a.content_full CONTAINS 'Gesundheit'
                   OR a.content_full CONTAINS 'Pflege'
                   OR a.content_full CONTAINS 'notwendige'
                RETURN a.number as num, a.title as title
                ORDER BY toInteger(a.number)
            """)

            print("\n\nArticles mentioning 'Gesundheit', 'Pflege', or 'notwendige':")
            print('=' * 80)
            for record in result:
                print(f"Article {record['num']}: {record['title'] if record['title'] else 'No title'}")

        driver.close()

    except Exception as e:
        print(f"Error: {e}")
        print("\nPossible issues:")
        print("1. Neo4j is not running")
        print("2. Database is empty - run: python scripts/build_lawast_graph.py --sr-filter 101")
        print("3. Wrong credentials")

if __name__ == "__main__":
    check_articles()