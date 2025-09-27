#!/usr/bin/env python3
"""
Legal Logic AST Search - Enhanced AST with semantic legal understanding
This transforms AST from simple paths to legal intelligence
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..data_access.neo4j_connection import Neo4jConnectionManager
from ..extractors.legal_logic_extractor import LegalLogicExtractor, LegalRule, LegalLogicNode, NodeType, LegalOperator

logger = logging.getLogger(__name__)


@dataclass
class LegalLogicSearchResult:
    """Result from Legal Logic AST search"""
    node_id: str
    uri: str
    node_type: str
    score: float
    title: Optional[str] = None
    content: Optional[str] = None
    sr_number: Optional[str] = None
    article_number: Optional[str] = None

    # Legal logic fields
    legal_rule: Optional[LegalRule] = None
    matched_conditions: List[str] = field(default_factory=list)
    matched_consequences: List[str] = field(default_factory=list)
    matched_exceptions: List[str] = field(default_factory=list)
    applicable_operators: List[LegalOperator] = field(default_factory=list)

    # Reasoning chain
    reasoning: Optional[str] = None
    confidence: float = 0.0

    def __post_init__(self):
        """Initialize empty lists if None"""
        if self.matched_conditions is None:
            self.matched_conditions = []
        if self.matched_consequences is None:
            self.matched_consequences = []
        if self.matched_exceptions is None:
            self.matched_exceptions = []
        if self.applicable_operators is None:
            self.applicable_operators = []


class QueryIntent(Enum):
    """Types of legal query intents"""
    OBLIGATION = "obligation"  # What must be done
    PERMISSION = "permission"  # What may be done
    PROHIBITION = "prohibition"  # What must not be done
    CONDITION = "condition"  # Under what circumstances
    EXCEPTION = "exception"  # What are the exceptions
    DEFINITION = "definition"  # What does this mean
    PROCEDURE = "procedure"  # How to do something
    TIMELINE = "timeline"  # When/timeframes
    RIGHTS = "rights"  # What rights exist


class LegalLogicASTSearch:
    """
    Enhanced AST Search using Legal Logic extraction.

    Instead of just hierarchical paths, this extracts and searches:
    - IF-THEN-EXCEPT patterns
    - Legal operators (MUST, MAY, SHALL NOT)
    - Temporal constraints
    - Cross-references
    """

    def __init__(self, connection: Optional[Neo4jConnectionManager] = None, language: str = "de"):
        """
        Initialize Legal Logic AST Search.

        Args:
            connection: Neo4j connection
            language: Language for extraction (de/fr/it)
        """
        self.connection = connection or Neo4jConnectionManager()
        self.language = language
        self.extractor = LegalLogicExtractor(language=language)

        # Cache for extracted legal logic
        self._logic_cache = {}

        logger.info(f"Legal Logic AST Search initialized for language: {language}")

    def detect_query_intent(self, query: str) -> List[QueryIntent]:
        """
        Detect the legal intent of a query.

        Args:
            query: User query

        Returns:
            List of detected query intents
        """
        intents = []
        query_lower = query.lower()

        # Obligation patterns
        obligation_patterns = [
            r"\bmuss\b", r"\bmüssen\b", r"\bverpflichtet\b", r"\bpflicht\b",  # German
            r"\bdoit\b", r"\bdevez\b", r"\bobligation\b", r"\bobligé\b",  # French
            r"\bmust\b", r"\bshall\b", r"\brequired\b", r"\bobligation\b"  # English
        ]
        if any(re.search(p, query_lower) for p in obligation_patterns):
            intents.append(QueryIntent.OBLIGATION)

        # Permission patterns
        permission_patterns = [
            r"\bdarf\b", r"\bdürfen\b", r"\bkann\b", r"\bkönnen\b", r"\bberechtigt\b",  # German
            r"\bpeut\b", r"\bpeuvent\b", r"\bautorisé\b", r"\bpermis\b",  # French
            r"\bmay\b", r"\bcan\b", r"\ballowed\b", r"\bpermitted\b"  # English
        ]
        if any(re.search(p, query_lower) for p in permission_patterns):
            intents.append(QueryIntent.PERMISSION)

        # Prohibition patterns
        prohibition_patterns = [
            r"\bdarf nicht\b", r"\bdürfen nicht\b", r"\bverboten\b", r"\buntersagt\b",  # German
            r"\bne.*?pas\b", r"\binterdit\b", r"\bdéfendu\b",  # French
            r"\bmust not\b", r"\bshall not\b", r"\bprohibited\b", r"\bforbidden\b"  # English
        ]
        if any(re.search(p, query_lower) for p in prohibition_patterns):
            intents.append(QueryIntent.PROHIBITION)

        # Condition patterns
        condition_patterns = [
            r"\bwenn\b", r"\bfalls\b", r"\bunter welchen.*?umständen\b", r"\bvoraussetzung\b",  # German
            r"\bsi\b", r"\bquand\b", r"\blorsque\b", r"\bcondition\b",  # French
            r"\bif\b", r"\bwhen\b", r"\bunder what\b", r"\bcircumstances\b"  # English
        ]
        if any(re.search(p, query_lower) for p in condition_patterns):
            intents.append(QueryIntent.CONDITION)

        # Exception patterns
        exception_patterns = [
            r"\bausnahme\b", r"\bausgenommen\b", r"\bausser\b",  # German
            r"\bexception\b", r"\bsauf\b", r"\bhormis\b",  # French
            r"\bexcept\b", r"\bunless\b", r"\bexclud"  # English
        ]
        if any(re.search(p, query_lower) for p in exception_patterns):
            intents.append(QueryIntent.EXCEPTION)

        # Timeline patterns
        timeline_patterns = [
            r"\bfrist\b", r"\btage?\b", r"\bwochen?\b", r"\bmonat\b", r"\bjahr\b", r"\bwann\b",  # German
            r"\bdélai\b", r"\bjours?\b", r"\bsemaines?\b", r"\bmois\b", r"\ban(née)?s?\b",  # French
            r"\bdeadline\b", r"\bdays?\b", r"\bweeks?\b", r"\bmonths?\b", r"\byears?\b", r"\bnotice period\b"  # English
        ]
        if any(re.search(p, query_lower) for p in timeline_patterns):
            intents.append(QueryIntent.TIMELINE)

        # Rights patterns
        rights_patterns = [
            r"\brecht\b", r"\banspruch\b", r"\bberechtigung\b",  # German
            r"\bdroit\b", r"\bliberté\b",  # French
            r"\bright\b", r"\bentitled\b", r"\bfreedom\b"  # English
        ]
        if any(re.search(p, query_lower) for p in rights_patterns):
            intents.append(QueryIntent.RIGHTS)

        # Don't default to CONDITION - let AST search be skipped for general queries
        # if not intents:
        #     intents.append(QueryIntent.CONDITION)

        return intents

    def search_by_legal_logic(self, query: str, limit: int = 20) -> List[LegalLogicSearchResult]:
        """
        Search using legal logic patterns.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of results with legal logic analysis
        """
        # Detect query intent
        intents = self.detect_query_intent(query)
        logger.debug(f"Detected intents: {[i.value for i in intents]}")

        # Extract entities from query
        entities = self._extract_query_entities(query)
        logger.debug(f"Extracted entities: {entities}")

        # Build Cypher query based on intents
        cypher_query, params = self._build_logic_search_query(intents, entities, limit)

        try:
            # Execute search
            raw_results = self.connection.execute_query(cypher_query, params)

            # Process results with legal logic extraction
            results = []
            for row in raw_results:
                result = self._process_logic_result(row, query, intents)
                if result:
                    results.append(result)

            # Sort by relevance
            results.sort(key=lambda x: x.score, reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Error in legal logic search: {e}")
            return []

    def _extract_query_entities(self, query: str) -> Dict[str, Any]:
        """
        Extract legal entities from query.

        Args:
            query: Search query

        Returns:
            Dictionary of extracted entities
        """
        entities = {}

        # Extract SR numbers
        sr_pattern = r"\b(\d{3}(?:\.\d+)*)\b"
        sr_match = re.search(sr_pattern, query)
        if sr_match:
            entities["sr_number"] = sr_match.group(1)

        # Extract article numbers
        article_pattern = r"\b(?:art(?:icle)?\.?\s*|artikel\s*)(\d+[a-z]?)\b"
        article_match = re.search(article_pattern, query, re.IGNORECASE)
        if article_match:
            entities["article"] = article_match.group(1)

        # Extract temporal values
        temporal_patterns = {
            "days": r"(\d+)\s*(?:tage?|days?|jours?|giorn[oi])",
            "weeks": r"(\d+)\s*(?:wochen?|weeks?|semaines?|settiman[ae])",
            "months": r"(\d+)\s*(?:monat[en]?|months?|mois|mes[ei])",
            "years": r"(\d+)\s*(?:jahr[en]?|years?|an(?:née)?s?|ann[oi])"
        }

        for unit, pattern in temporal_patterns.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                entities[unit] = int(match.group(1))

        # Extract subject (who is affected)
        subject_patterns = {
            "employee": r"\b(?:arbeitnehmer|employee|employé|lavoratore|mitarbeiter)\b",
            "employer": r"\b(?:arbeitgeber|employer|employeur|datore di lavoro)\b",
            "person": r"\b(?:person|personne|persona)\b",
            "authority": r"\b(?:behörde|authority|autorité|autorità)\b"
        }

        for subject, pattern in subject_patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                entities["subject"] = subject
                break

        return entities

    def _build_logic_search_query(self, intents: List[QueryIntent], entities: Dict[str, Any], limit: int) -> Tuple[str, Dict]:
        """
        Build Cypher query for legal logic search.

        Args:
            intents: Query intents
            entities: Extracted entities
            limit: Result limit

        Returns:
            Tuple of (cypher_query, parameters)
        """
        # If no specific intent, skip AST search
        if not intents:
            logger.debug("No specific legal intent detected - skipping AST search")
            return "", {"limit": 0}

        # Base query to find articles with content
        where_clauses = []

        # Filter by SR number if provided
        if "sr_number" in entities:
            where_clauses.append("l.sr_number = $sr_number")

        # Filter by article if provided
        if "article" in entities:
            where_clauses.append("a.number = $article")

        # Build WHERE clause
        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Query based on intent
        if QueryIntent.OBLIGATION in intents:
            # Find articles with obligation keywords
            cypher_query = f"""
            MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
            WHERE {where_clause}
            AND (
                a.content_full =~ '.*(?i)(muss|müssen|verpflichtet|doit|doivent|deve|devono).*'
                OR a.content_preview =~ '.*(?i)(muss|müssen|verpflichtet|doit|doivent|deve|devono).*'
            )
            RETURN
                elementId(a) as node_id,
                a.uri as uri,
                'Article' as node_type,
                a.number as article_number,
                l.sr_number as sr_number,
                COALESCE(l.title_de, l.title_fr, l.title_it) as law_title,
                'Art. ' + a.number as title,
                a.content_full as content
            LIMIT $limit
            """
        elif QueryIntent.PERMISSION in intents:
            # Find articles with permission keywords
            cypher_query = f"""
            MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
            WHERE {where_clause}
            AND (
                a.content_full =~ '.*(?i)(darf|dürfen|kann|können|peut|peuvent|può|possono).*'
                OR a.content_preview =~ '.*(?i)(darf|dürfen|kann|können|peut|peuvent|può|possono).*'
            )
            RETURN
                elementId(a) as node_id,
                a.uri as uri,
                'Article' as node_type,
                a.number as article_number,
                l.sr_number as sr_number,
                COALESCE(l.title_de, l.title_fr, l.title_it) as law_title,
                'Art. ' + a.number as title,
                a.content_full as content
            LIMIT $limit
            """
        elif QueryIntent.TIMELINE in intents:
            # Find articles with temporal constraints
            cypher_query = f"""
            MATCH (l:Law)-[:HAS_ARTICLE]->(a:Article)
            WHERE {where_clause}
            AND (
                a.content_full =~ '.*(?i)\\\\d+\\\\s*(tag|woche|monat|jahr|jour|semaine|mois|giorn|settiman|mes|ann).*'
                OR a.content_preview =~ '.*(?i)\\\\d+\\\\s*(tag|woche|monat|jahr|jour|semaine|mois|giorn|settiman|mes|ann).*'
            )
            RETURN
                elementId(a) as node_id,
                a.uri as uri,
                'Article' as node_type,
                a.number as article_number,
                l.sr_number as sr_number,
                COALESCE(l.title_de, l.title_fr, l.title_it) as law_title,
                'Art. ' + a.number as title,
                a.content_full as content
            LIMIT $limit
            """
        else:
            # For general queries without specific legal intent, return empty results
            # AST search should only be used for specific legal logic patterns
            logger.debug(f"No specific legal intent detected for query: '{query[:50]}...' - skipping AST search")
            return "", {"limit": 0}

        # Build parameters
        params = {"limit": limit}
        if "sr_number" in entities:
            params["sr_number"] = entities["sr_number"]
        if "article" in entities:
            params["article"] = entities["article"]

        return cypher_query, params

    def _process_logic_result(self, row: Dict[str, Any], query: str, intents: List[QueryIntent]) -> Optional[LegalLogicSearchResult]:
        """
        Process a search result with legal logic extraction.

        Args:
            row: Database row
            query: Original query
            intents: Query intents

        Returns:
            LegalLogicSearchResult or None
        """
        try:
            # Get content
            content = row.get("content", "")
            if not content:
                return None

            # Extract legal logic
            article_ref = f"Art. {row.get('article_number', '')} SR {row.get('sr_number', '')}"

            # Check cache
            cache_key = f"{article_ref}_{self.language}"
            if cache_key in self._logic_cache:
                legal_rule = self._logic_cache[cache_key]
            else:
                # Extract logic
                legal_rule = self.extractor.extract_legal_logic(content, article_ref)
                self._logic_cache[cache_key] = legal_rule

            # Create result
            result = LegalLogicSearchResult(
                node_id=row["node_id"],
                uri=row["uri"],
                node_type=row["node_type"],
                title=row.get("title"),
                content=content,
                sr_number=row.get("sr_number"),
                article_number=row.get("article_number"),
                legal_rule=legal_rule,
                score=0.5  # Base score
            )

            # Score based on intent matching
            score = self._calculate_logic_score(legal_rule, query, intents)
            result.score = score

            # Extract matched elements
            for condition in legal_rule.conditions:
                if self._matches_query(condition.text, query):
                    result.matched_conditions.append(condition.text)

            for consequence in legal_rule.consequences:
                if self._matches_query(consequence.text, query):
                    result.matched_consequences.append(consequence.text)
                if consequence.operator:
                    result.applicable_operators.append(consequence.operator)

            for exception in legal_rule.exceptions:
                if self._matches_query(exception.text, query):
                    result.matched_exceptions.append(exception.text)

            # Generate reasoning
            result.reasoning = self._generate_reasoning(legal_rule, query, intents)
            result.confidence = min(score * 1.2, 1.0)  # Boost confidence slightly

            return result

        except Exception as e:
            logger.error(f"Error processing logic result: {e}")
            return None

    def _matches_query(self, text: str, query: str) -> bool:
        """
        Check if text matches query terms.

        Args:
            text: Text to check
            query: Query string

        Returns:
            True if matches
        """
        # Simple keyword matching (can be enhanced)
        query_words = query.lower().split()
        text_lower = text.lower()

        matches = sum(1 for word in query_words if word in text_lower)
        return matches >= len(query_words) * 0.3  # 30% word match threshold

    def _calculate_logic_score(self, rule: LegalRule, query: str, intents: List[QueryIntent]) -> float:
        """
        Calculate relevance score based on legal logic.

        Args:
            rule: Extracted legal rule
            query: Query string
            intents: Query intents

        Returns:
            Score (0-1)
        """
        score = 0.5  # Base score

        # Score based on intent matching
        for intent in intents:
            if intent == QueryIntent.OBLIGATION:
                # Check for obligation operators
                for consequence in rule.consequences:
                    if consequence.operator == LegalOperator.MUST:
                        score += 0.2
                        break

            elif intent == QueryIntent.PERMISSION:
                # Check for permission operators
                for consequence in rule.consequences:
                    if consequence.operator == LegalOperator.MAY:
                        score += 0.2
                        break

            elif intent == QueryIntent.PROHIBITION:
                # Check for prohibition operators
                for consequence in rule.consequences:
                    if consequence.operator == LegalOperator.SHALL_NOT:
                        score += 0.2
                        break

            elif intent == QueryIntent.CONDITION:
                # Boost if has conditions
                if rule.conditions:
                    score += 0.1 * min(len(rule.conditions), 2)

            elif intent == QueryIntent.EXCEPTION:
                # Boost if has exceptions
                if rule.exceptions:
                    score += 0.15 * min(len(rule.exceptions), 2)

            elif intent == QueryIntent.TIMELINE:
                # Check for temporal elements
                for consequence in rule.consequences:
                    if consequence.temporal:
                        score += 0.2
                        break

        # Boost for complete rules (IF-THEN structure)
        if rule.conditions and rule.consequences:
            score += 0.1

        # Boost for exceptions (comprehensive coverage)
        if rule.exceptions:
            score += 0.05

        return min(score, 1.0)

    def _generate_reasoning(self, rule: LegalRule, query: str, intents: List[QueryIntent]) -> str:
        """
        Generate reasoning explanation.

        Args:
            rule: Legal rule
            query: Query
            intents: Query intents

        Returns:
            Reasoning text
        """
        reasoning_parts = []

        # Explain what was found
        if rule.conditions:
            reasoning_parts.append(f"Found {len(rule.conditions)} condition(s)")

        if rule.consequences:
            operators = [c.operator for c in rule.consequences if c.operator]
            if operators:
                op_names = [op.value for op in set(operators)]
                reasoning_parts.append(f"Legal operators: {', '.join(op_names)}")

        if rule.exceptions:
            reasoning_parts.append(f"Has {len(rule.exceptions)} exception(s)")

        # Add temporal info
        for consequence in rule.consequences:
            if consequence.temporal:
                reasoning_parts.append(
                    f"Temporal: {consequence.temporal['value']} {consequence.temporal['unit']}"
                )

        return "; ".join(reasoning_parts) if reasoning_parts else "Direct text match"

    def evaluate_conditions(self, rule: LegalRule, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate if conditions in a legal rule are met.

        Args:
            rule: Legal rule to evaluate
            context: Context with facts to check

        Returns:
            Evaluation result with reasoning
        """
        result = {
            "applicable": False,
            "conditions_met": [],
            "conditions_not_met": [],
            "missing_facts": [],
            "consequences": [],
            "exceptions_apply": [],
            "reasoning": ""
        }

        # Check each condition
        for condition in rule.conditions:
            # Simple keyword matching (can be enhanced with NLP)
            condition_met = self._evaluate_single_condition(condition, context)

            if condition_met is None:
                result["missing_facts"].append(condition.text)
            elif condition_met:
                result["conditions_met"].append(condition.text)
            else:
                result["conditions_not_met"].append(condition.text)

        # Check exceptions
        for exception in rule.exceptions:
            if self._evaluate_single_condition(exception, context):
                result["exceptions_apply"].append(exception.text)

        # Determine if rule applies
        if result["conditions_met"] and not result["conditions_not_met"]:
            if not result["exceptions_apply"]:
                result["applicable"] = True
                result["consequences"] = [c.text for c in rule.consequences]

        # Generate reasoning
        reasoning_parts = []
        if result["conditions_met"]:
            reasoning_parts.append(f"✓ Conditions met: {len(result['conditions_met'])}")
        if result["conditions_not_met"]:
            reasoning_parts.append(f"✗ Conditions not met: {len(result['conditions_not_met'])}")
        if result["exceptions_apply"]:
            reasoning_parts.append(f"! Exceptions apply: {len(result['exceptions_apply'])}")

        result["reasoning"] = "; ".join(reasoning_parts)

        return result

    def _evaluate_single_condition(self, condition: LegalLogicNode, context: Dict[str, Any]) -> Optional[bool]:
        """
        Evaluate a single condition against context.

        Args:
            condition: Condition to evaluate
            context: Context with facts

        Returns:
            True if met, False if not met, None if insufficient info
        """
        # This is simplified - in production would use NLP
        condition_text = condition.text.lower()

        # Check for temporal conditions
        if condition.temporal:
            if "duration" in context:
                # Compare durations
                context_duration = context.get("duration", {})
                condition_value = condition.temporal["value"]
                condition_unit = condition.temporal["unit"]

                # Convert to days for comparison (simplified)
                unit_days = {"tag": 1, "woche": 7, "monat": 30, "jahr": 365}
                if condition_unit in unit_days:
                    condition_days = condition_value * unit_days[condition_unit]
                    context_days = context_duration.get("days", 0)

                    if "weniger als" in condition_text or "less than" in condition_text:
                        return context_days < condition_days
                    elif "mehr als" in condition_text or "more than" in condition_text:
                        return context_days > condition_days

        # Check for subject matching
        if condition.subject and "subject" in context:
            if condition.subject.lower() != context["subject"].lower():
                return False

        # Check for action matching
        if condition.action and "action" in context:
            if condition.action.lower() not in context["action"].lower():
                return False

        # If we can't evaluate, return None
        return None