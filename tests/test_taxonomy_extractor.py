"""
Unit tests for TaxonomyExtractor

Tests taxonomy extraction from Fedlex HTML documents including:
- SR number extraction
- Multi-language title extraction
- Hierarchy building
- Domain classification
- Metadata extraction
- Error handling
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.extractors.taxonomy_extractor import (
    TaxonomyExtractor,
    TaxonomyResult,
    HierarchyLevel
)
from src.extractors.base_extractor import ExtractionResult
from src.parsers.unified_html_parser import UnifiedHtmlParser


class TestTaxonomyExtractor:
    """Test the TaxonomyExtractor class"""

    @pytest.fixture
    def extractor(self):
        """Create a TaxonomyExtractor instance for testing"""
        return TaxonomyExtractor()

    @pytest.fixture
    def sample_fedlex_html(self):
        """Sample Fedlex HTML with all taxonomy elements"""
        return """<!DOCTYPE HTML>
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>fedlex-data-admin-ch-eli-cc</title>
        </head>
        <body>
            <div id="lawcontent">
                <div id="preface">
                    <p class="srnummer">210</p>
                    <h1 class="erlasstitel">Schweizerisches Zivilgesetzbuch</h1>
                    <p>Abgeschlossen am 10. Dezember 1907</p>
                    <p>In Kraft getreten am 1. Januar 1912</p>
                    <p>Stand am 1. Januar 2023</p>
                </div>
                <main id="maintext">
                    <h2>1. Buch: Das Personenrecht</h2>
                    <h3>Titel 1: Die natürlichen Personen</h3>
                    <h4>Kapitel 1: Die Persönlichkeit</h4>
                    <article id="art_1">
                        <h6 class="heading"><b>Art. 1</b></h6>
                        <div class="collapseable">
                            <p>Die Persönlichkeit beginnt mit dem Leben nach der vollendeten Geburt und endet mit dem Tode.</p>
                        </div>
                    </article>
                    <article id="art_2">
                        <h6 class="heading"><b>Art. 2</b></h6>
                        <div class="collapseable">
                            <p>Jedermann hat in der Ausübung seiner Rechte und in der Erfüllung seiner Pflichten nach Treu und Glauben zu handeln.</p>
                        </div>
                    </article>
                </main>
            </div>
        </body>
        </html>"""

    @pytest.fixture
    def minimal_html(self):
        """Minimal HTML with only required elements"""
        return """<!DOCTYPE HTML>
        <html>
        <body>
            <div id="lawcontent">
                <div id="preface">
                    <h1 class="erlasstitel">Test Law Title</h1>
                </div>
            </div>
        </body>
        </html>"""

    @pytest.fixture
    def french_html(self):
        """French language HTML sample"""
        return """<!DOCTYPE HTML>
        <html>
        <body>
            <div id="lawcontent">
                <div id="preface">
                    <p class="srnummer">311.0</p>
                    <h1 class="erlasstitel">Code pénal suisse</h1>
                    <p>Conclu le 21 décembre 1937</p>
                    <p>Entré en vigueur le 1er janvier 1942</p>
                    <p>Etat le 1er juillet 2023</p>
                </div>
                <main id="maintext">
                    <h2>Livre 1: Dispositions générales</h2>
                    <h3>Titre 1: Champ d'application</h3>
                    <h4>Chapitre 1: Crimes et délits</h4>
                </main>
            </div>
        </body>
        </html>"""

    def test_initialization(self):
        """Test TaxonomyExtractor initialization"""
        extractor = TaxonomyExtractor()
        assert extractor.parser is not None
        assert isinstance(extractor.parser, UnifiedHtmlParser)

        # Test with custom parser
        custom_parser = UnifiedHtmlParser(cache_size=100)
        extractor_custom = TaxonomyExtractor(parser=custom_parser)
        assert extractor_custom.parser is custom_parser

    def test_extract_sr_number(self, extractor, sample_fedlex_html):
        """Test SR number extraction"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_fedlex_html, 'lxml')

        sr_number = extractor._extract_sr_number(soup)
        assert sr_number == "210"

    def test_extract_sr_number_missing(self, extractor, minimal_html):
        """Test SR number extraction when missing"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(minimal_html, 'lxml')

        sr_number = extractor._extract_sr_number(soup)
        assert sr_number is None

    def test_extract_title_german(self, extractor, sample_fedlex_html):
        """Test German title extraction"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_fedlex_html, 'lxml')

        titles = extractor._extract_title(soup, 'de')
        assert 'de' in titles
        assert titles['de'] == "Schweizerisches Zivilgesetzbuch"

    def test_extract_title_french(self, extractor, french_html):
        """Test French title extraction"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(french_html, 'lxml')

        titles = extractor._extract_title(soup, 'fr')
        assert 'fr' in titles
        assert titles['fr'] == "Code pénal suisse"

    def test_extract_metadata(self, extractor, sample_fedlex_html):
        """Test metadata extraction from preface"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_fedlex_html, 'lxml')

        metadata = extractor._extract_metadata(soup)
        assert 'conclusion_date' in metadata
        assert 'entry_force_date' in metadata
        assert 'status_date' in metadata
        assert "10. Dezember 1907" in metadata['conclusion_date']
        assert "1. Januar 1912" in metadata['entry_force_date']
        assert "1. Januar 2023" in metadata['status_date']

    def test_extract_hierarchy_german(self, extractor, sample_fedlex_html):
        """Test German hierarchy extraction"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_fedlex_html, 'lxml')

        hierarchy = extractor._extract_hierarchy(soup, 'de')
        assert len(hierarchy) >= 3

        # Check Book level
        book = next((h for h in hierarchy if h.type == 'book'), None)
        assert book is not None
        assert book.number == '1'
        assert 'de' in book.title
        assert 'Personenrecht' in book.title['de']

        # Check Title level
        title = next((h for h in hierarchy if h.type == 'title'), None)
        assert title is not None
        assert title.number == '1'
        assert 'natürlichen Personen' in title.title['de']

        # Check Chapter level
        chapter = next((h for h in hierarchy if h.type == 'chapter'), None)
        assert chapter is not None
        assert chapter.number == '1'
        assert 'Persönlichkeit' in chapter.title['de']

    def test_extract_hierarchy_french(self, extractor, french_html):
        """Test French hierarchy extraction"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(french_html, 'lxml')

        hierarchy = extractor._extract_hierarchy(soup, 'fr')
        assert len(hierarchy) >= 3

        book = next((h for h in hierarchy if h.type == 'book'), None)
        assert book is not None
        assert 'fr' in book.title
        assert 'Dispositions générales' in book.title['fr']

    def test_classify_domain(self, extractor):
        """Test legal domain classification"""
        # Test various SR numbers
        assert extractor._classify_domain("210") == "Private Law - Civil Procedure - Enforcement"
        assert extractor._classify_domain("311.0") == "Criminal Law - Criminal Procedure - Execution"
        assert extractor._classify_domain("101") == "State - People - Authorities"
        assert extractor._classify_domain("414.110") == "Education - Science - Culture"
        assert extractor._classify_domain("510.10") == "National Defence"
        assert extractor._classify_domain("641.20") == "Finance"
        assert extractor._classify_domain("742.101") == "Public Works - Energy - Transport"
        assert extractor._classify_domain("832.10") == "Health - Employment - Social Security"
        assert extractor._classify_domain("946.31") == "Economy - Technical Cooperation"

    def test_classify_domain_invalid(self, extractor):
        """Test domain classification with invalid SR numbers"""
        assert extractor._classify_domain(None) is None
        assert extractor._classify_domain("") is None
        assert extractor._classify_domain("ABC") is None

    def test_extract_language_from_path(self, extractor):
        """Test language extraction from file path"""
        assert extractor._extract_language_from_path("/fedlex-assets/eli/cc/1999/404/20200101/de/html/file.html") == "de"
        assert extractor._extract_language_from_path("/fedlex-assets/eli/cc/1999/404/20200101/fr/html/file.html") == "fr"
        assert extractor._extract_language_from_path("/fedlex-assets/eli/cc/1999/404/20200101/it/html/file.html") == "it"
        assert extractor._extract_language_from_path("/fedlex-assets/eli/cc/1999/404/20200101/rm/html/file.html") == "rm"
        assert extractor._extract_language_from_path("/some/other/path/file.html") is None

    def test_full_extraction(self, extractor, sample_fedlex_html, tmp_path):
        """Test complete extraction pipeline"""
        # Create temporary HTML file
        html_file = tmp_path / "test.html"
        html_file.write_text(sample_fedlex_html)

        # Extract taxonomy
        result = extractor.extract(str(html_file), str(html_file))

        assert isinstance(result, ExtractionResult)
        assert len(result.errors) == 0
        assert result.statistics['documents_processed'] == 1
        assert result.statistics['sr_numbers_extracted'] == 1

        # Check nodes were created
        assert len(result.nodes) > 0

        # Find document node
        doc_nodes = [n for n in result.nodes if n['type'] == 'Document']
        assert len(doc_nodes) == 1

        doc_node = doc_nodes[0]
        assert doc_node['sr_number'] == "210"
        assert doc_node['domain'] == "Private Law - Civil Procedure - Enforcement"
        assert 'title_de' in doc_node or 'title_unknown' in doc_node

        # Check hierarchy nodes
        hierarchy_nodes = [n for n in result.nodes if n['type'].startswith('Hierarchy_')]
        assert len(hierarchy_nodes) >= 3

        # Check relationships
        assert len(result.relationships) > 0
        contains_rels = [r for r in result.relationships if r[2] == 'CONTAINS']
        assert len(contains_rels) >= 3

    def test_extraction_with_missing_elements(self, extractor, minimal_html):
        """Test extraction with missing optional elements"""
        result = extractor.extract(minimal_html)

        assert isinstance(result, ExtractionResult)
        assert result.statistics['documents_processed'] == 1
        assert result.statistics['sr_numbers_extracted'] == 0  # No SR number

    def test_extraction_with_invalid_html(self, extractor):
        """Test extraction with invalid HTML"""
        invalid_html = "<html><body>Invalid structure</body></html>"

        result = extractor.extract(invalid_html)
        assert isinstance(result, ExtractionResult)
        # Should handle gracefully without crashes

    def test_batch_processing(self, extractor, sample_fedlex_html, french_html, tmp_path):
        """Test batch processing of multiple files"""
        # Create test files
        file1 = tmp_path / "test1.html"
        file1.write_text(sample_fedlex_html)

        file2 = tmp_path / "test2.html"
        file2.write_text(french_html)

        file_paths = [str(file1), str(file2)]

        # Track progress
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        # Process batch
        results = extractor.process_batch(file_paths, progress_callback)

        assert len(results) == 2
        assert all(isinstance(r, ExtractionResult) for r in results)
        assert len(progress_calls) == 2
        assert progress_calls == [(1, 2), (2, 2)]

    def test_parse_hierarchy_heading(self, extractor):
        """Test parsing of hierarchy headings"""
        # Test various heading formats
        number, title = extractor._parse_hierarchy_heading("1. Buch: Allgemeine Bestimmungen")
        assert number == "1"
        assert title == "Allgemeine Bestimmungen"

        number, title = extractor._parse_hierarchy_heading("Titel 2: Die natürlichen Personen")
        assert number == "2"
        assert title == "Die natürlichen Personen"

        number, title = extractor._parse_hierarchy_heading("Kapitel III: Test Chapter")
        assert number == "III"
        assert title == "Test Chapter"

        # Test without number
        number, title = extractor._parse_hierarchy_heading("Buch: Allgemeine Bestimmungen")
        assert number is None
        assert title == "Allgemeine Bestimmungen"

    def test_generate_uri(self, extractor):
        """Test URI generation from file paths"""
        uri = extractor._generate_uri("/fedlex-assets/eli/cc/1999/404/20200101/de/html/file.html")
        assert uri == "https://fedlex.data.admin.ch/eli/cc/1999/404"

        uri = extractor._generate_uri("/some/other/path/file.html")
        assert uri.startswith("file://")

    def test_performance_requirement(self, extractor, sample_fedlex_html, tmp_path):
        """Test that performance meets requirements (100 files/minute)"""
        import time

        # Create a test file
        html_file = tmp_path / "perf_test.html"
        html_file.write_text(sample_fedlex_html)

        # Process multiple times
        start = time.time()
        iterations = 10

        for _ in range(iterations):
            result = extractor.extract(str(html_file))
            assert len(result.errors) == 0

        elapsed = time.time() - start
        files_per_second = iterations / elapsed
        files_per_minute = files_per_second * 60

        # Should process at least 100 files per minute
        assert files_per_minute >= 100, f"Processing speed {files_per_minute:.1f} files/min is below requirement"

    def test_multi_language_support(self, extractor):
        """Test support for all 4 official languages"""
        languages = ['de', 'fr', 'it', 'rm']

        for lang in languages:
            assert lang in extractor.HIERARCHY_MARKERS
            markers = extractor.HIERARCHY_MARKERS[lang]
            assert 'book' in markers
            assert 'title' in markers
            assert 'chapter' in markers
            assert 'section' in markers