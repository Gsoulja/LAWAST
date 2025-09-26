"""
Confidence scorer for reasoning quality assessment
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .models import (
    ReasoningStep,
    Contradiction,
    ValidationResult,
    Citation
)

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """Factors contributing to confidence score"""
    source_agreement: float = 0.0  # Sources agree on facts
    citation_quality: float = 0.0  # Quality of citations
    temporal_validity: float = 0.0  # Currency of information
    coverage_completeness: float = 0.0  # How complete the answer is
    contradiction_penalty: float = 0.0  # Penalty for contradictions
    reasoning_quality: float = 0.0  # Quality of reasoning chain


class ConfidenceScorer:
    """
    Calculates confidence scores for reasoning results based on multiple factors.
    """

    def __init__(self,
                 weights: Optional[Dict[str, float]] = None):
        """
        Initialize the confidence scorer.

        Args:
            weights: Custom weights for confidence factors
        """
        self.weights = weights or {
            "source_agreement": 0.25,
            "citation_quality": 0.20,
            "temporal_validity": 0.15,
            "coverage_completeness": 0.20,
            "contradiction_penalty": 0.10,
            "reasoning_quality": 0.10
        }

    def calculate_confidence(self,
                            reasoning_steps: List[ReasoningStep],
                            evidence: List[Dict[str, Any]],
                            citations: List[Citation],
                            validation_result: Optional[ValidationResult] = None,
                            contradictions: List[Contradiction] = None) -> tuple[float, ConfidenceFactors]:
        """
        Calculate overall confidence score for the reasoning.

        Args:
            reasoning_steps: List of reasoning steps
            evidence: Evidence used in reasoning
            citations: Citations extracted
            validation_result: Validation results
            contradictions: List of contradictions

        Returns:
            Tuple of (overall confidence score 0.0-1.0, detailed factors)
        """
        factors = ConfidenceFactors()

        # Calculate source agreement score
        factors.source_agreement = self._calculate_source_agreement(evidence)

        # Calculate citation quality score
        factors.citation_quality = self._calculate_citation_quality(citations, evidence)

        # Calculate temporal validity score
        factors.temporal_validity = self._calculate_temporal_validity(evidence)

        # Calculate coverage completeness
        factors.coverage_completeness = self._calculate_coverage(reasoning_steps, evidence)

        # Calculate contradiction penalty
        factors.contradiction_penalty = self._calculate_contradiction_penalty(
            contradictions or [],
            validation_result
        )

        # Calculate reasoning quality
        factors.reasoning_quality = self._calculate_reasoning_quality(reasoning_steps)

        # Calculate weighted overall score
        overall_score = self._calculate_weighted_score(factors)

        return overall_score, factors

    def _calculate_source_agreement(self, evidence: List[Dict[str, Any]]) -> float:
        """
        Calculate how well sources agree with each other.

        Args:
            evidence: List of evidence

        Returns:
            Agreement score (0.0 to 1.0)
        """
        if len(evidence) < 2:
            # Single source, neutral confidence
            return 0.5

        # Check how many sources found each fact
        source_counts = {}
        for fact in evidence:
            methods = fact.get("methods", [])
            if len(methods) > 1:
                fact_key = fact.get("uri", fact.get("id", "unknown"))
                source_counts[fact_key] = len(methods)

        if not source_counts:
            return 0.5

        # Calculate agreement based on multi-source confirmation
        multi_source_facts = len([c for c in source_counts.values() if c > 1])
        total_facts = len(evidence)

        agreement_ratio = multi_source_facts / total_facts if total_facts > 0 else 0

        # Boost score if multiple search methods found same facts
        avg_sources = sum(source_counts.values()) / len(source_counts) if source_counts else 1
        source_diversity_bonus = min((avg_sources - 1) * 0.2, 0.3)

        return min(0.5 + agreement_ratio * 0.4 + source_diversity_bonus, 1.0)

    def _calculate_citation_quality(self,
                                   citations: List[Citation],
                                   evidence: List[Dict[str, Any]]) -> float:
        """
        Calculate quality of citations.

        Args:
            citations: List of citations
            evidence: Supporting evidence

        Returns:
            Citation quality score (0.0 to 1.0)
        """
        if not citations:
            return 0.3  # No citations is low confidence

        score = 0.5  # Base score

        # Check citation completeness (SR, article, paragraph)
        complete_citations = 0
        for citation in citations:
            completeness = sum([
                bool(citation.sr_number),
                bool(citation.article),
                bool(citation.paragraph) * 0.5,  # Paragraph is less critical
                bool(citation.subpoint) * 0.3,  # Subpoint is optional
            ]) / 2.8  # Normalize to 0-1
            complete_citations += completeness

        avg_completeness = complete_citations / len(citations) if citations else 0
        score += avg_completeness * 0.3

        # Check if citations are from primary sources (laws) vs secondary
        primary_citations = 0
        for citation in citations:
            # SR numbers starting with 1-9 are primary federal laws
            if citation.sr_number and citation.sr_number[0].isdigit():
                sr_first_digit = int(citation.sr_number[0])
                if 1 <= sr_first_digit <= 9:
                    primary_citations += 1

        primary_ratio = primary_citations / len(citations) if citations else 0
        score += primary_ratio * 0.2

        return min(score, 1.0)

    def _calculate_temporal_validity(self, evidence: List[Dict[str, Any]]) -> float:
        """
        Calculate temporal validity of information.

        Args:
            evidence: List of evidence

        Returns:
            Temporal validity score (0.0 to 1.0)
        """
        from datetime import datetime, date
        today = date.today()

        score = 0.7  # Base score
        temporal_issues = 0
        checked_facts = 0

        for fact in evidence:
            if fact.get("metadata"):
                checked_facts += 1

                # Check if in force
                in_force = fact["metadata"].get("in_force_date")
                if in_force:
                    try:
                        in_force_date = datetime.strptime(in_force, "%Y-%m-%d").date()
                        if in_force_date > today:
                            temporal_issues += 1  # Not yet in force
                    except (ValueError, TypeError):
                        pass

                # Check if repealed
                repealed = fact["metadata"].get("repeal_date")
                if repealed:
                    try:
                        repeal_date = datetime.strptime(repealed, "%Y-%m-%d").date()
                        if repeal_date <= today:
                            temporal_issues += 2  # Repealed is worse than not yet in force
                    except (ValueError, TypeError):
                        pass

                # Check last updated date for recency
                updated = fact["metadata"].get("last_updated")
                if updated:
                    try:
                        updated_date = datetime.strptime(updated, "%Y-%m-%d").date()
                        days_old = (today - updated_date).days
                        if days_old > 365:
                            score -= 0.1  # Penalty for old information
                        elif days_old < 90:
                            score += 0.1  # Bonus for recent information
                    except (ValueError, TypeError):
                        pass

        if checked_facts > 0:
            # Apply temporal issues penalty
            issue_ratio = temporal_issues / (checked_facts * 2)  # Max 2 issues per fact
            score -= issue_ratio * 0.5

        return max(0.0, min(score, 1.0))

    def _calculate_coverage(self,
                           reasoning_steps: List[ReasoningStep],
                           evidence: List[Dict[str, Any]]) -> float:
        """
        Calculate how complete the coverage is.

        Args:
            reasoning_steps: Reasoning steps
            evidence: Available evidence

        Returns:
            Coverage score (0.0 to 1.0)
        """
        score = 0.5  # Base score

        # Check if reasoning has multiple steps
        if len(reasoning_steps) < 2:
            score -= 0.2  # Too simple
        elif len(reasoning_steps) > 5:
            score += 0.1  # Comprehensive

        # Check evidence coverage
        if len(evidence) < 3:
            score -= 0.1  # Limited evidence
        elif len(evidence) > 10:
            score += 0.2  # Extensive evidence

        # Check if reasoning uses evidence
        evidence_used = set()
        for step in reasoning_steps:
            if hasattr(step, "evidence"):
                for fact in step.evidence:
                    evidence_used.add(fact.get("id", fact.get("uri", "")))

        if evidence:
            usage_ratio = len(evidence_used) / len(evidence)
            score += usage_ratio * 0.2

        # Check for final conclusion
        has_conclusion = any(
            step.description.lower() in ["conclusion", "final answer", "final conclusion"]
            for step in reasoning_steps
        )
        if has_conclusion:
            score += 0.1

        return max(0.0, min(score, 1.0))

    def _calculate_contradiction_penalty(self,
                                        contradictions: List[Contradiction],
                                        validation_result: Optional[ValidationResult]) -> float:
        """
        Calculate penalty for contradictions.

        Args:
            contradictions: List of contradictions
            validation_result: Validation results

        Returns:
            Contradiction penalty (0.0 to 1.0, higher is better)
        """
        score = 1.0  # Start with no penalty

        # Direct contradictions
        for contradiction in contradictions:
            score -= contradiction.confidence_impact  # Use impact from contradiction

        # Validation issues
        if validation_result:
            if not validation_result.is_consistent:
                score -= 0.2
            # Use validation consistency score
            score = score * 0.5 + validation_result.consistency_score * 0.5

        return max(0.0, min(score, 1.0))

    def _calculate_reasoning_quality(self, reasoning_steps: List[ReasoningStep]) -> float:
        """
        Calculate quality of reasoning chain.

        Args:
            reasoning_steps: List of reasoning steps

        Returns:
            Reasoning quality score (0.0 to 1.0)
        """
        if not reasoning_steps:
            return 0.0

        # Average confidence of all steps
        step_confidences = [step.confidence for step in reasoning_steps if hasattr(step, "confidence")]
        avg_confidence = sum(step_confidences) / len(step_confidences) if step_confidences else 0.5

        # Check logical progression
        has_evidence = sum(1 for step in reasoning_steps if step.evidence) / len(reasoning_steps)
        has_conclusions = sum(1 for step in reasoning_steps if step.conclusion) / len(reasoning_steps)

        # Check for legal logic application
        has_legal_logic = any(
            hasattr(step, "logic_applied") and step.logic_applied
            for step in reasoning_steps
        )

        score = (
            avg_confidence * 0.4 +
            has_evidence * 0.3 +
            has_conclusions * 0.2 +
            (0.1 if has_legal_logic else 0.0)
        )

        return max(0.0, min(score, 1.0))

    def _calculate_weighted_score(self, factors: ConfidenceFactors) -> float:
        """
        Calculate weighted overall score from factors.

        Args:
            factors: Confidence factors

        Returns:
            Weighted score (0.0 to 1.0)
        """
        score = (
            factors.source_agreement * self.weights["source_agreement"] +
            factors.citation_quality * self.weights["citation_quality"] +
            factors.temporal_validity * self.weights["temporal_validity"] +
            factors.coverage_completeness * self.weights["coverage_completeness"] +
            factors.contradiction_penalty * self.weights["contradiction_penalty"] +
            factors.reasoning_quality * self.weights["reasoning_quality"]
        )

        return max(0.0, min(score, 1.0))

    def get_confidence_level(self, score: float) -> str:
        """
        Get human-readable confidence level.

        Args:
            score: Confidence score (0.0 to 1.0)

        Returns:
            Confidence level string
        """
        if score >= 0.9:
            return "Very High"
        elif score >= 0.75:
            return "High"
        elif score >= 0.6:
            return "Moderate"
        elif score >= 0.4:
            return "Low"
        else:
            return "Very Low"

    def explain_confidence(self, score: float, factors: ConfidenceFactors) -> str:
        """
        Generate explanation for confidence score.

        Args:
            score: Overall score
            factors: Detailed factors

        Returns:
            Human-readable explanation
        """
        level = self.get_confidence_level(score)
        explanation = [f"Confidence Level: {level} ({score:.1%})"]

        # Explain main factors
        if factors.source_agreement > 0.7:
            explanation.append("✓ Multiple sources confirm the information")
        elif factors.source_agreement < 0.5:
            explanation.append("⚠ Limited source agreement")

        if factors.citation_quality > 0.7:
            explanation.append("✓ High-quality primary source citations")
        elif factors.citation_quality < 0.5:
            explanation.append("⚠ Citations lack detail or primary sources")

        if factors.temporal_validity > 0.8:
            explanation.append("✓ Information is current and valid")
        elif factors.temporal_validity < 0.6:
            explanation.append("⚠ Some information may be outdated")

        if factors.contradiction_penalty < 0.8:
            explanation.append("⚠ Contradictions detected and resolved")

        if factors.coverage_completeness > 0.7:
            explanation.append("✓ Comprehensive coverage of the topic")
        elif factors.coverage_completeness < 0.5:
            explanation.append("⚠ Limited evidence coverage")

        return "\n".join(explanation)