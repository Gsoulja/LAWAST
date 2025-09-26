"""
Result Merger component for Triple RAG
Handles score normalization, deduplication, and merging of results
"""

import logging
from typing import List, Dict, Any, Union, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

from .vector_search import VectorSearchResult
from .graph_search import GraphSearchResult
from .ast_search import ASTSearchResult

logger = logging.getLogger(__name__)


class SearchMethod(Enum):
    """Search method identifiers"""
    VECTOR = "vector"
    GRAPH = "graph"
    AST = "ast"


@dataclass
class MergedResult:
    """Unified result from multiple search methods"""
    node_id: str
    uri: str
    node_type: str
    combined_score: float
    method_scores: Dict[str, float]
    title: Optional[str] = None
    content: Optional[str] = None
    methods: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Ensure methods list is populated
        if not self.methods and self.method_scores:
            self.methods = list(self.method_scores.keys())


class ScoreNormalizer:
    """Handles score normalization across different search methods"""

    @staticmethod
    def min_max_normalize(scores: List[float]) -> List[float]:
        """
        Min-max normalization to [0, 1] range.

        Args:
            scores: List of raw scores

        Returns:
            Normalized scores
        """
        if not scores:
            return []

        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [0.5] * len(scores)

        return [(s - min_score) / (max_score - min_score) for s in scores]

    @staticmethod
    def z_score_normalize(scores: List[float]) -> List[float]:
        """
        Z-score normalization (standardization).

        Args:
            scores: List of raw scores

        Returns:
            Standardized scores
        """
        if not scores or len(scores) < 2:
            return scores

        scores_array = np.array(scores)
        mean = np.mean(scores_array)
        std = np.std(scores_array)

        if std == 0:
            return [0.5] * len(scores)

        # Normalize and clip to [0, 1]
        normalized = (scores_array - mean) / std
        # Convert to [0, 1] using sigmoid
        return (1 / (1 + np.exp(-normalized))).tolist()

    @staticmethod
    def rank_based_normalize(scores: List[float]) -> List[float]:
        """
        Rank-based normalization.

        Args:
            scores: List of raw scores

        Returns:
            Rank-normalized scores
        """
        if not scores:
            return []

        # Create (score, index) pairs and sort by score
        indexed_scores = [(score, i) for i, score in enumerate(scores)]
        indexed_scores.sort(reverse=True)

        # Assign normalized scores based on rank
        normalized = [0.0] * len(scores)
        for rank, (_, original_index) in enumerate(indexed_scores):
            normalized[original_index] = 1.0 - (rank / len(scores))

        return normalized


class ResultMerger:
    """
    Merges and deduplicates results from multiple search methods.
    """

    def __init__(self,
                 vector_weight: float = 0.4,
                 graph_weight: float = 0.3,
                 ast_weight: float = 0.3,
                 normalization_method: str = "min_max"):
        """
        Initialize result merger.

        Args:
            vector_weight: Weight for vector search scores
            graph_weight: Weight for graph search scores
            ast_weight: Weight for AST search scores
            normalization_method: Method for score normalization
        """
        # Ensure weights sum to 1.0
        total_weight = vector_weight + graph_weight + ast_weight
        self.weights = {
            SearchMethod.VECTOR.value: vector_weight / total_weight,
            SearchMethod.GRAPH.value: graph_weight / total_weight,
            SearchMethod.AST.value: ast_weight / total_weight
        }

        self.normalization_method = normalization_method
        self.normalizer = ScoreNormalizer()

        logger.info(f"Result merger initialized with weights: {self.weights}")

    def merge_results(self,
                     vector_results: Optional[List[VectorSearchResult]] = None,
                     graph_results: Optional[List[GraphSearchResult]] = None,
                     ast_results: Optional[List[ASTSearchResult]] = None,
                     top_k: int = 20) -> List[MergedResult]:
        """
        Merge results from multiple search methods.

        Args:
            vector_results: Results from vector search
            graph_results: Results from graph search
            ast_results: Results from AST search
            top_k: Number of top results to return

        Returns:
            List of merged and ranked results
        """
        # Collect all results by URI
        results_by_uri = {}

        # Process vector results
        if vector_results:
            normalized_scores = self._normalize_scores(
                [r.score for r in vector_results]
            )
            for result, norm_score in zip(vector_results, normalized_scores):
                self._add_result(
                    results_by_uri,
                    result,
                    SearchMethod.VECTOR,
                    norm_score
                )

        # Process graph results
        if graph_results:
            normalized_scores = self._normalize_scores(
                [r.score for r in graph_results]
            )
            for result, norm_score in zip(graph_results, normalized_scores):
                self._add_result(
                    results_by_uri,
                    result,
                    SearchMethod.GRAPH,
                    norm_score
                )

        # Process AST results
        if ast_results:
            normalized_scores = self._normalize_scores(
                [r.score for r in ast_results]
            )
            for result, norm_score in zip(ast_results, normalized_scores):
                self._add_result(
                    results_by_uri,
                    result,
                    SearchMethod.AST,
                    norm_score
                )

        # Calculate combined scores
        merged_results = []
        for uri, result_data in results_by_uri.items():
            combined_score = self._calculate_combined_score(
                result_data["method_scores"]
            )

            merged_result = MergedResult(
                node_id=result_data["node_id"],
                uri=uri,
                node_type=result_data["node_type"],
                combined_score=combined_score,
                method_scores=result_data["method_scores"],
                title=result_data.get("title"),
                content=result_data.get("content"),
                methods=list(result_data["method_scores"].keys()),
                metadata=result_data.get("metadata", {})
            )

            merged_results.append(merged_result)

        # Sort by combined score and return top k
        merged_results.sort(key=lambda x: x.combined_score, reverse=True)

        # Log statistics
        self._log_merge_statistics(merged_results[:top_k])

        return merged_results[:top_k]

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """
        Normalize scores using the configured method.

        Args:
            scores: Raw scores to normalize

        Returns:
            Normalized scores
        """
        if not scores:
            return []

        if self.normalization_method == "min_max":
            return self.normalizer.min_max_normalize(scores)
        elif self.normalization_method == "z_score":
            return self.normalizer.z_score_normalize(scores)
        elif self.normalization_method == "rank":
            return self.normalizer.rank_based_normalize(scores)
        else:
            # Default to min-max
            return self.normalizer.min_max_normalize(scores)

    def _add_result(self,
                   results_dict: Dict[str, Any],
                   result: Union[VectorSearchResult, GraphSearchResult, ASTSearchResult],
                   method: SearchMethod,
                   normalized_score: float):
        """
        Add a result to the results dictionary.

        Args:
            results_dict: Dictionary to store results by URI
            result: Search result object
            method: Search method that produced the result
            normalized_score: Normalized score for the result
        """
        uri = result.uri

        if uri not in results_dict:
            results_dict[uri] = {
                "node_id": result.node_id,
                "node_type": result.node_type,
                "title": result.title,
                "content": result.content,
                "method_scores": {},
                "metadata": {}
            }

        # Update scores
        results_dict[uri]["method_scores"][method.value] = normalized_score

        # Merge metadata
        if hasattr(result, 'metadata') and result.metadata:
            results_dict[uri]["metadata"].update({
                f"{method.value}_{k}": v
                for k, v in result.metadata.items()
            })

        # Keep best title/content
        if result.title and not results_dict[uri]["title"]:
            results_dict[uri]["title"] = result.title
        if result.content and not results_dict[uri]["content"]:
            results_dict[uri]["content"] = result.content

    def _calculate_combined_score(self, method_scores: Dict[str, float]) -> float:
        """
        Calculate combined score from individual method scores.

        Args:
            method_scores: Dictionary of method names to scores

        Returns:
            Combined weighted score
        """
        combined = 0.0

        for method, score in method_scores.items():
            weight = self.weights.get(method, 0.0)
            combined += weight * score

        # Boost for results found by multiple methods
        method_count = len(method_scores)
        if method_count > 1:
            # Add bonus for multi-method matches
            bonus = 0.1 * (method_count - 1)
            combined = min(1.0, combined + bonus)

        return combined

    def _log_merge_statistics(self, results: List[MergedResult]):
        """
        Log statistics about the merge operation.

        Args:
            results: Merged results
        """
        if not results:
            logger.info("No results after merging")
            return

        # Count methods
        method_counts = {
            SearchMethod.VECTOR.value: 0,
            SearchMethod.GRAPH.value: 0,
            SearchMethod.AST.value: 0
        }

        multi_method_count = 0

        for result in results:
            for method in result.methods:
                method_counts[method] += 1

            if len(result.methods) > 1:
                multi_method_count += 1

        logger.info(
            f"Merged {len(results)} results: "
            f"Vector={method_counts[SearchMethod.VECTOR.value]}, "
            f"Graph={method_counts[SearchMethod.GRAPH.value]}, "
            f"AST={method_counts[SearchMethod.AST.value]}, "
            f"Multi-method={multi_method_count}"
        )

    def adjust_weights(self,
                      vector_weight: Optional[float] = None,
                      graph_weight: Optional[float] = None,
                      ast_weight: Optional[float] = None):
        """
        Dynamically adjust search method weights.

        Args:
            vector_weight: New weight for vector search
            graph_weight: New weight for graph search
            ast_weight: New weight for AST search
        """
        if vector_weight is not None:
            self.weights[SearchMethod.VECTOR.value] = vector_weight
        if graph_weight is not None:
            self.weights[SearchMethod.GRAPH.value] = graph_weight
        if ast_weight is not None:
            self.weights[SearchMethod.AST.value] = ast_weight

        # Renormalize weights
        total = sum(self.weights.values())
        if total > 0:
            for key in self.weights:
                self.weights[key] /= total

        logger.info(f"Adjusted weights: {self.weights}")

    def get_diversity_score(self, results: List[MergedResult]) -> float:
        """
        Calculate diversity score for the result set.

        Args:
            results: List of merged results

        Returns:
            Diversity score (0-1, higher is more diverse)
        """
        if not results:
            return 0.0

        # Check method diversity
        method_sets = [set(r.methods) for r in results]
        unique_combinations = len(set(tuple(sorted(s)) for s in method_sets))
        method_diversity = unique_combinations / len(results)

        # Check node type diversity
        node_types = [r.node_type for r in results]
        unique_types = len(set(node_types))
        type_diversity = unique_types / min(4, len(results))  # Max 4 types expected

        return (method_diversity + type_diversity) / 2