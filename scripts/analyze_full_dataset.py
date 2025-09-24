#!/usr/bin/env python3
"""
LAWAST Full Dataset Analysis
Analyze the complete Fedlex dataset and provide execution plan
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import time

sys.path.insert(0, str(Path(__file__).parent.parent))


def analyze_directory(base_path: Path, pattern: str = "*.json"):
    """Analyze a directory for JSON files"""
    stats = {
        'file_count': 0,
        'total_size': 0,
        'by_year': defaultdict(int),
        'by_type': defaultdict(int),
        'samples': [],
        'largest_files': []
    }

    files = list(base_path.rglob(pattern))
    stats['file_count'] = len(files)

    for file_path in files:
        file_size = file_path.stat().st_size
        stats['total_size'] += file_size

        # Track large files
        if file_size > 500000:  # > 500KB
            stats['largest_files'].append((str(file_path), file_size))

        # Extract year from path
        year_match = None
        for part in str(file_path).split('/'):
            if part.isdigit() and len(part) == 4:
                year_match = part
                break
        if year_match:
            stats['by_year'][year_match] += 1

        # Get samples (first 5)
        if len(stats['samples']) < 5:
            stats['samples'].append(str(file_path))

    # Sort largest files
    stats['largest_files'] = sorted(stats['largest_files'], key=lambda x: x[1], reverse=True)[:10]

    return stats


def print_section(title, content):
    """Print a formatted section"""
    print(f"\n{'=' * 60}")
    print(f"📊 {title}")
    print('=' * 60)
    print(content)


def format_bytes(bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           LAWAST FULL DATASET ANALYSIS & BUILD PLAN         ║
╚══════════════════════════════════════════════════════════════╝
""")

    print(f"🕐 Analysis started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Analyze each major directory
    directories = {
        'Classified Compilation': 'fedlex/eli/cc',
        'Official Compilation': 'fedlex/eli/oc',
        'Federal Gazette': 'fedlex/eli/fga',
        'Treaties': 'fedlex/eli/treaty'
    }

    total_stats = {
        'total_files': 0,
        'total_size': 0,
        'by_directory': {}
    }

    # Analyze each directory
    for name, path in directories.items():
        dir_path = Path(path)
        if not dir_path.exists():
            print(f"⚠️  Directory not found: {path}")
            continue

        print(f"\n🔍 Analyzing {name}: {path}")
        stats = analyze_directory(dir_path)
        total_stats['total_files'] += stats['file_count']
        total_stats['total_size'] += stats['total_size']
        total_stats['by_directory'][name] = stats

        # Print directory stats
        print(f"   📁 Files: {stats['file_count']:,}")
        print(f"   💾 Size: {format_bytes(stats['total_size'])}")
        if stats['samples']:
            print(f"   📄 Sample: {Path(stats['samples'][0]).name}")

    # DATASET OVERVIEW
    print_section("DATASET OVERVIEW", f"""
Total JSON Files: {total_stats['total_files']:,}
Total Size: {format_bytes(total_stats['total_size'])}

By Directory:
""")
    for name, stats in total_stats['by_directory'].items():
        pct = (stats['file_count'] / total_stats['total_files'] * 100) if total_stats['total_files'] > 0 else 0
        print(f"  • {name:25} {stats['file_count']:7,} files ({pct:5.1f}%) - {format_bytes(stats['total_size'])}")

    # PROCESSING ESTIMATES
    processing_rate = 100  # files per second (conservative)
    total_time_seconds = total_stats['total_files'] / processing_rate
    total_time_minutes = total_time_seconds / 60
    total_time_hours = total_time_minutes / 60

    nodes_per_file = 9  # Average: 1 law, 3 expressions, 5 manifestations
    total_nodes = total_stats['total_files'] * nodes_per_file
    relationships_per_file = 12  # Average relationships
    total_relationships = total_stats['total_files'] * relationships_per_file

    print_section("PROCESSING ESTIMATES", f"""
Processing Rate: {processing_rate} files/second
Total Processing Time: {total_time_hours:.1f} hours ({total_time_minutes:.0f} minutes)
Memory Required: ~2-4 GB (with streaming)
Disk Space for Neo4j: ~8-10 GB

Expected Graph Size:
  • Nodes: ~{total_nodes:,}
  • Relationships: ~{total_relationships:,}
  • Total Graph Objects: ~{(total_nodes + total_relationships):,}
""")

    # EXECUTION PLAN
    print_section("RECOMMENDED EXECUTION PLAN", """
PHASE 1: Environment Setup (5 minutes)
  1. Verify Neo4j is running: docker ps | grep neo4j
  2. Clean database: source venv/bin/activate && echo "yes" | python scripts/clean_neo4j.py
  3. Initialize schema: python scripts/init_neo4j_schema.py

PHASE 2: JSON Processing (Primary) - 20 minutes
  4. Process classified compilation (CC):
     python scripts/run_json_parser.py -d fedlex/eli/cc
     → Creates ~650,000 nodes (Laws, Versions, Expressions)

PHASE 3: JSON Processing (Secondary) - 15 minutes
  5. Process official compilation (OC):
     python scripts/run_json_parser.py -d fedlex/eli/oc
     → Creates ~400,000 nodes (Acts, Publications)

PHASE 4: Relationship Building - 10 minutes
  6. Extract and build relationships:
     python scripts/run_relationship_extraction.py
     → Creates ~1,000,000+ relationships

PHASE 5: JSON Processing (Tertiary) - 40 minutes
  7. Process federal gazette (FGA) - OPTIONAL:
     python scripts/run_json_parser.py -d fedlex/eli/fga
     → Creates ~1,300,000 nodes

  8. Process treaties - OPTIONAL:
     python scripts/run_json_parser.py -d fedlex/eli/treaty
     → Creates ~165,000 nodes

PHASE 6: HTML Processing - 2+ hours (OPTIONAL)
  9. Extract HTML references:
     python scripts/run_html_reference_extraction.py
     → Adds Article nodes and cross-references

PHASE 7: Verification - 5 minutes
  10. Check database content:
      python scripts/check_database_content.py

  11. Test temporal queries:
      python scripts/test_temporal_features.py
""")

    # QUICK START OPTIONS
    print_section("QUICK START OPTIONS", """
Option A: MINIMAL BUILD (CC only) - 30 minutes
  source venv/bin/activate
  echo "yes" | python scripts/clean_neo4j.py
  python scripts/init_neo4j_schema.py
  python scripts/run_json_parser.py -d fedlex/eli/cc
  python scripts/run_relationship_extraction.py
  python scripts/check_database_content.py

Option B: STANDARD BUILD (CC + OC) - 1 hour
  source venv/bin/activate
  echo "yes" | python scripts/clean_neo4j.py
  python scripts/init_neo4j_schema.py
  python scripts/run_json_parser.py -d fedlex/eli/cc
  python scripts/run_json_parser.py -d fedlex/eli/oc
  python scripts/run_relationship_extraction.py
  python scripts/check_database_content.py

Option C: FULL BUILD (All JSON) - 2 hours
  source venv/bin/activate
  python scripts/build_complete_graph_rag.py
""")

    # MONITORING COMMANDS
    print_section("MONITORING COMMANDS", """
During processing, monitor progress with:

1. Watch Neo4j metrics:
   watch -n 5 'echo "MATCH (n) RETURN count(n)" | cypher-shell -u neo4j -p password'

2. Check checkpoint status:
   cat checkpoint_fedlex_eli_*.json | python -m json.tool | head -20

3. Monitor system resources:
   htop  # CPU and memory usage
   iotop # Disk I/O

4. Neo4j Browser:
   http://localhost:7474
   Username: neo4j
   Password: password
""")

    # TROUBLESHOOTING
    print_section("TROUBLESHOOTING", """
Common Issues & Solutions:

1. "Neo4j connection failed"
   → Start Neo4j: docker start lawast-neo4j
   → Check logs: docker logs lawast-neo4j

2. "Out of memory"
   → Reduce batch size: --batch-size 500
   → Process in smaller chunks: --limit 10000

3. "Processing interrupted"
   → Resume from checkpoint: --resume (default)
   → Clear checkpoint to restart: --clear-checkpoint

4. "Slow processing"
   → Check disk I/O: iotop
   → Increase batch size: --batch-size 2000
   → Use SSD if available
""")

    print(f"\n✅ Analysis complete at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n💡 Recommended: Start with Option A (MINIMAL BUILD) to test the system")
    print("📚 Full documentation: See FEDLEX_DATA_CONNECTION_GUIDE.md")


if __name__ == "__main__":
    main()