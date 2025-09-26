"""
Intelligent Agent System - Main orchestrator for query analysis and RAG coordination
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from .query_analyzer import QueryAnalyzer, QueryAnalysis
from .strategy_planner import StrategyPlanner, StrategyDecision
from .clarification_generator import ClarificationGenerator, ClarificationQuestion
from .context_tree import ContextTree
from .session_manager import SessionManager, SessionState
from ..retrieval.triple_rag import TripleRAG, MergedResult, SearchMetrics

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from the intelligent agent"""
    response: str
    clarification_needed: bool = False
    clarifications: List[ClarificationQuestion] = None
    strategy_used: str = None
    confidence: float = 1.0
    search_metrics: Optional[SearchMetrics] = None
    session_id: Optional[str] = None


class IntelligentAgent:
    """Main orchestrator for the intelligent agent system"""

    def __init__(self,
                triple_rag: Optional[TripleRAG] = None,
                session_manager: Optional[SessionManager] = None):
        """
        Initialize the intelligent agent.

        Args:
            triple_rag: Triple RAG orchestrator instance
            session_manager: Session manager instance
        """
        # Initialize components
        self.query_analyzer = QueryAnalyzer()
        self.strategy_planner = StrategyPlanner()
        self.clarification_generator = ClarificationGenerator()
        self.session_manager = session_manager or SessionManager()

        # Triple RAG for retrieval
        self.triple_rag = triple_rag

        logger.info("Intelligent Agent initialized")

    def process_query(self,
                      query: str,
                      session_id: Optional[str] = None,
                      force_new_session: bool = False) -> AgentResponse:
        """
        Process a user query through the full agent pipeline.

        Args:
            query: User query
            session_id: Optional session ID for multi-turn dialogue
            force_new_session: Force creation of new session

        Returns:
            AgentResponse with results or clarifications
        """
        # Get or create session
        session = self._get_or_create_session(session_id, force_new_session)
        session_id = session.session_id

        # Add query to context tree
        if session.context_tree:
            session.context_tree.add_question(query)

        # Analyze query
        analysis = self.query_analyzer.analyze(query)
        logger.info(f"Query analysis: intent={analysis.intent.value}, "
                   f"complexity={analysis.complexity.value}, "
                   f"ambiguity={analysis.ambiguity_score:.2f}")

        # Plan strategy
        strategy = self.strategy_planner.plan(analysis)
        logger.info(f"Strategy: {strategy.primary_strategy.value} "
                   f"(confidence: {strategy.confidence:.2f})")

        # Check if clarification is needed
        if self.strategy_planner.needs_clarification(analysis, strategy.confidence):
            clarifications = self._generate_clarifications(analysis, session)
            if clarifications:
                # Update session
                self.session_manager.update_session(session_id, query=query)

                return AgentResponse(
                    response=self.clarification_generator.format_for_user(clarifications),
                    clarification_needed=True,
                    clarifications=clarifications,
                    strategy_used=strategy.primary_strategy.value,
                    confidence=strategy.confidence,
                    session_id=session_id
                )

        # Execute retrieval if Triple RAG is available
        if self.triple_rag:
            try:
                results, metrics = self._execute_retrieval(
                    query, strategy, session
                )
                response = self._format_response(results, analysis, strategy)
            except Exception as e:
                logger.error(f"Retrieval error: {e}")
                response = "An error occurred during retrieval. Please try rephrasing your query."
                metrics = None
        else:
            # Fallback response without retrieval
            response = f"Analysis complete. Strategy: {strategy.primary_strategy.value} " \
                      f"(confidence: {strategy.confidence:.2f}). " \
                      f"Triple RAG not available for retrieval."
            metrics = None

        # Update session with response
        self.session_manager.update_session(session_id, query=query, response=response)

        # Add to context tree
        if session.context_tree:
            session.context_tree.add_answer(response, {
                'strategy': strategy.primary_strategy.value,
                'confidence': strategy.confidence
            })
            # Extract and store information
            session.context_tree.extract_and_store_info(
                entities=analysis.entities,
                intent=analysis.intent.value,
                topics=analysis.keywords
            )

        return AgentResponse(
            response=response,
            clarification_needed=False,
            strategy_used=strategy.primary_strategy.value,
            confidence=strategy.confidence,
            search_metrics=metrics,
            session_id=session_id
        )

    def process_clarification_response(self,
                                      session_id: str,
                                      clarification_response: str,
                                      original_query: str) -> AgentResponse:
        """
        Process user's response to clarification question.

        Args:
            session_id: Session ID
            clarification_response: User's clarification response
            original_query: Original query that needed clarification

        Returns:
            AgentResponse with refined results
        """
        # Get session
        session = self.session_manager.get_session(session_id)
        if not session:
            # Session expired, create new one
            return self.process_query(original_query, force_new_session=True)

        # Add clarification to context tree
        if session.context_tree:
            session.context_tree.add_clarification(
                "Clarification requested",
                clarification_response
            )

        # Build refined query
        refined_query = f"{original_query}. {clarification_response}"

        # Re-analyze with clarification
        analysis = self.query_analyzer.analyze(refined_query)

        # Update context with clarification
        if 'naturalization' in clarification_response.lower():
            analysis.entities['citizenship_type'] = ['naturalization']
        elif 'birth' in clarification_response.lower():
            analysis.entities['citizenship_type'] = ['by_birth']
        elif 'marriage' in clarification_response.lower():
            analysis.entities['citizenship_type'] = ['by_marriage']

        # Re-plan strategy with updated context
        strategy = self.strategy_planner.plan(analysis)

        # Execute retrieval with refined understanding
        if self.triple_rag:
            results, metrics = self._execute_retrieval(
                refined_query, strategy, session
            )
            response = self._format_response(results, analysis, strategy)
        else:
            response = f"Refined analysis complete. Strategy: {strategy.primary_strategy.value}"
            metrics = None

        # Update session
        self.session_manager.update_session(
            session_id,
            query=refined_query,
            response=response
        )

        return AgentResponse(
            response=response,
            clarification_needed=False,
            strategy_used=strategy.primary_strategy.value,
            confidence=strategy.confidence,
            search_metrics=metrics,
            session_id=session_id
        )

    def _get_or_create_session(self,
                              session_id: Optional[str],
                              force_new: bool) -> SessionState:
        """
        Get existing session or create new one.

        Args:
            session_id: Optional session ID
            force_new: Force new session creation

        Returns:
            SessionState object
        """
        if force_new or not session_id:
            return self.session_manager.create_session()

        session = self.session_manager.get_session(session_id)
        if not session:
            # Session expired or not found
            return self.session_manager.create_session()

        return session

    def _generate_clarifications(self,
                                analysis: QueryAnalysis,
                                session: SessionState) -> List[ClarificationQuestion]:
        """
        Generate clarification questions.

        Args:
            analysis: Query analysis
            session: Current session

        Returns:
            List of clarification questions
        """
        # Get context from session
        context = None
        if session.context_tree:
            context = session.context_tree.get_summary()

        # Generate clarifications
        clarifications = self.clarification_generator.generate(
            analysis, context
        )

        return clarifications

    def _execute_retrieval(self,
                          query: str,
                          strategy: StrategyDecision,
                          session: SessionState) -> Tuple[List[MergedResult], SearchMetrics]:
        """
        Execute retrieval using Triple RAG.

        Args:
            query: Search query
            strategy: Strategy decision
            session: Current session

        Returns:
            Tuple of (results, metrics)
        """
        # Build context-enhanced query if we have history
        enhanced_query = query
        if session.context_tree and session.turn_count > 0:
            context = session.context_tree.get_summary()
            if context.get('topics'):
                enhanced_query = f"{query} (context: {', '.join(context['topics'][:3])})"

        # Execute Triple RAG with strategy config
        results, metrics = self.triple_rag.search(
            enhanced_query,
            config_override=strategy.config_overrides
        )

        # Check fallback if needed
        if not results and strategy.fallback_strategy:
            logger.info(f"Primary strategy yielded no results, trying fallback: "
                       f"{strategy.fallback_strategy.value}")
            # Adjust config for fallback
            fallback_config = self._get_fallback_config(strategy.fallback_strategy)
            results, metrics = self.triple_rag.search(
                enhanced_query,
                config_override=fallback_config
            )

        return results, metrics

    def _get_fallback_config(self, fallback_strategy) -> Dict[str, Any]:
        """
        Get configuration for fallback strategy.

        Args:
            fallback_strategy: Fallback strategy enum

        Returns:
            Configuration dictionary
        """
        # Use balanced weights for fallback
        return {
            'vector_weight': 0.4,
            'graph_weight': 0.3,
            'ast_weight': 0.3,
            'final_top_k': 15
        }

    def _format_response(self,
                        results: List[MergedResult],
                        analysis: QueryAnalysis,
                        strategy: StrategyDecision) -> str:
        """
        Format retrieval results into response.

        Args:
            results: Retrieval results
            analysis: Query analysis
            strategy: Strategy used

        Returns:
            Formatted response string
        """
        if not results:
            return "No relevant information found for your query. " \
                  "Please try rephrasing or providing more context."

        # Build response based on intent
        response_parts = []

        # Add header based on intent
        if analysis.intent.name == "FACTUAL":
            response_parts.append("Based on the legal documents:")
        elif analysis.intent.name == "COMPARATIVE":
            response_parts.append("Comparison of the relevant provisions:")
        elif analysis.intent.name == "PROCEDURAL":
            response_parts.append("Here are the steps/requirements:")
        else:
            response_parts.append("Relevant information found:")

        # Format top results
        for i, result in enumerate(results[:3], 1):
            content = result.content[:500]  # Limit content length
            source = result.metadata.get('source', 'Unknown')
            response_parts.append(f"\n{i}. {content}... (Source: {source})")

        # Add confidence note if low
        if strategy.confidence < 0.7:
            response_parts.append(
                f"\nNote: Confidence in this response is {strategy.confidence:.1%}. "
                f"You may want to refine your query for better results."
            )

        return "\n".join(response_parts)

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of a session.

        Args:
            session_id: Session ID

        Returns:
            Session summary dictionary
        """
        context = self.session_manager.get_session_context(session_id)
        history = self.session_manager.get_session_history(session_id)

        if context:
            return {
                'session_id': session_id,
                'context': context,
                'history_length': len(history),
                'last_turns': history[-4:] if history else []
            }
        return None

    def clear_session(self, session_id: str) -> bool:
        """
        Clear/expire a session.

        Args:
            session_id: Session ID

        Returns:
            True if cleared
        """
        return self.session_manager.expire_session(session_id)