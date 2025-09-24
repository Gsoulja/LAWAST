#!/usr/bin/env python3
"""
Quick LAWAST Pipeline Test
Run a small test of the complete pipeline
"""
import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=Path.cwd())
        if result.returncode == 0:
            print(f"✅ {description} completed")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False


def check_database_state():
    """Check database state"""
    print("\n📊 Database State:")
    try:
        connection = get_connection()
        
        # Node counts
        query = "MATCH (n) RETURN labels(n) AS labels, count(*) AS count ORDER BY count DESC"
        result = connection.execute_query(query)
        
        print("  Nodes:")
        for row in result:
            labels = row['labels']
            count = row['count']
            print(f"    • {labels[0] if labels else 'Unknown'}: {count}")
        
        # Relationship counts
        query = "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"
        result = connection.execute_query(query)
        
        print("  Relationships:")
        for row in result:
            rel_type = row['type']
            count = row['count']
            print(f"    • {rel_type}: {count}")
        
        return True
    except Exception as e:
        print(f"  ❌ Database check failed: {e}")
        return False


def main():
    print("🚀 LAWAST Quick Pipeline Test")
    print("=" * 40)
    
    # Check initial state
    print("📋 Initial Database State:")
    check_database_state()
    
    # Option 1: Interactive mode - let user choose
    print(f"\n🎯 Choose what to test:")
    print(f"1. JSON Parser (process 5 files)")
    print(f"2. Relationship Extractor (process relationships)")
    print(f"3. HTML Reference Miner (process 10 HTML files)")
    print(f"4. Temporal Queries (test with existing data)")
    print(f"5. Complete Pipeline (small scale)")
    print(f"6. Just show current state")
    
    try:
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == "1":
            # JSON Parser test
            cmd = 'echo "y" | python scripts/run_json_parser.py --limit 5 --clear-checkpoint'
            if run_command(cmd, "JSON Parser (5 files)"):
                check_database_state()
        
        elif choice == "2":
            # Relationship extractor test
            cmd = 'python scripts/run_relationship_extraction.py --limit 10'
            if run_command(cmd, "Relationship Extractor"):
                check_database_state()
        
        elif choice == "3":
            # HTML reference test with article extraction
            cmd = 'python scripts/build_complete_graph.py --html-only --limit 10'
            if run_command(cmd, "HTML Article & Reference Extraction"):
                check_database_state()
        
        elif choice == "4":
            # Temporal queries test
            cmd = 'python scripts/complete_temporal_system_test.py'
            run_command(cmd, "Temporal Query System")
        
        elif choice == "5":
            # Complete pipeline
            print("\n🔄 Running Complete Pipeline (Small Scale)...")
            
            # Step 1: Process some JSON files
            cmd = 'echo "y" | python scripts/run_json_parser.py --limit 3 --clear-checkpoint'
            if run_command(cmd, "Step 1: JSON Processing"):
                
                # Step 2: Extract relationships
                cmd = 'python scripts/run_relationship_extraction.py --limit 5'
                if run_command(cmd, "Step 2: Relationship Extraction"):
                    
                    # Step 3: Test temporal queries
                    cmd = 'python scripts/test_temporal_features.py'
                    run_command(cmd, "Step 3: Temporal Queries")
            
            print("\n📊 Final Database State:")
            check_database_state()
        
        elif choice == "6":
            # Just show state
            print("\n📊 Current Database State:")
            check_database_state()
        
        else:
            print("Invalid choice")
    
    except KeyboardInterrupt:
        print("\n👋 Test cancelled by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    main()
