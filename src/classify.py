"""
Stage 2 — Taxonomy & Classification.

We don't have the real ~161,000-row cross-category LOV file, so this is a
small, honest, rule-based classifier scoped to our chosen category
(Lighting -> LED bulbs), not a general-purpose classifier. It looks for
keyword signals in the raw description to decide Dept / Class / Fine and
a Classpath string, in the same style as the one worked example we do
have (e.g. "Appliances & Consumer Electronics>Kitchen Appliances>Built-In
Dishwashers").
"""

import re
from dataclasses import dataclass

from ingest import CleanRow

# Keyword -> (Dept, Class, Fine) for the lighting slice.
# LED bulb descriptions in the real sample all mention "Led" plus a shape
# code (A19, ST19, MR16, R20, PAR...) or "Flor"/"Strip"/"Sodium" for other
# lamp technologies. We classify what we can and mark the rest UNKNOWN
# rather than guessing.
BULB_SHAPE_RE = re.compile(
    r"\b(A19|A15|ST19|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|T12|T9|T8)\b",
    re.IGNORECASE,
)

TECH_KEYWORDS = {
    "led": "LED",
    "flor": "Fluorescent",
    "sodium": "High-Intensity Discharge",
    "strip": "LED Strip Light",
}


@dataclass
class Classification:
    dept: str
    cls: str
    fine: str
    classpath: str
    bulb_shape: str | None
    technology: str | None
    state: str  # FOUND or UNKNOWN


def classify(row: CleanRow) -> Classification:
    desc = row.part_desc.lower()

    technology = None
    for kw, label in TECH_KEYWORDS.items():
        if kw in desc:
            technology = label
            break

    shape_match = BULB_SHAPE_RE.search(row.part_desc)
    bulb_shape = shape_match.group(1).upper() if shape_match else None

    if technology == "LED Strip Light":
        dept, cls, fine = "Lighting & Ceiling Fans", "Light Fixtures", "LED Strip Lights"
    elif bulb_shape or technology in ("LED", "Fluorescent", "High-Intensity Discharge"):
        dept, cls, fine = "Lighting & Ceiling Fans", "Light Bulbs", "LED Bulbs" if technology == "LED" else "Light Bulbs"
    else:
        dept, cls, fine = "Lighting & Ceiling Fans", "Light Bulbs", "UNKNOWN"

    classpath = f"{dept}>{cls}>{fine}"
    state = "FOUND" if (bulb_shape or technology) else "UNKNOWN"

    return Classification(
        dept=dept,
        cls=cls,
        fine=fine,
        classpath=classpath,
        bulb_shape=bulb_shape,
        technology=technology,
        state=state,
    )


if __name__ == "__main__":
    from ingest import load_and_clean

    rows = load_and_clean("sample_data/input_slice.csv")
    for r in rows[:10]:
        c = classify(r)
        print(r.mfg_part_num, "|", r.part_desc, "->", c.classpath, "|", c.bulb_shape, c.technology, c.state)
