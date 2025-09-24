"""
Multilingual Legal Reference Pattern Detection

Detects legal cross-references in German, French, Italian, and Romansh texts.
Handles various reference formats like "Art. 335b OR", "selon CO art. 269", etc.
"""
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import regex

logger = logging.getLogger(__name__)


class LanguageCode(Enum):
    """Supported language codes"""
    GERMAN = "de"
    FRENCH = "fr"
    ITALIAN = "it"
    ROMANSH = "rm"
    ENGLISH = "en"


@dataclass
class ReferenceMatch:
    """
    Represents a matched legal reference
    """
    raw_text: str
    law_code: str
    article_number: Optional[str]
    paragraph: Optional[str]
    normalized: str
    confidence: float
    position: Tuple[int, int]  # Start, end positions in text


class LawCodeMapper:
    """
    Maps law codes between languages to standardized SR numbers
    """
    
    # Mapping from language-specific codes to SR numbers
    LAW_CODE_MAPPING = {
        # German codes
        'OR': '220',           # Obligationenrecht
        'ZGB': '210',          # Zivilgesetzbuch
        'StGB': '311.0',       # Strafgesetzbuch
        'DSG': '235.1',        # Datenschutzgesetz
        'BV': '101',           # Bundesverfassung
        'ArG': '822.11',       # Arbeitsgesetz
        'AHVG': '831.10',      # AHV-Gesetz
        'UVG': '832.20',       # Unfallversicherungsgesetz
        'KVG': '832.10',       # Krankenversicherungsgesetz
        
        # French codes (many same as German)
        'CO': '220',           # Code des obligations
        'CC': '210',           # Code civil
        'CP': '311.0',         # Code pénal
        'LPD': '235.1',        # Loi sur la protection des données
        'Cst': '101',          # Constitution
        'LTr': '822.11',       # Loi sur le travail
        
        # Italian codes
        'Cost': '101',         # Costituzione
        
        # Special formats
        'AS': 'AS',            # Amtliche Sammlung
        'RU': 'AS',            # Recueil officiel
        'RS': 'SR',            # Raccolta sistematica (SR)
        'BBl': 'BBl',          # Bundesblatt
        'FF': 'BBl',           # Feuille fédérale
        'CS': 'CS',            # Classificazione sistematica
    }
    
    # Reverse mapping for normalization
    NORMALIZED_NAMES = {
        '220': 'OR',
        '210': 'ZGB', 
        '311.0': 'StGB',
        '235.1': 'DSG',
        '101': 'BV',
        '822.11': 'ArG',
    }
    
    @classmethod
    def normalize_law_code(cls, code: str, language: str) -> str:
        """
        Normalize law code to standard form
        
        Args:
            code: Law code (OR, CO, CC, etc.)
            language: Language context
            
        Returns:
            Normalized code or SR number
        """
        if code in cls.LAW_CODE_MAPPING:
            sr_number = cls.LAW_CODE_MAPPING[code]
            return f"SR {sr_number}" if sr_number.replace('.', '').isdigit() else sr_number
        
        # Return as-is if not found
        return code
    
    @classmethod
    def get_sr_number(cls, code: str) -> Optional[str]:
        """Get SR number for a law code"""
        return cls.LAW_CODE_MAPPING.get(code)


class ReferencePatternDetector:
    """
    Detects legal references using language-specific patterns
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.law_mapper = LawCodeMapper()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for each language"""
        
        # Define article number suffix pattern
        article_suffix = r'(?:[a-z]|bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)'

        # German patterns
        self.german_patterns = [
            # Range references: Art. 5-10 OR, Art. 5 bis 10 ZGB, Art. 5bis-10ter
            regex.compile(
                rf'\b(?:Art\.|Artikel|Articles)\s*(\d+{article_suffix}?)(?:\s*[-–]\s*|\s+bis\s+)(\d+{article_suffix}?)(?:\s+([A-Z]{{2,5}}))?\b',
                regex.IGNORECASE
            ),

            # List references: Art. 5, 7 und 9 OR (must have comma or und, exclude "bis" as law code)
            regex.compile(
                rf'\b(?:Art\.|Artikel)\s*(\d+{article_suffix}?)(?:\s*,\s*\d+{article_suffix}?)+(?:\s+und\s+\d+{article_suffix}?)?(?:\s+(?!bis\b)([A-Z]{{2,5}}))?\b',
                regex.IGNORECASE
            ),

            # Art. 335bis OR, Art. 12 DSG (exclude standalone "bis" as law code)
            regex.compile(
                rf'\b(?:Art\.|Artikel)\s*(\d+{article_suffix}?)\s+(?!bis\b)([A-Z]{{2,5}})\b',
                regex.IGNORECASE
            ),

            # gemäss Art. 335bis, nach Art. 15ter (exclude "bis" as range indicator)
            regex.compile(
                rf'\b(?:gemäss|nach|laut)\s+(?:Art\.|Artikel)\s*(\d+{article_suffix}?)(?!\s+bis\s+\d)\b',
                regex.IGNORECASE
            ),

            # Standalone article: Art. 5quater (without law code)
            regex.compile(
                rf'\b(?:Art\.|Artikel)\s*(\d+{article_suffix}?)\b(?!\s+[A-Z]{{2,5}})',
                regex.IGNORECASE
            ),

            # § 12 ArG, § 23
            regex.compile(
                r'\b§\s*(\d+[a-z]?)\s*([A-Z]{2,5})?\b',
                regex.IGNORECASE
            ),

            # Abs. 2, Absatz 3
            regex.compile(
                r'\b(?:Abs\.|Absatz)\s*(\d+)\b',
                regex.IGNORECASE
            ),

            # Ziff. 1, Ziffer 2 (number/point)
            regex.compile(
                r'\b(?:Ziff\.|Ziffer)\s*(\d+)\b',
                regex.IGNORECASE
            ),

            # lit. a, Bst. b (letters)
            regex.compile(
                r'\b(?:lit\.|Bst\.|Buchst\.)\s*([a-z])\b',
                regex.IGNORECASE
            ),

            # SR references: SR 220, SR 311.0
            regex.compile(
                r'\bSR\s+([\d.]+)\b',
                regex.IGNORECASE
            ),

            # AS references: AS 2023 1234
            regex.compile(
                r'\bAS\s+(\d{4})\s+(\d+)\b',
                regex.IGNORECASE
            ),

            # RU references: RU 1988 1705 (Recueil officiel)
            regex.compile(
                r'\bRU\s+(\d{4})\s+(\d+)\b',
                regex.IGNORECASE
            ),

            # FF references: FF 1869 234 (Feuille fédérale)
            regex.compile(
                r'\b(?:FF|BBl)\s+(\d{4})\s+(\d+)\b',
                regex.IGNORECASE
            ),
        ]
        
        # French patterns
        self.french_patterns = [
            # art. 269bis CO, art. 12ter LPD
            regex.compile(
                rf'\b(?:art\.|article)\s*(\d+{article_suffix}?)\s+([A-Z]{{2,5}})\b',
                regex.IGNORECASE
            ),

            # selon art. 23bis, conformément à l'art. 15ter
            regex.compile(
                rf'\b(?:selon|conformément\s+à)\s+l?\'?(?:art\.|article)\s*(\d+{article_suffix}?)\b',
                regex.IGNORECASE
            ),
            
            # al. 2 (alinéa)
            regex.compile(
                r'\bal\.\s*(\d+)\b',
                regex.IGNORECASE
            ),

            # let. a (lettre)
            regex.compile(
                r'\blet\.\s*([a-z])\b',
                regex.IGNORECASE
            ),

            # ch. 1 (chiffre)
            regex.compile(
                r'\bch\.\s*(\d+)\b',
                regex.IGNORECASE
            ),
            
            # RS references: RS 220
            regex.compile(
                r'\bRS\s+([\d.]+)\b',
                regex.IGNORECASE
            ),
            
            # RU references: RU 2023 1234
            regex.compile(
                r'\bRU\s+(\d{4})\s+(\d+)\b',
                regex.IGNORECASE
            ),
        ]
        
        # Italian patterns
        self.italian_patterns = [
            # art. 269bis CO, articolo 12ter LPD
            regex.compile(
                rf'\b(?:art\.|articolo)\s*(\d+{article_suffix}?)\s+([A-Z]{{2,5}})\b',
                regex.IGNORECASE
            ),

            # secondo l'art. 23bis
            regex.compile(
                rf'\bsecondo\s+l\'(?:art\.|articolo)\s*(\d+{article_suffix}?)\b',
                regex.IGNORECASE
            ),
            
            # cpv. 2 (capoverso)
            regex.compile(
                r'\bcpv\.\s*(\d+)\b',
                regex.IGNORECASE
            ),

            # lett. a (lettera)
            regex.compile(
                r'\blett\.\s*([a-z])\b',
                regex.IGNORECASE
            ),

            # n. 1 (numero)
            regex.compile(
                r'\bn\.\s*(\d+)\b',
                regex.IGNORECASE
            ),
            
            # RS references: RS 220
            regex.compile(
                r'\bRS\s+([\d.]+)\b',
                regex.IGNORECASE
            ),
            
            # RU references: RU 2023 1234
            regex.compile(
                r'\bRU\s+(\d{4})\s+(\d+)\b',
                regex.IGNORECASE
            ),
        ]
    
    def find_references(self, text: str, language: str) -> List[Dict[str, Any]]:
        """
        Find all legal references in text
        
        Args:
            text: Text content to search
            language: Language code (de, fr, it, rm, en)
            
        Returns:
            List of reference matches
        """
        references = []
        
        # Select patterns based on language
        patterns = self._get_patterns_for_language(language)
        
        for pattern_func in patterns:
            matches = pattern_func(text, language)
            references.extend(matches)
        
        # Remove duplicates and sort by position
        references = self._deduplicate_references(references)
        references.sort(key=lambda x: x['position'][0])
        
        self.logger.debug(f"Found {len(references)} references in {language} text")
        return references
    
    def _get_patterns_for_language(self, language: str) -> List:
        """Get pattern detection functions for language"""
        if language == 'de':
            return [
                self._find_german_article_references,
                self._find_sr_references,
                self._find_publication_references,
            ]
        elif language == 'fr':
            return [
                self._find_french_article_references,
                self._find_sr_references,
                self._find_publication_references,
            ]
        elif language == 'it':
            return [
                self._find_italian_article_references,
                self._find_sr_references,
                self._find_publication_references,
            ]
        else:
            # Default to German patterns for rm/en
            return [
                self._find_german_article_references,
                self._find_sr_references,
                self._find_publication_references,
            ]
    
    def _find_german_article_references(self, text: str, language: str) -> List[Dict[str, Any]]:
        """Find German article references"""
        references = []

        for i, pattern in enumerate(self.german_patterns):  # Process all patterns
            for match in pattern.finditer(text):
                try:
                    raw_text = match.group(0)
                    groups = match.groups()

                    # Handle different pattern types
                    if i == 0:  # Range pattern (Art. 5-10 OR)
                        if len(groups) >= 2 and groups[0] and groups[1]:
                            start_article = groups[0]
                            end_article = groups[1]
                            law_code = groups[2].upper() if len(groups) > 2 and groups[2] else 'UNKNOWN'

                            # Create reference for the range
                            article = f"{start_article}-{end_article}"
                            if law_code != 'UNKNOWN':
                                normalized = f"{self.law_mapper.normalize_law_code(law_code, language)}:{article}"
                            else:
                                normalized = f"ART:{article}"
                        else:
                            continue

                    elif i == 1:  # List pattern (Art. 5, 7 und 9 OR)
                        if len(groups) >= 1:
                            article = groups[0]
                            law_code = groups[1].upper() if len(groups) > 1 and groups[1] else 'UNKNOWN'
                            if law_code != 'UNKNOWN':
                                normalized = f"{self.law_mapper.normalize_law_code(law_code, language)}:{article}"
                            else:
                                normalized = f"ART:{article}"
                        else:
                            continue

                    else:  # Standard patterns
                        if len(groups) >= 2 and groups[1]:
                            # Art. X LAW format
                            article = groups[0]
                            law_code = groups[1].upper()
                            normalized = f"{self.law_mapper.normalize_law_code(law_code, language)}:{article}"
                        elif len(groups) >= 1:
                            # Art. X format (without law code)
                            article = groups[0]
                            law_code = 'UNKNOWN'
                            normalized = f"ART:{article}"
                        else:
                            continue

                    reference = {
                        'raw_text': raw_text,
                        'law': law_code,
                        'article': article,
                        'normalized': normalized,
                        'confidence': 0.9,
                        'position': match.span(),
                        'language': language
                    }
                    references.append(reference)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing German pattern match: {e}")
                    continue
        
        return references
    
    def _find_french_article_references(self, text: str, language: str) -> List[Dict[str, Any]]:
        """Find French article references"""
        references = []
        
        for pattern in self.french_patterns[:3]:  # Article patterns only
            for match in pattern.finditer(text):
                try:
                    law_code = None
                    if len(match.groups()) >= 2 and match.group(2):
                        # art. X LAW format
                        article = match.group(1)
                        law_code = match.group(2).upper()
                        raw_text = match.group(0)
                        normalized = f"{self.law_mapper.normalize_law_code(law_code, language)}:{article}"
                    elif len(match.groups()) >= 1:
                        # art. X format
                        article = match.group(1)
                        raw_text = match.group(0)
                        normalized = f"ART:{article}"
                        law_code = 'UNKNOWN'
                    else:
                        continue
                    
                    reference = {
                        'raw_text': raw_text,
                        'law': law_code,
                        'article': article,
                        'normalized': normalized,
                        'confidence': 0.9,
                        'position': match.span(),
                        'language': language
                    }
                    references.append(reference)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing French pattern match: {e}")
                    continue
        
        return references
    
    def _find_italian_article_references(self, text: str, language: str) -> List[Dict[str, Any]]:
        """Find Italian article references"""
        references = []
        
        for pattern in self.italian_patterns[:3]:  # Article patterns only
            for match in pattern.finditer(text):
                try:
                    law_code = None
                    if len(match.groups()) >= 2 and match.group(2):
                        # art. X LAW format
                        article = match.group(1)
                        law_code = match.group(2).upper()
                        raw_text = match.group(0)
                        normalized = f"{self.law_mapper.normalize_law_code(law_code, language)}:{article}"
                    elif len(match.groups()) >= 1:
                        # art. X format
                        article = match.group(1)
                        raw_text = match.group(0)
                        normalized = f"ART:{article}"
                        law_code = 'UNKNOWN'
                    else:
                        continue
                    
                    reference = {
                        'raw_text': raw_text,
                        'law': law_code,
                        'article': article,
                        'normalized': normalized,
                        'confidence': 0.9,
                        'position': match.span(),
                        'language': language
                    }
                    references.append(reference)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing Italian pattern match: {e}")
                    continue
        
        return references
    
    def _find_sr_references(self, text: str, language: str) -> List[Dict[str, Any]]:
        """Find SR number references"""
        references = []
        
        # SR pattern is language-agnostic
        sr_pattern = regex.compile(r'\b(?:SR|RS)\s+([\d.]+)\b', regex.IGNORECASE)
        
        for match in sr_pattern.finditer(text):
            try:
                sr_number = match.group(1)
                raw_text = match.group(0)
                normalized = f"SR {sr_number}"
                
                reference = {
                    'raw_text': raw_text,
                    'law': f"SR_{sr_number.replace('.', '_')}",
                    'article': None,
                    'normalized': normalized,
                    'confidence': 0.95,
                    'position': match.span(),
                    'language': language
                }
                references.append(reference)
                
            except Exception as e:
                self.logger.debug(f"Error processing SR pattern match: {e}")
                continue
        
        return references
    
    def _find_publication_references(self, text: str, language: str) -> List[Dict[str, Any]]:
        """Find publication references (AS, RU, BBl, etc.)"""
        references = []
        
        # Publication patterns
        patterns = {
            'AS': regex.compile(r'\bAS\s+(\d{4})\s+(\d+)\b', regex.IGNORECASE),
            'RU': regex.compile(r'\bRU\s+(\d{4})\s+(\d+)\b', regex.IGNORECASE),
            'BBl': regex.compile(r'\bBBl\s+(\d{4})\s+([IVX]+)\s+(\d+)\b', regex.IGNORECASE),
            'FF': regex.compile(r'\bFF\s+(\d{4})\s+([IVX]+)\s+(\d+)\b', regex.IGNORECASE),
        }
        
        for pub_type, pattern in patterns.items():
            for match in pattern.finditer(text):
                try:
                    raw_text = match.group(0)
                    groups = match.groups()
                    
                    if len(groups) >= 2:
                        year = groups[0]
                        number = groups[-1]  # Last group is usually the page/number
                        normalized = f"{pub_type} {year} {number}"
                    else:
                        normalized = raw_text
                    
                    reference = {
                        'raw_text': raw_text,
                        'law': pub_type,
                        'article': None,
                        'normalized': normalized,
                        'confidence': 0.85,
                        'position': match.span(),
                        'language': language
                    }
                    references.append(reference)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing publication pattern match: {e}")
                    continue
        
        return references
    
    def _deduplicate_references(self, references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate references"""
        seen = set()
        unique_refs = []
        
        for ref in references:
            # Create unique key from position and normalized text
            key = (ref['position'], ref['normalized'])
            if key not in seen:
                seen.add(key)
                unique_refs.append(ref)
        
        return unique_refs
