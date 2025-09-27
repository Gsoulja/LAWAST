#!/usr/bin/env python3
"""
Enhanced Triple RAG Orchestrator with Legal Logic AST
Coordinates Vector, Graph, and Legal Logic AST search methods
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..data_access.neo4j_connection import Neo4jConnectionManager
from .vector_search import VectorSearch, VectorSearchResult
from .graph_search import GraphSearch, GraphSearchResult
from .legal_logic_ast_search import LegalLogicASTSearch, LegalLogicSearchResult
from .hybrid_search import HybridSearch, HybridSearchResult
from .result_merger import ResultMerger, MergedResult

logger = logging.getLogger(__name__)


@dataclass
class EnhancedTripleRAGConfig:
    """Configuration for Enhanced Triple RAG orchestrator"""
    # Search method weights
    vector_weight: float = 0.25
    graph_weight: float = 0.25
    legal_logic_weight: float = 0.35  # Higher weight for legal logic
    hybrid_weight: float = 0.15

    # Search parameters
    vector_top_k: int = 15
    graph_max_depth: int = 3
    legal_logic_max_results: int = 20  # More results from logic search
    hybrid_top_k: int = 10
    final_top_k: int = 20

    # Hybrid search parameters
    hybrid_vector_weight: float = 0.6
    hybrid_bm25_weight: float = 0.4
    enable_hybrid: bool = True

    # Legal logic specific
    enable_legal_logic: bool = True
    legal_language: str = "de"  # Default to German
    enable_condition_evaluation: bool = True

    # Score thresholds
    min_confidence: float = 0.6
    legal_logic_boost: float = 1.2  # Boost for legal logic matches

    # Performance settings
    use_parallel: bool = True
    cache_results: bool = True
    cache_ttl: int = 300  # seconds


@dataclass
class EnhancedSearchMetrics:
    """Metrics for enhanced search performance"""
    total_time: float = 0.0
    vector_time: float = 0.0
    graph_time: float = 0.0
    legal_logic_time: float = 0.0
    hybrid_time: float = 0.0
    merge_time: float = 0.0

    vector_count: int = 0
    graph_count: int = 0
    legal_logic_count: int = 0
    hybrid_count: int = 0
    merged_count: int = 0

    detected_intents: List[str] = field(default_factory=list)
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    cache_hit: bool = False


class EnhancedTripleRAG:
    """
    Enhanced Triple RAG with Legal Logic AST.

    Combines:
    1. Vector similarity search
    2. Graph relationship traversal
    3. Legal Logic AST (semantic legal understanding)
    4. Hybrid vector+BM25 search
    """

    def __init__(self,
                 config: Optional[EnhancedTripleRAGConfig] = None,
                 connection: Optional[Neo4jConnectionManager] = None):
        """
        Initialize Enhanced Triple RAG orchestrator.

        Args:
            config: Configuration object
            connection: Neo4j connection manager
        """
        self.config = config or EnhancedTripleRAGConfig()
        self.connection = connection or Neo4jConnectionManager()

        # Initialize search components
        logger.info("Initializing Enhanced Triple RAG components...")

        # Traditional searches
        self.vector_search = VectorSearch(
            connection=self.connection,
            device="cpu"  # Force CPU to avoid CUDA memory issues
        )
        self.graph_search = GraphSearch(connection=self.connection)

        # Enhanced Legal Logic AST search
        if self.config.enable_legal_logic:
            self.legal_logic_search = LegalLogicASTSearch(
                connection=self.connection,
                language=self.config.legal_language
            )
        else:
            self.legal_logic_search = None

        # Hybrid search
        if self.config.enable_hybrid:
            self.hybrid_search = HybridSearch(
                connection=self.connection,
                vector_weight=self.config.hybrid_vector_weight,
                bm25_weight=self.config.hybrid_bm25_weight
            )
        else:
            self.hybrid_search = None

        # Initialize result merger with legal logic weight
        self.merger = ResultMerger(
            vector_weight=self.config.vector_weight,
            graph_weight=self.config.graph_weight,
            ast_weight=self.config.legal_logic_weight,  # Use legal logic weight
            hybrid_weight=self.config.hybrid_weight if self.config.enable_hybrid else 0
        )

        # Cache for results if enabled
        self._cache = {} if self.config.cache_results else None
        self._cache_timestamps = {}

        logger.info("Enhanced Triple RAG orchestrator initialized")

    def search(self,
               query: str,
               context: Optional[Dict[str, Any]] = None,
               config_override: Optional[Dict[str, Any]] = None) -> Tuple[List[MergedResult], EnhancedSearchMetrics]:
        """
        Perform Enhanced Triple RAG search with legal logic.

        Args:
            query: Search query text
            context: Optional context for condition evaluation
            config_override: Optional config overrides for this search

        Returns:
            Tuple of (merged results, search metrics)
        """
        start_time = time.time()
        metrics = EnhancedSearchMetrics()

        # Check cache if enabled
        if self._cache is not None:
            cached_result = self._check_cache(query)
            if cached_result:
                metrics.cache_hit = True
                metrics.total_time = time.time() - start_time
                return cached_result, metrics

        # Apply config overrides if provided
        config = self._apply_config_override(config_override)

        # Execute searches (parallel or sequential)
        if config.use_parallel:
            results = self._parallel_search(query, context, config, metrics)
        else:
            results = self._sequential_search(query, context, config, metrics)

        vector_results, graph_results, legal_logic_results, hybrid_results = results

        # Convert legal logic results to standard format for merging
        ast_results = self._convert_legal_logic_results(legal_logic_results)

        # Merge results
        merge_start = time.time()
        merged_results = self.merger.merge_results(
            vector_results=vector_results,
            graph_results=graph_results,
            ast_results=ast_results,  # Use converted legal logic results
            hybrid_results=hybrid_results,
            top_k=config.final_top_k
        )
        metrics.merge_time = time.time() - merge_start

        # Apply legal logic boost to results that have legal rules
        merged_results = self._apply_legal_logic_boost(merged_results, legal_logic_results, config)

        # Update metrics
        metrics.vector_count = len(vector_results) if vector_results else 0
        metrics.graph_count = len(graph_results) if graph_results else 0
        metrics.legal_logic_count = len(legal_logic_results) if legal_logic_results else 0
        metrics.hybrid_count = len(hybrid_results) if hybrid_results else 0
        metrics.merged_count = len(merged_results)
        metrics.total_time = time.time() - start_time

        # Add intent and entity info to metrics
        if self.legal_logic_search and legal_logic_results:
            intents = self.legal_logic_search.detect_query_intent(query)
            metrics.detected_intents = [i.value for i in intents]
            metrics.extracted_entities = self.legal_logic_search._extract_query_entities(query)

        # Cache results if enabled
        if self._cache is not None:
            self._cache_result(query, merged_results)

        # Log performance
        self._log_performance(query, metrics)

        return merged_results, metrics

    def _parallel_search(self,
                        query: str,
                        context: Optional[Dict[str, Any]],
                        config: EnhancedTripleRAGConfig,
                        metrics: EnhancedSearchMetrics) -> Tuple:
        """
        Execute searches in parallel.

        Args:
            query: Search query
            context: Optional context
            config: Configuration
            metrics: Metrics object

        Returns:
            Tuple of search results
        """
        vector_results = []
        graph_results = []
        legal_logic_results = []
        hybrid_results = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}

            # Submit vector search
            futures[executor.submit(
                self._execute_vector_search, query, config
            )] = "vector"

            # Submit graph search
            futures[executor.submit(
                self._execute_graph_search, query, config
            )] = "graph"

            # Submit legal logic search
            if config.enable_legal_logic and self.legal_logic_search:
                futures[executor.submit(
                    self._execute_legal_logic_search, query, context, config
                )] = "legal_logic"

            # Submit hybrid search
            if config.enable_hybrid and self.hybrid_search:
                futures[executor.submit(
                    self._execute_hybrid_search, query, config
                )] = "hybrid"

            # Collect results
            for future in as_completed(futures):
                search_type = futures[future]
                try:
                    result, elapsed = future.result()

                    if search_type == "vector":
                        vector_results = result
                        metrics.vector_time = elapsed
                    elif search_type == "graph":
                        graph_results = result
                        metrics.graph_time = elapsed
                    elif search_type == "legal_logic":
                        legal_logic_results = result
                        metrics.legal_logic_time = elapsed
                    elif search_type == "hybrid":
                        hybrid_results = result
                        metrics.hybrid_time = elapsed

                except Exception as e:
                    logger.error(f"Error in {search_type} search: {e}")

        return vector_results, graph_results, legal_logic_results, hybrid_results

    def _sequential_search(self,
                          query: str,
                          context: Optional[Dict[str, Any]],
                          config: EnhancedTripleRAGConfig,
                          metrics: EnhancedSearchMetrics) -> Tuple:
        """
        Execute searches sequentially.

        Args:
            query: Search query
            context: Optional context
            config: Configuration
            metrics: Metrics object

        Returns:
            Tuple of search results
        """
        # Vector search
        vector_results, metrics.vector_time = self._execute_vector_search(query, config)

        # Graph search
        graph_results, metrics.graph_time = self._execute_graph_search(query, config)

        # Legal logic search
        legal_logic_results = []
        if config.enable_legal_logic and self.legal_logic_search:
            legal_logic_results, metrics.legal_logic_time = self._execute_legal_logic_search(
                query, context, config
            )

        # Hybrid search
        hybrid_results = []
        if config.enable_hybrid and self.hybrid_search:
            hybrid_results, metrics.hybrid_time = self._execute_hybrid_search(query, config)

        return vector_results, graph_results, legal_logic_results, hybrid_results

    def _execute_vector_search(self, query: str, config: EnhancedTripleRAGConfig) -> Tuple[List, float]:
        """Execute vector search."""
        start = time.time()
        try:
            results = self.vector_search.search(
                query=query,
                top_k=config.vector_top_k,
                node_types=["Law", "Article", "Paragraph"]
            )
            elapsed = time.time() - start
            return results, elapsed
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return [], time.time() - start

    def _execute_graph_search(self, query: str, config: EnhancedTripleRAGConfig) -> Tuple[List, float]:
        """Execute graph search."""
        start = time.time()
        try:
            results = self.graph_search.search(
                query=query,
                max_depth=config.graph_max_depth
            )
            elapsed = time.time() - start
            return results, elapsed
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return [], time.time() - start

    def _execute_legal_logic_search(self,
                                   query: str,
                                   context: Optional[Dict[str, Any]],
                                   config: EnhancedTripleRAGConfig) -> Tuple[List, float]:
        """Execute legal logic AST search."""
        start = time.time()
        try:
            results = self.legal_logic_search.search_by_legal_logic(
                query=query,
                limit=config.legal_logic_max_results
            )

            # If context provided, evaluate conditions
            if context and config.enable_condition_evaluation:
                for result in results:
                    if result.legal_rule:
                        evaluation = self.legal_logic_search.evaluate_conditions(
                            result.legal_rule, context
                        )
                        # Boost score if conditions are met
                        if evaluation["applicable"]:
                            result.score *= 1.5
                            result.reasoning += f" | Conditions met: {evaluation['reasoning']}"

            elapsed = time.time() - start
            return results, elapsed
        except Exception as e:
            logger.error(f"Legal logic search failed: {e}")
            return [], time.time() - start

    def _execute_hybrid_search(self, query: str, config: EnhancedTripleRAGConfig) -> Tuple[List, float]:
        """Execute hybrid search."""
        start = time.time()
        try:
            results = self.hybrid_search.search(
                query=query,
                top_k=config.hybrid_top_k
            )
            elapsed = time.time() - start
            return results, elapsed
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return [], time.time() - start

    def _convert_legal_logic_results(self, legal_logic_results: List[LegalLogicSearchResult]) -> List:
        """
        Convert legal logic results to standard AST result format for merging.

        Args:
            legal_logic_results: Legal logic search results

        Returns:
            List of converted results
        """
        from .ast_search import ASTSearchResult

        converted = []
        for ll_result in legal_logic_results:
            # Create AST-compatible result
            ast_result = ASTSearchResult(
                node_id=ll_result.node_id,
                uri=ll_result.uri,
                node_type=ll_result.node_type,
                ast_path="",  # Not used in legal logic
                level=6 if ll_result.node_type == "Article" else 7,  # Article or Paragraph level
                score=ll_result.score,
                title=ll_result.title,
                content=ll_result.content,
                metadata={
                    "sr_number": ll_result.sr_number,
                    "article_number": ll_result.article_number,
                    "legal_rule": ll_result.legal_rule,
                    "reasoning": ll_result.reasoning,
                    "confidence": ll_result.confidence,
                    "matched_conditions": ll_result.matched_conditions,
                    "matched_consequences": ll_result.matched_consequences,
                    "applicable_operators": [op.value for op in ll_result.applicable_operators]
                }
            )
            converted.append(ast_result)

        return converted

    def _apply_legal_logic_boost(self,
                                 merged_results: List[MergedResult],
                                 legal_logic_results: List[LegalLogicSearchResult],
                                 config: EnhancedTripleRAGConfig) -> List[MergedResult]:
        """
        Apply boost to results that have legal logic.

        Args:
            merged_results: Merged results
            legal_logic_results: Legal logic results
            config: Configuration

        Returns:
            Updated merged results
        """
        # Create lookup for legal logic results
        logic_lookup = {r.uri: r for r in legal_logic_results}

        for result in merged_results:
            if result.uri in logic_lookup:
                logic_result = logic_lookup[result.uri]

                # Apply boost based on legal logic quality
                if logic_result.legal_rule:
                    # Boost for having legal rules
                    result.combined_score *= config.legal_logic_boost

                    # Add legal logic metadata
                    if not result.metadata:
                        result.metadata = {}

                    result.metadata.update({
                        "has_legal_logic": True,
                        "legal_confidence": logic_result.confidence,
                        "legal_reasoning": logic_result.reasoning,
                        "applicable_operators": [op.value for op in logic_result.applicable_operators]
                    })

        # Re-sort by score
        merged_results.sort(key=lambda x: x.combined_score, reverse=True)

        return merged_results

    def _check_cache(self, query: str) -> Optional[List[MergedResult]]:
        """Check cache for results."""
        if query in self._cache:
            timestamp = self._cache_timestamps.get(query, 0)
            if time.time() - timestamp < self.config.cache_ttl:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return self._cache[query]
            else:
                # Expired
                del self._cache[query]
                del self._cache_timestamps[query]
        return None

    def _cache_result(self, query: str, results: List[MergedResult]):
        """Cache search results."""
        self._cache[query] = results
        self._cache_timestamps[query] = time.time()

        # Limit cache size
        if len(self._cache) > 100:
            # Remove oldest entries
            oldest_query = min(self._cache_timestamps, key=self._cache_timestamps.get)
            del self._cache[oldest_query]
            del self._cache_timestamps[oldest_query]

    def _apply_config_override(self, override: Optional[Dict[str, Any]]) -> EnhancedTripleRAGConfig:
        """Apply configuration overrides."""
        if not override:
            return self.config

        # Create a copy with overrides
        config_dict = {
            "vector_weight": self.config.vector_weight,
            "graph_weight": self.config.graph_weight,
            "legal_logic_weight": self.config.legal_logic_weight,
            "hybrid_weight": self.config.hybrid_weight,
            "vector_top_k": self.config.vector_top_k,
            "graph_max_depth": self.config.graph_max_depth,
            "legal_logic_max_results": self.config.legal_logic_max_results,
            "hybrid_top_k": self.config.hybrid_top_k,
            "final_top_k": self.config.final_top_k,
            "enable_legal_logic": self.config.enable_legal_logic,
            "legal_language": self.config.legal_language,
            "enable_condition_evaluation": self.config.enable_condition_evaluation,
            "min_confidence": self.config.min_confidence,
            "legal_logic_boost": self.config.legal_logic_boost,
            "use_parallel": self.config.use_parallel,
            "enable_hybrid": self.config.enable_hybrid
        }

        # Apply overrides
        config_dict.update(override)

        return EnhancedTripleRAGConfig(**config_dict)

    def _log_performance(self, query: str, metrics: EnhancedSearchMetrics):
        """Log search performance metrics."""
        logger.info(
            f"Enhanced search completed for '{query[:50]}...' | "
            f"Total: {metrics.total_time:.2f}s | "
            f"Vector: {metrics.vector_count} in {metrics.vector_time:.2f}s | "
            f"Graph: {metrics.graph_count} in {metrics.graph_time:.2f}s | "
            f"Legal Logic: {metrics.legal_logic_count} in {metrics.legal_logic_time:.2f}s | "
            f"Hybrid: {metrics.hybrid_count} in {metrics.hybrid_time:.2f}s | "
            f"Merged: {metrics.merged_count} | "
            f"Intents: {metrics.detected_intents} | "
            f"Cache: {'HIT' if metrics.cache_hit else 'MISS'}"
        )