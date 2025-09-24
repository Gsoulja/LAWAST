"""Swiss law classification system"""

LAW_RANGES = {
    "employment": {
        "law": "OR",
        "articles": range(319, 363),
        "title": "Employment Contract"
    },
    "rental": {
        "law": "OR",
        "articles": range(253, 305),
        "title": "Rental and Lease"
    },
    "credit": {
        "law": "OR",
        "articles": range(312, 319),
        "title": "Loan and Credit"
    }
}

def classify_article(law: str, article_num: int) -> str:
    """Classify which domain an article belongs to"""
    if law != "OR":
        return "other"

    for domain, info in LAW_RANGES.items():
        if article_num in info["articles"]:
            return domain

    return "other"

def get_domain_articles(domain: str) -> range:
    """Get article range for a domain"""
    if domain in LAW_RANGES:
        return LAW_RANGES[domain]["articles"]
    return range(0)
