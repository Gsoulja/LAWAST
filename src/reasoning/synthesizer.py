"""
Multi-source result synthesizer for reasoning engine
"""

import logging
from typing import List, Dict, Any, Set, Tuple, Optional
from collections import defaultdict
from difflib import SequenceMatcher

from ..retrieval.result_merger import MergedResult
from .models import SynthesisResult, Contradiction

logger = logging.getLogger(__name__)


class ResultSynthesizer:
    """
    Synthesizes results from multiple RAG sources into unified facts.
    Handles deduplication, conflict resolution, and source tracking.
    """

    def __init__(self,
                 similarity_threshold: float = 0.85,
                 reliability_weights: Dict[str, float] = None):
        """
        Initialize the synthesizer.

        Args:
            similarity_threshold: Threshold for considering facts as duplicates
            reliability_weights: Weights for different source types
        """
        self.similarity_threshold = similarity_threshold
        self.reliability_weights = reliability_weights or {
            "vector": 0.3,
            "graph": 0.35,
            "ast": 0.35
        }

    def synthesize(self, results: List[MergedResult]) -> SynthesisResult:
        """
        Synthesize multiple RAG results into unified facts.

        Args:
            results: List of merged results from Triple RAG

        Returns:
            Synthesized result with unified facts and contradictions
        """
        if not results:
            return SynthesisResult(
                unified_facts=[],
                complementary_info=[],
                contradictions=[],
                source_mapping={},
                reliability_scores={}
            )

        # Group results by content similarity
        fact_groups = self._group_similar_facts(results)

        # Process each group
        unified_facts = []
        contradictions = []
        source_mapping = {}
        reliability_scores = {}

        for group_id, group_results in fact_groups.items():
            if len(group_results) == 1:
                # Single source, no conflict
                fact = self._convert_to_fact(group_results[0])
                unified_facts.append(fact)
                source_mapping[fact["id"]] = [group_results[0].node_id]
                reliability_scores[fact["id"]] = self._calculate_reliability(group_results[0])
            else:
                # Multiple sources, need to merge/resolve
                fact, contradiction = self._merge_fact_group(group_results)
                unified_facts.append(fact)
                source_mapping[fact["id"]] = [r.node_id for r in group_results]
                reliability_scores[fact["id"]] = self._calculate_group_reliability(group_results)

                if contradiction:
                    contradictions.append(contradiction)

        # Extract complementary information
        complementary_info = self._extract_complementary_info(results, unified_facts)

        # Sort by reliability
        unified_facts.sort(key=lambda f: reliability_scores.get(f["id"], 0), reverse=True)

        return SynthesisResult(
            unified_facts=unified_facts,
            complementary_info=complementary_info,
            contradictions=contradictions,
            source_mapping=source_mapping,
            reliability_scores=reliability_scores
        )

    def _group_similar_facts(self, results: List[MergedResult]) -> Dict[str, List[MergedResult]]:
        """
        Group results by content similarity.

        Args:
            results: List of RAG results

        Returns:
            Dictionary of group_id -> list of similar results
        """
        groups = {}
        used = set()

        for i, result1 in enumerate(results):
            if i in used:
                continue

            group_id = f"group_{i}"
            group = [result1]
            used.add(i)

            for j, result2 in enumerate(results[i+1:], start=i+1):
                if j in used:
                    continue

                similarity = self._calculate_similarity(result1, result2)
                if similarity >= self.similarity_threshold:
                    group.append(result2)
                    used.add(j)

            groups[group_id] = group

        return groups

    def _calculate_similarity(self, result1: MergedResult, result2: MergedResult) -> float:
        """
        Calculate similarity between two results.

        Args:
            result1: First result
            result2: Second result

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Check if same node
        if result1.node_id == result2.node_id:
            return 1.0

        # Check URI similarity
        if result1.uri == result2.uri:
            return 0.95

        # Check content similarity
        if result1.content and result2.content:
            matcher = SequenceMatcher(None, result1.content, result2.content)
            content_sim = matcher.ratio()
        else:
            content_sim = 0.0

        # Check title similarity
        if result1.title and result2.title:
            matcher = SequenceMatcher(None, result1.title, result2.title)
            title_sim = matcher.ratio()
        else:
            title_sim = 0.0

        # Weighted average
        return 0.7 * content_sim + 0.3 * title_sim

    def _merge_fact_group(self,
                         results: List[MergedResult]) -> Tuple[Dict[str, Any], Optional[Contradiction]]:
        """
        Merge a group of similar results into a single fact.

        Args:
            results: List of similar results

        Returns:
            Tuple of (merged fact, contradiction if any)
        """
        # Use highest scoring result as base
        base = max(results, key=lambda r: r.combined_score)

        fact = self._convert_to_fact(base)
        contradiction = None

        # Check for contradictions in metadata
        if self._has_contradictions(results):
            contradiction = self._create_contradiction(results)

        # Merge additional information from other results
        for result in results:
            if result.node_id != base.node_id:
                # Add complementary metadata
                if result.metadata:
                    for key, value in result.metadata.items():
                        if key not in fact["metadata"]:
                            fact["metadata"][key] = value

        return fact, contradiction

    def _has_contradictions(self, results: List[MergedResult]) -> bool:
        """
        Check if results contain contradictory information.

        Args:
            results: List of results to check

        Returns:
            True if contradictions found
        """
        # Check for different versions or dates
        versions = set()
        dates = set()

        for result in results:
            if result.metadata:
                if "version" in result.metadata:
                    versions.add(result.metadata["version"])
                if "in_force_date" in result.metadata:
                    dates.add(result.metadata["in_force_date"])

        return len(versions) > 1 or len(dates) > 1

    def _create_contradiction(self, results: List[MergedResult]) -> Contradiction:
        """
        Create a contradiction object from conflicting results.

        Args:
            results: Conflicting results

        Returns:
            Contradiction object
        """
        # Find the specific contradiction
        fact_type = "version_conflict"

        source1 = {
            "node_id": results[0].node_id,
            "uri": results[0].uri,
            "metadata": results[0].metadata
        }

        source2 = {
            "node_id": results[1].node_id,
            "uri": results[1].uri,
            "metadata": results[1].metadata
        }

        # Resolution: use highest scored source
        resolution_strategy = "highest_confidence_score"
        resolved = max(results, key=lambda r: r.combined_score)
        resolved_value = resolved.metadata

        return Contradiction(
            fact_type=fact_type,
            source1=source1,
            source2=source2,
            resolution_strategy=resolution_strategy,
            resolved_value=resolved_value,
            confidence_impact=-0.1  # Reduce confidence due to contradiction
        )

    def _convert_to_fact(self, result: MergedResult) -> Dict[str, Any]:
        """
        Convert a MergedResult to a fact dictionary.

        Args:
            result: RAG result

        Returns:
            Fact dictionary
        """
        return {
            "id": result.node_id,
            "uri": result.uri,
            "type": result.node_type,
            "title": result.title,
            "content": result.content,
            "score": result.combined_score,
            "methods": result.methods,
            "metadata": result.metadata or {}
        }

    def _calculate_reliability(self, result: MergedResult) -> float:
        """
        Calculate reliability score for a single result.

        Args:
            result: RAG result

        Returns:
            Reliability score (0.0 to 1.0)
        """
        # Base score from combined score
        base_score = result.combined_score

        # Boost for multiple methods agreeing
        method_boost = len(result.methods) * 0.1

        # Weight by source types
        source_weight = 0.0
        for method in result.methods:
            source_weight += self.reliability_weights.get(method, 0.3)
        source_weight = min(source_weight, 1.0)

        return min(base_score + method_boost, 1.0) * source_weight

    def _calculate_group_reliability(self, results: List[MergedResult]) -> float:
        """
        Calculate reliability score for a group of results.

        Args:
            results: Group of similar results

        Returns:
            Group reliability score (0.0 to 1.0)
        """
        # Average individual reliabilities
        individual_scores = [self._calculate_reliability(r) for r in results]
        avg_score = sum(individual_scores) / len(individual_scores)

        # Boost for agreement
        agreement_boost = min(len(results) * 0.05, 0.2)

        return min(avg_score + agreement_boost, 1.0)

    def _extract_complementary_info(self,
                                   results: List[MergedResult],
                                   unified_facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract complementary information not in main facts.

        Args:
            results: All RAG results
            unified_facts: Main unified facts

        Returns:
            List of complementary information
        """
        complementary = []
        used_ids = {fact["id"] for fact in unified_facts}

        for result in results:
            if result.node_id not in used_ids:
                # This is additional context
                if result.combined_score < 0.5:  # Lower threshold for context
                    info = {
                        "id": result.node_id,
                        "type": "context",
                        "content": result.title or result.uri,
                        "relevance": result.combined_score
                    }
                    complementary.append(info)

        return complementary[:10]  # Limit to top 10 complementary items