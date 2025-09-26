#!/usr/bin/env python3
"""
Test LAWAST API endpoints
"""

import requests
import json
from rich.console import Console
from rich.panel import Panel

console = Console()

API_BASE = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    console.print("\n[bold]Testing Health Endpoint[/bold]")
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            data = response.json()
            console.print(f"✅ Status: {data['status']}")
            console.print(f"Components: {json.dumps(data['components'], indent=2)}")
        else:
            console.print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        console.print(f"❌ Error: {e}")


def test_chat_completion():
    """Test OpenAI-compatible chat endpoint"""
    console.print("\n[bold]Testing Chat Completion Endpoint[/bold]")

    payload = {
        "model": "lawast",
        "messages": [
            {"role": "user", "content": "Was ist das Rentenalter in der Schweiz?"}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }

    try:
        response = requests.post(
            f"{API_BASE}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            console.print("✅ Chat completion successful")
            console.print(f"Response: {data['choices'][0]['message']['content'][:200]}...")
        else:
            console.print(f"❌ Request failed: {response.status_code}")
            console.print(response.text)
    except Exception as e:
        console.print(f"❌ Error: {e}")


def test_direct_query():
    """Test direct query endpoint"""
    console.print("\n[bold]Testing Direct Query Endpoint[/bold]")

    payload = {
        "query": "What are the main Swiss federal laws?",
        "include_citations": True,
        "include_confidence": True
    }

    try:
        response = requests.post(
            f"{API_BASE}/v1/query",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            console.print("✅ Query successful")
            console.print(Panel(
                f"Answer: {data['answer'][:200]}...\n"
                f"Confidence: {data.get('confidence', 'N/A')}\n"
                f"Citations: {len(data.get('citations', []))} sources\n"
                f"Execution Time: {data.get('execution_time', 'N/A')}s",
                title="Query Result"
            ))
        else:
            console.print(f"❌ Request failed: {response.status_code}")
    except Exception as e:
        console.print(f"❌ Error: {e}")


def main():
    console.print(Panel.fit(
        "[bold cyan]LAWAST API Test Suite[/bold cyan]",
        border_style="cyan"
    ))

    console.print("\nMake sure the API server is running:")
    console.print("  python -m src.interfaces.api.app")

    test_health()
    test_chat_completion()
    test_direct_query()

    console.print("\n[bold green]Test complete![/bold green]")
    console.print("\nTo integrate with OpenWebUI:")
    console.print("  1. Set API Base URL in OpenWebUI to: http://localhost:8000/v1")
    console.print("  2. Select 'lawast' as the model")
    console.print("  3. Start chatting!")


if __name__ == "__main__":
    main()