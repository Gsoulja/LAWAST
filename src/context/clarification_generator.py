"""
Clarification Generator - Generates clarifying questions for ambiguous queries
"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
from enum import Enum

from .query_analyzer import QueryAnalysis

logger = logging.getLogger(__name__)


class ClarificationType(Enum):
    """Types of clarifications"""
    MISSING_CONTEXT = "missing_context"
    AMBIGUOUS_TERM = "ambiguous_term"
    MULTIPLE_OPTIONS = "multiple_options"
    SCOPE_DEFINITION = "scope_definition"
    TIME_PERIOD = "time_period"
    JURISDICTION = "jurisdiction"


@dataclass
class ClarificationQuestion:
    """A clarification question with metadata"""
    question: str
    question_type: ClarificationType
    options: Optional[List[str]] = None
    context: Optional[str] = None
    priority: float = 1.0


class ClarificationGenerator:
    """Generates clarifying questions for ambiguous or incomplete queries"""

    def __init__(self, max_questions: int = 2):
        """
        Initialize the clarification generator.

        Args:
            max_questions: Maximum number of questions to generate per turn
        """
        self.max_questions = max_questions

        # Templates for common clarification types
        self.templates = {
            'citizenship_type': {
                'question': "Are you asking about naturalization, citizenship by birth, or citizenship by marriage?",
                'options': ["Naturalization", "By birth", "By marriage", "Other"]
            },
            'tax_type': {
                'question': "Which type of tax are you interested in?",
                'options': ["Income tax", "Corporate tax", "VAT", "Property tax", "Inheritance tax"]
            },
            'time_period': {
                'question': "What time period are you interested in?",
                'options': ["Current laws", "Historical laws", "Specific year", "Changes over time"]
            },
            'jurisdiction': {
                'question': "Which jurisdiction are you asking about?",
                'options': ["Federal (Switzerland)", "Cantonal", "Municipal", "International"]
            },
            'article_specificity': {
                'question': "Are you looking for a specific article or a general overview?",
                'options': ["Specific article", "General overview", "Related articles"]
            },
            'comparison_scope': {
                'question': "What aspects would you like to compare?",
                'options': ["Requirements", "Procedures", "Penalties", "Scope", "All aspects"]
            }
        }

    def generate(self,
                analysis: QueryAnalysis,
                context: Optional[Dict] = None) -> List[ClarificationQuestion]:
        """
        Generate clarification questions based on query analysis.

        Args:
            analysis: Query analysis results
            context: Optional context from previous interactions

        Returns:
            List of clarification questions (limited by max_questions)
        """
        questions = []

        # Check for missing context
        if analysis.missing_context:
            questions.extend(self._generate_context_questions(analysis))

        # Check for high ambiguity
        if analysis.ambiguity_score > 0.5:
            questions.extend(self._generate_ambiguity_questions(analysis))

        # Check for specific domain ambiguities
        questions.extend(self._generate_domain_questions(analysis))

        # Sort by priority and limit
        questions.sort(key=lambda q: -q.priority)
        limited_questions = questions[:self.max_questions]

        if limited_questions:
            logger.info(f"Generated {len(limited_questions)} clarification questions")

        return limited_questions

    def _generate_context_questions(self,
                                   analysis: QueryAnalysis) -> List[ClarificationQuestion]:
        """
        Generate questions for missing context.

        Args:
            analysis: Query analysis

        Returns:
            List of clarification questions
        """
        questions = []

        for missing in analysis.missing_context:
            if missing == 'time_period':
                questions.append(ClarificationQuestion(
                    question=self.templates['time_period']['question'],
                    question_type=ClarificationType.TIME_PERIOD,
                    options=self.templates['time_period']['options'],
                    priority=0.9
                ))
            elif missing == 'jurisdiction':
                questions.append(ClarificationQuestion(
                    question=self.templates['jurisdiction']['question'],
                    question_type=ClarificationType.JURISDICTION,
                    options=self.templates['jurisdiction']['options'],
                    priority=0.9
                ))
            elif missing == 'specific_type':
                # Determine which type based on keywords
                if any(word in analysis.query.lower()
                      for word in ['citizenship', 'naturalization', 'passport']):
                    questions.append(ClarificationQuestion(
                        question=self.templates['citizenship_type']['question'],
                        question_type=ClarificationType.SCOPE_DEFINITION,
                        options=self.templates['citizenship_type']['options'],
                        priority=1.0
                    ))
                elif any(word in analysis.query.lower() for word in ['tax', 'taxation']):
                    questions.append(ClarificationQuestion(
                        question=self.templates['tax_type']['question'],
                        question_type=ClarificationType.SCOPE_DEFINITION,
                        options=self.templates['tax_type']['options'],
                        priority=1.0
                    ))

        return questions

    def _generate_ambiguity_questions(self,
                                     analysis: QueryAnalysis) -> List[ClarificationQuestion]:
        """
        Generate questions for ambiguous terms or concepts.

        Args:
            analysis: Query analysis

        Returns:
            List of clarification questions
        """
        questions = []

        # Check for vague terms that need specification
        query_lower = analysis.query.lower()

        if 'requirements' in query_lower and not analysis.has_article_reference:
            questions.append(ClarificationQuestion(
                question="Could you specify which requirements you're interested in? "
                        "(e.g., eligibility, documentation, procedural)",
                question_type=ClarificationType.AMBIGUOUS_TERM,
                priority=0.8
            ))

        if 'changes' in query_lower or 'amendments' in query_lower:
            questions.append(ClarificationQuestion(
                question="Are you interested in recent changes, historical changes, "
                        "or proposed amendments?",
                question_type=ClarificationType.TIME_PERIOD,
                options=["Recent changes", "Historical changes", "Proposed amendments"],
                priority=0.7
            ))

        if any(word in query_lower for word in ['process', 'procedure', 'steps']):
            if not any(word in query_lower
                      for word in ['application', 'appeal', 'registration', 'filing']):
                questions.append(ClarificationQuestion(
                    question="Which specific process are you asking about?",
                    question_type=ClarificationType.SCOPE_DEFINITION,
                    priority=0.8
                ))

        return questions

    def _generate_domain_questions(self,
                                  analysis: QueryAnalysis) -> List[ClarificationQuestion]:
        """
        Generate domain-specific clarification questions.

        Args:
            analysis: Query analysis

        Returns:
            List of clarification questions
        """
        questions = []
        query_lower = analysis.query.lower()

        # Comparison queries
        if 'compare' in query_lower or 'difference' in query_lower:
            if not self.templates['comparison_scope'] in questions:
                questions.append(ClarificationQuestion(
                    question=self.templates['comparison_scope']['question'],
                    question_type=ClarificationType.SCOPE_DEFINITION,
                    options=self.templates['comparison_scope']['options'],
                    priority=0.6
                ))

        # Article queries without specific numbers
        if ('article' in query_lower or 'provision' in query_lower) and not analysis.has_article_reference:
            questions.append(ClarificationQuestion(
                question=self.templates['article_specificity']['question'],
                question_type=ClarificationType.SCOPE_DEFINITION,
                options=self.templates['article_specificity']['options'],
                priority=0.7
            ))

        # Legal domain detection
        if any(term in query_lower for term in ['law', 'legal', 'regulation', 'statute']):
            if not any(term in query_lower
                      for term in ['federal', 'cantonal', 'municipal', 'swiss']):
                # Jurisdiction might be unclear
                if 'jurisdiction' not in [q.question_type for q in questions]:
                    questions.append(ClarificationQuestion(
                        question="Are you asking about Swiss federal law, cantonal law, "
                               "or international law?",
                        question_type=ClarificationType.JURISDICTION,
                        options=["Swiss federal", "Cantonal", "International"],
                        priority=0.5
                    ))

        return questions

    def generate_followup(self,
                         original_question: ClarificationQuestion,
                         user_response: str) -> Optional[ClarificationQuestion]:
        """
        Generate a follow-up question based on user's response to clarification.

        Args:
            original_question: The original clarification question
            user_response: User's response

        Returns:
            Optional follow-up question if needed
        """
        response_lower = user_response.lower()

        # Handle citizenship follow-ups
        if original_question.question_type == ClarificationType.SCOPE_DEFINITION:
            if 'naturalization' in response_lower:
                return ClarificationQuestion(
                    question="Are you interested in ordinary naturalization or "
                            "simplified naturalization?",
                    question_type=ClarificationType.SCOPE_DEFINITION,
                    options=["Ordinary naturalization", "Simplified naturalization", "Both"],
                    priority=0.8
                )
            elif 'tax' in original_question.question and 'income' in response_lower:
                return ClarificationQuestion(
                    question="Are you asking about personal income tax or "
                            "corporate income tax?",
                    question_type=ClarificationType.SCOPE_DEFINITION,
                    options=["Personal", "Corporate", "Both"],
                    priority=0.7
                )

        # Handle time period follow-ups
        if original_question.question_type == ClarificationType.TIME_PERIOD:
            if 'specific year' in response_lower:
                return ClarificationQuestion(
                    question="Which year are you interested in?",
                    question_type=ClarificationType.TIME_PERIOD,
                    priority=0.9
                )

        return None

    def format_for_user(self, questions: List[ClarificationQuestion]) -> str:
        """
        Format clarification questions for user presentation.

        Args:
            questions: List of clarification questions

        Returns:
            Formatted string for user display
        """
        if not questions:
            return ""

        formatted = "I need some clarification to provide the most accurate information:\n\n"

        for i, q in enumerate(questions, 1):
            formatted += f"{i}. {q.question}\n"
            if q.options:
                for j, option in enumerate(q.options):
                    formatted += f"   {chr(97+j)}) {option}\n"
            formatted += "\n"

        return formatted.strip()