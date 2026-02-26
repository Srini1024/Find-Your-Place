"""
Quick script to check which Gemini models are available with your API key.
"""

import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env")
    exit(1)

print(f"Testing with API key: {api_key[:10]}...")
print("\n" + "="*60)
print("AVAILABLE GEMINI MODELS:")
print("="*60)

try:
    genai.configure(api_key=api_key)
    
    models = genai.list_models()
    
    text_gen_models = []
    for model in models:
        # Filter for text generation models
        if 'generateContent' in model.supported_generation_methods:
            text_gen_models.append(model.name)
            print(f"✓ {model.name}")
            print(f"  Display: {model.display_name}")
            print(f"  Description: {model.description[:80]}...")
            print()
    
    if not text_gen_models:
        print("No text generation models found!")
    else:
        print(f"\nTotal models available: {len(text_gen_models)}")
        print("\nRecommended for your app:")
        for model_name in text_gen_models:
            if 'flash' in model_name.lower():
                print(f"  → {model_name} (Fast & efficient)")
            elif 'pro' in model_name.lower():
                print(f"  → {model_name} (More capable)")
    
except Exception as e:
    print(f"ERROR: {e}")
    print("\nTip: Make sure your API key is valid and has access to Gemini models")
