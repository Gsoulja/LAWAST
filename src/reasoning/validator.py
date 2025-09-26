"""
Consistency validator for reasoning engine
"""

import logging
from typing import List, Dict, Any, Set, Tuple, Optional
from difflib import SequenceMatcher

from .models import ValidationResult, Contradiction

logger = logging.getLogger(__name__)


class ConsistencyValidator:
    """
    Validates consistency across multiple sources and detects contradictions.
    """

    def __init__(self, strict_mode: bool = False):
        """
        Initialize the consistency validator.

        Args:
            strict_mode: If True, more aggressive contradiction detection
        """
        self.strict_mode = strict_mode

    def validate_consistency(self,
                            evidence: List[Dict[str, Any]],
                            reasoning_steps: List[Any] = None) -> ValidationResult:
        """
        Validate consistency across evidence and reasoning.

        Args:
            evidence: List of evidence facts
            reasoning_steps: Optional reasoning steps to validate

        Returns:
            ValidationResult with consistency assessment
        """
        contradictions = []
        uncertainties = []
        validation_notes = []

        # Check for contradictions in evidence
        evidence_contradictions = self._detect_evidence_contradictions(evidence)
        contradictions.extend(evidence_contradictions)

        # Check for temporal inconsistencies
        temporal_issues = self._check_temporal_consistency(evidence)
        if temporal_issues:
            uncertainties.extend(temporal_issues)
            validation_notes.append("Temporal inconsistencies detected")

        # Check for missing critical information
        missing_info = self._check_completeness(evidence)
        if missing_info:
            uncertainties.extend(missing_info)
            validation_notes.append("Some information may be incomplete")

        # Validate reasoning steps if provided
        if reasoning_steps:
            reasoning_issues = self._validate_reasoning_consistency(reasoning_steps, evidence)
            if reasoning_issues:
                uncertainties.extend(reasoning_issues)
                validation_notes.append("Reasoning validation warnings")

        # Calculate consistency score
        consistency_score = self._calculate_consistency_score(
            len(contradictions),
            len(uncertainties),
            len(evidence)
        )

        # Determine if overall consistent
        is_consistent = len(contradictions) == 0 or (
            not self.strict_mode and consistency_score >= 0.7
        )

        return ValidationResult(
            is_consistent=is_consistent,
            consistency_score=consistency_score,
            contradictions=contradictions,
            uncertainties=uncertainties,
            validation_notes=validation_notes
        )

    def detect_contradictions(self, facts: List[Dict[str, Any]]) -> List[Contradiction]:
        """
        Detect contradictions in a list of facts.

        Args:
            facts: List of facts to check

        Returns:
            List of detected contradictions
        """
        return self._detect_evidence_contradictions(facts)

    def _detect_evidence_contradictions(self,
                                       evidence: List[Dict[str, Any]]) -> List[Contradiction]:
        """Detect contradictions in evidence"""
        contradictions = []

        # Group evidence by similar topics/articles
        groups = self._group_by_similarity(evidence)

        for group in groups.values():
            if len(group) < 2:
                continue

            # Check each pair in the group
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    contradiction = self._check_pair_contradiction(group[i], group[j])
                    if contradiction:
                        contradictions.append(contradiction)

        return contradictions

    def _group_by_similarity(self, evidence: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Group evidence by similar URIs or content"""
        groups = {}

        for fact in evidence:
            # Try to extract article/law reference
            uri = fact.get("uri", "")
            key = self._extract_grouping_key(uri)

            if key not in groups:
                groups[key] = []
            groups[key].append(fact)

        return groups

    def _extract_grouping_key(self, uri: str) -> str:
        """Extract a grouping key from URI"""
        import re

        # Try to extract SR number and article
        sr_pattern = r'SR\s*(\d{3}(?:\.\d+)*)'
        art_pattern = r'[Aa]rt(?:icle)?\.?\s*(\d+)'

        sr_match = re.search(sr_pattern, uri)
        art_match = re.search(art_pattern, uri)

        if sr_match and art_match:
            return f"{sr_match.group(1)}_art_{art_match.group(1)}"
        elif sr_match:
            return sr_match.group(1)
        else:
            # Use first 20 chars of URI as key
            return uri[:20]

    def _check_pair_contradiction(self,
                                  fact1: Dict[str, Any],
                                  fact2: Dict[str, Any]) -> Optional[Contradiction]:
        """Check if two facts contradict each other"""
        # Check for different content for same article
        if fact1.get("uri") == fact2.get("uri"):
            if fact1.get("content") != fact2.get("content"):
                return Contradiction(
                    fact_type="content_mismatch",
                    source1=fact1,
                    source2=fact2,
                    resolution_strategy="prefer_higher_score",
                    resolved_value=fact1 if fact1.get("score", 0) > fact2.get("score", 0) else fact2,
                    confidence_impact=-0.15
                )

        # Check for conflicting dates
        if fact1.get("metadata") and fact2.get("metadata"):
            date1 = fact1["metadata"].get("in_force_date")
            date2 = fact2["metadata"].get("in_force_date")

            if date1 and date2 and date1 != date2:
                # Same provision, different dates = version conflict
                if self._is_same_provision(fact1, fact2):
                    return Contradiction(
                        fact_type="version_conflict",
                        source1=fact1,
                        source2=fact2,
                        resolution_strategy="use_latest_version",
                        resolved_value=fact1 if date1 > date2 else fact2,
                        confidence_impact=-0.1
                    )

        # Check for conflicting legal interpretations
        if self.strict_mode:
            content_contradiction = self._check_content_contradiction(fact1, fact2)
            if content_contradiction:
                return content_contradiction

        return None

    def _is_same_provision(self, fact1: Dict[str, Any], fact2: Dict[str, Any]) -> bool:
        """Check if two facts refer to the same legal provision"""
        # Compare URIs
        uri1 = fact1.get("uri", "")
        uri2 = fact2.get("uri", "")

        if uri1 and uri2:
            # Remove version/date suffixes
            base_uri1 = uri1.split("?")[0].split("#")[0]
            base_uri2 = uri2.split("?")[0].split("#")[0]
            return base_uri1 == base_uri2

        return False

    def _check_content_contradiction(self,
                                    fact1: Dict[str, Any],
                                    fact2: Dict[str, Any]) -> Optional[Contradiction]:
        """Check for semantic contradictions in content"""
        content1 = fact1.get("content", "").lower()
        content2 = fact2.get("content", "").lower()

        if not content1 or not content2:
            return None

        # Check for opposite terms
        opposites = [
            ("erlaubt", "verboten"),
            ("allowed", "prohibited"),
            ("permis", "interdit"),
            ("darf", "darf nicht"),
            ("must", "must not"),
            ("obligatory", "optional")
        ]

        for term1, term2 in opposites:
            if (term1 in content1 and term2 in content2) or (term2 in content1 and term1 in content2):
                return Contradiction(
                    fact_type="semantic_opposition",
                    source1=fact1,
                    source2=fact2,
                    resolution_strategy="requires_legal_interpretation",
                    resolved_value=None,
                    confidence_impact=-0.2
                )

        return None

    def _check_temporal_consistency(self, evidence: List[Dict[str, Any]]) -> List[str]:
        """Check for temporal inconsistencies"""
        issues = []

        from datetime import datetime, date
        today = date.today()

        for fact in evidence:
            if fact.get("metadata"):
                # Check if provision is not yet in force
                in_force = fact["metadata"].get("in_force_date")
                if in_force:
                    try:
                        in_force_date = datetime.strptime(in_force, "%Y-%m-%d").date()
                        if in_force_date > today:
                            issues.append(
                                f"Provision {fact.get('uri', 'unknown')} not yet in force (starts {in_force})"
                            )
                    except (ValueError, TypeError):
                        pass

                # Check if provision is repealed
                repealed = fact["metadata"].get("repeal_date")
                if repealed:
                    try:
                        repeal_date = datetime.strptime(repealed, "%Y-%m-%d").date()
                        if repeal_date <= today:
                            issues.append(
                                f"Provision {fact.get('uri', 'unknown')} has been repealed (since {repealed})"
                            )
                    except (ValueError, TypeError):
                        pass

        return issues

    def _check_completeness(self, evidence: List[Dict[str, Any]]) -> List[str]:
        """Check for missing critical information"""
        issues = []

        # Check if we have enough evidence
        if len(evidence) < 2:
            issues.append("Limited evidence available - answer may be incomplete")

        # Check for missing content
        empty_content = [e for e in evidence if not e.get("content")]
        if len(empty_content) > len(evidence) * 0.5:
            issues.append("Many provisions lack detailed content")

        # Check source diversity
        methods = set()
        for fact in evidence:
            if fact.get("methods"):
                methods.update(fact["methods"])

        if len(methods) < 2:
            issues.append("Evidence from limited search methods - may miss relevant provisions")

        return issues

    def _validate_reasoning_consistency(self,
                                       reasoning_steps: List[Any],
                                       evidence: List[Dict[str, Any]]) -> List[str]:
        """Validate reasoning steps against evidence"""
        issues = []

        evidence_ids = {e.get("id") for e in evidence}

        for step in reasoning_steps:
            # Check if step references valid evidence
            if hasattr(step, "evidence"):
                for ref in step.evidence:
                    if ref.get("id") not in evidence_ids:
                        issues.append(
                            f"Step {step.step_number} references unverified evidence"
                        )

            # Check if conclusions are supported
            if hasattr(step, "conclusion") and hasattr(step, "confidence"):
                if step.confidence < 0.5 and step.conclusion:
                    issues.append(
                        f"Step {step.step_number} has low confidence conclusion"
                    )

        return issues

    def _calculate_consistency_score(self,
                                    num_contradictions: int,
                                    num_uncertainties: int,
                                    num_evidence: int) -> float:
        """Calculate overall consistency score"""
        if num_evidence == 0:
            return 0.0

        # Base score
        score = 1.0

        # Penalty for contradictions (heavy)
        score -= num_contradictions * 0.2

        # Penalty for uncertainties (lighter)
        score -= num_uncertainties * 0.05

        # Bonus for more evidence (up to 0.1)
        evidence_bonus = min(num_evidence * 0.02, 0.1)
        score += evidence_bonus

        return max(0.0, min(1.0, score))