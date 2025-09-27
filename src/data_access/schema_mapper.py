"""
Schema Mapper and Validator for LAWAST

Validates and maps properties against the graph schema definitions.
Ensures all nodes comply with schema requirements while maintaining
backward compatibility.
"""

import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from .graph_schema import (
    LawNode, ArticleNode, ParagraphNode,
    VersionNode, ActNode, SubpointNode,
    NodeLabels
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of schema validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    mapped_properties: Dict[str, Any] = field(default_factory=dict)


class SchemaPropertyMapper:
    """
    Maps and validates properties against LAWAST graph schema.

    Features:
    - Property validation against schema
    - Name mapping for compatibility
    - Default value injection
    - Strict mode for full compliance
    """

    def __init__(self, strict_mode: bool = False):
        """
        Initialize the schema mapper.

        Args:
            strict_mode: If True, enforce all required fields strictly
        """
        self.strict_mode = strict_mode

        # Define required fields for each node type
        self.required_fields = {
            'Law': ['uri', 'sr_number'],
            'Article': ['uri', 'law_uri', 'number'],
            'Paragraph': ['uri', 'article_uri', 'number', 'text'],
            'Version': ['uri', 'law_uri', 'date_applicable'],
            'Act': ['uri', 'type_document'],
            'Subpoint': ['uri', 'paragraph_uri', 'letter', 'text']
        }

        # Define optional fields with defaults
        self.optional_defaults = {
            'Law': {
                'ast_level': 5,
                'type': 'Law',
                'in_force': True,
                'status': 'unknown',
                'language': 'de',
                'parent_uri': None,
                'parent_id': None,
                'title_de': None,
                'title_fr': None,
                'title_it': None,
                'title_rm': None,
                'title_en': None,
                'date_document': None,
                'date_entry_in_force': None,
                'date_no_longer_in_force': None,
                'date_modified': None,
                'in_force_status': None,
                'basic_act': None,
                'classified_by_taxonomy': None,
                'type_document': None,
                'embedding': None
            },
            'Article': {
                'ast_level': 6,
                'title': None,
                'content_uri': None,
                'section': None,
                'chapter': None,
                'parent_id': None,
                'position': None,
                'content_full': None,
                'embedding': None
            },
            'Paragraph': {
                'ast_level': 7,
                'language': 'de',
                'position': None,
                'parent_id': None,
                'word_count': 0,
                'has_subpoints': False,
                'embedding': None
            }
        }

        # Property name mappings for backward compatibility
        self.property_mappings = {
            'Law': {
                # Map old names to new names
                'dateDocument': 'date_document',
                'dateEntryInForce': 'date_entry_in_force',
                'dateNoLongerInForce': 'date_no_longer_in_force',
                'inForce': 'in_force',
                'basicAct': 'basic_act',
                'typeDocument': 'type_document'
            },
            'Article': {
                'content': 'content_full',
                'normalized_number': 'number_normalized'
            },
            'Paragraph': {
                'lang': 'language',
                'has_subpoint': 'has_subpoints'
            }
        }

    def validate_and_map(self, node_type: str, properties: Dict[str, Any]) -> ValidationResult:
        """
        Validate properties against schema and return mapped properties.

        Args:
            node_type: Type of node (Law, Article, Paragraph, etc.)
            properties: Raw properties to validate

        Returns:
            ValidationResult with validation status and mapped properties
        """
        result = ValidationResult(valid=True)

        # Check if node type is valid
        if not self._is_valid_node_type(node_type):
            result.valid = False
            result.errors.append(f"Invalid node type: {node_type}")
            return result

        # Apply property name mappings
        mapped = self._apply_property_mappings(node_type, properties)

        # Validate required fields
        missing = self._check_required_fields(node_type, mapped)
        if missing:
            if self.strict_mode:
                result.valid = False
                result.errors.extend([f"Missing required field: {field}" for field in missing])
            else:
                result.warnings.extend([f"Missing required field: {field}" for field in missing])

        # Apply defaults for optional fields
        mapped = self._apply_defaults(node_type, mapped)

        # Validate data types
        type_errors = self._validate_data_types(node_type, mapped)
        if type_errors:
            result.errors.extend(type_errors)
            if self.strict_mode:
                result.valid = False

        # Additional validations
        custom_errors = self._custom_validations(node_type, mapped)
        if custom_errors:
            result.warnings.extend(custom_errors)

        result.mapped_properties = mapped
        return result

    def _is_valid_node_type(self, node_type: str) -> bool:
        """Check if node type is valid"""
        valid_types = [label.value for label in NodeLabels]
        return node_type in valid_types

    def _apply_property_mappings(self, node_type: str, properties: Dict) -> Dict:
        """Apply property name mappings for backward compatibility"""
        mapped = properties.copy()

        if node_type in self.property_mappings:
            mappings = self.property_mappings[node_type]
            for old_name, new_name in mappings.items():
                if old_name in mapped and new_name not in mapped:
                    mapped[new_name] = mapped[old_name]
                    # Keep old name for compatibility unless in strict mode
                    if self.strict_mode:
                        del mapped[old_name]

        return mapped

    def _check_required_fields(self, node_type: str, properties: Dict) -> List[str]:
        """Check for missing required fields"""
        required = self.required_fields.get(node_type, [])
        missing = []

        for field in required:
            if field not in properties or properties[field] is None:
                missing.append(field)

        return missing

    def _apply_defaults(self, node_type: str, properties: Dict) -> Dict:
        """Apply default values for optional fields"""
        defaults = self.optional_defaults.get(node_type, {})

        for field, default_value in defaults.items():
            if field not in properties:
                properties[field] = default_value

        return properties

    def _validate_data_types(self, node_type: str, properties: Dict) -> List[str]:
        """Validate data types of properties"""
        errors = []

        # Remove complex nested properties that Neo4j can't store
        properties_to_remove = [
            'content_by_language',
            'content_languages',
            'metadata',
            'included',  # From Fedlex JSON
            'data',      # From Fedlex JSON
            'references', # When nested as object
            'attributes', # When nested as object
        ]

        # Also remove any property that is a dict or list of dicts
        keys_to_remove = []
        for key, value in properties.items():
            if isinstance(value, dict):
                # Check if it's a nested object (not a simple date dict)
                if not all(k in ['xsd:date', 'xsd:string', 'rdfs:Resource'] for k in value.keys()):
                    keys_to_remove.append(key)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                # List of complex objects
                keys_to_remove.append(key)

        properties_to_remove.extend(keys_to_remove)

        for prop in set(properties_to_remove):
            if prop in properties:
                del properties[prop]

        # Type validation rules
        type_rules = {
            'Law': {
                'uri': str,
                'sr_number': str,
                'ast_level': int,
                'in_force': bool,
                'word_count': (int, type(None)),
                'embedding': (list, type(None))
            },
            'Article': {
                'uri': str,
                'law_uri': str,
                'number': str,
                'number_normalized': (int, type(None)),
                'position': (int, type(None)),
                'ast_level': int,
                'embedding': (list, type(None))
            },
            'Paragraph': {
                'uri': str,
                'article_uri': str,
                'number': str,
                'text': str,
                'position': (int, type(None)),
                'word_count': (int, type(None)),
                'has_subpoints': bool,
                'ast_level': int,
                'embedding': (list, type(None))
            }
        }

        rules = type_rules.get(node_type, {})
        for field, expected_type in rules.items():
            if field in properties and properties[field] is not None:
                value = properties[field]
                if isinstance(expected_type, tuple):
                    # Multiple allowed types
                    if not isinstance(value, expected_type):
                        errors.append(
                            f"Field '{field}' has wrong type: expected {expected_type}, got {type(value)}"
                        )
                else:
                    # Single expected type
                    if not isinstance(value, expected_type):
                        errors.append(
                            f"Field '{field}' has wrong type: expected {expected_type}, got {type(value)}"
                        )

        return errors

    def _custom_validations(self, node_type: str, properties: Dict) -> List[str]:
        """Perform custom validations specific to each node type"""
        warnings = []

        if node_type == 'Law':
            # Validate SR number format
            sr_number = properties.get('sr_number', '')
            if sr_number and not self._is_valid_sr_number(sr_number):
                warnings.append(f"Unusual SR number format: {sr_number}")

            # Check language consistency
            titles = [properties.get(f'title_{lang}') for lang in ['de', 'fr', 'it', 'rm', 'en']]
            if all(t is None for t in titles):
                warnings.append("No titles provided in any language")

            # Validate dates
            date_in = properties.get('date_entry_in_force')
            date_out = properties.get('date_no_longer_in_force')
            if date_in and date_out:
                if date_out < date_in:
                    warnings.append(
                        f"date_no_longer_in_force ({date_out}) is before date_entry_in_force ({date_in})"
                    )

        elif node_type == 'Article':
            # Validate article number
            number = properties.get('number', '')
            if number and not re.match(r'^\d+[a-z]?$', number):
                warnings.append(f"Unusual article number format: {number}")

            # Check content presence
            if not properties.get('content_full') and not properties.get('content_uri'):
                warnings.append("No content or content_uri provided")

        elif node_type == 'Paragraph':
            # Validate paragraph has text
            text = properties.get('text', '')
            if not text or len(text.strip()) < 10:
                warnings.append("Paragraph text is very short or empty")

            # Validate language code
            lang = properties.get('language', '')
            valid_langs = ['de', 'fr', 'it', 'rm', 'en']
            if lang and lang not in valid_langs:
                warnings.append(f"Invalid language code: {lang}")

        return warnings

    def _is_valid_sr_number(self, sr_number: str) -> bool:
        """Check if SR number follows expected patterns"""
        import re

        # Common patterns:
        # - Simple: 101, 210, 311
        # - Dotted: 142.20, 311.0
        # - Historical: I/271_271_445
        patterns = [
            r'^\d{3}$',  # Simple 3-digit
            r'^\d{3}\.\d+$',  # Dotted notation
            r'^[IVX]+/\d+_\d+_\d+$',  # Historical format
            r'^\d{1,3}(?:\.\d+)*$'  # General dotted
        ]

        return any(re.match(pattern, sr_number) for pattern in patterns)

    def batch_validate(self, node_type: str, properties_list: List[Dict]) -> List[ValidationResult]:
        """
        Validate multiple nodes of the same type.

        Args:
            node_type: Type of nodes
            properties_list: List of property dictionaries

        Returns:
            List of ValidationResult objects
        """
        results = []
        for properties in properties_list:
            result = self.validate_and_map(node_type, properties)
            results.append(result)

        return results

    def get_schema_info(self, node_type: str) -> Dict[str, Any]:
        """
        Get schema information for a node type.

        Args:
            node_type: Type of node

        Returns:
            Dictionary with required fields, optional fields, and defaults
        """
        return {
            'required_fields': self.required_fields.get(node_type, []),
            'optional_defaults': self.optional_defaults.get(node_type, {}),
            'property_mappings': self.property_mappings.get(node_type, {})
        }

    def enable_strict_mode(self):
        """Enable strict validation mode"""
        self.strict_mode = True
        logger.info("Schema mapper strict mode enabled")

    def disable_strict_mode(self):
        """Disable strict validation mode"""
        self.strict_mode = False
        logger.info("Schema mapper strict mode disabled")


# Convenience function for quick validation
def validate_node(node_type: str, properties: Dict, strict: bool = False) -> ValidationResult:
    """
    Quick validation of a single node.

    Args:
        node_type: Type of node
        properties: Node properties
        strict: Whether to use strict mode

    Returns:
        ValidationResult
    """
    mapper = SchemaPropertyMapper(strict_mode=strict)
    return mapper.validate_and_map(node_type, properties)


import re  # Add at top of file for regex support