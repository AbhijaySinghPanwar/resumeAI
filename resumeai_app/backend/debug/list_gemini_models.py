import os
import google.generativeai as genai

# The user requested specifically this exact script structure in their prompt.
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

print("=== Available Models ===")
try:
    for model in genai.list_models():
        print(model.name)
except Exception as e:
    print(f"Error fetching models via legacy sdk: {e}")

# We will also use the new SDK to ensure we see the active models accurately.
print("\n=== Models via google-genai SDK ===")
try:
    from google import genai as new_genai
    client = new_genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
    models = list(client.models.list())
    for m in models:
        actions = getattr(m, 'supported_actions', None) or getattr(m, 'supported_generation_methods', [])
        if "generateContent" in actions:
            print(f"{m.name} (Supports generateContent)")
except Exception as e:
    print(f"Error fetching models via new sdk: {e}")

# Test the backend singleton
print("\n=== Active Model Selected by Service ===")
import sys
import os as _os
sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..")))
from services.gemini_service import GeminiService
svc = GeminiService()
print(f"Available: {svc.is_available}")
print(f"Active Model: {svc.active_model}")
