"""Quick smoke test for src/models.py — run from project root with:
    python3 scripts/test_models.py
"""
import sys
sys.path.insert(0, "src")

from models import (
    CleanRow, Attribute, Classification, EnrichedRow,
    make_found_attr, make_blank_attr, ATTRIBUTE_LABELS,
)

# CleanRow
row = CleanRow("565374", "565374 75W Led A19 Med 27k 4pk", None, None, None, "Phillips Lighting", "5831")
print("CleanRow OK:", row.mfg_part_num, row.manufacturer_name)

# FOUND attribute
a = make_found_attr("Wattage", "75", "W", "High", "Part_Desc")
print("Attribute FOUND:", a.label, a.state, a.confidence)

# BLANK attribute
b = make_blank_attr("Lumens")
print("Attribute BLANK:", b.label, b.state, b.confidence, b.value)

# Invariant — BLANK with High confidence must raise
try:
    bad = Attribute("Test", None, None, "High", "Part_Desc")
    print("ERROR: should have raised ValueError")
except ValueError as e:
    print("Invariant enforced OK:", e)

# Classification
c = Classification(
    "Lighting & Ceiling Fans", "Light Bulbs", "LED Bulbs",
    "Lighting & Ceiling Fans>Light Bulbs>LED Bulbs", True
)
print("Classification OK:", c.classpath)

# EnrichedRow
er = EnrichedRow("565374", row.part_desc, "https://www.usa.lighting.philips.com/...", [], [])
print("EnrichedRow OK:", er.mfg_part_num, er.mfr_url)

# Attribute labels order
print("ATTRIBUTE_LABELS:", ATTRIBUTE_LABELS)

print("\nAll models OK.")
