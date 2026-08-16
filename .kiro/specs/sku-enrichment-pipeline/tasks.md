# Implementation Plan: SKU Enrichment Pipeline

## Overview

Build the SKU Enrichment Pipeline from scratch using the two Unilog-provided files as ground truth:
- Input: `docs/Unihack_ Sample Dataset - Input (1).csv` (1,000 real rows)
- Ground truth: `docs/Unihack_ Expected Output - Delivery Format (1).csv` (Frigidaire and Whirlpool worked examples)

Every format, casing, UOM, and description decision is anchored to those two worked examples. The existing `src/` stubs are discarded — we write clean implementations from the spec. Category: Lighting (Phillips, Kichler, Satco rows). Deadline: 23 Aug 2026 11:59 PM IST.

## Tasks

- [ ] 1. Prepare sample data — slice input to Lighting rows and set up curated sources
  - Read `docs/Unihack_ Sample Dataset - Input (1).csv` and filter to Lighting rows: keep rows where `Part_Manuf` contains `Phillips Lighting`, `Kichler Lighting`, or `Satco Prod`, or where `Part_Desc` contains any of `Led`, `Flor`, `Bulb`, `Light`, `Lamp`, `Strip`, `Halogen`, `Sodium` (case-insensitive)
  - Write the filtered rows to `sample_data/input_slice.csv` with the same 6-column header (`Mfg_Part_Num,Part_Desc,E1_Brand,Unilog_Brand,DIB_Brand,Part_Manuf`)
  - Verify the slice contains 50–200 rows and that representative SKUs from Phillips Lighting are present
  - Verify `sample_data/curated_sources/manifest.json` exists and its `source_url` values are manufacturer domain URLs (not Amazon, eBay, or distributor sites)
  - Verify the two `.txt` source files referenced by the manifest exist and contain readable product page text
  - **Requirement refs:** 3.1, 3.4, 11.4

- [ ] 2. Implement `src/ingest.py` — ingestion and placeholder cleansing
  - Define `CleanRow` dataclass with fields: `mfg_part_num: str`, `part_desc: str`, `e1_brand: str | None`, `unilog_brand: str | None`, `dib_brand: str | None`, `manufacturer_name: str | None`, `manufacturer_code: str | None`
  - Define `PLACEHOLDER_VALUES = frozenset({"-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --"})`
  - Implement `clean_brand(v: str) -> str | None` — returns `None` if `v` stripped is empty or in `PLACEHOLDER_VALUES`, else returns stripped `v`
  - Implement `parse_manufacturer(raw: str) -> tuple[str | None, str | None]` using regex `r"^(?P<name>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*$"` — returns `(name.strip(), code)` on match, `(raw.strip(), None)` if no code, `(None, None)` if empty/whitespace
  - Implement `load_and_clean(path: str) -> list[CleanRow]` — raises `IOError` if file cannot be opened, raises `ValueError` naming missing column(s) if any of the 6 required columns absent, otherwise returns list of `CleanRow` in input order
  - Manually verify with a few rows from `sample_data/input_slice.csv` that placeholders become `None` and `Part_Manuf` like `"Phillips Lighting (5831)"` parses to `("Phillips Lighting", "5831")`
  - **Requirement refs:** 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8

- [ ] 3. Implement `src/normalize.py` — deterministic attribute parsing from Part_Desc
  - Define regex patterns: `WATTAGE_RE = re.compile(r"(?<![A-Za-z])(\d+)\s*[wW]\b")`, `CCT_RE = re.compile(r"\b([2-7]\d)[kK]\b")`, `PACK_RE = re.compile(r"(\d+)\s*pk\b", re.IGNORECASE)`
  - Define `BASE_TYPE_MAP = {"med": "E26", "medium": "E26", "e26": "E26", "e27": "E26", "cand": "E12", "candelabra": "E12"}`
  - Implement `parse_wattage(desc: str) -> str | None` — returns `"<N> W"` (e.g. `"75 W"`) or `None`
  - Implement `parse_cct(desc: str) -> str | None` — returns `"<NNN0> K"` (e.g. `"2700 K"`) or `None`; multiply the two-digit match by 100
  - Implement `parse_pack_qty(desc: str) -> str | None` — returns plain numeric string (e.g. `"4"`) or `None`
  - Implement `parse_base_type(desc: str) -> str | None` — splits `Part_Desc` on whitespace and checks each word (lowercased) against `BASE_TYPE_MAP`; returns canonical code or `None`
  - All returned unit strings must have exactly one space between the number and unit abbreviation — matching ground truth style `"120 V"`, `"15 A"`, `"47 dBA"`
  - Test manually: `"565374 75W Led A19 Med 27k 4pk"` → wattage=`"75 W"`, cct=`"2700 K"`, pack=`"4"`, base=`"E26"`
  - **Requirement refs:** 4.1, 4.2, 4.3, 4.4, 4.5, 4.6

- [ ] 4. Implement `src/classify.py` — keyword-based taxonomy classification
  - Define `Classification` dataclass with fields: `dept: str`, `cls: str`, `fine: str`, `classpath: str`, `found: bool`
  - Define `BULB_SHAPE_RE = re.compile(r"\b(A19|A15|ST19|MR16|R20|R14|PAR20|PAR30|PAR38|BR30|BR40|G25|T12|T9|T8)\b", re.IGNORECASE)`
  - Implement `classify(row: CleanRow) -> Classification` with priority order: (1) `strip` → `Lighting & Ceiling Fans>Light Fixtures>LED Strip Lights`; (2) `led` OR bulb shape match → `Lighting & Ceiling Fans>Light Bulbs>LED Bulbs`; (3) `flor`, `sodium`, `halogen`, `lamp`, `bulb`, `highbay`, `downlight`, or `pendant` (case-insensitive) → `Lighting & Ceiling Fans>Light Bulbs>Light Bulbs`; (4) no match → all fields `""`, `found=False`
  - Classpath must use single `>` delimiter with no spaces around it — matching ground truth format exactly
  - When no signal found, all four fields (`dept`, `cls`, `fine`, `classpath`) are empty string `""` — NOT the string `"UNKNOWN"`
  - Test manually: `"75W Led A19 Med 27k 4pk"` → `found=True`, `fine="LED Bulbs"`, `classpath="Lighting & Ceiling Fans>Light Bulbs>LED Bulbs"`
  - **Requirement refs:** 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7

- [ ] 5. Implement `src/retrieve.py` — curated source manifest lookup
  - Load `sample_data/curated_sources/manifest.json` once at module level into a `_MANIFEST` variable (not on every call)
  - Implement `retrieve(mfg_part_num: str) -> dict | None` — returns `{"source_url": str, "source_text": str}` if part number is in manifest AND source file is readable; returns `None` in all other cases
  - Wrap all file I/O in try/except — on any `IOError` or `json.JSONDecodeError`, log a warning with `logging.warning(...)` and return `None`; never raise
  - Validate that manifest `source_url` values do not contain marketplace domains (`amazon.`, `ebay.`, `homedepot.`, `lowes.`, `grainger.`) — log a warning for any violation found at load time
  - **Requirement refs:** 3.1, 3.2, 3.3, 3.4, 3.5

- [ ] 6. Implement `src/enrich.py` — attribute assembly combining Part_Desc parsing and source extraction
  - Define `Attribute` dataclass with fields: `label: str`, `value: str | None`, `uom: str | None`, `confidence: Literal["High", "Medium", "Low"]`, `evidence_note: str`; add `@property state` returning `"FOUND"` if `value is not None` else `"BLANK"`; add `__post_init__` that raises `ValueError` if `confidence` not in `("High", "Medium", "Low")`
  - Define `EnrichedRow` dataclass with fields: `mfg_part_num: str`, `part_desc: str`, `mfr_url: str | None`, `ref_urls: list[str]`, `attributes: list[Attribute]`
  - Define `XAI_API_KEY = os.environ.get("XAI_API_KEY")`, `XAI_API_URL = "https://api.x.ai/v1/chat/completions"`, `MODEL = "grok-4"`
  - Implement `_deterministic_attributes(row: CleanRow) -> list[Attribute]` — calls `parse_wattage`, `parse_cct`, `parse_pack_qty`, `parse_base_type`; for each, stores the numeric part as `value` and the unit abbreviation as `uom` separately (e.g. wattage value=`"75"`, uom=`"W"` — NOT value=`"75 W"`); confidence=`"High"` if value found, `"Low"` if `None`; returns exactly 4 Attributes in order: Wattage, Color Temperature, Pack Quantity, Base Type
  - Implement `_fallback_extract_from_source(source_text: str) -> list[Attribute]` — regex-based extraction of lumens, rated life hours, dimmable from source text; confidence=`"Medium"` if found, `"Low"` if not; returns exactly 3 Attributes: Lumens, Rated Life, Dimmable
  - Implement `_llm_extract_from_source(source_text: str) -> list[Attribute]` — POST to Grok API with system prompt instructing JSON response `{"lumens": int|null, "rated_life_hours": int|null, "dimmable": bool|null}`; coerce integer values to `str`; coerce `True` → `"Yes"`, `False`/`null` → `None`; wrap entire function in try/except catching `URLError`, `TimeoutError`, `json.JSONDecodeError`, `KeyError` — on any error return 3 BLANK Attributes with `confidence="Low"` and log the error
  - Implement `enrich(row: CleanRow) -> EnrichedRow` — calls deterministic parsing → retrieval → LLM or fallback extraction; always returns `EnrichedRow` with exactly 7 Attributes in fixed order: Wattage, Color Temperature, Pack Quantity, Base Type, Lumens, Rated Life, Dimmable
  - Add assertion `assert len(result.attributes) == 7` at end of `enrich()`
  - **Requirement refs:** 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6

- [ ] 7. Implement `src/describe.py` — generate four description formats from FOUND attributes only
  - Implement helper `_found(attributes: list[Attribute], label: str) -> str | None` — returns first attribute value where `label` matches and `value is not None`, else `None`
  - Implement `build_invoice_desc(enriched: EnrichedRow, manufacturer_name: str) -> str` — ALL CAPS, ≤40 chars; format: `LED BULB <Wattage>W <BaseType> <PackQty>PK`; only include a component if the corresponding attribute is FOUND; truncate to last full word within 40 chars if needed. Example: `"LED BULB 75W E26 4PK"`
  - Implement `build_mobile_desc(enriched: EnrichedRow, manufacturer_name: str) -> str` — brand-led, sentence case; format: `"<Brand>, LED Bulb, <Wattage> W, <CCT> K, <BaseType>, <PackQty>-Pack"`; omit any component whose attribute is BLANK; fallback to `manufacturer_name or ""` if all blank. Example: `"Philips, LED Bulb, 75 W, 2700 K, E26, 4-Pack"`
  - Implement `build_short_desc(enriched: EnrichedRow, manufacturer_name: str) -> str` — format: `"<Brand> <MPN> LED Bulb, <Wattage> W, <BaseType> Base, <CCT> K, <Lumens> lm, <PackQty>-Pack"`; omit BLANK attributes. Example: `"Philips 565374 LED Bulb, 75 W, E26 Base, 2700 K, 800 lm, 4-Pack"`
  - Implement `build_long_desc(enriched: EnrichedRow, manufacturer_name: str) -> str` — comma-separated spec list, all FOUND attributes in fixed order: Wattage → Color Temperature → Lumens → Rated Life → Base Type → Pack Quantity → Dimmable; BLANK attrs silently omitted; UOM appended with space per ground truth style. Example: `"Philips LED Bulb, 75 W, 2700 K, 800 lm, 10950 h, E26 Base, 4-Pack, Dimmable"`
  - Implement `build_all(enriched: EnrichedRow, manufacturer_name: str) -> dict[str, str]` — returns dict with exactly keys `"INVOICE_DESC"`, `"MOBILE_DESC"`, `"SHORT_DESC"`, `"LONG_DESC1"`; all values are `str` (never `None`)
  - **Requirement refs:** 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7

- [ ] 8. Implement `src/pipeline.py` — orchestrate all stages and write 252-column output CSV
  - Implement `load_real_headers() -> list[str]` — load from `sample_data/real_output_headers.json`
  - Implement `build_output_row(row: CleanRow, headers: list[str]) -> dict[str, str]` — init all 252 headers to `""`; run classify → retrieve → enrich → describe; populate columns per the rules in the design (see Column population rules table); note that `ATTRIBUTE_VALUE` stores the numeric value only (e.g. `"75"`) and `ATTRIBUTE_UOM` stores the unit (e.g. `"W"`) separately — matching ground truth attribute format; assert all 252 values are `str`; return the dict
  - Implement `run(input_path: str, output_path: str, limit: int | None = None) -> None` — load headers once; load and clean rows; apply limit; write CSV with `csv.DictWriter(extrasaction='raise')`; print `"Written N rows to output_demo.csv"`; on output file write failure print to stderr and `sys.exit(1)`
  - Add `if __name__ == "__main__":` block using `argparse` with `--limit N` optional argument; default input path `sample_data/input_slice.csv`, default output path `output_demo.csv`
  - Add `src/__init__.py` (empty) so the package is importable as `python -m src.pipeline`
  - Fix all imports in `src/*.py` to use relative imports (`from .ingest import ...`) for package usage, with `sys.path` fallback in `__main__` blocks for direct script execution
  - Run smoke test: `python src/pipeline.py --limit 5` — verify `output_demo.csv` has 5 data rows, 252 columns, no `None` values, header row matches `real_output_headers.json`
  - **Requirement refs:** 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 12.1, 12.2, 12.3, 12.4, 12.5

- [ ] 9. Build `sample_data/eval_set.csv` and implement `src/evaluate.py`
  - Hand-verify attributes for at least 10 Lighting SKUs from `sample_data/input_slice.csv` following manufacturer-only sourcing rules: for the 2 curated-source SKUs read values from the `.txt` source files; for others verify Wattage/CCT/Pack Qty/Base Type directly from `Part_Desc`
  - Write `sample_data/eval_set.csv` with columns: `mfg_part_num,attribute_label,expected_value,expected_uom,notes`; use same value format the pipeline produces (e.g. `"75"` not `"75W"`, `"2700"` not `"2700K"`, `"E26"` not `"e26"`); set `expected_value=""` for attributes that are genuinely unknown (no source, not in Part_Desc)
  - Implement `load_eval_set(path: str) -> dict` — returns `{mfg_part_num: {attribute_label: {"expected_value": str, "expected_uom": str, "notes": str}}}`
  - Implement `run_eval(output_csv: str, eval_csv: str) -> None` — load output CSV, reconstruct attribute map from `ATTRIBUTE_LABEL N`/`ATTRIBUTE_VALUE N` pairs, compare against eval set using scoring rules (correct/unsupported-claim/miss), print summary and per-mismatch detail, exit 0
  - Run: `python src/evaluate.py` — verify it completes without error and prints accuracy stats
  - **Requirement refs:** 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7

- [ ] 10. Implement `app.py` — Streamlit review UI
  - Use `sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))` before imports so the `src/` modules are importable when running `streamlit run app.py`
  - Load and cache input slice with `@st.cache_data`; populate `st.selectbox` with `"<Mfg_Part_Num> — <Part_Desc>"` for each row
  - On SKU selection, run all pipeline stages in-process (do not read from `output_demo.csv`)
  - Display in two columns: (left) raw input as `st.json`, classification badge (`st.success` FOUND / `st.info` blank); (right) MFR URL as clickable link or `st.warning` if none, attributes table as styled DataFrame
  - Apply row styling to attributes table: BLANK attributes → amber background `#fff3cd`; FOUND + Low confidence → red background `#ffe0e0`; FOUND + High/Medium → no highlight
  - Below the columns: show all four descriptions each with `(N chars)` count next to the label
  - Show "Review Queue" section listing FOUND + Medium/Low confidence attributes with their `evidence_note`
  - Show `st.expander("Blank Attributes (N)")` listing all BLANK attributes
  - Add `st.caption` footer: confidence and review flags are UI-only and not written to the 252-column output CSV
  - Run `streamlit run app.py` manually and verify: dropdown populates, selecting a curated-source SKU shows a clickable MFR URL and populated attributes, selecting a non-curated SKU shows the warning and only Part_Desc-derived attributes
  - **Requirement refs:** 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7

- [ ] 11. Add property-based tests with Hypothesis
  - Add `hypothesis>=6.100,<7` and `pytest>=8.0,<9` to `requirements.txt`
  - Create `tests/__init__.py` and `tests/conftest.py` with `sys.path` setup
  - Create `tests/test_properties.py` with Hypothesis `@given` tests for:
    - Property 1: `parse_manufacturer` round-trip — `f"{name} ({code})"` → `(name.strip(), code)`
    - Property 2: `clean_brand` on any of the three placeholder strings returns `None`
    - Property 3: `parse_wattage(f"{N}W")` returns `f"{N} W"` for any integer N 1–9999
    - Property 4: `parse_cct(f"{N}k")` returns `f"{N*100} K"` for any two-digit N 20–79
    - Property 5: `parse_pack_qty(f"{N}pk")` returns `str(N)` for any integer N 1–999
    - Property 6: `enrich(row)` always returns exactly 7 attributes in fixed label order — **CRITICAL: set `XAI_API_KEY` to `None` in the test environment (using `monkeypatch.delenv` or `os.environ.pop`) before running this property test so Hypothesis never calls the live Grok API; the fallback/no-source path is exercised instead**
    - Property 7: `build_output_row(row, headers)` returns dict with exactly 252 string-valued keys
    - Property 8: `build_invoice_desc` result is ALL CAPS and `len <= 40`
    - Property 9: for any `Attribute` with `state == "FOUND"` produced by `_deterministic_attributes`, its `evidence_note` equals `"Part_Desc"` — confirming no attribute is labelled as coming from a marketplace/distributor URL
  - Create `tests/test_unit.py` with example-based tests using real Part_Desc strings from the input slice (e.g. `"565374 75W Led A19 Med 27k 4pk"`)
  - Run `python -m pytest tests/ -v` and fix any failures
  - **Requirement refs:** Design Correctness Properties 1–9

- [ ] 12. Final integration check and requirements.txt update
  - Update `requirements.txt`: `streamlit>=1.38,<2`, `pandas>=2.2,<3`, `hypothesis>=6.100,<7`, `pytest>=8.0,<9`
  - Run full pipeline on all Lighting rows: `python src/pipeline.py` → verify `output_demo.csv` has correct row count, 252 columns, all string values, no extra columns
  - Run evaluator: `python src/evaluate.py` → verify accuracy stats print and no unhandled exceptions
  - Run `streamlit run app.py` and do a final manual check of the full UI flow
  - Verify output CSV matches ground truth format by comparing a sample row against the Frigidaire/Whirlpool examples: check `INVOICE_DESC` is ALL CAPS ≤40 chars, `ATTRIBUTE_VALUE` columns contain plain numeric values (not `"75 W"`), `ATTRIBUTE_UOM` contains the unit, `MFR URL` is populated for curated-source SKUs
  - **Requirement refs:** All

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": [1] },
    { "wave": 2, "tasks": [2, 3, 4, 5] },
    { "wave": 3, "tasks": [6] },
    { "wave": 4, "tasks": [7] },
    { "wave": 5, "tasks": [8] },
    { "wave": 6, "tasks": [9, 10] },
    { "wave": 7, "tasks": [11] },
    { "wave": 8, "tasks": [12] }
  ]
}
```

Tasks 2, 3, 4, 5 can run in parallel after Task 1 completes. Tasks 9 and 10 can run in parallel after Task 8 completes.

## Notes

- The two Unilog ground truth rows (Frigidaire PDSH4816AF, Whirlpool WDTS7024RZ) in `docs/Unihack_ Expected Output - Delivery Format (1).csv` are the single authoritative reference. When in doubt about any format decision, check those rows first.
- `ATTRIBUTE_VALUE` in the output CSV must store the plain numeric value (`"75"`, `"2700"`) NOT the formatted string with unit (`"75 W"`). The unit goes in `ATTRIBUTE_UOM`. This is confirmed by the ground truth: `ATTRIBUTE_VALUE 4 = "120"`, `ATTRIBUTE_UOM 4 = "V"` for the Voltage Rating attribute.
- The existing `src/` stub files contain AI-generated code that may conflict with this spec. Read the spec, not the stubs, when implementing.
- `XAI_API_KEY` controls LLM vs regex fallback. All tasks must work and be testable without it set.
- The 252-column header list in `sample_data/real_output_headers.json` is authoritative. Never modify it.
- Deadline: 23 August 2026, 11:59 PM IST. Tasks 1–8 are the critical path.
