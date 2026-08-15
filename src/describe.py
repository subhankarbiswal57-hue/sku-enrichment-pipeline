"""
Stage 6 — Description Building.

Generates the different description formats the real output schema
requires, using ONLY attributes marked FOUND — never inventing a claim
that isn't backed by an extracted value. Casing/length behavior is
reverse-engineered from the one worked example we have (the Frigidaire
dishwasher row):
  - INVOICE_DESC:  short, ALL CAPS   (worked example: "DISHWASHER LEG 5
    SST 120V 15A 50-1/4IN" — 38 chars)
  - MOBILE_DESC:   ~60-80 chars, sentence case, brand-led
  - SHORT_DESC:    title/product-name style
  - LONG_DESC1:    the fullest description, comma-separated spec list

We don't have the exact character-limit rulebook (content guidelines
doc), so limits below are inferred from the worked example's actual
lengths, not copied from a source we don't have. This is stated
explicitly rather than presented as if it were the official rule.
"""

from enrich import EnrichedRow


def _found(attrs, label) -> str | None:
    for a in attrs:
        if a.label == label and a.state == "FOUND":
            return a.value
    return None


def build_invoice_desc(row: EnrichedRow, manufacturer_name: str) -> str:
    """ALL CAPS, short — matches worked example's style and rough length."""
    watt = _found(row.attributes, "Wattage")
    base = _found(row.attributes, "Base Type")
    pack = _found(row.attributes, "Pack Quantity")

    parts = ["LED BULB"]
    if watt:
        parts.append(f"{watt}W")
    if base:
        parts.append(base)
    if pack:
        parts.append(f"{pack}PK")

    return " ".join(parts).upper()[:40]


def build_mobile_desc(row: EnrichedRow, manufacturer_name: str) -> str:
    """Brand-led, sentence style, ~60-80 char target (not enforced here
    since we don't have the exact character-limit spec)."""
    watt = _found(row.attributes, "Wattage")
    cct = _found(row.attributes, "Color Temperature")

    parts = [manufacturer_name, "LED Bulb"]
    if watt:
        parts.append(f"{watt}W")
    if cct:
        parts.append(f"{cct}K")
    return ", ".join(parts)


def build_short_desc(row: EnrichedRow, manufacturer_name: str) -> str:
    watt = _found(row.attributes, "Wattage")
    base = _found(row.attributes, "Base Type")
    pack = _found(row.attributes, "Pack Quantity")

    bits = [manufacturer_name, "LED Bulb"]
    if watt:
        bits.append(f"{watt}W")
    if base:
        bits.append(f"{base} Base")
    if pack:
        bits.append(f"{pack}-Pack")
    return " ".join(bits)


def build_long_desc(row: EnrichedRow, manufacturer_name: str) -> str:
    """Full comma-separated spec list — only from FOUND attributes."""
    bits = [f"{manufacturer_name} LED Bulb"]
    for label, uom in [
        ("Wattage", "W"),
        ("Color Temperature", "K"),
        ("Lumens", "lm"),
        ("Rated Life", "h"),
        ("Base Type", None),
        ("Pack Quantity", None),
        ("Dimmable", None),
    ]:
        val = _found(row.attributes, label)
        if not val:
            continue
        if label == "Pack Quantity":
            bits.append(f"{val}-Pack")
        elif label == "Dimmable":
            bits.append("Dimmable")
        elif label == "Base Type":
            bits.append(f"{val} Base")
        elif uom:
            bits.append(f"{val} {uom}")
        else:
            bits.append(val)
    return ", ".join(bits)


def build_all(row: EnrichedRow, manufacturer_name: str) -> dict:
    return {
        "INVOICE_DESC": build_invoice_desc(row, manufacturer_name),
        "MOBILE_DESC": build_mobile_desc(row, manufacturer_name),
        "SHORT_DESC": build_short_desc(row, manufacturer_name),
        "LONG_DESC1": build_long_desc(row, manufacturer_name),
    }


if __name__ == "__main__":
    from enrich import enrich
    from ingest import load_and_clean

    rows = load_and_clean("sample_data/input_slice.csv")
    by_part = {r.mfg_part_num: r for r in rows}

    for part_num in ["565374", "586875"]:
        raw_row = by_part[part_num]
        enriched = enrich(raw_row)
        descs = build_all(enriched, raw_row.manufacturer_name)
        print(part_num, "|", raw_row.part_desc)
        for k, v in descs.items():
            print(f"  {k} ({len(v)} chars): {v}")
        print()
