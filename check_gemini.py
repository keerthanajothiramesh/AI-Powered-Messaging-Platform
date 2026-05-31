"""Quick check: is the Gemini API key valid and working?
Run from the messaging-platform directory:
    python check_gemini.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "")
if not api_key:
    print("FAIL  GEMINI_API_KEY is not set in .env")
    raise SystemExit(1)

print(f"Key   {api_key[:8]}...{api_key[-4:]}  ({len(api_key)} chars)\n")

import google.generativeai as genai
genai.configure(api_key=api_key)

MODEL = "models/gemini-2.5-flash"
print(f"Testing {MODEL} ...")
try:
    model = genai.GenerativeModel(MODEL)
    response = model.generate_content("Say 'API working' and nothing else.")
    print(f"OK    {response.text.strip()}")
except Exception as e:
    print(f"FAIL  {e}")
    raise SystemExit(1)
