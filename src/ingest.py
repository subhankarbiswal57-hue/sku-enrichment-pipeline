"""
Stage 1 — Ingestion & Cleansing.

Reads the real 6-column raw input format and:
  - filters known placeholder values ("-- Unbranded --", "N/A", "NULL", etc.) to None,
    ensuring placeholder markers are never treated as real brand data.
  - parses embedded manufacturer codes out of Part_Manuf across multiple formats, e.g.
    "Phillips Lighting (5831)" -> name="Phillips Lighting", code="5831"
    "Satco Prod Inc - 5573"    -> name="Satco Prod Inc", code="5573"
  - performs string hygiene (collapsing multiple spaces, stripping unprintable characters).
"""

import csv
import re
from dataclasses import dataclass

PLACEHOLDER_EXACT = {
    "-- unbranded --",
    "-- no unilog brand --",
    "-- no dib brand --",
    "-- none --",
    "unbranded",
    "generic",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "tbd",
    "-",
    ".",
}

PLACEHOLDER_PATTERN = re.compile(r"^(--\s*.+?\s*--|n/?a|null|none|tbd)$", re.IGNORECASE)

MANUF_CODE_RE = re.compile(
    r"^(?P<name>.+?)\s*(?:[\(\[\{](?P<code1>[A-Za-z0-9_-]+)[\)\]\}]|\s+-\s+(?P<code2>[A-Za-z0-9_-]+)|\s+#(?P<code3>[A-Za-z0-9_-]+))\s*$"
)


@dataclass
class CleanRow:
    mfg_part_num: str
    part_desc: str
    e1_brand: str | None
    unilog_brand: str | None
    dib_brand: str | None
    manufacturer_name: str
    manufacturer_code: str | None


def clean_string(s: str | None) -> str:
    """Normalize whitespace and remove non-printable characters."""
    if not s:
        return ""
    s = s.replace("\xa0", " ").strip()
    return re.sub(r"\s+", " ", s)


def clean_value(v: str | None) -> str | None:
    """Clean a field value and return None if it matches a known placeholder."""
    v = clean_string(v)
    if not v:
        return None
    v_lower = v.lower()
    if v_lower in PLACEHOLDER_EXACT or PLACEHOLDER_PATTERN.match(v_lower):
        return None
    return v


def parse_manufacturer(raw: str | None) -> tuple[str, str | None]:
    """
    Extracts canonical manufacturer name and identifier code.
    Examples:
      'Phillips Lighting (5831)' -> ('Phillips Lighting', '5831')
      'Satco Prod Inc - 5573'    -> ('Satco Prod Inc', '5573')
      'Kichler Lighting'         -> ('Kichler Lighting', None)
    """
    raw = clean_string(raw)
    if not raw:
        return "UNKNOWN", None

    m = MANUF_CODE_RE.match(raw)
    if m:
        name = m.group("name").strip()
        code = m.group("code1") or m.group("code2") or m.group("code3")
        return name, code.strip() if code else None

    return raw, None


def load_and_clean(path: str) -> list[CleanRow]:
    """Loads CSV and applies stage 1 cleansing and normalization."""
    rows: list[CleanRow] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            col_map = {k.strip().lower(): v for k, v in r.items() if k}
            
            part_num = col_map.get("mfg_part_num") or col_map.get("part_number") or ""
            part_desc = col_map.get("part_desc") or col_map.get("description") or ""
            part_manuf = col_map.get("part_manuf") or col_map.get("manufacturer") or ""
            
            e1_brand = col_map.get("e1_brand")
            unilog_brand = col_map.get("unilog_brand")
            dib_brand = col_map.get("dib_brand")

            name, code = parse_manufacturer(part_manuf)
            rows.append(
                CleanRow(
                    mfg_part_num=clean_string(part_num),
                    part_desc=clean_string(part_desc),
                    e1_brand=clean_value(e1_brand),
                    unilog_brand=clean_value(unilog_brand),
                    dib_brand=clean_value(dib_brand),
                    manufacturer_name=name,
                    manufacturer_code=code,
                )
            )
    return rows


if __name__ == "__main__":
    import sys

    data_file = sys.argv[1] if len(sys.argv) > 1 else "sample_data/input_slice.csv"
    rows = load_and_clean(data_file)
    print(f"Loaded and cleansed {len(rows)} rows from {data_file}")
    for r in rows[:5]:
        print(f"  Part: {r.mfg_part_num} | Manuf: {r.manufacturer_name} (Code: {r.manufacturer_code}) | Desc: {r.part_desc}")
