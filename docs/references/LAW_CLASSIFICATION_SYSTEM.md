# Swiss Law Classification System for LAWAST
## Hierarchical Structure and Relationship Mapping

### Overview

This document defines the classification system for Swiss federal law, designed to handle overlapping legal domains, multi-level relationships, and efficient retrieval for the LAWAST system.

---

## 1. SR Number Classification (Primary Level)

### SR Number Ranges - Foundation Structure

The Swiss legal system uses a systematic numbering scheme (SR = Systematic Collection):

| SR Range | Domain | Description | Key Examples |
|----------|---------|-------------|--------------|
| **1xx** | Constitutional Law | Fundamental rights and state organization | 101 (Constitution) |
| **2xx** | Private Law | Civil and commercial relations | 210 (ZGB), 220 (OR) |
| **3xx** | Criminal Law | Criminal code and procedure | 311.0 (StGB) |
| **4xx** | Education & Science | Schools, research, culture | 414.20 (University Act) |
| **5xx** | National Defense | Military and civil protection | 510.10 (Military Law) |
| **6xx** | Finance | Taxes, customs, currency | 641.20 (VAT) |
| **7xx** | Public Works & Energy | Transport, communication, energy | 742.101 (Railway) |
| **8xx** | Health, Work, Social | Employment, insurance, health | 822.11 (ArG) |
| **9xx** | Economy | Trade, agriculture, banking | 941.41 (Banking Act) |

---

## 2. Article Range Mapping (Secondary Level)

### Code of Obligations (SR 220) - Detailed Breakdown

The OR is Switzerland's largest single law with 1186 articles, organized as follows:

```yaml
OR_Structure:
  Part_1_General_Obligations:
    range: [1, 183]
    sections:
      Formation: [1, 40]
      Performance: [68, 96]
      Non-performance: [97, 109]
      Assignment: [164, 183]

  Part_2_Specific_Contracts:
    Sale_and_Exchange:
      range: [184, 236]
      topics: [purchase, warranties, property_transfer]

    Gift:
      range: [239, 252]
      topics: [donations, promises]

    Rental_and_Lease:  # TARGET AREA 1
      range: [253, 304]
      subsections:
        General_Rental: [253, 274]
        Residential_Rental: [275, 290]
        Commercial_Rental: [291, 304]
      key_articles:
        rent_increase: [269, 270]
        termination: [266, 271]
        deposit: [257]

    Loan:
      range: [305, 318]
      includes: [consumer_credit, interest_limits]  # TARGET AREA 3

    Employment:  # TARGET AREA 2
      range: [319, 362]
      subsections:
        Individual_Employment: [319, 343]
        Collective_Employment: [356, 362]
      key_articles:
        termination: [335, 337]
        vacation: [329]
        salary: [322, 323]
        overtime: [321]

    Other_Contracts:
      range: [363, 529]
      includes: [mandate, agency, construction]

  Part_3_Commercial_Entities:
    range: [530, 1186]
    includes: [partnerships, corporations, cooperatives]
```

---

## 3. Multi-Tagging System

### Tag Categories

Each article/law can have multiple tags across different dimensions:

```yaml
Tagging_Structure:
  Primary_Tag:
    description: "Main legal domain"
    examples: [employment, rental, credit]
    cardinality: 1  # Exactly one primary tag

  Secondary_Tags:
    description: "Related domains affected"
    examples: [data_protection, consumer_rights]
    cardinality: n  # Multiple allowed

  Context_Tags:
    description: "Applicable contexts"
    examples: [b2b, b2c, residential, commercial]
    cardinality: n

  Procedural_Tags:
    description: "Legal procedures involved"
    examples: [litigation, mediation, enforcement]
    cardinality: n
```

### Example Tagged Article

```json
{
  "article": "OR 266",
  "title": "Termination of rental agreement",
  "primary_tag": "rental",
  "secondary_tags": ["contract_law", "property_rights"],
  "context_tags": ["residential", "commercial"],
  "procedural_tags": ["notice_period", "formal_requirements"],
  "cross_references": ["OR 271", "OR 272", "ZGB 641"]
}
```

---

## 4. Legal Context Layers

### Hierarchical Layer Model

```
┌─────────────────────────────────────────┐
│      Universal Layer (Always Applies)    │
│  • Constitution (SR 101)                 │
│  • Human Rights                          │
│  • International Treaties                │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Domain Layer (Primary)           │
│  • Employment Law (OR 319-362)           │
│  • Rental Law (OR 253-304)               │
│  • Credit Law (OR 312-318)               │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      Specific Layer (Specialized)        │
│  • IT Employment (Special provisions)    │
│  • Social Housing (VMWG)                 │
│  • Consumer Credit (KKG)                 │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    Implementation Layer (Practical)      │
│  • Ordinances                            │
│  • Canton-specific rules                 │
│  • Municipal regulations                 │
└─────────────────────────────────────────┘
```

---

## 5. Relationship Classification

### Relationship Types

```yaml
Relationship_Types:
  DEFINES:
    strength: strong
    description: "Article defines a legal concept"
    example: "OR 256 DEFINES rent"

  AMENDS:
    strength: strong
    description: "Law changes another law"
    example: "2023 revision AMENDS OR 269"

  IMPLEMENTS:
    strength: strong
    description: "Provides detailed implementation"
    example: "VMWG IMPLEMENTS OR 270 (rent control)"

  REFERENCES:
    strength: medium
    description: "Explicitly mentions another article"
    example: "OR 266 REFERENCES OR 271"

  APPLIES_WITH:
    strength: medium
    description: "Must be considered together"
    example: "OR 337 APPLIES_WITH ArG 10"

  MAY_AFFECT:
    strength: weak
    description: "Potential relevance in certain contexts"
    example: "Constitution Art 27 MAY_AFFECT employment"

  OVERRIDES:
    strength: strong
    description: "Takes precedence over another law"
    example: "Federal law OVERRIDES cantonal law"
```

### Relationship Strength Matrix

| Strength | Weight | Query Impact | Include in Results |
|----------|---------|--------------|-------------------|
| Strong | 1.0 | Always include | Yes - Primary |
| Medium | 0.5 | Include if relevant | Yes - Secondary |
| Weak | 0.2 | Consider for context | Maybe - Context only |

---

## 6. Overlap Resolution Strategy

### Common Overlap Scenarios

```yaml
Overlap_Examples:
  Data_Protection_Overlap:
    primary_domains: [employment, rental, credit]
    relevant_law: "DSG (SR 235.1)"
    resolution: "Apply DSG requirements to domain-specific rules"

  Consumer_Protection_Overlap:
    affects: [rental_b2c, credit_consumer, employment]
    laws: ["OR general", "KKG", "UWG"]
    resolution: "Most protective provision applies"

  Constitutional_Rights_Overlap:
    affects: ALL
    examples:
      - "Property rights (Art 26) → rental"
      - "Economic freedom (Art 27) → employment"
      - "Privacy (Art 13) → data in all contexts"
    resolution: "Constitutional rights prevail"
```

### Overlap Resolution Rules

1. **Hierarchy Rule**: Federal > Cantonal > Municipal
2. **Specificity Rule**: Specific provision > General provision
3. **Temporal Rule**: Newer law > Older law (if same level)
4. **Protection Rule**: More protective > Less protective (consumer/employee)

---

## 7. Implementation for LAWAST

### Quick Lookup Structure

```python
# Python implementation structure
LAW_CLASSIFICATION = {
    "rental": {
        "primary_refs": [
            ("OR", range(253, 305)),  # Main rental law
        ],
        "secondary_refs": [
            ("ZGB", [641, 642, 644]),  # Property law
            ("VMWG", "all"),  # Rent control
        ],
        "context_layers": {
            "universal": ["Constitution Art 26", "ECHR"],
            "domain": ["OR 253-304"],
            "specific": ["VMWG", "Cantonal rental laws"],
        },
        "common_overlaps": ["data_protection", "consumer_rights"],
        "key_articles": {
            "deposit": 257,
            "rent_increase": [269, 270],
            "termination": [266, 271, 272],
            "defects": [259, 259a],
        }
    },

    "employment": {
        "primary_refs": [
            ("OR", range(319, 363)),  # Employment contract
        ],
        "secondary_refs": [
            ("ArG", "all"),  # Labor law
            ("DSG", "relevant"),  # Data protection
            ("GlG", "all"),  # Gender equality
        ],
        "context_layers": {
            "universal": ["Constitution Art 27", "ILO conventions"],
            "domain": ["OR 319-362", "ArG"],
            "specific": ["GAV", "Normal contracts"],
        },
        "common_overlaps": ["data_protection", "social_insurance"],
        "key_articles": {
            "termination": [335, 336, 337],
            "vacation": [329, 329a],
            "salary": [322, 323],
            "illness": [324a],
        }
    },

    "credit": {
        "primary_refs": [
            ("OR", range(312, 319)),  # Loan contracts
        ],
        "secondary_refs": [
            ("KKG", "all"),  # Consumer credit
            ("SchKG", "relevant"),  # Debt collection
            ("UWG", "relevant"),  # Unfair competition
        ],
        "context_layers": {
            "universal": ["Constitution Art 27"],
            "domain": ["OR 312-318", "KKG"],
            "specific": ["BankG", "FINMA regulations"],
        },
        "common_overlaps": ["consumer_protection", "data_protection"],
        "key_articles": {
            "interest_limits": 314,
            "consumer_credit": [KKG", "all"],
            "early_repayment": 317,
        }
    }
}
```

### Query Resolution Flow

```
1. User Query: "Can landlord increase rent?"
   ↓
2. Identify Primary Domain: "rental"
   ↓
3. Find Key Articles: OR 269-270
   ↓
4. Check Overlaps: VMWG (rent control)
   ↓
5. Apply Layers:
   - Universal: Property rights
   - Domain: OR 269-270
   - Specific: Cantonal limits
   ↓
6. Return Structured Result
```

---

## 8. Hackathon Implementation Priority

### Phase 1 (MVP - Day 1 Morning)
- Implement primary classification only
- Hardcode article ranges for 3 target areas
- Simple keyword matching

### Phase 2 (Enhanced - Day 1 Afternoon)
- Add secondary references
- Implement relationship types
- Basic overlap detection

### Phase 3 (If Time - Day 2)
- Full tagging system
- Context layers
- Relationship strength weighting

---

## Conclusion

This classification system provides:
- **Clear structure** for organizing Swiss law
- **Flexible tagging** for overlapping domains
- **Hierarchical layers** for context
- **Relationship mapping** for connected articles
- **Practical implementation** path for hackathon

The system is designed to be extensible - starting simple for the hackathon demo but capable of growing into a comprehensive legal navigation system.

---

*Document Version 1.0 - Swiss AI Hackathon Preparation*