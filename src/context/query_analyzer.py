"""
Query Analyzer - Analyzes user queries for intent, complexity, and entities
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Types of query intents"""
    FACTUAL = "factual"  # Looking for specific facts
    COMPARATIVE = "comparative"  # Comparing laws or articles
    PROCEDURAL = "procedural"  # How-to questions
    EXPLORATORY = "exploratory"  # Broad research questions
    DEFINITIONAL = "definitional"  # What is X?
    TEMPORAL = "temporal"  # Questions about time/dates
    JURISDICTIONAL = "jurisdictional"  # Questions about jurisdiction
    RELATIONSHIP = "relationship"  # Questions about relationships


class QueryComplexity(Enum):
    """Query complexity levels"""
    SIMPLE = "simple"  # Single concept, direct answer
    MEDIUM = "medium"  # Multiple concepts, some context needed
    COMPLEX = "complex"  # Multiple interconnected concepts


@dataclass
class QueryAnalysis:
    """Results of query analysis"""
    query: str
    intent: QueryIntent
    complexity: QueryComplexity
    confidence: float
    entities: Dict[str, List[str]] = field(default_factory=dict)
    ambiguity_score: float = 0.0
    missing_context: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    has_article_reference: bool = False
    has_law_reference: bool = False
    has_date_reference: bool = False


class QueryAnalyzer:
    """Analyzes queries to determine intent, complexity, and entities"""

    def __init__(self):
        """Initialize the query analyzer with patterns and keywords"""
        # Intent patterns
        self.intent_patterns = {
            QueryIntent.FACTUAL: [
                r'\bwhat\s+(?:is|are)\b',
                r'\bwhich\s+(?:law|article|section)\b',
                r'\btell\s+me\s+about\b',
                r'\bexplain\b',
            ],
            QueryIntent.COMPARATIVE: [
                r'\bdifference\s+between\b',
                r'\bcompare\b',
                r'\bversus\b|\bvs\b',
                r'\bsimilar(?:ity|ities)?\b',
                r'\bhow\s+does\s+.*\s+differ\b',
            ],
            QueryIntent.PROCEDURAL: [
                r'\bhow\s+(?:to|do|can)\b',
                r'\bsteps\s+(?:to|for)\b',
                r'\bprocess\s+(?:for|of)\b',
                r'\brequirements?\s+(?:for|to)\b',
                r'\bprocedure\b',
            ],
            QueryIntent.EXPLORATORY: [
                r'\boverview\b',
                r'\bsummar(?:y|ize)\b',
                r'\bgeneral\s+information\b',
                r'\bbackground\b',
                r'\bcontext\b',
            ],
            QueryIntent.DEFINITIONAL: [
                r'\bdefin(?:e|ition)\b',
                r'\bwhat\s+(?:is|are)\s+(?:a|an|the)?\b',
                r'\bmean(?:s|ing)?\b',
                r'\bstand\s+for\b',
            ],
            QueryIntent.TEMPORAL: [
                r'\bwhen\s+(?:was|did|will)\b',
                r'\bsince\s+when\b',
                r'\bsince\s+\d{4}\b',
                r'\bhistorical\b',
                r'\btimeline\b',
                r'\bhistory\b',
                r'\bchanges?\s+(?:over\s+time|since|to)\b',
            ],
            QueryIntent.JURISDICTIONAL: [
                r'\bwhere\b',
                r'\bjurisdiction\b',
                r'\bappl(?:y|ies|icable)\s+(?:to|in)\b',
                r'\bscope\b',
                r'\bterritor(?:y|ial)\b',
            ],
            QueryIntent.RELATIONSHIP: [
                r'\brelat(?:e|ed|ion|ionship)?\b',
                r'\bconnect(?:ed|ion)\b',
                r'\blink(?:ed|s)?\b',
                r'\bassociat(?:e|ed|ion)\b',
                r'\bdepend(?:s|ent|ency|encies)\b',
                r'\bbetween\s+\w+\s+(?:law|article|regulation)',
            ]
        }

        # Compile patterns for efficiency
        self.compiled_patterns = {
            intent: [re.compile(pattern, re.IGNORECASE)
                    for pattern in patterns]
            for intent, patterns in self.intent_patterns.items()
        }

        # Entity extraction patterns
        self.entity_patterns = {
            'article': re.compile(r'\b(?:art(?:icle)?|artikel)\.?\s*(\d+(?:\.\d+)?(?:[a-z])?)', re.IGNORECASE),
            'law': re.compile(r'\b((?:Civil\s+Code|Federal\s+Act|Tax\s+Law|Criminal\s+Code|Constitution|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Law|Act|Code|Statute)))', re.IGNORECASE),
            'date': re.compile(r'\b(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})', re.IGNORECASE),
            'section': re.compile(r'\b(?:section|paragraph|§)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
            'chapter': re.compile(r'\b(?:chapter|titel|title)\s+(\d+|[IVXLCDM]+)', re.IGNORECASE),
        }

        # Ambiguity indicators
        self.ambiguity_indicators = [
            r'\b(?:any|some|certain)\b',
            r'\b(?:might|maybe|perhaps|possibly)\b',
            r'\b(?:generally|usually|typically)\b',
            r'\b(?:or|and/or)\b',
            r'\b(?:etc|and so on)\b',
            r'\b(?:kinds? of|types? of|forms? of)\b',
        ]
        self.ambiguity_patterns = [re.compile(p, re.IGNORECASE)
                                   for p in self.ambiguity_indicators]

    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyze a query for intent, complexity, and entities.

        Args:
            query: The user's query text

        Returns:
            QueryAnalysis object with analysis results
        """
        # Extract entities
        entities = self._extract_entities(query)

        # Determine intent with confidence
        intent, intent_confidence = self._classify_intent(query)

        # Calculate complexity
        complexity = self._assess_complexity(query, entities)

        # Calculate ambiguity score
        ambiguity_score = self._calculate_ambiguity(query)

        # Identify missing context
        missing_context = self._identify_missing_context(query, entities)

        # Extract keywords
        keywords = self._extract_keywords(query)

        # Check for specific references
        has_article = bool(entities.get('article'))
        has_law = bool(entities.get('law'))
        has_date = bool(entities.get('date'))

        analysis = QueryAnalysis(
            query=query,
            intent=intent,
            complexity=complexity,
            confidence=intent_confidence,
            entities=entities,
            ambiguity_score=ambiguity_score,
            missing_context=missing_context,
            keywords=keywords,
            has_article_reference=has_article,
            has_law_reference=has_law,
            has_date_reference=has_date
        )

        logger.debug(f"Query analysis: intent={intent.value}, "
                    f"complexity={complexity.value}, "
                    f"confidence={intent_confidence:.2f}")

        return analysis

    def _classify_intent(self, query: str) -> tuple[QueryIntent, float]:
        """
        Classify the intent of the query.

        Args:
            query: The query text

        Returns:
            Tuple of (intent, confidence)
        """
        query_lower = query.lower()
        scores = {}

        # Priority weights for more specific intents
        intent_priority = {
            QueryIntent.COMPARATIVE: 1.5,  # Boost comparative
            QueryIntent.PROCEDURAL: 1.3,   # Boost procedural
            QueryIntent.TEMPORAL: 1.3,     # Boost temporal
            QueryIntent.RELATIONSHIP: 1.2, # Boost relationship
            QueryIntent.JURISDICTIONAL: 1.1,
            QueryIntent.DEFINITIONAL: 1.0,
            QueryIntent.FACTUAL: 0.9,      # Lower priority for generic factual
            QueryIntent.EXPLORATORY: 0.8,  # Lowest priority
        }

        # Check each intent pattern
        for intent, patterns in self.compiled_patterns.items():
            score = 0.0
            matches = 0
            for pattern in patterns:
                if pattern.search(query_lower):
                    matches += 1
                    score += 1.0

            if matches > 0:
                # Apply priority weighting
                priority = intent_priority.get(intent, 1.0)
                scores[intent] = score * priority

        # If no patterns match, default to exploratory
        if not scores:
            return QueryIntent.EXPLORATORY, 0.5

        # Get the highest scoring intent
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent] / intent_priority.get(best_intent, 1.0)  # Unwrap priority

        # Calculate confidence based on match strength
        total_patterns = len(self.compiled_patterns[best_intent])
        # More generous confidence calculation
        if best_score >= 2:
            confidence = 0.8
        elif best_score >= 1:
            confidence = 0.6 + (best_score - 1) * 0.2
        else:
            confidence = 0.5

        # Boost confidence if only one intent matched
        if len(scores) == 1:
            confidence = min(1.0, confidence * 1.2)

        # Boost for very specific patterns
        if best_intent in [QueryIntent.COMPARATIVE, QueryIntent.PROCEDURAL]:
            confidence = min(1.0, confidence * 1.2)

        return best_intent, confidence

    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract named entities from the query.

        Args:
            query: The query text

        Returns:
            Dictionary of entity types to lists of values
        """
        entities = {}

        for entity_type, pattern in self.entity_patterns.items():
            matches = pattern.findall(query)
            if matches:
                # Clean up matches
                cleaned = []
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    cleaned.append(match.strip())
                if cleaned:
                    entities[entity_type] = cleaned

        return entities

    def _assess_complexity(self, query: str, entities: Dict) -> QueryComplexity:
        """
        Assess the complexity of the query.

        Args:
            query: The query text
            entities: Extracted entities

        Returns:
            QueryComplexity level
        """
        # Factors that increase complexity
        word_count = len(query.split())
        entity_count = sum(len(v) for v in entities.values())
        has_multiple_clauses = len(re.findall(r'[,;]|\band\b|\bor\b', query)) > 2
        has_comparisons = bool(re.search(r'\b(compar|differ|versus|between)\b', query, re.IGNORECASE))
        has_conditions = bool(re.search(r'\b(if|when|unless|except|but)\b', query, re.IGNORECASE))

        complexity_score = 0

        # Word count factor
        if word_count > 30:
            complexity_score += 2
        elif word_count > 15:
            complexity_score += 1

        # Entity factor
        if entity_count > 3:
            complexity_score += 2
        elif entity_count > 1:
            complexity_score += 1

        # Structural factors
        if has_multiple_clauses:
            complexity_score += 1
        if has_comparisons:
            complexity_score += 1
        if has_conditions:
            complexity_score += 1

        # Determine complexity level (adjusted thresholds)
        if complexity_score >= 3:  # Lowered from 4
            return QueryComplexity.COMPLEX
        elif complexity_score >= 2:
            return QueryComplexity.MEDIUM
        else:
            return QueryComplexity.SIMPLE

    def _calculate_ambiguity(self, query: str) -> float:
        """
        Calculate ambiguity score for the query.

        Args:
            query: The query text

        Returns:
            Ambiguity score (0.0 = clear, 1.0 = very ambiguous)
        """
        ambiguity_count = 0

        for pattern in self.ambiguity_patterns:
            if pattern.search(query):
                ambiguity_count += 1.5  # Increased weight

        # Check for vague quantifiers
        vague_quantifiers = r'\b(many|few|several|various|numerous|multiple)\b'
        if re.search(vague_quantifiers, query, re.IGNORECASE):
            ambiguity_count += 1

        # Check for pronouns without clear antecedents
        pronouns = r'\b(it|they|them|this|that|these|those)\b'
        if re.search(pronouns, query, re.IGNORECASE):
            ambiguity_count += 0.5

        # Check for "maybe" specifically (strong ambiguity)
        if 'maybe' in query.lower():
            ambiguity_count += 2

        # Normalize to 0-1 range (adjusted max for higher scores)
        max_ambiguity = len(self.ambiguity_patterns) * 1.5 + 3.5
        ambiguity_score = min(1.0, ambiguity_count / max_ambiguity)

        return ambiguity_score

    def _identify_missing_context(self, query: str, entities: Dict) -> List[str]:
        """
        Identify missing context in the query.

        Args:
            query: The query text
            entities: Extracted entities

        Returns:
            List of missing context types
        """
        missing = []
        query_lower = query.lower()

        # Check for missing time context
        temporal_words = r'\b(recent|current|old|new|latest|previous)\b'
        if re.search(temporal_words, query_lower) and not entities.get('date'):
            missing.append('time_period')

        # Check for missing jurisdiction
        if 'swiss' not in query_lower and 'switzerland' not in query_lower:
            if any(word in query_lower for word in ['law', 'legal', 'statute', 'regulation']):
                missing.append('jurisdiction')

        # Check for missing specificity
        if re.search(r'\b(citizenship|immigration|tax|property)\b', query_lower):
            if not any(word in query_lower for word in ['naturalization', 'visa', 'income', 'real estate']):
                missing.append('specific_type')

        # Check for missing scope
        if re.search(r'\brequirements?\b', query_lower) and not entities.get('law'):
            missing.append('specific_law_or_context')

        return missing

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from the query.

        Args:
            query: The query text

        Returns:
            List of keywords
        """
        # Remove common words
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'must', 'can', 'shall', 'what', 'which', 'who', 'whom', 'whose', 'where',
            'when', 'why', 'how', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
            'she', 'it', 'we', 'they', 'them', 'their', 'me', 'him', 'her', 'us'
        }

        # Extract words
        words = re.findall(r'\b[a-z]+\b', query.lower())

        # Filter out stopwords and short words
        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords[:10]  # Limit to top 10 keywords