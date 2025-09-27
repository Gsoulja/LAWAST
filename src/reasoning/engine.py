"""
Main reasoning engine orchestrator for LAWAST
"""

import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..articulation.apertus_client import ApertusChatClient
from ..retrieval.result_merger import MergedResult
from .models import ReasonedAnswer, ReasoningStep, LegalRule, Citation
from .synthesizer import ResultSynthesizer
from .legal_logic import LegalLogicEngine
from .chain_of_thought import ChainOfThoughtGenerator
from .validator import ConsistencyValidator
from .citation_tracker import CitationTracker
from .confidence_scorer import ConfidenceScorer
from ..context.query_analyzer import QueryAnalyzer

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Orchestrates the complete reasoning process for legal queries.
    Combines multi-source synthesis, legal logic, chain-of-thought reasoning,
    validation, citation tracking, and confidence scoring.
    """

    def __init__(self,
                 apertus_client: Optional[ApertusChatClient] = None,
                 config: Optional[Dict[str, Any]] = None,
                 neo4j_connection = None):
        """
        Initialize the reasoning engine.

        Args:
            apertus_client: Apertus LLM client
            config: Optional configuration dictionary
            neo4j_connection: Optional Neo4j connection for graph lookups
        """
        # Initialize components
        self.synthesizer = ResultSynthesizer()
        self.legal_logic = LegalLogicEngine()
        self.cot_generator = ChainOfThoughtGenerator(apertus_client)
        self.validator = ConsistencyValidator()
        self.citation_tracker = CitationTracker(neo4j_connection=neo4j_connection)
        self.confidence_scorer = ConfidenceScorer()

        # Configuration
        self.config = config or {}
        # Use rule-based reasoning for consistency
        self.enable_llm_reasoning = self.config.get("enable_llm_reasoning", False)
        self.max_reasoning_steps = self.config.get("max_reasoning_steps", 10)
        self.min_confidence_threshold = self.config.get("min_confidence_threshold", 0.3)

        # Initialize query analyzer
        self.query_analyzer = QueryAnalyzer()

        logger.info("Reasoning engine initialized")

    def reason(self,
               query: str,
               rag_results: List[MergedResult],
               context: Optional[Dict[str, Any]] = None) -> ReasonedAnswer:
        """
        Perform complete reasoning process on RAG results.

        Args:
            query: User's question
            rag_results: Results from Triple RAG search
            context: Optional additional context

        Returns:
            ReasonedAnswer with full reasoning chain and citations
        """
        start_time = time.time()
        logger.info(f"Starting reasoning for query: {query[:100]}...")

        try:
            # Step 1: Synthesize multi-source results
            logger.debug("Step 1: Synthesizing results")
            synthesis_result = self.synthesizer.synthesize(rag_results)

            # Convert MergedResults to evidence format
            evidence = self._convert_to_evidence(rag_results)

            # Step 2: Apply legal logic rules
            logger.debug("Step 2: Applying legal logic")
            legal_rules = self.legal_logic.apply_legal_rules(synthesis_result.unified_facts)

            # Step 3: Generate chain-of-thought reasoning
            logger.debug("Step 3: Generating chain-of-thought")
            if self.enable_llm_reasoning:
                reasoning_steps = self.cot_generator.generate_reasoning_chain(
                    query=query,
                    evidence=evidence,
                    legal_rules=legal_rules,
                    synthesis_result={
                        "contradictions": synthesis_result.contradictions,
                        "unified_facts": synthesis_result.unified_facts
                    }
                )
            else:
                # Fallback to rule-based reasoning
                reasoning_steps = self._generate_rule_based_reasoning(
                    query, synthesis_result, legal_rules
                )

            # Step 4: Validate consistency
            logger.debug("Step 4: Validating consistency")
            validation_result = self.validator.validate_consistency(
                evidence=synthesis_result.unified_facts,
                reasoning_steps=reasoning_steps
            )

            # Step 5: Generate preliminary answer (for citation filtering)
            logger.debug("Step 5: Generating preliminary answer")
            # Get preliminary answer from reasoning steps
            preliminary_answer = reasoning_steps[-1].conclusion if reasoning_steps else ""

            # Step 6: Track citations (with answer context for filtering)
            logger.debug("Step 6: Tracking citations")
            citations = self.citation_tracker.track_citations(
                reasoning_steps=reasoning_steps,
                evidence=synthesis_result.unified_facts,
                answer_text=preliminary_answer
            )

            # Step 7: Calculate confidence score
            logger.debug("Step 7: Calculating confidence")
            confidence_score, confidence_factors = self.confidence_scorer.calculate_confidence(
                reasoning_steps=reasoning_steps,
                evidence=synthesis_result.unified_facts,
                citations=citations,
                validation_result=validation_result,
                contradictions=synthesis_result.contradictions
            )

            # Step 8: Generate final answer
            logger.debug("Step 8: Generating final answer")
            final_answer = self._generate_final_answer(
                reasoning_steps=reasoning_steps,
                legal_rules=legal_rules,
                citations=citations,
                confidence=confidence_score
            )

            # Create ReasonedAnswer
            processing_time = time.time() - start_time

            reasoned_answer = ReasonedAnswer(
                answer=final_answer,
                confidence=confidence_score,
                reasoning_steps=reasoning_steps,
                legal_rules_applied=legal_rules,
                evidence_used=synthesis_result.unified_facts,
                citations=citations,
                validation_result=validation_result,
                contradictions=synthesis_result.contradictions,
                query=query,
                processing_time=processing_time,
                timestamp=datetime.now()
            )

            # Log summary
            logger.info(
                f"Reasoning complete: confidence={confidence_score:.2%}, "
                f"steps={len(reasoning_steps)}, citations={len(citations)}, "
                f"time={processing_time:.2f}s"
            )

            return reasoned_answer

        except Exception as e:
            logger.error(f"Error in reasoning engine: {e}", exc_info=True)
            # Return minimal answer on error
            return self._create_error_answer(query, str(e))

    def _convert_to_evidence(self, rag_results: List[MergedResult]) -> List[Dict[str, Any]]:
        """Convert MergedResults to evidence format"""
        evidence = []
        for result in rag_results:
            evidence.append({
                "id": result.node_id,
                "uri": result.uri,
                "type": result.node_type,
                "title": result.title,
                "content": result.content,
                "score": result.combined_score,
                "methods": result.methods,
                "metadata": result.metadata
            })
        return evidence

    def _generate_rule_based_reasoning(self,
                                      query: str,
                                      synthesis_result: Any,
                                      legal_rules: List[LegalRule]) -> List[ReasoningStep]:
        """Generate reasoning without LLM"""
        steps = []
        step_number = 0

        # Step 1: Query understanding
        step_number += 1
        steps.append(ReasoningStep(
            step_number=step_number,
            description="Query Analysis",
            evidence=[],
            conclusion=f"Analyzing: {query}",
            confidence=0.9
        ))

        # Step 2: Evidence synthesis
        if synthesis_result.unified_facts:
            step_number += 1
            steps.append(ReasoningStep(
                step_number=step_number,
                description="Evidence Synthesis",
                evidence=synthesis_result.unified_facts[:3],
                conclusion=f"Found {len(synthesis_result.unified_facts)} relevant legal provisions",
                confidence=0.8
            ))

        # Step 3: Apply legal rules
        for rule in legal_rules[:3]:  # Limit to top 3 rules
            step_number += 1
            steps.append(ReasoningStep(
                step_number=step_number,
                description=f"Apply {rule.rule_type.value} rule",
                evidence=rule.input_facts[:2],
                logic_applied=rule.description,
                conclusion=rule.output_conclusion,
                confidence=rule.confidence
            ))

        # Step 4: Handle contradictions if any
        if synthesis_result.contradictions:
            step_number += 1
            steps.append(ReasoningStep(
                step_number=step_number,
                description="Contradiction Resolution",
                evidence=[],
                conclusion=f"Resolved {len(synthesis_result.contradictions)} contradictions using legal hierarchy",
                confidence=0.7
            ))

        # Step 5: Final conclusion - Generate answer dynamically from evidence
        step_number += 1
        if synthesis_result.unified_facts:
            # Analyze query to determine relevant articles
            query_analysis = self.query_analyzer.analyze(query)
            logger.info(f"Query analysis - intent: {query_analysis.intent.value}, complexity: {query_analysis.complexity.value}")

            # Score and rank facts by relevance to query
            scored_facts = []
            for fact in synthesis_result.unified_facts:
                content = fact.get('content', '')
                title = fact.get('title', '')

                # Extract article number from title if available
                article_num = None
                if title and 'Art.' in title:
                    import re
                    match = re.search(r'Art\.\s*(\d+)', title)
                    if match:
                        article_num = match.group(1)

                # Score relevance
                relevance_score = 0.0
                if article_num:
                    relevance_score = self.query_analyzer.score_article_relevance(
                        query, content, article_num
                    )
                else:
                    # Basic text similarity for non-article content
                    query_terms = set(query.lower().split())
                    content_terms = set(content.lower().split()) if content else set()
                    if query_terms:
                        relevance_score = len(query_terms & content_terms) / len(query_terms)

                scored_facts.append((fact, relevance_score))

            # Sort by relevance score
            scored_facts.sort(key=lambda x: x[1], reverse=True)

            # Log relevance scores for debugging
            if scored_facts:
                logger.info(f"Top 3 article relevance scores:")
                for fact, score in scored_facts[:3]:
                    title = fact.get('title', 'Unknown')
                    logger.info(f"  {title}: {score:.3f}")

            # Get top relevant facts
            top_facts = [fact for fact, score in scored_facts[:3] if score > 0.1]

            if top_facts:
                # Extract and combine relevant content from evidence
                answer_parts = []
                article_refs = []

                for fact in top_facts:
                    content = fact.get('content', '')
                    title = fact.get('title', '')

                    # Add article reference if available
                    if title and 'Art.' in title:
                        article_refs.append(title)

                    # Extract meaningful content (limit length for clarity)
                    if content:
                        # Take a reasonable portion of content
                        content_excerpt = content[:400].strip()
                        # Ensure we end at a sentence boundary if possible
                        last_period = content_excerpt.rfind('.')
                        if last_period > 200:
                            content_excerpt = content_excerpt[:last_period + 1]

                        answer_parts.append(content_excerpt)

                # Build the conclusion from the evidence
                if answer_parts:
                    # Combine the evidence into a coherent answer
                    if len(answer_parts) == 1:
                        conclusion = answer_parts[0]
                    else:
                        # Multiple pieces of evidence - combine them
                        conclusion = " ".join(answer_parts[:2])  # Use top 2 to avoid overly long answers

                    # Add source reference if available
                    if article_refs and article_refs[0]:
                        if not conclusion.startswith(article_refs[0]):
                            conclusion = f"According to {article_refs[0]}: {conclusion}"
                else:
                    # No content found in evidence
                    conclusion = "Unable to extract sufficient information from the available evidence."

                # Ensure answer is clean and complete
                conclusion = conclusion.replace("  ", " ").strip()
                if not conclusion.endswith('.'):
                    conclusion += '.'

            else:
                conclusion = "No relevant evidence found to answer this question."
        else:
            conclusion = "Insufficient evidence for definitive answer"

        steps.append(ReasoningStep(
            step_number=step_number,
            description="Final Conclusion",
            evidence=synthesis_result.unified_facts[:1] if synthesis_result.unified_facts else [],
            conclusion=conclusion,
            confidence=0.7
        ))

        return steps

    def _generate_final_answer(self,
                              reasoning_steps: List[ReasoningStep],
                              legal_rules: List[LegalRule],
                              citations: List[Citation],
                              confidence: float) -> str:
        """Generate the final answer text with structured format"""
        # Get conclusion from last reasoning step
        if reasoning_steps:
            last_step = reasoning_steps[-1]
            base_answer = last_step.conclusion

            # Remove evidence markers (E1, E2, etc.) from the answer
            import re
            # Pattern to match (E1), (E1, E2), etc.
            base_answer = re.sub(r'\s*\([E]\d+(?:,\s*[E]\d+)*\)', '', base_answer)
            # Also remove standalone E1, E2 references
            base_answer = re.sub(r'\b[E]\d+\b', '', base_answer)
            # Clean up any double spaces left behind
            base_answer = re.sub(r'\s+', ' ', base_answer).strip()
        else:
            base_answer = "Unable to provide a definitive answer based on available evidence."

        # Add legal rule conclusions if significant
        if legal_rules:
            rule_conclusions = []
            for rule in legal_rules[:2]:  # Top 2 rules
                if rule.confidence > 0.7:
                    rule_conclusions.append(rule.output_conclusion)

            if rule_conclusions:
                base_answer = f"{base_answer}\n\nLegal Analysis: {'; '.join(rule_conclusions)}"

        # Add confidence qualifier if low
        if confidence < 0.5:
            base_answer = f"{base_answer}\n\nNote: This answer has lower confidence due to limited or conflicting evidence."

        # Format the structured response
        formatted_answer = f"Answer: {base_answer}"

        # Add citations in the required format
        if citations:
            # Format citations properly
            citation_strings = []
            for citation in citations[:10]:  # Check more citations to find articles
                try:
                    # First check if citation has article attribute
                    if hasattr(citation, 'article') and citation.article:
                        # Format as Art. X BV for Bundesverfassung
                        if hasattr(citation, 'sr_number') and citation.sr_number == "101":
                            citation_strings.append(f"Art. {citation.article} BV")
                        else:
                            citation_strings.append(f"Art. {citation.article}")
                    else:
                        citation_str = str(citation)
                        # Skip paragraph text (usually starts with "Para" or is too long)
                        if citation_str.startswith("Para") or len(citation_str) > 80:
                            continue
                        # Skip if citation string is invalid
                        if not citation_str or citation_str == "Unknown citation":
                            continue
                        # Only add if it looks like an article reference
                        if "Art." in citation_str:
                            citation_strings.append(citation_str)
                except Exception as e:
                    logger.debug(f"Error formatting citation: {e}")
                    continue

            # Remove duplicates while preserving order
            seen = set()
            unique_citations = []
            for c in citation_strings[:5]:  # Limit to 5 unique citations
                if c and c not in seen:  # Check c is not None
                    seen.add(c)
                    unique_citations.append(c)

            if unique_citations:
                # Filter out any None values before joining
                valid_citations = [c for c in unique_citations if c]
                if valid_citations:
                    formatted_answer = f"{formatted_answer}\nCitations: {', '.join(valid_citations)}"
            else:
                # If no proper citations found, indicate that
                formatted_answer = f"{formatted_answer}\nCitations: See constitutional provisions referenced above"

        # Add confidence score
        formatted_answer = f"{formatted_answer}\nConfidence: {confidence:.2f}"

        return formatted_answer

    def _create_error_answer(self, query: str, error_msg: str) -> ReasonedAnswer:
        """Create a minimal answer when reasoning fails"""
        error_step = ReasoningStep(
            step_number=1,
            description="Error in reasoning process",
            evidence=[],
            conclusion=f"Unable to complete reasoning: {error_msg}",
            confidence=0.0
        )

        return ReasonedAnswer(
            answer=f"I encountered an error while processing your query: {error_msg}",
            confidence=0.0,
            reasoning_steps=[error_step],
            legal_rules_applied=[],
            evidence_used=[],
            citations=[],
            query=query,
            timestamp=datetime.now()
        )

    def explain_reasoning(self, reasoned_answer: ReasonedAnswer) -> str:
        """
        Generate a human-readable explanation of the reasoning.

        Args:
            reasoned_answer: The reasoned answer to explain

        Returns:
            Formatted explanation string
        """
        explanation = []

        # Header
        explanation.append("=" * 60)
        explanation.append("LEGAL REASONING EXPLANATION")
        explanation.append("=" * 60)
        explanation.append(f"\nQuery: {reasoned_answer.query}\n")

        # Reasoning steps
        explanation.append("REASONING PROCESS:")
        explanation.append("-" * 40)
        for step in reasoned_answer.reasoning_steps:
            explanation.append(f"\nStep {step.step_number}: {step.description}")
            if step.logic_applied:
                explanation.append(f"   Logic: {step.logic_applied}")
            if step.conclusion:
                explanation.append(f"   → {step.conclusion}")
            if step.citations:
                cit_strs = [str(c) for c in step.citations[:2]]
                explanation.append(f"   Sources: {', '.join(cit_strs)}")
            explanation.append(f"   Confidence: {step.confidence:.1%}")

        # Legal rules applied
        if reasoned_answer.legal_rules_applied:
            explanation.append("\n\nLEGAL RULES APPLIED:")
            explanation.append("-" * 40)
            for rule in reasoned_answer.legal_rules_applied:
                explanation.append(f"• {rule.rule_type.value.upper()}: {rule.description}")
                explanation.append(f"  → {rule.output_conclusion}")

        # Contradictions resolved
        if reasoned_answer.contradictions:
            explanation.append("\n\nCONTRADICTIONS RESOLVED:")
            explanation.append("-" * 40)
            for contradiction in reasoned_answer.contradictions:
                explanation.append(f"• {contradiction.fact_type}: {contradiction.resolution_strategy}")

        # Citations
        if reasoned_answer.citations:
            explanation.append("\n\nSOURCES CITED:")
            explanation.append("-" * 40)
            bibliography = self.citation_tracker.generate_bibliography(reasoned_answer.citations)
            explanation.append(bibliography)

        # Confidence assessment
        explanation.append("\n\nCONFIDENCE ASSESSMENT:")
        explanation.append("-" * 40)
        confidence_level = self.confidence_scorer.get_confidence_level(reasoned_answer.confidence)
        explanation.append(f"Overall Confidence: {confidence_level} ({reasoned_answer.confidence:.1%})")

        if reasoned_answer.validation_result:
            if reasoned_answer.validation_result.is_consistent:
                explanation.append("✓ Evidence is consistent")
            else:
                explanation.append("⚠ Some inconsistencies detected")

        # Final answer
        explanation.append("\n\nFINAL ANSWER:")
        explanation.append("=" * 60)
        explanation.append(reasoned_answer.answer)
        explanation.append("=" * 60)

        return "\n".join(explanation)