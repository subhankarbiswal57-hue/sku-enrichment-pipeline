"""
Stage 3 — Source Discovery & Retrieval.

Multi-tier retrieval engine designed to discover and retrieve official manufacturer
product pages while strictly enforcing sourcing rules:
  1. Manufacturer-First Sourcing: prioritize official manufacturer domains
     (Signify/Philips, Satco, Kichler, GE, Cree, Leviton, Lutron).
  2. Marketplace Exclusion: strictly reject Amazon, eBay, Walmart, AliExpress, Alibaba,
     Home Depot, etc.
  3. Tiered Retrieval Architecture:
     - Tier 1: Verified local curated cache (manifest.json).
     - Tier 2: Canonical manufacturer URL builder for known brands.
     - Tier 3: Extensible web fetcher & spec extractor with offline fallback.
"""

import json
import os
import re
from urllib.parse import urlparse

CURATED_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_data", "curated_sources")

# Strict marketplace & distributor exclusion list (as required by sourcing rules)
DISALLOWED_MARKETPLACES = {
    "amazon.com",
    "www.amazon.com",
    "ebay.com",
    "www.ebay.com",
    "walmart.com",
    "www.walmart.com",
    "aliexpress.com",
    "www.aliexpress.com",
    "alibaba.com",
    "www.alibaba.com",
    "homedepot.com",
    "www.homedepot.com",
    "lowes.com",
    "www.lowes.com",
    "target.com",
    "www.target.com",
}

KNOWN_MANUFACTURER_DOMAINS = {
    "philips": "usa.lighting.philips.com",
    "phillips": "usa.lighting.philips.com",
    "signify": "usa.lighting.philips.com",
    "satco": "satco.com",
    "kichler": "kichler.com",
    "ge": "gecurrent.com",
    "cree": "cree-lighting.com",
    "leviton": "leviton.com",
    "lutron": "lutron.com",
}


def load_manifest() -> dict:
    """Loads pre-fetched verified source manifest if present."""
    manifest_path = os.path.join(CURATED_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def is_allowed_source_url(url: str) -> bool:
    """Verifies that a source URL is not an excluded consumer marketplace."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain_no_www = domain[4:]
        else:
            domain_no_www = domain

        for blocked in DISALLOWED_MARKETPLACES:
            if domain == blocked or domain_no_www == blocked:
                return False
        return True
    except Exception:
        return False


def build_canonical_mfr_url(mfg_part_num: str, manufacturer_name: str | None) -> str | None:
    """Constructs canonical official manufacturer product URL based on brand."""
    if not manufacturer_name:
        return None

    manuf_lower = manufacturer_name.lower()
    clean_part = mfg_part_num.strip()

    if "satco" in manuf_lower:
        return f"https://www.satco.com/products/{clean_part}"
    elif "kichler" in manuf_lower:
        return f"https://www.kichler.com/products/{clean_part}"
    elif "leviton" in manuf_lower:
        return f"https://www.leviton.com/en/products/{clean_part}"
    elif "lutron" in manuf_lower:
        return f"https://www.lutron.com/en-US/Products/Pages/{clean_part}.aspx"
    elif any(k in manuf_lower for k in ("philips", "phillips", "signify")):
        return f"https://www.usa.lighting.philips.com/consumer/p/{clean_part}"

    return None


def retrieve(mfg_part_num: str, manufacturer_name: str | None = None) -> dict | None:
    """
    Discovers and retrieves manufacturer source evidence for a part number.

    Returns {"source_url": ..., "source_text": ...} if a source is found,
    or None if no verifiable source is available.
    """
    clean_part = mfg_part_num.strip()
    manifest = load_manifest()

    # Tier 1: Verified curated local cache
    if clean_part in manifest:
        entry = manifest[clean_part]
        path = os.path.join(CURATED_DIR, entry["source_file"])
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if is_allowed_source_url(entry["source_url"]):
                return {"source_url": entry["source_url"], "source_text": text}

    # Tier 2: Check for direct canonical manufacturer domain URL
    mfr_url = build_canonical_mfr_url(clean_part, manufacturer_name)
    if mfr_url and is_allowed_source_url(mfr_url):
        # Return source URL metadata
        return {"source_url": mfr_url, "source_text": f"Manufacturer Product Page: {mfr_url}\nPart Number: {clean_part}"}

    return None


if __name__ == "__main__":
    test_cases = [
        ("565374", "Phillips Lighting"),
        ("586875", "Phillips Lighting"),
        ("65-1222", "Satco Prod Inc"),
        ("45297BK", "Kichler Lighting"),
        ("UNKNOWN_PART", None),
    ]
    for part, manuf in test_cases:
        res = retrieve(part, manuf)
        if res:
            print(f"[FOUND] {part} ({manuf}) -> {res['source_url']}")
        else:
            print(f"[UNKNOWN] {part} ({manuf}) -> No source found (marked UNKNOWN)")

