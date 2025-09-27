#!/usr/bin/env python3
"""
Test script for Swiss Law RAG Challenge queries
Validates LAWAST system against challenge requirements
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

# Import your pipeline
from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig
from src.reasoning.models import ReasonedAnswer


class ChallengeEvaluator:
    """Evaluates LAWAST against Swiss Law RAG Challenge requirements"""

    def __init__(self):
        # Initialize pipeline with full features
        config = PipelineConfig(
            enable_agent=True,
            enable_rag=True,
            enable_reasoning=True,
            enable_articulation=True,
            enable_graceful_degradation=True,
            enable_monitoring=True,
            include_citations=True,
            include_confidence=True
        )
        self.pipeline = QueryPipeline(config)

        # Challenge test cases
        self.test_cases = [
            {
                "id": "Q.a",
                "query": "Welche Rechte hat eine Person gemäss Bundesverfassung bei der Meinungsfreiheit?",
                "expected_citations": ["Art. 16 BV"],
                "expected_answer_keywords": ["Meinung", "frei", "bilden", "äußern", "verbreiten"],
                "min_confidence": 0.8
            },
            {
                "id": "Q.b",
                "query": "Unter welchen Umständen darf ein Arbeitsvertrag in der Probezeit gekündigt werden?",
                "expected_citations": ["Art. 335b OR"],
                "expected_answer_keywords": ["Probezeit", "sieben Tagen", "Frist"],
                "min_confidence": 0.7
            },
            {
                "id": "Q.c",
                "query": "Welche Datenschutzpflichten bestehen für Bundesbehörden?",
                "expected_citations": ["Art. 4", "Art. 5", "Art. 6", "Art. 7", "DSG"],
                "expected_answer_keywords": ["rechtmäßig", "Transparenz", "Zweckbindung", "Datensicherheit"],
                "min_confidence": 0.8
            }
        ]

    async def evaluate_query(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single test query"""
        print(f"\n{'='*60}")
        print(f"Testing {test_case['id']}: {test_case['query'][:50]}...")
        print(f"{'='*60}")

        # Execute query
        start_time = datetime.now()
        result = await self.pipeline.execute(test_case['query'])
        execution_time = (datetime.now() - start_time).total_seconds()

        # Evaluate response - using structured format
        evaluation = {
            "test_id": test_case["id"],
            "query": test_case["query"],
            "answer": result.answer,  # Clean answer text
            "confidence": result.confidence,
            "execution_time": execution_time,
            "citations": [],  # Will be populated from result.citations
            "checks": {
                "has_answer": bool(result.answer),
                "has_confidence": result.confidence is not None,
                "confidence_acceptable": result.confidence >= test_case["min_confidence"],
                "has_citations": bool(result.citations),
                "correct_citations": False,
                "keywords_present": False
            }
        }

        # Format citations for evaluation using challenge format
        if result.citations:
            for citation in result.citations:
                # Use the challenge format if available
                if hasattr(citation, 'format_for_challenge'):
                    citation_str = citation.format_for_challenge()
                else:
                    citation_str = str(citation)
                evaluation["citations"].append(citation_str)

                # Check if expected citations are present
                for expected in test_case["expected_citations"]:
                    if expected in citation_str:
                        evaluation["checks"]["correct_citations"] = True
                        break

        # Check for expected keywords in answer
        answer_lower = result.answer.lower()
        keywords_found = 0
        for keyword in test_case["expected_answer_keywords"]:
            if keyword.lower() in answer_lower:
                keywords_found += 1

        evaluation["checks"]["keywords_present"] = keywords_found >= len(test_case["expected_answer_keywords"]) * 0.5

        # Calculate overall pass/fail
        evaluation["passed"] = all([
            evaluation["checks"]["has_answer"],
            evaluation["checks"]["has_confidence"],
            evaluation["checks"]["confidence_acceptable"],
            evaluation["checks"]["has_citations"],
            evaluation["checks"]["correct_citations"]
        ])

        # Print results
        self._print_results(evaluation)

        return evaluation

    def _print_results(self, evaluation: Dict[str, Any]):
        """Pretty print evaluation results"""
        print(f"\n📊 Results for {evaluation['test_id']}:")
        print(f"├─ Answer: {evaluation['answer'][:200]}...")
        print(f"├─ Confidence: {evaluation['confidence']:.2%}")
        print(f"├─ Citations: {', '.join(evaluation['citations'])}")
        print(f"├─ Execution Time: {evaluation['execution_time']:.2f}s")
        print(f"└─ Status: {'✅ PASSED' if evaluation['passed'] else '❌ FAILED'}")

        if not evaluation["passed"]:
            print("\n  Failed checks:")
            for check, passed in evaluation["checks"].items():
                if not passed:
                    print(f"    - {check}")

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all challenge test cases"""
        print("\n" + "="*60)
        print("🚀 SWISS LAW RAG CHALLENGE EVALUATION")
        print("="*60)

        results = []
        for test_case in self.test_cases:
            result = await self.evaluate_query(test_case)
            results.append(result)

        # Summary
        passed = sum(1 for r in results if r["passed"])
        total = len(results)

        print("\n" + "="*60)
        print("📈 EVALUATION SUMMARY")
        print("="*60)
        print(f"Tests Passed: {passed}/{total}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        print(f"Average Confidence: {sum(r['confidence'] for r in results)/total:.2%}")
        print(f"Average Time: {sum(r['execution_time'] for r in results)/total:.2f}s")

        # Save results
        with open("challenge_evaluation_results.json", "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "passed": passed,
                    "total": total,
                    "success_rate": passed/total
                },
                "results": results
            }, f, indent=2)

        print("\n✅ Results saved to challenge_evaluation_results.json")

        return {
            "passed": passed,
            "total": total,
            "results": results
        }

    def format_challenge_response(self, result: ReasonedAnswer) -> Dict[str, Any]:
        """Format response in challenge-required format"""
        # Extract citations in challenge format
        citations = []
        for citation in result.citations[:5]:  # Limit to top 5
            if citation.article and citation.sr_number:
                # Map SR numbers to law abbreviations
                law_abbrev = self._get_law_abbreviation(citation.sr_number)
                if law_abbrev:
                    citations.append(f"Art. {citation.article} {law_abbrev}")
                else:
                    citations.append(f"Art. {citation.article} (SR {citation.sr_number})")
            elif citation.article:
                citations.append(f"Art. {citation.article}")
            else:
                citations.append(str(citation))

        return {
            "Answer": result.answer,
            "Citations": citations,
            "Confidence": round(result.confidence, 2)
        }

    def _get_law_abbreviation(self, sr_number: str) -> str:
        """Map SR numbers to common abbreviations"""
        mappings = {
            "101": "BV",      # Bundesverfassung
            "220": "OR",      # Obligationenrecht
            "235.1": "DSG",   # Datenschutzgesetz
            "210": "ZGB",     # Zivilgesetzbuch
            "311.0": "StGB",  # Strafgesetzbuch
            "312.0": "StPO",  # Strafprozessordnung
            "172.021": "RVOG", # Regierungs- und Verwaltungsorganisationsgesetz
        }

        # Check if SR number starts with known mapping
        for sr_prefix, abbrev in mappings.items():
            if sr_number.startswith(sr_prefix):
                return abbrev

        return None


async def main():
    """Run the challenge evaluation"""
    evaluator = ChallengeEvaluator()
    await evaluator.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())