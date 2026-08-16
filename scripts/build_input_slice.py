"""
One-time script: filter the full 1,000-row input to Lighting rows only
and write sample_data/input_slice.csv.

Run from the project root:
    python scripts/build_input_slice.py

Filters: keep a row if ANY of the following are true:
  - Part_Manuf contains "Phillips Lighting", "Kichler", or "Satco Prod"
  - Part_Desc contains any lighting keyword (case-insensitive):
    Led, Flor, Bulb, Lamp, Strip, Halogen, Sodium, Highbay, Downlight, Pendant

This matches the dataset filter described in the team-split.md shared setup.
"""

import csv
import os
import re

INPUT_PATH  = os.path.join("docs", "Unihack_ Sample Dataset - Input (1).csv")
OUTPUT_PATH = os.path.join("sample_data", "input_slice.csv")

# Manufacturer substrings that identify Lighting rows
MANUF_PATTERNS = [
    "Phillips Lighting",
    "Kichler",
    "Satco Prod",
    "Hunter Fan",
    "Feit Electric",
    "Cooper Lighting",
    "Lithonia Lighting",
    "Maxsa Innovations",
    "Streamlight",
]

# Part_Desc keywords that identify Lighting rows (case-insensitive)
DESC_KEYWORDS_RE = re.compile(
    r"\b(led|flor|bulb|lamp|strip|halogen|sodium|highbay|downlight|pendant|chandelier|sconce|luminar)\b",
    re.IGNORECASE,
)


def is_lighting_row(row: dict) -> bool:
    part_manuf = row.get("Part_Manuf", "")
    part_desc  = row.get("Part_Desc", "")

    for pat in MANUF_PATTERNS:
        if pat.lower() in part_manuf.lower():
            return True

    if DESC_KEYWORDS_RE.search(part_desc):
        return True

    return False


def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}\n"
            "Make sure you are running this script from the project root."
        )

    lighting_rows = []
    total = 0

    with open(INPUT_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            total += 1
            if is_lighting_row(row):
                lighting_rows.append(row)

    os.makedirs("sample_data", exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(lighting_rows)

    print(f"Total input rows:    {total}")
    print(f"Lighting rows kept:  {len(lighting_rows)}")
    print(f"Written to:          {OUTPUT_PATH}")

    # Quick sanity check
    if len(lighting_rows) < 50:
        print("WARNING: fewer than 50 rows — check filter patterns")
    elif len(lighting_rows) > 300:
        print("WARNING: more than 300 rows — filter may be too broad")
    else:
        print("Row count looks good (50–300 range).")


if __name__ == "__main__":
    main()
