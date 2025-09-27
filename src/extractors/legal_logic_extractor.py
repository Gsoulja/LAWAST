#!/usr/bin/env python3
"""
Legal Logic Extractor for Swiss Law
Transforms AST from simple paths to semantic legal logic understanding
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LegalOperator(Enum):
    """Legal operators found in Swiss law"""
    MUST = "MUST"  # muss, doit, deve
    MAY = "MAY"  # darf, peut, può
    SHALL_NOT = "SHALL_NOT"  # darf nicht, ne doit pas
    ENTITLED = "ENTITLED"  # hat Anspruch, a droit
    OBLIGATED = "OBLIGATED"  # ist verpflichtet, est obligé
    FORBIDDEN = "FORBIDDEN"  # ist untersagt, est interdit


class NodeType(Enum):
    """Types of legal logic nodes"""
    CONDITION = "CONDITION"  # IF clause
    CONSEQUENCE = "CONSEQUENCE"  # THEN clause
    EXCEPTION = "EXCEPTION"  # EXCEPT clause
    DEFINITION = "DEFINITION"  # Term definition
    OBLIGATION = "OBLIGATION"  # Must do
    PERMISSION = "PERMISSION"  # May do
    PROHIBITION = "PROHIBITION"  # Must not do
    RIGHT = "RIGHT"  # Entitled to


@dataclass
class LegalLogicNode:
    """Semantic node representing legal logic"""
    node_type: NodeType
    operator: Optional[LegalOperator]
    text: str
    subject: Optional[str] = None  # Who/what is affected
    action: Optional[str] = None  # What must/may be done
    value: Optional[Any] = None  # Numeric values, durations
    temporal: Optional[Dict[str, Any]] = None  # Time constraints
    references: List[str] = field(default_factory=list)  # Cross-references
    language: str = "de"
    confidence: float = 1.0


@dataclass
class LegalRule:
    """Complete legal rule with conditions and consequences"""
    article_ref: str
    conditions: List[LegalLogicNode] = field(default_factory=list)
    consequences: List[LegalLogicNode] = field(default_factory=list)
    exceptions: List[LegalLogicNode] = field(default_factory=list)
    definitions: List[LegalLogicNode] = field(default_factory=list)


class LegalLogicExtractor:
    """Extract legal logic from Swiss law text"""

    # Swiss legal patterns in German, French, Italian
    PATTERNS = {
        "conditions": {
            "de": [
                r"(?:wenn|falls|sofern|vorausgesetzt|im Falle)\s+(.+?)(?:,|dann|so|\.|;)",
                r"(?:bei|nach|vor|während)\s+(.+?)(?:,|dann|so|\.|;)",
                r"(?:für den Fall|unter der Bedingung)\s+(.+?)(?:,|dann|so|\.|;)"
            ],
            "fr": [
                r"(?:si|lorsque|quand|à condition que|dans le cas où)\s+(.+?)(?:,|alors|ainsi|\.|;)",
                r"(?:lors de|après|avant|pendant)\s+(.+?)(?:,|alors|ainsi|\.|;)"
            ],
            "it": [
                r"(?:se|quando|qualora|a condizione che|nel caso)\s+(.+?)(?:,|allora|quindi|\.|;)",
                r"(?:durante|dopo|prima|mentre)\s+(.+?)(?:,|allora|quindi|\.|;)"
            ]
        },
        "consequences": {
            "de": [
                r"(?:dann|so)\s+(.+?)(?:\.|;)",
                r"(?:gilt|beträgt|muss|darf)\s+(.+?)(?:\.|;)",
                r"(?:hat.*?Anspruch|ist.*?verpflichtet)\s+(.+?)(?:\.|;)"
            ],
            "fr": [
                r"(?:alors|ainsi)\s+(.+?)(?:\.|;)",
                r"(?:s'applique|est de|doit|peut)\s+(.+?)(?:\.|;)",
                r"(?:a.*?droit|est.*?obligé)\s+(.+?)(?:\.|;)"
            ],
            "it": [
                r"(?:allora|quindi)\s+(.+?)(?:\.|;)",
                r"(?:si applica|è di|deve|può)\s+(.+?)(?:\.|;)",
                r"(?:ha.*?diritto|è.*?obbligato)\s+(.+?)(?:\.|;)"
            ]
        },
        "exceptions": {
            "de": [
                r"(?:ausser|ausgenommen|es sei denn|sofern nicht)\s+(.+?)(?:\.|;)",
                r"(?:mit Ausnahme|vorbehaltlich|unbeschadet)\s+(.+?)(?:\.|;)"
            ],
            "fr": [
                r"(?:sauf|excepté|à moins que|hormis)\s+(.+?)(?:\.|;)",
                r"(?:à l'exception|sous réserve|sans préjudice)\s+(.+?)(?:\.|;)"
            ],
            "it": [
                r"(?:salvo|eccetto|a meno che|tranne)\s+(.+?)(?:\.|;)",
                r"(?:ad eccezione|con riserva|senza pregiudizio)\s+(.+?)(?:\.|;)"
            ]
        },
        "temporal": {
            "de": [
                r"(\d+)\s*(Tag|Woche|Monat|Jahr)(?:e|en)?",
                r"(?:innert|innerhalb|binnen)\s*(\d+)\s*(Tag|Woche|Monat)",
                r"(?:nach|vor|ab)\s+(.+?)(?:\.|,)"
            ],
            "fr": [
                r"(\d+)\s*(jour|semaine|mois|an)s?",
                r"(?:dans|sous|en)\s*(\d+)\s*(jour|semaine|mois)",
                r"(?:après|avant|dès)\s+(.+?)(?:\.|,)"
            ],
            "it": [
                r"(\d+)\s*(giorno|settimana|mese|anno)(?:i)?",
                r"(?:entro|in)\s*(\d+)\s*(giorno|settimana|mese)",
                r"(?:dopo|prima|da)\s+(.+?)(?:\.|,)"
            ]
        },
        "obligations": {
            "de": ["muss", "müssen", "hat zu", "haben zu", "ist verpflichtet", "sind verpflichtet"],
            "fr": ["doit", "doivent", "est obligé", "sont obligés", "est tenu", "sont tenus"],
            "it": ["deve", "devono", "è obbligato", "sono obbligati", "è tenuto", "sono tenuti"]
        },
        "permissions": {
            "de": ["darf", "dürfen", "kann", "können", "ist berechtigt", "sind berechtigt"],
            "fr": ["peut", "peuvent", "est autorisé", "sont autorisés", "a le droit", "ont le droit"],
            "it": ["può", "possono", "è autorizzato", "sono autorizzati", "ha il diritto", "hanno il diritto"]
        },
        "prohibitions": {
            "de": ["darf nicht", "dürfen nicht", "ist untersagt", "ist verboten"],
            "fr": ["ne doit pas", "ne doivent pas", "est interdit", "est défendu"],
            "it": ["non deve", "non devono", "è vietato", "è proibito"]
        }
    }

    def __init__(self, language: str = "de"):
        """Initialize extractor for specific language"""
        self.language = language

    def extract_legal_logic(self, text: str, article_ref: str = "") -> LegalRule:
        """
        Extract legal logic from article text

        Args:
            text: Article text content
            article_ref: Article reference (e.g., "Art. 335b OR")

        Returns:
            LegalRule with extracted logic
        """
        rule = LegalRule(article_ref=article_ref)

        # Split into sentences for analysis
        sentences = self._split_legal_sentences(text)

        for sentence in sentences:
            # Extract conditions
            conditions = self._extract_conditions(sentence)
            rule.conditions.extend(conditions)

            # Extract consequences
            consequences = self._extract_consequences(sentence)
            rule.consequences.extend(consequences)

            # Extract exceptions
            exceptions = self._extract_exceptions(sentence)
            rule.exceptions.extend(exceptions)

            # Extract temporal constraints
            temporal = self._extract_temporal(sentence)
            if temporal and rule.consequences:
                rule.consequences[-1].temporal = temporal

            # Extract obligations/permissions
            obligations = self._extract_obligations(sentence)
            rule.consequences.extend(obligations)

        return rule

    def _split_legal_sentences(self, text: str) -> List[str]:
        """Split legal text into sentences, handling abbreviations"""
        # Handle common legal abbreviations that shouldn't split sentences
        text = re.sub(r'\bArt\.\s*', 'Art ', text)
        text = re.sub(r'\bAbs\.\s*', 'Abs ', text)
        text = re.sub(r'\blit\.\s*', 'lit ', text)
        text = re.sub(r'\bSR\s*', 'SR ', text)

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.;])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_conditions(self, sentence: str) -> List[LegalLogicNode]:
        """Extract IF conditions from sentence"""
        conditions = []
        patterns = self.PATTERNS["conditions"].get(self.language, [])

        for pattern in patterns:
            matches = re.finditer(pattern, sentence, re.IGNORECASE)
            for match in matches:
                condition_text = match.group(1) if match.groups() else match.group(0)
                conditions.append(LegalLogicNode(
                    node_type=NodeType.CONDITION,
                    operator=None,
                    text=condition_text.strip(),
                    language=self.language
                ))

        return conditions

    def _extract_consequences(self, sentence: str) -> List[LegalLogicNode]:
        """Extract THEN consequences from sentence"""
        consequences = []
        patterns = self.PATTERNS["consequences"].get(self.language, [])

        for pattern in patterns:
            matches = re.finditer(pattern, sentence, re.IGNORECASE)
            for match in matches:
                consequence_text = match.group(1) if match.groups() else match.group(0)

                # Determine operator
                operator = self._determine_operator(consequence_text)

                consequences.append(LegalLogicNode(
                    node_type=NodeType.CONSEQUENCE,
                    operator=operator,
                    text=consequence_text.strip(),
                    language=self.language
                ))

        return consequences

    def _extract_exceptions(self, sentence: str) -> List[LegalLogicNode]:
        """Extract EXCEPT clauses from sentence"""
        exceptions = []
        patterns = self.PATTERNS["exceptions"].get(self.language, [])

        for pattern in patterns:
            matches = re.finditer(pattern, sentence, re.IGNORECASE)
            for match in matches:
                exception_text = match.group(1) if match.groups() else match.group(0)
                exceptions.append(LegalLogicNode(
                    node_type=NodeType.EXCEPTION,
                    operator=None,
                    text=exception_text.strip(),
                    language=self.language
                ))

        return exceptions

    def _extract_temporal(self, sentence: str) -> Optional[Dict[str, Any]]:
        """Extract temporal constraints from sentence"""
        patterns = self.PATTERNS["temporal"].get(self.language, [])

        for pattern in patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                if match.groups() and len(match.groups()) >= 2:
                    return {
                        "value": int(match.group(1)),
                        "unit": match.group(2),
                        "text": match.group(0)
                    }

        return None

    def _extract_obligations(self, sentence: str) -> List[LegalLogicNode]:
        """Extract obligations and permissions"""
        nodes = []

        # Check for obligations
        for term in self.PATTERNS["obligations"].get(self.language, []):
            if term in sentence.lower():
                nodes.append(LegalLogicNode(
                    node_type=NodeType.OBLIGATION,
                    operator=LegalOperator.MUST,
                    text=sentence,
                    language=self.language
                ))
                break

        # Check for permissions
        for term in self.PATTERNS["permissions"].get(self.language, []):
            if term in sentence.lower():
                nodes.append(LegalLogicNode(
                    node_type=NodeType.PERMISSION,
                    operator=LegalOperator.MAY,
                    text=sentence,
                    language=self.language
                ))
                break

        # Check for prohibitions
        for term in self.PATTERNS["prohibitions"].get(self.language, []):
            if term in sentence.lower():
                nodes.append(LegalLogicNode(
                    node_type=NodeType.PROHIBITION,
                    operator=LegalOperator.SHALL_NOT,
                    text=sentence,
                    language=self.language
                ))
                break

        return nodes

    def _determine_operator(self, text: str) -> Optional[LegalOperator]:
        """Determine the legal operator from text"""
        text_lower = text.lower()

        # Check each operator type
        if any(term in text_lower for term in self.PATTERNS["obligations"].get(self.language, [])):
            return LegalOperator.MUST
        elif any(term in text_lower for term in self.PATTERNS["permissions"].get(self.language, [])):
            return LegalOperator.MAY
        elif any(term in text_lower for term in self.PATTERNS["prohibitions"].get(self.language, [])):
            return LegalOperator.SHALL_NOT

        return None

    def format_rule_for_display(self, rule: LegalRule) -> str:
        """Format extracted rule for display"""
        output = []

        if rule.article_ref:
            output.append(f"=== {rule.article_ref} Legal Logic ===\n")

        if rule.conditions:
            output.append("CONDITIONS (IF):")
            for i, cond in enumerate(rule.conditions, 1):
                output.append(f"  {i}. {cond.text}")

        if rule.consequences:
            output.append("\nCONSEQUENCES (THEN):")
            for i, cons in enumerate(rule.consequences, 1):
                operator = f"[{cons.operator.value}] " if cons.operator else ""
                temporal = f" (within {cons.temporal['value']} {cons.temporal['unit']})" if cons.temporal else ""
                output.append(f"  {i}. {operator}{cons.text}{temporal}")

        if rule.exceptions:
            output.append("\nEXCEPTIONS (EXCEPT):")
            for i, exc in enumerate(rule.exceptions, 1):
                output.append(f"  {i}. {exc.text}")

        return "\n".join(output)


# Example usage and testing
if __name__ == "__main__":
    # Test with Article 335b OR example
    article_335b_text = """
    Während der Probezeit kann das Arbeitsverhältnis mit einer Kündigungsfrist
    von sieben Tagen gekündigt werden; dabei gilt jeder Tag als Kündigungstermin.
    Die Probezeit darf höchstens drei Monate betragen.
    Ausgenommen sind Fälle gemäss Artikel 336.
    """

    extractor = LegalLogicExtractor(language="de")
    rule = extractor.extract_legal_logic(article_335b_text, "Art. 335b OR")

    print(extractor.format_rule_for_display(rule))

    # Test with Article 16 BV example
    article_16_text = """
    Die Meinungs- und Informationsfreiheit ist gewährleistet.
    Jede Person hat das Recht, ihre Meinung frei zu bilden und sie ungehindert
    zu äussern und zu verbreiten.
    Jede Person hat das Recht, Informationen frei zu empfangen, aus allgemein
    zugänglichen Quellen zu beschaffen und zu verbreiten.
    """

    rule_16 = extractor.extract_legal_logic(article_16_text, "Art. 16 BV")
    print("\n" + extractor.format_rule_for_display(rule_16))