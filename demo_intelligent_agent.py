#!/usr/bin/env python3
"""
Demo script for the Intelligent Agent System
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.context import IntelligentAgent, QueryAnalyzer
from src.retrieval.triple_rag import TripleRAG, TripleRAGConfig


def demo_query_analysis():
    """Demonstrate query analysis capabilities"""
    print("\n" + "="*60)
    print("QUERY ANALYSIS DEMO")
    print("="*60)

    analyzer = QueryAnalyzer()

    test_queries = [
        "What is Article 121a of the Swiss Constitution?",
        "Compare ordinary and simplified naturalization",
        "How to apply for citizenship?",
        "What are the requirements?",  # Ambiguous
        "Recent changes to tax law",  # Missing time context
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        analysis = analyzer.analyze(query)
        print(f"  Intent: {analysis.intent.value}")
        print(f"  Complexity: {analysis.complexity.value}")
        print(f"  Confidence: {analysis.confidence:.2%}")
        print(f"  Ambiguity: {analysis.ambiguity_score:.2%}")
        if analysis.entities:
            print(f"  Entities: {analysis.entities}")
        if analysis.missing_context:
            print(f"  Missing: {analysis.missing_context}")


def demo_agent_without_rag():
    """Demonstrate agent without Triple RAG"""
    print("\n" + "="*60)
    print("INTELLIGENT AGENT DEMO (Without RAG)")
    print("="*60)

    # Create agent without Triple RAG
    agent = IntelligentAgent(triple_rag=None)

    # Test simple query
    print("\n1. Simple Query:")
    response = agent.process_query("What is Article 121a?")
    print(f"   Strategy: {response.strategy_used}")
    print(f"   Confidence: {response.confidence:.2%}")
    print(f"   Response: {response.response[:100]}...")

    # Test ambiguous query
    print("\n2. Ambiguous Query:")
    response = agent.process_query("What are the requirements for citizenship?")
    print(f"   Needs clarification: {response.clarification_needed}")
    if response.clarification_needed:
        print(f"   Questions: {response.response[:200]}...")

        # Simulate clarification response
        print("\n3. After Clarification:")
        response2 = agent.process_clarification_response(
            session_id=response.session_id,
            clarification_response="Naturalization",
            original_query="What are the requirements for citizenship?"
        )
        print(f"   Strategy: {response2.strategy_used}")
        print(f"   Confidence: {response2.confidence:.2%}")


def demo_session_management():
    """Demonstrate session management"""
    print("\n" + "="*60)
    print("SESSION MANAGEMENT DEMO")
    print("="*60)

    agent = IntelligentAgent(triple_rag=None)

    # Create a session with multiple queries
    queries = [
        "Tell me about Swiss citizenship",
        "What are the language requirements?",
        "How long does the process take?",
    ]

    session_id = None
    for i, query in enumerate(queries, 1):
        print(f"\nTurn {i}: {query}")
        if session_id:
            response = agent.process_query(query, session_id=session_id)
        else:
            response = agent.process_query(query)
            session_id = response.session_id

        print(f"   Session: {session_id[:8]}...")

    # Get session summary
    summary = agent.get_session_summary(session_id)
    if summary:
        print(f"\nSession Summary:")
        print(f"   Turns: {summary['history_length'] // 2}")
        print(f"   Topics: {summary['context'].get('topics', [])}")
        print(f"   Entities: {summary['context'].get('extracted_entities', [])}")


def demo_with_mock_rag():
    """Demonstrate agent with mock Triple RAG"""
    print("\n" + "="*60)
    print("INTELLIGENT AGENT WITH MOCK RAG")
    print("="*60)

    try:
        # Try to create real Triple RAG (will fail if Neo4j not running)
        config = TripleRAGConfig(use_parallel=False)
        triple_rag = TripleRAG(config=config)
        print("Using real Triple RAG")
    except:
        # Create mock Triple RAG
        from unittest.mock import Mock
        triple_rag = Mock()

        # Mock search results
        mock_result = Mock()
        mock_result.content = "Swiss citizenship requires 10 years of residence..."
        mock_result.metadata = {"source": "Article 15"}

        mock_metrics = Mock()
        mock_metrics.total_time = 0.5

        triple_rag.search.return_value = ([mock_result], mock_metrics)
        print("Using mock Triple RAG")

    agent = IntelligentAgent(triple_rag=triple_rag)

    # Test with RAG
    print("\nQuery with RAG retrieval:")
    response = agent.process_query("What are the requirements for naturalization?")
    print(f"   Strategy: {response.strategy_used}")
    print(f"   Confidence: {response.confidence:.2%}")
    if response.search_metrics:
        print(f"   Search time: {response.search_metrics.total_time:.2f}s")
    print(f"   Response preview: {response.response[:200]}...")


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# LAWAST INTELLIGENT AGENT SYSTEM DEMO")
    print("#"*60)

    # Run demos
    demo_query_analysis()
    demo_agent_without_rag()
    demo_session_management()
    demo_with_mock_rag()

    print("\n" + "#"*60)
    print("# Demo Complete!")
    print("#"*60)