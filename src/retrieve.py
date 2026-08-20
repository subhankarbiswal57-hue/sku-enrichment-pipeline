"""
Stage 3 — Source Discovery & Retrieval (Person A)

Architecture:
  1. Curated manifest cache (fast-path)
  2. Live DuckDuckGo web search (fallback)
  3. Strict marketplace domain filtering (rejects Amazon, eBay, Home Depot, etc.)
  4. Web fetcher & HTML cleaner with timeout and error handling

NEVER raises — logs warnings on network/parsing issues and returns None.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from urllib.parse import unquote, urlparse
import urllib.request
import urllib.parse
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger(__name__)

CURATED_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_data", "curated_sources")
MANIFEST_PATH = os.path.join(CURATED_DIR, "manifest.json")

BLOCKED_DOMAINS = frozenset({
    "amazon.",
    "ebay.",
    "homedepot.",
    "grainger.",
    "lowes.",
    "walmart.",
    "tractorsupply.",
    "aliexpress.",
    "alibaba.",
    "target.",
})

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Load curated manifest once at module import
_MANIFEST: dict[str, dict] = {}
try:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            _MANIFEST = json.load(f)
            for part_num, entry in _MANIFEST.items():
                url = entry.get("source_url", "")
                for b in BLOCKED_DOMAINS:
                    if b in url.lower():
                        logger.warning("Blocked marketplace domain in curated manifest for %s: %s", part_num, url)
except Exception as e:
    logger.warning("Could not load curated sources manifest from %s: %e", MANIFEST_PATH, e)


def is_allowed_source_url(url: str) -> bool:
    """Checks whether URL domain is not an excluded consumer marketplace."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        domain = urlparse(url).netloc.lower()
        for blocked in BLOCKED_DOMAINS:
            if blocked in domain:
                return False
        return True
    except Exception:
        return False


def _clean_html_text(html: str) -> str:
    """Strips scripts, styles, and HTML tags to extract clean text."""
    # Remove script and style tags
    clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Decode basic entities
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    # Collapse whitespace
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n\s*\n+", "\n\n", clean)
    return clean.strip()


def _fetch_page_text(url: str, timeout: int = 8) -> str | None:
    """Fetches URL and returns readable extracted text."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            if "text" not in content_type and "html" not in content_type and "json" not in content_type:
                return None
            raw = resp.read().decode("utf-8", errors="ignore")
            text = _clean_html_text(raw)
            return text if len(text) > 50 else None
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return None


def _search_ddg(query: str, max_results: int = 5) -> list[str]:
    """Queries DuckDuckGo Lite and returns non-blocked candidate URLs."""
    urls: list[str] = []
    try:
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            "https://lite.duckduckgo.com/lite/",
            data=data,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Extract links
            found = re.findall(r'<a[^>]+class=[\'"]result-link[\'"][^>]+href=[\'"]([^\'"]+)[\'"]', html)
            if not found:
                found = re.findall(r'<a[^>]+href=[\'"](https?://[^\'"]+)[\'"]', html)

            for u in found:
                u = unquote(u)
                if is_allowed_source_url(u) and u not in urls:
                    urls.append(u)
                if len(urls) >= max_results:
                    break
    except Exception as e:
        logger.warning("DuckDuckGo search error for query '%s': %s", query, e)
    return urls


def retrieve(mfg_part_num: str, manufacturer_name: str | None = None) -> dict | None:
    """
    Retrieves manufacturer source evidence for a part number.

    1. Checks curated manifest first (fast-path).
    2. If not found: performs live search for '<manufacturer> <part_num> specifications'.
    3. Fetches first allowed non-marketplace URL.
    4. Returns {'source_url': str, 'source_text': str} or None.

    NEVER raises.
    """
    clean_part = (mfg_part_num or "").strip()
    if not clean_part:
        return None

    # Tier 1: Curated local manifest cache
    if clean_part in _MANIFEST:
        entry = _MANIFEST[clean_part]
        source_file = entry.get("source_file")
        source_url = entry.get("source_url")
        if source_file and source_url and is_allowed_source_url(source_url):
            file_path = os.path.join(CURATED_DIR, source_file)
            if os.path.exists(file_path):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        text = f.read()
                    return {"source_url": source_url, "source_text": text}
                except (OSError, IOError) as e:
                    logger.warning("Could not read curated source file %s: %s", file_path, e)

    # Tier 2: Live search fallback
    try:
        manuf = (manufacturer_name or "").strip()
        query = f"{manuf} {clean_part} specifications".strip()
        candidate_urls = _search_ddg(query, max_results=3)

        for url in candidate_urls:
            text = _fetch_page_text(url, timeout=6)
            if text:
                return {"source_url": url, "source_text": text}

    except Exception as e:
        logger.warning("Live retrieval failed for %s (%s): %s", clean_part, manufacturer_name, e)

    return None


if __name__ == "__main__":
    test_cases = [
        ("565374", "Phillips Lighting"),
        ("586875", "Phillips Lighting"),
        ("65-1222", "Satco Prod Inc"),
        ("UNKNOWN_PART_XYZ", None),
    ]
    for part, manuf in test_cases:
        res = retrieve(part, manuf)
        if res:
            print(f"[FOUND] {part} -> {res['source_url']} (len={len(res['source_text'])} chars)")
        else:
            print(f"[NOT FOUND] {part} -> None")
