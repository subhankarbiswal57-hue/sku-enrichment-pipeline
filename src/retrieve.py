"""
Stage 3 — Source Discovery & Retrieval.

MVP implementation: a curated set of real, pre-fetched manufacturer pages
(sample_data/curated_sources/), looked up by part number via manifest.json.
This is a deliberate MVP simplification, named explicitly rather than
hidden — see the project plan's architecture section. In production this
stage would be a live, rate-limited web search that:
  - prioritizes the manufacturer's own domain
  - excludes known marketplace/distributor domains (Amazon, eBay, etc.)
  - falls back to other legitimate third-party technical sources

The two curated sources included here are REAL pages fetched from
usa.lighting.philips.com (Philips' actual manufacturer site) for two SKUs
in our real input slice — not fabricated text.
"""

import json
import os

CURATED_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_data", "curated_sources")


def load_manifest() -> dict:
    with open(os.path.join(CURATED_DIR, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def retrieve(mfg_part_num: str) -> dict | None:
    """
    Returns {"source_url": ..., "source_text": ...} if a curated source
    exists for this part number, else None (meaning: no source found,
    downstream extraction should mark everything UNKNOWN for this row
    rather than guess).
    """
    manifest = load_manifest()
    entry = manifest.get(mfg_part_num)
    if not entry:
        return None

    path = os.path.join(CURATED_DIR, entry["source_file"])
    with open(path, encoding="utf-8") as f:
        text = f.read()

    return {"source_url": entry["source_url"], "source_text": text}


if __name__ == "__main__":
    for part_num in ["565374", "586875", "999999-not-in-set"]:
        result = retrieve(part_num)
        if result:
            print(f"{part_num}: FOUND -> {result['source_url']}")
        else:
            print(f"{part_num}: NO SOURCE (would be UNKNOWN downstream)")
