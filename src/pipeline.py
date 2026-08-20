"""
pipeline.py — Person C's task
Orchestrates: clean -> classify -> enrich -> build descriptions -> write 252-column CSV.

Matches the shared contracts in src/models.py:
    CleanRow(mfg_part_num, part_desc, e1_brand, unilog_brand, dib_brand,
             manufacturer_name, manufacturer_code)
    Classification(dept, cls, fine, classpath, found)
    Attribute(label, value, uom, confidence, evidence_note) with .state property
    EnrichedRow(mfg_part_num, part_desc, mfr_url, ref_urls, attributes)

HOW THIS FILE WORKS WHILE TEAMMATES ARE STILL BUILDING:
Every "real" import below is wrapped in try/except. If a teammate's module
doesn't exist yet (or doesn't have the function yet), we fall back to a local
stub that returns empty/default data. This means:
  - You can run `python src/pipeline.py --limit 5` TODAY and get a valid
    (mostly empty) 252-column CSV.
  - The moment a teammate's real module lands with the matching module/function
    name, Python will import the real one automatically — you don't change
    a single line of your own logic.

BEFORE FINAL SUBMISSION: confirm the exact module + function names with A and
B (search "TODO: CONFIRM" below).

ASSUMPTIONS FLAGGED FOR TEAM REVIEW (search "TODO: CONFIRM WITH TEAM"):
CleanRow has no separate Part_Manuf / BRAND_NAME / MANUFACTURER_PART_NUMBER
fields — only manufacturer_name + manufacturer_code, and three brand fields.
This file makes a best-effort mapping onto those four output columns. Check
this against the ground-truth CSV / whoever owns the taxonomy before demo day.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import argparse
from typing import Optional

from models import CleanRow, Classification, Attribute, EnrichedRow, ATTRIBUTE_LABELS


# ---------------------------------------------------------------------------
# Stage functions owned by Person A / Person B — stubbed until they land
# ---------------------------------------------------------------------------
try:
    from ingest import load_and_clean as load_clean_rows  # confirmed: ingest.load_and_clean
except ImportError:
    print("[pipeline] ingest module not found yet — using local stub load_clean_rows", file=sys.stderr)

    def load_clean_rows(input_path: str) -> list:
        """
        Fallback: read the raw input CSV and best-effort build CleanRow objects.
        Real ingest.py should replace this — it owns placeholder-brand stripping
        and parsing manufacturer_code out of Part_Manuf.
        """
        rows = []
        with open(input_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                mfg_part_num = (r.get("Mfg_Part_Num") or "").strip()
                part_desc = (r.get("Part_Desc") or "").strip()
                if not mfg_part_num or not part_desc:
                    continue  # CleanRow requires these non-empty

                def blank_to_none(v):
                    v = (v or "").strip()
                    return v if v else None

                part_manuf_raw = (r.get("Part_Manuf") or "").strip()
                manufacturer_name = None
                manufacturer_code = None
                if part_manuf_raw:
                    if "(" in part_manuf_raw and part_manuf_raw.endswith(")"):
                        name_part, code_part = part_manuf_raw.rsplit("(", 1)
                        manufacturer_name = name_part.strip() or None
                        manufacturer_code = code_part.rstrip(")").strip() or None
                    else:
                        manufacturer_name = part_manuf_raw

                rows.append(
                    CleanRow(
                        mfg_part_num=mfg_part_num,
                        part_desc=part_desc,
                        e1_brand=blank_to_none(r.get("E1_Brand")),
                        unilog_brand=blank_to_none(r.get("Unilog_Brand")),
                        dib_brand=blank_to_none(r.get("DIB_Brand")),
                        manufacturer_name=manufacturer_name,
                        manufacturer_code=manufacturer_code,
                    )
                )
        return rows


try:
    from classify import classify  # confirmed: classify.classify
    # NOTE: real classify.py returns ITS OWN local Classification class with a
    # `state` field ("FOUND"/"UNKNOWN"), not the models.py contract's `found`
    # bool. See _classification_found() below for the adapter. Flag this
    # mismatch to whoever owns classify.py / models.py before final submission.
except ImportError:
    print("[pipeline] classify module not found yet — using local stub classify()", file=sys.stderr)

    def classify(row: "CleanRow") -> Classification:
        return Classification(dept="", cls="", fine="", classpath="", found=False)


try:
    from enrich import enrich  # TODO: CONFIRM real module name (Person B)
except ImportError:
    print("[pipeline] enrich module not found yet — using local stub enrich()", file=sys.stderr)

    def enrich(row: "CleanRow") -> "EnrichedRow":
        blank_attrs = [Attribute(label=lbl, value=None, uom=None, confidence="Low",
                                  evidence_note="no source") for lbl in ATTRIBUTE_LABELS]
        return EnrichedRow(
            mfg_part_num=row.mfg_part_num,
            part_desc=row.part_desc,
            mfr_url=None,
            ref_urls=[],
            attributes=blank_attrs,
        )


try:
    from descriptions import build_all  # TODO: CONFIRM real module name (Person B)
except ImportError:
    print("[pipeline] descriptions module not found yet — using local stub build_all()", file=sys.stderr)

    def build_all(enriched: "EnrichedRow", manufacturer_name: Optional[str]) -> dict:
        return {"invoice_desc": "", "mobile_desc": "", "short_desc": "", "long_desc1": ""}


# ---------------------------------------------------------------------------
# Your actual job: headers + row assembly + CSV writing
# ---------------------------------------------------------------------------
HEADERS_PATH = os.path.join("sample_data", "real_output_headers.json")
MAX_REF_URLS = 5


def load_real_headers() -> list:
    """Load the authoritative 252-column header list, in exact order."""
    with open(HEADERS_PATH, encoding="utf-8") as f:
        headers = json.load(f)
    if not isinstance(headers, list):
        raise ValueError(f"{HEADERS_PATH} must contain a JSON array of column names")
    return headers


def _resolve_part_manuf(row: "CleanRow") -> str:
    """TODO: CONFIRM WITH TEAM — reconstruct the combined Part_Manuf display string."""
    if row.manufacturer_name and row.manufacturer_code:
        return f"{row.manufacturer_name} ({row.manufacturer_code})"
    return row.manufacturer_name or row.manufacturer_code or ""


def _resolve_brand_name(row: "CleanRow") -> str:
    """TODO: CONFIRM WITH TEAM — which brand field wins when several are present."""
    return row.e1_brand or row.unilog_brand or row.dib_brand or ""


def _classification_found(classification) -> bool:
    """
    Adapter for the two Classification shapes floating around the team:
      - models.py contract: has a `found: bool` field
      - actual classify.py:  has a `state: "FOUND" | "UNKNOWN"` field instead
    Works with either without needing classify.py to change.
    """
    if hasattr(classification, "found"):
        return bool(classification.found)
    if hasattr(classification, "state"):
        return classification.state == "FOUND"
    return False


def _resolve_mfr_url(enriched) -> Optional[str]:
    """
    Adapter for the two EnrichedRow shapes floating around the team:
      - models.py contract: field is `mfr_url`
      - actual enrich.py:    field is `source_url` instead
    """
    if hasattr(enriched, "mfr_url"):
        return enriched.mfr_url
    return getattr(enriched, "source_url", None)


def _resolve_ref_urls(enriched) -> list:
    """
    TODO: CONFIRM WITH TEAM — the real enrich.py has no ref_urls field at
    all (it only tracks a single manufacturer source, not extra reference
    links). Returns [] until/unless that's added, so Ref URL 1-5 stay blank.
    """
    return getattr(enriched, "ref_urls", [])


def build_output_row(row: "CleanRow", headers: list) -> dict:
    out = {h: "" for h in headers}

    classification = classify(row)
    enriched = enrich(row)
    descs = build_all(enriched, row.manufacturer_name)

    # --- Always-populated identity/description columns ---
    always = {
        "Mfg_Part_Num": row.mfg_part_num,
        "Part_Desc": row.part_desc,
        "E1_Brand": row.e1_brand or "",
        "Unilog_Brand": row.unilog_brand or "",
        "DIB_Brand": row.dib_brand or "",
        "Part_Manuf": _resolve_part_manuf(row),
        "MANUFACTURER_NAME": row.manufacturer_name or "",
        "MANUFACTURER_PART_NUMBER": row.mfg_part_num,  # TODO: CONFIRM WITH TEAM
        "BRAND_NAME": _resolve_brand_name(row),
        "INVOICE_DESC": descs.get("invoice_desc", ""),
        "MOBILE_DESC": descs.get("mobile_desc", ""),
        "SHORT_DESC": descs.get("short_desc", ""),
        "LONG_DESC1": descs.get("long_desc1", ""),
    }
    for col, val in always.items():
        if col in out:
            out[col] = val if val is not None else ""

    # --- Classification columns, only if found ---
    if _classification_found(classification):
        for col, val in {
            "Dept": classification.dept,
            "Class": classification.cls,
            "Fine": classification.fine,
            "Classpath": classification.classpath,
        }.items():
            if col in out:
                out[col] = val or ""

    # --- MFR URL ---
    mfr_url = _resolve_mfr_url(enriched)
    if mfr_url is not None and "MFR URL" in out:
        out["MFR URL"] = mfr_url

    # --- Ref URLs (up to 5) ---
    for i, url in enumerate(_resolve_ref_urls(enriched)[:MAX_REF_URLS], start=1):
        col = f"Ref URL {i}"
        if col in out:
            out[col] = url

    # --- Attributes: sequential slots, no gaps, skip BLANK (value is None) ---
    slot = 1
    for attr in enriched.attributes:
        if attr.value is None:  # BLANK state
            continue
        label_col = f"ATTRIBUTE_LABEL {slot}"
        value_col = f"ATTRIBUTE_VALUE {slot}"
        uom_col = f"ATTRIBUTE_UOM {slot}"
        if label_col in out:
            out[label_col] = attr.label
        if value_col in out:
            out[value_col] = str(attr.value)
        if uom_col in out:
            out[uom_col] = str(attr.uom) if attr.uom is not None else ""
        slot += 1

    assert all(isinstance(v, str) for v in out.values()), "All output values must be strings"
    return out


def run(input_path: str, output_path: str, limit: Optional[int] = None) -> None:
    headers = load_real_headers()
    rows = load_clean_rows(input_path)

    if limit is not None:
        rows = rows[:limit]

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="raise")
            writer.writeheader()
            n = 0
            for row in rows:
                out_row = build_output_row(row, headers)
                writer.writerow(out_row)
                n += 1
        print(f"Written {n} rows to {output_path}")
    except Exception as e:
        print(f"Failed to write output CSV: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--input", default="sample_data/input_slice.csv")
    parser.add_argument("--output", default="output_demo.csv")
    args = parser.parse_args()
    run(args.input, args.output, args.limit)
