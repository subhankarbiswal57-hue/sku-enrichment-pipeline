"""
Main pipeline — runs Stages 1-6 on the real input slice and writes output
using the EXACT 252-column header row from Unihack__Expected_Output_-_Delivery_Format.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from classify import classify
from describe import build_all
from enrich import enrich
from ingest import load_and_clean

HEADERS_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_data", "real_output_headers.json")


def load_real_headers() -> list[str]:
    if os.path.exists(HEADERS_PATH):
        with open(HEADERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def build_output_row(raw_row, headers: list[str]) -> tuple[dict, any, any]:
    out = {h: "" for h in headers}

    classification = classify(raw_row)
    enriched = enrich(raw_row)
    descs = build_all(enriched, raw_row.manufacturer_name)

    out["Mfg_Part_Num"] = raw_row.mfg_part_num
    out["Part_Desc"] = raw_row.part_desc
    out["E1_Brand"] = raw_row.e1_brand or ""
    out["Unilog_Brand"] = raw_row.unilog_brand or ""
    out["DIB_Brand"] = raw_row.dib_brand or ""
    out["Part_Manuf"] = f"{raw_row.manufacturer_name} ({raw_row.manufacturer_code})" if raw_row.manufacturer_code else raw_row.manufacturer_name

    out["MANUFACTURER_NAME"] = raw_row.manufacturer_name
    out["MANUFACTURER_PART_NUMBER"] = raw_row.mfg_part_num

    if classification and classification.state == "FOUND":
        out["Dept"] = classification.dept
        out["Class"] = classification.cls
        out["Fine"] = classification.fine
        out["Classpath"] = classification.classpath

    if enriched.mfr_url:
        out["MFR URL"] = enriched.mfr_url

    out["INVOICE_DESC"] = descs.get("INVOICE_DESC", "")
    out["MOBILE_DESC"] = descs.get("MOBILE_DESC", "")
    out["SHORT_DESC"] = descs.get("SHORT_DESC", "")
    out["LONG_DESC1"] = descs.get("LONG_DESC1", "")

    # Populate ATTRIBUTE_LABEL/VALUE/UOM 1-7 from FOUND attributes only
    found_attrs = [a for a in enriched.attributes if a.state == "FOUND"]
    for i, attr in enumerate(found_attrs[:50], start=1):
        out[f"ATTRIBUTE_LABEL {i}"] = attr.label
        out[f"ATTRIBUTE_VALUE {i}"] = attr.value
        out[f"ATTRIBUTE_UOM {i}"] = attr.uom or ""

    return out, enriched, classification


def run(input_path: str, output_path: str, limit: int | None = None):
    headers = load_real_headers()
    raw_rows = load_and_clean(input_path)
    if limit:
        raw_rows = raw_rows[:limit]

    written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for raw_row in raw_rows:
            out_row, _, _ = build_output_row(raw_row, headers)
            w.writerow(out_row)
            written += 1

    print(f"Wrote {written} rows -> {output_path}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run("sample_data/input_slice.csv", "output_demo.csv", limit=limit)
