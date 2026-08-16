"""
Shared data models for the SKU Enrichment Pipeline.

All pipeline stages import from here. These are the interface contracts
between the four team members' modules — agree on these before splitting.

Do NOT add stage-specific logic here. This file is models only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# CleanRow — output of ingest.py
# ---------------------------------------------------------------------------

@dataclass
class CleanRow:
    """
    A sanitised input row with placeholder brand values removed and the
    manufacturer code parsed out of Part_Manuf.

    Fields are never mutated after construction.
    mfg_part_num and part_desc are always non-empty stripped strings.
    All brand/manufacturer fields may be None.
    """
    mfg_part_num: str           # stripped, never None or empty
    part_desc: str              # stripped, never None or empty
    e1_brand: str | None        # None if placeholder ("-- Unbranded --") or empty
    unilog_brand: str | None    # None if placeholder or empty
    dib_brand: str | None       # None if placeholder or empty
    manufacturer_name: str | None   # text before the parenthesis in Part_Manuf, or None
    manufacturer_code: str | None   # alphanumeric code inside parenthesis, e.g. "5831"


# ---------------------------------------------------------------------------
# Attribute — core data contract for extracted product characteristics
# ---------------------------------------------------------------------------

@dataclass
class Attribute:
    """
    A single extracted product characteristic.

    state is derived from value (not stored):
        FOUND  — value is a non-empty string, confirmed from evidence
        BLANK  — value is None, no evidence found

    Confidence reflects how the value was obtained:
        High   — confirmed from Part_Desc via deterministic regex
        Medium — confirmed from manufacturer source page (LLM or regex fallback)
        Low    — no value found (always paired with BLANK state)

    evidence_note is a human-readable source description for the review UI:
        "Part_Desc"       — for deterministic High-confidence attributes
        "https://..."     — the manufacturer page URL for Medium-confidence attributes
        "no source"       — for BLANK attributes when no source was retrieved
        "not in Part_Desc"— for BLANK attributes when Part_Desc was searched but nothing matched
    """
    label: str                              # e.g. "Wattage", "Color Temperature"
    value: str | None                       # plain numeric or text, no unit (e.g. "75" not "75 W")
    uom: str | None                         # unit abbreviation (e.g. "W", "K", "lm") or None
    confidence: Literal["High", "Medium", "Low"]
    evidence_note: str                      # source description for the review UI

    @property
    def state(self) -> Literal["FOUND", "BLANK"]:
        """Derived from value. FOUND if value is not None, BLANK otherwise."""
        return "FOUND" if self.value is not None else "BLANK"

    def __post_init__(self) -> None:
        if self.confidence not in ("High", "Medium", "Low"):
            raise ValueError(
                f"Attribute '{self.label}': invalid confidence {self.confidence!r}. "
                "Must be 'High', 'Medium', or 'Low'."
            )
        # BLANK state (value is None) must always have Low confidence.
        # A value cannot be absent yet be claimed as High or Medium confidence.
        if self.value is None and self.confidence != "Low":
            raise ValueError(
                f"Attribute '{self.label}': BLANK state (value=None) requires "
                f"confidence='Low', got {self.confidence!r}."
            )


# ---------------------------------------------------------------------------
# Classification — output of classify.py
# ---------------------------------------------------------------------------

@dataclass
class Classification:
    """
    Taxonomy assignment for a single input row.

    When found=True, dept/cls/fine/classpath are all populated.
    When found=False, all four fields are empty string "" (NOT "UNKNOWN").
    The ground truth uses blank cells for unclassified items.

    Classpath format: single ">" delimiter, no spaces.
    Example: "Lighting & Ceiling Fans>Light Bulbs>LED Bulbs"
    """
    dept: str       # e.g. "Lighting & Ceiling Fans" or ""
    cls: str        # e.g. "Light Bulbs" or ""
    fine: str       # e.g. "LED Bulbs" or ""
    classpath: str  # e.g. "Lighting & Ceiling Fans>Light Bulbs>LED Bulbs" or ""
    found: bool     # True when at least one keyword/shape signal was matched


# ---------------------------------------------------------------------------
# EnrichedRow — output of enrich.py
# ---------------------------------------------------------------------------

@dataclass
class EnrichedRow:
    """
    The fully enriched record for a single input row, ready for output assembly.

    attributes is always exactly 7 elements in fixed label order:
        1. Wattage          (Part_Desc source)
        2. Color Temperature (Part_Desc source)
        3. Pack Quantity    (Part_Desc source)
        4. Base Type        (Part_Desc source)
        5. Lumens           (Manufacturer source)
        6. Rated Life       (Manufacturer source)
        7. Dimmable         (Manufacturer source)

    mfr_url is the manufacturer page URL used as evidence, or None.
    ref_urls holds up to 5 additional reference URLs (manuals, spec sheets).
    """
    mfg_part_num: str
    part_desc: str
    mfr_url: str | None          # None if no manufacturer source was retrieved
    ref_urls: list[str] = field(default_factory=list)   # up to 5 entries
    attributes: list[Attribute] = field(default_factory=list)  # always 7


# ---------------------------------------------------------------------------
# Convenience factory helpers (used by enrich.py)
# ---------------------------------------------------------------------------

def make_found_attr(
    label: str,
    value: str,
    uom: str | None,
    confidence: Literal["High", "Medium"],
    evidence_note: str,
) -> Attribute:
    """Create a FOUND Attribute. value must be a non-empty string."""
    if not value:
        raise ValueError(f"make_found_attr called with empty value for label '{label}'")
    return Attribute(
        label=label,
        value=value,
        uom=uom,
        confidence=confidence,
        evidence_note=evidence_note,
    )


def make_blank_attr(label: str, evidence_note: str = "not in Part_Desc") -> Attribute:
    """Create a BLANK Attribute with Low confidence."""
    return Attribute(
        label=label,
        value=None,
        uom=None,
        confidence="Low",
        evidence_note=evidence_note,
    )


# ---------------------------------------------------------------------------
# Fixed attribute label order (used by enrich.py and pipeline.py)
# ---------------------------------------------------------------------------

ATTRIBUTE_LABELS: list[str] = [
    "Wattage",
    "Color Temperature",
    "Pack Quantity",
    "Base Type",
    "Lumens",
    "Rated Life",
    "Dimmable",
]
