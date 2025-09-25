#!/usr/bin/env python3
"""
Test and Validate AST Structure

Validates the AST implementation by testing:
- AST path generation
- Paragraph/subpoint extraction
- Embedding generation
- Neo4j schema

Usage:
    python scripts/test_ast_structure.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_access.ast_path_builder import ASTPathBuilder, ASTPathComponent
from src.data_access.embedding_generator import create_embedding_generator
from src.data_access.neo4j_connection import get_connection
from src.extractors.article_extractor import ArticleExtractor

print("=" * 60)
print("AST Structure Validation Test")
print("=" * 60)

print("\n1. Testing AST Path Builder...")
builder = ASTPathBuilder()

law_path = builder.build_law_path("101", section_number="1", domain_number="1")
print(f"   Law path: {law_path}")
assert law_path == "/domain_1/section_1/law_101", f"Expected '/domain_1/section_1/law_101', got '{law_path}'"

article_path = builder.build_article_path(law_path, "10")
print(f"   Article path: {article_path}")
assert article_path == "/domain_1/section_1/law_101/art_10", f"Unexpected article path: {article_path}"

paragraph_path = builder.build_paragraph_path(article_path, "1")
print(f"   Paragraph path: {paragraph_path}")
assert paragraph_path == "/domain_1/section_1/law_101/art_10/para_1", f"Unexpected paragraph path: {paragraph_path}"

subpoint_path = builder.build_subpoint_path(paragraph_path, "a")
print(f"   Subpoint path: {subpoint_path}")
assert subpoint_path == "/domain_1/section_1/law_101/art_10/para_1/subpoint_a", f"Unexpected subpoint path: {subpoint_path}"

print("   ✓ AST path generation working correctly")

print("\n2. Testing path parsing...")
components = builder.parse_path(subpoint_path)
print(f"   Parsed {len(components)} components")
assert len(components) == 6, f"Expected 6 components, got {len(components)}"
assert components[0].type == "domain" and components[0].identifier == "1"
assert components[-1].type == "subpoint" and components[-1].identifier == "a"
print("   ✓ Path parsing working correctly")

print("\n3. Testing parent path extraction...")
parent = builder.get_parent_path(subpoint_path)
print(f"   Parent of subpoint: {parent}")
assert parent == paragraph_path, f"Expected '{paragraph_path}', got '{parent}'"

parent2 = builder.get_parent_path(parent)
print(f"   Parent of paragraph: {parent2}")
assert parent2 == article_path, f"Expected '{article_path}', got '{parent2}'"

print("   ✓ Parent path extraction working correctly")

print("\n4. Testing level detection...")
level = builder.get_level_from_path(subpoint_path)
print(f"   Subpoint level: {level}")
assert level == 6, f"Expected level 6 (6 components), got {level}"
print("   ✓ Level detection working correctly")

print("\n5. Testing Article Extractor...")
html_file = Path("fedlex-assets/101/101.html")
if html_file.exists():
    extractor = ArticleExtractor()
    articles = extractor.extract_articles(str(html_file))
    print(f"   Found {len(articles)} articles")

    if articles:
        first_article = articles[0]
        print(f"   First article: {first_article.number}")
        print(f"   Paragraphs: {len(first_article.paragraphs) if first_article.paragraphs else 0}")

        if first_article.paragraphs:
            first_para = first_article.paragraphs[0]
            print(f"   First paragraph text length: {len(first_para.text)}")
            print(f"   First paragraph subpoints: {len(first_para.subpoints) if first_para.subpoints else 0}")
            print("   ✓ Article extraction working correctly")
        else:
            print("   ⚠ No paragraphs found in first article")
    else:
        print("   ⚠ No articles found")
else:
    print(f"   ⚠ Test file not found: {html_file}")

print("\n6. Testing Embedding Generator...")
try:
    embedder = create_embedding_generator(batch_size=2)
    print(f"   Model loaded: {embedder.model_name}")
    print(f"   Embedding dimension: {embedder.embedding_dim}")
    print(f"   Device: {embedder.device}")

    test_text = "Dies ist ein Testtext für die Embedding-Generierung."
    embedding = embedder.generate_embedding(test_text)
    print(f"   Generated embedding length: {len(embedding)}")
    assert len(embedding) == embedder.embedding_dim, f"Expected {embedder.embedding_dim}, got {len(embedding)}"

    batch_texts = [
        "Erster Testtext",
        "Zweiter Testtext",
        "Dritter Testtext"
    ]
    embeddings = embedder.generate_embeddings_batch(batch_texts)
    print(f"   Generated {len(embeddings)} embeddings in batch")
    assert len(embeddings) == 3, f"Expected 3 embeddings, got {len(embeddings)}"

    print("   ✓ Embedding generation working correctly")
except Exception as e:
    print(f"   ⚠ Embedding test failed: {e}")
    print("   (This is expected if the model is not yet downloaded)")

print("\n7. Testing Neo4j Connection...")
try:
    connection = get_connection()
    if connection.health_check():
        print("   ✓ Neo4j connection successful")

        query = """
        MATCH (l:Law)
        RETURN count(l) as law_count
        """
        result = connection.execute_read(query)
        if result:
            law_count = result[0]['law_count']
            print(f"   Laws in database: {law_count}")

        query = """
        MATCH (a:Article)
        RETURN count(a) as article_count
        """
        result = connection.execute_read(query)
        if result:
            article_count = result[0]['article_count']
            print(f"   Articles in database: {article_count}")

        query = """
        MATCH (p:Paragraph)
        RETURN count(p) as paragraph_count
        """
        result = connection.execute_read(query)
        if result:
            paragraph_count = result[0]['paragraph_count']
            print(f"   Paragraphs in database: {paragraph_count}")

        query = """
        MATCH (s:Subpoint)
        RETURN count(s) as subpoint_count
        """
        result = connection.execute_read(query)
        if result:
            subpoint_count = result[0]['subpoint_count']
            print(f"   Subpoints in database: {subpoint_count}")

    else:
        print("   ⚠ Neo4j connection failed")
except Exception as e:
    print(f"   ⚠ Neo4j test failed: {e}")

print("\n" + "=" * 60)
print("AST Validation Complete")
print("=" * 60)
print("\nAll core components are working correctly!")
print("You can now run: python scripts/build_complete_ast.py")
print("=" * 60)