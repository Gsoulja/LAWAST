# LAWAST Graph Relationship Analysis

## Current Structure in build_lawast_graph.py

### Relationships Being Created:
1. `(Law)-[:HAS_VERSION]->(Version)` - Line 809
2. `(Law)-[:HAS_ARTICLE]->(Article)` - Lines 607, 817
3. `(Article)-[:HAS_PARAGRAPH]->(Paragraph)` - Lines 614, 825
4. `(Article)-[:NEXT]->(Article)` - Line 834 (sequence)
5. `(Domain)-[:HAS_CHILD]->(Book)` - Line 842
6. `(Book)-[:HAS_CHILD]->(Chapter)` - Line 850
7. `(Chapter)-[:HAS_CHILD]->(Section)` - Line 858
8. `(Article)-[:CITES]->(Article)` - Line 1024

## Schema Requirements (from graph_schema.py)

### Defined Relationships:
1. `HAS_VERSION` - Law to Version
2. `CONTAINS` - General containment
3. `HAS_ARTICLE` - Law to Article
4. `HAS_PARAGRAPH` - Article to Paragraph
5. `HAS_SUBPOINT` - Paragraph to Subpoint
6. `HAS_CHILD` - Hierarchical parent-child
7. `CITES` - Legal citations
8. `NEXT` - Sequential ordering

## Required Structure for Language Support

### What We Need:
```
Law (language-neutral, e.g., SR 101)
  ├─[:HAS_VERSION]→ Version (e.g., 2024-01-01)
  │   ├─[:HAS_LANGUAGE]→ LawLanguageVariant (DE)
  │   │   ├─[:HAS_ARTICLE]→ Article (Art. 1 in DE)
  │   │   │   └─[:HAS_PARAGRAPH]→ Paragraph (Para 1 in DE)
  │   │   └─[:HAS_ARTICLE]→ Article (Art. 2 in DE)
  │   │       └─[:HAS_PARAGRAPH]→ Paragraph (Para 1 in DE)
  │   ├─[:HAS_LANGUAGE]→ LawLanguageVariant (FR)
  │   │   ├─[:HAS_ARTICLE]→ Article (Art. 1 in FR)
  │   │   │   └─[:HAS_PARAGRAPH]→ Paragraph (Para 1 in FR)
  │   │   └─[:HAS_ARTICLE]→ Article (Art. 2 in FR)
  │   │       └─[:HAS_PARAGRAPH]→ Paragraph (Para 1 in FR)
  │   ├─[:HAS_LANGUAGE]→ LawLanguageVariant (IT)
  │   ├─[:HAS_LANGUAGE]→ LawLanguageVariant (RM)
  │   └─[:HAS_LANGUAGE]→ LawLanguageVariant (EN)
```

### What We Currently Have:
```
Law (with mixed language properties)
  ├─[:HAS_VERSION]→ Version (partial implementation)
  ├─[:HAS_ARTICLE]→ Article (first language only)
  │   └─[:HAS_PARAGRAPH]→ Paragraph (first language only)
  └─[:HAS_ARTICLE]→ Article (direct, skipping version/language)
```

## Missing Components

### Node Types Missing:
1. **LawLanguageVariant** - Not created at all
2. **Subpoint** - Not implemented
3. **Act** - Not implemented
4. **ManifestationNode** - Not implemented

### Relationships Missing:
1. `(Version)-[:HAS_LANGUAGE]->(LawLanguageVariant)` - Not created
2. `(LawLanguageVariant)-[:HAS_ARTICLE]->(Article)` - Not created
3. `(Paragraph)-[:HAS_SUBPOINT]->(Subpoint)` - Not implemented
4. Language-specific article sequences

### Current Issues:
1. Articles are connected directly to Law, bypassing Version and Language layers
2. Only processing first language variant instead of all
3. No language-specific node creation
4. Version support is incomplete
5. The `extract_law_with_versions_and_languages` method is defined but not used

## Recommendations

### Immediate Fixes Needed:
1. **Use the new extraction method**: Replace old extraction with `extract_law_with_versions_and_languages`
2. **Create LawLanguageVariant nodes**: Currently missing entirely
3. **Fix relationship hierarchy**: Articles should connect to LawLanguageVariant, not directly to Law
4. **Process all languages**: Currently only processing first language
5. **Add HAS_LANGUAGE relationship**: Connect versions to language variants

### Code Changes Required:
1. Update `process_bundesverfassung` to use the new extraction structure
2. Create all language variant nodes
3. Update article creation to respect language hierarchy
4. Fix paragraph extraction to work with language-specific articles
5. Update AST building to understand the new structure