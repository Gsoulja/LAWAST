#!/usr/bin/env python3
"""Debug API response structure"""

import requests
import json
from rich.console import Console
from rich.json import JSON

console = Console()

# Test query
es_query = {
    "query": {
        "query_string": {
            "query": "Meinungsfreiheit",
            "default_operator": "AND"
        }
    },
    "size": 1
}

response = requests.post(
    "https://entscheidsuche.ch/_search.php",
    json=es_query,
    timeout=10
)

if response.status_code == 200:
    data = response.json()
    console.print("\n[bold]Full Response Structure:[/bold]\n")

    # Pretty print the entire response
    console.print(JSON.from_data(data))

    # Check what fields are actually present
    if data.get('hits', {}).get('hits'):
        first_hit = data['hits']['hits'][0]
        console.print("\n[bold]Available fields in _source:[/bold]")
        if '_source' in first_hit:
            console.print(list(first_hit['_source'].keys()))
        else:
            console.print("No _source field")

        console.print("\n[bold]All top-level fields in hit:[/bold]")
        console.print(list(first_hit.keys()))