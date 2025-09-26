#!/usr/bin/env python3
"""
Test different endpoint configurations
"""

from huggingface_hub import InferenceClient
import os

api_key = os.getenv("HUGGINGFACE_API_KEY")

# Test different endpoint variations
endpoints = [
    "https://grg8pdp0ndex8j6a.us-east-1.aws.endpoints.huggingface.cloud",
    "https://api-inference.huggingface.co/models/swiss-ai/Apertus-8B-2509",
    "https://api-inference.huggingface.co/models/swiss-ai/Apertus-70B-2509",
]

test_prompt = "Hello, how are you?"

for endpoint in endpoints:
    print(f"\nTesting endpoint: {endpoint}")
    print("-" * 60)

    try:
        client = InferenceClient(model=endpoint, token=api_key)

        # Try simple text generation
        response = client.text_generation(
            test_prompt,
            max_new_tokens=50,
            temperature=0.7,
        )

        print(f"✅ Success!")
        print(f"Response: {response[:100]}...")
        break  # Stop if successful

    except Exception as e:
        print(f"❌ Failed: {str(e)[:200]}")
        continue

print("\n" + "=" * 60)

# If none work, try without model parameter for serverless
print("\nTrying serverless inference with model names:")
model_names = [
    "swiss-ai/Apertus-8B-2509",
    "swiss-ai/Apertus-8B-Instruct-2509",
    "swiss-ai/Apertus-70B-2509",
]

for model_name in model_names:
    print(f"\nTesting model: {model_name}")
    print("-" * 60)

    try:
        client = InferenceClient(token=api_key)

        response = client.text_generation(
            test_prompt,
            model=model_name,
            max_new_tokens=50,
            temperature=0.7,
        )

        print(f"✅ Success!")
        print(f"Response: {response[:100]}...")
        break

    except Exception as e:
        print(f"❌ Failed: {str(e)[:200]})")
        continue