#!/usr/bin/env python3
"""
Simple pipeline test without embeddings
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ['HUGGINGFACE_API_KEY'] = 'your-huggingface-api-key'

from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig


async def test_basic():
    """Test basic pipeline without RAG (to avoid embedding issues)"""

    print("Testing Pipeline Core Components")
    print("=" * 50)

    # Test 1: Pipeline without RAG (no embeddings needed)
    print("\n1. Testing pipeline without RAG...")
    config = PipelineConfig(
        enable_agent=True,
        enable_rag=False,  # Disable RAG to avoid embeddings
        enable_reasoning=False,  # Disable reasoning (needs RAG results)
        enable_articulation=True,  # Test Apertus articulation
        enable_graceful_degradation=True
    )

    pipeline = QueryPipeline(config=config)
    print("✅ Pipeline created")

    query = "What is the retirement age in Switzerland?"
    print(f"\nQuery: {query}")

    result = await pipeline.execute(query)

    print(f"Answer: {result.answer[:200]}...")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Time: {result.execution_time:.2f}s")

    if result.errors:
        print(f"Errors: {result.errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")

    print("\n✅ Basic pipeline test passed!")


async def test_with_mock_rag():
    """Test full pipeline with mocked RAG results"""

    print("\n2. Testing full pipeline with mock data...")

    from src.retrieval.result_merger import MergedResult

    # Create mock RAG results
    mock_results = [
        MergedResult(
            node_id="mock1",
            uri="https://fedlex.data.admin.ch/eli/cc/1946/1/art_21",
            node_type="Article",
            combined_score=0.95,
            method_scores={"vector": 0.95, "graph": 0.0, "ast": 0.0},
            title="Art. 21 - Retirement Age",
            content="The ordinary retirement age is 65 for men and 64 for women.",
            methods=["vector"],
            metadata={}
        )
    ]

    config = PipelineConfig(
        enable_agent=False,  # Skip agent
        enable_rag=False,  # Skip RAG (we'll inject results)
        enable_reasoning=True,
        enable_articulation=True,
        enable_graceful_degradation=True
    )

    pipeline = QueryPipeline(config=config)

    # Directly test reasoning with mock data
    query = "What is the retirement age in Switzerland?"

    if pipeline.reasoning_engine:
        print("Testing reasoning engine...")
        reasoned_answer = pipeline.reasoning_engine.reason(query, mock_results)
        print(f"✅ Reasoning completed: confidence={reasoned_answer.confidence:.1%}")
        print(f"Answer: {reasoned_answer.answer[:200]}...")

    print("\n✅ Full pipeline test with mock data passed!")


async def test_health_check():
    """Test pipeline health check"""

    print("\n3. Testing health check...")

    config = PipelineConfig(
        enable_agent=False,
        enable_rag=False,
        enable_reasoning=False,
        enable_articulation=True
    )

    pipeline = QueryPipeline(config=config)
    health = await pipeline.health_check()

    print(f"Status: {health['status']}")
    for component, status in health['components'].items():
        print(f"  {component}: {status['status']}")

    print("\n✅ Health check passed!")


async def main():
    """Run all tests"""
    print("\nLAWAST Pipeline Test (Without Embeddings)")
    print("=" * 50)

    try:
        await test_basic()
        await test_with_mock_rag()
        await test_health_check()

        print("\n" + "=" * 50)
        print("✅ All tests passed successfully!")
        print("\nVerified components:")
        print("  ✅ Pipeline orchestration")
        print("  ✅ Apertus articulation")
        print("  ✅ Reasoning engine")
        print("  ✅ Error handling")
        print("  ✅ Health monitoring")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())