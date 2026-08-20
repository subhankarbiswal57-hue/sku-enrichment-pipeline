# Team Split — SKU Enrichment Pipeline
### UniHack 2026 | 4 People | Deadline: 23 Aug 2026, 11:59 PM IST

---

## Current Project Status

| File | Status | Owner | Notes |
|------|--------|-------|-------|
| `src/models.py` | ✅ Done | Shared | CleanRow, Attribute (+ is_novel_value), Classification, EnrichedRow (+ marketing_description, item_features) |
| `src/__init__.py` | ✅ Done | Shared | Package marker |
| `src/enrich.py` | ✅ Done | B | 7 attrs, FOUND/BLANK, Grok API + fallback, marketing_description + item_features extracted from source |
| `src/describe.py` | ✅ Done | B | 5 descriptions: INVOICE, MOBILE, SHORT, LONG, RETAIL |
| `src/ingest.py` | ⏳ Pending | A | |
| `src/normalize.py` | ⏳ Pending | A | |
| `src/classify.py` | ⏳ Pending | A | |
| `src/retrieve.py` | ⏳ Pending | A | **Must be live search + curated cache — not hardcoded** |
| `src/pipeline.py` | ⏳ Pending | C | |
| `src/evaluate.py` | ⏳ Pending | D | |
| `app.py` | ⏳ Pending | D | **Must have CSV upload tab** |
| `sample_data/eval_set.csv` | ⏳ Pending | D | |
| `tests/` | ⏳ Pending | D | |
| `scripts/test_person_b.py` | ✅ Done | B | Full test with inline stubs |

**Key model changes from the video (already applied to `models.py` + `enrich.py` + `describe.py`):**
- `Attribute` now has `is_novel_value: bool = False` — set to `True` when a value isn't in any known LOV
- `EnrichedRow` now has `marketing_description: str | None` and `item_features: list[str]` — extracted from manufacturer source only, never generated
- `build_all()` now returns **5** description keys: `INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, `LONG_DESC1`, `RETAIL_DESC`

---

## ✅ Shared Setup — DONE

Already in the repo:
- `src/__init__.py` — package marker
- `src/models.py` — all shared dataclasses
- `sample_data/input_slice.csv` — 228 Lighting rows
- `sample_data/curated_sources/manifest.json` + 2 Philips `.txt` source files

Verify on your machine:
```bash
cd /Users/shazam/Downloads/sku-enrichment-pipeline
python3 scripts/test_models.py
```

---

## Standard Import

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# or from project root:
sys.path.insert(0, 'src')

from models import CleanRow, Attribute, Classification, EnrichedRow
from models import make_found_attr, make_blank_attr, ATTRIBUTE_LABELS
```

---

## Person A — Data Pipeline Core

**You own:** `src/ingest.py`, `src/normalize.py`, `src/classify.py`, `src/retrieve.py`

**Person B's enrich.py already uses your modules via lazy import — it degrades gracefully until you land your code. Aim to finish by 17 Aug.**

---

### File 1: `src/ingest.py`

```python
from models import CleanRow

PLACEHOLDER_VALUES = frozenset({
    "-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --",
})
MANUF_CODE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$")

def clean_brand(v: str) -> str | None: ...
def parse_manufacturer(raw: str) -> tuple[str | None, str | None]: ...
def load_and_clean(path: str) -> list[CleanRow]: ...
# Raises IOError if file unreadable, ValueError naming missing columns
```

Test:
```bash
python3 -c "import sys; sys.path.insert(0,'src'); from ingest import load_and_clean; rows=load_and_clean('sample_data/input_slice.csv'); print(len(rows), 'rows')"
```

---

### File 2: `src/normalize.py`

```python
WATTAGE_RE  = re.compile(r"(?<![A-Za-z])(\d+)\s*[wW]\b")
CCT_RE      = re.compile(r"\b([2-7]\d)[kK]\b")
PACK_RE     = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)
BASE_TYPE_MAP = {"med":"E26","medium":"E26","e26":"E26","e27":"E26","cand":"E12","candelabra":"E12"}

def parse_wattage(desc: str) -> str | None:   # "75W" → "75 W"
def parse_cct(desc: str) -> str | None:       # "27k" → "2700 K"
def parse_pack_qty(desc: str) -> str | None:  # "4pk" → "4"
def parse_base_type(desc: str) -> str | None: # "Med" → "E26"
```

Test:
```bash
python3 -c "import sys; sys.path.insert(0,'src'); from normalize import parse_wattage,parse_cct,parse_pack_qty,parse_base_type; d='565374 75W Led A19 Med 27k 4pk'; print(parse_wattage(d), parse_cct(d), parse_pack_qty(d), parse_base_type(d))"
```
Expected: `75 W  2700 K  4  E26`

---

### File 3: `src/classify.py`

```python
from models import CleanRow, Classification

BULB_SHAPE_RE = re.compile(r"\b(A19|A15|ST19|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|T12|T9|T8)\b", re.IGNORECASE)

def classify(row: CleanRow) -> Classification:
    # Priority: strip → led/shape → flor/sodium/halogen/lamp/bulb/highbay/downlight/pendant → blank
    # Classpath format: "Lighting & Ceiling Fans>Light Bulbs>LED Bulbs"  (single >, no spaces)
    # No match → all fields "", found=False  (NOT "UNKNOWN")
```

---

### File 4: `src/retrieve.py` ⚠️ CRITICAL CHANGE FROM VIDEO

**The evaluators explicitly said "avoid hardcoded or mocked outputs." The old 2-SKU lookup is not acceptable.**

```python
# Architecture: curated cache (fast-path) + live DuckDuckGo search (fallback)
# Marketplace domains excluded at code level: amazon., ebay., homedepot., grainger., lowes.

CURATED_DIR = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'curated_sources')
_MANIFEST: dict = {}   # loaded once at module level

def retrieve(mfg_part_num: str) -> dict | None:
    """
    1. Check curated manifest first (fast-path for known SKUs)
    2. If not found: run live web search for "<manufacturer> <part_num> specifications site:<manufacturer_domain>"
    3. Fetch the best result that is NOT a marketplace/distributor domain
    4. Return {"source_url": str, "source_text": str} or None
    5. NEVER raises — return None on any failure, log warning
    """
```

**Live search approach (no API key needed):**
```python
import urllib.request, urllib.parse

def _duckduckgo_search(query: str) -> list[str]:
    """Return up to 5 URLs from DuckDuckGo HTML search. Filter out marketplace domains."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    # Parse <a class="result__a" href="..."> links from HTML response
    # Filter: skip amazon., ebay., homedepot., grainger., lowes., walmart.
    ...

BLOCKED_DOMAINS = {"amazon.", "ebay.", "homedepot.", "grainger.", "lowes.", "walmart.", "tractorsupply."}

def _is_allowed_domain(url: str) -> bool:
    return not any(d in url.lower() for d in BLOCKED_DOMAINS)
```

Test:
```bash
python3 -c "import sys; sys.path.insert(0,'src'); from retrieve import retrieve; r=retrieve('565374'); print(r['source_url'] if r else 'NOT FOUND')"
```

---

## Person B — ✅ DONE

**`src/enrich.py` and `src/describe.py` are complete and passing all tests.**

Run to verify:
```bash
python3 scripts/test_person_b.py
```

**What was completed:**
- 7 attributes in fixed order (Wattage, Color Temperature, Pack Quantity, Base Type, Lumens, Rated Life, Dimmable)
- FOUND/BLANK state with High/Medium/Low confidence
- Grok API extraction + regex fallback (no API key needed for testing)
- `marketing_description` and `item_features` extracted from manufacturer source (manufacturer-only, never generated)
- `is_novel_value` flag on Attribute for values not in any known LOV
- 5 description formats: INVOICE_DESC (≤40 chars ALL CAPS), MOBILE_DESC, SHORT_DESC, LONG_DESC1, RETAIL_DESC

**No further changes needed unless Person A or C expose a bug.**

---

## Person C — Pipeline Orchestration + Output CSV

**You own:** `src/pipeline.py`

**Depends on A and B. B is done. Wait for A's ingest/normalize/classify/retrieve, then wire everything together.**

### Updated requirements from the video:

In addition to the original 252-column output, the pipeline must now also write:

1. **`RETAIL_DESC`** — already produced by `build_all()` (5th key), write it to the `RETAIL_DESC` column
2. **`MARKETING_DESCRIPTION`** — use `enriched.marketing_description` (from manufacturer source only); write to the `MARKETING_DESCRIPTION` column; leave blank if `None`
3. **`ITEM_FEATURES_1` through `ITEM_FEATURES_20`** — use `enriched.item_features` list; write each feature to `ITEM_FEATURES_1`, `ITEM_FEATURES_2`, etc. (up to 20); leave remainder blank

```python
import csv, json, os, sys, argparse
from models import CleanRow

def load_real_headers() -> list[str]:
    """Load from sample_data/real_output_headers.json — 252 headers in exact order."""

def build_output_row(row: CleanRow, headers: list[str]) -> dict[str, str]:
    """
    1. out = {h: "" for h in headers}
    2. classify(row) → classification
    3. enrich(row)   → enriched
    4. build_all(enriched, row.manufacturer_name) → descs (5 keys now)
    5. Populate columns — see rules below
    6. assert all(isinstance(v, str) for v in out.values())
    7. return out
    """

def run(input_path: str, output_path: str, limit: int | None = None) -> None: ...

if __name__ == "__main__":
    # argparse: --limit N, --input, --output
```

**Column population rules:**

| Condition | Columns |
|-----------|---------|
| Always | `Mfg_Part_Num`, `Part_Desc`, `E1_Brand`, `Unilog_Brand`, `DIB_Brand`, `Part_Manuf`, `MANUFACTURER_NAME`, `MANUFACTURER_PART_NUMBER`, `BRAND_NAME`, `INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, `LONG_DESC1`, `RETAIL_DESC` |
| `classification.found == True` | `Dept`, `Class`, `Fine`, `Classpath` |
| `enriched.mfr_url is not None` | `MFR URL` |
| `enriched.ref_urls` has entries | `Ref URL 1` … `Ref URL 5` |
| `enriched.marketing_description is not None` | `MARKETING_DESCRIPTION` |
| `enriched.item_features` has entries | `ITEM_FEATURES_1` … `ITEM_FEATURES_20` (up to 20, sequential) |
| Each FOUND attribute | `ATTRIBUTE_LABEL N`, `ATTRIBUTE_VALUE N`, `ATTRIBUTE_UOM N` (sequential, no gaps) |
| Everything else | `""` |

**Critical:** `ATTRIBUTE_VALUE N` = plain number (`"75"`), `ATTRIBUTE_UOM N` = unit (`"W"`). NOT `"75 W"` in value.

Smoke test:
```bash
python3 src/pipeline.py --limit 5
# Verify: output_demo.csv has 5 rows + header, 252 columns, no None values
```

---

## Person D — Evaluation + Streamlit UI + Tests

**You own:** `sample_data/eval_set.csv`, `src/evaluate.py`, `app.py`, `tests/`

### Updated requirement from the video: Dynamic CSV upload ⚠️ CRITICAL

**Evaluators will upload their own CSV. A static demo that only works on your sample data will be penalised.**

`app.py` must have TWO tabs:
1. **Demo tab** — your pre-loaded `input_slice.csv` with SKU dropdown (existing design)
2. **Upload tab** — `st.file_uploader` accepting any correctly-shaped 6-column CSV, runs the full pipeline on the uploaded data, shows results, and offers a downloadable 252-column output CSV

```python
import streamlit as st
import pandas as pd
import io

tab1, tab2 = st.tabs(["Demo", "Upload Your Own CSV"])

with tab1:
    # Existing SKU dropdown + enrichment display

with tab2:
    uploaded = st.file_uploader("Upload a 6-column product CSV", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        # Validate columns: Mfg_Part_Num, Part_Desc, E1_Brand, Unilog_Brand, DIB_Brand, Part_Manuf
        # Run pipeline on each row
        # Show results table
        # st.download_button to download the 252-column output CSV
```

### File 1: `sample_data/eval_set.csv`

Schema: `mfg_part_num,attribute_label,expected_value,expected_uom,notes`

For `565374` and `586875`: read values from the `.txt` source files.
For 8 other rows: read directly from `Part_Desc` in `input_slice.csv`.

Value format: `"75"` not `"75W"`, `"2700"` not `"2700K"`, `"E26"` not `"e26"`.
Set `expected_value=""` for attributes not found (genuinely BLANK is expected).

### File 2: `src/evaluate.py`

```python
def load_eval_set(path: str) -> dict: ...
def run_eval(output_csv: str = "output_demo.csv", eval_csv: str = "sample_data/eval_set.csv") -> None:
    # Load output CSV, reconstruct attributes from ATTRIBUTE_LABEL N / ATTRIBUTE_VALUE N
    # Score: correct / unsupported_claim / miss
    # Print: total, correct, unsupported, misses, accuracy %
    # Exit 0 always

if __name__ == "__main__":
    run_eval()
```

### File 3: `tests/`

```bash
mkdir -p tests && touch tests/__init__.py tests/conftest.py
```

**CRITICAL in `tests/test_properties.py`:**
```python
import os
os.environ.pop("XAI_API_KEY", None)  # MUST be first line — never call live API in tests
```

Property tests to implement (see `src/models.py` for reference):
- `parse_wattage(f"{N}W")` → `f"{N} W"` for N 1–9999
- `parse_cct(f"{N}k")` → `f"{N*100} K"` for N 20–79
- `parse_pack_qty(f"{N}pk")` → `str(N)` for N 1–999
- `enrich(row)` always returns exactly 7 attributes (XAI_API_KEY unset)
- `build_output_row(row, headers)` → 252 string-valued keys
- `build_invoice_desc(...)` → ALL CAPS, `len ≤ 40`

Run:
```bash
python3 -m pytest tests/ -v
```

---

## Interface Summary

| Person | Output | Consumed by |
|--------|--------|-------------|
| A | `CleanRow`, `Classification`, normalize functions, `retrieve()` | B (already wired), C |
| B ✅ | `EnrichedRow`, `build_all()` → 5 descriptions, `marketing_description`, `item_features` | C, D |
| C | `output_demo.csv` | D (evaluate.py) |
| D | Eval numbers, upload UI, test results | Everyone (pitch deck) |

---

## Schedule

| Day | A | B | C | D |
|-----|---|---|---|---|
| 16 Aug (Sat) | ingest + normalize + classify | **DONE** | pipeline structure | eval_set.csv |
| 17 Aug (Sun) | retrieve (live search) | support bugs | full CSV output | evaluate.py + app.py (upload tab) |
| 18 Aug (Mon) | Done | Done | integration smoke test | property tests |
| 19 Aug (Tue) | support | support | full pipeline run + numbers | final UI check |
| 20 Aug | README + Solution Brief Overview |
| 21 Aug | Deck + screenshots |
| 22 Aug | Demo video |
| **23 Aug** | **Submit by 11:59 PM IST** |
