#!/usr/bin/env python3
"""
Test the integrated hybrid search with Triple RAG system
"""

import asyncio
from src.retrieval.triple_rag import TripleRAG, TripleRAGConfig

def test_integrated_hybrid():
    print("TESTING INTEGRATED HYBRID SEARCH WITH TRIPLE RAG")
    print("=" * 80)

    # Configure with hybrid search enabled
    config = TripleRAGConfig(
        # Enable hybrid search
        enable_hybrid=True,

        # Adjust weights to give hybrid search significant influence
        vector_weight=0.25,
        graph_weight=0.15,
        ast_weight=0.15,
        hybrid_weight=0.45,  # Higher weight for hybrid

        # Hybrid-specific settings
        hybrid_vector_weight=0.6,
        hybrid_bm25_weight=0.4,
        hybrid_top_k=20,

        # Standard settings
        vector_top_k=15,
        graph_max_depth=3,
        ast_max_results=15,
        final_top_k=10,

        # Use sequential for easier debugging
        use_parallel=False
    )

    # Initialize Triple RAG with hybrid
    rag = TripleRAG(config=config)

    # Test queries
    test_queries = [
        {
            'query': "Erhält jede Person die für ihre Gesundheit notwendige Pflege?",
            'expected': '41',
            'description': 'German health query (exact match)'
        },
        {
            'query': "Gesundheit soziale Ziele Pflege",
            'expected': '41',
            'description': 'Keywords query'
        },
        {
            'query': "What are the social objectives regarding healthcare?",
            'expected': '41',
            'description': 'English semantic query'
        }
    ]

    for test_case in test_queries:
        query = test_case['query']
        expected = test_case['expected']
        description = test_case['description']

        print(f"\n{'='*60}")
        print(f"TEST: {description}")
        print(f"Query: {query}")
        print(f"Expected Article: {expected}")
        print("-" * 60)

        # Perform search
        results, metrics = rag.search(query)

        # Display top 5 results
        print(f"\nTop 5 Results:")
        found_expected = False
        expected_position = None

        for i, result in enumerate(results[:5], 1):
            # Extract article number from title or metadata
            article_num = None
            if result.title and 'Art.' in result.title:
                parts = result.title.split()
                for j, part in enumerate(parts):
                    if part == 'Art.' and j + 1 < len(parts):
                        article_num = parts[j + 1].rstrip(':')
                        break

            is_expected = article_num == expected
            if is_expected:
                found_expected = True
                expected_position = i

            marker = "⭐⭐⭐" if is_expected else "   "
            print(f"{marker} {i}. {result.title or result.uri}")
            print(f"     Score: {result.combined_score:.4f}")
            print(f"     Methods: {', '.join(result.methods)}")

            # Show method-specific scores
            if result.method_scores:
                scores_str = ", ".join([
                    f"{method}: {score:.3f}"
                    for method, score in result.method_scores.items()
                ])
                print(f"     Method Scores: {scores_str}")

        # Performance metrics
        print(f"\nSearch Metrics:")
        print(f"  Vector: {metrics.vector_count} results in {metrics.vector_time:.3f}s")
        print(f"  Graph:  {metrics.graph_count} results in {metrics.graph_time:.3f}s")
        print(f"  AST:    {metrics.ast_count} results in {metrics.ast_time:.3f}s")
        print(f"  Hybrid: {metrics.hybrid_count} results in {metrics.hybrid_time:.3f}s")
        print(f"  Merge:  {metrics.merged_count} results in {metrics.merge_time:.3f}s")
        print(f"  Total:  {metrics.total_time:.3f}s")

        # Result summary
        print(f"\n{'='*60}")
        if found_expected:
            print(f"✅ SUCCESS: Article {expected} found at position #{expected_position}")
        else:
            print(f"❌ FAILED: Article {expected} not in top 5 results")

    # Test with hybrid disabled for comparison
    print("\n" + "=" * 80)
    print("COMPARISON: Testing WITHOUT hybrid search")
    print("=" * 80)

    config_no_hybrid = TripleRAGConfig(
        enable_hybrid=False,
        vector_weight=0.4,
        graph_weight=0.3,
        ast_weight=0.3,
        hybrid_weight=0.0,
        use_parallel=False
    )

    rag_no_hybrid = TripleRAG(config=config_no_hybrid)

    query = "Erhält jede Person die für ihre Gesundheit notwendige Pflege?"
    results_no_hybrid, _ = rag_no_hybrid.search(query)

    print(f"\nQuery: {query}")
    print("Top 5 Results WITHOUT Hybrid:")
    for i, result in enumerate(results_no_hybrid[:5], 1):
        article_num = None
        if result.title and 'Art.' in result.title:
            parts = result.title.split()
            for j, part in enumerate(parts):
                if part == 'Art.' and j + 1 < len(parts):
                    article_num = parts[j + 1].rstrip(':')
                    break

        is_expected = article_num == '41'
        marker = "⭐" if is_expected else " "
        print(f"  {marker} {i}. {result.title or result.uri} (Score: {result.combined_score:.4f})")

def main():
    test_integrated_hybrid()

if __name__ == "__main__":
    main()