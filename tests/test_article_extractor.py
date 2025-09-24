"""
Unit tests for Article Content Extraction Module

Tests all article extraction functionality including:
- Article number extraction (all formats)
- Multi-language title extraction
- Paragraph and subpoint parsing
- Edge cases and error handling
- Performance validation
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup

from src.extractors.article_extractor import (
    ArticleExtractor,
    Article,
    ArticleContent,
    Paragraph,
    Subpoint
)
from src.extractors.base_extractor import ExtractionResult


class TestArticleExtractor:
    """Test suite for ArticleExtractor"""

    @pytest.fixture
    def extractor(self):
        """Create ArticleExtractor instance"""
        return ArticleExtractor()

    @pytest.fixture
    def sample_html_single_article(self):
        """HTML with a single article"""
        return """
        <html>
        <body>
            <main id="maintext">
                <article id="art_1">
                    <h6 class="heading">
                        <a href="#art_1"><b>Art. 1</b> Persönlichkeit</a>
                    </h6>
                    <div class="collapseable">
                        <p>¹ Die Persönlichkeit beginnt mit der Geburt.</p>
                        <p>² Das Kind wird mit der Geburt rechtsfähig.</p>
                        <p>³ Vorbehalten bleiben:</p>
                        <dl>
                            <dt>a.</dt>
                            <dd>die Handlungsfähigkeit;</dd>
                            <dt>b.</dt>
                            <dd>besondere Vorschriften.</dd>
                        </dl>
                        <div class="footnotes">
                            <p id="fn-1">Fassung gemäss Ziff. I des BG vom 19. Dez. 2008</p>
                        </div>
                    </div>
                </article>
            </main>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_html_multiple_articles(self):
        """HTML with multiple articles including complex numbering"""
        return """
        <html>
        <body>
            <main id="maintext">
                <article id="art_1">
                    <h6 class="heading">Art. 1</h6>
                    <div class="collapseable">
                        <p>First article content</p>
                    </div>
                </article>
                <article id="art_1a">
                    <h6 class="heading">Art. 1a</h6>
                    <div class="collapseable">
                        <p>Article 1a content</p>
                    </div>
                </article>
                <article id="art_1bis">
                    <h6 class="heading">Art. 1bis</h6>
                    <div class="collapseable">
                        <p>Article 1bis content</p>
                    </div>
                </article>
                <article id="art_335b">
                    <h6 class="heading">Art. 335b</h6>
                    <div class="collapseable">
                        <p>Article 335b content</p>
                    </div>
                </article>
            </main>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_html_no_articles(self):
        """HTML document without articles"""
        return """
        <html>
        <body>
            <div id="preface">
                <p>This is a decree without articles</p>
            </div>
            <main id="maintext">
                <div class="decree">
                    <p>Decree content here</p>
                </div>
            </main>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_html_repealed_article(self):
        """HTML with a repealed article"""
        return """
        <html>
        <body>
            <main id="maintext">
                <article id="art_5">
                    <h6 class="heading">Art. 5</h6>
                    <div class="collapseable">
                        <p>Aufgehoben</p>
                    </div>
                </article>
            </main>
        </body>
        </html>
        """

    def test_extract_single_article(self, extractor, sample_html_single_article):
        """Test extraction of a single article with all components"""
        result = extractor.extract(sample_html_single_article)

        assert result.statistics['articles_extracted'] == 1
        assert len(result.nodes) == 1

        article_node = result.nodes[0]
        assert article_node['type'] == 'Article'
        assert article_node['number'] == '1'
        assert article_node['number_normalized'] == '001'
        assert 'Persönlichkeit' in article_node.get('title_unknown', '')

        # Check content structure
        content = article_node['content']
        assert len(content['paragraphs']) == 3  # 3 paragraphs, last one has subpoints

        # Check that last paragraph has subpoints
        assert len(content['paragraphs'][2]['subpoints']) == 2
        assert content['paragraphs'][2]['subpoints'][0]['letter'] == 'a'

        # Check footnotes
        assert len(content['footnotes']) == 1
        assert 'Fassung gemäss' in content['footnotes'][0]['text']

    def test_extract_article_numbers(self, extractor, sample_html_multiple_articles):
        """Test extraction of various article number formats"""
        result = extractor.extract(sample_html_multiple_articles)

        assert result.statistics['articles_extracted'] == 4

        numbers = [node['number'] for node in result.nodes]
        assert '1' in numbers
        assert '1a' in numbers
        assert '1bis' in numbers
        assert '335b' in numbers

        # Check normalization
        normalized = [node['number_normalized'] for node in result.nodes]
        assert '001' in normalized
        assert '001a' in normalized
        assert '001bis' in normalized
        assert '335b' in normalized

    def test_extract_paragraphs_with_subpoints(self, extractor, sample_html_single_article):
        """Test extraction of paragraphs with lettered subpoints"""
        result = extractor.extract(sample_html_single_article)

        article_node = result.nodes[0]
        paragraphs = article_node['content']['paragraphs']

        # Find paragraph with subpoints
        para_with_subpoints = None
        for para in paragraphs:
            if para.get('subpoints'):
                para_with_subpoints = para
                break

        assert para_with_subpoints is not None
        assert len(para_with_subpoints['subpoints']) == 2
        assert para_with_subpoints['subpoints'][0]['letter'] == 'a'
        assert 'Handlungsfähigkeit' in para_with_subpoints['subpoints'][0]['text']

    def test_no_articles_document(self, extractor, sample_html_no_articles):
        """Test handling of documents without articles"""
        result = extractor.extract(sample_html_no_articles)

        assert result.statistics.get('documents_without_articles') == 1
        assert result.statistics.get('articles_extracted', 0) == 0
        assert len(result.nodes) == 0
        assert len(result.errors) == 0  # Should not error, just return empty

    def test_repealed_article_detection(self, extractor, sample_html_repealed_article):
        """Test detection of repealed articles"""
        result = extractor.extract(sample_html_repealed_article)

        assert result.statistics['articles_extracted'] == 1
        article_node = result.nodes[0]
        assert article_node['status'] == 'repealed'

    def test_article_number_extraction_edge_cases(self, extractor):
        """Test article number extraction with various edge cases"""
        test_cases = [
            ("Art. 1ter", "1ter", "001ter"),
            ("Art. 41quater", "41quater", "041quater"),
            ("Artikel 99quinquies", "99quinquies", "099quinquies"),
            ("Article 7sexies", "7sexies", "007sexies"),
            ("Art. 100", "100", "100"),
        ]

        for heading_text, expected_num, expected_normalized in test_cases:
            html = f"""
            <article id="test">
                <h6 class="heading">{heading_text}</h6>
                <div class="collapseable"><p>Content</p></div>
            </article>
            """
            soup = BeautifulSoup(html, 'lxml')
            article_elem = soup.find('article')

            number, normalized = extractor._extract_article_number(article_elem)
            assert number == expected_num, f"Failed for {heading_text}"
            assert normalized == expected_normalized, f"Failed normalization for {heading_text}"

    def test_multi_language_support(self, extractor):
        """Test extraction with different language patterns"""
        languages = [
            ('de', 'Artikel', 'Persönlichkeit'),
            ('fr', 'Article', 'Personnalité'),
            ('it', 'Articolo', 'Personalità'),
        ]

        for lang, article_word, title_word in languages:
            html = f"""
            <article id="art_1">
                <h6 class="heading">{article_word} 1 {title_word}</h6>
                <div class="collapseable"><p>Content</p></div>
            </article>
            """

            # Mock file path with language
            file_path = f"/path/to/eli/cc/2020/1/20200101/{lang}/html/file.html"

            result = extractor.extract(html, file_path)
            assert result.statistics['articles_extracted'] == 1

            article_node = result.nodes[0]
            assert article_node['number'] == '1'
            assert article_node['language'] == lang

    def test_footnote_extraction(self, extractor):
        """Test extraction of footnotes"""
        html = """
        <article id="art_1">
            <h6 class="heading">Art. 1</h6>
            <div class="collapseable">
                <p>Article content<sup><a href="#fn-1">1</a></sup></p>
                <div class="footnotes">
                    <p id="fn-1">This is footnote 1</p>
                    <p id="fn-2">This is footnote 2</p>
                </div>
            </div>
        </article>
        """

        result = extractor.extract(html)
        article_node = result.nodes[0]

        footnotes = article_node['content']['footnotes']
        assert len(footnotes) == 2
        assert footnotes[0]['id'] == 'fn-1'
        assert 'This is footnote 1' in footnotes[0]['text']

    def test_table_extraction(self, extractor):
        """Test extraction of tables within articles"""
        html = """
        <article id="art_1">
            <h6 class="heading">Art. 1</h6>
            <div class="collapseable">
                <p>Article content</p>
                <table>
                    <tr><td>Cell 1</td><td>Cell 2</td></tr>
                    <tr><td>Cell 3</td><td>Cell 4</td></tr>
                </table>
            </div>
        </article>
        """

        result = extractor.extract(html)
        article_node = result.nodes[0]

        assert article_node['has_tables'] is True

    def test_superscript_normalization(self, extractor):
        """Test normalization of superscript numbers in paragraphs"""
        superscript_tests = [
            ('¹', '1'),
            ('²³', '23'),
            ('⁴⁵⁶', '456'),
        ]

        for superscript, expected in superscript_tests:
            normalized = extractor._normalize_superscript(superscript)
            assert normalized == expected

    def test_uri_generation(self, extractor):
        """Test URI generation from file paths"""
        test_cases = [
            (
                "/fedlex-assets/eli/cc/1999/404/20200101/de/html/file.html",
                "1",
                "eli/cc/1999/404/20200101/art_1"
            ),
            (
                "/data/eli/cc/2020/778/de/html/doc.html",
                "335b",
                "eli/cc/2020/778/de/art_335b"
            ),
        ]

        for file_path, article_num, expected_uri in test_cases:
            uri = extractor._generate_article_uri(file_path, article_num)
            assert expected_uri in uri

    def test_batch_processing(self, extractor, sample_html_single_article):
        """Test batch processing with progress callback"""
        # Mock parser to return parsed content
        with patch.object(extractor.parser, 'parse') as mock_parse:
            mock_parse.return_value = BeautifulSoup(sample_html_single_article, 'lxml')

            progress_calls = []

            def progress_callback(current, total):
                progress_calls.append((current, total))

            file_paths = [f"file_{i}.html" for i in range(5)]
            results = extractor.process_batch(file_paths, progress_callback)

            assert len(results) == 5
            assert len(progress_calls) == 5
            assert progress_calls[-1] == (5, 5)

    def test_performance_validation(self, extractor):
        """Test performance validation method"""
        metrics = extractor.validate_performance()

        assert 'articles_extracted' in metrics
        assert 'extraction_time_ms' in metrics
        assert 'articles_per_second' in metrics
        assert 'meets_200_per_second_target' in metrics

        # Should extract 200 test articles
        assert metrics['articles_extracted'] == 200

        # Check performance target
        assert metrics['articles_per_second'] > 0

    def test_empty_article_handling(self, extractor):
        """Test handling of empty articles"""
        html = """
        <article id="art_1">
            <h6 class="heading">Art. 1</h6>
            <div class="collapseable"></div>
        </article>
        """

        result = extractor.extract(html)
        assert result.statistics['articles_extracted'] == 1
        article_node = result.nodes[0]
        assert article_node['paragraph_count'] == 0

    def test_malformed_html_handling(self, extractor):
        """Test graceful handling of malformed HTML"""
        malformed_html = """
        <article id="art_1">
            <h6 class="heading">Art. 1
            <div class="collapseable">
                <p>Unclosed paragraph
            </div>
        """

        # Should not raise exception
        result = extractor.extract(malformed_html)
        # May or may not extract depending on parser recovery
        assert isinstance(result, ExtractionResult)

    def test_extract_without_file_path(self, extractor, sample_html_single_article):
        """Test extraction when no file path is provided"""
        soup = BeautifulSoup(sample_html_single_article, 'lxml')
        result = extractor.extract(soup)

        assert result.statistics['articles_extracted'] == 1
        article_node = result.nodes[0]
        assert article_node['uri'] == 'art_1'  # Falls back to article ID

    def test_complex_definition_lists(self, extractor):
        """Test extraction of complex nested definition lists"""
        html = """
        <article id="art_1">
            <h6 class="heading">Art. 1</h6>
            <div class="collapseable">
                <dl>
                    <dt>1.</dt>
                    <dd>First paragraph</dd>
                    <dt>2.</dt>
                    <dd>Second paragraph with subpoints:</dd>
                    <dt>a.</dt>
                    <dd>First subpoint</dd>
                    <dt>b.</dt>
                    <dd>Second subpoint</dd>
                    <dt>3.</dt>
                    <dd>Third paragraph</dd>
                </dl>
            </div>
        </article>
        """

        result = extractor.extract(html)
        article_node = result.nodes[0]
        paragraphs = article_node['content']['paragraphs']

        # Should have 3 main paragraphs
        main_paragraphs = [p for p in paragraphs if p['number'].isdigit()]
        assert len(main_paragraphs) == 3

        # Second paragraph should have subpoints
        para_2 = next(p for p in paragraphs if p['number'] == '2')
        assert len(para_2['subpoints']) == 2

    def test_parser_integration(self, extractor):
        """Test integration with UnifiedHtmlParser"""
        assert extractor.parser is not None
        assert extractor.parser.cache_size == 1000

        # Test with file path (will fail but should handle gracefully)
        result = extractor.extract("/nonexistent/file.html")
        assert len(result.errors) > 0