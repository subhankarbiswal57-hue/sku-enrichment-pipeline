"""
Test the live Grok API call using the real XAI_API_KEY from .env.
Run from project root: python3 scripts/test_grok_api.py

This test uses the real curated Philips source file (565374) and calls
the actual Grok API — requires a valid XAI_API_KEY in .env.
"""
import os
import sys
import json
import types
import re

sys.path.insert(0, "src")

# Load .env
from dotenv import load_dotenv
load_dotenv(".env")

openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
xai_key = os.environ.get("XAI_API_KEY", "")
llm_model = os.environ.get("LLM_MODEL", "google/gemma-4-26b-a4b-it:free")

if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
    print(f"OpenRouter API key loaded: {openrouter_key[:12]}...{openrouter_key[-4:]}")
    print(f"Model: {llm_model}")
elif xai_key and xai_key != "your_xai_api_key_here":
    print(f"xAI API key loaded: {xai_key[:8]}...{xai_key[-4:]}")
    print("Model: grok-beta")
else:
    print("ERROR: Neither OPENROUTER_API_KEY nor XAI_API_KEY set in .env")
    sys.exit(1)

print("Calling LLM API for SKU 565374 (Philips 75W A19 Med 27k 4pk)...\n")

# Stub normalize so enrich.py can import it
norm = types.ModuleType("normalize")
_W_RE   = re.compile(r"(?<![A-Za-z])(\d+)\s*[wW]\b")
_CCT_RE = re.compile(r"\b([2-7]\d)[kK]\b")
_PK_RE  = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)
_BASE   = {"med":"E26","medium":"E26","e26":"E26","e27":"E26","cand":"E12","candelabra":"E12"}
norm.parse_wattage   = lambda d: (f"{m.group(1)} W" if (m := _W_RE.search(d)) else None)
norm.parse_cct       = lambda d: (f"{int(m.group(1))*100} K" if (m := _CCT_RE.search(d)) else None)
norm.parse_pack_qty  = lambda d: (m.group(1) if (m := _PK_RE.search(d)) else None)
norm.parse_base_type = lambda d: next((v for w in d.split() if (v := _BASE.get(w.lower()))), None)
sys.modules["normalize"] = norm

# Stub retrieve to use curated source
import json as _json
retr = types.ModuleType("retrieve")
with open("sample_data/curated_sources/manifest.json") as f:
    _MANIFEST = _json.load(f)
def _retrieve(mpn):
    e = _MANIFEST.get(mpn)
    if not e: return None
    txt = open(f"sample_data/curated_sources/{e['source_file']}").read()
    return {"source_url": e["source_url"], "source_text": txt}
retr.retrieve = _retrieve
sys.modules["retrieve"] = retr

from models import CleanRow
from enrich import enrich

row = CleanRow("565374", "565374 75W Led A19 Med 27k 4pk", None, None, None, "Phillips Lighting", "5831")
result = enrich(row)

print(f"MFR URL: {result.mfr_url}")
print(f"Attributes:")
for a in result.attributes:
    val = f"{a.value} {a.uom}".strip() if a.value else "—"
    novel = " [NOVEL]" if a.is_novel_value else ""
    print(f"  [{a.state:5} {a.confidence:6}] {a.label:<22} {val}{novel}")

print(f"\nMarketing description: {result.marketing_description}")
print(f"Item features: {result.item_features}")
