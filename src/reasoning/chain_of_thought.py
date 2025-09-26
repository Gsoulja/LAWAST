"""
Chain-of-thought reasoning generator using Apertus LLM
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..articulation.apertus_client import ApertusChatClient
from .models import ReasoningStep, LegalRule, Citation

logger = logging.getLogger(__name__)


class ChainOfThoughtGenerator:
    """
    Generates step-by-step reasoning chains using Apertus LLM.
    Validates each step against retrieved facts to prevent hallucination.
    """

    def __init__(self, apertus_client: Optional[ApertusChatClient] = None):
        """
        Initialize the chain-of-thought generator.

        Args:
            apertus_client: Apertus LLM client instance
        """
        self.llm = apertus_client or ApertusChatClient()

    def generate_reasoning_chain(self,
                                query: str,
                                evidence: List[Dict[str, Any]],
                                legal_rules: List[LegalRule],
                                synthesis_result: Dict[str, Any] = None) -> List[ReasoningStep]:
        """
        Generate a chain-of-thought reasoning for the query.

        Args:
            query: User's question
            evidence: Retrieved evidence from RAG
            legal_rules: Applied legal rules
            synthesis_result: Synthesis results with contradictions

        Returns:
            List of reasoning steps
        """
        # Build context for LLM
        context = self._build_context(evidence, legal_rules, synthesis_result)

        # Create structured prompt
        prompt = self._create_reasoning_prompt(query, context)

        # Generate reasoning with LLM
        try:
            reasoning_text = self.llm.chat(
                message=prompt,
                system_prompt=self._get_system_prompt(),
                max_tokens=1024,
                temperature=0.3  # Lower temperature for more consistent reasoning
            )

            # Parse reasoning into steps
            steps = self._parse_reasoning_steps(reasoning_text, evidence)

            # Validate steps against facts
            validated_steps = self._validate_steps(steps, evidence)

            return validated_steps

        except Exception as e:
            logger.error(f"Error generating reasoning chain: {e}")
            # Fallback to basic reasoning
            return self._generate_fallback_reasoning(query, evidence, legal_rules)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for legal reasoning"""
        return """You are a Swiss legal reasoning assistant. Your task is to generate clear,
step-by-step legal reasoning based ONLY on the provided evidence and legal rules.

Rules:
1. Each reasoning step must cite specific evidence
2. Apply Swiss legal principles correctly
3. Be precise and factual
4. Never invent information not in the evidence
5. Format your response as numbered steps
6. Each step should have: description, evidence used, and conclusion

Use this format:
Step 1: [Description]
Evidence: [Specific evidence citation]
Conclusion: [What this means]

Step 2: [Description]
Evidence: [Specific evidence citation]
Conclusion: [What this means]

Final Answer: [Clear, concise answer to the question]
"""

    def _build_context(self,
                       evidence: List[Dict[str, Any]],
                       legal_rules: List[LegalRule],
                       synthesis_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """Build context for reasoning"""
        context = {
            "evidence_count": len(evidence),
            "evidence_summary": self._summarize_evidence(evidence),
            "legal_rules_applied": [
                {
                    "type": rule.rule_type.value,
                    "description": rule.description,
                    "conclusion": rule.output_conclusion
                }
                for rule in legal_rules
            ] if legal_rules else []
        }

        # Add contradiction information if present
        if synthesis_result and "contradictions" in synthesis_result:
            context["contradictions"] = [
                {
                    "type": c.fact_type,
                    "resolution": c.resolution_strategy,
                    "resolved_value": str(c.resolved_value)[:100]
                }
                for c in synthesis_result["contradictions"]
            ]

        return context

    def _summarize_evidence(self, evidence: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Summarize evidence for LLM context"""
        summaries = []
        for i, fact in enumerate(evidence[:10]):  # Limit to top 10 for context length
            summary = {
                "id": f"E{i+1}",
                "type": fact.get("type", "Unknown"),
                "uri": fact.get("uri", ""),
                "title": fact.get("title", "")[:100] if fact.get("title") else "",
                "key_content": fact.get("content", "")[:200] if fact.get("content") else ""
            }
            summaries.append(summary)
        return summaries

    def _create_reasoning_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Create the reasoning prompt for LLM"""
        prompt_parts = [
            f"Question: {query}\n",
            "\nAvailable Evidence:",
        ]

        # Add evidence summaries
        for evidence in context["evidence_summary"]:
            prompt_parts.append(
                f"- {evidence['id']}: {evidence['type']} - {evidence['uri']} - {evidence['title']}"
            )
            if evidence['key_content']:
                prompt_parts.append(f"  Content: {evidence['key_content']}")

        # Add legal rules if any
        if context["legal_rules_applied"]:
            prompt_parts.append("\nLegal Rules Applied:")
            for rule in context["legal_rules_applied"]:
                prompt_parts.append(f"- {rule['type']}: {rule['description']}")
                prompt_parts.append(f"  Conclusion: {rule['conclusion']}")

        # Add contradictions if any
        if context.get("contradictions"):
            prompt_parts.append("\nContradictions Resolved:")
            for contradiction in context["contradictions"]:
                prompt_parts.append(f"- {contradiction['type']}: {contradiction['resolution']}")

        prompt_parts.append(
            "\nGenerate step-by-step legal reasoning to answer the question. "
            "Cite specific evidence (E1, E2, etc.) in each step."
        )

        return "\n".join(prompt_parts)

    def _parse_reasoning_steps(self,
                               reasoning_text: str,
                               evidence: List[Dict[str, Any]]) -> List[ReasoningStep]:
        """Parse LLM output into reasoning steps"""
        steps = []
        current_step = None
        step_number = 0

        lines = reasoning_text.split("\n")
        for line in lines:
            line = line.strip()

            # Detect new step
            if line.lower().startswith("step "):
                if current_step:
                    steps.append(current_step)
                step_number += 1
                # Extract step description
                description = line.split(":", 1)[1].strip() if ":" in line else line
                current_step = ReasoningStep(
                    step_number=step_number,
                    description=description,
                    evidence=[],
                    citations=[]
                )

            # Extract evidence references
            elif line.lower().startswith("evidence:") and current_step:
                evidence_text = line.split(":", 1)[1].strip()
                # Find referenced evidence
                evidence_refs = self._extract_evidence_references(evidence_text, evidence)
                current_step.evidence.extend(evidence_refs)

            # Extract conclusion
            elif line.lower().startswith("conclusion:") and current_step:
                conclusion = line.split(":", 1)[1].strip()
                current_step.conclusion = conclusion

            # Extract final answer
            elif line.lower().startswith("final answer:"):
                if current_step:
                    steps.append(current_step)
                # Create final conclusion step
                final_answer = line.split(":", 1)[1].strip()
                steps.append(ReasoningStep(
                    step_number=step_number + 1,
                    description="Final Conclusion",
                    evidence=[],
                    conclusion=final_answer
                ))
                break

        # Add last step if not added
        if current_step and current_step not in steps:
            steps.append(current_step)

        return steps

    def _extract_evidence_references(self,
                                    evidence_text: str,
                                    evidence_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract referenced evidence from text"""
        referenced = []

        # Look for E1, E2, etc. references
        import re
        pattern = r'E(\d+)'
        matches = re.findall(pattern, evidence_text)

        for match in matches:
            idx = int(match) - 1
            if 0 <= idx < len(evidence_list):
                referenced.append(evidence_list[idx])

        # Also look for SR number references
        sr_pattern = r'SR\s*(\d{3}(?:\.\d+)*)'
        sr_matches = re.findall(sr_pattern, evidence_text)

        for sr_number in sr_matches:
            for evidence in evidence_list:
                if sr_number in evidence.get("uri", ""):
                    if evidence not in referenced:
                        referenced.append(evidence)

        return referenced

    def _validate_steps(self,
                       steps: List[ReasoningStep],
                       evidence: List[Dict[str, Any]]) -> List[ReasoningStep]:
        """Validate reasoning steps against evidence"""
        validated = []

        for step in steps:
            # Check if step references actual evidence
            if step.evidence or step.step_number == len(steps):  # Final conclusion may not have evidence
                # Extract citations from evidence
                for fact in step.evidence:
                    citation = self._extract_citation(fact)
                    if citation:
                        step.citations.append(citation)

                # Calculate confidence based on evidence support
                if step.evidence:
                    step.confidence = min(1.0, len(step.evidence) * 0.3 + 0.4)
                else:
                    step.confidence = 0.5

                validated.append(step)
            else:
                # Step without evidence - lower confidence
                step.confidence = 0.3
                validated.append(step)

        return validated

    def _extract_citation(self, fact: Dict[str, Any]) -> Optional[Citation]:
        """Extract citation from a fact"""
        # Try to extract SR number from URI
        uri = fact.get("uri", "")
        sr_pattern = r'SR\s*(\d{3}(?:\.\d+)*)'
        sr_match = re.search(sr_pattern, uri)

        if sr_match:
            sr_number = sr_match.group(1)

            # Extract article number if present
            article = None
            art_pattern = r'[Aa]rt(?:icle)?\.?\s*(\d+[a-z]?)'
            art_match = re.search(art_pattern, uri)
            if art_match:
                article = art_match.group(1)

            return Citation(
                sr_number=sr_number,
                article=article,
                title=fact.get("title"),
                ast_path=fact.get("metadata", {}).get("ast_path") if fact.get("metadata") else None
            )

        return None

    def _generate_fallback_reasoning(self,
                                    query: str,
                                    evidence: List[Dict[str, Any]],
                                    legal_rules: List[LegalRule]) -> List[ReasoningStep]:
        """Generate basic reasoning without LLM"""
        steps = []

        # Step 1: Query analysis
        steps.append(ReasoningStep(
            step_number=1,
            description="Query Analysis",
            evidence=[],
            conclusion=f"Analyzing legal question: {query}",
            confidence=0.8
        ))

        # Step 2: Evidence review
        if evidence:
            steps.append(ReasoningStep(
                step_number=2,
                description="Evidence Review",
                evidence=evidence[:3],  # Top 3 evidence
                conclusion=f"Found {len(evidence)} relevant legal provisions",
                confidence=0.7
            ))

        # Step 3: Legal rules
        if legal_rules:
            for i, rule in enumerate(legal_rules, start=3):
                steps.append(ReasoningStep(
                    step_number=i,
                    description=f"Apply {rule.rule_type.value} rule",
                    evidence=[],
                    logic_applied=rule.description,
                    conclusion=rule.output_conclusion,
                    confidence=rule.confidence
                ))

        # Final step: Conclusion
        final_step_num = len(steps) + 1
        if evidence:
            top_fact = evidence[0]
            conclusion = f"Based on the evidence, particularly {top_fact.get('uri', 'the relevant provision')}"
        else:
            conclusion = "Unable to provide definitive answer without sufficient evidence"

        steps.append(ReasoningStep(
            step_number=final_step_num,
            description="Conclusion",
            evidence=evidence[:1] if evidence else [],
            conclusion=conclusion,
            confidence=0.6
        ))

        return steps