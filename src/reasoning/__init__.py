"""
LAWAST Reasoning Engine

Synthesizes results from multiple RAG sources, applies legal logic,
and generates transparent chain-of-thought explanations.
"""

from .models import (
    ReasoningStep,
    LegalRule,
    LegalRuleType,
    Citation,
    Contradiction,
    ReasonedAnswer,
    SynthesisResult,
    ValidationResult
)
from .engine import ReasoningEngine
from .synthesizer import ResultSynthesizer
from .legal_logic import LegalLogicEngine
from .chain_of_thought import ChainOfThoughtGenerator
from .validator import ConsistencyValidator
from .citation_tracker import CitationTracker
from .confidence_scorer import ConfidenceScorer

__version__ = "0.1.0"

__all__ = [
    "ReasoningEngine",
    "ResultSynthesizer",
    "LegalLogicEngine",
    "ChainOfThoughtGenerator",
    "ConsistencyValidator",
    "CitationTracker",
    "ConfidenceScorer",
    "ReasoningStep",
    "LegalRule",
    "LegalRuleType",
    "Citation",
    "Contradiction",
    "ReasonedAnswer",
    "SynthesisResult",
    "ValidationResult",
]