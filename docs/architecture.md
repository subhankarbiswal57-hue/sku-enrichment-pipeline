# Architecture

## MVP (what's actually built and running in this repo)

```
Real input row (Mfg_Part_Num, Part_Desc, E1_Brand, Unilog_Brand,
DIB_Brand, Part_Manuf)
      │
      ▼
Ingestion & Cleansing (ingest.py)
  — filters placeholder brand values, parses manufacturer code
      ▼
Taxonomy & Classification (classify.py)
  — rule-based Dept / Class / Fine / Classpath for the Lighting slice
      ▼
Source Discovery (retrieve.py)
  — curated set of 2 real, pre-fetched manufacturer pages
      ▼
Attribute Extraction (enrich.py)
  — deterministic parsing from Part_Desc (normalize.py) +
    extraction from retrieved source text (regex fallback or Grok API)
  — every attribute: FOUND or UNKNOWN, never guessed
      ▼
Description Building (describe.py)
  — INVOICE_DESC / MOBILE_DESC / SHORT_DESC / LONG_DESC1
  — built only from FOUND attributes
      ▼
252-column output row (pipeline.py)
  — real required headers, unattempted columns left blank
      ▼
Streamlit UI (app.py) — confidence/review shown here only,
not as extra CSV columns
```

## Production (explained, not built)

```
Full catalog (Unilog's real ~150k SKUs/month)
      │
      ▼
Live retrieval layer
  — rate-limited web search, manufacturer-domain-first,
    marketplace/distributor domains excluded
      ▼
Extraction (LLM + deterministic rules)
      ▼
Validation against real master data
  — the ~500-entry UOM standards file, 27,000-row manufacturer/brand
    list, and ~161,000-row cross-category LOV file (none of which were
    provided to participants — this MVP substitutes small hand-built
    rules scoped to one category instead)
      ▼
      ├─→ high confidence → auto-accept → Product Store / PIM / export
      └─→ low confidence  → human review → approved value
```

The gap between these two is named explicitly rather than hidden: the
MVP proves the pipeline shape and the evidence/confidence approach on a
real (if small) slice of real data; production scale needs live
retrieval, the real master-data files, and queue-based processing.
