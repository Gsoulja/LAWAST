#!/usr/bin/env python3
"""
Test Apertus using conversational API
"""

from huggingface_hub import InferenceClient
import os

api_key = os.getenv("HUGGINGFACE_API_KEY")

# Initialize client
client = InferenceClient(token=api_key)

# Model that supports conversational
model = "swiss-ai/Apertus-8B-Instruct-2509"

print(f"Testing model: {model}")
print("-" * 60)

try:
    # Use conversational API
    messages = [
        {"role": "user", "content": "Hello, how are you today?"}
    ]

    response = client.chat_completion(
        model=model,
        messages=messages,
        max_tokens=100,
        temperature=0.7,
    )

    print("✅ Success!")
    print(f"Response: {response.choices[0].message.content}")

except Exception as e:
    print(f"❌ Chat completion failed: {str(e)}")

    # Try conversational endpoint
    try:
        print("\nTrying conversational endpoint...")
        response = client.conversational(
            model=model,
            text="Hello, how are you?",
            max_new_tokens=100,
        )

        print("✅ Success with conversational!")
        print(f"Response: {response['generated_text']}")

    except Exception as e2:
        print(f"❌ Conversational failed: {str(e2)}")

# Try direct endpoint access
print("\n" + "=" * 60)
print("Testing direct endpoint access...")

try:
    import requests

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Try the AWS endpoint directly
    url = "https://grg8pdp0ndex8j6a.us-east-1.aws.endpoints.huggingface.cloud"

    data = {
        "inputs": "Hello, how are you?",
        "parameters": {
            "max_new_tokens": 100,
            "temperature": 0.7,
        }
    }

    response = requests.post(url, headers=headers, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")

except Exception as e:
    print(f"❌ Direct request failed: {str(e)}")