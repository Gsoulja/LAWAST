"""
Triple RAG Orchestrator
Main component that coordinates Vector, Graph, and AST search methods
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from ..data_access.neo4j_connection import Neo4jConnectionManager
from .vector_search import VectorSearch, VectorSearchResult
from .graph_search import GraphSearch, GraphSearchResult
from .ast_search import ASTSearch, ASTSearchResult
from .hybrid_search import HybridSearch, HybridSearchResult
from .result_merger import ResultMerger, MergedResult

logger = logging.getLogger(__name__)


@dataclass
class TripleRAGConfig:
    """Configuration for Triple RAG orchestrator"""
    # Search method weights
    vector_weight: float = 0.3
    graph_weight: float = 0.2
    ast_weight: float = 0.2
    hybrid_weight: float = 0.3

    # Search parameters
    vector_top_k: int = 15
    graph_max_depth: int = 3
    ast_max_results: int = 15
    hybrid_top_k: int = 15
    final_top_k: int = 20

    # Hybrid search parameters
    hybrid_vector_weight: float = 0.6
    hybrid_bm25_weight: float = 0.4
    enable_hybrid: bool = True

    # Score thresholds
    vector_min_score: float = 0.5
    graph_min_results: int = 5
    ast_min_results: int = 5

    # Performance settings
    use_parallel: bool = True
    cache_results: bool = True
    cache_ttl: int = 300  # seconds

    # Normalization method
    normalization_method: str = "min_max"

    # Node types to search
    search_node_types: List[str] = field(default_factory=lambda: ["Law", "Article", "Paragraph"])


@dataclass
class SearchMetrics:
    """Metrics for search performance"""
    total_time: float = 0.0
    vector_time: float = 0.0
    graph_time: float = 0.0
    ast_time: float = 0.0
    hybrid_time: float = 0.0
    merge_time: float = 0.0
    vector_count: int = 0
    graph_count: int = 0
    ast_count: int = 0
    hybrid_count: int = 0
    merged_count: int = 0
    cache_hit: bool = False


class TripleRAG:
    """
    Orchestrates Quad RAG search combining:
    1. Vector similarity search
    2. Graph relationship traversal
    3. AST structural search
    4. Hybrid vector+BM25 search (for better keyword matching)
    """

    def __init__(self,
                 config: Optional[TripleRAGConfig] = None,
                 connection: Optional[Neo4jConnectionManager] = None):
        """
        Initialize Triple RAG orchestrator.

        Args:
            config: Configuration object
            connection: Neo4j connection manager
        """
        self.config = config or TripleRAGConfig()
        self.connection = connection or Neo4jConnectionManager()

        # Initialize search components (use CPU to avoid memory issues)
        logger.info("Initializing Triple RAG components...")
        self.vector_search = VectorSearch(
            connection=self.connection,
            device="cpu"  # Force CPU to avoid CUDA memory issues
        )
        self.graph_search = GraphSearch(connection=self.connection)
        self.ast_search = ASTSearch(connection=self.connection)

        # Initialize hybrid search if enabled
        if self.config.enable_hybrid:
            self.hybrid_search = HybridSearch(
                connection=self.connection,
                vector_weight=self.config.hybrid_vector_weight,
                bm25_weight=self.config.hybrid_bm25_weight
            )
        else:
            self.hybrid_search = None

        # Initialize result merger
        self.merger = ResultMerger(
            vector_weight=self.config.vector_weight,
            graph_weight=self.config.graph_weight,
            ast_weight=self.config.ast_weight,
            hybrid_weight=self.config.hybrid_weight if self.config.enable_hybrid else 0,
            normalization_method=self.config.normalization_method
        )

        # Cache for results if enabled
        self._cache = {} if self.config.cache_results else None
        self._cache_timestamps = {}

        logger.info("Triple RAG orchestrator initialized")

    def search(self,
               query: str,
               config_override: Optional[Dict[str, Any]] = None) -> Tuple[List[MergedResult], SearchMetrics]:
        """
        Perform Triple RAG search.

        Args:
            query: Search query text
            config_override: Optional config overrides for this search

        Returns:
            Tuple of (merged results, search metrics)
        """
        start_time = time.time()
        metrics = SearchMetrics()

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
            vector_results, graph_results, ast_results, hybrid_results = self._parallel_search(
                query, config, metrics
            )
        else:
            vector_results, graph_results, ast_results, hybrid_results = self._sequential_search(
                query, config, metrics
            )

        # Merge results
        merge_start = time.time()
        merged_results = self.merger.merge_results(
            vector_results=vector_results,
            graph_results=graph_results,
            ast_results=ast_results,
            hybrid_results=hybrid_results,
            top_k=config.final_top_k
        )
        metrics.merge_time = time.time() - merge_start

        # Update metrics
        metrics.vector_count = len(vector_results) if vector_results else 0
        metrics.graph_count = len(graph_results) if graph_results else 0
        metrics.ast_count = len(ast_results) if ast_results else 0
        metrics.hybrid_count = len(hybrid_results) if hybrid_results else 0
        metrics.merged_count = len(merged_results)
        metrics.total_time = time.time() - start_time

        # Cache results if enabled
        if self._cache is not None:
            self._cache_result(query, merged_results)

        # Log performance
        self._log_performance(query, metrics)

        return merged_results, metrics

    def _parallel_search(self,
                        query: str,
                        config: TripleRAGConfig,
                        metrics: SearchMetrics) -> Tuple[
                            Optional[List[VectorSearchResult]],
                            Optional[List[GraphSearchResult]],
                            Optional[List[ASTSearchResult]],
                            Optional[List[HybridSearchResult]]
                        ]:
        """
        Execute searches in parallel.

        Args:
            query: Search query
            config: Search configuration
            metrics: Metrics object to update

        Returns:
            Tuple of search results from each method
        """
        vector_results = None
        graph_results = None
        ast_results = None
        hybrid_results = None

        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all search tasks
            futures = {}

            # Vector search
            futures[executor.submit(
                self._execute_vector_search,
                query,
                config
            )] = "vector"

            # Graph search
            futures[executor.submit(
                self._execute_graph_search,
                query,
                config
            )] = "graph"

            # AST search
            futures[executor.submit(
                self._execute_ast_search,
                query,
                config
            )] = "ast"

            # Hybrid search (if enabled)
            if config.enable_hybrid and self.hybrid_search:
                futures[executor.submit(
                    self._execute_hybrid_search,
                    query,
                    config
                )] = "hybrid"

            # Collect results as they complete
            for future in as_completed(futures):
                search_type = futures[future]
                try:
                    if search_type == "vector":
                        start = time.time()
                        vector_results = future.result()
                        metrics.vector_time = time.time() - start
                    elif search_type == "graph":
                        start = time.time()
                        graph_results = future.result()
                        metrics.graph_time = time.time() - start
                    elif search_type == "ast":
                        start = time.time()
                        ast_results = future.result()
                        metrics.ast_time = time.time() - start
                    elif search_type == "hybrid":
                        start = time.time()
                        hybrid_results = future.result()
                        metrics.hybrid_time = time.time() - start
                except Exception as e:
                    logger.error(f"Error in {search_type} search: {e}")

        return vector_results, graph_results, ast_results, hybrid_results

    def _sequential_search(self,
                          query: str,
                          config: TripleRAGConfig,
                          metrics: SearchMetrics) -> Tuple[
                              Optional[List[VectorSearchResult]],
                              Optional[List[GraphSearchResult]],
                              Optional[List[ASTSearchResult]],
                              Optional[List[HybridSearchResult]]
                          ]:
        """
        Execute searches sequentially.

        Args:
            query: Search query
            config: Search configuration
            metrics: Metrics object to update

        Returns:
            Tuple of search results from each method
        """
        # Vector search
        start = time.time()
        vector_results = self._execute_vector_search(query, config)
        metrics.vector_time = time.time() - start

        # Graph search
        start = time.time()
        graph_results = self._execute_graph_search(query, config)
        metrics.graph_time = time.time() - start

        # AST search
        start = time.time()
        ast_results = self._execute_ast_search(query, config)
        metrics.ast_time = time.time() - start

        # Hybrid search (if enabled)
        hybrid_results = None
        if config.enable_hybrid and self.hybrid_search:
            start = time.time()
            hybrid_results = self._execute_hybrid_search(query, config)
            metrics.hybrid_time = time.time() - start

        return vector_results, graph_results, ast_results, hybrid_results

    def _execute_vector_search(self,
                              query: str,
                              config: TripleRAGConfig) -> Optional[List[VectorSearchResult]]:
        """
        Execute vector similarity search.

        Args:
            query: Search query
            config: Search configuration

        Returns:
            Vector search results
        """
        try:
            logger.debug(f"Executing vector search for: {query[:50]}...")
            return self.vector_search.search(
                query=query,
                node_types=config.search_node_types,
                top_k=config.vector_top_k,
                min_score=config.vector_min_score
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return None

    def _execute_graph_search(self,
                             query: str,
                             config: TripleRAGConfig) -> Optional[List[GraphSearchResult]]:
        """
        Execute graph traversal search.

        Args:
            query: Search query
            config: Search configuration

        Returns:
            Graph search results
        """
        try:
            logger.debug(f"Executing graph search for: {query[:50]}...")
            return self.graph_search.search(
                query=query,
                relationship_types=None,  # Use defaults
                max_depth=config.graph_max_depth,
                max_results=config.graph_min_results * 3
            )
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return None

    def _execute_ast_search(self,
                           query: str,
                           config: TripleRAGConfig) -> Optional[List[ASTSearchResult]]:
        """
        Execute AST structural search.

        Args:
            query: Search query
            config: Search configuration

        Returns:
            AST search results
        """
        try:
            logger.debug(f"Executing AST search for: {query[:50]}...")
            return self.ast_search.search(
                query=query,
                max_results=config.ast_max_results
            )
        except Exception as e:
            logger.error(f"AST search failed: {e}")
            return None

    def _execute_hybrid_search(self,
                              query: str,
                              config: TripleRAGConfig) -> Optional[List[HybridSearchResult]]:
        """
        Execute hybrid vector+BM25 search.

        Args:
            query: Search query
            config: Search configuration

        Returns:
            Hybrid search results
        """
        if not self.hybrid_search:
            return None

        try:
            logger.debug(f"Executing hybrid search for: {query[:50]}...")

            # Generate embedding for hybrid search (reuse vector search's embedding)
            query_embedding = None
            if self.vector_search:
                query_embedding = self.vector_search.generate_query_embedding(query)

            return self.hybrid_search.search(
                query=query,
                query_embedding=query_embedding,
                node_types=config.search_node_types,
                top_k=config.hybrid_top_k,
                min_score=config.vector_min_score
            )
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return None

    def _check_cache(self, query: str) -> Optional[List[MergedResult]]:
        """
        Check cache for query results.

        Args:
            query: Search query

        Returns:
            Cached results if found and not expired
        """
        if query not in self._cache:
            return None

        # Check if cache entry is expired
        timestamp = self._cache_timestamps.get(query, 0)
        if time.time() - timestamp > self.config.cache_ttl:
            # Expired, remove from cache
            del self._cache[query]
            del self._cache_timestamps[query]
            return None

        logger.debug(f"Cache hit for query: {query[:50]}...")
        return self._cache[query]

    def _cache_result(self, query: str, results: List[MergedResult]):
        """
        Cache search results.

        Args:
            query: Search query
            results: Results to cache
        """
        self._cache[query] = results
        self._cache_timestamps[query] = time.time()

        # Limit cache size
        if len(self._cache) > 100:
            # Remove oldest entries
            oldest_queries = sorted(
                self._cache_timestamps.items(),
                key=lambda x: x[1]
            )[:20]
            for old_query, _ in oldest_queries:
                del self._cache[old_query]
                del self._cache_timestamps[old_query]

    def _apply_config_override(self, override: Optional[Dict[str, Any]]) -> TripleRAGConfig:
        """
        Apply configuration overrides.

        Args:
            override: Dictionary of config overrides

        Returns:
            Modified configuration
        """
        if not override:
            return self.config

        # Create a copy of the config
        import copy
        config = copy.deepcopy(self.config)

        # Apply overrides
        for key, value in override.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config

    def _log_performance(self, query: str, metrics: SearchMetrics):
        """
        Log search performance metrics.

        Args:
            query: Search query
            metrics: Search metrics
        """
        logger.info(
            f"Search completed for '{query[:30]}...': "
            f"Total={metrics.total_time:.2f}s, "
            f"Vector={metrics.vector_time:.2f}s ({metrics.vector_count}), "
            f"Graph={metrics.graph_time:.2f}s ({metrics.graph_count}), "
            f"AST={metrics.ast_time:.2f}s ({metrics.ast_count}), "
            f"Merged={metrics.merged_count}, "
            f"Cache={'HIT' if metrics.cache_hit else 'MISS'}"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics from all search components.

        Returns:
            Combined statistics dictionary
        """
        stats = {
            "vector": self.vector_search.get_index_statistics(),
            "graph": self.graph_search.get_graph_statistics(),
            "ast": self.ast_search.get_ast_statistics(),
            "cache_size": len(self._cache) if self._cache else 0,
            "config": {
                "weights": {
                    "vector": self.config.vector_weight,
                    "graph": self.config.graph_weight,
                    "ast": self.config.ast_weight
                },
                "parallel_enabled": self.config.use_parallel,
                "cache_enabled": self.config.cache_results
            }
        }
        return stats

    def clear_cache(self):
        """Clear the results cache."""
        if self._cache is not None:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("Cache cleared")