"""
Stage 5 (also used inline during extraction) — Normalization.

We don't have the real ~500-entry UOM master file, so this is a small,
hand-built set of rules for the units that actually show up in our
Lighting slice, reverse-engineered from how the one worked example
formats units in practice: "24 in" (space, not "24in"), "120 V", "15 A".
We follow the same style: a space between the number and the unit,
using the abbreviation forms visible on real manufacturer pages
(K, lm, h, W).

Also includes small deterministic parsers for the patterns that appear
directly in our raw Part_Desc strings (wattage, color temperature,
pack quantity, base/shape code) — this is the "obvious cases, handled by
rules, not the LLM" layer from the project plan.
"""

import re

BASE_TYPE_MAP = {
    "med": "E26",
    "medium": "E26",
    "e26": "E26",
    "e27": "E27",
    "candelabra": "E12",
}

WATTAGE_RE = re.compile(r"(\d+)\s*[wW]\b")
CCT_RE = re.compile(r"(\d{2})[kK]\b")  # "27k" -> 27 -> 2700K
PACK_RE = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)


def format_unit(value: str, unit: str) -> str:
    """Always a space between number and unit, matching the worked example's style."""
    return f"{value} {unit}"


def normalize_cct(raw_two_digit: str) -> str:
    """'27' -> '2700 K', matching manufacturer-page style (e.g. '2700K')."""
    kelvin = int(raw_two_digit) * 100
    return format_unit(str(kelvin), "K")


def normalize_base_type(raw: str) -> str | None:
    key = raw.strip().lower()
    return BASE_TYPE_MAP.get(key)


def parse_wattage(desc: str) -> str | None:
    m = WATTAGE_RE.search(desc)
    return format_unit(m.group(1), "W") if m else None


def parse_cct(desc: str) -> str | None:
    m = CCT_RE.search(desc)
    return normalize_cct(m.group(1)) if m else None


def parse_pack_qty(desc: str) -> str | None:
    m = PACK_RE.search(desc)
    return m.group(1) if m else None


def parse_base_type(desc: str) -> str | None:
    for word in desc.replace('"', " ").split():
        mapped = normalize_base_type(word)
        if mapped:
            return mapped
    return None


if __name__ == "__main__":
    samples = [
        "565374 75W Led A19 Med 27k 4pk",
        "586875 60W Led Multi CCT 4pk",
        "567313 50W Led MR16 30K 3pk",
    ]
    for s in samples:
        print(s, "->", {
            "wattage": parse_wattage(s),
            "cct": parse_cct(s),
            "pack_qty": parse_pack_qty(s),
            "base_type": parse_base_type(s),
        })
