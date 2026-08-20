"""
Stage 4 — Attribute Extraction.

Combines two sources per attribute:
  1. Deterministic parsing directly from Part_Desc (normalize.py) — for
     wattage, color temperature, pack quantity, base type, when they're
     spelled out in the raw description itself.
  2. LLM extraction from the retrieved manufacturer source text — for
     attributes that aren't in Part_Desc but ARE on the manufacturer page
     (lumens, rated life hours, dimmable).

Every attribute gets: value, state (FOUND/UNKNOWN — no INFERRED, per the
project plan), and internally a confidence level (High/Medium/Low) that
drives the review queue in the demo UI. This confidence is NOT written
as an extra output column (the real 252-column format isn't modified),
only shown in app.py.

Two run modes:
  - XAI_API_KEY set  -> calls the real Grok API for source-text extraction
  - XAI_API_KEY unset -> falls back to a small regex-based extractor over
    the curated source text, so the pipeline is runnable and testable
    without a live key. This fallback is clearly a stand-in for the LLM
    call, not a claim that it IS the LLM call.
"""

import json
import os
import re
from dataclasses import dataclass, field

from ingest import CleanRow
from normalize import parse_base_type, parse_cct, parse_pack_qty, parse_wattage
from retrieve import retrieve

XAI_API_KEY = os.environ.get("XAI_API_KEY")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = "grok-4"

LUMENS_RE = re.compile(r"(\d{3,5})\s*lm", re.IGNORECASE)
LIFE_HOURS_RE = re.compile(r"(\d{3,6})\s*h\b", re.IGNORECASE)
DIMMING_RE = re.compile(r"\bdimm", re.IGNORECASE)


@dataclass
class Attribute:
    label: str
    value: str | None
    uom: str | None
    state: str  # FOUND or UNKNOWN
    confidence: str  # High / Medium / Low (internal only)
    evidence_note: str  # where it came from, for the review UI


@dataclass
class EnrichedRow:
    mfg_part_num: str
    part_desc: str
    source_url: str | None
    attributes: list[Attribute] = field(default_factory=list)


def _attr(label, value, uom, source) -> Attribute:
    if value is None:
        return Attribute(label, None, None, "UNKNOWN", "Low", "not found in Part_Desc or source")
    conf = "High" if source == "part_desc" else "Medium"
    return Attribute(label, value, uom, "FOUND", conf, source)


def _deterministic_attributes(row: CleanRow) -> list[Attribute]:
    """Attributes we can parse straight from the raw description — no
    retrieval or LLM call needed, matches this data's actual pattern."""
    wattage = parse_wattage(row.part_desc)
    cct = parse_cct(row.part_desc)
    pack_qty = parse_pack_qty(row.part_desc)
    base_type = parse_base_type(row.part_desc)

    return [
        _attr("Wattage", wattage.split()[0] if wattage else None, "W", "part_desc"),
        _attr("Color Temperature", cct.split()[0] if cct else None, "K", "part_desc"),
        _attr("Pack Quantity", pack_qty, None, "part_desc"),
        _attr("Base Type", base_type, None, "part_desc"),
    ]


def _fallback_extract_from_source(source_text: str) -> list[Attribute]:
    """Regex extractor for manufacturer page text. Only reads what's
    literally present in the fetched manufacturer page text."""
    lumens_m = LUMENS_RE.search(source_text)
    life_m = LIFE_HOURS_RE.search(source_text)
    dimmable = bool(DIMMING_RE.search(source_text))

    return [
        _attr("Lumens", lumens_m.group(1) if lumens_m else None, "lm", "manufacturer_source"),
        _attr("Rated Life", life_m.group(1) if life_m else None, "h", "manufacturer_source"),
        _attr("Dimmable", "Yes" if dimmable else None, None, "manufacturer_source"),
    ]


def _llm_extract_from_source(source_text: str, source_url: str) -> list[Attribute]:
    """Real LLM extraction call from manufacturer source text."""
    import urllib.request

    system_prompt = (
        "Extract product attributes (Lumens, Rated Life in hours, Dimmable "
        "yes/no, Base Type) from the manufacturer page text below. Return ONLY a JSON "
        "object: {\"lumens\": <number or null>, \"rated_life_hours\": "
        "<number or null>, \"dimmable\": <true/false/null>, \"base_type\": <string or null>}. "
        "Use null for anything not explicitly stated in the text — never guess."
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_text},
        ],
        "max_tokens": 300,
    }
    req = urllib.request.Request(
        XAI_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    content = result["choices"][0]["message"]["content"]
    parsed = json.loads(content)

    return [
        _attr("Lumens", parsed.get("lumens"), "lm", "manufacturer_source"),
        _attr("Rated Life", parsed.get("rated_life_hours"), "h", "manufacturer_source"),
        _attr("Dimmable", "Yes" if parsed.get("dimmable") else None, None, "manufacturer_source"),
    ]


def enrich(row: CleanRow) -> EnrichedRow:
    attributes = _deterministic_attributes(row)

    source = retrieve(row.mfg_part_num, row.manufacturer_name)
    if source is None:
        attributes += [
            _attr("Lumens", None, "lm", "no_source"),
            _attr("Rated Life", None, "h", "no_source"),
            _attr("Dimmable", None, None, "no_source"),
        ]
        return EnrichedRow(row.mfg_part_num, row.part_desc, None, attributes)

    # If base type was not found in part_desc, attempt extraction from source text
    base_attr = next((a for a in attributes if a.label == "Base Type"), None)
    if base_attr and base_attr.state == "UNKNOWN":
        source_base = parse_base_type(source["source_text"])
        if source_base:
            base_attr.value = source_base
            base_attr.state = "FOUND"
            base_attr.confidence = "Medium"
            base_attr.evidence_note = "manufacturer_source"

    if XAI_API_KEY:
        source_attrs = _llm_extract_from_source(source["source_text"], source["source_url"])
    else:
        source_attrs = _fallback_extract_from_source(source["source_text"])

    return EnrichedRow(row.mfg_part_num, row.part_desc, source["source_url"], attributes + source_attrs)



if __name__ == "__main__":
    from ingest import load_and_clean

    rows = load_and_clean("sample_data/input_slice.csv")
    by_part = {r.mfg_part_num: r for r in rows}

    if not XAI_API_KEY:
        print("(No XAI_API_KEY set — using regex fallback extractor, not the real LLM call)\n")

    for part_num in ["565374", "586875"]:
        result = enrich(by_part[part_num])
        print(f"{result.mfg_part_num} | {result.part_desc}")
        print(f"  source: {result.source_url}")
        for a in result.attributes:
            print(f"  {a.label}: {a.value} {a.uom or ''} [{a.state}, confidence={a.confidence}]")
        print()
