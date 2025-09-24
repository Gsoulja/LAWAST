#!/usr/bin/env python3
"""
Simple test script for Apertus endpoint
"""

from huggingface_hub import InferenceClient
import os

# Endpoint URL
endpoint_url = "https://grg8pdp0ndex8j6a.us-east-1.aws.endpoints.huggingface.cloud"

# Initialize client (set HUGGINGFACE_API_KEY environment variable if needed)
api_key = os.getenv("HUGGINGFACE_API_KEY")
client = InferenceClient(model=endpoint_url, token=api_key)

# Test 1: Simple greeting
print("Test 1: Simple greeting")
print("-" * 50)
prompt = "User: Hello, how are you?\nAssistant:"

response = client.text_generation(
    prompt,
    max_new_tokens=128,
    temperature=0.7,
    do_sample=True,
)

print(f"Prompt: {prompt}")
print(f"Response: {response}")
print()

# Test 2: Legal question (Swiss context)
print("Test 2: Legal question")
print("-" * 50)
legal_prompt = """User: What is Article 337 of the Swiss Code of Obligations about?
Assistant:"""

response = client.text_generation(
    legal_prompt,
    max_new_tokens=256,
    temperature=0.5,
    do_sample=True,
)

print(f"Prompt: {legal_prompt}")
print(f"Response: {response}")
print()

# Test 3: Multilingual (German)
print("Test 3: Multilingual test (German)")
print("-" * 50)
german_prompt = """Benutzer: Was ist der Unterschied zwischen einer AG und einer GmbH in der Schweiz?
Assistent:"""

response = client.text_generation(
    german_prompt,
    max_new_tokens=256,
    temperature=0.5,
    do_sample=True,
)

print(f"Prompt: {german_prompt}")
print(f"Response: {response}")
print()

# Test 4: Streaming
print("Test 4: Streaming response")
print("-" * 50)
stream_prompt = "User: Explain the Swiss federal system in one paragraph.\nAssistant:"

print(f"Prompt: {stream_prompt}")
print("Response (streaming): ", end="")

for token in client.text_generation(
    stream_prompt,
    max_new_tokens=150,
    temperature=0.7,
    do_sample=True,
    stream=True,
):
    print(token, end="", flush=True)

print("\n")
print("All tests completed!")