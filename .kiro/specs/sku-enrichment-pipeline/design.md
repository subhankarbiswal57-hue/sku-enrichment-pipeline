# Design Document — SKU Enrichment Pipeline

## Overview

A linear enrichment pipeline for UniHack 2026 that turns minimal 6-column product rows into 252-column Unilog delivery format records. The two ground-truth rows in `docs/Unihack_ Expected Output - Delivery Format (1).csv` (Frigidaire PDSH4816AF and Whirlpool WDTS7024RZ) are the single source of truth for all format, casing, UOM style, and description construction decisions.

**Three steps done convincingly with evidence** (per the Solution Guide's explicit instruction to pick 2–3 steps and do them well):
1. Taxonomy & Classification → `Dept`, `Class`, `Fine`, `Classpath`
2. Attribute Extraction + Enrichment from manufacturer sources → `ATTRIBUTE_LABEL/VALUE/UOM` slots, `MFR URL`, `Ref URL 1–5`
3. Description Building → `SHORT_DESC`, `LONG_DESC1`, `MOBILE_DESC`, `INVOICE_DESC`

Ingestion/cleansing and normalization support all three. Evaluation and a Streamlit review UI complete the submission package.

Category: **Lighting** — Phillips Lighting (~111 rows), Kichler (~56), Satco (~41) from the real 1,000-row input. Strongest volume + standardizable attribute set.

Tech: Python 3.11, xAI Grok API (`grok-4`), Streamlit, Pandas.

---

## Architecture

### Data Flow

```
docs/Unihack_ Sample Dataset - Input (1).csv  →  filter to Lighting  →  sample_data/input_slice.csv
                                                                                    │
                                                                                    ▼
                                                                          [src/ingest.py]
                                                                      Filter placeholders, parse
                                                                      manufacturer code
                                                                                    │
                                                                                    ▼
                                                                         [src/classify.py]
                                                                      Dept / Class / Fine / Classpath
                                                                      (keyword rules on Part_Desc)
                                                                                    │
                                                                                    ▼
                                                                         [src/retrieve.py]
                                                                      Look up curated manufacturer
                                                                      page by mfg_part_num
                                                                                    │
                                                                                    ▼
                                                              [src/normalize.py] ──► [src/enrich.py]
                                                              Deterministic parsing    Grok API or
                                                              from Part_Desc           regex fallback
                                                              (wattage, CCT,           over source text
                                                              pack qty, base type)     (lumens, rated
                                                                                       life, dimmable)
                                                                                    │
                                                                                    ▼
                                                                         [src/describe.py]
                                                                      INVOICE_DESC / MOBILE_DESC /
                                                                      SHORT_DESC / LONG_DESC1
                                                                      (FOUND attributes only)
                                                                                    │
                                                                                    ▼
                                                                         [src/pipeline.py]
                                                                      Assemble 252-column output row
                                                                      using real headers from
                                                                      sample_data/real_output_headers.json
                                                                                    │
                                                                                    ▼
                                                                          output_demo.csv
                                                                                    │
                                                                                    ▼
                                                                            [app.py]
                                                                      Streamlit UI — confidence/
                                                                      review shown here only
```

### Module Responsibility Summary

| File | Responsibility |
|------|----------------|
| `src/ingest.py` | Load CSV, filter placeholder brands, parse manufacturer code |
| `src/classify.py` | Keyword-based Dept/Class/Fine/Classpath assignment |
| `src/retrieve.py` | Curated source manifest lookup |
| `src/normalize.py` | Deterministic regex parsing of Part_Desc attributes |
| `src/enrich.py` | Combine Part_Desc attributes + LLM/regex source extraction → 7 Attributes |
| `src/describe.py` | Generate 4 description fields from FOUND attributes only |
| `src/pipeline.py` | Orchestrate all stages, write 252-column output CSV, CLI |
| `src/evaluate.py` | Score output against eval_set.csv |
| `app.py` | Streamlit review UI |

---

## Data Models

### `CleanRow`

```python
@dataclass
class CleanRow:
    mfg_part_num: str           # stripped, never None
    part_desc: str              # stripped, never None
    e1_brand: str | None        # None if placeholder or empty
    unilog_brand: str | None    # None if placeholder or empty
    dib_brand: str | None       # None if placeholder or empty
    manufacturer_name: str | None   # None if Part_Manuf is empty
    manufacturer_code: str | None   # alphanumeric code, e.g. "5831"
```

### `Attribute`

The central data contract. State and confidence are separate concerns. State is derived from value; confidence reflects how the value was obtained.

```python
@dataclass
class Attribute:
    label: str                          # e.g. "Wattage"
    value: str | None                   # None means not found (BLANK state)
    uom: str | None                     # e.g. "W", "K", "lm" — None if no unit
    confidence: Literal["High", "Medium", "Low"]
    evidence_note: str                  # "Part_Desc" for deterministic attrs;
                                        # source URL for LLM/regex attrs;
                                        # "no source" for BLANK attrs

    # Derived from value — not stored:
    @property
    def state(self) -> Literal["FOUND", "BLANK"]:
        return "FOUND" if self.value is not None else "BLANK"

    def __post_init__(self):
        if self.confidence not in ("High", "Medium", "Low"):
            raise ValueError(f"Invalid confidence: {self.confidence!r}")
        # Enforce: BLANK state must have Low confidence
        if self.value is None and self.confidence != "Low":
            raise ValueError(
                f"Attribute '{self.label}': BLANK state requires confidence='Low', got {self.confidence!r}"
            )
```

**Valid combinations:**

| `value` | `state` | `confidence` | `evidence_note` | valid? |
|---------|---------|-------------|-----------------|--------|
| non-empty str | FOUND | High | `"Part_Desc"` | ✓ — confirmed from Part_Desc |
| non-empty str | FOUND | Medium | `"https://..."` | ✓ — confirmed from manufacturer page |
| None | BLANK | Low | `"no source"` or `"not in Part_Desc"` | ✓ — not found anywhere |
| None | BLANK | High or Medium | any | ✗ — constructor raises |

**UI review queue logic:** Show in review queue when `state == "FOUND" AND confidence == "Medium"` (i.e. sourced from manufacturer page — worth a human check). High-confidence attributes from Part_Desc do not need review. BLANK attributes appear in the separate "Blank Attributes" section.

### `Classification`

```python
@dataclass
class Classification:
    dept: str           # empty string if not classified
    cls: str            # empty string if not classified
    fine: str           # empty string if not classified
    classpath: str      # empty string if not classified
    found: bool         # True when at least one signal was matched
```

### `EnrichedRow`

```python
@dataclass
class EnrichedRow:
    mfg_part_num: str
    part_desc: str
    mfr_url: str | None          # manufacturer page URL, or None
    ref_urls: list[str]          # up to 5 additional reference URLs
    attributes: list[Attribute]  # always exactly 7, in fixed order
```

**Fixed attribute order (positions 1–7 in ATTRIBUTE_LABEL/VALUE/UOM slots):**

| # | Label | Source |
|---|-------|--------|
| 1 | Wattage | Part_Desc |
| 2 | Color Temperature | Part_Desc |
| 3 | Pack Quantity | Part_Desc |
| 4 | Base Type | Part_Desc |
| 5 | Lumens | Manufacturer source |
| 6 | Rated Life | Manufacturer source |
| 7 | Dimmable | Manufacturer source |

---

## Components and Interfaces

The pipeline is composed of 8 modules, each with a single responsibility. They are called in sequence by `pipeline.py`. All modules are in `src/` and importable as a package.

| Component | File | Interface |
|-----------|------|-----------|
| Ingestor | `src/ingest.py` | `load_and_clean(path) -> list[CleanRow]` |
| Classifier | `src/classify.py` | `classify(row: CleanRow) -> Classification` |
| Retriever | `src/retrieve.py` | `retrieve(mfg_part_num: str) -> dict \| None` |
| Normalizer | `src/normalize.py` | `parse_wattage`, `parse_cct`, `parse_pack_qty`, `parse_base_type` — each `(desc: str) -> str \| None` |
| Enricher | `src/enrich.py` | `enrich(row: CleanRow) -> EnrichedRow` |
| DescriptionBuilder | `src/describe.py` | `build_all(enriched, manufacturer_name) -> dict[str, str]` |
| Pipeline | `src/pipeline.py` | `run(input_path, output_path, limit=None)`, `build_output_row(row, headers) -> dict[str, str]` |
| Evaluator | `src/evaluate.py` | `run_eval(output_csv, eval_csv) -> None` |

All data flows forward — no back-edges between stages. `pipeline.py` calls each stage in sequence for every input row.

---

## Module Designs

### `src/ingest.py`

```python
PLACEHOLDER_VALUES = frozenset({
    "-- Unbranded --",
    "-- No Unilog Brand --",
    "-- No DIB Brand --",
})

MANUF_CODE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$")

def clean_brand(v: str) -> str | None:
    """Return None if v is a placeholder, empty, or whitespace-only. Else return stripped v."""

def parse_manufacturer(raw: str) -> tuple[str | None, str | None]:
    """
    'Phillips Lighting (5831)' -> ('Phillips Lighting', '5831')
    'Some Vendor'             -> ('Some Vendor', None)
    ''                        -> (None, None)
    """

def load_and_clean(path: str) -> list[CleanRow]:
    """
    Load CSV. Raises IOError if file unreadable.
    Raises ValueError naming missing column(s) if any of the 6 required
    columns are absent.
    Returns list of CleanRow.
    """
```

### `src/classify.py`

Classification rules derived from the Lighting slice of the real input and the Frigidaire/Whirlpool classpath format from the ground truth (`Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers`).

```python
# Priority order for keyword matching:
# 1. strip  → Lighting & Ceiling Fans > Light Fixtures > LED Strip Lights
# 2. led / bulb shape → Lighting & Ceiling Fans > Light Bulbs > LED Bulbs
# 3. flor / sodium / halogen / lamp / bulb / highbay → Lighting & Ceiling Fans > Light Bulbs > Light Bulbs
# 4. no match → all fields empty string, found=False
# Note: "light" alone is too broad (matches non-lighting rows) — use only with other signals

BULB_SHAPE_RE = re.compile(
    r"\b(A19|A15|ST19|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|T12|T9|T8)\b",
    re.IGNORECASE,
)

LIGHTING_GENERIC_KEYWORDS = {"flor", "sodium", "halogen", "lamp", "bulb", "highbay", "downlight", "pendant", "sconce"}

def classify(row: CleanRow) -> Classification:
    ...
```

**Dataset filter vs classifier alignment:** The dataset filter uses broad keywords (`Led`, `Flor`, `Bulb`, `Light`, `Lamp`, `Strip`, `Halogen`, `Sodium`) to select Lighting rows for the input slice. The classifier recognises all of these (except bare "Light" which is too broad) so virtually all rows in the slice will be classified. Rows that pass the filter but are not classified (e.g. lighting *fixtures* that don't say "strip", "led", "flor" etc.) will have blank taxonomy — this is correct behavior per Requirement 2.6.

**Classpath format:** single `>` delimiter, no spaces around it, matching ground truth exactly.

**UNKNOWN vs blank:** When no signal is found, `Dept`, `Class`, `Fine`, `Classpath` are all empty string `""` — NOT the string `"UNKNOWN"`. The ground truth has blank cells, not "UNKNOWN" cells.

### `src/retrieve.py`

```python
# Manifest schema: sample_data/curated_sources/manifest.json
# {
#   "<mfg_part_num>": {
#     "source_file": "<filename>.txt",
#     "source_url": "https://<manufacturer-domain>/..."
#   }
# }
# Only manufacturer domain URLs permitted.

def retrieve(mfg_part_num: str) -> dict | None:
    """
    Returns {"source_url": str, "source_text": str} or None.
    Never raises — returns None on any I/O error, logs a warning.
    Loads manifest once and caches at module level.
    """
```

### `src/normalize.py`

Patterns reverse-engineered from the ground truth UOM style:
- `"120 V"`, `"15 A"`, `"47 dBA"`, `"24 in"`, `"24-1/4 in"`, `"50-1/4 in"` — always one space between number and unit

```python
WATTAGE_RE   = re.compile(r"(?<![A-Za-z])(\d+)\s*[wW]\b")
CCT_RE       = re.compile(r"\b([2-7]\d)[kK]\b")   # 2-digit shorthand, valid range 20–79
PACK_RE      = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)
BASE_TYPE_MAP = {
    "med": "E26", "medium": "E26", "e26": "E26", "e27": "E26",
    "cand": "E12", "candelabra": "E12",
}

def parse_wattage(desc: str) -> str | None:   # "75W" → "75 W"
def parse_cct(desc: str) -> str | None:       # "27k" → "2700 K"
def parse_pack_qty(desc: str) -> str | None:  # "4pk" → "4"
def parse_base_type(desc: str) -> str | None: # "Med" → "E26", "Cand" → "E12"
```

**Unit formatting invariant:** exactly one space between number and unit. No `"75W"`, no `"75  W"`.

### `src/enrich.py`

```python
XAI_API_KEY = os.environ.get("XAI_API_KEY")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
MODEL       = "grok-4"

SYSTEM_PROMPT = (
    "Extract product attributes from the manufacturer page text below. "
    "Return ONLY a JSON object: "
    '{\"lumens\": <integer or null>, \"rated_life_hours\": <integer or null>, '
    '\"dimmable\": <true/false/null>}. '
    "Use null for anything not explicitly stated — never guess."
)

def enrich(row: CleanRow) -> EnrichedRow:
    """
    1. Run normalize.py parsers on Part_Desc → 4 deterministic Attributes
    2. Call retrieve(mfg_part_num)
    3. If source found:
       - If XAI_API_KEY set: call Grok API → 3 source Attributes
       - Else: run regex fallback over source_text → 3 source Attributes
    4. If no source: all 3 source Attributes have value=None, confidence=Low
    5. Always return EnrichedRow with exactly 7 Attributes in fixed order
    """
```

**Grok API error handling:** wrap the entire API call in try/except catching `URLError`, `TimeoutError`, `json.JSONDecodeError`, `KeyError`. On any failure → log warning, set all 3 source attributes to `value=None, confidence=Low`. Never propagate the exception.

**Value coercion:** Grok returns integers for lumens/rated_life_hours. Convert to `str` before storing. Boolean `True` for dimmable → `"Yes"`. `False` or `null` → `None`.

### `src/describe.py`

All four description formats are defined concretely for the Lighting category, using the 7 available attributes (Wattage, Color Temperature, Pack Quantity, Base Type, Lumens, Rated Life, Dimmable) plus `manufacturer_name` and `mfg_part_num`. The Frigidaire/Whirlpool ground truth examples establish the structural pattern (brand-led, comma-separated, UOM style); the specific field values come from Lighting attributes.

| Field | Lighting format | Example |
|-------|----------------|---------|
| `INVOICE_DESC` | `LED BULB <Wattage>W <BaseType> <PackQty>PK`, ALL CAPS, ≤40 chars | `LED BULB 75W E26 4PK` |
| `MOBILE_DESC` | `<Brand>, LED Bulb, <Wattage> W, <CCT> K, <BaseType>, <PackQty>-Pack`, sentence case | `Philips, LED Bulb, 75 W, 2700 K, E26, 4-Pack` |
| `SHORT_DESC` | `<Brand> <MPN> LED Bulb, <Wattage> W, <BaseType> Base, <CCT> K, <Lumens> lm, <PackQty>-Pack` | `Philips 565374 LED Bulb, 75 W, E26 Base, 2700 K, 800 lm, 4-Pack` |
| `LONG_DESC1` | `<Brand> LED Bulb, <Wattage> W, <CCT> K, <Lumens> lm, <RatedLife> h, <BaseType> Base, <PackQty>-Pack, Dimmable` | `Philips LED Bulb, 75 W, 2700 K, 800 lm, 10950 h, E26 Base, 4-Pack, Dimmable` |

BLANK attributes (value is None) are silently omitted from all formats. UOM values use one space between number and unit (matching ground truth: `"75 W"`, `"2700 K"`).

```python
def build_all(row: EnrichedRow, manufacturer_name: str) -> dict[str, str]:
    """Returns {"INVOICE_DESC": ..., "MOBILE_DESC": ..., "SHORT_DESC": ..., "LONG_DESC1": ...}
    All four values are str, never None."""
```

### `src/pipeline.py`

```python
def load_real_headers() -> list[str]:
    """Load from sample_data/real_output_headers.json"""

def build_output_row(row: CleanRow, headers: list[str]) -> dict[str, str]:
    """
    1. Init all 252 headers to ""
    2. Run all stages: classify → retrieve → enrich → describe
    3. Populate fields per column population rules below
    4. Assert all values are str (never None)
    5. Return the dict — use extrasaction='raise' when writing
    """

def run(input_path: str, output_path: str, limit: int | None = None) -> None:
    """Write output_demo.csv. Print 'Written N rows to output_demo.csv'."""
```

**Column population rules:**

| Condition | Columns populated |
|-----------|------------------|
| Always | `Mfg_Part_Num`, `Part_Desc`, `E1_Brand`, `Unilog_Brand`, `DIB_Brand`, `Part_Manuf`, `MANUFACTURER_NAME`, `MANUFACTURER_PART_NUMBER`, `BRAND_NAME`, `INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, `LONG_DESC1` |
| classification.found == True | `Dept`, `Class`, `Fine`, `Classpath` |
| mfr_url is not None | `MFR URL` |
| ref_urls has entries | `Ref URL 1` … `Ref URL 5` (up to 5) |
| attribute.value is not None (FOUND) | `ATTRIBUTE_LABEL N`, `ATTRIBUTE_VALUE N`, `ATTRIBUTE_UOM N` (sequential, no gaps) |
| Everything else | Left as `""` |

### `src/evaluate.py`

```python
def load_eval_set(path: str) -> dict[str, dict[str, str]]:
    """
    Load sample_data/eval_set.csv
    Schema: mfg_part_num, attribute_label, expected_value, expected_uom, notes
    Returns: {mfg_part_num: {attribute_label: expected_value}}
    """

def run_eval(output_csv: str, eval_csv: str) -> None:
    """
    Compare pipeline output (from output_demo.csv) against eval_set.csv.
    Print: total pairs, correct, unsupported claims, misses, accuracy %.
    Print per-mismatch detail when mismatches exist.
    Exit 0 always.
    """
```

### `app.py` (Streamlit)

Layout (2-column):
```
[Title + caption]
[st.selectbox — "<Mfg_Part_Num> — <Part_Desc>"]

col1                              col2
─────────────────────────         ─────────────────────────
1. Raw Input (st.json)            3. Retrieved Source (link or warning)
2. Classification badge           4. Attributes table (styled)
   FOUND (green) / blank (grey)      FOUND=white, FOUND+Low=red bg,
                                     BLANK=amber bg

[5. Generated Descriptions — each with (N chars) count]
[6. Review Queue — FOUND Medium/Low with evidence note]
[7. st.expander "Blank Attributes (N)"]
[caption: confidence is UI-only, not in output CSV]
```

The UI runs the pipeline stages in-process on the selected SKU — it does **not** read from `output_demo.csv`.

---

## Key Algorithms

### Classification Priority

```python
desc_lower = row.part_desc.lower()

if "strip" in desc_lower:
    → Lighting & Ceiling Fans > Light Fixtures > LED Strip Lights

elif "led" in desc_lower or BULB_SHAPE_RE.search(row.part_desc):
    → Lighting & Ceiling Fans > Light Bulbs > LED Bulbs

elif "flor" in desc_lower or "sodium" in desc_lower:
    → Lighting & Ceiling Fans > Light Bulbs > Light Bulbs

else:
    → dept="", cls="", fine="", classpath="", found=False
```

### Attribute Slot Assembly (no gaps)

```python
found_attrs = [a for a in enriched.attributes if a.value is not None]
for i, attr in enumerate(found_attrs[:50], start=1):
    out[f"ATTRIBUTE_LABEL {i}"] = attr.label
    out[f"ATTRIBUTE_VALUE {i}"] = attr.value
    out[f"ATTRIBUTE_UOM {i}"]   = attr.uom or ""
```

Slots not populated stay as `""`. Slot numbering is always sequential (1, 2, 3…) — gaps only exist if fewer than 50 attributes are found.

### Grok API Request

```python
payload = {
    "model": "grok-4",
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": source_text},
    ],
    "max_tokens": 300,
}
headers = {
    "Authorization": f"Bearer {XAI_API_KEY}",
    "Content-Type": "application/json",
}
# POST to https://api.x.ai/v1/chat/completions
# Parse response["choices"][0]["message"]["content"] as JSON
```

---

## Curated Source Manifest Schema

**File:** `sample_data/curated_sources/manifest.json`

```json
{
  "<mfg_part_num>": {
    "source_file": "<filename relative to curated_sources/>",
    "source_url": "https://<manufacturer-domain>/..."
  }
}
```

Keys are the `Mfg_Part_Num` values as they appear in `input_slice.csv`. Only manufacturer domain URLs are permitted — no Amazon, eBay, Home Depot, Grainger, or distributor URLs.

## Correctness Properties

For property-based testing with Hypothesis. Each property is a formal statement about system behavior that must hold for all valid inputs.

### Property 1: Manufacturer parse round-trip

For any non-empty name string and alphanumeric code, `parse_manufacturer(f"{name} ({code})")` returns `(name.strip(), code)` exactly.

**Validates: Requirements 1.3**

### Property 2: Placeholder brand normalisation

For any of the three placeholder strings (`-- Unbranded --`, `-- No Unilog Brand --`, `-- No DIB Brand --`) and for any whitespace-only string, `clean_brand(v)` returns `None`. For any non-empty non-placeholder string, it returns the stripped input.

**Validates: Requirements 1.2**

### Property 3: Wattage parse round-trip

For any positive integer N in 1–9999, `parse_wattage(f"{N}W")` returns `f"{N} W"`.

**Validates: Requirements 4.1**

### Property 4: Color temperature expansion

For any two-digit integer N in 20–79, `parse_cct(f"{N}k")` returns `f"{N * 100} K"`.

**Validates: Requirements 4.2**

### Property 5: Pack quantity round-trip

For any positive integer N in 1–999, `parse_pack_qty(f"{N}pk")` returns `str(N)`.

**Validates: Requirements 4.3**

### Property 6: EnrichedRow always has exactly 7 attributes in fixed order

For any `CleanRow` input (with or without a curated source), `enrich(row)` returns an `EnrichedRow` whose `attributes` list has exactly 7 elements with labels in the fixed order: Wattage, Color Temperature, Pack Quantity, Base Type, Lumens, Rated Life, Dimmable.

**Validates: Requirements 6.1**

### Property 7: Output row has exactly 252 string-valued keys

For any `CleanRow` processed by `build_output_row(row, headers)`, the returned dict has exactly 252 keys matching `real_output_headers.json` and every value is a `str` (never `None`).

**Validates: Requirements 8.1, 8.2**

### Property 8: INVOICE_DESC is always ALL CAPS and at most 40 characters

For any `EnrichedRow` and any manufacturer name, `build_invoice_desc` returns a string where every alphabetic character is uppercase and `len(result) <= 40`.

**Validates: Requirements 7.1**

### Property 9: No invented values from non-manufacturer sources

For any attribute with a non-None value in the pipeline output, its `evidence_note` does not reference a marketplace or distributor domain.

**Validates: Requirements 11.2**

---

## Error Handling

| Location | Condition | Behaviour |
|----------|-----------|-----------|
| `load_and_clean` | File not found | Raise `IOError` with path |
| `load_and_clean` | Missing column | Raise `ValueError` naming column |
| `retrieve` | Manifest or source file unreadable | Return `None`, log warning |
| `_llm_extract_from_source` | Network/timeout/JSON error | Return 3× BLANK attributes, log warning |
| `pipeline.run` | Output file unwritable | Print to stderr, `sys.exit(1)` |
| `build_output_row` | Key outside 252 headers | Raise immediately (extrasaction='raise') |

---

## Testing Strategy

**Property-Based Testing (Hypothesis):** The pure parsing functions (`normalize.py`, `ingest.py`) have clear input/output contracts ideal for PBT. Run with minimum 100 examples per property.

**Unit Tests:** Example-based tests using real Part_Desc strings from `sample_data/input_slice.csv`. Cover known patterns and known edge cases (e.g. `"27k"` vs `"5CCT"`).

**Integration Tests:** End-to-end smoke test running `pipeline.run` on the full input slice and checking:
1. Output CSV has correct column count (252)
2. All values are strings
3. No `None` values in any cell
4. Curated-source SKUs have `MFR URL` populated
5. `ATTRIBUTE_VALUE` columns contain plain numeric values (not formatted strings with units)

**Ground Truth Validation:** Compare generated descriptions and attributes for the two curated-source SKUs against their known manufacturer page content to confirm no hallucination.

Key format decisions locked to the Frigidaire/Whirlpool worked examples in `docs/Unihack_ Expected Output - Delivery Format (1).csv`:

| Decision | Ground Truth Evidence |
|----------|-----------------------|
| UOM style: space between number and unit | `"120 V"`, `"15 A"`, `"47 dBA"`, `"24 in"`, `"24-1/4 in"` |
| INVOICE_DESC: ALL CAPS, ≤40 chars | `"DISHWASHER LEG 5 SST 120V 15A 50-1/4IN"` (38 chars) |
| MOBILE_DESC: brand-led, ~60-80 chars | `"Rheem Manufacturing FRIGIDAIRE, Dishwasher, Professional Series, PDSH4816AF"` |
| Blank fields are empty string, not "N/A" or "Unknown" | UNSPSC, Country Of Origin, etc. are blank in ground truth |
| Classpath uses `>` delimiter, no spaces | `"Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers"` |
| Attribute values are plain — no unit embedded in VALUE | `ATTRIBUTE_VALUE = "120"`, `ATTRIBUTE_UOM = "V"` (not `"120 V"` in VALUE) |
| MFR URL: manufacturer site only | `"https://www.frigidaire.com/..."`, `"https://learnwhirlpool.com/..."` |
| Ref URLs: manuals and spec sheets from manufacturer domains | Whirlpool: owners manual PDF, installation guide PDF |

---

## Sample Data Preparation

**`sample_data/input_slice.csv`:** Filter `docs/Unihack_ Sample Dataset - Input (1).csv` to Lighting rows. Target: rows where `Part_Manuf` contains `"Phillips Lighting"`, `"Kichler Lighting"`, `"Satco Prod"`, or `Part_Desc` contains lighting keywords (`Led`, `Flor`, `Bulb`, `Light`, `Lamp`, `Strip`, `Halogen`, `Sodium`). Expected: ~150–200 rows.

**`sample_data/eval_set.csv`:** Hand-verify 10 Lighting rows following manufacturer-only sourcing rules. Schema: `mfg_part_num, attribute_label, expected_value, expected_uom, notes`. Use the same value format the pipeline produces: `"75"` not `"75W"`, `"2700"` not `"2700K"`.

---

## Correctness Properties (for Property-Based Testing)

| # | Property | Validates |
|---|----------|-----------|
| 1 | `parse_manufacturer(f"{name} ({code})")` → `(name.strip(), code)` | Req 1.3 |
| 2 | `clean_brand` on any placeholder string → `None` | Req 1.2 |
| 3 | `parse_wattage(f"{N}W")` → `f"{N} W"` for any N 1–9999 | Req 4.1 |
| 4 | `parse_cct(f"{N}k")` → `f"{N*100} K"` for any two-digit N in 20–79 | Req 4.2 |
| 5 | `parse_pack_qty(f"{N}pk")` → `str(N)` for any N 1–999 | Req 4.3 |
| 6 | `enrich(row)` always returns exactly 7 attributes in fixed label order | Req 6.1 |
| 7 | `build_output_row(row, headers)` returns exactly 252 string-valued keys | Req 8.1, 8.2 |
| 8 | `build_invoice_desc` result is ALL CAPS and `len ≤ 40` | Req 7.1 |
| 9 | No attribute value in output CSV comes from a marketplace/distributor URL | Req 11.2 |

---

## Error Handling Summary

| Location | Condition | Behaviour |
|----------|-----------|-----------|
| `load_and_clean` | File not found | Raise `IOError` with path |
| `load_and_clean` | Missing column | Raise `ValueError` naming column |
| `retrieve` | Manifest or source file unreadable | Return `None`, log warning |
| `_llm_extract_from_source` | Network/timeout/JSON error | Return 3× BLANK attributes, log warning |
| `pipeline.run` | Output file unwritable | Print to stderr, `sys.exit(1)` |
| `build_output_row` | Key outside 252 headers | Raise immediately (extrasaction='raise') |
