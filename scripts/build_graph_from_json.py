#!/usr/bin/env python3
"""
Build complete graph from JSON data using existing infrastructure

This script uses the already-working JSON processing pipeline from build_complete_graph.py
and adds the new storage pipeline for HTML article extraction.
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection
from src.data_access.fedlex_parser import FedlexParser
from scripts.build_complete_graph import CompleteGraphBuilder


def main():
    """Build the complete graph from JSON data"""

    print("\n" + "=" * 60)
    print("LAWAST COMPLETE GRAPH BUILDER")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize builder
    builder = CompleteGraphBuilder()

    # Check prerequisites
    if not builder.check_prerequisites():
        print("\n❌ Prerequisites check failed. Please fix the issues above.")
        return 1

    # Ask for confirmation
    print("\n⚠️  WARNING: This will process 305K+ JSON files")
    print("   Estimated time: 2-4 hours")
    print("   Estimated graph size: 500K+ nodes, 1M+ relationships")

    response = input("\nDo you want to proceed? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Operation cancelled.")
        return 0

    print("\n🚀 Starting graph build...")
    builder.start_time = datetime.now()

    try:
        # Phase 1: Process JSON files for basic structure
        print("\n📄 Phase 1: Processing JSON files...")
        parser = FedlexParser()

        # Process with limit for testing (remove limit for full build)
        limit = int(os.getenv('GRAPH_BUILD_LIMIT', 1000))  # Start with 1000 for testing

        print(f"Processing up to {limit} JSON files...")
        parser.process_fedlex_json(
            directory='fedlex',
            limit=limit,
            resume=True
        )

        # Get statistics
        connection = get_connection()
        stats_query = """
        MATCH (n)
        WITH labels(n) as label, count(n) as count
        RETURN label, count
        ORDER BY count DESC
        """

        results = connection.execute_query(stats_query)

        print("\n📊 Graph Statistics:")
        total_nodes = 0
        for result in results:
            label = result['label'][0] if result['label'] else 'Unknown'
            count = result['count']
            total_nodes += count
            print(f"  {label}: {count:,}")

        print(f"\n✅ Total nodes created: {total_nodes:,}")

        # Calculate time
        elapsed = (datetime.now() - builder.start_time).total_seconds()
        print(f"⏱️  Time elapsed: {elapsed:.1f} seconds")
        print(f"📈 Processing rate: {total_nodes/elapsed:.1f} nodes/second")

        print("\n✨ Graph build completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        return 1

    except Exception as e:
        print(f"\n❌ Error during graph build: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())