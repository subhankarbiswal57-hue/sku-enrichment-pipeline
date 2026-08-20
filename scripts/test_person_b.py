"""
Test script for Person B's work: enrich.py + describe.py
Run from project root:  python3 scripts/test_person_b.py

Uses inline stubs for normalize.py and retrieve.py so this test
works even before Person A has written their modules.
Never calls the live Grok API.
"""
import os
import re
import sys
import json
import types

# Force fallback — never call the live API
os.environ.pop("XAI_API_KEY", None)

sys.path.insert(0, "src")

# ── Stub: normalize.py ───────────────────────────────────────────────────────
norm = types.ModuleType("normalize")

_W_RE   = re.compile(r"(?<![A-Za-z])(\d+)\s*[wW]\b")
_CCT_RE = re.compile(r"\b([2-7]\d)[kK]\b")
_PK_RE  = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)
_BASE   = {
    "med": "E26", "medium": "E26", "e26": "E26", "e27": "E26",
    "cand": "E12", "candelabra": "E12",
}

def _parse_wattage(desc):
    m = _W_RE.search(desc)
    return f"{m.group(1)} W" if m else None

def _parse_cct(desc):
    m = _CCT_RE.search(desc)
    return f"{int(m.group(1)) * 100} K" if m else None

def _parse_pack_qty(desc):
    m = _PK_RE.search(desc)
    return m.group(1) if m else None

def _parse_base_type(desc):
    for word in desc.replace('"', " ").split():
        key = word.strip(".,").lower()
        if key in _BASE:
            return _BASE[key]
    return None

norm.parse_wattage  = _parse_wattage
norm.parse_cct      = _parse_cct
norm.parse_pack_qty = _parse_pack_qty
norm.parse_base_type = _parse_base_type
sys.modules["normalize"] = norm

# ── Stub: retrieve.py ────────────────────────────────────────────────────────
retr = types.ModuleType("retrieve")

with open("sample_data/curated_sources/manifest.json", encoding="utf-8") as f:
    _MANIFEST = json.load(f)

def _retrieve(mfg_part_num):
    entry = _MANIFEST.get(mfg_part_num)
    if not entry:
        return None
    path = os.path.join("sample_data", "curated_sources", entry["source_file"])
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return {"source_url": entry["source_url"], "source_text": text}
    except OSError:
        return None

retr.retrieve = _retrieve
sys.modules["retrieve"] = retr

# ── Now import Person B's modules ────────────────────────────────────────────
from models import CleanRow
from enrich import enrich
from describe import build_all

# ── Test rows ────────────────────────────────────────────────────────────────
rows = {
    "565374": CleanRow(
        "565374", "565374 75W Led A19 Med 27k 4pk",
        None, None, None, "Phillips Lighting", "5831"
    ),
    "586875": CleanRow(
        "586875", "586875 60W Led Multi CCT 4pk",
        None, None, None, "Phillips Lighting", "5831"
    ),
    "NO_SRC": CleanRow(
        "999999", "999999 40W Led A19 Med 27k 2pk",
        None, None, None, "Phillips Lighting", "5831"
    ),
}

errors = []

for mpn, row in rows.items():
    print(f"\n{'='*60}")
    print(f"SKU: {mpn} | {row.part_desc}")
    print(f"{'='*60}")

    result = enrich(row)

    # Assert: always exactly 7 attributes
    if len(result.attributes) != 7:
        errors.append(f"{mpn}: expected 7 attrs, got {len(result.attributes)}")

    # Assert: labels in fixed order
    from models import ATTRIBUTE_LABELS
    for i, (attr, expected_label) in enumerate(zip(result.attributes, ATTRIBUTE_LABELS)):
        if attr.label != expected_label:
            errors.append(
                f"{mpn}: attr[{i}].label={attr.label!r}, expected {expected_label!r}"
            )

    print(f"MFR URL: {result.mfr_url or '(none)'}")
    for a in result.attributes:
        val = f"{a.value} {a.uom}".strip() if a.value else "—"
        print(f"  [{a.state:5} {a.confidence:6}] {a.label:<20} {val}")

    descs = build_all(result, row.manufacturer_name)
    print()

    # Assert: exactly 5 keys, all str
    expected_keys = {"INVOICE_DESC", "MOBILE_DESC", "SHORT_DESC", "LONG_DESC1", "RETAIL_DESC"}
    if set(descs.keys()) != expected_keys:
        errors.append(f"{mpn}: build_all returned wrong keys: {set(descs.keys())}")

    for key, val in descs.items():
        if not isinstance(val, str):
            errors.append(f"{mpn}: {key} is not str (got {type(val)})")
        print(f"  {key} ({len(val)} chars): {val}")

    # Assert: INVOICE_DESC is ALL CAPS and ≤ 40 chars
    inv = descs["INVOICE_DESC"]
    if inv != inv.upper():
        errors.append(f"{mpn}: INVOICE_DESC is not ALL CAPS: {inv!r}")
    if len(inv) > 40:
        errors.append(f"{mpn}: INVOICE_DESC exceeds 40 chars ({len(inv)}): {inv!r}")

    # Check new fields on EnrichedRow
    print(f"\n  marketing_description: {result.marketing_description!r}")
    print(f"  item_features ({len(result.item_features)}): {result.item_features}")


print(f"\n{'='*60}")
if errors:
    print(f"FAILURES ({len(errors)}):")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
else:
    print("All assertions passed. Person B modules OK.")
