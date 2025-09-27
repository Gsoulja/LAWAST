"""
Data models for the reasoning engine
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class LegalRuleType(Enum):
    """Types of legal reasoning rules"""
    HIERARCHY = "hierarchy"      # Constitution > Law > Ordinance
    TEMPORAL = "temporal"         # Newer overrides older
    SPECIFICITY = "specificity"   # Specific overrides general
    SCOPE = "scope"               # Federal vs Cantonal
    VALIDITY = "validity"         # In force vs repealed


@dataclass
class Citation:
    """Represents a legal citation"""
    sr_number: Optional[str] = None
    article: Optional[str] = None
    paragraph: Optional[str] = None
    subpoint: Optional[str] = None
    ast_path: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None  # Raw source reference
    reference: Optional[str] = None  # Formatted reference
    relevance: Optional[float] = None  # Relevance score
    law_abbreviation: Optional[str] = None  # Cached law abbreviation (BV, OR, DSG, etc.)

    def __str__(self) -> str:
        """Format citation as string"""
        # Use formatted reference if available
        if self.reference:
            return self.reference

        # Use source if available and looks like a citation with law abbreviation
        if self.source and ("Art." in self.source or "SR" in self.source):
            # Check if source already contains law abbreviation
            if any(abbrev in self.source for abbrev in ["BV", "OR", "DSG", "ZGB", "StGB"]):
                return self.source

        # Build from components with law abbreviation
        if self.article:
            # Use law abbreviation if available
            if self.law_abbreviation:
                if self.paragraph:
                    return f"Art. {self.article} Abs. {self.paragraph} {self.law_abbreviation}"
                else:
                    return f"Art. {self.article} {self.law_abbreviation}"

            # Try to get law abbreviation from SR number
            elif self.sr_number:
                # Import here to avoid circular dependency
                from ..reasoning.citation_tracker import CitationTracker
                tracker = CitationTracker()
                law_abbrev = tracker.get_law_abbreviation(self.sr_number)
                if law_abbrev:
                    if self.paragraph:
                        return f"Art. {self.article} Abs. {self.paragraph} {law_abbrev}"
                    else:
                        return f"Art. {self.article} {law_abbrev}"

        # Build from SR number if no law abbreviation found
        if self.sr_number:
            parts = [f"SR {self.sr_number}"]
            if self.article:
                parts.append(f"Art. {self.article}")
            if self.paragraph:
                parts.append(f"Para. {self.paragraph}")
            if self.subpoint:
                parts.append(f"lit. {self.subpoint}")
            return " ".join(parts)

        # Use article alone if no SR number or law abbreviation
        if self.article:
            # Always default to BV for articles (since we're processing BV)
            return f"Art. {self.article} BV"

        # Use title as fallback
        if self.title:
            return self.title

        # Last resort - use source
        if self.source:
            return self.source

        return "Unknown citation"

    def format_for_challenge(self) -> str:
        """Format citation for Swiss Law RAG Challenge compliance"""
        # If we have a law abbreviation cached, use it
        if self.law_abbreviation and self.article:
            if self.paragraph:
                return f"Art. {self.article} Abs. {self.paragraph} {self.law_abbreviation}"
            else:
                return f"Art. {self.article} {self.law_abbreviation}"

        # Try to extract from SR number if available
        if self.sr_number and self.article:
            # Import here to avoid circular dependency
            from ..reasoning.citation_tracker import CitationTracker
            tracker = CitationTracker()
            law_abbrev = tracker.get_law_abbreviation(self.sr_number)
            if law_abbrev:
                self.law_abbreviation = law_abbrev  # Cache it
                if self.paragraph:
                    return f"Art. {self.article} Abs. {self.paragraph} {law_abbrev}"
                else:
                    return f"Art. {self.article} {law_abbrev}"

        # Fallback to standard format
        return str(self)


@dataclass
class ReasoningStep:
    """Individual step in chain-of-thought reasoning"""
    step_number: int
    description: str
    evidence: List[Dict[str, Any]]  # Raw evidence used
    logic_applied: Optional[str] = None  # Legal rule or logical inference
    conclusion: str = ""
    citations: List[Citation] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "step": self.step_number,
            "description": self.description,
            "evidence_count": len(self.evidence),
            "logic": self.logic_applied,
            "conclusion": self.conclusion,
            "citations": [str(c) for c in self.citations],
            "confidence": self.confidence
        }


@dataclass
class LegalRule:
    """Represents a legal logic rule application"""
    rule_type: LegalRuleType
    description: str
    input_facts: List[Dict[str, Any]]
    output_conclusion: str
    confidence: float = 1.0

    def apply(self) -> str:
        """Apply the legal rule and return conclusion"""
        return self.output_conclusion


@dataclass
class Contradiction:
    """Represents conflicting information from different sources"""
    fact_type: str  # What kind of information conflicts
    source1: Dict[str, Any]  # First source info
    source2: Dict[str, Any]  # Second source info
    resolution_strategy: str  # How it was resolved
    resolved_value: Any  # Final resolved value
    confidence_impact: float = 0.0  # How much it affects confidence


@dataclass
class SynthesisResult:
    """Result from multi-source synthesis"""
    unified_facts: List[Dict[str, Any]]  # Deduplicated, merged facts
    complementary_info: List[Dict[str, Any]]  # Additional context
    contradictions: List[Contradiction] = field(default_factory=list)
    source_mapping: Dict[str, List[str]] = field(default_factory=dict)  # fact_id -> source_ids
    reliability_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result from consistency validation"""
    is_consistent: bool
    consistency_score: float  # 0.0 to 1.0
    contradictions: List[Contradiction] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)  # Areas of uncertainty
    validation_notes: List[str] = field(default_factory=list)


@dataclass
class ReasonedAnswer:
    """Final output from reasoning engine"""
    # Core answer
    answer: str
    confidence: float  # Overall confidence score (0.0-1.0)

    # Reasoning details
    reasoning_steps: List[ReasoningStep]
    legal_rules_applied: List[LegalRule]

    # Evidence and citations
    evidence_used: List[Dict[str, Any]]
    citations: List[Citation]

    # Validation results
    validation_result: Optional[ValidationResult] = None
    contradictions: List[Contradiction] = field(default_factory=list)

    # Metadata
    query: str = ""
    processing_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "reasoning_steps": [step.to_dict() for step in self.reasoning_steps],
            "legal_rules": len(self.legal_rules_applied),
            "citations": [str(c) for c in self.citations],
            "contradictions": len(self.contradictions),
            "query": self.query,
            "timestamp": self.timestamp.isoformat()
        }

    def get_explanation(self) -> str:
        """Generate human-readable explanation"""
        explanation = []
        explanation.append(f"Answer: {self.answer}\n")
        explanation.append(f"Confidence: {self.confidence:.2%}\n")

        if self.reasoning_steps:
            explanation.append("\nReasoning Steps:")
            for step in self.reasoning_steps:
                explanation.append(f"  {step.step_number}. {step.description}")
                if step.conclusion:
                    explanation.append(f"     → {step.conclusion}")

        if self.citations:
            explanation.append("\nSources:")
            for citation in self.citations[:5]:  # Limit to 5 for readability
                explanation.append(f"  - {citation}")

        if self.contradictions:
            explanation.append(f"\nNote: {len(self.contradictions)} contradictions resolved")

        return "\n".join(explanation)