"""
Main Query Pipeline Orchestrator
Coordinates Agent → Triple RAG → Reasoning → Articulation flow
"""

import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from ..context.agent import IntelligentAgent, AgentResponse
from ..context.session_manager import SessionManager
from ..retrieval.triple_rag import TripleRAG, MergedResult, SearchMetrics
from ..retrieval.enhanced_triple_rag import EnhancedTripleRAG, EnhancedTripleRAGConfig, EnhancedSearchMetrics
from ..reasoning.engine import ReasoningEngine, ReasonedAnswer
from ..reasoning.models import Citation
from ..articulation.apertus_client import ApertusChatClient
from ..enrichment.court_decision_client import EntscheidSucheClient, CourtDecisionEnricher
from .async_wrapper import AsyncWrapper
from .error_handler import ErrorHandler, PipelineError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the query pipeline"""
    # Component enable flags
    enable_agent: bool = True
    enable_rag: bool = True
    enable_reasoning: bool = True
    enable_articulation: bool = True
    enable_legal_logic: bool = True  # Enable Legal Logic AST
    enable_court_decisions: bool = True  # Enable court decision enrichment

    # Performance settings
    timeout_seconds: int = 30
    enable_caching: bool = True
    cache_ttl: int = 300

    # Parallel execution
    use_parallel: bool = True
    max_workers: int = 4

    # Error handling
    enable_graceful_degradation: bool = True
    retry_on_failure: bool = True
    max_retries: int = 3

    # Monitoring
    enable_monitoring: bool = True
    enable_tracing: bool = True

    # Response settings
    max_response_length: int = 2000
    include_citations: bool = True
    include_confidence: bool = True
    include_reasoning_chain: bool = False
    include_metrics: bool = False


@dataclass
class PipelineResult:
    """Result from the query pipeline execution"""
    # Core response
    answer: str
    confidence: float

    # Supporting information
    citations: List[Citation] = field(default_factory=list)
    reasoning_chain: Optional[List[str]] = None
    sources: Optional[List[Dict[str, Any]]] = None
    court_decisions: Optional[Dict[str, List[Dict[str, Any]]]] = None  # Court decisions by article

    # Metadata
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    execution_time: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None

    # Error information
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        result = {
            "answer": self.answer,
            "confidence": self.confidence
        }

        if self.citations:
            result["citations"] = [
                {
                    "source": c.source,
                    "reference": c.reference,
                    "relevance": c.relevance
                } for c in self.citations
            ]

        if self.reasoning_chain:
            result["reasoning_chain"] = self.reasoning_chain

        if self.sources:
            result["sources"] = self.sources

        if self.court_decisions:
            result["court_decisions"] = self.court_decisions

        if self.session_id:
            result["session_id"] = self.session_id

        if self.trace_id:
            result["trace_id"] = self.trace_id

        if self.execution_time:
            result["execution_time"] = self.execution_time

        if self.metrics:
            result["metrics"] = self.metrics

        if self.errors:
            result["errors"] = self.errors

        if self.warnings:
            result["warnings"] = self.warnings

        return result

    def format_for_challenge(self) -> Dict[str, Any]:
        """
        Format result for Swiss Law RAG Challenge requirements.
        Returns dictionary with Answer, Citations, and Confidence.
        """
        # Format citations in challenge format
        formatted_citations = []
        if self.citations:
            for citation in self.citations[:5]:  # Limit to top 5
                # Use the challenge format method if available
                if hasattr(citation, 'format_for_challenge'):
                    formatted_citations.append(citation.format_for_challenge())
                elif hasattr(citation, 'law_abbreviation') and citation.law_abbreviation:
                    # Format with law abbreviation
                    if citation.article:
                        if citation.paragraph:
                            formatted_citations.append(f"Art. {citation.article} Abs. {citation.paragraph} {citation.law_abbreviation}")
                        else:
                            formatted_citations.append(f"Art. {citation.article} {citation.law_abbreviation}")
                    else:
                        formatted_citations.append(citation.law_abbreviation)
                else:
                    # Fallback to string representation
                    formatted_citations.append(str(citation))

        return {
            "Answer": self.answer,
            "Citations": formatted_citations,
            "Confidence": round(self.confidence, 2) if self.confidence else 0.5
        }


class QueryPipeline:
    """
    Main orchestrator for the LAWAST query pipeline.
    Coordinates the flow: Agent → Triple RAG → Reasoning → Articulation
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize the query pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()

        # Initialize components
        self._init_components()

        # Initialize utilities
        self.async_wrapper = AsyncWrapper()
        self.error_handler = ErrorHandler(
            enable_graceful_degradation=self.config.enable_graceful_degradation
        )

        if self.config.enable_monitoring:
            self.monitor = PerformanceMonitor()
        else:
            self.monitor = None

        logger.info("Query pipeline initialized with config: %s", self.config)

    def _init_components(self):
        """Initialize pipeline components"""
        # Session manager (always needed for multi-turn support)
        self.session_manager = SessionManager()

        # Initialize components based on config
        if self.config.enable_agent:
            self.agent = IntelligentAgent(
                triple_rag=None,  # Will be set if RAG is enabled
                session_manager=self.session_manager
            )
        else:
            self.agent = None

        if self.config.enable_rag:
            # Use Enhanced Triple RAG if Legal Logic is enabled
            if self.config.enable_legal_logic:
                # Configure Enhanced Triple RAG with Legal Logic
                enhanced_config = EnhancedTripleRAGConfig(
                    enable_legal_logic=True,
                    legal_language="de",  # Default to German
                    enable_condition_evaluation=True,
                    legal_logic_weight=0.35,  # Higher weight for legal logic
                    vector_weight=0.25,
                    graph_weight=0.25,
                    hybrid_weight=0.15,
                    legal_logic_boost=1.2,  # Boost results with legal logic
                    use_parallel=self.config.use_parallel
                )
                self.rag = EnhancedTripleRAG(config=enhanced_config)
                logger.info("Using Enhanced Triple RAG with Legal Logic AST")
            else:
                # Use standard Triple RAG
                self.rag = TripleRAG()
                logger.info("Using standard Triple RAG")

            if self.agent:
                self.agent.triple_rag = self.rag
        else:
            self.rag = None

        if self.config.enable_reasoning:
            # Initialize Apertus client for reasoning if needed
            apertus_client = ApertusChatClient() if self.config.enable_articulation else None

            # Get Neo4j connection from RAG if available
            neo4j_connection = None
            if self.rag:
                # Access the connection directly from TripleRAG
                neo4j_connection = self.rag.connection

            # Configure reasoning engine to use rule-based reasoning for consistency
            reasoning_config = {
                "enable_llm_reasoning": False,  # Use rule-based for consistent results
                "max_reasoning_steps": 10,
                "min_confidence_threshold": 0.3
            }
            self.reasoning_engine = ReasoningEngine(
                apertus_client=apertus_client,
                neo4j_connection=neo4j_connection,
                config=reasoning_config
            )
        else:
            self.reasoning_engine = None

        if self.config.enable_articulation and not self.config.enable_reasoning:
            # Standalone articulation client
            self.articulator = ApertusChatClient()
        else:
            self.articulator = None

        # Initialize court decision enricher if enabled
        if self.config.enable_court_decisions:
            self.court_decision_enricher = CourtDecisionEnricher()
        else:
            self.court_decision_enricher = None

    async def execute(self,
                     query: str,
                     session_id: Optional[str] = None,
                     context: Optional[Dict[str, Any]] = None) -> PipelineResult:
        """
        Execute the complete query pipeline.

        Args:
            query: User query to process
            session_id: Optional session ID for multi-turn dialogue
            context: Optional additional context

        Returns:
            PipelineResult with answer and metadata
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())

        # Initialize result
        result = PipelineResult(
            answer="",
            confidence=0.0,
            session_id=session_id,
            trace_id=trace_id
        )

        try:
            # Start monitoring
            if self.monitor:
                self.monitor.start_request(trace_id)

            logger.info(f"[{trace_id}] Starting pipeline for query: {query[:100]}...")
            print(f"\n{'='*60}")
            print(f"🔍 PIPELINE EXECUTION DETAILS")
            print(f"{'='*60}")
            print(f"Query: {query}")
            print(f"Session: {session_id or 'New session'}")
            print(f"Trace ID: {trace_id}")
            print(f"{'='*60}\n")

            # Stage 1: Agent Analysis
            print(f"\n1️⃣  STAGE 1: INTELLIGENT AGENT ANALYSIS")
            print(f"   Analyzing query intent and context...")
            agent_response = await self._execute_agent(query, session_id, trace_id)
            if agent_response:
                print(f"   ✓ Agent analysis complete")
                print(f"   - Legal domain: {agent_response.legal_domain if hasattr(agent_response, 'legal_domain') else 'General'}")
                print(f"   - Clarification needed: {agent_response.clarification_needed if hasattr(agent_response, 'clarification_needed') else False}")
            else:
                print(f"   ⚠ Agent analysis skipped or failed")

            # Check if clarification is needed
            if agent_response and agent_response.clarification_needed:
                result.answer = agent_response.response
                result.warnings.append("Clarification needed from user")
                return result

            # Stage 2: RAG Retrieval
            print(f"\n2️⃣  STAGE 2: RAG RETRIEVAL")
            print(f"   Searching legal database...")
            rag_results, search_metrics = await self._execute_rag(
                query,
                agent_response,
                trace_id,
                context=context
            )
            if rag_results:
                print(f"   ✓ Retrieved {len(rag_results)} relevant documents")
                for i, doc in enumerate(rag_results[:3], 1):
                    print(f"   {i}. {getattr(doc, 'title', 'Document')} (Score: {getattr(doc, 'combined_score', 0):.2f})")
            else:
                print(f"   ⚠ No documents retrieved")

            # Stage 3: Reasoning
            print(f"\n3️⃣  STAGE 3: REASONING ENGINE")
            print(f"   Analyzing legal implications...")
            reasoned_answer = await self._execute_reasoning(
                query,
                rag_results,
                trace_id
            )
            if reasoned_answer:
                print(f"   ✓ Reasoning complete")
                print(f"   - Confidence: {reasoned_answer.confidence:.1%}")
                print(f"   - Citations: {len(reasoned_answer.citations) if reasoned_answer.citations else 0}")
            else:
                print(f"   ⚠ Reasoning engine skipped")

            # Stage 4: Articulation (if not already done in reasoning)
            print(f"\n4️⃣  STAGE 4: ARTICULATION WITH APERTUS")
            print(f"   Generating natural language response...")
            final_answer = await self._execute_articulation(
                query,
                reasoned_answer,
                rag_results,
                trace_id
            )
            if final_answer:
                print(f"   ✓ Response generated ({len(final_answer)} chars)")
            else:
                print(f"   ⚠ Using fallback response")

            # Stage 5: Court Decision Enrichment (if enabled)
            # Keep court decisions as separate metadata, don't modify the answer
            if self.config.enable_court_decisions and self.court_decision_enricher:
                print(f"\n5️⃣  STAGE 5: COURT DECISION ENRICHMENT")
                print(f"   Searching for relevant court decisions...")
                court_decisions = await self._get_court_decisions(
                    final_answer,
                    reasoned_answer.citations if reasoned_answer else [],
                    trace_id
                )
                if court_decisions:
                    print(f"   ✓ Found {len(court_decisions)} relevant court decisions")
                    result.court_decisions = court_decisions
                else:
                    print(f"   ⚠ No court decisions found")

            # Compile final result (answer unchanged)
            result.answer = final_answer

            if reasoned_answer:
                result.confidence = reasoned_answer.confidence
                result.citations = reasoned_answer.citations
                if self.config.include_reasoning_chain:
                    result.reasoning_chain = [
                        step.description for step in reasoned_answer.reasoning_steps
                    ]

            if self.config.include_metrics and search_metrics:
                result.metrics = {
                    "search": search_metrics.__dict__ if hasattr(search_metrics, '__dict__') else {}
                }

            # Add sources if requested
            if rag_results and context and context.get("include_sources"):
                result.sources = [
                    {
                        "id": r.id,
                        "title": r.title,
                        "score": r.final_score
                    } for r in rag_results[:5]
                ]

        except Exception as e:
            logger.error(f"[{trace_id}] Pipeline error: {str(e)}")

            # Handle error with graceful degradation
            if self.config.enable_graceful_degradation:
                result = await self._handle_error(e, query, trace_id)
            else:
                raise PipelineError(f"Pipeline execution failed: {str(e)}")

        finally:
            # Calculate execution time
            result.execution_time = time.time() - start_time

            # End monitoring
            if self.monitor:
                self.monitor.end_request(trace_id, result.execution_time)

            print(f"\n{'='*60}")
            print(f"📊 EXECUTION SUMMARY")
            print(f"{'='*60}")
            print(f"Total execution time: {result.execution_time:.2f}s")
            print(f"Final confidence: {result.confidence:.1%}")
            print(f"Response length: {len(result.answer)} chars")
            print(f"{'='*60}\n")

            logger.info(
                f"[{trace_id}] Pipeline completed in {result.execution_time:.2f}s"
            )

        return result

    async def _execute_agent(self,
                           query: str,
                           session_id: Optional[str],
                           trace_id: str) -> Optional[AgentResponse]:
        """Execute agent analysis stage"""
        if not self.config.enable_agent or not self.agent:
            return None

        try:
            if self.monitor:
                self.monitor.start_stage(trace_id, "agent")

            # Agent is synchronous, wrap in async
            response = await self.async_wrapper.run_sync(
                self.agent.process_query,
                query,
                session_id=session_id
            )

            if self.monitor:
                self.monitor.end_stage(trace_id, "agent")

            return response

        except Exception as e:
            logger.error(f"[{trace_id}] Agent stage failed: {str(e)}")
            if not self.config.enable_graceful_degradation:
                raise
            return None

    async def _execute_rag(self,
                          query: str,
                          agent_response: Optional[AgentResponse],
                          trace_id: str,
                          context: Optional[Dict[str, Any]] = None) -> tuple:
        """Execute RAG retrieval stage"""
        if not self.config.enable_rag or not self.rag:
            return [], None

        try:
            if self.monitor:
                self.monitor.start_stage(trace_id, "rag")

            # Prepare config override from agent strategy
            config_override = None
            if agent_response and agent_response.strategy_used:
                strategy = agent_response.strategy_used
                if strategy == "vector":
                    config_override = {"vector_weight": 0.8, "graph_weight": 0.1, "ast_weight": 0.1}
                elif strategy == "graph":
                    config_override = {"vector_weight": 0.1, "graph_weight": 0.8, "ast_weight": 0.1}
                elif strategy == "ast":
                    config_override = {"vector_weight": 0.1, "graph_weight": 0.1, "ast_weight": 0.8}

            # Check if using Enhanced Triple RAG with Legal Logic
            if self.config.enable_legal_logic and isinstance(self.rag, EnhancedTripleRAG):
                # Enhanced RAG can accept context for condition evaluation
                results, metrics = await self.async_wrapper.run_sync(
                    self.rag.search,
                    query,
                    context=context,
                    config_override=config_override
                )
            else:
                # Standard RAG doesn't accept context
                results, metrics = await self.async_wrapper.run_sync(
                    self.rag.search,
                    query,
                    config_override=config_override
                )

            if self.monitor:
                self.monitor.end_stage(trace_id, "rag")

            return results, metrics

        except Exception as e:
            logger.error(f"[{trace_id}] RAG stage failed: {str(e)}")
            if not self.config.enable_graceful_degradation:
                raise
            return [], None

    async def _execute_reasoning(self,
                                query: str,
                                rag_results: List[MergedResult],
                                trace_id: str) -> Optional[ReasonedAnswer]:
        """Execute reasoning stage"""
        if not self.config.enable_reasoning or not self.reasoning_engine:
            return None

        try:
            if self.monitor:
                self.monitor.start_stage(trace_id, "reasoning")

            # Reasoning is synchronous, wrap in async
            answer = await self.async_wrapper.run_sync(
                self.reasoning_engine.reason,
                query,
                rag_results
            )

            if self.monitor:
                self.monitor.end_stage(trace_id, "reasoning")

            return answer

        except Exception as e:
            logger.error(f"[{trace_id}] Reasoning stage failed: {str(e)}")
            if not self.config.enable_graceful_degradation:
                raise
            return None

    async def _execute_articulation(self,
                                  query: str,
                                  reasoned_answer: Optional[ReasonedAnswer],
                                  rag_results: List[MergedResult],
                                  trace_id: str) -> str:
        """Execute articulation stage"""
        # If reasoning already generated the answer, return it
        if reasoned_answer and reasoned_answer.answer:
            return reasoned_answer.answer

        # If standalone articulation is not enabled, create basic answer
        if not self.config.enable_articulation or not self.articulator:
            if rag_results:
                # Create simple answer from top result
                top_result = rag_results[0]
                return f"Based on {top_result.title}: {top_result.content[:500]}..."
            else:
                return "I couldn't find relevant information to answer your question."

        try:
            if self.monitor:
                self.monitor.start_stage(trace_id, "articulation")

            # Prepare context for articulation
            context = self._prepare_articulation_context(query, rag_results)

            # Articulator.chat is synchronous, wrap in async
            answer = await self.async_wrapper.run_sync(
                self.articulator.chat,
                query,
                system_prompt=context
            )

            if self.monitor:
                self.monitor.end_stage(trace_id, "articulation")

            return answer

        except Exception as e:
            logger.error(f"[{trace_id}] Articulation stage failed: {str(e)}")
            if not self.config.enable_graceful_degradation:
                raise
            return "I encountered an error while generating the response."

    def _prepare_articulation_context(self,
                                     query: str,
                                     rag_results: List[MergedResult]) -> str:
        """Prepare context for articulation"""
        context = "You are a Swiss legal assistant. Answer based on the following information:\n\n"

        for i, result in enumerate(rag_results[:3], 1):
            context += f"{i}. {result.title}:\n{result.content[:300]}...\n\n"

        context += f"\nQuestion: {query}\n"
        context += "Provide a clear, accurate answer based on Swiss law."

        return context

    async def _get_court_decisions(self,
                                          answer: str,
                                          citations: List[Citation],
                                          trace_id: str) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """
        Get relevant court decisions for citations (without modifying answer).

        Args:
            answer: The generated answer
            citations: List of citations from reasoning
            trace_id: Trace ID for logging

        Returns:
            Dictionary of court decisions by article reference
        """
        if not self.court_decision_enricher:
            return None

        try:
            # Extract article citations from the answer and citations
            article_citations = []

            # Extract from citations
            import re
            for citation in citations:
                # First try to get law abbreviation from the citation object itself
                if hasattr(citation, 'law_abbreviation') and citation.law_abbreviation:
                    law_abbrev = citation.law_abbreviation
                elif hasattr(citation, 'sr_number') and citation.sr_number == '101':
                    law_abbrev = 'BV'
                else:
                    law_abbrev = 'BV'  # Default to BV since we're processing BV articles

                # Get article number
                article_num = None
                if hasattr(citation, 'article') and citation.article:
                    article_num = citation.article
                elif hasattr(citation, 'reference') and citation.reference:
                    match = re.search(r"Art\.\s*(\d+[a-z]?)", str(citation.reference))
                    if match:
                        article_num = match.group(1)
                elif hasattr(citation, 'source') and citation.source:
                    match = re.search(r"Art\.\s*(\d+[a-z]?)", str(citation.source))
                    if match:
                        article_num = match.group(1)

                # Add citation if we have an article number
                if article_num and not any(c['article'] == article_num and c['law'] == law_abbrev for c in article_citations):
                    article_citations.append({
                        'article': article_num,
                        'law': law_abbrev
                    })

            # Also extract from the answer text - but be careful with parsing
            # Look for explicit law citations like "Art. 114 BV" or "Art. 335b OR"
            explicit_pattern = r"Art(?:icle|ikel|\.)?\s*(\d+[a-z]?)\s+(BV|OR|DSG|ZGB|StGB|ZPO|StPO)\b"
            matches = re.findall(explicit_pattern, answer)
            for article_num, law_abbrev in matches:
                if not any(c['article'] == article_num and c['law'] == law_abbrev
                          for c in article_citations):
                    article_citations.append({
                        'article': article_num,
                        'law': law_abbrev
                    })

            # For articles without explicit law abbreviation in answer, use BV default
            simple_pattern = r"Art(?:icle|ikel|\.)?\s*(\d+[a-z]?)(?:\s+[A-Z][a-z]|\s*:|\s+\d|\s*$)"
            simple_matches = re.findall(simple_pattern, answer)
            for article_num in simple_matches:
                # Only add if not already present
                if article_num and not any(c['article'] == article_num for c in article_citations):
                    article_citations.append({
                        'article': article_num,
                        'law': 'BV'  # Default to BV for articles in answer
                    })

            if not article_citations:
                logger.info(f"[{trace_id}] No article citations found for court decision enrichment")
                return None

            logger.info(f"[{trace_id}] Found {len(article_citations)} article citations to enrich")

            # Search for court decisions for each citation
            court_decisions = {}
            enrichment_text = ""

            for citation in article_citations[:3]:  # Limit to top 3 citations
                key = f"Art. {citation['article']} {citation['law']}"

                # Search for court decisions
                decisions = await self.async_wrapper.run_sync(
                    self.court_decision_enricher.client.search_by_article,
                    citation['article'],
                    citation['law'],
                    limit=2  # Get top 2 decisions per article
                )

                if decisions:
                    court_decisions[key] = [
                        {
                            'id': d.decision_id,
                            'court': d.court,
                            'date': d.date,
                            'title': d.title,
                            'excerpt': d.excerpt,
                            'url': d.url,
                            'relevance': d.relevance_score
                        }
                        for d in decisions
                    ]

                    # Add to enrichment text with links
                    if not enrichment_text:
                        enrichment_text = "\n\n**📚 Relevant Court Decisions:**\n"

                    enrichment_text += f"\n**{key}:**\n"
                    for decision in decisions[:2]:
                        enrichment_text += f"• **{decision.decision_id}** - {decision.court} ({decision.date})\n"
                        if decision.title:
                            enrichment_text += f"  *{decision.title[:100]}{'...' if len(decision.title) > 100 else ''}*\n"
                        if decision.excerpt:
                            excerpt = decision.excerpt[:150] + "..." if len(decision.excerpt) > 150 else decision.excerpt
                            enrichment_text += f"  \"{excerpt}\"\n"
                        if decision.url:
                            enrichment_text += f"  🔗 [View Full Decision]({decision.url})\n"
                        enrichment_text += "\n"

            # Return court decisions if found
            if court_decisions:
                logger.info(f"[{trace_id}] Found {len(court_decisions)} court decision references")
                return court_decisions
            else:
                return None

        except Exception as e:
            logger.error(f"[{trace_id}] Error enriching with court decisions: {str(e)}")
            # Return None on error
            return None

    async def _handle_error(self,
                          error: Exception,
                          query: str,
                          trace_id: str) -> PipelineResult:
        """Handle pipeline errors with graceful degradation"""
        logger.warning(f"[{trace_id}] Attempting graceful degradation after error: {str(error)}")

        result = PipelineResult(
            answer="I encountered an issue processing your request. Please try rephrasing your question.",
            confidence=0.0,
            trace_id=trace_id,
            errors=[str(error)]
        )

        # Try to provide a basic response
        try:
            # Attempt direct RAG search without other components
            if self.rag:
                results, _ = await self.async_wrapper.run_sync(
                    self.rag.search,
                    query,
                    config_override={"final_top_k": 3}
                )

                if results:
                    top_result = results[0]
                    result.answer = (
                        f"Based on available information from {top_result.title}: "
                        f"{top_result.content[:300]}..."
                    )
                    result.confidence = 0.3
                    result.warnings.append("Response generated with limited processing due to system error")

        except Exception as fallback_error:
            logger.error(f"[{trace_id}] Fallback also failed: {str(fallback_error)}")
            result.errors.append(str(fallback_error))

        return result

    async def process_with_session(self,
                                  query: str,
                                  session_id: Optional[str] = None) -> PipelineResult:
        """
        Process query with session management for multi-turn dialogue.

        Args:
            query: User query
            session_id: Session ID (creates new if None)

        Returns:
            PipelineResult with session information
        """
        # Create or get session
        if not session_id:
            session_id = str(uuid.uuid4())
            self.session_manager.create_session(session_id)

        # Execute pipeline with session
        result = await self.execute(query, session_id=session_id)
        result.session_id = session_id

        return result

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all pipeline components.

        Returns:
            Health status of each component
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }

        # Check each component
        components_to_check = [
            ("agent", self.agent),
            ("rag", self.rag),
            ("reasoning", self.reasoning_engine),
            ("articulation", self.articulator)
        ]

        for name, component in components_to_check:
            if component:
                try:
                    # Simple existence check for now
                    health["components"][name] = {"status": "healthy"}
                except Exception as e:
                    health["components"][name] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
                    health["status"] = "degraded"
            else:
                health["components"][name] = {"status": "disabled"}

        return health