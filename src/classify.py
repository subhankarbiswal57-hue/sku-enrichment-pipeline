"""
Stage 2 — Taxonomy Classification (Person A)

Maps raw SKU part descriptions to standard retail taxonomy hierarchies.
Priority:
  1. 'strip' -> Lighting & Ceiling Fans>Light Fixtures>LED Strip Lights
  2. 'led' or standard bulb shape -> Lighting & Ceiling Fans>Light Bulbs>LED Bulbs
  3. 'flor', 'sodium', 'halogen', 'lamp', 'bulb', 'highbay', 'downlight', 'pendant' -> Lighting & Ceiling Fans>Light Bulbs>Light Bulbs
  4. No match -> all fields "", found=False (NOT "UNKNOWN")

Classpath uses single '>' delimiter with no spaces around it.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from models import CleanRow, Classification

BULB_SHAPE_RE = re.compile(
    r"\b(A19|A15|A21|ST19|ST21|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|G16.5|T12|T9|T8|T5|ED28)\b",
    re.IGNORECASE,
)

STRIP_RE = re.compile(r"\b(?:strip|tape\s*light|under[\s-]?cabinet)\b", re.IGNORECASE)
LED_RE = re.compile(r"\bled\b", re.IGNORECASE)
GENERIC_LIGHT_RE = re.compile(
    r"\b(?:flor|fluorescent|sodium|hid|halogen|xenon|lamp|bulb|highbay|high[\s-]?bay|downlight|pendant|sconce|chandelier|flush\s*mount)\b",
    re.IGNORECASE,
)


def classify(row: CleanRow) -> Classification:
    """
    Classify a CleanRow into Dept > Class > Fine taxonomy.
    Always returns a Classification instance.
    """
    desc = row.part_desc or ""

    # Priority 1: Strip / undercabinet fixtures
    if STRIP_RE.search(desc):
        dept = "Lighting & Ceiling Fans"
        cls = "Light Fixtures"
        fine = "LED Strip Lights"
        return Classification(
            dept=dept,
            cls=cls,
            fine=fine,
            classpath=f"{dept}>{cls}>{fine}",
            found=True,
        )

    # Priority 2: LED or specific bulb shape -> LED Bulbs
    if LED_RE.search(desc) or BULB_SHAPE_RE.search(desc):
        dept = "Lighting & Ceiling Fans"
        cls = "Light Bulbs"
        fine = "LED Bulbs"
        return Classification(
            dept=dept,
            cls=cls,
            fine=fine,
            classpath=f"{dept}>{cls}>{fine}",
            found=True,
        )

    # Priority 3: Fluorescent, halogen, sodium, lamp, bulb, highbay, downlight, pendant
    if GENERIC_LIGHT_RE.search(desc):
        dept = "Lighting & Ceiling Fans"
        cls = "Light Bulbs"
        fine = "Light Bulbs"
        return Classification(
            dept=dept,
            cls=cls,
            fine=fine,
            classpath=f"{dept}>{cls}>{fine}",
            found=True,
        )

    # Priority 4: No match -> all empty strings, found=False
    return Classification(
        dept="",
        cls="",
        fine="",
        classpath="",
        found=False,
    )


if __name__ == "__main__":
    from ingest import load_and_clean

    rows = load_and_clean("sample_data/input_slice.csv")
    found_count = 0
    for r in rows:
        c = classify(r)
        if c.found:
            found_count += 1
    print(f"Classified {found_count}/{len(rows)} rows ({100*found_count/len(rows):.1f}%)")
    for r in rows[:5]:
        c = classify(r)
        print(f"  {r.mfg_part_num} | {r.part_desc} -> {c.classpath} [found={c.found}]")
