"""
Tests for HTML Reference Extractor

Tests multilingual pattern detection, HTML parsing, and reference extraction.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.extractors.html_reference_extractor import HTMLReferenceExtractor, HTMLPaginationHandler
from src.extractors.reference_patterns import ReferencePatternDetector
from src.extractors.reference_cache import ReferenceCache


class TestHTMLPaginationHandler:
    """Test pagination file grouping"""
    
    def test_group_single_files(self):
        """Test grouping of single HTML files"""
        handler = HTMLPaginationHandler()
        
        files = [
            Path("fedlex-assets/eli/cc/1999/404/de/html/file1.html"),
            Path("fedlex-assets/eli/cc/2000/500/fr/html/file2.html"),
        ]
        
        groups = handler.group_paginated_files(files)
        
        assert len(groups) == 2
        assert all(len(group) == 1 for group in groups.values())
    
    def test_group_paginated_files(self):
        """Test grouping of paginated files"""
        handler = HTMLPaginationHandler()
        
        files = [
            Path("fedlex-assets/eli/cc/1999/404/de/html/doc.html"),
            Path("fedlex-assets/eli/cc/1999/404/de/html/doc-1.html"),
            Path("fedlex-assets/eli/cc/1999/404/de/html/doc-2.html"),
            Path("fedlex-assets/eli/cc/2000/500/fr/html/other.html"),
        ]
        
        groups = handler.group_paginated_files(files)
        
        assert len(groups) == 2
        
        # Find the group with 3 files (paginated document)
        paginated_group = None
        for group in groups.values():
            if len(group) == 3:
                paginated_group = group
                break
        
        assert paginated_group is not None
        # Check that files are sorted by page number
        filenames = [f.name for f in paginated_group]
        expected = ["doc.html", "doc-1.html", "doc-2.html"]
        assert filenames == expected


class TestReferencePatternDetector:
    """Test multilingual pattern detection"""
    
    def test_german_article_patterns(self):
        """Test German article reference detection"""
        detector = ReferencePatternDetector()
        
        text = "gemäss Art. 335b OR und Art. 12 DSG"
        references = detector.find_references(text, "de")
        
        assert len(references) >= 2
        
        # Check for OR reference
        or_refs = [r for r in references if "OR" in r.get('law', '')]
        assert len(or_refs) == 1
        assert or_refs[0]['article'] == '335b'
        
        # Check for DSG reference
        dsg_refs = [r for r in references if "DSG" in r.get('law', '')]
        assert len(dsg_refs) == 1
        assert dsg_refs[0]['article'] == '12'
    
    def test_french_article_patterns(self):
        """Test French article reference detection"""
        detector = ReferencePatternDetector()
        
        text = "selon art. 269 CO et conformément à l'art. 12 LPD"
        references = detector.find_references(text, "fr")
        
        assert len(references) >= 2
        
        # Check for CO reference
        co_refs = [r for r in references if "CO" in r.get('law', '')]
        assert len(co_refs) == 1
        assert co_refs[0]['article'] == '269'
    
    def test_italian_article_patterns(self):
        """Test Italian article reference detection"""
        detector = ReferencePatternDetector()
        
        text = "secondo l'art. 123 CO e articolo 45 Cost"
        references = detector.find_references(text, "it")
        
        assert len(references) >= 1
        
        # Check for CO reference
        co_refs = [r for r in references if r.get('law') == 'CO']
        assert len(co_refs) == 1
        assert co_refs[0]['article'] == '123'
    
    def test_sr_number_detection(self):
        """Test SR number detection across languages"""
        detector = ReferencePatternDetector()
        
        texts = [
            "SR 220 regelt die Obligationen",  # German
            "RS 220 règle les obligations",    # French
            "RS 220 disciplina le obbligazioni"  # Italian
        ]
        
        for text in texts:
            for lang in ['de', 'fr', 'it']:
                references = detector.find_references(text, lang)
                sr_refs = [r for r in references if 'SR' in r.get('normalized', '')]
                assert len(sr_refs) >= 1
                assert '220' in sr_refs[0]['normalized']
    
    def test_publication_references(self):
        """Test publication reference detection"""
        detector = ReferencePatternDetector()
        
        text = "AS 2023 1234 und BBl 2023 III 567"
        references = detector.find_references(text, "de")
        
        # Should find both AS and BBl references
        as_refs = [r for r in references if r.get('law') == 'AS']
        bbl_refs = [r for r in references if r.get('law') == 'BBl']
        
        assert len(as_refs) >= 1
        assert '2023' in as_refs[0]['normalized']
        assert '1234' in as_refs[0]['normalized']


class TestReferenceCache:
    """Test reference caching system"""
    
    def test_cache_storage_retrieval(self):
        """Test storing and retrieving cache entries"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ReferenceCache(cache_dir=temp_dir)
            
            # Create mock extraction result
            from src.extractors.base_extractor import ExtractionResult
            result = ExtractionResult()
            result.add_relationship("uri1", "uri2", "REFERENCES", {"test": "data"})
            
            # Create a test file
            test_file = Path(temp_dir) / "test.html"
            test_file.write_text("<html>Test content</html>")
            
            # Store result
            success = cache.store(str(test_file), result)
            assert success
            
            # Retrieve result
            cached_result = cache.get_cached(str(test_file))
            assert cached_result is not None
            assert len(cached_result.relationships) == 1
            assert cached_result.relationships[0][0] == "uri1"
            assert cached_result.relationships[0][1] == "uri2"
    
    def test_cache_invalidation_on_file_change(self):
        """Test that cache is invalidated when file changes"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = ReferenceCache(cache_dir=temp_dir)
            
            # Create test file
            test_file = Path(temp_dir) / "test.html"
            test_file.write_text("<html>Original content</html>")
            
            # Store result
            from src.extractors.base_extractor import ExtractionResult
            result = ExtractionResult()
            cache.store(str(test_file), result)
            
            # Verify cached
            cached = cache.get_cached(str(test_file))
            assert cached is not None
            
            # Modify file
            test_file.write_text("<html>Modified content</html>")
            
            # Cache should be invalid
            cached = cache.get_cached(str(test_file))
            assert cached is None


class TestHTMLReferenceExtractor:
    """Test main HTML reference extractor"""
    
    def test_language_detection_from_path(self):
        """Test language detection from file paths"""
        extractor = HTMLReferenceExtractor()
        
        test_cases = [
            ("fedlex-assets/eli/cc/1999/404/de/html/file.html", "de"),
            ("fedlex-assets/eli/cc/1999/404/fr/html/file.html", "fr"),
            ("fedlex-assets/eli/cc/1999/404/it/html/file.html", "it"),
            ("fedlex-assets/eli/cc/1999/404/rm/html/file.html", "rm"),
            ("fedlex-assets/eli/cc/1999/404/en/html/file.html", "en"),
        ]
        
        for path, expected_lang in test_cases:
            detected = extractor._detect_language(path)
            assert detected == expected_lang
    
    def test_source_uri_extraction(self):
        """Test source URI extraction from file paths"""
        extractor = HTMLReferenceExtractor()
        
        path = "fedlex-assets/eli/cc/1999/404/20240101/de/html/file.html"
        uri = extractor._extract_source_uri(path)
        
        assert "fedlex.data.admin.ch" in uri
        assert "/eli/cc/1999/404/20240101" in uri
    
    @patch('builtins.open')
    def test_html_file_processing(self, mock_open):
        """Test processing of HTML file with references"""
        # Mock HTML content with references
        html_content = """
        <html>
        <body>
            <div id="lawcontent">
                <p>Gemäss Art. 335b OR ist dies geregelt.</p>
                <p>Siehe auch SR 220 für weitere Details.</p>
            </div>
        </body>
        </html>
        """
        
        mock_open.return_value.__enter__.return_value.read.return_value = html_content
        
        extractor = HTMLReferenceExtractor(use_cache=False)
        result = extractor.extract_from_html_file("test.html")
        
        # Should find references
        assert len(result.relationships) >= 1
        
        # Should have REFERENCES relationship type
        ref_relationships = [r for r in result.relationships if r[2] == "REFERENCES"]
        assert len(ref_relationships) >= 1


class TestIntegration:
    """Integration tests for the complete system"""
    
    def test_pattern_detector_integration(self):
        """Test that pattern detector works with realistic legal text"""
        detector = ReferencePatternDetector()
        
        # Realistic German legal text
        german_text = """
        Die Bestimmungen des Obligationenrechts (Art. 1 ff. OR) gelten auch hier.
        Gemäss Art. 335b OR haben Arbeitnehmer Anspruch auf Lohn.
        Nach Art. 12 DSG sind personenbezogene Daten zu schützen.
        Siehe auch AS 2023 1234 und BBl 2023 III 567.
        """
        
        references = detector.find_references(german_text, "de")
        
        # Should find multiple references
        assert len(references) >= 3
        
        # Should find different types of references
        law_codes = {r.get('law') for r in references}
        assert 'OR' in law_codes or 'DSG' in law_codes
    
    @pytest.mark.integration
    def test_full_extraction_pipeline(self):
        """Test the complete extraction pipeline (requires setup)"""
        # This test would require actual HTML files and database connection
        # Mark as integration test to run separately
        pass
