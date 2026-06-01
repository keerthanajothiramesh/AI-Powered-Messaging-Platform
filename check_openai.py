"""Quick sanity-check: verifies the OPENAI_API_KEY in .env is valid."""
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY", "")
if not api_key or api_key == "your-openai-api-key-here":
    print("ERROR  OPENAI_API_KEY is not set in .env")
    raise SystemExit(1)

print(f"Key   {api_key[:8]}...{api_key[-4:]}  ({len(api_key)} chars)\n")

MODEL = "gpt-4o-mini"
print(f"Testing {MODEL} ...")

try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=5,
    )
    print(f"OK    API working — response: {response.choices[0].message.content.strip()}")
except Exception as e:
    print(f"FAIL  {e}")
    raise SystemExit(1)
