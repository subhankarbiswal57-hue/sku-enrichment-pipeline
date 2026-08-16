# Team Split — SKU Enrichment Pipeline
### UniHack 2026 | 4 People | Deadline: 23 Aug 2026, 11:59 PM IST

---

## ✅ Shared Setup — DONE

The foundation is built. Everyone can start immediately.

What's already in the repo:
- `src/__init__.py` — package marker (empty)
- `src/models.py` — all shared dataclasses (`CleanRow`, `Attribute`, `Classification`, `EnrichedRow`, `make_found_attr`, `make_blank_attr`, `ATTRIBUTE_LABELS`)
- `sample_data/input_slice.csv` — 228 Lighting rows filtered from the real 1,000-row input
- `sample_data/curated_sources/manifest.json` — 2 real Philips manufacturer pages
- `sample_data/curated_sources/046677589233_philips.txt` — Philips 75W A19 E26 ×4
- `sample_data/curated_sources/046677586874_philips.txt` — Philips 60W A19 E26 ×4

Verify it works on your machine:
```bash
cd /Users/shazam/Downloads/sku-enrichment-pipeline
python3 scripts/test_models.py
```
Expected output: `All models OK.`

---

## The Standard Import

Every file you write starts with:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# or if running from project root:
sys.path.insert(0, 'src')

from models import CleanRow, Attribute, Classification, EnrichedRow
from models import make_found_attr, make_blank_attr, ATTRIBUTE_LABELS
```

---

## Person A — Data Pipeline Core

**You own:** `src/ingest.py`, `src/normalize.py`, `src/classify.py`, `src/retrieve.py`

**Person B needs your work to proceed. Aim to finish by end of Day 1 (16 Aug).**

### How to start

```bash
cd /Users/shazam/Downloads/sku-enrichment-pipeline
open src/ingest.py        # start here
```

Delete the existing stub content and rewrite from scratch using the spec.

---

### File 1: `src/ingest.py`

**What it does:** Load the 6-column input CSV, filter placeholder brand values to `None`, parse the manufacturer code out of `Part_Manuf`.

**Key things to implement:**

```python
from models import CleanRow

PLACEHOLDER_VALUES = frozenset({
    "-- Unbranded --",
    "-- No Unilog Brand --",
    "-- No DIB Brand --",
})

MANUF_CODE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$")

def clean_brand(v: str) -> str | None:
    # Return None if v is placeholder, empty, or whitespace-only
    # Else return v.strip()

def parse_manufacturer(raw: str) -> tuple[str | None, str | None]:
    # "Phillips Lighting (5831)" -> ("Phillips Lighting", "5831")
    # "Some Vendor"             -> ("Some Vendor", None)
    # ""                        -> (None, None)

def load_and_clean(path: str) -> list[CleanRow]:
    # Raises IOError if file not found
    # Raises ValueError naming any missing column from the 6 required
    # Returns list[CleanRow] in input order
```

**Test it:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from ingest import load_and_clean
rows = load_and_clean('sample_data/input_slice.csv')
print(len(rows), 'rows loaded')
print(rows[0])
"
```

---

### File 2: `src/normalize.py`

**What it does:** Parse wattage, color temperature, pack quantity, and base type directly from a `Part_Desc` string using regex.

**Key things to implement:**

```python
# All return str | None. Return None if pattern absent — never invent a value.

def parse_wattage(desc: str) -> str | None:
    # "75W Led A19" -> "75 W"   (one space, uppercase W)

def parse_cct(desc: str) -> str | None:
    # "27k 4pk" -> "2700 K"    (multiply 2-digit by 100, one space, uppercase K)

def parse_pack_qty(desc: str) -> str | None:
    # "4pk" -> "4"              (plain number string, no unit)

def parse_base_type(desc: str) -> str | None:
    # "Med" -> "E26"
    # "Cand" -> "E12"
    # None if not found
```

**Regex patterns to use:**
```python
WATTAGE_RE = re.compile(r"(?<![A-Za-z])(\d+)\s*[wW]\b")
CCT_RE     = re.compile(r"\b([2-7]\d)[kK]\b")
PACK_RE    = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)
BASE_TYPE_MAP = {
    "med": "E26", "medium": "E26", "e26": "E26", "e27": "E26",
    "cand": "E12", "candelabra": "E12",
}
```

**Test it:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from normalize import parse_wattage, parse_cct, parse_pack_qty, parse_base_type
desc = '565374 75W Led A19 Med 27k 4pk'
print(parse_wattage(desc))   # 75 W
print(parse_cct(desc))       # 2700 K
print(parse_pack_qty(desc))  # 4
print(parse_base_type(desc)) # E26
"
```

---

### File 3: `src/classify.py`

**What it does:** Assign `Dept`, `Class`, `Fine`, `Classpath` to a row using keyword rules on `Part_Desc`.

**Key things to implement:**

```python
from models import CleanRow, Classification

BULB_SHAPE_RE = re.compile(
    r"\b(A19|A15|ST19|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|T12|T9|T8)\b",
    re.IGNORECASE,
)

def classify(row: CleanRow) -> Classification:
    # Priority order (check in this order, stop at first match):
    # 1. "strip"   -> Lighting & Ceiling Fans > Light Fixtures > LED Strip Lights
    # 2. "led" OR bulb shape match -> Lighting & Ceiling Fans > Light Bulbs > LED Bulbs
    # 3. "flor", "sodium", "halogen", "lamp", "bulb", "highbay", "downlight", "pendant"
    #              -> Lighting & Ceiling Fans > Light Bulbs > Light Bulbs
    # 4. No match  -> dept="", cls="", fine="", classpath="", found=False
    #
    # Classpath format: "Dept>Class>Fine"  (single >, no spaces around it)
    # When found=False: all fields are "" (NOT "UNKNOWN")
```

**Test it:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from ingest import load_and_clean
from classify import classify
rows = load_and_clean('sample_data/input_slice.csv')
for r in rows[:5]:
    c = classify(r)
    print(r.mfg_part_num, '->', c.classpath, '| found:', c.found)
"
```

---

### File 4: `src/retrieve.py`

**What it does:** Look up a pre-fetched manufacturer page by part number using `manifest.json`.

**Key things to implement:**

```python
import json, os, logging

CURATED_DIR = os.path.join(os.path.dirname(__file__), '..', 'sample_data', 'curated_sources')
_MANIFEST: dict | None = None   # loaded once, cached

def _load_manifest() -> dict:
    # Load manifest.json once. On IOError/JSONDecodeError: log warning, return {}

def retrieve(mfg_part_num: str) -> dict | None:
    # Returns {"source_url": str, "source_text": str} if found
    # Returns None if not in manifest, or any file read error
    # NEVER raises — all errors are logged as warnings
```

**Test it:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from retrieve import retrieve
r = retrieve('565374')
print('565374:', r['source_url'] if r else 'NOT FOUND')
r2 = retrieve('999999')
print('999999:', r2)
"
```

---

## Person B — Attribute Extraction + Descriptions

**You own:** `src/enrich.py`, `src/describe.py`

**Depends on Person A's normalize.py and retrieve.py. You can stub those locally until A is done.**

### How to start

```bash
cd /Users/shazam/Downloads/sku-enrichment-pipeline
open src/enrich.py        # start here
```

---

### File 1: `src/enrich.py`

**What it does:** Combine Part_Desc parsing (4 attributes) + manufacturer source extraction (3 attributes) into one `EnrichedRow` with exactly 7 attributes.

**Key things to implement:**

```python
import os, json, re, logging
import urllib.request
from models import CleanRow, EnrichedRow, Attribute, make_found_attr, make_blank_attr, ATTRIBUTE_LABELS

XAI_API_KEY = os.environ.get("XAI_API_KEY")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
MODEL       = "grok-4"

LUMENS_RE    = re.compile(r"(\d{3,5})\s*lm", re.IGNORECASE)
LIFE_RE      = re.compile(r"(\d{3,6})\s*h(?:our|r)?\b", re.IGNORECASE)
DIMMABLE_RE  = re.compile(r"\bdimm", re.IGNORECASE)

def _deterministic_attributes(row: CleanRow) -> list[Attribute]:
    # Call parse_wattage, parse_cct, parse_pack_qty, parse_base_type from normalize.py
    # IMPORTANT: store numeric value and unit SEPARATELY
    #   wattage: value="75", uom="W"   (NOT value="75 W")
    #   cct:     value="2700", uom="K" (NOT value="2700 K")
    #   pack:    value="4", uom=None
    #   base:    value="E26", uom=None
    # confidence=High if found, Low if None
    # evidence_note="Part_Desc" for all four
    # Returns exactly 4 Attributes in order: Wattage, CCT, Pack Quantity, Base Type

def _fallback_extract_from_source(source_text: str, source_url: str) -> list[Attribute]:
    # Use LUMENS_RE, LIFE_RE, DIMMABLE_RE on source_text
    # confidence=Medium if found, Low if not
    # evidence_note=source_url for found attrs, "no source" for blank
    # Returns exactly 3 Attributes: Lumens, Rated Life, Dimmable

def _llm_extract_from_source(source_text: str, source_url: str) -> list[Attribute]:
    # POST to Grok API, parse JSON response
    # Coerce: int -> str, True -> "Yes", False/null -> None
    # Wrap ENTIRE function in try/except — on ANY error return 3 blank attrs + log warning
    # Returns exactly 3 Attributes: Lumens, Rated Life, Dimmable

def enrich(row: CleanRow) -> EnrichedRow:
    # 1. _deterministic_attributes(row) -> 4 attrs
    # 2. retrieve(row.mfg_part_num) -> source dict or None
    # 3. If source found: _llm_extract or _fallback -> 3 attrs
    #    If no source: 3 blank attrs with evidence_note="no source"
    # 4. Return EnrichedRow with exactly 7 attrs in ATTRIBUTE_LABELS order
    # Assert: assert len(result.attributes) == 7
```

**IMPORTANT — never call the API in tests.** Always unset the key when testing:
```bash
XAI_API_KEY="" python3 -c "
import sys; sys.path.insert(0, 'src')
from ingest import load_and_clean
from enrich import enrich
rows = {r.mfg_part_num: r for r in load_and_clean('sample_data/input_slice.csv')}
result = enrich(rows['565374'])
print('Attrs:', [(a.label, a.value, a.state) for a in result.attributes])
print('MFR URL:', result.mfr_url)
"
```

---

### File 2: `src/describe.py`

**What it does:** Generate the 4 description fields using only FOUND attributes (value is not None).

**Lighting-specific formats:**

| Field | Format | Example |
|-------|--------|---------|
| `INVOICE_DESC` | `LED BULB <W>W <Base> <Qty>PK` ALL CAPS ≤40 chars | `LED BULB 75W E26 4PK` |
| `MOBILE_DESC` | `<Brand>, LED Bulb, <W> W, <CCT> K, <Base>, <Qty>-Pack` | `Philips, LED Bulb, 75 W, 2700 K, E26, 4-Pack` |
| `SHORT_DESC` | `<Brand> <MPN> LED Bulb, <W> W, <Base> Base, <CCT> K, <Lumens> lm, <Qty>-Pack` | `Philips 565374 LED Bulb, 75 W, E26 Base, 2700 K, 800 lm, 4-Pack` |
| `LONG_DESC1` | comma-separated, fixed attr order, BLANK attrs skipped | `Philips LED Bulb, 75 W, 2700 K, 800 lm, 10950 h, E26 Base, 4-Pack, Dimmable` |

```python
from models import EnrichedRow

def _found(attributes, label: str) -> str | None:
    # Return value of first FOUND attribute matching label, else None

def build_invoice_desc(enriched: EnrichedRow, manufacturer_name: str) -> str: ...
def build_mobile_desc(enriched: EnrichedRow, manufacturer_name: str) -> str: ...
def build_short_desc(enriched: EnrichedRow, manufacturer_name: str) -> str: ...
def build_long_desc(enriched: EnrichedRow, manufacturer_name: str) -> str: ...

def build_all(enriched: EnrichedRow, manufacturer_name: str) -> dict[str, str]:
    # Returns exactly: {"INVOICE_DESC": ..., "MOBILE_DESC": ..., "SHORT_DESC": ..., "LONG_DESC1": ...}
    # All values are str, never None
```

**Rules:**
- BLANK attributes (value is None) are silently omitted — no placeholder text
- `INVOICE_DESC` ≤ 40 chars — truncate to last full word if needed
- `manufacturer_name` fallback: use `"Unknown Brand"` if None
- If all 7 attrs are BLANK: `INVOICE_DESC=""`, `SHORT_DESC=""`, `LONG_DESC1=""`, `MOBILE_DESC=manufacturer_name or ""`

---

## Person C — Pipeline Orchestration + Output CSV

**You own:** `src/pipeline.py`

**Depends on A and B being done. You can start by writing the structure and stubbing the stage calls.**

### How to start

```bash
cd /Users/shazam/Downloads/sku-enrichment-pipeline
open src/pipeline.py
```

---

### File: `src/pipeline.py`

**What it does:** Orchestrate all stages and write the 252-column output CSV.

```python
import csv, json, os, sys, argparse
from models import CleanRow, EnrichedRow

def load_real_headers() -> list[str]:
    # Load from sample_data/real_output_headers.json
    # This is the authoritative column list — 252 headers in exact order

def build_output_row(row: CleanRow, headers: list[str]) -> dict[str, str]:
    # 1. Init: out = {h: "" for h in headers}
    # 2. Call classify(row) -> classification
    # 3. Call enrich(row)   -> enriched
    # 4. Call build_all(enriched, row.manufacturer_name) -> descs
    # 5. Populate columns (see rules below)
    # 6. assert all(isinstance(v, str) for v in out.values())
    # 7. return out

def run(input_path: str, output_path: str, limit: int | None = None) -> None:
    # Load headers once
    # Load and clean rows from input_path
    # Apply limit if given
    # Write CSV with csv.DictWriter(extrasaction='raise')
    # Print "Written N rows to output_demo.csv"
    # On write failure: print to stderr, sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--input",  default="sample_data/input_slice.csv")
    parser.add_argument("--output", default="output_demo.csv")
    args = parser.parse_args()
    run(args.input, args.output, args.limit)
```

**Column population rules:**

| Condition | Columns to populate |
|-----------|-------------------|
| Always | `Mfg_Part_Num`, `Part_Desc`, `E1_Brand`, `Unilog_Brand`, `DIB_Brand`, `Part_Manuf`, `MANUFACTURER_NAME`, `MANUFACTURER_PART_NUMBER`, `BRAND_NAME`, `INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, `LONG_DESC1` |
| `classification.found == True` | `Dept`, `Class`, `Fine`, `Classpath` |
| `enriched.mfr_url is not None` | `MFR URL` |
| `enriched.ref_urls` has entries | `Ref URL 1` … `Ref URL 5` |
| Each FOUND attribute (value is not None) | `ATTRIBUTE_LABEL N`, `ATTRIBUTE_VALUE N`, `ATTRIBUTE_UOM N` — sequential slots, no gaps |
| Everything else | Leave as `""` |

**Critical:** `ATTRIBUTE_VALUE N` = plain number e.g. `"75"`, `ATTRIBUTE_UOM N` = unit e.g. `"W"`. NOT `"75 W"` in value.

**Smoke test:**
```bash
python3 src/pipeline.py --limit 5
# Verify: output_demo.csv has 5 data rows + header, 252 columns, no None values
```

---

## Person D — Evaluation + Streamlit UI + Tests

**You own:** `sample_data/eval_set.csv`, `src/evaluate.py`, `app.py`, `tests/`

**Can start eval_set.csv and app.py immediately. Tests need A and B done first.**

### How to start

```bash
cd /Users/shazam/Downloads/sku-enrichment-pipeline
# Start with the eval set — it's just CSV data entry
open sample_data/eval_set.csv   # create this file
```

---

### File 1: `sample_data/eval_set.csv`

**What it is:** Hand-verified ground truth for 10 Lighting SKUs. You look up the real values from the source files and Part_Desc strings.

**Schema:**
```
mfg_part_num,attribute_label,expected_value,expected_uom,notes
```

**How to fill it:**
- For `565374` and `586875`: open the `.txt` files in `sample_data/curated_sources/` and read the actual values
- For 8 other SKUs: read the value directly from `Part_Desc` in `sample_data/input_slice.csv`
- Value format must match what the pipeline produces: `"75"` not `"75W"`, `"2700"` not `"2700K"`, `"E26"` not `"e26"`
- If an attribute genuinely can't be verified: `expected_value=""` (blank = UNKNOWN is expected)

**Example rows:**
```csv
565374,Wattage,75,W,from Part_Desc: "75W"
565374,Color Temperature,2700,K,from Part_Desc: "27k"
565374,Pack Quantity,4,,from Part_Desc: "4pk"
565374,Base Type,E26,,from Part_Desc: "Med"
565374,Lumens,800,lm,from 046677589233_philips.txt
565374,Rated Life,10950,h,from 046677589233_philips.txt
565374,Dimmable,Yes,,from 046677589233_philips.txt
```

---

### File 2: `src/evaluate.py`

```python
import csv, sys

def load_eval_set(path: str) -> dict:
    # Returns {mfg_part_num: {attribute_label: {"expected_value": str, "expected_uom": str, "notes": str}}}

def run_eval(output_csv: str = "output_demo.csv", eval_csv: str = "sample_data/eval_set.csv") -> None:
    # Load output_csv, reconstruct {mfg_part_num: {label: value}} from ATTRIBUTE_LABEL N / ATTRIBUTE_VALUE N pairs
    # Compare against eval set
    # Score each pair: correct / unsupported_claim / miss
    # Print: total, correct, unsupported claims, misses, accuracy %
    # Print per-mismatch detail
    # Exit 0 always

if __name__ == "__main__":
    run_eval()
```

---

### File 3: `app.py` (Streamlit)

```bash
# Start by reading the existing app.py stub — keep the structure, fix the imports
open app.py
```

**Fix the import at the top:**
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from models import CleanRow, Attribute
from ingest import load_and_clean
from classify import classify
from enrich import enrich
from describe import build_all
```

**UI must show:**
1. Selectbox: `"<Mfg_Part_Num> — <Part_Desc>"`
2. Raw input as `st.json`
3. Classification badge: `st.success` if found, `st.info` if blank
4. MFR URL as clickable link or `st.warning` if none
5. Attributes table — amber row for BLANK, red row for FOUND+Low
6. 4 descriptions each with `(N chars)` count
7. Review Queue: FOUND + Medium confidence with evidence_note
8. `st.expander("Blank Attributes (N)")` for BLANK attrs
9. Footer caption: confidence is UI-only, not in the output CSV

**Run it:**
```bash
streamlit run app.py
```

---

### File 4: `tests/` (Property-Based Tests)

```bash
mkdir -p tests
touch tests/__init__.py
```

**`tests/conftest.py`:**
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
```

**`tests/test_properties.py`** — run with `XAI_API_KEY` unset:
```python
import os
os.environ.pop("XAI_API_KEY", None)  # MUST be at top — before any imports

from hypothesis import given, settings
import hypothesis.strategies as st

# Property 3: parse_wattage round-trip
@given(st.integers(min_value=1, max_value=9999))
def test_wattage_roundtrip(n):
    from normalize import parse_wattage
    assert parse_wattage(f"{n}W") == f"{n} W"

# Property 4: CCT expansion
@given(st.integers(min_value=20, max_value=79))
def test_cct_expansion(n):
    from normalize import parse_cct
    assert parse_cct(f"{n}k") == f"{n * 100} K"

# Property 6: enrich always returns 7 attrs (no API call)
@given(st.text(min_size=1, max_size=50))
def test_enrich_always_7(part_desc):
    from ingest import CleanRow
    from enrich import enrich
    row = CleanRow("TEST", part_desc, None, None, None, "Test Brand", None)
    result = enrich(row)
    assert len(result.attributes) == 7

# ... (properties 1, 2, 5, 7, 8, 9 from design.md)
```

**Run tests:**
```bash
python3 -m pytest tests/ -v
```

---

## Interface Summary

| Person | Outputs | Consumed by |
|--------|---------|------------|
| A | `CleanRow` via `load_and_clean()`, `Classification` via `classify()`, normalize functions, `retrieve()` | B, C |
| B | `EnrichedRow` via `enrich()`, descriptions via `build_all()` | C, D (app.py) |
| C | `output_demo.csv` | D (evaluate.py) |
| D | Eval numbers, UI demo, test pass/fail | Everyone (pitch deck) |

---

## Schedule

| Day | A | B | C | D |
|-----|---|---|---|---|
| 16 Aug (Sat) | ingest + normalize | enrich structure + deterministic attrs | pipeline structure | eval_set.csv |
| 17 Aug (Sun) | classify + retrieve | enrich complete + describe | output CSV working | evaluate.py + app.py |
| 18 Aug (Mon) | Done | Done | Integration smoke test | Property tests |
| 19 Aug (Tue) | Support bugs | Support bugs | Full pipeline run | Final UI check |
| 20 Aug | README + Solution Brief Overview |
| 21 Aug | Deck + screenshots |
| 22 Aug | Demo video |
| **23 Aug** | **Submit by 11:59 PM IST** |
