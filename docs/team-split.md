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
| `src/ingest.py` | ✅ Done | A | Cleans placeholders, parses mfg code, raises IOError/ValueError |
| `src/normalize.py` | ✅ Done | A | Deterministic wattage (W), CCT (K), pack qty, base type |
| `src/classify.py` | ✅ Done | A | Dept>Class>Fine priority taxonomy, returns Classification with found flag |
| `src/retrieve.py` | ✅ Done | A | Curated manifest cache + live DuckDuckGo fallback + marketplace blocking |
| `src/pipeline.py` | ✅ Done | C | Complete orchestration, wires A & B, outputs exact 252 delivery columns |
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

**Clone the repo (everyone):**

Mac/Linux:
```bash
git clone https://github.com/shazamcodes64/sku-enrichment-pipeline.git
cd sku-enrichment-pipeline
```

Windows (cmd):
```cmd
git clone https://github.com/shazamcodes64/sku-enrichment-pipeline.git
cd sku-enrichment-pipeline
```

**Install dependencies:**

Mac/Linux:
```bash
pip3 install -r requirements.txt
```

Windows (cmd):
```cmd
pip install -r requirements.txt
```

**Verify models work:**

Mac/Linux:
```bash
python3 scripts/test_models.py
```

Windows (cmd):
```cmd
python scripts\test_models.py
```

Expected output: `All models OK.`

---

## Standard Import

Every file you write starts with:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# or when running from project root:
sys.path.insert(0, 'src')

from models import CleanRow, Attribute, Classification, EnrichedRow
from models import make_found_attr, make_blank_attr, ATTRIBUTE_LABELS
```

---

## Person A — ✅ DONE

**`src/ingest.py`, `src/normalize.py`, `src/classify.py`, and `src/retrieve.py` are complete.**

**Verify — Mac/Linux:**
```bash
python3 -c "import sys; sys.path.insert(0,'src'); from ingest import load_and_clean; rows=load_and_clean('sample_data/input_slice.csv'); print('Ingest OK:', len(rows), 'rows')"
python3 -c "import sys; sys.path.insert(0,'src'); from normalize import parse_wattage,parse_cct,parse_pack_qty,parse_base_type; d='565374 75W Led A19 Med 27k 4pk'; print('Normalize OK:', parse_wattage(d), parse_cct(d), parse_pack_qty(d), parse_base_type(d))"
python3 -c "import sys; sys.path.insert(0,'src'); from classify import classify; from ingest import CleanRow; c=classify(CleanRow('565374','75W Led A19 Med 27k 4pk',None,None,None,'Phillips Lighting','5831')); print('Classify OK:', c.classpath, 'found=' + str(c.found))"
python3 -c "import sys; sys.path.insert(0,'src'); from retrieve import retrieve; r=retrieve('565374'); print('Retrieve OK:', r['source_url'] if r else 'NOT FOUND')"
```

**Verify — Windows (cmd):**
```cmd
python -c "import sys; sys.path.insert(0,'src'); from ingest import load_and_clean; rows=load_and_clean('sample_data/input_slice.csv'); print('Ingest OK:', len(rows), 'rows')"
python -c "import sys; sys.path.insert(0,'src'); from normalize import parse_wattage,parse_cct,parse_pack_qty,parse_base_type; d='565374 75W Led A19 Med 27k 4pk'; print('Normalize OK:', parse_wattage(d), parse_cct(d), parse_pack_qty(d), parse_base_type(d))"
python -c "import sys; sys.path.insert(0,'src'); from classify import classify; from ingest import CleanRow; c=classify(CleanRow('565374','75W Led A19 Med 27k 4pk',None,None,None,'Phillips Lighting','5831')); print('Classify OK:', c.classpath, 'found=' + str(c.found))"
python -c "import sys; sys.path.insert(0,'src'); from retrieve import retrieve; r=retrieve('565374'); print('Retrieve OK:', r['source_url'] if r else 'NOT FOUND')"
```

**What's done:**
- `src/ingest.py`: Filters placeholders (`-- Unbranded --`, `N/A`, `NULL`), parses manufacturer code e.g. `Phillips Lighting (5831)` $\rightarrow$ `("Phillips Lighting", "5831")`, validates 6 required headers and returns `list[CleanRow]`.
- `src/normalize.py`: Deterministic parsers for `Wattage` (`75 W`), `Color Temperature` (`2700 K`), `Pack Quantity` (`4`), and `Base Type` (`E26`).
- `src/classify.py`: 4-tier taxonomy priority (`strip` $\rightarrow$ `LED Strip Lights`, `led`/shape $\rightarrow$ `LED Bulbs`, generic $\rightarrow$ `Light Bulbs`, fallback $\rightarrow$ `""` with `found=False`).
- `src/retrieve.py`: Multi-tier source discovery (Tier 1 curated manifest fast-path + Tier 2 live DuckDuckGo search fallback) with strict marketplace domain rejection (`amazon.`, `ebay.`, `homedepot.`, `lowes.`, etc.) and HTML text cleaner.

---

### File 1: `src/ingest.py`

```python
from models import CleanRow

PLACEHOLDER_VALUES = frozenset({
    "-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --",
})
MANUF_CODE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$")

def clean_brand(v: str | None) -> str | None: ...
def parse_manufacturer(raw: str | None) -> tuple[str | None, str | None]: ...
def load_and_clean(path: str) -> list[CleanRow]: ...
# Raises IOError if file unreadable, ValueError naming missing columns
```

---

### File 2: `src/normalize.py`

```python
WATTAGE_RE  = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*[wW]\b")
CCT_RE      = re.compile(r"\b([2-7]\d)[kK]\b")
PACK_RE     = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)
BASE_TYPE_MAP = {"med":"E26","medium":"E26","e26":"E26","e27":"E26","cand":"E12","candelabra":"E12"}

def parse_wattage(desc: str) -> str | None:   # "75W" → "75 W"
def parse_cct(desc: str) -> str | None:       # "27k" → "2700 K"
def parse_pack_qty(desc: str) -> str | None:  # "4pk" → "4"
def parse_base_type(desc: str) -> str | None: # "Med" → "E26"
```

---

### File 3: `src/classify.py`

```python
from models import CleanRow, Classification

BULB_SHAPE_RE = re.compile(r"\b(A19|A15|ST19|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|T12|T9|T8)\b", re.IGNORECASE)

def classify(row: CleanRow) -> Classification:
    # Priority: strip → led/shape → flor/sodium/halogen/lamp/bulb/highbay/downlight/pendant → blank
    # Classpath: "Lighting & Ceiling Fans>Light Bulbs>LED Bulbs"  (single >, no spaces)
    # No match → all fields "", found=False  (NOT "UNKNOWN")
```

---

### File 4: `src/retrieve.py`

```python
# Architecture: curated cache (fast-path) + live DuckDuckGo search (fallback)
BLOCKED_DOMAINS = frozenset({"amazon.", "ebay.", "homedepot.", "grainger.", "lowes.", "walmart.", "tractorsupply."})

def retrieve(mfg_part_num: str, manufacturer_name: str | None = None) -> dict | None:
    # 1. Check curated manifest first
    # 2. If not found: DuckDuckGo search "<manufacturer> <part_num> specifications"
    # 3. Fetch first non-marketplace URL
    # 4. Return {"source_url": str, "source_text": str} or None
    # 5. NEVER raises — log warnings only
```

---

## Person B — ✅ DONE

**`src/enrich.py` and `src/describe.py` are complete.**

**Verify — Mac/Linux:**
```bash
python3 scripts/test_person_b.py
```

**Verify — Windows (cmd):**
```cmd
python scripts\test_person_b.py
```

Expected: `All assertions passed. Person B modules OK.`

**What's done:**
- 7 attributes in fixed order (Wattage, Color Temperature, Pack Quantity, Base Type, Lumens, Rated Life, Dimmable)
- FOUND/BLANK states, High/Medium/Low confidence, `is_novel_value` flag
- Grok API + regex fallback (no API key needed for testing)
- `marketing_description` and `item_features` from manufacturer source only
- 5 descriptions: INVOICE_DESC (≤40 chars ALL CAPS), MOBILE_DESC, SHORT_DESC, LONG_DESC1, RETAIL_DESC

---

## Person C — Pipeline Orchestration + Output CSV

**You own:** `src/pipeline.py`

**Depends on A (ingest/classify/retrieve) and B (done). Wire everything together.**

### Column population rules

| Condition | Columns |
|-----------|---------|
| Always | `Mfg_Part_Num`, `Part_Desc`, `E1_Brand`, `Unilog_Brand`, `DIB_Brand`, `Part_Manuf`, `MANUFACTURER_NAME`, `MANUFACTURER_PART_NUMBER`, `BRAND_NAME`, `INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, `LONG_DESC1`, `RETAIL_DESC` |
| `classification.found == True` | `Dept`, `Class`, `Fine`, `Classpath` |
| `enriched.mfr_url is not None` | `MFR URL` |
| `enriched.ref_urls` has entries | `Ref URL 1` … `Ref URL 5` |
| `enriched.marketing_description is not None` | `MARKETING_DESCRIPTION` |
| `enriched.item_features` has entries | `ITEM_FEATURES_1` … `ITEM_FEATURES_20` (up to 20) |
| Each FOUND attribute | `ATTRIBUTE_LABEL N`, `ATTRIBUTE_VALUE N`, `ATTRIBUTE_UOM N` (sequential, no gaps) |
| Everything else | `""` |

`ATTRIBUTE_VALUE N` = plain number (`"75"`), `ATTRIBUTE_UOM N` = unit (`"W"`). NOT `"75 W"` in value.

**Smoke test — Mac/Linux:**
```bash
python3 src/pipeline.py --limit 5
```

**Smoke test — Windows (cmd):**
```cmd
python src\pipeline.py --limit 5
```

Verify: `output_demo.csv` has 5 rows + header, 252 columns, no `None` values.

---

## Person D — Evaluation + Streamlit UI + Tests

**You own:** `sample_data/eval_set.csv`, `src/evaluate.py`, `app.py`, `tests/`

### app.py — TWO TABS REQUIRED ⚠️

```python
tab1, tab2 = st.tabs(["Demo", "Upload Your Own CSV"])

with tab1:
    # SKU dropdown + enrichment display (existing design)

with tab2:
    uploaded = st.file_uploader("Upload a 6-column product CSV", type="csv")
    if uploaded:
        # Run pipeline, show results, st.download_button for 252-col output CSV
```

**Run Streamlit — Mac/Linux:**
```bash
streamlit run app.py
```

**Run Streamlit — Windows (cmd):**
```cmd
streamlit run app.py
```

### eval_set.csv schema

```
mfg_part_num,attribute_label,expected_value,expected_uom,notes
565374,Wattage,75,W,from Part_Desc
565374,Color Temperature,2700,K,from Part_Desc
565374,Lumens,1100,lm,from 046677589233_philips.txt
...
```

Value format: `"75"` not `"75W"`, `"2700"` not `"2700K"`, `"E26"` not `"e26"`.

### Run evaluator

**Mac/Linux:**
```bash
python3 src/evaluate.py
```

**Windows (cmd):**
```cmd
python src\evaluate.py
```

### Run property tests

**Mac/Linux:**
```bash
pip3 install hypothesis pytest
python3 -m pytest tests/ -v
```

**Windows (cmd):**
```cmd
pip install hypothesis pytest
python -m pytest tests\ -v
```

**CRITICAL:** First line of `tests/test_properties.py` must be:
```python
import os; os.environ.pop("XAI_API_KEY", None)  # never call live API in tests
```

### Create tests directory

**Mac/Linux:**
```bash
mkdir -p tests && touch tests/__init__.py tests/conftest.py
```

**Windows (cmd):**
```cmd
mkdir tests
type nul > tests\__init__.py
type nul > tests\conftest.py
```

---

## Interface Summary

| Person | Output | Consumed by |
|--------|--------|-------------|
| A ✅ | `CleanRow`, `Classification`, normalize functions, `retrieve()` | B (already wired), C |
| B ✅ | `EnrichedRow`, `build_all()` → 5 descriptions, `marketing_description`, `item_features` | C, D |
| C | `output_demo.csv` | D (evaluate.py) |
| D | Eval numbers, upload UI, test results | Everyone (pitch deck) |

---

## Schedule

| Day | A | B | C | D |
|-----|---|---|---|---|
| 16 Aug (Sat) | ingest + normalize + classify | **DONE** | pipeline structure | eval_set.csv |
| 17 Aug (Sun) | retrieve (live search) | support bugs | full CSV output | evaluate.py + app.py upload tab |
| 18 Aug (Mon) | Done | Done | integration smoke test | property tests |
| 19 Aug (Tue) | support | support | full pipeline run + numbers | final UI check |
| 20 Aug | README + Solution Brief Overview |
| 21 Aug | Deck + screenshots |
| 22 Aug | Demo video |
| **23 Aug** | **Submit by 11:59 PM IST** |
