#!/usr/bin/env python3
"""
Check what data exists in the Neo4j database
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection


def main():
    print("🔍 Checking Neo4j Database Content")
    print("=" * 40)
    
    try:
        connection = get_connection()
        
        # Check node counts
        queries = [
            ("Total nodes", "MATCH (n) RETURN count(n) AS count"),
            ("Law nodes", "MATCH (l:Law) RETURN count(l) AS count"),
            ("Version nodes", "MATCH (v:Version) RETURN count(v) AS count"),
            ("Article nodes", "MATCH (a:Article) RETURN count(a) AS count"),
        ]
        
        print("📊 Node Counts:")
        for name, query in queries:
            result = connection.execute_query(query)
            count = result[0]['count'] if result else 0
            print(f"  {name}: {count}")
        
        # Check relationships
        rel_queries = [
            ("HAS_VERSION", "MATCH ()-[r:HAS_VERSION]->() RETURN count(r) AS count"),
            ("SUPERSEDES", "MATCH ()-[r:SUPERSEDES]->() RETURN count(r) AS count"),
            ("CONTAINS", "MATCH ()-[r:CONTAINS]->() RETURN count(r) AS count"),
        ]
        
        print("\n🔗 Relationship Counts:")
        for name, query in rel_queries:
            try:
                result = connection.execute_query(query)
                count = result[0]['count'] if result else 0
                print(f"  {name}: {count}")
            except Exception as e:
                print(f"  {name}: 0 (not found)")
        
        # Sample some data if it exists
        print("\n📋 Sample Data:")
        sample_query = "MATCH (n) RETURN labels(n) AS labels, n LIMIT 5"
        try:
            samples = connection.execute_query(sample_query)
            for i, sample in enumerate(samples, 1):
                labels = sample['labels']
                node = sample['n']
                print(f"  {i}. {labels}: {dict(node)}")
        except Exception as e:
            print(f"  Error getting samples: {e}")
        
    except Exception as e:
        print(f"❌ Database error: {e}")


if __name__ == "__main__":
    main()
