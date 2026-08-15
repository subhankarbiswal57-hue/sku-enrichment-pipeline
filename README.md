# SKU Enrichment Pipeline — UniHack 2026

Given minimal product identifiers (manufacturer, part number, brand),
retrieves the manufacturer's own source page, extracts structured
attributes with source-URL evidence, and generates the required output
fields — never inventing a value the source doesn't support.

## What this actually does

Built and tested against **real UniHack sample data**: a 111-row slice of
the official 1000-item sample (`Sample-1000_Items`), filtered to Phillips
Lighting LED bulbs. Two of those rows are enriched against **real,
live-fetched manufacturer pages** from `usa.lighting.philips.com` (Philips'
actual manufacturer site, not a marketplace — per the sourcing rule).

Pipeline stages:
1. **Ingestion & Cleansing** — filters placeholder brand values
   (`-- Unbranded --`, etc.), parses the manufacturer code out of
   `Part_Manuf`
2. **Taxonomy & Classification** — rule-based Dept/Class/Fine + Classpath
   assignment for the Lighting slice
3. **Source Discovery** — MVP uses a curated set of 2 real, pre-fetched
   manufacturer pages (`sample_data/curated_sources/`); production would
   do live, rate-limited search with the same manufacturer-first,
   marketplace-excluded rule
4. **Attribute Extraction** — combines deterministic parsing from the raw
   description (wattage, color temp, pack size, base type) with
   extraction from the retrieved source text (lumens, rated life,
   dimmable). Every attribute is `FOUND` or `UNKNOWN` — never guessed.
5. **Description Building** — `INVOICE_DESC`, `MOBILE_DESC`,
   `SHORT_DESC`, `LONG_DESC1` generated only from `FOUND` attributes

Output is written using the **exact 252-column header row** from
`Unihack__Expected_Output_-_Delivery_Format.csv` — unattempted columns
(pricing, images, warranty, dimensions, etc.) are left blank, consistent
with how the one real worked example we have also has blank cells.

## What's real vs. a stand-in

- **Real:** the input data, the output schema, the two manufacturer
  source pages, the deterministic parsing, the classification logic, the
  description generation, the evaluation numbers below.
- **Stand-in, named explicitly:** source discovery uses a small curated
  set of 2 pre-fetched pages rather than live web search (reliability
  tradeoff for a timed demo — see project plan). Without an `XAI_API_KEY`,
  `enrich.py` falls back to a small regex extractor over the curated
  source text instead of a real LLM call, so the pipeline is runnable and
  testable without a live key.
- **Not attempted:** the ~500-entry UOM master file, the 27,000-row
  manufacturer/brand master list, and the cross-category LOV file were
  never provided to participants (see project plan §0) — normalization
  and manufacturer canonicalization here are small, hand-built rules
  scoped to this category, not the real master data.

## Evaluation

Scored against a 14-attribute hand-verified ground truth
(`sample_data/eval_set.csv`), checked by us directly against the real
manufacturer pages:

| Metric | Result |
|---|---|
| Attribute accuracy | 13/14 (93%) |
| Unsupported claims (guessed when we should've said UNKNOWN) | 0 |
| Known gap | Base Type isn't checked against the source page, only the raw description — one real, specific fix identified, not hidden |

Run it yourself: `python3 src/evaluate.py`

## Running it

```bash
pip install -r requirements.txt

# Run the pipeline on the real 111-row input slice, writing the real
# 252-column output format:
python3 src/pipeline.py          # all 111 rows
python3 src/pipeline.py 15       # first 15 rows only

# Run the evaluation:
python3 src/evaluate.py

# Launch the demo UI:
streamlit run app.py
```

To use the real Grok API instead of the regex fallback for source-text
extraction, copy `.env.example` to `.env` and set `XAI_API_KEY`.

## Repo structure

```
sku-enrichment-pipeline/
├── README.md
├── LICENSE
├── .env.example
├── requirements.txt
├── sample_data/
│   ├── input_slice.csv         # 111 real Phillips Lighting rows
│   ├── eval_set.csv            # hand-verified ground truth
│   ├── real_output_headers.json
│   └── curated_sources/        # 2 real fetched manufacturer pages + manifest
├── src/
│   ├── ingest.py                # Stage 1
│   ├── classify.py              # Stage 2
│   ├── retrieve.py              # Stage 3
│   ├── enrich.py                # Stage 4
│   ├── normalize.py             # deterministic parsing helpers
│   ├── describe.py              # Stage 6
│   ├── pipeline.py              # runs it all end-to-end
│   └── evaluate.py
├── app.py                       # Streamlit demo UI
└── docs/
    └── architecture.md
```

## What we picked, per the Solution Guide's "pick 2-3 steps" guidance

Taxonomy & classification, attribute extraction + manufacturer-source
enrichment, and description building — done convincingly on a real data
slice, with evidence and honest gaps, rather than a shallow pass over
all 1000 rows. De-duplication and digital assets are explicitly out of
scope (see project plan).
