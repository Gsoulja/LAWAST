#!/usr/bin/env python3
"""
Court Decision Formatter for Web UI
Formats court decisions with proper HTML links and styling
"""

from typing import Dict, List, Any, Optional


class CourtDecisionFormatter:
    """Formats court decisions for display in web UI"""

    @staticmethod
    def format_for_web(court_decisions: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format court decisions for web display with HTML links.

        Args:
            court_decisions: Dictionary of court decisions by article

        Returns:
            HTML formatted string
        """
        if not court_decisions:
            return ""

        html = """
<div class="court-decisions">
    <h3>📚 Relevant Court Decisions</h3>
"""

        for article_ref, decisions in court_decisions.items():
            html += f"""
    <div class="article-section">
        <h4>{article_ref}</h4>
        <ul class="decision-list">
"""
            for decision in decisions[:3]:  # Limit to 3 per article
                html += f"""
            <li class="decision-item">
                <strong>{decision.get('id', 'N/A')}</strong> -
                {decision.get('court', 'Court')}
                <span class="date">({decision.get('date', 'N/A')})</span>
                <br>
                <em>{decision.get('title', '')[:150]}{'...' if len(decision.get('title', '')) > 150 else ''}</em>
                <br>
                <a href="{decision.get('url', '#')}" target="_blank" class="decision-link">
                    🔗 View Full Decision
                </a>
            </li>
"""
            html += """
        </ul>
    </div>
"""

        html += """
</div>

<style>
.court-decisions {
    margin-top: 20px;
    padding: 15px;
    background-color: #f8f9fa;
    border-radius: 8px;
    border-left: 4px solid #007bff;
}

.court-decisions h3 {
    color: #333;
    margin-bottom: 15px;
}

.article-section {
    margin-bottom: 20px;
}

.article-section h4 {
    color: #495057;
    margin-bottom: 10px;
    font-weight: 600;
}

.decision-list {
    list-style: none;
    padding-left: 0;
}

.decision-item {
    padding: 12px;
    margin-bottom: 10px;
    background: white;
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.decision-item strong {
    color: #007bff;
}

.decision-item .date {
    color: #6c757d;
    font-size: 0.9em;
}

.decision-item em {
    display: block;
    margin: 5px 0;
    color: #495057;
    font-size: 0.95em;
}

.decision-link {
    color: #007bff;
    text-decoration: none;
    font-weight: 500;
    display: inline-block;
    margin-top: 5px;
}

.decision-link:hover {
    text-decoration: underline;
    color: #0056b3;
}
</style>
"""
        return html

    @staticmethod
    def format_for_markdown(court_decisions: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format court decisions for markdown display.

        Args:
            court_decisions: Dictionary of court decisions by article

        Returns:
            Markdown formatted string
        """
        if not court_decisions:
            return ""

        md = "\n## 📚 Relevant Court Decisions\n\n"

        for article_ref, decisions in court_decisions.items():
            md += f"### {article_ref}\n\n"

            for decision in decisions[:3]:
                decision_id = decision.get('id', 'N/A')
                court = decision.get('court', 'Court')
                date = decision.get('date', 'N/A')
                title = decision.get('title', '')[:150]
                if len(decision.get('title', '')) > 150:
                    title += '...'
                url = decision.get('url', '')

                md += f"**{decision_id}** - {court} ({date})\n"
                if title:
                    md += f"*{title}*\n"
                if decision.get('excerpt'):
                    excerpt = decision['excerpt'][:200]
                    if len(decision['excerpt']) > 200:
                        excerpt += '...'
                    md += f"> {excerpt}\n"
                if url:
                    md += f"[🔗 View Full Decision]({url})\n"
                md += "\n"

        return md

    @staticmethod
    def format_for_terminal(court_decisions: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format court decisions for terminal/console display.

        Args:
            court_decisions: Dictionary of court decisions by article

        Returns:
            Plain text formatted string
        """
        if not court_decisions:
            return ""

        text = "\n" + "="*60 + "\n"
        text += "📚 RELEVANT COURT DECISIONS\n"
        text += "="*60 + "\n"

        for article_ref, decisions in court_decisions.items():
            text += f"\n{article_ref}:\n"
            text += "-" * 40 + "\n"

            for i, decision in enumerate(decisions[:3], 1):
                text += f"{i}. {decision.get('id', 'N/A')}\n"
                text += f"   Court: {decision.get('court', 'N/A')}\n"
                text += f"   Date: {decision.get('date', 'N/A')}\n"

                title = decision.get('title', '')
                if title:
                    text += f"   Title: {title[:80]}\n"
                    if len(title) > 80:
                        text += f"          {title[80:160]}...\n"

                if decision.get('excerpt'):
                    text += f"   Excerpt: \"{decision['excerpt'][:100]}...\"\n"

                if decision.get('url'):
                    text += f"   Link: {decision['url']}\n"

                text += "\n"

        return text

    @staticmethod
    def create_citation_links(text: str, court_decisions: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Add hyperlinks to article citations in the text.

        Args:
            text: The answer text with article citations
            court_decisions: Dictionary of court decisions by article

        Returns:
            Text with linked citations
        """
        import re

        # Pattern to find article citations
        pattern = r"(Art\.\s*\d+[a-z]?\s+[A-Z]+)"

        def replace_with_link(match):
            citation = match.group(1)

            # Check if we have court decisions for this citation
            for article_ref in court_decisions.keys():
                if citation in article_ref:
                    # Get the first decision URL as the link
                    if court_decisions[article_ref]:
                        first_decision = court_decisions[article_ref][0]
                        url = first_decision.get('url', '')
                        if url:
                            return f"[{citation}]({url})"

            return citation  # Return unchanged if no link available

        return re.sub(pattern, replace_with_link, text)