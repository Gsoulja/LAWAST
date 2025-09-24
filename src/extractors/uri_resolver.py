"""
URI resolver utilities for Fedlex data
Handles normalization and extraction of components from Fedlex URIs
"""
import re
from typing import Optional, Tuple
from urllib.parse import urlparse


class URIResolver:
    """
    Resolves and normalizes Fedlex URIs for consistent matching
    """

    # Base URI patterns
    FEDLEX_BASE = "https://fedlex.data.admin.ch"
    EUROPA_BASE = "http://publications.europa.eu"

    # Language mapping
    LANGUAGE_MAP = {
        "de": "DEU",
        "fr": "FRA",
        "it": "ITA",
        "rm": "ROH",
        "en": "ENG"
    }

    # Reverse language mapping
    LANGUAGE_CODE_MAP = {
        f"{EUROPA_BASE}/resource/authority/language/DEU": "de",
        f"{EUROPA_BASE}/resource/authority/language/FRA": "fr",
        f"{EUROPA_BASE}/resource/authority/language/ITA": "it",
        f"{EUROPA_BASE}/resource/authority/language/ROH": "rm",
        f"{EUROPA_BASE}/resource/authority/language/ENG": "en"
    }

    def normalize_uri(self, uri: str) -> str:
        """
        Normalize a URI for consistent matching

        Args:
            uri: Raw URI from JSON

        Returns:
            Normalized URI string
        """
        if not uri:
            return ""

        # Remove trailing slashes
        uri = uri.rstrip("/")

        # Ensure consistent protocol
        if uri.startswith("http://fedlex.data.admin.ch"):
            uri = uri.replace("http://", "https://", 1)

        return uri

    def extract_language_code(self, uri: str) -> Optional[str]:
        """
        Extract language code from URI

        Args:
            uri: URI containing language code

        Returns:
            Language code (de, fr, it, rm, en) or None

        Examples:
            .../eli/cc/1999/404/de -> "de"
            .../eli/cc/1999/404/20240101/fr -> "fr"
        """
        # Check if it's a language authority URI
        if uri in self.LANGUAGE_CODE_MAP:
            return self.LANGUAGE_CODE_MAP[uri]

        # Extract from path
        pattern = r'/(?:de|fr|it|rm|en)(?:/|$)'
        match = re.search(pattern, uri)
        if match:
            lang = match.group(0).strip('/')
            return lang

        return None

    def extract_format(self, uri: str) -> Optional[str]:
        """
        Extract document format from URI

        Args:
            uri: URI containing format

        Returns:
            Format (html, pdf, xml, docx, etc.) or None

        Examples:
            .../de/html -> "html"
            .../fr/pdf-a -> "pdf-a"
        """
        # Common format patterns
        formats = ["html", "pdf", "pdf-a", "pdf-x", "xml", "docx", "doc", "json"]

        # Check URI ending
        for fmt in formats:
            if uri.endswith(f"/{fmt}"):
                return fmt

        return None

    def get_parent_law_uri(self, version_uri: str) -> Optional[str]:
        """
        Extract parent law URI from a version URI

        Args:
            version_uri: Version URI

        Returns:
            Parent law URI or None

        Example:
            .../eli/cc/1999/404/20240101 -> .../eli/cc/1999/404
        """
        # Remove date suffix (8 digits)
        pattern = r'(/eli/cc/[^/]+/[^/]+)/\d{8}'
        match = re.search(pattern, version_uri)
        if match:
            base = match.group(1)
            # Reconstruct full URI
            if version_uri.startswith("http"):
                parsed = urlparse(version_uri)
                return f"{parsed.scheme}://{parsed.netloc}{base}"
            return base

        return None

    def extract_sr_number(self, uri: str) -> Optional[str]:
        """
        Extract SR number from law URI

        Args:
            uri: Law URI

        Returns:
            SR number or None

        Handles special cases:
        - Roman numerals: /eli/cc/I/271_271_445 -> "SR I 271"
        - Double underscore: /eli/cc/1959/__1811 -> "Special 1811"
        - Standard: /eli/cc/1999/404 -> "SR 1999.404"
        """
        # Extract path components
        pattern = r'/eli/cc/([^/]+)/([^/]+)'
        match = re.search(pattern, uri)

        if not match:
            return None

        year_or_section = match.group(1)
        number = match.group(2).split('/')[0]  # Remove any date suffix

        # Handle Roman numerals
        if year_or_section in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]:
            # Extract first number from multi-part
            main_num = number.split('_')[0] if '_' in number else number
            return f"SR {year_or_section} {main_num}"

        # Handle double underscore (special legislation)
        if number.startswith("__"):
            return f"Special {number[2:]}"

        # Standard format
        return f"SR {year_or_section}.{number}"

    def is_version_uri(self, uri: str) -> bool:
        """
        Check if URI represents a version (has date suffix)

        Args:
            uri: URI to check

        Returns:
            True if version URI, False otherwise
        """
        # Check for 8-digit date at end of path
        pattern = r'/\d{8}(?:/|$)'
        return bool(re.search(pattern, uri))

    def extract_date_from_version(self, uri: str) -> Optional[str]:
        """
        Extract date from version URI

        Args:
            uri: Version URI

        Returns:
            Date string (YYYY-MM-DD) or None

        Example:
            .../eli/cc/1999/404/20240101 -> "2024-01-01"
        """
        pattern = r'/(\d{8})(?:/|$)'
        match = re.search(pattern, uri)
        if match:
            date_str = match.group(1)
            # Format as YYYY-MM-DD
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        return None

    def get_law_type(self, uri: str) -> Optional[str]:
        """
        Determine the type of law from URI

        Args:
            uri: Law URI

        Returns:
            Type: "cc", "oc", "fga", "treaty", or None
        """
        if "/eli/cc/" in uri:
            return "cc"  # Classified compilation
        elif "/eli/oc/" in uri:
            return "oc"  # Official compilation
        elif "/eli/fga/" in uri:
            return "fga"  # Federal gazette
        elif "/eli/treaty/" in uri:
            return "treaty"  # International treaty

        return None

    def build_manifestation_uri(
        self,
        base_uri: str,
        language: str,
        format: str
    ) -> str:
        """
        Build a manifestation URI from components

        Args:
            base_uri: Base URI (law or version)
            language: Language code
            format: Document format

        Returns:
            Complete manifestation URI
        """
        base = self.normalize_uri(base_uri)
        return f"{base}/{language}/{format}"

    def decompose_uri(self, uri: str) -> dict:
        """
        Decompose a URI into its components

        Args:
            uri: URI to decompose

        Returns:
            Dictionary with components
        """
        normalized = self.normalize_uri(uri)

        return {
            "normalized": normalized,
            "type": self.get_law_type(normalized),
            "sr_number": self.extract_sr_number(normalized),
            "is_version": self.is_version_uri(normalized),
            "date": self.extract_date_from_version(normalized),
            "language": self.extract_language_code(normalized),
            "format": self.extract_format(normalized),
            "parent_law": self.get_parent_law_uri(normalized) if self.is_version_uri(normalized) else None
        }