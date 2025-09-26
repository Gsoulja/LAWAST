#!/usr/bin/env python3
"""
Simple test for Apertus integration
"""

import os
os.environ['HUGGINGFACE_API_KEY'] = 'your-huggingface-api-key'

# Test just the Apertus client first
from src.articulation.apertus_client import ApertusChatClient

print("Testing Apertus Client...")
print("-" * 50)

try:
    # Initialize client
    client = ApertusChatClient()

    # Test simple query
    query = "What is the capital of Switzerland?"
    print(f"Query: {query}")

    response = client.chat(
        query,
        system_prompt="You are a helpful assistant. Answer briefly.",
        max_tokens=100
    )

    print(f"Response: {response}")
    print("\n✅ Apertus client working!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()