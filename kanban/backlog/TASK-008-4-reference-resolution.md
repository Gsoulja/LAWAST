# TASK-008.4: Reference Resolution Module

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Parent**: TASK-008
**Estimated Effort**: 1 day
**Created**: 2024-01-24

## Description
Extract and resolve cross-references between articles and laws. This includes internal references (same law), external references (other laws), and hierarchical references. Creates the relationship network essential for legal navigation.

## Acceptance Criteria
- [ ] Extracts all reference patterns
- [ ] Resolves internal article references
- [ ] Resolves external law references
- [ ] Handles range references (Art. 5-10)
- [ ] Multi-language reference patterns
- [ ] Creates REFERENCES relationships
- [ ] Validates reference targets exist
- [ ] Performance: 1000+ references/second
- [ ] All tests pass
- [ ] Documentation complete

## Technical Implementation

### Reference Resolver
```python
class ReferenceResolver:
    def extract_and_resolve(self, article: Article, context: Context) -> List[Reference]:
        references = []

        # Extract raw references
        raw_refs = self.extract_references(article.content)

        for raw_ref in raw_refs:
            # Resolve to actual targets
            resolved = self.resolve_reference(raw_ref, context)

            if resolved:
                references.append(Reference(
                    source=article.uri,
                    target=resolved.uri,
                    type=resolved.type,
                    raw_text=raw_ref.text
                ))

        return references

    def extract_references(self, content):
        patterns = [
            # Internal: Art. 5, Articles 10-15
            r'Art(?:icles?|ikel)?\s*(\d+(?:-\d+)?)',
            # External: Art. 5 OR, Art. 10 ZGB
            r'Art\.\s*(\d+)\s+([A-Z]{2,})',
            # Paragraph: Abs. 2, al. 3
            r'(?:Abs|al)\.\s*(\d+)',
            # Chapter: Kapitel III
            r'(?:Kapitel|Chapitre|Capitolo)\s*([IVX]+|\d+)'
        ]
        ...
```

## Reference Types to Extract

### Internal References
- Same article paragraphs: "Absatz 2", "al. 3"
- Other articles: "Art. 5", "Articles 10-15"
- Sections: "Abschnitt 2", "Section II"
- Chapters: "Kapitel III"

### External References
- Other laws: "Art. 5 OR", "Art. 10 ZGB"
- SR numbers: "SR 210", "SR 311.0"
- International: "Art. 8 EMRK"

### Special Patterns
- Ranges: "Art. 5-10", "Art. 5 bis 10"
- Lists: "Art. 5, 7 und 9"
- Complex: "Art. 5 Abs. 2 lit. a OR"

## Multi-language Patterns
```python
PATTERNS = {
    'de': {
        'article': r'Art(?:ikel)?\s*(\d+[a-z]?)',
        'paragraph': r'Abs(?:atz)?\s*(\d+)',
        'letter': r'lit\.\s*([a-z])'
    },
    'fr': {
        'article': r'Art(?:icle)?\s*(\d+[a-z]?)',
        'paragraph': r'al(?:inéa)?\s*(\d+)',
        'letter': r'let\.\s*([a-z])'
    },
    'it': {
        'article': r'Art(?:icolo)?\s*(\d+[a-z]?)',
        'paragraph': r'cpv\.\s*(\d+)',
        'letter': r'lett\.\s*([a-z])'
    }
}
```

## Relationship Creation
```cypher
// Create reference relationships
MATCH (source:Article {uri: $source_uri})
MATCH (target:Article {uri: $target_uri})
CREATE (source)-[:REFERENCES {
  raw_text: $raw_text,
  type: $ref_type
}]->(target)
```

## Testing Requirements
- Test all reference patterns
- Verify resolution accuracy
- Test with non-existent targets
- Multi-language pattern tests
- Performance benchmarks

## Success Metrics
- 95%+ reference extraction rate
- 90%+ resolution accuracy
- All languages supported
- Graceful handling of unresolved refs