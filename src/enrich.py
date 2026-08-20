"""
Stage 4 — Attribute Extraction & EnrichedRow Assembly  (Person B)

Combines two attribute sources per row:
  1. Deterministic parsing from Part_Desc via normalize.py
     → Wattage, Color Temperature, Pack Quantity, Base Type
     → confidence=High, evidence_note="Part_Desc"

  2. Extraction from retrieved manufacturer page via Grok API (or regex fallback)
     → Lumens, Rated Life, Dimmable
     → confidence=Medium if found, Low if not

Always returns EnrichedRow with exactly 7 Attributes in fixed ATTRIBUTE_LABELS order.
Never raises — all errors are caught and logged.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import urllib.request
import urllib.error
from typing import TYPE_CHECKING

# Load .env file if present (so XAI_API_KEY is picked up automatically)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass  # dotenv not installed — rely on environment variable being set manually

sys.path.insert(0, os.path.dirname(__file__))

from models import (
    ATTRIBUTE_LABELS,
    Attribute,
    CleanRow,
    EnrichedRow,
    make_blank_attr,
    make_found_attr,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API config — OpenRouter (primary) or xAI Grok (fallback)
# ---------------------------------------------------------------------------

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
XAI_API_KEY        = os.environ.get("XAI_API_KEY")
LLM_MODEL          = os.environ.get("LLM_MODEL", "qwen/qwen3-8b:free")

# Determine which API to use
if OPENROUTER_API_KEY:
    _API_URL = "https://openrouter.ai/api/v1/chat/completions"
    _API_KEY = OPENROUTER_API_KEY
    _MODEL   = LLM_MODEL
elif XAI_API_KEY:
    _API_URL = "https://api.x.ai/v1/chat/completions"
    _API_KEY = XAI_API_KEY
    _MODEL   = "grok-beta"  # use grok-beta — grok-4 requires special access
else:
    _API_URL = None
    _API_KEY = None
    _MODEL   = None

SYSTEM_PROMPT = (
    "Extract product attributes from the manufacturer page text below. "
    "Return ONLY a JSON object with exactly these three fields: "
    '{"lumens": <integer or null>, "rated_life_hours": <integer or null>, '
    '"dimmable": <true/false/null>}. '
    "Use null for anything not explicitly stated in the text — never guess."
)

# ---------------------------------------------------------------------------
# Regex patterns for fallback source extraction
# ---------------------------------------------------------------------------

# Numeric attribute patterns
LUMENS_RE   = re.compile(r"(\d{3,5})\s*lm", re.IGNORECASE)
LIFE_RE     = re.compile(r"(\d{3,6})\s*h(?:our|r)?(?:\b|$)", re.IGNORECASE)
DIMMABLE_RE = re.compile(r"\bdi(?:mm|mming|mmable)\b", re.IGNORECASE)

# Marketing description: paragraph(s) after "Description:" heading
MARKETING_DESC_RE = re.compile(
    r"(?:^|\n)(?:Description|Marketing|Overview)[:\s]*\n+(.*?)(?:\n\n|\nSpecification|\nTitle|\Z)",
    re.DOTALL | re.IGNORECASE,
)
# Item features: bullet-point lines (-, •, *) — require at least 3 chars of content
ITEM_FEATURE_RE = re.compile(r"^[-•*]\s*(.{3,})$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Lazy import of normalize functions (Person A's module)
# If Person A hasn't written normalize.py yet, gracefully degrade.
# ---------------------------------------------------------------------------

def _get_normalize():
    try:
        import normalize
        return normalize
    except ImportError:
        logger.warning("normalize.py not found — deterministic attributes will all be BLANK")
        return None


def _get_retrieve():
    try:
        import retrieve
        return retrieve
    except ImportError:
        logger.warning("retrieve.py not found — source retrieval will return None")
        return None


# ---------------------------------------------------------------------------
# Helper: split a formatted unit string into (value, uom)
# e.g. "75 W" -> ("75", "W"),  "2700 K" -> ("2700", "K"),  None -> (None, None)
# ---------------------------------------------------------------------------

def _split_value_uom(formatted: str | None) -> tuple[str | None, str | None]:
    if formatted is None:
        return None, None
    parts = formatted.strip().split()
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], None
    return formatted, None


# ---------------------------------------------------------------------------
# Stage 1 of 2: deterministic attributes from Part_Desc
# ---------------------------------------------------------------------------

def _deterministic_attributes(row: CleanRow) -> list[Attribute]:
    """
    Return exactly 4 Attributes from Part_Desc parsing.
    Order: Wattage, Color Temperature, Pack Quantity, Base Type.

    Value and UOM are stored SEPARATELY:
        Wattage:           value="75",   uom="W"
        Color Temperature: value="2700", uom="K"
        Pack Quantity:     value="4",    uom=None
        Base Type:         value="E26",  uom=None
    """
    norm = _get_normalize()
    desc = row.part_desc

    if norm:
        raw_wattage  = norm.parse_wattage(desc)
        raw_cct      = norm.parse_cct(desc)
        raw_pack     = norm.parse_pack_qty(desc)
        raw_base     = norm.parse_base_type(desc)
    else:
        raw_wattage = raw_cct = raw_pack = raw_base = None

    w_val, w_uom = _split_value_uom(raw_wattage)
    c_val, c_uom = _split_value_uom(raw_cct)
    # pack and base already return plain strings (no unit suffix)

    attrs: list[Attribute] = []

    # Wattage
    if w_val:
        attrs.append(make_found_attr("Wattage", w_val, w_uom or "W", "High", "Part_Desc"))
    else:
        attrs.append(make_blank_attr("Wattage", "not in Part_Desc"))

    # Color Temperature
    if c_val:
        attrs.append(make_found_attr("Color Temperature", c_val, c_uom or "K", "High", "Part_Desc"))
    else:
        attrs.append(make_blank_attr("Color Temperature", "not in Part_Desc"))

    # Pack Quantity
    if raw_pack:
        attrs.append(make_found_attr("Pack Quantity", raw_pack, None, "High", "Part_Desc"))
    else:
        attrs.append(make_blank_attr("Pack Quantity", "not in Part_Desc"))

    # Base Type
    if raw_base:
        attrs.append(make_found_attr("Base Type", raw_base, None, "High", "Part_Desc"))
    else:
        attrs.append(make_blank_attr("Base Type", "not in Part_Desc"))

    return attrs


# ---------------------------------------------------------------------------
# Stage 2a: regex fallback extraction from manufacturer source text
# ---------------------------------------------------------------------------

def _fallback_extract_from_source(source_text: str, source_url: str) -> list[Attribute]:
    """
    Return exactly 3 Attributes by scanning source_text with regex.
    Order: Lumens, Rated Life, Dimmable.
    Used when XAI_API_KEY is not set.
    """
    attrs: list[Attribute] = []

    # Lumens
    m = LUMENS_RE.search(source_text)
    if m:
        attrs.append(make_found_attr("Lumens", m.group(1), "lm", "Medium", source_url))
    else:
        attrs.append(make_blank_attr("Lumens", "not in source"))

    # Rated Life (hours)
    m = LIFE_RE.search(source_text)
    if m:
        attrs.append(make_found_attr("Rated Life", m.group(1), "h", "Medium", source_url))
    else:
        attrs.append(make_blank_attr("Rated Life", "not in source"))

    # Dimmable
    if DIMMABLE_RE.search(source_text):
        attrs.append(make_found_attr("Dimmable", "Yes", None, "Medium", source_url))
    else:
        attrs.append(make_blank_attr("Dimmable", "not in source"))

    return attrs


# ---------------------------------------------------------------------------
# Stage 2b: Grok API extraction from manufacturer source text
# ---------------------------------------------------------------------------

def _llm_extract_from_source(source_text: str, source_url: str) -> list[Attribute]:
    """
    Return exactly 3 Attributes by calling the LLM API (OpenRouter or xAI).
    On ANY failure: return 3 BLANK attributes and log the error.
    NEVER raises.
    """
    if not _API_KEY:
        # No API key configured — should not be called, but guard anyway
        return [
            make_blank_attr("Lumens",     "no API key"),
            make_blank_attr("Rated Life", "no API key"),
            make_blank_attr("Dimmable",   "no API key"),
        ]
    try:
        headers = {
            "Authorization": f"Bearer {_API_KEY}",
            "Content-Type": "application/json",
        }
        # OpenRouter requires these extra headers
        if OPENROUTER_API_KEY:
            headers["HTTP-Referer"] = "https://github.com/shazamcodes64/sku-enrichment-pipeline"
            headers["X-Title"] = "SKU Enrichment Pipeline"

        payload = json.dumps({
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": source_text},
            ],
            "max_tokens": 300,
        }).encode()

        req = urllib.request.Request(
            _API_URL,
            data=payload,
            headers=headers,
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())

        content = body["choices"][0]["message"]["content"].strip()

        # Strip markdown code fences if model returns ```json ... ```
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        parsed = json.loads(content)

        attrs: list[Attribute] = []

        # Lumens
        lm = parsed.get("lumens")
        if lm is not None:
            attrs.append(make_found_attr("Lumens", str(lm), "lm", "Medium", source_url))
        else:
            attrs.append(make_blank_attr("Lumens", "not stated in source"))

        # Rated Life
        rl = parsed.get("rated_life_hours")
        if rl is not None:
            attrs.append(make_found_attr("Rated Life", str(rl), "h", "Medium", source_url))
        else:
            attrs.append(make_blank_attr("Rated Life", "not stated in source"))

        # Dimmable — True -> "Yes", False/null -> BLANK
        dm = parsed.get("dimmable")
        if dm is True:
            attrs.append(make_found_attr("Dimmable", "Yes", None, "Medium", source_url))
        else:
            attrs.append(make_blank_attr("Dimmable", "not stated in source"))

        return attrs

    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, Exception) as exc:
        logger.warning("Grok API call failed for source %s: %s", source_url, exc)
        return [
            make_blank_attr("Lumens",     "API error"),
            make_blank_attr("Rated Life", "API error"),
            make_blank_attr("Dimmable",   "API error"),
        ]


# ---------------------------------------------------------------------------
# 3 BLANK source attributes — used when no manufacturer source is available
# ---------------------------------------------------------------------------

def _no_source_attrs() -> list[Attribute]:
    return [
        make_blank_attr("Lumens",     "no source"),
        make_blank_attr("Rated Life", "no source"),
        make_blank_attr("Dimmable",   "no source"),
    ]


# ---------------------------------------------------------------------------
# Extract manufacturer-only fields (marketing description + item features)
# These fields have ZERO fallback — manufacturer page only, never generated.
# ---------------------------------------------------------------------------

def _extract_manufacturer_only_fields(
    source_text: str,
) -> tuple[str | None, list[str]]:
    """
    Returns (marketing_description, item_features_list).

    Both are extracted from the source text as-is — we do NOT generate or
    rephrase these. If not found, marketing_description=None and
    item_features=[].

    Per the official rules:
    - MARKETING_DESCRIPTION must come from the manufacturer's site verbatim.
    - ITEM_FEATURES must come from the manufacturer's site only.
    """
    # Marketing description: paragraph after "Description:" heading
    marketing_description: str | None = None
    m = MARKETING_DESC_RE.search(source_text)
    if m:
        marketing_description = m.group(1).strip()
        # Collapse excessive whitespace but preserve paragraphs
        marketing_description = re.sub(r"\n{3,}", "\n\n", marketing_description)

    # Item features: bullet-point lines
    item_features = [m.group(1).strip() for m in ITEM_FEATURE_RE.finditer(source_text)]

    return marketing_description, item_features


# ---------------------------------------------------------------------------
def enrich(row: CleanRow) -> EnrichedRow:
    """
    Run full attribute extraction for one input row.

    Always returns an EnrichedRow with exactly 7 Attributes
    in fixed ATTRIBUTE_LABELS order:
        Wattage, Color Temperature, Pack Quantity, Base Type,
        Lumens, Rated Life, Dimmable
    """
    # Step 1: deterministic attributes from Part_Desc
    part_desc_attrs = _deterministic_attributes(row)  # 4 attrs

    # Step 2: manufacturer source lookup
    retrieve_mod = _get_retrieve()
    if retrieve_mod:
        try:
            source = retrieve_mod.retrieve(row.mfg_part_num, row.manufacturer_name)
        except TypeError:
            source = retrieve_mod.retrieve(row.mfg_part_num)
    else:
        source = None

    # Step 3: source-based extraction
    if source:
        source_url = source["source_url"]
        source_text = source["source_text"]
        if _API_KEY:
            source_attrs = _llm_extract_from_source(source_text, source_url)
        else:
            source_attrs = _fallback_extract_from_source(source_text, source_url)
        mfr_url = source_url
        marketing_description, item_features = _extract_manufacturer_only_fields(source_text)
    else:
        source_attrs = _no_source_attrs()  # 3 blank attrs
        mfr_url = None
        marketing_description = None
        item_features = []

    # Combine: always 7 attrs in fixed order
    all_attrs = part_desc_attrs + source_attrs
    assert len(all_attrs) == 7, (
        f"enrich() produced {len(all_attrs)} attributes for {row.mfg_part_num}; expected 7"
    )

    return EnrichedRow(
        mfg_part_num=row.mfg_part_num,
        part_desc=row.part_desc,
        mfr_url=mfr_url,
        ref_urls=[],
        attributes=all_attrs,
        marketing_description=marketing_description,
        item_features=item_features,
    )


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(__file__))

    # Use regex fallback for quick ad-hoc tests (don't consume API quota)
    os.environ.pop("XAI_API_KEY", None)
    os.environ.pop("OPENROUTER_API_KEY", None)

    try:
        from ingest import load_and_clean
        rows = {r.mfg_part_num: r for r in load_and_clean("sample_data/input_slice.csv")}
    except ImportError:
        print("ingest.py not available — using minimal test row")
        rows = {
            "565374": CleanRow("565374", "565374 75W Led A19 Med 27k 4pk",
                               None, None, None, "Phillips Lighting", "5831"),
        }

    for part_num in ["565374", "586875"]:
        if part_num not in rows:
            print(f"{part_num}: not in input slice")
            continue
        result = enrich(rows[part_num])
        print(f"\n{result.mfg_part_num} | {result.part_desc}")
        print(f"  MFR URL: {result.mfr_url}")
        for a in result.attributes:
            val = f"{a.value} {a.uom}".strip() if a.value else "—"
            print(f"  [{a.state:5} {a.confidence:6}] {a.label}: {val}  ({a.evidence_note})")
