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
        
        # German patterns
        self.german_patterns = [
            # Art. 335b OR, Art. 12 DSG
            regex.compile(
                r'\b(?:Art\.|Artikel)\s*(\d+[a-z]?)\s+([A-Z]{2,5})\b',
                regex.IGNORECASE
            ),
            
            # gemäss Art. 23, nach Art. 15
            regex.compile(
                r'\b(?:gemäss|nach|laut)\s+(?:Art\.|Artikel)\s*(\d+[a-z]?)\b',
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
        ]
        
        # French patterns
        self.french_patterns = [
            # art. 269 CO, art. 12 LPD
            regex.compile(
                r'\b(?:art\.|article)\s*(\d+[a-z]?)\s+([A-Z]{2,5})\b',
                regex.IGNORECASE
            ),
            
            # selon art. 23, conformément à l'art. 15
            regex.compile(
                r'\b(?:selon|conformément\s+à)\s+l?\'?(?:art\.|article)\s*(\d+[a-z]?)\b',
                regex.IGNORECASE
            ),
            
            # al. 2 (alinéa)
            regex.compile(
                r'\bal\.\s*(\d+)\b',
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
            # art. 269 CO, articolo 12 LPD
            regex.compile(
                r'\b(?:art\.|articolo)\s*(\d+[a-z]?)\s+([A-Z]{2,5})\b',
                regex.IGNORECASE
            ),
            
            # secondo l'art. 23
            regex.compile(
                r'\bsecondo\s+l\'(?:art\.|articolo)\s*(\d+[a-z]?)\b',
                regex.IGNORECASE
            ),
            
            # cpv. 2 (capoverso)
            regex.compile(
                r'\bcpv\.\s*(\d+)\b',
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
        
        for pattern in self.german_patterns[:4]:  # Article patterns only
            for match in pattern.finditer(text):
                try:
                    law_code = None
                    if len(match.groups()) >= 2 and match.group(2):
                        # Art. X LAW format
                        article = match.group(1)
                        law_code = match.group(2).upper()
                        raw_text = match.group(0)
                        normalized = f"{self.law_mapper.normalize_law_code(law_code, language)}:{article}"
                    elif len(match.groups()) >= 1:
                        # Art. X format (without law code)
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
