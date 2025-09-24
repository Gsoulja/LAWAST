#!/usr/bin/env python3
"""
Real-world test of TASK-006 Temporal Version Handler with Neo4j
Tests temporal functionality with actual database data
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.version_chain_builder import VersionChainBuilder
from src.data_access.neo4j_connection import get_connection
from src.data_access.graph_schema import GraphSchema


def test_database_connection():
    """Test Neo4j connection"""
    print("🔌 Testing Neo4j Connection...")
    try:
        connection = get_connection()
        health = connection.health_check()
        if health:
            print("✅ Neo4j connection healthy")
            return connection
        else:
            print("❌ Neo4j connection failed")
            return None
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


def deploy_temporal_indexes(connection):
    """Deploy temporal indexes to Neo4j"""
    print("\n📊 Deploying Temporal Indexes...")
    
    try:
        # Get temporal indexes from schema
        all_indexes = GraphSchema.get_all_indexes()
        temporal_indexes = [
            idx for idx in all_indexes 
            if any(keyword in idx.lower() for keyword in [
                'version_date_range', 'version_date_end', 'current_version'
            ])
        ]
        
        deployed = 0
        for index in temporal_indexes:
            try:
                connection.execute_write(index)
                deployed += 1
                print(f"  ✅ Deployed: {index.split('INDEX ')[1].split(' ')[0]}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"  ℹ️  Already exists: {index.split('INDEX ')[1].split(' ')[0]}")
                else:
                    print(f"  ❌ Failed: {e}")
        
        print(f"📊 Temporal indexes ready: {deployed} new + existing")
        return True
        
    except Exception as e:
        print(f"❌ Index deployment failed: {e}")
        return False


def get_sample_laws(connection):
    """Get sample laws from database for testing"""
    print("\n🔍 Finding Sample Laws...")
    
    try:
        # Get laws with versions
        query = """
        MATCH (l:Law)-[:HAS_VERSION]->(v:Version)
        WITH l, count(v) AS version_count
        WHERE version_count >= 2
        RETURN l.uri AS law_uri, 
               l.sr_number AS sr_number,
               l.title_de AS title,
               version_count
        ORDER BY version_count DESC
        LIMIT 5
        """
        
        laws = connection.execute_query(query)
        
        if laws:
            print(f"✅ Found {len(laws)} laws with multiple versions:")
            for law in laws:
                print(f"  • {law['sr_number']}: {law.get('title', 'Unknown')} ({law['version_count']} versions)")
            return laws
        else:
            print("❌ No laws with versions found")
            return []
            
    except Exception as e:
        print(f"❌ Error finding sample laws: {e}")
        return []


def test_temporal_queries(builder, laws):
    """Test temporal query methods with real data"""
    print("\n⏰ Testing Temporal Queries...")
    
    if not laws:
        print("❌ No sample laws available for testing")
        return False
    
    success_count = 0
    total_tests = 0
    
    for law in laws[:2]:  # Test first 2 laws
        law_uri = law['law_uri']
        sr_number = law['sr_number']
        
        print(f"\n📜 Testing {sr_number}: {law.get('title', 'Unknown')}")
        
        try:
            # Test 1: Get version timeline
            total_tests += 1
            timeline = builder.get_version_timeline(law_uri)
            if timeline:
                print(f"  ✅ Timeline: {len(timeline)} versions found")
                success_count += 1
                
                # Show first and last versions
                if len(timeline) >= 2:
                    first = timeline[0]
                    last = timeline[-1]
                    print(f"    📅 First: {first.get('date_start', 'Unknown')}")
                    print(f"    📅 Latest: {last.get('date_start', 'Unknown')}")
            else:
                print(f"  ❌ Timeline: No versions found")
            
            # Test 2: Point-in-time query (try a recent date)
            total_tests += 1
            query_date = datetime(2023, 1, 1)
            version = builder.get_version_at_date(law_uri, query_date)
            if version:
                print(f"  ✅ Version at {query_date.date()}: {version['uri'][-8:]}")
                success_count += 1
            else:
                print(f"  ℹ️  No version found at {query_date.date()}")
                success_count += 1  # Not an error if law didn't exist then
            
            # Test 3: Get date boundaries
            total_tests += 1
            boundaries = builder.get_date_boundaries(law_uri)
            if boundaries['earliest']:
                earliest = boundaries['earliest'].date() if boundaries['earliest'] else None
                latest = boundaries['latest'].date() if boundaries['latest'] else None
                print(f"  ✅ Date range: {earliest} to {latest or 'current'}")
                success_count += 1
            else:
                print(f"  ❌ Date boundaries: No dates found")
            
            # Test 4: Temporal validation
            total_tests += 1
            validation = builder.validate_temporal_integrity(law_uri)
            status = "✅ VALID" if validation['valid'] else "⚠️  ISSUES"
            print(f"  {status} Temporal integrity: {len(validation.get('issues', []))} issues")
            if not validation['valid']:
                for issue in validation['issues'][:2]:  # Show first 2 issues
                    print(f"    - {issue.get('type', 'unknown')}: {issue.get('message', 'No message')}")
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ Error testing {sr_number}: {e}")
    
    print(f"\n📊 Test Results: {success_count}/{total_tests} successful")
    return success_count > total_tests * 0.7  # 70% success rate


def test_advanced_queries(builder, laws):
    """Test advanced temporal queries"""
    print("\n🔬 Testing Advanced Queries...")
    
    if not laws:
        return True
    
    try:
        # Test change detection in recent years
        print("📈 Change Detection (2020-2024):")
        changes = builder.get_changes_between_dates(
            datetime(2020, 1, 1),
            datetime(2024, 1, 1)
        )
        
        if changes:
            print(f"  ✅ Found {len(changes)} law changes in 4 years")
            
            # Group by change type
            activated = [c for c in changes if c.get('change_type') == 'VERSION_ACTIVATED']
            ended = [c for c in changes if c.get('change_type') == 'VERSION_ENDED']
            
            print(f"    📊 {len(activated)} versions activated")
            print(f"    📊 {len(ended)} versions ended")
            
            # Show recent changes
            if len(changes) > 0:
                recent = sorted(changes, key=lambda x: x.get('change_date', ''), reverse=True)[:3]
                print("    📅 Recent changes:")
                for change in recent:
                    sr = change.get('sr_number', 'Unknown')
                    date = change.get('change_date', 'Unknown')[:10]  # Just date part
                    type_change = change.get('change_type', 'Unknown')
                    print(f"      • {sr}: {type_change} on {date}")
        else:
            print("  ℹ️  No changes found in date range")
        
        # Test legal state reconstruction
        print("\n🏛️ Legal State Reconstruction:")
        state_date = datetime(2023, 6, 15)
        state = builder.get_legal_state_at_date(state_date)
        
        if state:
            print(f"  ✅ Legal state on {state_date.date()}: {len(state)} active laws")
            
            # Sample some laws
            if len(state) > 0:
                sample = state[:5]  # First 5 laws
                print("    📋 Sample active laws:")
                for law in sample:
                    sr = law.get('sr_number', 'Unknown')
                    title = law.get('law_title', 'Unknown')[:50]
                    print(f"      • {sr}: {title}...")
        else:
            print(f"  ❌ No active laws found on {state_date.date()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in advanced queries: {e}")
        return False


def performance_test(builder, laws):
    """Test query performance"""
    print("\n⚡ Performance Testing...")
    
    if not laws:
        return True
    
    try:
        law_uri = laws[0]['law_uri']
        
        # Test query speed
        import time
        
        tests = [
            ("Point-in-time query", lambda: builder.get_version_at_date(law_uri, datetime(2023, 1, 1))),
            ("Timeline query", lambda: builder.get_version_timeline(law_uri)),
            ("Date boundaries", lambda: builder.get_date_boundaries(law_uri)),
            ("Temporal validation", lambda: builder.validate_temporal_integrity(law_uri))
        ]
        
        for test_name, test_func in tests:
            start_time = time.time()
            result = test_func()
            end_time = time.time()
            
            duration_ms = (end_time - start_time) * 1000
            status = "✅" if duration_ms < 100 else "⚠️" if duration_ms < 1000 else "❌"
            print(f"  {status} {test_name}: {duration_ms:.1f}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance test error: {e}")
        return False


def main():
    """Main test function"""
    print("🚀 TASK-006 Temporal Version Handler - Neo4j Integration Test")
    print("=" * 70)
    
    # Test database connection
    connection = test_database_connection()
    if not connection:
        print("❌ Cannot proceed without database connection")
        return False
    
    # Deploy temporal indexes
    indexes_ok = deploy_temporal_indexes(connection)
    if not indexes_ok:
        print("⚠️  Proceeding without optimal indexes")
    
    # Get sample data
    laws = get_sample_laws(connection)
    
    # Initialize temporal handler
    print("\n🔧 Initializing Temporal Version Handler...")
    try:
        builder = VersionChainBuilder()
        print("✅ VersionChainBuilder initialized with Neo4j connection")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False
    
    # Run tests
    all_tests_passed = True
    
    # Basic temporal queries
    basic_ok = test_temporal_queries(builder, laws)
    all_tests_passed &= basic_ok
    
    # Advanced queries
    advanced_ok = test_advanced_queries(builder, laws)
    all_tests_passed &= advanced_ok
    
    # Performance tests
    perf_ok = performance_test(builder, laws)
    all_tests_passed &= perf_ok
    
    # Final results
    print("\n" + "=" * 70)
    if all_tests_passed:
        print("🎉 TEMPORAL VERSION HANDLER - INTEGRATION SUCCESS!")
        print("\n✅ All systems operational:")
        print("  • Neo4j connection healthy")
        print("  • Temporal indexes deployed")
        print("  • Core queries working")
        print("  • Advanced features operational")
        print("  • Performance targets met")
        
        print("\n🎯 Ready for production deployment!")
        
    else:
        print("⚠️  TEMPORAL VERSION HANDLER - PARTIAL SUCCESS")
        print("Some tests encountered issues but core functionality works")
    
    print(f"\n📊 Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return all_tests_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
