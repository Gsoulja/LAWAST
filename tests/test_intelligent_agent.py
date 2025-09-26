"""
Integration tests for Intelligent Agent System
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from src.context import (
    IntelligentAgent,
    QueryAnalyzer,
    StrategyPlanner,
    ClarificationGenerator,
    SessionManager,
    ContextTree
)
from src.context.query_analyzer import QueryIntent, QueryComplexity
from src.context.strategy_planner import RAGStrategy


class TestIntelligentAgent(unittest.TestCase):
    """Integration tests for the Intelligent Agent System"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temp directory for sessions
        self.temp_dir = tempfile.mkdtemp()

        # Create mock Triple RAG
        self.mock_triple_rag = Mock()
        self.mock_triple_rag.search.return_value = ([], Mock())

        # Create session manager with temp directory
        self.session_manager = SessionManager(storage_path=self.temp_dir)

        # Create agent
        self.agent = IntelligentAgent(
            triple_rag=self.mock_triple_rag,
            session_manager=self.session_manager
        )

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_simple_query_flow(self):
        """Test processing a simple query"""
        query = "What is Article 121a of the Swiss Constitution?"

        response = self.agent.process_query(query)

        self.assertIsNotNone(response)
        self.assertFalse(response.clarification_needed)
        self.assertIsNotNone(response.session_id)
        self.assertEqual(response.strategy_used, RAGStrategy.AST.value)

    def test_ambiguous_query_clarification(self):
        """Test that ambiguous queries trigger clarification"""
        query = "What are the requirements for citizenship?"

        response = self.agent.process_query(query)

        self.assertTrue(response.clarification_needed)
        self.assertIsNotNone(response.clarifications)
        self.assertGreater(len(response.clarifications), 0)
        # Check that citizenship type clarification is requested
        self.assertIn("naturalization", response.response.lower())

    def test_clarification_response_flow(self):
        """Test processing clarification responses"""
        # First query needing clarification
        query = "What are the requirements for citizenship?"
        response1 = self.agent.process_query(query)
        session_id = response1.session_id

        self.assertTrue(response1.clarification_needed)

        # Process clarification response
        response2 = self.agent.process_clarification_response(
            session_id=session_id,
            clarification_response="Naturalization",
            original_query=query
        )

        self.assertFalse(response2.clarification_needed)
        self.assertEqual(response2.session_id, session_id)

    def test_session_persistence(self):
        """Test that sessions are persisted correctly"""
        query1 = "What is Article 5?"
        response1 = self.agent.process_query(query1)
        session_id = response1.session_id

        # Process another query in same session
        query2 = "What about Article 7?"
        response2 = self.agent.process_query(query2, session_id=session_id)

        self.assertEqual(response2.session_id, session_id)

        # Check session history
        history = self.session_manager.get_session_history(session_id)
        self.assertEqual(len(history), 4)  # 2 queries + 2 responses

    def test_strategy_selection_for_intents(self):
        """Test that correct strategies are selected for different intents"""
        test_cases = [
            ("What is Article 121a?", RAGStrategy.AST),
            ("Compare Article 5 and Article 7", RAGStrategy.GRAPH),
            ("How to apply for citizenship?", RAGStrategy.VECTOR),
            ("Overview of Swiss tax law", RAGStrategy.HYBRID),
        ]

        for query, expected_strategy in test_cases:
            response = self.agent.process_query(query, force_new_session=True)
            # Strategy might be adjusted, but should be in the same family
            self.assertIn(expected_strategy.value, response.strategy_used)

    def test_context_tree_building(self):
        """Test that context tree is built correctly"""
        session = self.session_manager.create_session()
        session_id = session.session_id

        # Process multiple queries
        queries = [
            "What is citizenship?",
            "Naturalization",  # Clarification response
            "What are the requirements?"
        ]

        for query in queries:
            self.agent.process_query(query, session_id=session_id)

        # Check context tree
        session = self.session_manager.get_session(session_id)
        self.assertIsNotNone(session.context_tree)
        self.assertGreater(session.context_tree.turn_count, 0)

        summary = session.context_tree.get_summary()
        self.assertIn('topics', summary)
        self.assertIn('constraints', summary)

    def test_session_timeout(self):
        """Test session timeout handling"""
        # Create session
        session = self.session_manager.create_session()
        session_id = session.session_id

        # Manually expire it
        self.session_manager.expire_session(session_id)

        # Try to use expired session
        response = self.agent.process_query("Test query", session_id=session_id)

        # Should get new session
        self.assertNotEqual(response.session_id, session_id)

    def test_complex_multi_turn_dialogue(self):
        """Test complex multi-turn dialogue"""
        session_id = None

        dialogue = [
            ("Tell me about Swiss citizenship", True),  # Should need clarification
            ("Naturalization", False),
            ("What are the requirements?", False),
            ("How long does it take?", False),
            ("What about the language requirements?", False)
        ]

        for query, expects_clarification in dialogue:
            if session_id:
                response = self.agent.process_query(query, session_id=session_id)
            else:
                response = self.agent.process_query(query)
                session_id = response.session_id

            if expects_clarification:
                self.assertTrue(response.clarification_needed)

        # Check final session state
        session = self.session_manager.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertGreater(len(session.history), 5)

    def test_query_analyzer_integration(self):
        """Test query analyzer component integration"""
        analyzer = self.agent.query_analyzer

        query = "Compare Article 5 and Article 7 of the Civil Code"
        analysis = analyzer.analyze(query)

        self.assertEqual(analysis.intent, QueryIntent.COMPARATIVE)
        self.assertTrue(analysis.has_article_reference)
        self.assertIn('5', analysis.entities['article'])
        self.assertIn('7', analysis.entities['article'])

    def test_strategy_planner_integration(self):
        """Test strategy planner component integration"""
        analyzer = self.agent.query_analyzer
        planner = self.agent.strategy_planner

        query = "Article 121a requirements"
        analysis = analyzer.analyze(query)
        strategy = planner.plan(analysis)

        self.assertEqual(strategy.primary_strategy, RAGStrategy.AST)
        self.assertGreater(strategy.confidence, 0.5)

    def test_clarification_generator_integration(self):
        """Test clarification generator component integration"""
        analyzer = self.agent.query_analyzer
        generator = self.agent.clarification_generator

        query = "What are the requirements?"
        analysis = analyzer.analyze(query)
        clarifications = generator.generate(analysis)

        self.assertGreater(len(clarifications), 0)
        self.assertLessEqual(len(clarifications), 2)  # Max 2 questions

    def test_error_handling(self):
        """Test error handling in agent"""
        # Mock Triple RAG to raise exception
        self.mock_triple_rag.search.side_effect = Exception("RAG error")

        # Should handle gracefully
        response = self.agent.process_query("Test query")
        self.assertIsNotNone(response)

    def test_fallback_strategy(self):
        """Test fallback strategy when primary fails"""
        # Mock Triple RAG to return empty for first call
        self.mock_triple_rag.search.side_effect = [
            ([], Mock()),  # First call returns empty
            ([Mock()], Mock())  # Fallback returns results
        ]

        response = self.agent.process_query("Complex query about multiple laws")
        self.assertIsNotNone(response)
        # Should have tried fallback
        self.assertEqual(self.mock_triple_rag.search.call_count, 2)


if __name__ == '__main__':
    unittest.main()