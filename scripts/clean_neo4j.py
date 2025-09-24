#!/usr/bin/env python3
"""
Clean Neo4j Database - Remove all nodes and relationships
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection


def clean_database():
    """Clean all nodes and relationships from Neo4j"""
    print("🧹 Cleaning Neo4j Database...")

    connection = get_connection()

    # First, get counts
    print("\n📊 Current Database State:")

    # Count nodes
    query = "MATCH (n) RETURN count(n) as count"
    result = connection.execute_query(query)
    node_count = result[0]['count'] if result else 0
    print(f"  Nodes: {node_count:,}")

    # Count relationships
    query = "MATCH ()-[r]->() RETURN count(r) as count"
    result = connection.execute_query(query)
    rel_count = result[0]['count'] if result else 0
    print(f"  Relationships: {rel_count:,}")

    if node_count == 0 and rel_count == 0:
        print("\n✅ Database is already empty!")
        return

    # Confirm deletion
    response = input(f"\n⚠️  Delete {node_count:,} nodes and {rel_count:,} relationships? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Cancelled")
        return

    print("\n🗑️  Deleting all data...")

    # Delete in batches to avoid memory issues
    batch_size = 10000
    total_deleted = 0

    while True:
        # Delete relationships first, then nodes
        query = f"""
        MATCH (n)
        WITH n LIMIT {batch_size}
        DETACH DELETE n
        RETURN count(n) as deleted
        """

        result = connection.execute_write(query)
        deleted = result[0]['deleted'] if result else 0
        total_deleted += deleted

        if deleted == 0:
            break

        print(f"  Deleted batch: {deleted:,} nodes (Total: {total_deleted:,})")

    print(f"\n✅ Database cleaned! Deleted {total_deleted:,} nodes and their relationships")

    # Verify empty
    query = "MATCH (n) RETURN count(n) as count"
    result = connection.execute_query(query)
    final_count = result[0]['count'] if result else 0

    if final_count == 0:
        print("✅ Database is now empty")
    else:
        print(f"⚠️  Warning: {final_count} nodes remain")


if __name__ == "__main__":
    try:
        clean_database()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)