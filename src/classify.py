"""
Stage 2 — Taxonomy & Classification.

Hierarchical taxonomy engine that maps product titles and manufacturer context into
standard retail classification trees (Dept > Class > Fine).

Covers:
  - Lighting & Ceiling Fans > Light Bulbs (LED, Fluorescent, Halogen, HID, Incandescent)
  - Lighting & Ceiling Fans > Light Fixtures (Wall Sconces, Bath Lights, Chandeliers, Pendants, Flush Mounts, Strip Lights, Commercial)
  - Lighting & Ceiling Fans > Ceiling Fans
  - Electrical > Wiring Devices (Switches, Dimmers, Outlets, Wall Plates)
  - Electrical > Distribution & Panels (Circuit Breakers, Load Centers)
"""

import re
from dataclasses import dataclass

from ingest import CleanRow

BULB_SHAPE_RE = re.compile(
    r"\b(A19|A15|A21|ST19|ST21|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|G16.5|T12|T9|T8|T5|ED28)\b",
    re.IGNORECASE,
)

TECH_KEYWORDS = {
    "led": "LED",
    "flor": "Fluorescent",
    "fluorescent": "Fluorescent",
    "sodium": "High-Intensity Discharge",
    "hid": "High-Intensity Discharge",
    "halogen": "Halogen",
    "xenon": "Halogen",
    "incandescent": "Incandescent",
    "filament": "LED Filament",
}

# Ordered taxonomy matching rules: (Pattern, Dept, Class, Fine)
FIXTURE_RULES = [
    # Bath & Vanity
    (re.compile(r"\b(?:bath\s*(?:lt|light)|vanity)\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "Vanity & Bath Lights"),
    # Wall Lights & Sconces
    (re.compile(r"\b(?:wall\s*(?:lt|light)|sconce|wall\s*mount)\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "Wall Sconces & Wall Lights"),
    # Chandeliers
    (re.compile(r"\b(?:chandelier|chand(?:elier)?\s*(?:lt|light))\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "Chandeliers"),
    # Pendants
    (re.compile(r"\b(?:pendant\s*(?:lt|light)?)\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "Pendant Lights"),
    # Flush & Semi-Flush Mounts
    (re.compile(r"\b(?:flush\s*(?:mt|mount)|semi[\s-]?flush)\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "Flush Mount Lighting"),
    # Strip Lights & Undercabinet
    (re.compile(r"\b(?:strip\s*(?:light|lt)|under[\s-]?cabinet|tape\s*light)\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "LED Strip Lights"),
    # Commercial & Industrial Troffers / High Bays
    (re.compile(r"\b(?:troffer|high[\s-]?bay|low[\s-]?bay|wrap\s*(?:around)?)\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "Commercial & Industrial Lighting"),
    # Ceiling Fans
    (re.compile(r"\b(?:ceiling\s*fan|paddle\s*fan)\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Ceiling Fans", "Ceiling Fans with Lights"),
    # Outdoor Fixtures
    (re.compile(r"\b(?:post\s*(?:lt|light)|lantern|landscape\s*(?:lt|light))\b", re.IGNORECASE), "Lighting & Ceiling Fans", "Light Fixtures", "Outdoor Lighting"),
]

ELECTRICAL_RULES = [
    (re.compile(r"\b(?:dimmer|slide\s*dimmer|rotary\s*dimmer)\b", re.IGNORECASE), "Electrical", "Wiring Devices", "Dimmers"),
    (re.compile(r"\b(?:rocker\s*switch|toggle\s*switch|single\s*pole\s*switch|3-way\s*switch)\b", re.IGNORECASE), "Electrical", "Wiring Devices", "Light Switches"),
    (re.compile(r"\b(?:receptacle|outlet|gfci|gfi)\b", re.IGNORECASE), "Electrical", "Wiring Devices", "Outlets & Receptacles"),
    (re.compile(r"\b(?:wall\s*plate|switch\s*plate)\b", re.IGNORECASE), "Electrical", "Wiring Devices", "Wall Plates"),
    (re.compile(r"\b(?:circuit\s*breaker|breaker)\b", re.IGNORECASE), "Electrical", "Distribution & Panels", "Circuit Breakers"),
    (re.compile(r"\b(?:load\s*center|panel\s*board|breaker\s*box)\b", re.IGNORECASE), "Electrical", "Distribution & Panels", "Electrical Panels & Load Centers"),
]


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
    desc = row.part_desc
    desc_lower = desc.lower()

    # 1. Check technology signal
    technology = None
    for kw, label in TECH_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", desc_lower):
            technology = label
            break

    # 2. Check bulb shape signal
    shape_match = BULB_SHAPE_RE.search(desc)
    bulb_shape = shape_match.group(1).upper() if shape_match else None

    # 3. Match against Light Fixtures rules
    for pattern, dept, cls, fine in FIXTURE_RULES:
        if pattern.search(desc):
            classpath = f"{dept}>{cls}>{fine}"
            return Classification(
                dept=dept,
                cls=cls,
                fine=fine,
                classpath=classpath,
                bulb_shape=bulb_shape,
                technology=technology or ("LED" if "led" in desc_lower else None),
                state="FOUND",
            )

    # 4. Match against Electrical rules
    for pattern, dept, cls, fine in ELECTRICAL_RULES:
        if pattern.search(desc):
            classpath = f"{dept}>{cls}>{fine}"
            return Classification(
                dept=dept,
                cls=cls,
                fine=fine,
                classpath=classpath,
                bulb_shape=None,
                technology=None,
                state="FOUND",
            )

    # 5. Match against Bulbs / Lamps rules
    if bulb_shape or (technology and any(w in desc_lower for w in ("bulb", "lamp", "cct", "pk", "pack", "w", "med", "candelabra"))):
        dept = "Lighting & Ceiling Fans"
        cls = "Light Bulbs"
        if technology == "LED" or "led" in desc_lower:
            fine = "LED Bulbs"
        elif technology == "Fluorescent":
            fine = "Fluorescent Bulbs"
        elif technology == "High-Intensity Discharge":
            fine = "High-Intensity Discharge Bulbs"
        elif technology == "Halogen":
            fine = "Halogen Bulbs"
        elif technology == "Incandescent":
            fine = "Incandescent Bulbs"
        else:
            fine = "Light Bulbs"

        classpath = f"{dept}>{cls}>{fine}"
        return Classification(
            dept=dept,
            cls=cls,
            fine=fine,
            classpath=classpath,
            bulb_shape=bulb_shape,
            technology=technology or "LED",
            state="FOUND",
        )

    # 6. Fallback if no specific signal found
    dept, cls, fine = "Lighting & Ceiling Fans", "Light Bulbs", "UNKNOWN"
    classpath = f"{dept}>{cls}>{fine}"
    return Classification(
        dept=dept,
        cls=cls,
        fine=fine,
        classpath=classpath,
        bulb_shape=bulb_shape,
        technology=technology,
        state="UNKNOWN",
    )


if __name__ == "__main__":
    from ingest import load_and_clean

    rows = load_and_clean("sample_data/input_slice.csv")
    print(f"Testing classification on {len(rows)} rows...")
    classified_count = 0
    for r in rows:
        c = classify(r)
        if c.state == "FOUND":
            classified_count += 1
    print(f"Successfully classified {classified_count}/{len(rows)} ({100*classified_count/len(rows):.1f}%)")
    for r in rows[:10]:
        c = classify(r)
        print(f"  {r.mfg_part_num} | {r.part_desc} -> {c.classpath} [State: {c.state}]")

