"""
Stage 5 (also used inline during extraction) — Normalization.

Expanded deterministic parsers for technical attributes from raw catalog text
and retrieved manufacturer pages:
  - Wattage (integers, decimals e.g. 9.5W, equivalent wattage)
  - Color Temperature (2-digit '27k', 4-digit '2700K', named color temperatures)
  - Pack Quantity ('4pk', '4-pack', 'pack of 4', '4 count', 'box of 10')
  - Base / Socket Types (E26, E12, E39, GU10, GU24, G9, G4, G13, Fa8, R17d)
  - Voltage, Lumens, Bulb Shape, Dimensions, and Dimmability
  - Strict UOM formatting: standard space between magnitude and symbol ("60 W", "2700 K", "120 V", "800 lm").
"""

import re

BASE_TYPE_MAP = {
    # Medium / Standard Screw
    "med": "E26",
    "medium": "E26",
    "e26": "E26",
    "e-26": "E26",
    # European / Standard Screw
    "e27": "E27",
    "e-27": "E27",
    # Candelabra
    "candelabra": "E12",
    "cand": "E12",
    "e12": "E12",
    "e-12": "E12",
    # Mogul
    "mogul": "E39",
    "e39": "E39",
    "e-39": "E39",
    "ex39": "EX39",
    # Twist & Lock / Pin Bases
    "gu10": "GU10",
    "gu-10": "GU10",
    "gu24": "GU24",
    "gu-24": "GU24",
    "g9": "G9",
    "g-9": "G9",
    "g4": "G4",
    "g-4": "G4",
    "gu5.3": "GU5.3",
    "mr16": "GU5.3",
    # Fluorescent / Linear Pin Bases
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

WATTAGE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:[wW]|watt|watts)\b", re.IGNORECASE)
CCT_4DIGIT_RE = re.compile(r"\b([2-6]\d{3})\s*[kK]\b")
CCT_2DIGIT_RE = re.compile(r"\b(2[0-9]|3[0-9]|4[0-9]|5[0-9]|6[0-5])[kK]\b")
MULTI_CCT_RE = re.compile(r"\b(?:multi[\s-]?cct|selectable|tunable|cct\s*selectable|\d{4}/\d{4})\b", re.IGNORECASE)

PACK_RE = re.compile(
    r"\b(?:(\d+)\s*pk|(\d+)\s*[-/]?\s*pack|pack\s*of\s*(\d+)|(\d+)\s*/\s*pk|(\d+)\s*count|\((\d+)\)\s*pack|box\s*of\s*(\d+)|case\s*of\s*(\d+))\b",
    re.IGNORECASE,
)

VOLTAGE_RE = re.compile(r"\b(120-277|120/277|120|277|240|208|480|12|24)\s*[vV]\b")
LUMENS_RE = re.compile(r"\b(\d{3,5})\s*(?:lm|lumens?)\b", re.IGNORECASE)
SHAPE_RE = re.compile(r"\b(A19|A15|A21|ST19|ST21|BR30|BR40|PAR20|PAR30|PAR38|MR16|R20|R14|G25|G16.5|T8|T5|T12|ED28)\b", re.IGNORECASE)


def format_unit(value: str | int | float, unit: str) -> str:
    """Always a space between number and unit: e.g. '60 W', '2700 K'."""
    val_str = str(value).strip()
    return f"{val_str} {unit}".strip()


def normalize_cct(raw_two_digit: str) -> str:
    """'27' -> '2700 K'."""
    kelvin = int(raw_two_digit) * 100
    return format_unit(str(kelvin), "K")


def normalize_base_type(raw: str) -> str | None:
    """Matches base type string against the ANSI/IEC socket dictionary."""
    key = raw.strip().lower()
    return BASE_TYPE_MAP.get(key)


def parse_wattage(desc: str) -> str | None:
    """Parses wattage value and formats with 'W' unit."""
    m = WATTAGE_RE.search(desc)
    if m:
        val = m.group(1)
        # Format whole floats as ints: 60.0 -> 60
        if val.endswith(".0"):
            val = val[:-2]
        return format_unit(val, "W")
    return None


def parse_cct(desc: str) -> str | None:
    """
    Parses color temperature. If multiple/selectable CCTs are detected,
    returns None so it is handled as UNKNOWN / variable rather than guessing.
    """
    if MULTI_CCT_RE.search(desc):
        return None

    # Check 4-digit Kelvin (e.g. 2700K, 5000K)
    m4 = CCT_4DIGIT_RE.search(desc)
    if m4:
        return format_unit(m4.group(1), "K")

    # Check 2-digit Kelvin (e.g. 27k, 30k)
    m2 = CCT_2DIGIT_RE.search(desc)
    if m2:
        return normalize_cct(m2.group(1))

    # Check named color temperatures (e.g. Soft White)
    desc_lower = desc.lower()
    for name, kelvin in NAMED_CCT_MAP.items():
        if re.search(rf"\b{re.escape(name)}\b", desc_lower):
            return format_unit(kelvin, "K")

    return None


def parse_pack_qty(desc: str) -> str | None:
    """Extracts pack count number."""
    m = PACK_RE.search(desc)
    if m:
        for g in m.groups():
            if g:
                return str(int(g))
    return None


def parse_base_type(desc: str) -> str | None:
    """Finds standard base/socket type from text tokens."""
    tokens = re.split(r'[\s",\(\)\[\]/]+', desc)
    for token in tokens:
        mapped = normalize_base_type(token)
        if mapped:
            return mapped
    return None


def parse_voltage(desc: str) -> str | None:
    """Extracts voltage specification e.g. '120 V' or '120-277 V'."""
    m = VOLTAGE_RE.search(desc)
    return format_unit(m.group(1), "V") if m else None


def parse_lumens(desc: str) -> str | None:
    """Extracts lumen output e.g. '800 lm'."""
    m = LUMENS_RE.search(desc)
    return format_unit(m.group(1), "lm") if m else None


def parse_bulb_shape(desc: str) -> str | None:
    """Extracts standard ANSI bulb shape e.g. 'A19', 'BR30', 'PAR38'."""
    m = SHAPE_RE.search(desc)
    return m.group(1).upper() if m else None


if __name__ == "__main__":
    samples = [
        "565374 75W Led A19 Med 27k 4pk",
        "586875 60W Led Multi CCT 4pk",
        "567313 50W Led MR16 30K 3pk",
        "9.5W LED Soft White A19 Pack of 4 120V 800lm",
        "Kichler Wall Lt Candelabra E12 60W 120V",
    ]
    for s in samples:
        print(s, "->", {
            "wattage": parse_wattage(s),
            "cct": parse_cct(s),
            "pack_qty": parse_pack_qty(s),
            "base_type": parse_base_type(s),
            "shape": parse_bulb_shape(s),
            "voltage": parse_voltage(s),
            "lumens": parse_lumens(s),
        })

