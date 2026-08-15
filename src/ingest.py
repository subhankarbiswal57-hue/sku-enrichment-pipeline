"""
Stage 1 — Ingestion & Cleansing.

Reads the real 6-column raw input format and:
  - filters known placeholder values ("-- Unbranded --", etc.) to empty,
    since the Solution Guide explicitly says these are not data
  - parses the embedded manufacturer code out of Part_Manuf, e.g.
    "Phillips Lighting (5831)" -> name="Phillips Lighting", code="5831"

This does not touch anything a real LOV/manufacturer-master file would
normally validate against — we don't have those files, so this stage is
intentionally limited to what's mechanically derivable from the raw row.
"""

import csv
import re
from dataclasses import dataclass

PLACEHOLDER_VALUES = {
    "-- Unbranded --",
    "-- No Unilog Brand --",
    "-- No DIB Brand --",
}

MANUF_CODE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$")


@dataclass
class CleanRow:
    mfg_part_num: str
    part_desc: str
    e1_brand: str | None
    unilog_brand: str | None
    dib_brand: str | None
    manufacturer_name: str
    manufacturer_code: str | None


def clean_value(v: str) -> str | None:
    v = (v or "").strip()
    return None if v in PLACEHOLDER_VALUES or v == "" else v


def parse_manufacturer(raw: str) -> tuple[str, str | None]:
    raw = (raw or "").strip()
    m = MANUF_CODE_RE.match(raw)
    if m:
        return m.group("name").strip(), m.group("code").strip()
    return raw, None


def load_and_clean(path: str) -> list[CleanRow]:
    rows: list[CleanRow] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            name, code = parse_manufacturer(r["Part_Manuf"])
            rows.append(
                CleanRow(
                    mfg_part_num=r["Mfg_Part_Num"].strip(),
                    part_desc=r["Part_Desc"].strip(),
                    e1_brand=clean_value(r["E1_Brand"]),
                    unilog_brand=clean_value(r["Unilog_Brand"]),
                    dib_brand=clean_value(r["DIB_Brand"]),
                    manufacturer_name=name,
                    manufacturer_code=code,
                )
            )
    return rows


if __name__ == "__main__":
    import sys

    rows = load_and_clean(sys.argv[1] if len(sys.argv) > 1 else "sample_data/input_slice.csv")
    print(f"Loaded {len(rows)} rows")
    for r in rows[:5]:
        print(r)
