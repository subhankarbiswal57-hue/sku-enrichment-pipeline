"""
Stage 1 — Ingestion & Cleansing (Person A)

Reads the raw 6-column input CSV and:
  - filters known placeholder values ("-- Unbranded --", "-- No Unilog Brand --", "N/A", "NULL", etc.) to None
  - parses embedded manufacturer codes out of Part_Manuf (e.g. "Phillips Lighting (5831)" -> ("Phillips Lighting", "5831"))
  - validates all required columns and raises IOError or ValueError naming missing columns
  - returns a list of immutable CleanRow dataclass instances.
"""

from __future__ import annotations

import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from models import CleanRow

PLACEHOLDER_VALUES = frozenset({
    "-- Unbranded --",
    "-- No Unilog Brand --",
    "-- No DIB Brand --",
    "-- unbranded --",
    "-- no unilog brand --",
    "-- no dib brand --",
    "-- none --",
    "-- None --",
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
})

PLACEHOLDER_PATTERN = re.compile(r"^(--\s*.+?\s*--|n/?a|null|none|tbd)$", re.IGNORECASE)

MANUF_CODE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$")
MANUF_CODE_DASH_RE = re.compile(r"^(?P<name>.+?)\s+-\s+(?P<code>[A-Za-z0-9]+)\s*$")

REQUIRED_COLUMNS = [
    "Mfg_Part_Num",
    "Part_Desc",
    "E1_Brand",
    "Unilog_Brand",
    "DIB_Brand",
    "Part_Manuf",
]


def clean_brand(v: str | None) -> str | None:
    """
    Clean brand values, converting empty strings and known placeholder markers to None.
    """
    if v is None:
        return None
    s = v.replace("\xa0", " ").strip()
    if not s:
        return None
    if s in PLACEHOLDER_VALUES or s.lower() in PLACEHOLDER_VALUES or PLACEHOLDER_PATTERN.match(s):
        return None
    return s


def parse_manufacturer(raw: str | None) -> tuple[str | None, str | None]:
    """
    Extracts canonical manufacturer name and identifier code.
    Examples:
      'Phillips Lighting (5831)' -> ('Phillips Lighting', '5831')
      'Satco Prod Inc - 5573'    -> ('Satco Prod Inc', '5573')
      'Kichler Lighting'         -> ('Kichler Lighting', None)
      ''                         -> (None, None)
    """
    if raw is None:
        return None, None
    raw_clean = raw.replace("\xa0", " ").strip()
    if not raw_clean:
        return None, None

    m = MANUF_CODE_RE.match(raw_clean)
    if m:
        return m.group("name").strip(), m.group("code").strip()

    m_dash = MANUF_CODE_DASH_RE.match(raw_clean)
    if m_dash:
        return m_dash.group("name").strip(), m_dash.group("code").strip()

    return raw_clean, None


def load_and_clean(path: str) -> list[CleanRow]:
    """
    Loads raw CSV and returns a list of validated CleanRow objects.
    Raises IOError if file cannot be opened.
    Raises ValueError naming missing columns if any required column is absent.
    """
    if not os.path.exists(path):
        raise IOError(f"Input file not found or unreadable: {path}")

    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"CSV file is empty: {path}")

            # Validate required columns (case-insensitive header mapping)
            headers_lower = {h.strip().lower(): h for h in reader.fieldnames if h}
            missing_cols = []
            for req in REQUIRED_COLUMNS:
                if req.lower() not in headers_lower:
                    missing_cols.append(req)

            if missing_cols:
                raise ValueError(f"Missing required column(s) in {path}: {', '.join(missing_cols)}")

            mfg_key = headers_lower["mfg_part_num"]
            desc_key = headers_lower["part_desc"]
            e1_key = headers_lower["e1_brand"]
            unilog_key = headers_lower["unilog_brand"]
            dib_key = headers_lower["dib_brand"]
            manuf_key = headers_lower["part_manuf"]

            rows: list[CleanRow] = []
            for line_idx, r in enumerate(reader, start=2):
                raw_part_num = (r.get(mfg_key) or "").replace("\xa0", " ").strip()
                raw_desc = (r.get(desc_key) or "").replace("\xa0", " ").strip()

                if not raw_part_num:
                    continue  # skip blank rows if any

                manuf_name, manuf_code = parse_manufacturer(r.get(manuf_key))

                clean_row = CleanRow(
                    mfg_part_num=raw_part_num,
                    part_desc=raw_desc,
                    e1_brand=clean_brand(r.get(e1_key)),
                    unilog_brand=clean_brand(r.get(unilog_key)),
                    dib_brand=clean_brand(r.get(dib_key)),
                    manufacturer_name=manuf_name,
                    manufacturer_code=manuf_code,
                )
                rows.append(clean_row)

            return rows

    except (OSError, IOError) as e:
        if isinstance(e, ValueError):
            raise
        raise IOError(f"Could not read input CSV {path}: {e}") from e


if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "sample_data/input_slice.csv"
    rows = load_and_clean(data_file)
    print(f"Loaded and cleansed {len(rows)} rows from {data_file}")
    for r in rows[:5]:
        print(f"  Part: {r.mfg_part_num} | Manuf: {r.manufacturer_name} (Code: {r.manufacturer_code}) | Desc: {r.part_desc}")
