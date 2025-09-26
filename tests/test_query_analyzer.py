"""
Unit tests for Query Analyzer
"""

import unittest
from src.context.query_analyzer import QueryAnalyzer, QueryIntent, QueryComplexity


class TestQueryAnalyzer(unittest.TestCase):
    """Test cases for QueryAnalyzer"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = QueryAnalyzer()

    def test_factual_intent_classification(self):
        """Test factual query intent classification"""
        queries = [
            "What is Article 121a of the Swiss Constitution?",
            "Tell me about naturalization requirements",
            "Explain the tax code section 5"
        ]
        for query in queries:
            analysis = self.analyzer.analyze(query)
            self.assertIn(analysis.intent, [QueryIntent.FACTUAL, QueryIntent.DEFINITIONAL])

    def test_comparative_intent_classification(self):
        """Test comparative query intent classification"""
        queries = [
            "What is the difference between ordinary and simplified naturalization?",
            "Compare Article 5 and Article 7",
            "How does Swiss law differ from German law?"
        ]
        for query in queries:
            analysis = self.analyzer.analyze(query)
            self.assertEqual(analysis.intent, QueryIntent.COMPARATIVE)

    def test_procedural_intent_classification(self):
        """Test procedural query intent classification"""
        queries = [
            "How to apply for Swiss citizenship?",
            "What are the steps for filing a tax appeal?",
            "Process for registering a business"
        ]
        for query in queries:
            analysis = self.analyzer.analyze(query)
            self.assertEqual(analysis.intent, QueryIntent.PROCEDURAL)

    def test_article_entity_extraction(self):
        """Test article number extraction"""
        test_cases = [
            ("Article 121a of the Constitution", ["121a"]),
            ("Art. 5 and Article 7.2", ["5", "7.2"]),
            ("Artikel 42", ["42"]),
        ]
        for query, expected in test_cases:
            analysis = self.analyzer.analyze(query)
            self.assertTrue(analysis.has_article_reference)
            self.assertEqual(analysis.entities.get('article', []), expected)

    def test_law_entity_extraction(self):
        """Test law name extraction"""
        queries = [
            "Civil Code of Switzerland",
            "Federal Act on Foreign Nationals",
            "Tax Law"
        ]
        for query in queries:
            analysis = self.analyzer.analyze(query)
            self.assertTrue(analysis.has_law_reference)
            self.assertIn('law', analysis.entities)

    def test_date_entity_extraction(self):
        """Test date extraction"""
        test_cases = [
            ("Laws from 2020", ["2020"]),
            ("Changes on 15/03/2023", ["15/03/2023"]),
            ("1 January 2022", ["1 January 2022"])
        ]
        for query, expected in test_cases:
            analysis = self.analyzer.analyze(query)
            self.assertTrue(analysis.has_date_reference)
            self.assertEqual(analysis.entities.get('date', []), expected)

    def test_complexity_assessment(self):
        """Test query complexity assessment"""
        simple_queries = [
            "What is Article 5?",
            "Define citizenship"
        ]
        complex_queries = [
            "Compare the requirements for ordinary naturalization versus simplified "
            "naturalization including residency requirements, language requirements, "
            "and integration criteria for both federal and cantonal levels",
            "What are the differences between Articles 121a, 121b, and 122 regarding "
            "immigration law and how do they interact with EU bilateral agreements?"
        ]

        for query in simple_queries:
            analysis = self.analyzer.analyze(query)
            self.assertEqual(analysis.complexity, QueryComplexity.SIMPLE)

        for query in complex_queries:
            analysis = self.analyzer.analyze(query)
            self.assertEqual(analysis.complexity, QueryComplexity.COMPLEX)

    def test_ambiguity_detection(self):
        """Test ambiguity score calculation"""
        clear_query = "Article 121a of the Swiss Constitution"
        ambiguous_query = "Some requirements for certain types of citizenship maybe"

        clear_analysis = self.analyzer.analyze(clear_query)
        ambiguous_analysis = self.analyzer.analyze(ambiguous_query)

        self.assertLess(clear_analysis.ambiguity_score, 0.3)
        self.assertGreater(ambiguous_analysis.ambiguity_score, 0.5)

    def test_missing_context_identification(self):
        """Test identification of missing context"""
        queries_with_missing_context = [
            ("Recent changes to the law", ['time_period']),
            ("Requirements for citizenship", ['specific_type']),
            ("Tax regulations", ['jurisdiction', 'specific_type'])
        ]

        for query, expected_missing in queries_with_missing_context:
            analysis = self.analyzer.analyze(query)
            for missing in expected_missing:
                self.assertIn(missing, analysis.missing_context)

    def test_keyword_extraction(self):
        """Test keyword extraction"""
        query = "What are the requirements for Swiss naturalization?"
        analysis = self.analyzer.analyze(query)

        self.assertIn('requirements', analysis.keywords)
        self.assertIn('swiss', analysis.keywords)
        self.assertIn('naturalization', analysis.keywords)
        self.assertNotIn('the', analysis.keywords)  # Stopword should be filtered

    def test_temporal_intent(self):
        """Test temporal query intent"""
        queries = [
            "When was Article 121a introduced?",
            "Changes to the law since 2020",
            "Historical development of citizenship law"
        ]
        for query in queries:
            analysis = self.analyzer.analyze(query)
            self.assertEqual(analysis.intent, QueryIntent.TEMPORAL)

    def test_jurisdictional_intent(self):
        """Test jurisdictional query intent"""
        queries = [
            "Where does this law apply?",
            "Jurisdiction of cantonal courts",
            "Territorial scope of the regulation"
        ]
        for query in queries:
            analysis = self.analyzer.analyze(query)
            self.assertEqual(analysis.intent, QueryIntent.JURISDICTIONAL)

    def test_relationship_intent(self):
        """Test relationship query intent"""
        queries = [
            "How are Article 5 and Article 7 related?",
            "Connection between tax law and property law",
            "Dependencies between different regulations"
        ]
        for query in queries:
            analysis = self.analyzer.analyze(query)
            self.assertEqual(analysis.intent, QueryIntent.RELATIONSHIP)

    def test_confidence_scoring(self):
        """Test confidence scoring for intent classification"""
        clear_query = "What is the difference between Article 5 and Article 7?"
        vague_query = "Something about laws and stuff"

        clear_analysis = self.analyzer.analyze(clear_query)
        vague_analysis = self.analyzer.analyze(vague_query)

        self.assertGreater(clear_analysis.confidence, 0.7)
        self.assertLess(vague_analysis.confidence, 0.6)

    def test_edge_cases(self):
        """Test edge cases and empty queries"""
        edge_cases = [
            "",  # Empty query
            "???",  # Only punctuation
            "a b c",  # Very short words
            "The the the"  # Only stopwords
        ]

        for query in edge_cases:
            analysis = self.analyzer.analyze(query)
            # Should not crash and return some default analysis
            self.assertIsNotNone(analysis)
            self.assertIsInstance(analysis.intent, QueryIntent)
            self.assertIsInstance(analysis.complexity, QueryComplexity)


if __name__ == '__main__':
    unittest.main()