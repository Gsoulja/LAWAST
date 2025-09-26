#!/usr/bin/env python3
"""
Test script for the LAWAST Reasoning Engine
"""

import sys
import os
from datetime import datetime, date
from typing import List

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, parent_dir)

from src.retrieval.result_merger import MergedResult
from src.reasoning.engine import ReasoningEngine
from src.reasoning.models import Citation

def create_mock_rag_results() -> List[MergedResult]:
    """Create mock RAG results for testing"""

    # Mock result 1: Article about retirement age
    result1 = MergedResult(
        node_id="node_001",
        uri="SR 831.10 Art. 21",
        node_type="Article",
        combined_score=0.95,
        method_scores={"vector": 0.9, "graph": 0.95, "ast": 1.0},
        title="Ordentliches Rentenalter",
        content="Das ordentliche Rentenalter beginnt für Männer nach Vollendung des 65. Altersjahres und für Frauen nach Vollendung des 64. Altersjahres.",
        methods=["vector", "graph", "ast"],
        metadata={
            "sr_number": "831.10",
            "article_number": "21",
            "in_force_date": "1997-01-01",
            "law_type": "Federal Law",
            "ast_path": "/domain_8/law_831_10/art_21"
        }
    )

    # Mock result 2: Updated retirement age (amendment)
    result2 = MergedResult(
        node_id="node_002",
        uri="SR 831.10 Art. 21 (amended 2024)",
        node_type="Article",
        combined_score=0.92,
        method_scores={"vector": 0.85, "graph": 0.9, "ast": 1.0},
        title="Ordentliches Rentenalter (Revision)",
        content="Ab 1. Januar 2024: Das ordentliche Rentenalter beträgt 65 Jahre für Männer und Frauen.",
        methods=["vector", "graph", "ast"],
        metadata={
            "sr_number": "831.10",
            "article_number": "21",
            "in_force_date": "2024-01-01",
            "law_type": "Federal Law",
            "ast_path": "/domain_8/law_831_10/art_21",
            "version": "2024"
        }
    )

    # Mock result 3: Related provision about early retirement
    result3 = MergedResult(
        node_id="node_003",
        uri="SR 831.10 Art. 40",
        node_type="Article",
        combined_score=0.75,
        method_scores={"vector": 0.7, "graph": 0.8},
        title="Vorbezug der Altersrente",
        content="Personen können die Altersrente um ein oder zwei ganze Jahre vorbeziehen.",
        methods=["vector", "graph"],
        metadata={
            "sr_number": "831.10",
            "article_number": "40",
            "in_force_date": "1997-01-01",
            "law_type": "Federal Law"
        }
    )

    # Mock result 4: Cantonal regulation (lower hierarchy)
    result4 = MergedResult(
        node_id="node_004",
        uri="ZH 831.1 § 5",
        node_type="Article",
        combined_score=0.65,
        method_scores={"vector": 0.6, "graph": 0.7},
        title="Kantonale Ergänzungsleistungen",
        content="Der Kanton Zürich gewährt zusätzliche Ergänzungsleistungen bei Rentenbezug.",
        methods=["vector", "graph"],
        metadata={
            "jurisdiction": "cantonal",
            "canton": "ZH",
            "law_type": "Cantonal Law"
        }
    )

    # Mock result 5: Contradictory information (for testing contradiction handling)
    result5 = MergedResult(
        node_id="node_005",
        uri="SR 831.10 Art. 21",
        node_type="Article",
        combined_score=0.70,
        method_scores={"vector": 0.7},
        title="Ordentliches Rentenalter (old version)",
        content="Das ordentliche Rentenalter beginnt für Männer nach Vollendung des 65. Altersjahres und für Frauen nach Vollendung des 63. Altersjahres.",
        methods=["vector"],
        metadata={
            "sr_number": "831.10",
            "article_number": "21",
            "in_force_date": "1990-01-01",
            "repeal_date": "1996-12-31",
            "law_type": "Federal Law"
        }
    )

    return [result1, result2, result3, result4, result5]


def test_basic_reasoning():
    """Test basic reasoning functionality"""
    print("\n" + "="*60)
    print("TEST 1: Basic Reasoning Engine Functionality")
    print("="*60)

    # Initialize reasoning engine (without Apertus for now)
    engine = ReasoningEngine(
        apertus_client=None,
        config={"enable_llm_reasoning": False}  # Use rule-based reasoning
    )

    # Create mock RAG results
    rag_results = create_mock_rag_results()

    # Test query
    query = "What is the retirement age in Switzerland?"

    print(f"\nQuery: {query}")
    print(f"RAG Results: {len(rag_results)} documents")

    # Run reasoning
    reasoned_answer = engine.reason(query, rag_results)

    # Display results
    print("\n--- REASONING RESULTS ---")
    print(f"Answer: {reasoned_answer.answer}")
    print(f"Confidence: {reasoned_answer.confidence:.2%}")
    print(f"Processing Time: {reasoned_answer.processing_time:.2f}s")

    print(f"\nReasoning Steps: {len(reasoned_answer.reasoning_steps)}")
    for step in reasoned_answer.reasoning_steps:
        print(f"  Step {step.step_number}: {step.description}")
        if step.conclusion:
            print(f"    → {step.conclusion}")

    print(f"\nLegal Rules Applied: {len(reasoned_answer.legal_rules_applied)}")
    for rule in reasoned_answer.legal_rules_applied:
        print(f"  - {rule.rule_type.value}: {rule.description}")

    print(f"\nCitations: {len(reasoned_answer.citations)}")
    for citation in reasoned_answer.citations[:5]:
        print(f"  - {citation}")

    print(f"\nContradictions: {len(reasoned_answer.contradictions)}")
    for contradiction in reasoned_answer.contradictions:
        print(f"  - {contradiction.fact_type}: {contradiction.resolution_strategy}")

    if reasoned_answer.validation_result:
        print(f"\nValidation:")
        print(f"  - Consistent: {reasoned_answer.validation_result.is_consistent}")
        print(f"  - Score: {reasoned_answer.validation_result.consistency_score:.2%}")

    return reasoned_answer


def test_contradiction_handling():
    """Test contradiction detection and resolution"""
    print("\n" + "="*60)
    print("TEST 2: Contradiction Handling")
    print("="*60)

    engine = ReasoningEngine(config={"enable_llm_reasoning": False})

    # Create contradictory results
    results = [
        MergedResult(
            node_id="node_a",
            uri="SR 641.20 Art. 25",
            node_type="Article",
            combined_score=0.9,
            method_scores={"vector": 0.9},
            title="VAT rates",
            content="The standard VAT rate is 7.7%",
            methods=["vector"],
            metadata={"in_force_date": "2024-01-01"}
        ),
        MergedResult(
            node_id="node_b",
            uri="SR 641.20 Art. 25",
            node_type="Article",
            combined_score=0.85,
            method_scores={"graph": 0.85},
            title="VAT rates",
            content="The standard VAT rate is 8.1%",
            methods=["graph"],
            metadata={"in_force_date": "2018-01-01"}
        )
    ]

    query = "What is the VAT rate in Switzerland?"
    reasoned_answer = engine.reason(query, results)

    print(f"\nContradictions detected: {len(reasoned_answer.contradictions)}")
    for c in reasoned_answer.contradictions:
        print(f"  Type: {c.fact_type}")
        print(f"  Resolution: {c.resolution_strategy}")
        print(f"  Confidence Impact: {c.confidence_impact}")


def test_legal_hierarchy():
    """Test legal hierarchy rule application"""
    print("\n" + "="*60)
    print("TEST 3: Legal Hierarchy Rules")
    print("="*60)

    engine = ReasoningEngine(config={"enable_llm_reasoning": False})

    # Create results with different hierarchy levels
    results = [
        MergedResult(
            node_id="node_1",
            uri="BV Art. 10",
            node_type="Article",
            combined_score=0.8,
            method_scores={"vector": 0.8},
            title="Constitutional provision",
            content="Right to life and personal freedom",
            methods=["vector"],
            metadata={"law_type": "Constitution"}
        ),
        MergedResult(
            node_id="node_2",
            uri="SR 311.0 Art. 47",
            node_type="Article",
            combined_score=0.85,
            method_scores={"vector": 0.85},
            title="Federal law provision",
            content="Implementation of constitutional right",
            methods=["vector"],
            metadata={"law_type": "Federal Law"}
        ),
        MergedResult(
            node_id="node_3",
            uri="ZH § 15",
            node_type="Article",
            combined_score=0.9,
            method_scores={"vector": 0.9},
            title="Cantonal provision",
            content="Cantonal implementation details",
            methods=["vector"],
            metadata={"law_type": "Cantonal Law", "jurisdiction": "cantonal"}
        )
    ]

    query = "Which law takes precedence?"
    reasoned_answer = engine.reason(query, results)

    print(f"\nLegal rules applied:")
    for rule in reasoned_answer.legal_rules_applied:
        if rule.rule_type.value == "hierarchy":
            print(f"  Hierarchy Rule: {rule.output_conclusion}")


def test_confidence_scoring():
    """Test confidence scoring with various factors"""
    print("\n" + "="*60)
    print("TEST 4: Confidence Scoring")
    print("="*60)

    engine = ReasoningEngine(config={"enable_llm_reasoning": False})

    # Test with high-quality evidence
    high_quality_results = [
        MergedResult(
            node_id=f"node_{i}",
            uri=f"SR 210 Art. {i}",
            node_type="Article",
            combined_score=0.95,
            method_scores={"vector": 0.9, "graph": 0.95, "ast": 1.0},
            title=f"Article {i}",
            content=f"Legal provision {i}",
            methods=["vector", "graph", "ast"],
            metadata={
                "sr_number": "210",
                "article_number": str(i),
                "in_force_date": "2024-01-01"
            }
        )
        for i in range(1, 4)
    ]

    query = "Test query with high-quality evidence"
    answer1 = engine.reason(query, high_quality_results)

    # Test with low-quality evidence
    low_quality_results = [
        MergedResult(
            node_id="node_low",
            uri="Unknown",
            node_type="Unknown",
            combined_score=0.4,
            method_scores={"vector": 0.4},
            title=None,
            content=None,
            methods=["vector"],
            metadata={}
        )
    ]

    answer2 = engine.reason(query, low_quality_results)

    print(f"\nHigh-quality evidence confidence: {answer1.confidence:.2%}")
    print(f"Low-quality evidence confidence: {answer2.confidence:.2%}")

    # Get detailed explanation
    level1 = engine.confidence_scorer.get_confidence_level(answer1.confidence)
    level2 = engine.confidence_scorer.get_confidence_level(answer2.confidence)

    print(f"\nConfidence levels:")
    print(f"  High-quality: {level1}")
    print(f"  Low-quality: {level2}")


def test_full_explanation():
    """Test the full explanation generation"""
    print("\n" + "="*60)
    print("TEST 5: Full Reasoning Explanation")
    print("="*60)

    engine = ReasoningEngine(config={"enable_llm_reasoning": False})
    rag_results = create_mock_rag_results()

    query = "What is the retirement age for women in Switzerland in 2025?"
    reasoned_answer = engine.reason(query, rag_results)

    # Generate full explanation
    explanation = engine.explain_reasoning(reasoned_answer)
    print(explanation)


def run_all_tests():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# LAWAST REASONING ENGINE TEST SUITE")
    print("#"*60)

    try:
        # Test 1: Basic functionality
        answer1 = test_basic_reasoning()
        print("✅ Test 1 passed")

        # Test 2: Contradiction handling
        test_contradiction_handling()
        print("✅ Test 2 passed")

        # Test 3: Legal hierarchy
        test_legal_hierarchy()
        print("✅ Test 3 passed")

        # Test 4: Confidence scoring
        test_confidence_scoring()
        print("✅ Test 4 passed")

        # Test 5: Full explanation
        test_full_explanation()
        print("✅ Test 5 passed")

        print("\n" + "#"*60)
        print("# ALL TESTS COMPLETED SUCCESSFULLY!")
        print("#"*60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()