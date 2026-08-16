# Requirements Document

## Introduction

The SKU Enrichment Pipeline is a multi-stage data enrichment system for UniHack 2026 (Unilog). It takes the real 6-column minimal input CSV (`Mfg_Part_Num, Part_Desc, E1_Brand, Unilog_Brand, DIB_Brand, Part_Manuf`) and produces structured, commerce-ready output in the exact 252-column Unilog delivery format.

The two ground-truth rows in `docs/Unihack_ Expected Output - Delivery Format (1).csv` (Frigidaire PDSH4816AF and Whirlpool WDTS7024RZ) are the authoritative reference for correct output format, casing, UOM style, and description construction. Every design and implementation decision is validated against these rows first.

Scope: we implement three steps convincingly with evidence — **taxonomy & classification**, **attribute extraction + enrichment from manufacturer sources**, and **description building** — with ingestion/cleansing and normalization as supporting layers. The guide explicitly says depth beats breadth: one category done fully beats a thin pass over all 1,000 rows. Our chosen category is **Lighting** (Phillips Lighting, Kichler, Satco rows from the 1,000-row input).

The pipeline never invents or guesses values. Every attribute is either `FOUND` (with source URL evidence) or left blank. Confidence and review flags are internal/demo features shown in the Streamlit UI only — never written as extra columns in the 252-column output.

---

## Glossary

- **Ground Truth File**: `docs/Unihack_ Expected Output - Delivery Format (1).csv` — the two fully-worked Unilog example rows. The authoritative reference for all format, casing, and UOM decisions.
- **Input File**: `docs/Unihack_ Sample Dataset - Input (1).csv` — the real 1,000-row input. We slice this to the Lighting category.
- **Delivery Format**: The fixed 252-column output schema defined by the header row of the ground truth file. Headers must not be added, removed, or reordered.
- **Placeholder Brand Value**: Literal strings `-- Unbranded --`, `-- No Unilog Brand --`, `-- No DIB Brand --`. These mean the field is empty — filter out before any processing.
- **Manufacturer Code**: The alphanumeric code in parentheses at the end of `Part_Manuf`, e.g. `Phillips Lighting (5831)` → code `5831`.
- **FOUND**: An attribute `state` value meaning the attribute has a confirmed, non-None value. A FOUND attribute sourced from `Part_Desc` has `evidence_note = "Part_Desc"` (no URL, the raw input text is the evidence). A FOUND attribute sourced from a manufacturer page has `evidence_note = <source_url>`.
- **BLANK**: An attribute `state` value meaning no value was found. `value` is `None`. Always has `confidence = "Low"`.
- **Blank/Unattempted**: A field the pipeline does not populate. Written as empty string `""` in the output CSV. The ground truth itself has blank UNSPSC, country of origin, etc. — leaving fields blank is correct behavior, not a shortcut.
- **MFR URL**: The manufacturer's own product page URL. The only permitted retrieval source. Marketplaces and distributor sites (Amazon, eBay, etc.) are explicitly excluded.
- **Ref URL 1–5**: Additional reference URLs (owner's manual, installation guide, spec sheet) from manufacturer domains only.
- **Classpath**: `>`-delimited taxonomy string, e.g. `Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers`. Exact format from the ground truth.
- **INVOICE_DESC**: ALL CAPS, ≤40 characters. e.g. `DISHWASHER LEG 5 SST 120V 15A 50-1/4IN` (38 chars from Frigidaire example).
- **MOBILE_DESC**: ~60–80 chars, brand-led, sentence case. e.g. `Rheem Manufacturing FRIGIDAIRE, Dishwasher, Professional Series, PDSH4816AF`.
- **SHORT_DESC**: Title/product-name style with brand, series, MPN, key attributes.
- **LONG_DESC1**: Full comma-separated spec list, all confirmed attributes included.
- **Curated Source Set**: Pre-fetched manufacturer pages in `sample_data/curated_sources/` with a `manifest.json` index. Used by the MVP in place of live web search.

---

## Requirements

### Requirement 1: Input Ingestion and Placeholder Cleansing

**User Story:** As a pipeline operator, I want the ingestion stage to load the 6-column input CSV and strip placeholder noise, so that downstream stages never see placeholder strings as real values.

#### Acceptance Criteria

1. WHEN the ingestion stage reads the CSV, IT SHALL parse each row into a structured record containing: `mfg_part_num`, `part_desc`, `e1_brand`, `unilog_brand`, `dib_brand`, `manufacturer_name`, `manufacturer_code`.
2. WHEN a brand field (`E1_Brand`, `Unilog_Brand`, `DIB_Brand`) contains the exact string `-- Unbranded --`, `-- No Unilog Brand --`, or `-- No DIB Brand --`, THE ingestion stage SHALL set that field to `None` — these strings are not data.
3. WHEN `Part_Manuf` matches the pattern `<name> (<code>)`, THE ingestion stage SHALL split it into `manufacturer_name` (text before the parenthesis, trimmed) and `manufacturer_code` (alphanumeric code inside the parenthesis).
4. IF `Part_Manuf` contains no parenthesised code, THE ingestion stage SHALL set `manufacturer_name` to the full trimmed value and `manufacturer_code` to `None`.
5. IF `Part_Manuf` is empty or whitespace-only, THE ingestion stage SHALL set both `manufacturer_name` and `manufacturer_code` to `None`.
6. THE ingestion stage SHALL strip leading and trailing whitespace from `mfg_part_num` and `part_desc`.
7. IF the input CSV file cannot be opened, THE ingestion stage SHALL raise an error with the file path and reason.
8. IF the input CSV is missing any of the six required column headers, THE ingestion stage SHALL raise an error naming the missing column(s).

---

### Requirement 2: Taxonomy and Classification

**User Story:** As a pipeline operator, I want the classification stage to assign `Dept`, `Class`, `Fine`, and `Classpath` to each row, so that the output record carries the correct Unilog taxonomy path.

#### Acceptance Criteria

1. WHEN the classifier processes a row whose `Part_Desc` contains a recognised lighting keyword or bulb shape code (case-insensitive), IT SHALL assign `Dept`, `Class`, `Fine`, and `Classpath` and mark the classification as FOUND.
2. THE `Classpath` SHALL use `>` as delimiter with no spaces around it, exactly matching the ground truth format (e.g. `Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers`).
3. WHEN `Part_Desc` contains `strip` (case-insensitive), THE classifier SHALL assign `Dept = Lighting & Ceiling Fans`, `Class = Light Fixtures`, `Fine = LED Strip Lights`. Strip takes priority over LED/bulb detection.
4. WHEN `Part_Desc` contains `led` (case-insensitive) or a bulb shape code (`A19`, `A15`, `ST19`, `MR16`, `R20`, `PAR20`, `PAR30`, `PAR38`, `BR30`, `BR40`, `G25`, `T12`, `T9`, `T8`) and `strip` is absent, THE classifier SHALL assign `Dept = Lighting & Ceiling Fans`, `Class = Light Bulbs`, `Fine = LED Bulbs`.
5. WHEN `Part_Desc` contains `flor` or `sodium` (case-insensitive) without an LED keyword or bulb shape, THE classifier SHALL assign `Dept = Lighting & Ceiling Fans`, `Class = Light Bulbs`, `Fine = Light Bulbs`.
6. WHEN `Part_Desc` contains `halogen` (case-insensitive) without a higher-priority keyword, THE classifier SHALL assign `Dept = Lighting & Ceiling Fans`, `Class = Light Bulbs`, `Fine = Light Bulbs`.
6. IF no recognised keyword or shape code is found, THE classifier SHALL leave `Dept`, `Class`, `Fine`, `Classpath` as empty string `""` in the output — not the string `"UNKNOWN"`.
7. THE classifier SHALL always produce a result (no exceptions) — unrecognised rows produce blank taxonomy fields.

---

### Requirement 3: Manufacturer Source Discovery

**User Story:** As a pipeline operator, I want the retrieval stage to find the manufacturer's own product page for a given part number, so that attribute extraction has real evidence text.

#### Acceptance Criteria

1. WHEN the retrieval stage is given a `mfg_part_num` that exists in `sample_data/curated_sources/manifest.json`, IT SHALL return a dict with `source_url` (the manufacturer page URL) and `source_text` (the full pre-fetched page content).
2. IF the `mfg_part_num` is not in the manifest, THE retrieval stage SHALL return `None` — no error, just no source found.
3. IF the manifest file or a referenced source file cannot be read, THE retrieval stage SHALL return `None` and log a warning — it SHALL NOT raise an unhandled exception.
4. THE manifest SHALL only contain entries whose `source_url` belongs to a manufacturer domain. Marketplace and distributor domains (Amazon, eBay, Home Depot, Grainger, etc.) are never valid source URLs.
5. WHEN no source is found for a part number, ALL attributes beyond what can be parsed from `Part_Desc` SHALL be left blank — never guessed.

---

### Requirement 4: Deterministic Attribute Parsing from Part_Desc

**User Story:** As a pipeline operator, I want the normalisation stage to extract attribute values directly from the `Part_Desc` string using fixed rules, so that high-confidence attributes are captured without an LLM call.

#### Acceptance Criteria

1. WHEN `Part_Desc` contains a wattage pattern (digits immediately followed by `W` or `w` at a word boundary), THE parser SHALL return the wattage as `"<N> W"` — exactly one space between number and unit, per the ground truth UOM style (`"120 V"`, `"15 A"`, `"47 dBA"`).
2. WHEN `Part_Desc` contains a two-digit color temperature shorthand followed by `k` or `K` (e.g. `27k` → 2700K), THE parser SHALL return `"<NNN0> K"`.
3. WHEN `Part_Desc` contains `<digit>pk` (case-insensitive), THE parser SHALL return the numeric count as a plain string with no unit suffix.
4. WHEN `Part_Desc` contains a base type keyword (`med`, `medium`, `e26`, `e27`, `cand`, `candelabra`), THE parser SHALL return the canonical base code: `E26` for medium/E26/E27, `E12` for candelabra.
5. IF a pattern is absent, THE parser SHALL return `None` for that attribute — no default or placeholder value.
6. ALL unit formatting SHALL use exactly one space between the numeric value and the unit abbreviation (e.g. `"120 V"` not `"120V"`, `"24 in"` not `"24in"`) — consistent with the ground truth examples.

---

### Requirement 5: LLM-Based Attribute Extraction from Manufacturer Source

**User Story:** As a pipeline operator, I want the enrichment stage to extract additional attributes from retrieved manufacturer page text using the Grok API, so that attributes not visible in `Part_Desc` (Lumens, Rated Life, Dimmable) can be populated with evidence.

#### Acceptance Criteria

1. WHEN `XAI_API_KEY` is set and a manufacturer source text is available, THE enrichment stage SHALL call the Grok API (`grok-4` at `https://api.x.ai/v1/chat/completions`) with a structured-output prompt requesting `lumens`, `rated_life_hours`, and `dimmable`.
2. THE system prompt SHALL instruct the model to return only a JSON object with those three fields (integer or null for numeric fields, boolean or null for dimmable) and to use `null` for anything not explicitly stated — never guess.
3. WHEN the API returns a non-null value, THE enrichment stage SHALL record the value as FOUND with the `source_url` as evidence.
4. WHEN the API returns `null` for a field, THE enrichment stage SHALL leave that field blank — not populated, not set to "Unknown".
5. IF the API call fails (network error, timeout, auth error, malformed JSON), THE enrichment stage SHALL leave all three fields blank and log the error — never raise an unhandled exception.
6. IF `XAI_API_KEY` is not set, THE enrichment stage SHALL use a regex-based fallback over the same source text, applying the same blank-on-miss rule.
7. IF no manufacturer source exists for a part number, ALL source-dependent attributes SHALL remain blank.

---

### Requirement 6: Attribute Assembly

**User Story:** As a pipeline operator, I want all extracted attributes combined into a single enriched record per SKU, so that the output assembly stage has one consistent structure to write from.

#### Acceptance Criteria

1. THE enrichment stage SHALL produce exactly seven named attributes per row: `Wattage`, `Color Temperature`, `Pack Quantity`, `Base Type` (from `Part_Desc` parsing) plus `Lumens`, `Rated Life`, `Dimmable` (from source extraction or blank if no source).
2. WHEN an attribute is confirmed from `Part_Desc`, its `state` SHALL be `FOUND`, its internal confidence SHALL be `High`, and its `evidence_note` SHALL be the string `"Part_Desc"`.
3. WHEN an attribute is confirmed from a manufacturer source page, its `state` SHALL be `FOUND`, its internal confidence SHALL be `Medium`, and its `evidence_note` SHALL be the manufacturer page URL.
4. WHEN an attribute has no confirmed value, its `state` SHALL be `BLANK`, its `value` SHALL be `None`, and its confidence SHALL be `Low`.
5. THE `mfr_url` SHALL be stored on the enriched record when a source was found, and `None` otherwise.
6. Confidence values SHALL be available on each attribute for the review UI but SHALL NOT be written as columns in the 252-column output.

---

### Requirement 7: Description Building

**User Story:** As a pipeline operator, I want the description stage to generate `INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, and `LONG_DESC1` using only confirmed attributes, so that every description claim is backed by evidence.

#### Acceptance Criteria

1. THE description stage SHALL generate `INVOICE_DESC` as ALL CAPS, at most 40 characters, built from FOUND attributes in the format `LED BULB <Wattage>W <BaseType> <PackQty>PK` — truncated to the last full word within 40 chars if needed. Example for a 75W E26 4-pack: `LED BULB 75W E26 4PK`.
2. THE description stage SHALL generate `MOBILE_DESC` as a brand-led, sentence-case string starting with `manufacturer_name`, followed by item type ("LED Bulb"), and FOUND attributes in the order Wattage, Color Temperature, Base Type, Pack Quantity. Example: `Philips, LED Bulb, 75 W, 2700 K, E26, 4-Pack`.
3. THE description stage SHALL generate `SHORT_DESC` as a title/product-name-style string with manufacturer name, MPN, item type, and FOUND attributes. Example: `Philips 565374 LED Bulb, 75 W, E26 Base, 2700 K, 800 lm, 4-Pack`.
4. THE description stage SHALL generate `LONG_DESC1` as a comma-separated specification string listing all FOUND attributes in the fixed order: Wattage, Color Temperature, Lumens, Rated Life, Base Type, Pack Quantity, Dimmable. BLANK attributes are silently omitted. Example: `Philips LED Bulb, 75 W, 2700 K, 800 lm, 10950 h, E26 Base, 4-Pack, Dimmable`.
5. IF an attribute is BLANK (`value is None`), THE description stage SHALL omit it from all descriptions — no placeholder text inserted.
6. IF all seven attributes are BLANK, `INVOICE_DESC`, `SHORT_DESC`, and `LONG_DESC1` SHALL be empty string; `MOBILE_DESC` SHALL contain at minimum the manufacturer name if known.
7. THE description stage SHALL return a dict with exactly the four keys `"INVOICE_DESC"`, `"MOBILE_DESC"`, `"SHORT_DESC"`, `"LONG_DESC1"`, all with `str` values (never `None`).

---

### Requirement 8: 252-Column Output CSV Production

**User Story:** As a pipeline operator, I want the pipeline to write the output using the exact 252-column header row from the Unilog delivery format, so that the submission file is structurally correct.

#### Acceptance Criteria

1. THE pipeline SHALL load the 252-column header list from `sample_data/real_output_headers.json` and use it as the sole fieldnames for the output CSV writer — in exact order, no additions or removals.
2. THE pipeline SHALL initialise every output row as a dict with all 252 headers set to `""` before populating any fields.
3. WHEN classification produced a FOUND result, THE pipeline SHALL write `Dept`, `Class`, `Fine`, and `Classpath` — when not FOUND, those columns remain `""`.
4. WHEN a manufacturer source URL was found, THE pipeline SHALL write it to `MFR URL` — additional reference URLs (spec sheets, manuals) go in `Ref URL 1` through `Ref URL 5`.
5. THE pipeline SHALL write these fields for every row regardless of enrichment state: `Mfg_Part_Num`, `Part_Desc`, `E1_Brand`, `Unilog_Brand`, `DIB_Brand`, `Part_Manuf`, `MANUFACTURER_NAME`, `MANUFACTURER_PART_NUMBER`, `INVOICE_DESC`, `MOBILE_DESC`, `SHORT_DESC`, `LONG_DESC1`.
6. THE pipeline SHALL write confirmed attributes into consecutive `ATTRIBUTE_LABEL N` / `ATTRIBUTE_VALUE N` / `ATTRIBUTE_UOM N` triplets starting at slot 1, skipping blank attributes so there are no gaps in slot numbering.
7. THE pipeline SHALL leave all unattempted columns (pricing, images, warranty, dimensions, UPC, UNSPSC, etc.) as `""` — the ground truth itself leaves these blank.
8. THE pipeline SHALL NOT write confidence or review flag values as output columns.
9. WHEN writing the output CSV, THE pipeline SHALL use `extrasaction='raise'` on the DictWriter so any key outside the 252-header list raises an error immediately.

---

### Requirement 9: Evaluation Against Ground Truth

**User Story:** As a pipeline developer, I want to measure field-level accuracy against the hand-verified eval set, so that the submission can report real numbers.

#### Acceptance Criteria

1. THE evaluator SHALL load `sample_data/eval_set.csv` and compare pipeline output attribute values against expected values by `mfg_part_num` and `attribute_label`.
2. A pair SHALL be scored **correct** when both pipeline and ground truth have the same non-empty value (case-insensitive) OR both have no value.
3. A pair SHALL be scored **unsupported claim** when the pipeline has a value and the ground truth has none.
4. A pair SHALL be scored **miss** when the ground truth has a value and the pipeline has none.
5. THE evaluator SHALL print to stdout: total pairs evaluated, correct count, unsupported claims, misses, and accuracy percentage (correct / total × 100, one decimal place).
6. WHEN mismatches exist, THE evaluator SHALL print per-mismatch detail: `mfg_part_num`, `attribute_label`, actual value, expected value, reason category.
7. THE evaluator SHALL exit with code 0 regardless of mismatches — it reports, it does not fail the build.

---

### Requirement 10: Streamlit Review UI

**User Story:** As a hackathon reviewer, I want a web UI that shows the full enrichment result for any SKU including confidence and source evidence, so that the pipeline's approach is visible without inspecting CSV files.

#### Acceptance Criteria

1. WHEN the UI loads, IT SHALL show a dropdown of all SKUs from the input slice in the format `<Mfg_Part_Num> — <Part_Desc>`.
2. WHEN a SKU is selected, THE UI SHALL display: raw input fields, classification result with FOUND/blank indicator, source URL as a clickable link (or a warning if none found), and the extracted attributes table.
3. THE attributes table SHALL highlight blank-value rows in amber and FOUND-but-Low-confidence rows in red.
4. THE UI SHALL display all four generated descriptions with their character counts.
5. THE UI SHALL show a review queue listing attributes that are FOUND with confidence Medium or Low (i.e. sourced from manufacturer page), with the `evidence_note` showing the source URL.
6. THE UI SHALL show a collapsible section for attributes with no confirmed value.
7. THE UI SHALL NOT write confidence or review flags to the 252-column output CSV at any point.

---

### Requirement 11: No Hallucination — Evidence-Only Values

**User Story:** As a pipeline operator, I want every populated attribute value to be traceable to a real source URL, so that the submission demonstrates evidence-backed enrichment with zero invented values.

#### Acceptance Criteria

1. THE pipeline SHALL derive attribute values only from the raw `Part_Desc` string or from the text content of a manufacturer page returned by the retrieval stage.
2. NO attribute value SHALL be derived from marketplace pages, distributor sites, or LLM prior knowledge not grounded in a retrieved source.
3. WHEN an attribute value cannot be confirmed from evidence, THE pipeline SHALL leave the field blank — an empty string in the output CSV, not a placeholder like `"N/A"` or `"Unknown"`.
4. THE `MFR URL` column in the output SHALL be populated if and only if a real manufacturer page was retrieved and used as evidence.

---

### Requirement 12: CLI Orchestration

**User Story:** As a pipeline developer, I want to run the full pipeline end-to-end from the command line and generate the 252-column output CSV.

#### Acceptance Criteria

1. WHEN `pipeline.py` is run as a script, IT SHALL accept an optional `--limit N` argument to process only the first N rows.
2. WHEN no `--limit` is given, IT SHALL process all rows in `sample_data/input_slice.csv`.
3. THE pipeline SHALL write the output CSV to `output_demo.csv` in the project root and print `Written N rows to output_demo.csv`.
4. IF the output file cannot be written, THE pipeline SHALL print an error to stderr and exit with a non-zero code.
5. THE pipeline stages SHALL be importable as a Python package (`src/` with `__init__.py`) so the pipeline runs correctly as `python -m src.pipeline`.
