# Fedlex Data Connection Guide
## Connecting Swiss Federal Legal Metadata with HTML Content

### Overview

This guide documents the connection architecture between two complementary datasets containing Swiss federal legal documents:

1. **fedlex/** - JSON metadata repository (5.6GB, ~305,440 files)
2. **fedlex-assets/** - HTML content repository (18GB)

Both repositories contain official Swiss federal publications including laws, treaties, and official compilations in multiple languages (German, French, Italian, Romansh, English).

---

## Data Structure

### 1. Fedlex Metadata Repository (`fedlex/`)

#### Directory Structure
```
fedlex/
├── eli/
│   ├── cc/      # Classified compilation (SR/RS) - ~17,000 objects
│   ├── fga/     # Federal gazette (BBl/FF) - ~146,000 objects
│   ├── oc/      # Official compilation (AS/RO/RU) - ~45,000 objects
│   ├── treaty/  # Treaties - ~18,500 objects
│   └── dl/      # Consultation procedures - ~2,000 objects
├── vocabulary/  # Reference vocabularies
└── updates.json # Update tracking file (27MB)
```

#### JSON Object Types
- **ConsolidationAbstract**: Main work metadata
- **Consolidation**: Specific version of a work at a point in time
- **Act**: Legislative acts
- **TreatyProcess**: Treaty documentation
- **Draft**: Consultation drafts

### 2. Fedlex Assets Repository (`fedlex-assets/`)

#### Directory Structure
```
fedlex-assets/
└── eli/
    └── cc/
        └── [year]/
            └── [document_number]/
                └── [date]/
                    └── [language]/
                        └── html/
                            ├── fedlex-data-admin-ch-eli-cc-[...].html
                            ├── fedlex-data-admin-ch-eli-cc-[...]-1.html
                            ├── fedlex-data-admin-ch-eli-cc-[...]-2.html
                            └── ... (paginated content)
```

---

## Connection Architecture

### Primary Connection Method: URI-based Linking

The JSON metadata and HTML content are connected through **Uniform Resource Identifiers (URIs)** that directly map to file system paths.

#### URI to File Path Transformation

```
URI:  https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/it/html
      ↓ (remove protocol and domain)
PATH: fedlex-assets/eli/cc/1999/404/20240101/it/html/
```

### Key Connection Points

#### 1. Abstract Work Level
**Location**: `fedlex/eli/cc/[year]/[number].json`

**Contains**:
- Basic work metadata
- Entry into force date
- Document type
- Available language expressions
- Links to all consolidation versions

**Example**: `fedlex/eli/cc/1999/404.json`
```json
{
  "data": {
    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404",
    "type": ["ConsolidationAbstract", "Work"],
    "attributes": {
      "dateDocument": {"xsd:date": "1999-04-18"},
      "dateEntryInForce": {"xsd:date": "2000-01-01"}
    },
    "references": {
      "isRealizedBy": [
        "https://fedlex.data.admin.ch/eli/cc/1999/404/de",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/fr",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/it"
      ]
    }
  }
}
```

#### 2. Consolidation Version Level
**Location**: `fedlex/eli/cc/[year]/[number]/[date].json`

**Contains**:
- Version-specific metadata
- Applicability date range
- References to manifestations (HTML, PDF, DOCX, XML)

**Example**: `fedlex/eli/cc/1999/404/20240101.json`
```json
{
  "data": {
    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101",
    "attributes": {
      "dateApplicability": {"xsd:date": "2024-01-01"},
      "dateEndApplicability": {"xsd:date": "2024-03-02"}
    },
    "references": {
      "isRealizedBy": [
        "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/it",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/fr",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/de"
      ]
    }
  },
  "included": [{
    "uri": "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/it",
    "references": {
      "isEmbodiedBy": [
        "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/it/html",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/it/pdf-a",
        "https://fedlex.data.admin.ch/eli/cc/1999/404/20240101/it/docx"
      ]
    }
  }]
}
```

#### 3. HTML Manifestation Level
**Location**: `fedlex-assets/eli/cc/[year]/[number]/[date]/[lang]/html/`

**Contains**:
- Actual legal text in HTML format
- Often paginated across multiple files
- Language-specific content

---

## Data Flow

```
┌─────────────────────────┐
│   Abstract Work (JSON)  │
│ fedlex/eli/cc/1999/404  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────────────────┐
│   Consolidation Versions (JSON)     │
│ fedlex/eli/cc/1999/404/20240101     │
│ fedlex/eli/cc/1999/404/20230301     │
│ fedlex/eli/cc/1999/404/20220101     │
└───────────┬─────────────────────────┘
            │
            ▼
┌─────────────────────────────────────┐
│   Language Expressions (JSON ref)   │
│ .../20240101/de                     │
│ .../20240101/fr                     │
│ .../20240101/it                     │
└───────────┬─────────────────────────┘
            │
            ▼
┌─────────────────────────────────────┐
│   HTML Manifestations (Files)       │
│ fedlex-assets/.../de/html/*.html    │
│ fedlex-assets/.../fr/html/*.html    │
│ fedlex-assets/.../it/html/*.html    │
└─────────────────────────────────────┘
```

---

## Important JSON Fields for Navigation

### Primary Navigation Fields

| Field | Purpose | Example |
|-------|---------|---------|
| `uri` | Unique identifier and path base | `https://fedlex.data.admin.ch/eli/cc/1999/404` |
| `isRealizedBy` | Links to language versions | Array of language-specific URIs |
| `isEmbodiedBy` | Links to format manifestations | Array of format-specific URIs (html, pdf, etc.) |
| `dateApplicability` | Version effective date | `2024-01-01` |
| `dateEndApplicability` | Version end date | `2024-03-02` |
| `language` | ISO language code | `http://publications.europa.eu/resource/authority/language/ITA` |

### Language Codes Mapping

| Code | Language | URI Suffix |
|------|----------|------------|
| DEU | German | `/de` |
| FRA | French | `/fr` |
| ITA | Italian | `/it` |
| ROH | Romansh | `/rm` |
| ENG | English | `/en` |

---

## Practical Usage Examples

### Example 1: Finding Current Version of a Law

1. **Start with abstract work**: `fedlex/eli/cc/1999/404.json`
2. **List available versions**: Check directory `fedlex/eli/cc/1999/404/`
3. **Select latest version**: e.g., `fedlex/eli/cc/1999/404/20240101.json`
4. **Extract HTML reference**: Find `isEmbodiedBy` with `/html` suffix
5. **Locate HTML files**: Navigate to `fedlex-assets/eli/cc/1999/404/20240101/[lang]/html/`

### Example 2: Retrieving Multilingual Versions

For document `cc/1999/404` on date `20240101`:

```bash
# German version
fedlex-assets/eli/cc/1999/404/20240101/de/html/*.html

# French version
fedlex-assets/eli/cc/1999/404/20240101/fr/html/*.html

# Italian version
fedlex-assets/eli/cc/1999/404/20240101/it/html/*.html
```

### Example 3: Tracking Document Evolution

```bash
# List all versions of Swiss Constitution
ls fedlex/eli/cc/1999/404/

# Output: Multiple JSON files with dates
# 20000101.json, 20010610.json, 20020303.json, ...

# Each represents the law as it stood on that date
```

---

## Working with the Data

### Data Characteristics

1. **JSON files**:
   - Prettified for git tracking
   - `timestampms` field set to null to avoid unnecessary commits
   - Updated multiple times daily

2. **HTML files**:
   - Paginated (suffix -1, -2, -3, etc.)
   - Images and assets referenced but not included
   - New versions get new names (no git history within files)

3. **Update tracking**:
   - `updates.json` contains last crawler update date for each file
   - Useful for monitoring changes

### Common Patterns

1. **Document Types**:
   - `/eli/cc/` - Classified compilation (current laws)
   - `/eli/oc/` - Official compilation (law changes)
   - `/eli/fga/` - Federal gazette (proposals)
   - `/eli/treaty/` - International treaties

2. **Version Dating**:
   - Format: `YYYYMMDD`
   - Represents applicability date, not publication date
   - Multiple versions per year common for frequently amended laws

3. **File Naming**:
   - Base: `fedlex-data-admin-ch-eli-[type]-[identifiers]-[date]-[lang]-html`
   - Pagination: Append `-1`, `-2`, etc. for multi-page documents

---

## Implementation Considerations

### For Developers

1. **Path Construction**:
   ```python
   def uri_to_path(uri, base_dir="fedlex-assets"):
       # Remove protocol and domain
       path = uri.replace("https://fedlex.data.admin.ch/", "")
       return os.path.join(base_dir, path)
   ```

2. **Version Selection**:
   - Latest version: Sort by date, take last
   - Version at date: Find last version <= target date
   - All versions: List directory contents

3. **Language Handling**:
   - Always check available languages in JSON
   - Not all documents available in all languages
   - Older documents may have limited language support

### Performance Tips

1. **Caching**: URI mappings are stable, cache path transformations
2. **Lazy Loading**: HTML files are large, load on demand
3. **Indexing**: Build indices for common queries (by date, language, type)
4. **Batch Processing**: Group operations by directory to minimize I/O

---

## Resources

- **Official Portal**: [www.fedlex.admin.ch](https://www.fedlex.admin.ch)
- **Backend API**: [fedlex.data.admin.ch](https://fedlex.data.admin.ch)
- **Metadata Repository**: [github.com/droid-f/fedlex](https://github.com/droid-f/fedlex)
- **Assets Repository**: [github.com/droid-f/fedlex-assets](https://github.com/droid-f/fedlex-assets)

## License

Data usage requirements: [fedlex.admin.ch/broadcasters](https://www.fedlex.admin.ch/broadcasters)
Repository license: CC BY-NC-SA 4.0 (non-commercial use only)

---

*Document generated for LAWAST project - September 2025*