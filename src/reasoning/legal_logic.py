"""
Legal logic engine for Swiss law reasoning
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from enum import Enum

from .models import LegalRule, LegalRuleType

logger = logging.getLogger(__name__)


class LegalHierarchy(Enum):
    """Swiss legal hierarchy levels"""
    CONSTITUTION = 5      # Bundesverfassung (BV)
    FEDERAL_LAW = 4      # Bundesgesetz (BG)
    ORDINANCE = 3        # Verordnung (VO)
    CANTONAL_LAW = 2     # Kantonales Gesetz
    MUNICIPAL_REG = 1    # Gemeindeverordnung


class LegalLogicEngine:
    """
    Applies Swiss legal reasoning rules to determine applicable law.
    Handles hierarchy, temporal, specificity, and scope rules.
    """

    def __init__(self):
        """Initialize the legal logic engine"""
        self.hierarchy_map = {
            "Constitution": LegalHierarchy.CONSTITUTION,
            "BV": LegalHierarchy.CONSTITUTION,
            "Law": LegalHierarchy.FEDERAL_LAW,
            "BG": LegalHierarchy.FEDERAL_LAW,
            "Gesetz": LegalHierarchy.FEDERAL_LAW,
            "Ordinance": LegalHierarchy.ORDINANCE,
            "VO": LegalHierarchy.ORDINANCE,
            "Verordnung": LegalHierarchy.ORDINANCE,
            "Cantonal": LegalHierarchy.CANTONAL_LAW,
            "Municipal": LegalHierarchy.MUNICIPAL_REG
        }

    def apply_legal_rules(self, facts: List[Dict[str, Any]]) -> List[LegalRule]:
        """
        Apply all relevant legal rules to the facts.

        Args:
            facts: List of legal facts to analyze

        Returns:
            List of applied legal rules with conclusions
        """
        rules_applied = []

        # Apply hierarchy rules if multiple levels present
        if self._has_hierarchy_conflict(facts):
            rule = self.apply_hierarchy_rule(facts)
            if rule:
                rules_applied.append(rule)

        # Apply temporal rules if multiple versions
        if self._has_temporal_conflict(facts):
            rule = self.apply_temporal_rule(facts)
            if rule:
                rules_applied.append(rule)

        # Apply specificity rules if general vs specific
        if self._has_specificity_conflict(facts):
            rule = self.apply_specificity_rule(facts)
            if rule:
                rules_applied.append(rule)

        # Apply scope rules if federal vs cantonal
        if self._has_scope_conflict(facts):
            rule = self.apply_scope_rule(facts)
            if rule:
                rules_applied.append(rule)

        # Check validity of all facts
        validity_rule = self.apply_validity_rule(facts)
        if validity_rule:
            rules_applied.append(validity_rule)

        return rules_applied

    def apply_hierarchy_rule(self, facts: List[Dict[str, Any]]) -> Optional[LegalRule]:
        """
        Apply hierarchy rule: Constitution > Federal Law > Ordinance > Cantonal > Municipal

        Args:
            facts: Facts to evaluate

        Returns:
            LegalRule with hierarchy resolution
        """
        # Determine hierarchy level for each fact
        fact_levels = []
        for fact in facts:
            level = self._determine_hierarchy_level(fact)
            if level:
                fact_levels.append((fact, level))

        if not fact_levels:
            return None

        # Sort by hierarchy (highest first)
        fact_levels.sort(key=lambda x: x[1].value, reverse=True)

        highest_fact = fact_levels[0][0]
        highest_level = fact_levels[0][1]

        # Check if there are conflicts
        conflicts = [f for f, l in fact_levels[1:] if l != highest_level]

        if conflicts:
            return LegalRule(
                rule_type=LegalRuleType.HIERARCHY,
                description=f"{highest_level.name} takes precedence over lower hierarchy levels",
                input_facts=facts,
                output_conclusion=f"Apply {highest_fact.get('uri', 'highest level provision')} "
                                 f"({highest_level.name})",
                confidence=0.95
            )

        return None

    def apply_temporal_rule(self, facts: List[Dict[str, Any]]) -> Optional[LegalRule]:
        """
        Apply temporal rule: Newer law overrides older law (lex posterior)

        Args:
            facts: Facts to evaluate

        Returns:
            LegalRule with temporal resolution
        """
        # Extract facts with dates
        dated_facts = []
        for fact in facts:
            if fact.get("metadata"):
                in_force_date = fact["metadata"].get("in_force_date")
                if in_force_date:
                    try:
                        # Parse date string
                        if isinstance(in_force_date, str):
                            date_obj = datetime.strptime(in_force_date, "%Y-%m-%d").date()
                        else:
                            date_obj = in_force_date
                        dated_facts.append((fact, date_obj))
                    except (ValueError, TypeError):
                        continue

        if len(dated_facts) < 2:
            return None

        # Sort by date (newest first)
        dated_facts.sort(key=lambda x: x[1], reverse=True)

        newest_fact = dated_facts[0][0]
        newest_date = dated_facts[0][1]

        # Check if newest is currently in force
        today = date.today()
        if newest_date <= today:
            return LegalRule(
                rule_type=LegalRuleType.TEMPORAL,
                description="Newer provision overrides older (lex posterior derogat legi priori)",
                input_facts=facts,
                output_conclusion=f"Apply {newest_fact.get('uri', 'newest provision')} "
                                 f"(in force since {newest_date})",
                confidence=0.9
            )

        return None

    def apply_specificity_rule(self, facts: List[Dict[str, Any]]) -> Optional[LegalRule]:
        """
        Apply specificity rule: Specific provision overrides general (lex specialis)

        Args:
            facts: Facts to evaluate

        Returns:
            LegalRule with specificity resolution
        """
        # Determine specificity based on scope indicators
        specificity_scores = []

        for fact in facts:
            score = self._calculate_specificity_score(fact)
            specificity_scores.append((fact, score))

        if not specificity_scores:
            return None

        # Sort by specificity (highest first)
        specificity_scores.sort(key=lambda x: x[1], reverse=True)

        most_specific = specificity_scores[0][0]
        highest_score = specificity_scores[0][1]

        # Check if there's a meaningful difference
        if len(specificity_scores) > 1:
            second_score = specificity_scores[1][1]
            if highest_score > second_score:
                return LegalRule(
                    rule_type=LegalRuleType.SPECIFICITY,
                    description="Specific provision overrides general (lex specialis derogat legi generali)",
                    input_facts=facts,
                    output_conclusion=f"Apply {most_specific.get('uri', 'most specific provision')} "
                                     f"(specificity score: {highest_score:.2f})",
                    confidence=0.85
                )

        return None

    def apply_scope_rule(self, facts: List[Dict[str, Any]]) -> Optional[LegalRule]:
        """
        Apply scope rule: Federal vs Cantonal jurisdiction

        Args:
            facts: Facts to evaluate

        Returns:
            LegalRule with scope resolution
        """
        federal_facts = []
        cantonal_facts = []

        for fact in facts:
            scope = self._determine_scope(fact)
            if scope == "federal":
                federal_facts.append(fact)
            elif scope == "cantonal":
                cantonal_facts.append(fact)

        if federal_facts and cantonal_facts:
            # Check if it's a matter of federal competence
            federal_matter = self._is_federal_matter(facts)

            if federal_matter:
                return LegalRule(
                    rule_type=LegalRuleType.SCOPE,
                    description="Federal law applies in matters of federal competence",
                    input_facts=facts,
                    output_conclusion=f"Apply federal provision: {federal_facts[0].get('uri', 'federal law')}",
                    confidence=0.9
                )
            else:
                # Cantonal autonomy applies
                return LegalRule(
                    rule_type=LegalRuleType.SCOPE,
                    description="Cantonal law applies due to cantonal autonomy",
                    input_facts=facts,
                    output_conclusion=f"Apply cantonal provision: {cantonal_facts[0].get('uri', 'cantonal law')}",
                    confidence=0.85
                )

        return None

    def apply_validity_rule(self, facts: List[Dict[str, Any]]) -> Optional[LegalRule]:
        """
        Check validity of legal provisions (in force vs repealed)

        Args:
            facts: Facts to evaluate

        Returns:
            LegalRule with validity assessment
        """
        valid_facts = []
        invalid_facts = []
        today = date.today()

        for fact in facts:
            if fact.get("metadata"):
                # Check in_force_date
                in_force = fact["metadata"].get("in_force_date")
                if in_force:
                    try:
                        in_force_date = datetime.strptime(in_force, "%Y-%m-%d").date()
                        if in_force_date > today:
                            invalid_facts.append((fact, "not yet in force"))
                            continue
                    except (ValueError, TypeError):
                        pass

                # Check repeal_date
                repealed = fact["metadata"].get("repeal_date")
                if repealed:
                    try:
                        repeal_date = datetime.strptime(repealed, "%Y-%m-%d").date()
                        if repeal_date <= today:
                            invalid_facts.append((fact, "repealed"))
                            continue
                    except (ValueError, TypeError):
                        pass

                valid_facts.append(fact)

        if invalid_facts and valid_facts:
            return LegalRule(
                rule_type=LegalRuleType.VALIDITY,
                description="Only currently valid provisions apply",
                input_facts=facts,
                output_conclusion=f"Apply valid provision: {valid_facts[0].get('uri', 'valid law')}. "
                                 f"Excluded {len(invalid_facts)} invalid provision(s)",
                confidence=0.95
            )

        return None

    def _determine_hierarchy_level(self, fact: Dict[str, Any]) -> Optional[LegalHierarchy]:
        """Determine the hierarchy level of a legal fact"""
        # Check type field
        fact_type = fact.get("type", "").lower()
        for key, level in self.hierarchy_map.items():
            if key.lower() in fact_type:
                return level

        # Check metadata
        if fact.get("metadata"):
            law_type = fact["metadata"].get("law_type", "").lower()
            for key, level in self.hierarchy_map.items():
                if key.lower() in law_type:
                    return level

        # Check SR number patterns
        uri = fact.get("uri", "")
        if "101" in uri:  # Constitution
            return LegalHierarchy.CONSTITUTION
        elif uri.startswith("SR"):
            # Default to federal law for SR citations
            return LegalHierarchy.FEDERAL_LAW

        return None

    def _calculate_specificity_score(self, fact: Dict[str, Any]) -> float:
        """Calculate specificity score for a fact"""
        score = 0.5  # Base score

        # Check for specific indicators
        content = (fact.get("content") or "").lower()
        title = (fact.get("title") or "").lower()

        # Specific terms increase score
        specific_terms = ["insbesondere", "specifically", "ausnahme", "exception",
                         "sonderfall", "special case", "abweichend", "derogation"]
        for term in specific_terms:
            if term in content or term in title:
                score += 0.2

        # General terms decrease score
        general_terms = ["allgemein", "general", "grundsatz", "principle",
                        "regel", "normally", "üblicherweise", "usually"]
        for term in general_terms:
            if term in content or term in title:
                score -= 0.1

        # Article level is more specific than law level
        if fact.get("type") == "Article":
            score += 0.1
        elif fact.get("type") == "Paragraph":
            score += 0.2
        elif fact.get("type") == "Subpoint":
            score += 0.3

        return max(0.0, min(1.0, score))

    def _determine_scope(self, fact: Dict[str, Any]) -> str:
        """Determine if fact is federal or cantonal scope"""
        uri = fact.get("uri", "").lower()

        # SR numbers indicate federal law
        if uri.startswith("sr"):
            return "federal"

        # Canton abbreviations
        canton_codes = ["zh", "be", "lu", "ur", "sz", "ow", "nw", "gl", "zg",
                       "fr", "so", "bs", "bl", "sh", "ar", "ai", "sg", "gr",
                       "ag", "tg", "ti", "vd", "vs", "ne", "ge", "ju"]

        for code in canton_codes:
            if code in uri:
                return "cantonal"

        # Check metadata
        if fact.get("metadata"):
            if fact["metadata"].get("jurisdiction") == "cantonal":
                return "cantonal"

        return "federal"

    def _is_federal_matter(self, facts: List[Dict[str, Any]]) -> bool:
        """Determine if the matter is under federal competence"""
        # Federal exclusive competences (non-exhaustive)
        federal_matters = [
            "military", "customs", "currency", "foreign affairs",
            "civil law", "criminal law", "social insurance",
            "nuclear energy", "railways", "aviation"
        ]

        for fact in facts:
            content = (fact.get("content") or "").lower()
            for matter in federal_matters:
                if matter in content:
                    return True

        return False

    def _has_hierarchy_conflict(self, facts: List[Dict[str, Any]]) -> bool:
        """Check if facts have different hierarchy levels"""
        levels = set()
        for fact in facts:
            level = self._determine_hierarchy_level(fact)
            if level:
                levels.add(level)
        return len(levels) > 1

    def _has_temporal_conflict(self, facts: List[Dict[str, Any]]) -> bool:
        """Check if facts have different in-force dates"""
        dates = set()
        for fact in facts:
            if fact.get("metadata"):
                in_force = fact["metadata"].get("in_force_date")
                if in_force:
                    dates.add(in_force)
        return len(dates) > 1

    def _has_specificity_conflict(self, facts: List[Dict[str, Any]]) -> bool:
        """Check if facts have different specificity levels"""
        scores = []
        for fact in facts:
            score = self._calculate_specificity_score(fact)
            scores.append(score)

        if len(scores) > 1:
            return max(scores) - min(scores) > 0.3
        return False

    def _has_scope_conflict(self, facts: List[Dict[str, Any]]) -> bool:
        """Check if facts have federal vs cantonal scope conflict"""
        scopes = set()
        for fact in facts:
            scope = self._determine_scope(fact)
            scopes.add(scope)
        return "federal" in scopes and "cantonal" in scopes