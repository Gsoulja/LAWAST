"""
AST Path Builder for LAWAST

Builds hierarchical paths for AST nodes in the knowledge graph.
Paths represent the complete position of a node in the document tree.

Example paths:
- Law: "/domain_1/section_101/law_101"
- Article: "/domain_1/section_101/law_101/art_10"
- Paragraph: "/domain_1/section_101/law_101/art_10/para_1"
- Subpoint: "/domain_1/section_101/law_101/art_10/para_1/subpoint_a"
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ASTPathComponent:
    """Represents a single component in an AST path"""
    level: int  # 0-8 (Corpus to Subpoint)
    type: str  # "domain", "law", "article", "paragraph", etc.
    identifier: str  # "101", "10", "1", "a", etc.


class ASTPathBuilder:
    """
    Builds hierarchical AST paths for legal document nodes.

    Supports 8 levels:
    0. Corpus (root)
    1. Domain
    2. Book
    3. Chapter
    4. Section
    5. Law
    6. Article
    7. Paragraph
    8. Subpoint
    """

    # Level definitions
    LEVEL_NAMES = {
        0: "corpus",
        1: "domain",
        2: "book",
        3: "chapter",
        4: "section",
        5: "law",
        6: "article",
        7: "paragraph",
        8: "subpoint"
    }

    def __init__(self):
        """Initialize the path builder"""
        pass

    def build_law_path(self, sr_number: str, section_number: Optional[str] = None,
                      domain_number: Optional[str] = None) -> str:
        """
        Build AST path for a Law node.

        Args:
            sr_number: SR classification number (e.g., "101")
            section_number: Section number (optional)
            domain_number: Domain number (optional)

        Returns:
            AST path string
        """
        components = []

        # Domain (from SR first digit)
        if domain_number:
            components.append(f"domain_{domain_number}")
        elif sr_number:
            # Extract domain from SR number (first digit)
            domain = sr_number.split('.')[0][0] if sr_number else "0"
            components.append(f"domain_{domain}")

        # Section (if provided)
        if section_number:
            components.append(f"section_{section_number}")

        # Law
        sr_clean = sr_number.replace('.', '_')
        components.append(f"law_{sr_clean}")

        return "/" + "/".join(components)

    def build_article_path(self, law_path: str, article_number: str) -> str:
        """
        Build AST path for an Article node.

        Args:
            law_path: Parent law's AST path
            article_number: Article number (e.g., "10", "10a", "335b")

        Returns:
            AST path string
        """
        article_clean = article_number.replace(' ', '_')
        return f"{law_path}/art_{article_clean}"

    def build_paragraph_path(self, article_path: str, paragraph_number: str) -> str:
        """
        Build AST path for a Paragraph node.

        Args:
            article_path: Parent article's AST path
            paragraph_number: Paragraph number (e.g., "1", "2")

        Returns:
            AST path string
        """
        return f"{article_path}/para_{paragraph_number}"

    def build_subpoint_path(self, paragraph_path: str, subpoint_letter: str) -> str:
        """
        Build AST path for a Subpoint node.

        Args:
            paragraph_path: Parent paragraph's AST path
            subpoint_letter: Subpoint letter (e.g., "a", "b", "c")

        Returns:
            AST path string
        """
        return f"{paragraph_path}/subpoint_{subpoint_letter}"

    def build_complete_path(self, components: List[ASTPathComponent]) -> str:
        """
        Build complete AST path from components.

        Args:
            components: List of path components in hierarchical order

        Returns:
            Complete AST path string
        """
        if not components:
            return "/"

        # Sort by level to ensure correct order
        sorted_components = sorted(components, key=lambda x: x.level)

        # Build path
        path_parts = []
        for comp in sorted_components:
            path_parts.append(f"{comp.type}_{comp.identifier}")

        return "/" + "/".join(path_parts)

    def parse_path(self, path: str) -> List[ASTPathComponent]:
        """
        Parse an AST path into components.

        Args:
            path: AST path string

        Returns:
            List of path components
        """
        if not path or path == "/":
            return []

        # Remove leading slash and split
        parts = path.lstrip('/').split('/')

        components = []
        for i, part in enumerate(parts):
            # Split type and identifier
            if '_' in part:
                type_part, identifier = part.split('_', 1)

                # Map type to level
                level = self._get_level_from_type(type_part)

                components.append(ASTPathComponent(
                    level=level,
                    type=type_part,
                    identifier=identifier
                ))

        return components

    def _get_level_from_type(self, type_name: str) -> int:
        """Get AST level number from type name"""
        for level, name in self.LEVEL_NAMES.items():
            if name == type_name:
                return level
        return -1

    def get_parent_path(self, path: str) -> Optional[str]:
        """
        Get parent path from a given path.

        Args:
            path: Current AST path

        Returns:
            Parent path or None if at root
        """
        if not path or path == "/":
            return None

        # Remove trailing slash if present
        path = path.rstrip('/')

        # Find last slash
        last_slash = path.rfind('/')
        if last_slash <= 0:
            return "/"

        return path[:last_slash]

    def get_level_from_path(self, path: str) -> int:
        """
        Determine AST level from path depth.

        Args:
            path: AST path string

        Returns:
            Level number (0-8)
        """
        if not path or path == "/":
            return 0

        # Count components
        components = path.lstrip('/').split('/')
        return len(components)

    def normalize_identifier(self, identifier: str) -> str:
        """
        Normalize an identifier for use in paths.

        Args:
            identifier: Raw identifier (e.g., "101.1", "10 a")

        Returns:
            Normalized identifier (e.g., "101_1", "10_a")
        """
        # Replace dots and spaces with underscores
        return identifier.replace('.', '_').replace(' ', '_')

    def build_uri_from_path(self, path: str) -> str:
        """
        Build a URI from an AST path.

        Args:
            path: AST path

        Returns:
            URI string
        """
        # Convert path to URI-friendly format
        return "ast:" + path.replace('/', ':')


# Convenience function
def build_ast_path(node_type: str, parent_path: Optional[str] = None,
                   identifier: str = "", **kwargs) -> str:
    """
    Convenience function to build AST paths.

    Args:
        node_type: Type of node ("law", "article", "paragraph", "subpoint")
        parent_path: Parent node's AST path
        identifier: Node identifier (SR number, article number, etc.)
        **kwargs: Additional parameters (sr_number, section_number, etc.)

    Returns:
        AST path string
    """
    builder = ASTPathBuilder()

    if node_type == "law":
        return builder.build_law_path(
            sr_number=identifier,
            section_number=kwargs.get('section_number'),
            domain_number=kwargs.get('domain_number')
        )
    elif node_type == "article":
        return builder.build_article_path(parent_path or "", identifier)
    elif node_type == "paragraph":
        return builder.build_paragraph_path(parent_path or "", identifier)
    elif node_type == "subpoint":
        return builder.build_subpoint_path(parent_path or "", identifier)
    else:
        raise ValueError(f"Unknown node type: {node_type}")