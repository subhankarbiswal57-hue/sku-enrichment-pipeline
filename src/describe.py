"""
Stage 6 — Description Building  (Person B)

Generates the four description fields from FOUND attributes only.
BLANK attributes are silently omitted — no placeholder text is ever inserted.

Lighting-specific formats (derived from the Frigidaire/Whirlpool ground truth
structure and adapted for the Lighting category attributes):

  INVOICE_DESC: "LED BULB 75W E26 4PK"          ALL CAPS, ≤40 chars
  MOBILE_DESC:  "Philips, LED Bulb, 75 W, 2700 K, E26, 4-Pack"
  SHORT_DESC:   "Philips 565374 LED Bulb, 75 W, E26 Base, 2700 K, 800 lm, 4-Pack"
  LONG_DESC1:   "Philips LED Bulb, 75 W, 2700 K, 800 lm, 11000 h, E26 Base, 4-Pack, Dimmable"

All four values are always str (never None).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from models import Attribute, EnrichedRow


# ---------------------------------------------------------------------------
# Helper: look up a FOUND attribute value by label
# ---------------------------------------------------------------------------

def _found(attributes: list[Attribute], label: str) -> str | None:
    """Return the value of the first FOUND attribute whose label matches, or None."""
    for a in attributes:
        if a.label == label and a.value is not None:
            return a.value
    return None


def _found_uom(attributes: list[Attribute], label: str) -> str | None:
    """Return the UOM of the first FOUND attribute whose label matches, or None."""
    for a in attributes:
        if a.label == label and a.value is not None:
            return a.uom
    return None


def _with_uom(value: str | None, uom: str | None) -> str | None:
    """Format value+uom with one space: '75 W', '2700 K'. Returns None if value is None."""
    if value is None:
        return None
    if uom:
        return f"{value} {uom}"
    return value


# ---------------------------------------------------------------------------
# INVOICE_DESC — ALL CAPS, ≤40 chars
# Format: "LED BULB <W>W <Base> <Qty>PK"
# ---------------------------------------------------------------------------

def build_invoice_desc(enriched: EnrichedRow, manufacturer_name: str | None) -> str:
    """
    ALL CAPS, at most 40 characters.
    Incorporates: Wattage, Base Type, Pack Quantity — only if FOUND.
    Truncates to the last full word within 40 chars.
    """
    attrs = enriched.attributes

    wattage  = _found(attrs, "Wattage")
    base     = _found(attrs, "Base Type")
    pack     = _found(attrs, "Pack Quantity")
    watt_uom = _found_uom(attrs, "Wattage")

    parts = ["LED BULB"]
    if wattage:
        # e.g. "75W" (no space in invoice — compact form matches ground truth)
        parts.append(f"{wattage}{watt_uom or 'W'}")
    if base:
        parts.append(base)
    if pack:
        parts.append(f"{pack}PK")

    result = " ".join(parts).upper()

    # Truncate to last full word within 40 chars
    if len(result) > 40:
        truncated = result[:40]
        last_space = truncated.rfind(" ")
        result = truncated[:last_space] if last_space > 0 else truncated

    return result


# ---------------------------------------------------------------------------
# MOBILE_DESC — brand-led, sentence case, ~60-80 chars
# Format: "<Brand>, LED Bulb, <W> W, <CCT> K, <Base>, <Qty>-Pack"
# ---------------------------------------------------------------------------

def build_mobile_desc(enriched: EnrichedRow, manufacturer_name: str | None) -> str:
    """
    Brand-led, sentence case.
    Starts with manufacturer_name, followed by LED Bulb, then FOUND attributes.
    """
    attrs  = enriched.attributes
    brand  = (manufacturer_name or "").strip() or "Unknown Brand"

    wattage = _found(attrs, "Wattage")
    cct     = _found(attrs, "Color Temperature")
    base    = _found(attrs, "Base Type")
    pack    = _found(attrs, "Pack Quantity")
    w_uom   = _found_uom(attrs, "Wattage")
    c_uom   = _found_uom(attrs, "Color Temperature")

    parts = [brand, "LED Bulb"]
    if wattage:
        parts.append(_with_uom(wattage, w_uom or "W"))
    if cct:
        parts.append(_with_uom(cct, c_uom or "K"))
    if base:
        parts.append(base)
    if pack:
        parts.append(f"{pack}-Pack")

    return ", ".join(parts)


# ---------------------------------------------------------------------------
# SHORT_DESC — title/product-name style
# Format: "<Brand> <MPN> LED Bulb, <W> W, <Base> Base, <CCT> K, <Lumens> lm, <Qty>-Pack"
# ---------------------------------------------------------------------------

def build_short_desc(enriched: EnrichedRow, manufacturer_name: str | None) -> str:
    """
    Title/product-name style with brand, MPN, and key FOUND attributes.
    """
    attrs  = enriched.attributes
    brand  = (manufacturer_name or "").strip() or "Unknown Brand"
    mpn    = enriched.mfg_part_num

    wattage = _found(attrs, "Wattage")
    base    = _found(attrs, "Base Type")
    cct     = _found(attrs, "Color Temperature")
    lumens  = _found(attrs, "Lumens")
    pack    = _found(attrs, "Pack Quantity")
    w_uom   = _found_uom(attrs, "Wattage")
    c_uom   = _found_uom(attrs, "Color Temperature")
    lm_uom  = _found_uom(attrs, "Lumens")

    # Headline: "Philips 565374 LED Bulb"
    headline = f"{brand} {mpn} LED Bulb"
    specs = []

    if wattage:
        specs.append(_with_uom(wattage, w_uom or "W"))
    if base:
        specs.append(f"{base} Base")
    if cct:
        specs.append(_with_uom(cct, c_uom or "K"))
    if lumens:
        specs.append(_with_uom(lumens, lm_uom or "lm"))
    if pack:
        specs.append(f"{pack}-Pack")

    if specs:
        return headline + ", " + ", ".join(specs)
    return headline


# ---------------------------------------------------------------------------
# LONG_DESC1 — full comma-separated spec list
# Fixed attribute order (BLANK attrs skipped):
#   Wattage → Color Temp → Lumens → Rated Life → Base Type → Pack Qty → Dimmable
# ---------------------------------------------------------------------------

def build_long_desc(enriched: EnrichedRow, manufacturer_name: str | None) -> str:
    """
    Full comma-separated specification string.
    BLANK attributes are silently omitted (no placeholders).
    """
    attrs  = enriched.attributes
    brand  = (manufacturer_name or "").strip() or "Unknown Brand"

    # Build ordered spec list
    spec_order = [
        ("Wattage",           _found_uom(attrs, "Wattage")           or "W"),
        ("Color Temperature", _found_uom(attrs, "Color Temperature") or "K"),
        ("Lumens",            _found_uom(attrs, "Lumens")            or "lm"),
        ("Rated Life",        _found_uom(attrs, "Rated Life")        or "h"),
        ("Base Type",         None),
        ("Pack Quantity",     None),
        ("Dimmable",          None),
    ]

    bits = [f"{brand} LED Bulb"]

    for label, uom in spec_order:
        val = _found(attrs, label)
        if val is None:
            continue
        if label == "Base Type":
            bits.append(f"{val} Base")
        elif label == "Pack Quantity":
            bits.append(f"{val}-Pack")
        elif label == "Dimmable":
            bits.append("Dimmable")
        else:
            bits.append(_with_uom(val, uom))

    # If nothing was found beyond the brand prefix, return empty string
    if len(bits) == 1:
        return ""

    return ", ".join(bits)


# ---------------------------------------------------------------------------
# build_all — single call returns all four descriptions
# ---------------------------------------------------------------------------

def build_all(enriched: EnrichedRow, manufacturer_name: str | None) -> dict[str, str]:
    """
    Returns a dict with exactly four keys:
        INVOICE_DESC, MOBILE_DESC, SHORT_DESC, LONG_DESC1
    All values are str (never None).
    """
    return {
        "INVOICE_DESC": build_invoice_desc(enriched, manufacturer_name),
        "MOBILE_DESC":  build_mobile_desc(enriched, manufacturer_name),
        "SHORT_DESC":   build_short_desc(enriched, manufacturer_name),
        "LONG_DESC1":   build_long_desc(enriched, manufacturer_name),
    }


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os as _os
    _os.environ.pop("XAI_API_KEY", None)

    from models import CleanRow

    try:
        from ingest import load_and_clean
        from enrich import enrich
        rows = {r.mfg_part_num: r for r in load_and_clean("sample_data/input_slice.csv")}
    except ImportError:
        from enrich import enrich
        rows = {
            "565374": CleanRow("565374", "565374 75W Led A19 Med 27k 4pk",
                               None, None, None, "Phillips Lighting", "5831"),
        }

    for part_num in ["565374", "586875"]:
        if part_num not in rows:
            continue
        raw_row  = rows[part_num]
        enriched = enrich(raw_row)
        descs    = build_all(enriched, raw_row.manufacturer_name)

        print(f"\n{part_num} | {raw_row.part_desc}")
        for key, val in descs.items():
            print(f"  {key} ({len(val)} chars): {val}")
