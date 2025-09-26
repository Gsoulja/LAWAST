"""
Strategy Planner - Decides which RAG methods to use based on query analysis
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from .query_analyzer import QueryAnalysis, QueryIntent, QueryComplexity

logger = logging.getLogger(__name__)


class RAGStrategy(Enum):
    """Available RAG strategies"""
    VECTOR = "vector"
    GRAPH = "graph"
    AST = "ast"
    HYBRID = "hybrid"
    VECTOR_GRAPH = "vector_graph"
    VECTOR_AST = "vector_ast"
    GRAPH_AST = "graph_ast"


@dataclass
class StrategyDecision:
    """Strategy decision with reasoning"""
    primary_strategy: RAGStrategy
    confidence: float
    reasoning: str
    rag_methods: List[str] = field(default_factory=list)
    fallback_strategy: Optional[RAGStrategy] = None
    config_overrides: Dict[str, Any] = field(default_factory=dict)


class StrategyPlanner:
    """Plans which RAG retrieval strategies to use based on query analysis"""

    def __init__(self):
        """Initialize the strategy planner with decision rules"""
        # Intent to strategy mapping
        self.intent_strategy_map = {
            QueryIntent.FACTUAL: [RAGStrategy.VECTOR, RAGStrategy.AST],
            QueryIntent.COMPARATIVE: [RAGStrategy.GRAPH, RAGStrategy.VECTOR_GRAPH],
            QueryIntent.PROCEDURAL: [RAGStrategy.VECTOR, RAGStrategy.HYBRID],
            QueryIntent.EXPLORATORY: [RAGStrategy.HYBRID, RAGStrategy.VECTOR_GRAPH],
            QueryIntent.DEFINITIONAL: [RAGStrategy.VECTOR, RAGStrategy.AST],
            QueryIntent.TEMPORAL: [RAGStrategy.GRAPH, RAGStrategy.HYBRID],
            QueryIntent.JURISDICTIONAL: [RAGStrategy.AST, RAGStrategy.VECTOR_AST],
            QueryIntent.RELATIONSHIP: [RAGStrategy.GRAPH, RAGStrategy.GRAPH_AST],
        }

        # Complexity modifiers
        self.complexity_modifiers = {
            QueryComplexity.SIMPLE: 1.0,
            QueryComplexity.MEDIUM: 0.9,
            QueryComplexity.COMPLEX: 0.8
        }

        # Default confidence thresholds
        self.min_confidence_threshold = 0.5
        self.high_confidence_threshold = 0.8

    def plan(self, analysis: QueryAnalysis) -> StrategyDecision:
        """
        Plan the retrieval strategy based on query analysis.

        Args:
            analysis: QueryAnalysis object from query analyzer

        Returns:
            StrategyDecision with selected strategy and configuration
        """
        # Determine base strategy from intent
        base_strategies = self.intent_strategy_map.get(
            analysis.intent,
            [RAGStrategy.HYBRID]
        )
        primary_strategy = base_strategies[0]
        fallback_strategy = base_strategies[1] if len(base_strategies) > 1 else None

        # Adjust based on entity presence
        primary_strategy, reasoning = self._adjust_for_entities(
            primary_strategy, analysis
        )

        # Calculate confidence
        confidence = self._calculate_confidence(analysis, primary_strategy)

        # Determine which RAG methods to use
        rag_methods = self._get_rag_methods(primary_strategy)

        # Configure search parameters based on analysis
        config_overrides = self._get_config_overrides(analysis, primary_strategy)

        decision = StrategyDecision(
            primary_strategy=primary_strategy,
            confidence=confidence,
            reasoning=reasoning,
            rag_methods=rag_methods,
            fallback_strategy=fallback_strategy,
            config_overrides=config_overrides
        )

        logger.info(f"Strategy decision: {primary_strategy.value} "
                   f"(confidence: {confidence:.2f}) - {reasoning}")

        return decision

    def _adjust_for_entities(self,
                            strategy: RAGStrategy,
                            analysis: QueryAnalysis) -> tuple[RAGStrategy, str]:
        """
        Adjust strategy based on detected entities.

        Args:
            strategy: Initial strategy
            analysis: Query analysis

        Returns:
            Tuple of (adjusted strategy, reasoning)
        """
        reasoning_parts = []

        # Strong preference for AST if article numbers are present
        if analysis.has_article_reference:
            if strategy not in [RAGStrategy.AST, RAGStrategy.VECTOR_AST, RAGStrategy.GRAPH_AST]:
                strategy = RAGStrategy.AST
                reasoning_parts.append("Using AST search for specific article references")

        # Use graph search for relationship queries or when multiple laws are mentioned
        elif analysis.has_law_reference and len(analysis.entities.get('law', [])) > 1:
            if strategy not in [RAGStrategy.GRAPH, RAGStrategy.VECTOR_GRAPH, RAGStrategy.GRAPH_AST]:
                strategy = RAGStrategy.GRAPH
                reasoning_parts.append("Using graph search for multiple law references")

        # Use vector search for conceptual queries without specific references
        elif not analysis.has_article_reference and not analysis.has_law_reference:
            if analysis.intent in [QueryIntent.DEFINITIONAL, QueryIntent.FACTUAL]:
                if strategy not in [RAGStrategy.VECTOR, RAGStrategy.VECTOR_GRAPH, RAGStrategy.VECTOR_AST]:
                    strategy = RAGStrategy.VECTOR
                    reasoning_parts.append("Using vector search for conceptual query")

        # High ambiguity suggests hybrid approach
        if analysis.ambiguity_score > 0.6:
            if strategy not in [RAGStrategy.HYBRID]:
                strategy = RAGStrategy.HYBRID
                reasoning_parts.append("Using hybrid search due to high ambiguity")

        # Complex queries benefit from multiple methods
        if analysis.complexity == QueryComplexity.COMPLEX:
            if strategy in [RAGStrategy.VECTOR, RAGStrategy.GRAPH, RAGStrategy.AST]:
                strategy = RAGStrategy.HYBRID
                reasoning_parts.append("Using hybrid search for complex query")

        # Build reasoning string
        if reasoning_parts:
            reasoning = ". ".join(reasoning_parts)
        else:
            reasoning = f"Default strategy for {analysis.intent.value} intent"

        return strategy, reasoning

    def _calculate_confidence(self,
                             analysis: QueryAnalysis,
                             strategy: RAGStrategy) -> float:
        """
        Calculate confidence in the selected strategy.

        Args:
            analysis: Query analysis
            strategy: Selected strategy

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Start with analysis confidence
        base_confidence = analysis.confidence

        # Apply complexity modifier
        complexity_modifier = self.complexity_modifiers[analysis.complexity]
        confidence = base_confidence * complexity_modifier

        # Boost confidence for clear entity matches
        if analysis.has_article_reference and strategy in [RAGStrategy.AST, RAGStrategy.VECTOR_AST]:
            confidence = min(1.0, confidence * 1.2)
        elif analysis.has_law_reference and strategy in [RAGStrategy.GRAPH, RAGStrategy.VECTOR_GRAPH]:
            confidence = min(1.0, confidence * 1.1)

        # Reduce confidence for high ambiguity
        if analysis.ambiguity_score > 0.5:
            confidence *= (1.0 - analysis.ambiguity_score * 0.3)

        # Reduce confidence if missing context
        if analysis.missing_context:
            confidence *= max(0.5, 1.0 - len(analysis.missing_context) * 0.1)

        # Ensure within bounds
        confidence = max(0.0, min(1.0, confidence))

        return confidence

    def _get_rag_methods(self, strategy: RAGStrategy) -> List[str]:
        """
        Get the list of RAG methods to use for the strategy.

        Args:
            strategy: Selected strategy

        Returns:
            List of RAG method names
        """
        method_map = {
            RAGStrategy.VECTOR: ["vector"],
            RAGStrategy.GRAPH: ["graph"],
            RAGStrategy.AST: ["ast"],
            RAGStrategy.HYBRID: ["vector", "graph", "ast"],
            RAGStrategy.VECTOR_GRAPH: ["vector", "graph"],
            RAGStrategy.VECTOR_AST: ["vector", "ast"],
            RAGStrategy.GRAPH_AST: ["graph", "ast"],
        }
        return method_map.get(strategy, ["vector", "graph", "ast"])

    def _get_config_overrides(self,
                             analysis: QueryAnalysis,
                             strategy: RAGStrategy) -> Dict[str, Any]:
        """
        Get configuration overrides for the RAG orchestrator.

        Args:
            analysis: Query analysis
            strategy: Selected strategy

        Returns:
            Dictionary of config overrides
        """
        overrides = {}

        # Adjust weights based on strategy
        if strategy == RAGStrategy.VECTOR:
            overrides['vector_weight'] = 0.7
            overrides['graph_weight'] = 0.15
            overrides['ast_weight'] = 0.15
        elif strategy == RAGStrategy.GRAPH:
            overrides['vector_weight'] = 0.15
            overrides['graph_weight'] = 0.7
            overrides['ast_weight'] = 0.15
        elif strategy == RAGStrategy.AST:
            overrides['vector_weight'] = 0.15
            overrides['graph_weight'] = 0.15
            overrides['ast_weight'] = 0.7
        elif strategy == RAGStrategy.VECTOR_GRAPH:
            overrides['vector_weight'] = 0.45
            overrides['graph_weight'] = 0.45
            overrides['ast_weight'] = 0.1
        elif strategy == RAGStrategy.VECTOR_AST:
            overrides['vector_weight'] = 0.45
            overrides['graph_weight'] = 0.1
            overrides['ast_weight'] = 0.45
        elif strategy == RAGStrategy.GRAPH_AST:
            overrides['vector_weight'] = 0.1
            overrides['graph_weight'] = 0.45
            overrides['ast_weight'] = 0.45
        # HYBRID uses default balanced weights

        # Adjust top_k based on complexity
        if analysis.complexity == QueryComplexity.SIMPLE:
            overrides['vector_top_k'] = 10
            overrides['final_top_k'] = 10
        elif analysis.complexity == QueryComplexity.COMPLEX:
            overrides['vector_top_k'] = 20
            overrides['final_top_k'] = 25

        # Increase graph depth for relationship queries
        if analysis.intent == QueryIntent.RELATIONSHIP:
            overrides['graph_max_depth'] = 4

        # Increase AST results for article-specific queries
        if analysis.has_article_reference:
            overrides['ast_max_results'] = 20

        return overrides

    def should_use_fallback(self, confidence: float) -> bool:
        """
        Determine if fallback strategy should be used.

        Args:
            confidence: Confidence in primary strategy

        Returns:
            True if fallback should be used
        """
        return confidence < self.min_confidence_threshold

    def needs_clarification(self, analysis: QueryAnalysis, confidence: float) -> bool:
        """
        Determine if clarification is needed before proceeding.

        Args:
            analysis: Query analysis
            confidence: Strategy confidence

        Returns:
            True if clarification should be requested
        """
        # Need clarification if:
        # 1. Low confidence and high ambiguity
        if confidence < 0.6 and analysis.ambiguity_score > 0.5:
            return True

        # 2. Missing critical context
        if len(analysis.missing_context) >= 2:
            return True

        # 3. Very low confidence
        if confidence < self.min_confidence_threshold:
            return True

        return False