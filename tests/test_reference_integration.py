#!/usr/bin/env python3
"""
Integration tests for Reference Resolution Module

Tests the complete pipeline from HTML files to Neo4j REFERENCES relationships.
Run with: pytest tests/test_reference_integration.py -v
"""
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extractors.article_extractor import ArticleExtractor
from src.extractors.html_reference_extractor import HTMLReferenceExtractor
from src.extractors.reference_patterns import ReferencePatternDetector
from src.data_access.graph_builder import GraphBuilder
from src.extractors.base_extractor import ExtractionResult


class TestReferenceIntegration:
    """Integration tests for reference extraction pipeline"""

    def test_article_extractor_with_references(self):
        """Test that ArticleExtractor properly extracts references"""
        # Create test HTML with articles and references
        test_html = """
        <html>
        <body>
            <div id="lawcontent">
                <article id="art_1">
                    <h6><b>Art. 1</b> Grundsatz</h6>
                    <div class="collapseable">
                        <p>1 Gemäss Art. 335b OR ist dies geregelt.</p>
                        <p>2 Siehe auch Art. 12 ZGB und SR 220 für Details.</p>
                    </div>
                </article>
                <article id="art_2">
                    <h6><b>Art. 2</b> Anwendung</h6>
                    <div class="collapseable">
                        <p>Nach Art. 1 DSG sind Daten zu schützen.</p>
                    </div>
                </article>
            </div>
        </body>
        </html>
        """

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(test_html)
            temp_path = f.name

        try:
            # Extract articles with references
            extractor = ArticleExtractor()
            result = extractor.extract(temp_path)

            # Should extract 2 articles
            assert len(result.nodes) == 2

            # Should extract REFERENCES relationships
            ref_relationships = [r for r in result.relationships if r[2] == "REFERENCES"]
            assert len(ref_relationships) >= 3  # At least OR, ZGB, DSG references

            # Check that references are attached to correct articles
            art1_refs = [r for r in ref_relationships if "art_1" in r[0]]
            assert len(art1_refs) >= 2  # OR and ZGB references

            art2_refs = [r for r in ref_relationships if "art_2" in r[0]]
            assert len(art2_refs) >= 1  # DSG reference

        finally:
            # Clean up
            Path(temp_path).unlink(missing_ok=True)

    def test_html_reference_extractor_pagination(self):
        """Test pagination handling in reference extraction"""
        from src.extractors.html_reference_extractor import HTMLPaginationHandler

        handler = HTMLPaginationHandler()

        # Create test files
        test_files = [
            Path("fedlex-assets/eli/cc/1999/404/de/html/doc.html"),
            Path("fedlex-assets/eli/cc/1999/404/de/html/doc-1.html"),
            Path("fedlex-assets/eli/cc/1999/404/de/html/doc-2.html"),
            Path("fedlex-assets/eli/cc/2000/500/de/html/other.html"),
        ]

        groups = handler.group_paginated_files(test_files)

        # Should group paginated files together
        assert len(groups) == 2

        # Find paginated group
        for group_files in groups.values():
            if len(group_files) == 3:
                # Check ordering
                assert group_files[0].name == "doc.html"
                assert group_files[1].name == "doc-1.html"
                assert group_files[2].name == "doc-2.html"
                break
        else:
            pytest.fail("Paginated group not found")

    def test_reference_pattern_coverage(self):
        """Test comprehensive pattern coverage across languages"""
        detector = ReferencePatternDetector()

        # Test all specified pattern types
        test_cases = [
            # Internal references
            ("de", "Abs. 2 und Abs. 3", 2),  # Paragraph references
            ("de", "Art. 5 und Art. 10-15", 2),  # Article references
            ("de", "Ziff. 1 und lit. a", 2),  # Number and letter references
            ("de", "SR 220 und RS 0.353.1", 2),  # Publication references

            # External references
            ("de", "Art. 5 OR und Art. 10 ZGB", 2),
            ("de", "SR 210 und SR 311.0", 2),
            ("fr", "Art. 8 CEDH", 1),

            # Special patterns
            ("de", "Art. 5-10 und Art. 5 bis 10", 2),
            ("de", "Art. 5, 7 und 9 OR", 2),  # Captures as one OR reference + one article reference
            ("de", "Art. 5 Abs. 2 lit. a OR", 1),
        ]

        for lang, text, min_expected in test_cases:
            refs = detector.find_references(text, lang)
            assert len(refs) >= min_expected, f"Failed for: {text}"

    def test_reference_normalization(self):
        """Test that references are properly normalized"""
        from src.extractors.reference_patterns import LawCodeMapper

        mapper = LawCodeMapper()

        # Test law code normalization
        assert mapper.normalize_law_code("OR", "de") == "SR 220"
        assert mapper.normalize_law_code("CO", "fr") == "SR 220"
        assert mapper.normalize_law_code("ZGB", "de") == "SR 210"
        assert mapper.normalize_law_code("CC", "fr") == "SR 210"
        assert mapper.normalize_law_code("StGB", "de") == "SR 311.0"

    def test_end_to_end_reference_extraction(self):
        """Test complete pipeline from HTML to graph relationships"""
        # Create test HTML
        test_html = """
        <html>
        <body>
            <div id="lawcontent">
                <article id="art_335b">
                    <h6><b>Art. 335b</b> Kündigungsfristen</h6>
                    <div>
                        <p>1 Die Kündigungsfrist beträgt gemäss Art. 335 OR mindestens einen Monat.</p>
                        <p>2 Nach Art. 336 OR kann sie verlängert werden.</p>
                        <p>3 Siehe auch SR 220 für weitere Bestimmungen.</p>
                    </div>
                </article>
            </div>
        </body>
        </html>
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(test_html)
            temp_path = f.name

        try:
            # Step 1: Extract articles with references
            article_extractor = ArticleExtractor()
            article_result = article_extractor.extract(temp_path)

            # Step 2: Extract document-level references
            ref_extractor = HTMLReferenceExtractor(use_cache=False)
            ref_result = ref_extractor.extract_from_html_file(temp_path)

            # Combine results
            combined_result = ExtractionResult()
            combined_result.nodes.extend(article_result.nodes)
            combined_result.relationships.extend(article_result.relationships)
            combined_result.relationships.extend(ref_result.relationships)

            # Verify extraction
            assert len(combined_result.nodes) >= 1  # At least one article
            assert len(combined_result.relationships) >= 3  # Multiple references

            # Check reference types
            ref_types = set()
            for rel in combined_result.relationships:
                if rel[2] == "REFERENCES" and len(rel) > 3:
                    props = rel[3]
                    if 'target_law' in props:
                        ref_types.add(props['target_law'])

            # Should have found OR references and SR reference
            assert 'OR' in ref_types or 'SR_220' in ref_types

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_performance_with_realistic_content(self):
        """Test performance with realistic legal content"""
        # Create a larger test document
        articles = []
        for i in range(1, 51):  # 50 articles
            articles.append(f"""
                <article id="art_{i}">
                    <h6><b>Art. {i}</b> Title {i}</h6>
                    <div>
                        <p>1 Gemäss Art. {i+1} OR und Art. {i+2} ZGB gilt dies.</p>
                        <p>2 Siehe auch SR 220 und Art. {i+3} DSG.</p>
                        <p>3 Nach AS 2023 {1000+i} wurde dies geändert.</p>
                    </div>
                </article>
            """)

        test_html = f"""
        <html>
        <body>
            <div id="lawcontent">
                {''.join(articles)}
            </div>
        </body>
        </html>
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(test_html)
            temp_path = f.name

        try:
            start_time = time.time()

            # Extract articles with references
            extractor = ArticleExtractor()
            result = extractor.extract(temp_path)

            elapsed = time.time() - start_time

            # Should extract 50 articles
            assert len(result.nodes) == 50

            # Should extract many references (at least 3 per article)
            ref_count = len([r for r in result.relationships if r[2] == "REFERENCES"])
            assert ref_count >= 150

            # Calculate extraction rate
            rate = ref_count / elapsed if elapsed > 0 else 0

            # Should achieve good performance (relaxed for integration test)
            assert rate > 100, f"Rate {rate:.0f} refs/sec is too slow"

            print(f"Performance: {ref_count} references in {elapsed:.2f}s = {rate:.0f} refs/sec")

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.skipif(not Path("fedlex-assets").exists(), reason="fedlex-assets not available")
    def test_with_real_fedlex_file(self):
        """Test with actual fedlex HTML file if available"""
        # Find a real HTML file
        html_files = list(Path("fedlex-assets").rglob("*.html"))[:1]

        if not html_files:
            pytest.skip("No fedlex HTML files found")

        test_file = str(html_files[0])
        print(f"Testing with real file: {test_file}")

        # Extract articles with references
        extractor = ArticleExtractor()
        result = extractor.extract(test_file)

        # Should extract something
        assert len(result.nodes) > 0 or len(result.relationships) > 0

        # Print statistics
        print(f"Extracted {len(result.nodes)} articles")
        ref_count = len([r for r in result.relationships if r[2] == "REFERENCES"])
        print(f"Found {ref_count} references")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])