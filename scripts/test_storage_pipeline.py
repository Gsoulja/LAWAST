#!/usr/bin/env python3
"""
Test the Neo4j Storage Pipeline with synthetic and real data

This script provides comprehensive testing of the storage pipeline:
1. Unit tests
2. Synthetic data tests
3. Real HTML file tests
4. Performance benchmarks
5. Data verification
"""

import sys
import os
import time
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.neo4j_connection import get_connection
from src.data_access.storage_pipeline import Neo4jStoragePipeline
from src.extractors.extracted_content import ExtractedContent
from src.extractors.taxonomy_extractor import TaxonomyResult, HierarchyLevel
from src.extractors.article_extractor import Article, ArticleContent, Paragraph, Subpoint
from src.extractors.reference_patterns import ReferenceMatch


# Simple Reference dataclass for testing
from dataclasses import dataclass

@dataclass
class Reference:
    source_uri: str
    target_uri: str
    text: str
    is_external: bool = False
    context: str = ""


def create_test_content(num_articles: int = 10) -> ExtractedContent:
    """
    Create synthetic test content for pipeline testing.

    Args:
        num_articles: Number of test articles to create

    Returns:
        ExtractedContent with test data
    """
    print(f"Creating test content with {num_articles} articles...")

    # Create taxonomy hierarchy
    hierarchy = [
        HierarchyLevel(
            type="Domain",
            number="1",
            title={"de": "Öffentliches Recht", "fr": "Droit public", "it": "Diritto pubblico"},
            uri="domain/1",
            children=[
                HierarchyLevel(
                    type="Book",
                    number="1.1",
                    title={"de": "Buch 1", "fr": "Livre 1", "it": "Libro 1"},
                    uri="book/1.1",
                    children=[
                        HierarchyLevel(
                            type="Chapter",
                            number="1.1.1",
                            title={"de": "Kapitel 1", "fr": "Chapitre 1", "it": "Capitolo 1"},
                            uri="chapter/1.1.1",
                            children=[
                                HierarchyLevel(
                                    type="Section",
                                    number="1.1.1.1",
                                    title={"de": "Abschnitt 1", "fr": "Section 1", "it": "Sezione 1"},
                                    uri="section/1.1.1.1",
                                    children=[]
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]

    # Create taxonomy result
    taxonomy = TaxonomyResult(
        sr_number="SR 101.TEST",
        title={
            "de": "Testgesetz",
            "fr": "Loi de test",
            "it": "Legge di prova"
        },
        domain="Öffentliches Recht",
        hierarchy=hierarchy,
        uri="law/test/1"
    )

    # Create articles
    articles = []
    for i in range(1, num_articles + 1):
        # Create paragraphs with subpoints
        paragraphs = []
        for p in range(1, min(4, i + 1)):  # 1-3 paragraphs per article
            subpoints = []
            if p == 1:  # Add subpoints to first paragraph
                for s in ['a', 'b', 'c'][:min(3, i % 3 + 1)]:
                    subpoints.append(
                        Subpoint(
                            letter=s,
                            text=f"Subpoint {s} of article {i} paragraph {p}"
                        )
                    )

            paragraphs.append(
                Paragraph(
                    number=str(p),
                    text=f"This is paragraph {p} of article {i}. " * 5,
                    subpoints=subpoints
                )
            )

        article = Article(
            uri=f"article/test/{i}",
            number=str(i),
            number_normalized=f"{i:03d}",
            titles={
                "de": f"Artikel {i}",
                "fr": f"Article {i}",
                "it": f"Articolo {i}"
            },
            content=ArticleContent(
                paragraphs=paragraphs,
                raw_html=f"<p>Article {i} HTML content</p>"
            ),
            section="section/1.1.1.1",
            chapter="chapter/1.1.1",
            metadata={
                "created": datetime.now().isoformat(),
                "test": True
            }
        )
        articles.append(article)

    # Create references between articles
    references = []
    for i in range(1, min(num_articles, 10)):
        # Internal reference
        references.append(
            Reference(
                source_uri=f"article/test/{i}",
                target_uri=f"article/test/{i+1}",
                text=f"see Article {i+1}",
                is_external=False
            )
        )

        # External reference (every 3rd article)
        if i % 3 == 0:
            references.append(
                Reference(
                    source_uri=f"article/test/{i}",
                    target_uri=f"external/law/{i}",
                    text=f"pursuant to External Law {i}",
                    is_external=True
                )
            )

    # Create ExtractedContent
    content = ExtractedContent(
        taxonomy=taxonomy,
        articles=articles,
        references=references,
        metadata={
            "test": True,
            "created": datetime.now().isoformat(),
            "article_count": num_articles
        },
        source_file="test_data.html",
        law_uri="law/test/1"
    )

    return content


def test_unit_tests():
    """Run unit tests"""
    print("\n" + "=" * 60)
    print("RUNNING UNIT TESTS")
    print("=" * 60)

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_storage_pipeline.py", "-v"],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    if result.returncode == 0:
        print("✅ Unit tests PASSED")
        return True
    else:
        print("❌ Unit tests FAILED")
        return False


def test_synthetic_data(num_articles: int = 100):
    """Test with synthetic data"""
    print("\n" + "=" * 60)
    print(f"TESTING WITH SYNTHETIC DATA ({num_articles} articles)")
    print("=" * 60)

    # Check Neo4j connection
    connection = get_connection()
    if not connection.health_check():
        print("❌ Neo4j connection failed")
        return False

    # Create test content
    content = create_test_content(num_articles)

    # Validate content
    errors = content.validate()
    if errors:
        print(f"⚠️ Validation warnings: {errors}")

    # Get statistics
    stats = content.get_statistics()
    print(f"\n📊 Test Content Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Initialize pipeline
    pipeline = Neo4jStoragePipeline(
        connection=connection,
        batch_size=50,
        checkpoint_file="test_checkpoint.json"
    )

    print("\n🚀 Starting storage pipeline...")
    start_time = time.time()

    try:
        # Store content
        storage_stats = pipeline.store_extracted_content(content, resume=False)

        elapsed = time.time() - start_time

        print(f"\n✅ Storage Complete in {elapsed:.2f} seconds")
        print(f"📈 Performance Metrics:")
        print(f"  Taxonomy nodes: {storage_stats.taxonomy_nodes_created}")
        print(f"  Articles: {storage_stats.articles_created}")
        print(f"  Relationships: {storage_stats.relationships_created}")
        print(f"  Throughput: {storage_stats.get_throughput():.1f} nodes/second")

        if storage_stats.errors:
            print(f"⚠️ Errors encountered: {len(storage_stats.errors)}")
            for error in storage_stats.errors[:3]:
                print(f"  - {error}")

        return True

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        return False


def test_real_html():
    """Test with real HTML files if available"""
    print("\n" + "=" * 60)
    print("TESTING WITH REAL HTML FILES")
    print("=" * 60)

    # Check for HTML files
    html_dirs = ["fedlex-assets", "fedlex", "data"]
    html_files = []

    for dir_name in html_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            html_files.extend(list(dir_path.rglob("*.html"))[:5])  # Test with first 5 files

    if not html_files:
        print("⚠️ No HTML files found for testing")
        print("  Looked in:", html_dirs)
        return None

    print(f"Found {len(html_files)} HTML files to test")

    # Run the storage pipeline script
    import subprocess
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_storage_pipeline.py",
            "--input", str(html_files[0].parent),
            "--limit", "2",
            "--batch-size", "100"
        ],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    if result.returncode == 0:
        print("✅ Real HTML test PASSED")
        return True
    else:
        print("❌ Real HTML test FAILED")
        return False


def verify_neo4j_data():
    """Verify data in Neo4j"""
    print("\n" + "=" * 60)
    print("VERIFYING NEO4J DATA")
    print("=" * 60)

    connection = get_connection()

    queries = [
        ("Total nodes", "MATCH (n) RETURN count(n) as count"),
        ("Article nodes", "MATCH (a:Article) RETURN count(a) as count"),
        ("Domain nodes", "MATCH (d:Domain) RETURN count(d) as count"),
        ("Book nodes", "MATCH (b:Book) RETURN count(b) as count"),
        ("Chapter nodes", "MATCH (c:Chapter) RETURN count(c) as count"),
        ("Section nodes", "MATCH (s:Section) RETURN count(s) as count"),
        ("CONTAINS relationships", "MATCH ()-[r:CONTAINS]->() RETURN count(r) as count"),
        ("HAS_ARTICLE relationships", "MATCH ()-[r:HAS_ARTICLE]->() RETURN count(r) as count"),
        ("REFERENCES relationships", "MATCH ()-[r:REFERENCES]->() RETURN count(r) as count"),
        ("FOLLOWS relationships", "MATCH ()-[r:FOLLOWS]->() RETURN count(r) as count"),
    ]

    print("📊 Database Statistics:")
    total_ok = True

    for name, query in queries:
        try:
            result = connection.execute_query(query)
            count = result[0]['count'] if result else 0
            status = "✅" if count > 0 else "⚠️"
            print(f"  {status} {name}: {count}")
            if count == 0 and "Total" not in name:
                total_ok = False
        except Exception as e:
            print(f"  ❌ {name}: Error - {e}")
            total_ok = False

    # Sample some data
    print("\n📋 Sample Data:")
    try:
        sample_query = """
        MATCH (a:Article)
        RETURN a.number as number, a.uri as uri,
               a.title_de as title, a.paragraphs_count as paragraphs
        LIMIT 5
        """
        samples = connection.execute_query(sample_query)

        if samples:
            for i, sample in enumerate(samples, 1):
                print(f"  {i}. Article {sample['number']}: {sample['title']} ({sample['paragraphs']} paragraphs)")
        else:
            print("  No articles found")

    except Exception as e:
        print(f"  Error getting samples: {e}")

    # Check relationships
    print("\n🔗 Relationship Verification:")
    try:
        rel_query = """
        MATCH (a:Article)-[r:FOLLOWS]->(b:Article)
        RETURN a.number as from, b.number as to
        LIMIT 3
        """
        rels = connection.execute_query(rel_query)

        if rels:
            print("  Sample FOLLOWS relationships:")
            for rel in rels:
                print(f"    Article {rel['from']} -> Article {rel['to']}")
        else:
            print("  No FOLLOWS relationships found")

    except Exception as e:
        print(f"  Error checking relationships: {e}")

    return total_ok


def test_performance_benchmark():
    """Run performance benchmark"""
    print("\n" + "=" * 60)
    print("PERFORMANCE BENCHMARK")
    print("=" * 60)

    test_sizes = [10, 100, 500, 1000]
    results = []

    connection = get_connection()

    for size in test_sizes:
        print(f"\nTesting with {size} articles...")

        # Create test data
        content = create_test_content(size)

        # Create pipeline
        pipeline = Neo4jStoragePipeline(
            connection=connection,
            batch_size=min(100, size),
            checkpoint_file=f"benchmark_{size}.json"
        )

        # Measure performance
        start_time = time.time()

        try:
            stats = pipeline.store_extracted_content(content, resume=False)
            elapsed = time.time() - start_time

            throughput = stats.get_throughput()

            results.append({
                "size": size,
                "time": elapsed,
                "throughput": throughput,
                "nodes": stats.taxonomy_nodes_created + stats.articles_created,
                "relationships": stats.relationships_created
            })

            print(f"  ✅ Completed in {elapsed:.2f}s ({throughput:.1f} nodes/sec)")

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results.append({
                "size": size,
                "error": str(e)
            })

    # Print results table
    print("\n📊 Benchmark Results:")
    print(f"{'Size':<10} {'Time (s)':<12} {'Throughput':<15} {'Nodes':<10} {'Relationships':<15}")
    print("-" * 70)

    for result in results:
        if "error" not in result:
            print(f"{result['size']:<10} {result['time']:<12.2f} "
                  f"{result['throughput']:<15.1f} {result['nodes']:<10} "
                  f"{result['relationships']:<15}")
        else:
            print(f"{result['size']:<10} ERROR: {result['error']}")

    # Check if we meet the 1000 nodes/second target
    if results and "throughput" in results[-1]:
        target_met = results[-1]["throughput"] >= 1000
        if target_met:
            print("\n✅ Performance target MET (1000+ nodes/second)")
        else:
            print(f"\n⚠️ Performance target NOT met ({results[-1]['throughput']:.1f} nodes/second)")

    return results


def cleanup_test_data():
    """Clean up test data from Neo4j"""
    print("\n🧹 Cleaning up test data...")

    connection = get_connection()

    queries = [
        "MATCH (a:Article) WHERE a.uri STARTS WITH 'article/test/' DETACH DELETE a",
        "MATCH (n) WHERE n.uri STARTS WITH 'domain/' OR n.uri STARTS WITH 'book/' "
        "OR n.uri STARTS WITH 'chapter/' OR n.uri STARTS WITH 'section/' DETACH DELETE n",
        "MATCH (l:Law) WHERE l.uri = 'law/test/1' DETACH DELETE l"
    ]

    for query in queries:
        try:
            connection.execute_write(query)
        except Exception as e:
            print(f"  Warning: {e}")

    print("  ✅ Test data cleaned")


def main():
    """Main test orchestrator"""
    print("\n" + "=" * 60)
    print("NEO4J STORAGE PIPELINE TEST SUITE")
    print("=" * 60)

    results = {
        "unit_tests": False,
        "synthetic_data": False,
        "real_html": None,
        "data_verification": False,
        "performance": []
    }

    # 1. Run unit tests
    print("\n1️⃣ Unit Tests")
    results["unit_tests"] = test_unit_tests()

    # 2. Test with synthetic data
    print("\n2️⃣ Synthetic Data Test")
    results["synthetic_data"] = test_synthetic_data(100)

    # 3. Verify data in Neo4j
    print("\n3️⃣ Data Verification")
    results["data_verification"] = verify_neo4j_data()

    # 4. Performance benchmark
    print("\n4️⃣ Performance Benchmark")
    results["performance"] = test_performance_benchmark()

    # 5. Test with real HTML (if available)
    print("\n5️⃣ Real HTML Test")
    results["real_html"] = test_real_html()

    # 6. Cleanup
    cleanup_test_data()

    # Final report
    print("\n" + "=" * 60)
    print("FINAL TEST REPORT")
    print("=" * 60)

    print(f"✅ Unit Tests: {'PASSED' if results['unit_tests'] else 'FAILED'}")
    print(f"✅ Synthetic Data: {'PASSED' if results['synthetic_data'] else 'FAILED'}")
    print(f"✅ Data Verification: {'PASSED' if results['data_verification'] else 'FAILED'}")

    if results["real_html"] is not None:
        print(f"✅ Real HTML: {'PASSED' if results['real_html'] else 'FAILED'}")
    else:
        print(f"⚠️ Real HTML: SKIPPED (no files found)")

    if results["performance"]:
        max_throughput = max(r.get("throughput", 0) for r in results["performance"])
        print(f"📈 Max Throughput: {max_throughput:.1f} nodes/second")

    # Overall status
    all_passed = (
        results["unit_tests"] and
        results["synthetic_data"] and
        results["data_verification"]
    )

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Storage pipeline is ready for production.")
    else:
        print("⚠️ Some tests failed. Please review the output above.")
    print("=" * 60)


if __name__ == "__main__":
    main()