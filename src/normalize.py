"""
Stage 5 / Inline — Normalization (Person A)

Deterministic parsers for technical attributes from raw catalog text:
  - Wattage (e.g. '75W' -> '75 W')
  - Color Temperature (e.g. '27k' -> '2700 K', '2700K' -> '2700 K', 'Soft White' -> '2700 K')
  - Pack Quantity (e.g. '4pk' -> '4')
  - Base / Socket Types (e.g. 'Med' -> 'E26', 'Cand' -> 'E12')
"""

from __future__ import annotations

import re

# Canonical Base Types mapping as required by spec
BASE_TYPE_MAP = {
    "med": "E26",
    "medium": "E26",
    "e26": "E26",
    "e-26": "E26",
    "e27": "E26",
    "e-27": "E26",
    "cand": "E12",
    "candelabra": "E12",
    "e12": "E12",
    "e-12": "E12",
    "mogul": "E39",
    "e39": "E39",
    "ex39": "EX39",
    "gu10": "GU10",
    "gu24": "GU24",
    "g9": "G9",
    "g4": "G4",
    "g13": "G13",
    "bi-pin": "G13",
    "bipin": "G13",
    "fa8": "Fa8",
    "r17d": "R17d",
}

NAMED_CCT_MAP = {
    "soft white": "2700",
    "warm white": "3000",
    "bright white": "3500",
    "neutral white": "4000",
    "cool white": "4000",
    "daylight": "5000",
    "daylight deluxe": "6500",
}

WATTAGE_RE = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*[wW]\b")
CCT_RE = re.compile(r"\b([2-7]\d)[kK]\b")
CCT_4DIGIT_RE = re.compile(r"\b([2-6]\d{3})\s*[kK]\b")
MULTI_CCT_RE = re.compile(r"\b(?:multi[\s-]?cct|selectable|tunable|cct\s*selectable|\d{4}/\d{4})\b", re.IGNORECASE)

PACK_RE = re.compile(
    r"(?:(\d+)\s*pk\b|(\d+)\s*[-/]?\s*pack\b|pack\s*of\s*(\d+)\b|(\d+)\s*/\s*pk\b|(\d+)\s*count\b|\((\d+)\)\s*pack\b|box\s*of\s*(\d+)\b|case\s*of\s*(\d+)\b)",
    re.IGNORECASE,
)

VOLTAGE_RE = re.compile(r"\b(120-277|120/277|120|277|240|208|480|12|24)\s*[vV]\b")
LUMENS_RE = re.compile(r"\b(\d{3,5})\s*(?:lm|lumens?)\b", re.IGNORECASE)
SHAPE_RE = re.compile(r"\b(A19|A15|A21|ST19|ST21|BR30|BR40|PAR20|PAR30|PAR38|MR16|R20|R14|G25|G16.5|T8|T5|T12|ED28)\b", re.IGNORECASE)


def format_unit(value: str | int | float, unit: str) -> str:
    """Always a single space between number and unit: e.g. '75 W', '2700 K'."""
    val_str = str(value).strip()
    return f"{val_str} {unit}".strip()


def parse_wattage(desc: str) -> str | None:
    """
    Parses wattage value and formats with 'W' unit.
    Example: '75W Led A19' -> '75 W'
    """
    m = WATTAGE_RE.search(desc)
    if m:
        val = m.group(1)
        if val.endswith(".0"):
            val = val[:-2]
        return format_unit(val, "W")
    return None


def parse_cct(desc: str) -> str | None:
    """
    Parses color temperature.
    Examples:
      '27k' -> '2700 K'
      '30K' -> '3000 K'
      '2700K' -> '2700 K'
      'Soft White' -> '2700 K'
      'Multi CCT' -> None (selectable / variable)
    """
    if MULTI_CCT_RE.search(desc):
        return None

    # 4-digit Kelvin (2700K, 5000K)
    m4 = CCT_4DIGIT_RE.search(desc)
    if m4:
        return format_unit(m4.group(1), "K")

    # 2-digit Kelvin (27k, 30k, 50k)
    m2 = CCT_RE.search(desc)
    if m2:
        kelvin = int(m2.group(1)) * 100
        return format_unit(str(kelvin), "K")

    # Named color temperature
    desc_lower = desc.lower()
    for name, kelvin in NAMED_CCT_MAP.items():
        if re.search(rf"\b{re.escape(name)}\b", desc_lower):
            return format_unit(kelvin, "K")

    return None


def parse_pack_qty(desc: str) -> str | None:
    """
    Extracts pack count number as a plain string.
    Example: '4pk' -> '4', 'Pack of 6' -> '6'
    """
    m = PACK_RE.search(desc)
    if m:
        for g in m.groups():
            if g:
                return str(int(g))
    return None


def parse_base_type(desc: str) -> str | None:
    """
    Finds standard base/socket type from text tokens.
    Example: 'Med' -> 'E26', 'candelabra' -> 'E12'
    """
    tokens = re.split(r'[\s",\(\)\[\]/]+', desc)
    for token in tokens:
        key = token.strip().lower()
        if key in BASE_TYPE_MAP:
            return BASE_TYPE_MAP[key]
    return None


def parse_voltage(desc: str) -> str | None:
    """Extracts voltage specification e.g. '120 V'."""
    m = VOLTAGE_RE.search(desc)
    return format_unit(m.group(1), "V") if m else None


def parse_lumens(desc: str) -> str | None:
    """Extracts lumen output e.g. '800 lm'."""
    m = LUMENS_RE.search(desc)
    return format_unit(m.group(1), "lm") if m else None


def parse_bulb_shape(desc: str) -> str | None:
    """Extracts standard ANSI bulb shape e.g. 'A19', 'PAR38'."""
    m = SHAPE_RE.search(desc)
    return m.group(1).upper() if m else None


if __name__ == "__main__":
    d = "565374 75W Led A19 Med 27k 4pk"
    print(parse_wattage(d), parse_cct(d), parse_pack_qty(d), parse_base_type(d))
