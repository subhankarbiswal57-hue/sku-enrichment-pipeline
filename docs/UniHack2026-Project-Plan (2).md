# SKU Enrichment Pipeline — Project Plan
### UniHack 2026 (Unilog) — Track: AI Powered Product Intelligence for Industrial Commerce

*Given minimal product identifiers, retrieve source material from
manufacturer sites, extract structured attributes with source-URL
evidence, validate deterministically against real formatting rules, and
route only ambiguous fields to a human reviewer.*

> **This version is grounded in the real dataset (`Unihack__Sample_Dataset_-_Input.csv`,
> `Unihack__Expected_Output_-_Delivery_Format.csv`), the official Solution
> Guide, and the submission email. Earlier drafts were built on
> assumptions before this material was available — see §0.**

---

## 0. What Changed Now That We Have the Real Data (read this first)

- **The real input is exactly 6 columns:** `Mfg_Part_Num, Part_Desc,
  E1_Brand, Unilog_Brand, DIB_Brand, Part_Manuf`. That's it — genuinely
  minimal, confirms the retrieval-based approach was the right call.
- **Brand fields are mostly placeholder junk, not data.** In the 1000-row
  sample, `E1_Brand` is `-- Unbranded --` in 799/1000 rows, and
  `Unilog_Brand` is `-- No Unilog Brand --` in 1000/1000 rows. These must
  be treated as empty at ingestion — filtered out before anything else
  happens, not passed through as if they were real values.
- **The domain is much broader than plumbing/HVAC/electrical.** The real
  sample is dominated by lighting (Phillips, Kichler, Satco), power tool
  accessories (Milwaukee, Makita, Festool), abrasives (Diablo/Freud, 3M,
  Mirka), building materials, and appliances. **Our earlier category
  choice (valves/breakers/filters) doesn't match the actual data** —
  revised below.
- **The real output is 252 fixed columns** we must populate (not modify
  the headers), including `MFR URL` and `Ref URL 1` through `Ref URL 5` —
  this is the mandated form of "evidence," and it's simpler than what we
  designed: **up to 6 source URLs per SKU record**, not a URL per
  individual field. Internally we can still track per-field evidence for
  our own review-queue UI — it just doesn't need to be 50 separate URL
  columns in the delivered CSV.
- **The Solution Guide explicitly says not to attempt everything.**
  Quote: *"You are not expected to automate all of it. Picking two or
  three steps and doing them convincingly, with evidence, beats a
  shallow attempt at everything."* The full pipeline they describe is:
  input analysis → de-duplication → taxonomy & classification → attribute
  extraction → enrichment from manufacturer sources → cleansing/
  normalization → description building → digital assets. We pick a
  subset (§3).
- **A confidence score / review flag is explicitly endorsed** by the
  guide as "a genuinely valuable feature" — so our review-queue idea is
  validated, but it's a **demo/UI feature**, not a mandated CSV column.
  Don't add extra columns to the required 252-column format; show
  confidence and review status in the Streamlit UI instead.
- **We only received two files, and that's by design.** The Solution
  Guide's own words: *"Only two contain items to be processed; the rest
  tell you how to process them."* We have those two: `Sample-1000_Items`
  (raw input to process) and `Unilog-Sample_200_Items-Input-vs-Output`
  (the "Expected Output" file — our ground truth reference, even though
  what came through the export is 2 fully worked example rows — a
  Frigidaire and a Whirlpool dishwasher — rather than all 200; those 2
  rows are still a real, complete worked example of input → correct
  output, including real `MFR URL`/`Ref URL` sourcing).
- **The rule-book/master-data files were not provided to us**: content
  guidelines doc, UOM standards file, decimal-fraction table,
  manufacturer/brand master list, the cross-category LOV, Faucets_LOV,
  Fittings_LOV, and the reference index. These aren't hiding somewhere we
  missed — the email only ever linked the two working-data files. **We
  will build small equivalents ourselves**, scoped to whichever category
  we pick, reverse-engineered from the one worked example we do have
  (which already shows real casing, character-limit behavior, and UOM
  style in practice — e.g. "24 in", "24-1/4 in", "120 V", "15 A"). Worth
  a low-effort email to support asking if these exist for participants,
  but we are not blocking the build on a reply.
- **Deadline confirmed: 23 August 2026** — this now has three consistent
  sources (submission email at 11:59 PM IST, the live dashboard listing
  "Sun 23 Aug 2026," and the explainer session), so treat it as settled,
  not tentative. Full official timeline: registration + prototype
  submission 29 Jul – 23 Aug; evaluations 24 Aug – 1 Sep; finalists
  announced 1 Sep; grand finale 4 Sep. Only the 23 Aug submission date is
  ours to hit.
- **New required deliverable:** a **Solution Brief Overview** (a text
  summary of the solution) alongside the deck, live link, GitHub repo,
  and demo video. Missed this in earlier drafts.
- **Official evaluator criteria — now fully reconciled.** The dashboard
  and the explainer session both state it plainly: **Innovation,
  Accuracy, Quality, Scalability — four criteria, equal weightage**
  (stated directly by Unilog's VP Product Engineering). The submission
  email's 5 bullets (understand from limited info, discover & validate,
  generate structured output, explain & trace reasoning, scale across
  catalogs) aren't a different rubric — they're what evaluators look for
  *within* those four categories. Use the 4-criteria framing as the
  primary structure; the 5 bullets as supporting detail.
- **Minor, non-blocking additions from the dashboard/session:**
  - Output format is genuinely flexible — Unilog's own suggestion was
    "add another worksheet to the input Excel as output," which we're
    not doing (we use the real 252-column CSV format instead, which is
    more directly comparable to their worked example) — worth a one-line
    mention in the pitch that we chose the stricter format on purpose.
  - IP rights for **winning** solutions transfer to the organizers on
    award confirmation — noted for awareness, doesn't change how we build.
  - Team size 1-4, confirmed.

---

## 1. Problem Statement

Unilog builds product content for industrial distributors — titles,
descriptions, attributes, images — from raw distributor data that is
mostly unusable as-is: cryptic descriptions ("3/8 CPLG BRS 150#"), the
same manufacturer spelled six different ways, units written five
different ways, and most fields simply empty. The real sample data
confirms this exactly (e.g. `DCB518ASTS06G Diablo 1/2"x18" - Sanding Belt
6pc`, manufacturer field `Freud Inc (2435)`, brand placeholder-filled).

**Goal:** given a messy row with almost no information, produce a
complete, standardized, search-ready product record — sourced from the
manufacturer's own site/documentation (marketplaces and distributor sites
are explicitly excluded by the sourcing rules), with every generated
value traceable to a real source URL, and honest gaps left blank or
flagged rather than invented.

---

## 2. Scope Decision: Which 2-3 Steps We're Doing

Full pipeline per the guide: input analysis → de-duplication → taxonomy &
classification → attribute extraction → enrichment from manufacturer
sources → cleansing/normalization → description building → digital
assets.

**We are doing, convincingly, with evidence:**
1. **Taxonomy & classification** — map each raw row to Dept / Class /
   Fine (or Classpath), from real signals in the raw description and
   manufacturer.
2. **Attribute extraction + enrichment from manufacturer sources** —
   retrieve the manufacturer's product page/spec sheet, extract
   structured attributes (`ATTRIBUTE_LABEL`/`ATTRIBUTE_VALUE`/
   `ATTRIBUTE_UOM` columns), with `MFR URL` / `Ref URL 1-5` populated as
   real evidence.
3. **Description building** — generate the different description formats
   (`SHORT_DESC`, `LONG_DESC1`, `MOBILE_DESC`, `INVOICE_DESC`) from
   verified attributes only, at their correct length/casing constraints.

**Cleansing/normalization is a supporting layer under all three above**
(unit standardization, manufacturer-name canonicalization, placeholder
filtering) rather than a separate major step — it's small in isolated
scope but touches everything.

**Explicitly not attempting** (leave blank, don't fabricate): de-
duplication, digital assets (images, manuals, SDS, drawings), pricing,
warranty, UPC/EAN/GTIN, dimensions/weight. The guide's own example output
has blank cells (UNSPSC, country of origin) — leaving fields honestly
blank is consistent with how the ground truth itself looks, not a
shortcut we're hiding.

---

## 3. Category Choice (revised to match real data)

Earlier draft picked valves/breakers/filters — not present in the actual
1000-row sample. Revised candidates, by row count in the real sample:

- **Lighting** (Phillips Lighting 111, Kichler Lighting 56, Satco Prod
  Inc 41 — ~208 rows) — strong volume, likely has a reasonably
  standardizable attribute set (wattage, lumens, color temp, base type)
- **Power tool accessories** (Milwaukee Accessory 108, Makita 23, Festool
  16, Kreg Tool 11) — also strong volume
- **Abrasives** (Freud/Diablo 46, 3M, Mirka Abrasives 9) — smaller but
  very consistent naming pattern, easy to demo

**Recommendation: Lighting**, for the strongest combination of row count
and attribute standardizability. Since we don't have the LOV files at
all (Faucets and Fittings are the guide's own worked examples, and
neither appears in our real sample), we'll build our own lightweight
attribute schema for Lighting from scratch — a reasonable, small
attribute set (wattage, lumens, color temperature, base type, bulb
shape) inferred from what real lighting products typically specify,
using the generic `ATTRIBUTE_LABEL/VALUE/UOM` structure the real output
format already provides.

---

## 4. MVP Scope

**Input:** the real 6-column schema — `Mfg_Part_Num, Part_Desc, E1_Brand,
Unilog_Brand, DIB_Brand, Part_Manuf` — sliced to our chosen category from
the real 1000-row sample (not invented data).

**Stage 1 — Ingestion & Cleansing**
- Filter placeholder values (`-- Unbranded --`, `-- No Unilog Brand --`,
  `-- No DIB Brand --`) to empty/UNKNOWN, not literal data
- Parse `Part_Manuf`'s embedded code pattern (e.g. `Freud Inc (2435)`)

**Stage 2 — Taxonomy & Classification**
- Assign Dept / Class / Fine (or Classpath) per row, from the raw
  description + manufacturer

**Stage 3 — Source Discovery**
- Search for the manufacturer's own product page / spec sheet for that
  part number — manufacturer sources first; explicitly exclude
  marketplaces/distributor sites per the sourcing rule
- For the demo: a small curated set of pre-fetched manufacturer pages for
  our sample SKUs, with live search named as the production path (same
  reliability tradeoff as before — worth revisiting if a team member can
  reliably wire up live search in time)

**Stage 4 — Attribute Extraction**
- LLM extraction from retrieved source text into
  `ATTRIBUTE_LABEL/VALUE/UOM` triples, with:
  - state: `FOUND` or `UNKNOWN` (never guessed)
  - confidence: High/Medium/Low (internal — drives the review UI, not a
    delivered column)
  - `MFR URL` and up to 5 `Ref URL`s recorded at the record level

**Stage 5 — Normalization**
- Unit formatting (space between number and unit, approved abbreviation
  form) — a small, hand-built list of common conversions for our chosen
  category, reverse-engineered from the worked example's style (e.g.
  "24 in", "120 V", "15 A", "24-1/4 in"), since we don't have the ~500-entry
  UOM master file
- Manufacturer-name canonicalization — a small hardcoded lookup built for
  our chosen category's actual manufacturers in the real 1000-row sample,
  since we don't have the 27,000-row master list

**Stage 6 — Description Building**
- Generate `SHORT_DESC`, `LONG_DESC1`, `MOBILE_DESC`, `INVOICE_DESC` from
  verified attributes only — different lengths/casings per field, one
  prompt rule per format, no invented claims

**Stage 7 — Review UI**
- Streamlit: raw input → retrieved source → populated output columns
  (highlighting which came from `FOUND` vs `UNKNOWN`) → confidence +
  review queue (internal/demo feature, not a CSV column)

**Evaluation**
- Use the 2 worked example rows (Frigidaire, Whirlpool) as the pattern
  reference for correct format, casing, and sourcing behavior
- Build our own small ground truth: hand-research 10 real rows from our
  chosen category (a human genuinely looking them up, following the same
  sourcing rules — manufacturer sites only), matching the rigor of the
  worked example — report field-level accuracy and character-limit
  compliance where applicable

---

## 5. Architecture

### MVP architecture

```
Real input row (Mfg_Part_Num, Part_Desc, E1_Brand, Unilog_Brand,
DIB_Brand, Part_Manuf)
      │
      ▼
[Ingestion & Cleansing]  — filter placeholders, parse manufacturer code
      ▼
[Taxonomy & Classification]  — Dept / Class / Fine
      ▼
[Source Discovery]  — manufacturer sites first; MVP uses curated set
      ▼
[LLM Extraction]  — ATTRIBUTE_LABEL/VALUE/UOM + FOUND/UNKNOWN + evidence
      ▼
[Normalization]  — unit format, manufacturer canonicalization
      ▼
[Description Building]  — SHORT_DESC/LONG_DESC1/MOBILE_DESC/INVOICE_DESC
      ▼
252-column output row (MFR URL + Ref URLs populated; unattempted
columns left blank, not fabricated)
      │
      ▼
[Demo UI] (Streamlit) — shows confidence/review internally, not as
extra CSV columns
```

### Production architecture (explained, not built)

```
Full 1000+ row catalog → live retrieval (rate-limited, manufacturer-
priority, marketplace-excluded) → extraction → LOV-constrained
validation → auto-accept/review → full 252-column delivery format
```

**Tech stack:**
- Python 3.11
- Grok API for extraction — structured JSON output (paid; report
  estimated cost-per-SKU)
- Web search/fetch mechanism for source discovery (or curated set for MVP)
- Pandas for data handling
- Streamlit for the demo UI
- GitHub for source control; a real hosted deployment (not localhost) for
  the required live link

---

## 6. Repo Structure

```
sku-enrichment-pipeline/
├── README.md
├── LICENSE                   # MIT
├── .gitignore
├── .env.example               # XAI_API_KEY=
├── requirements.txt
├── sample_data/
│   ├── input_slice.csv       # real rows from our chosen category, sliced from the 1000-row file
│   ├── curated_sources/      # pre-fetched manufacturer pages for the demo set
│   └── eval_set.csv          # 10 hand-labeled real rows (our own researched ground truth)
├── src/
│   ├── ingest.py             # placeholder filtering, manufacturer code parsing
│   ├── classify.py           # taxonomy / Dept-Class-Fine assignment
│   ├── retrieve.py           # source discovery
│   ├── enrich.py             # LLM extraction + evidence + confidence
│   ├── normalize.py          # unit formatting, manufacturer canonicalization
│   ├── describe.py           # multi-format description generation
│   └── evaluate.py           # scoring against ground truth
├── app.py                    # Streamlit demo UI
└── docs/
    └── architecture.md
```

---

## 7. Judging Criteria Alignment (official 4 criteria, equal weight — confirmed on the dashboard and directly by Unilog's VP Product Engineering)

| Criteria | How we address it |
|---|---|
| **Innovation** | Retrieval-with-evidence approach from genuinely minimal input, not just text cleanup; field-level UNKNOWN instead of guessing when no source supports a value |
| **Accuracy** | `MFR URL`/`Ref URL` populated with real source pages; FOUND/UNKNOWN states; measured against our own hand-verified eval set (93% attribute accuracy, 0 unsupported claims on the real build) |
| **Quality** | Populates the real 252-column delivery format correctly; descriptions generated only from verified attributes, following the casing/length patterns in the one worked example |
| **Scalability** | Stateless per-row processing, tested on a real 111-row slice of the actual 1000-row sample; schema-driven so new categories don't need new code; honest about what's demonstrated vs. what Unilog's real ~150k-750k SKU/month volume would need |

The submission email's 5-bullet version (understand from limited info,
discover & validate, generate structured output, explain & trace
reasoning, scale across catalogs) maps directly onto these four and is
useful phrasing for the pitch, but the four-criteria, equal-weight
framing above is the one to lead with — it's what was stated directly by
the organizers themselves, twice.

---

## 8. Build Timeline (compressed — deadline 23 Aug 2026, 11:59 PM IST)

- **Day 1 (13-14 Aug):** Slice real input data to chosen category; hand-build
  a small UOM/casing cheat sheet and manufacturer lookup from the worked
  example; confirm category choice; write extraction prompt and test on a
  handful of rows
- **Day 2-3 (15-16 Aug):** Build `ingest.py`, `classify.py`,
  `retrieve.py`, `enrich.py`
- **Day 4 (17 Aug):** Build `normalize.py`
- **Day 5 (18 Aug):** Build `describe.py`
- **Day 6 (19 Aug):** Build Streamlit UI, deploy to a real hosted URL
- **Day 7 (20 Aug):** Run evaluation, record real numbers + cost-per-SKU
- **Day 8 (21 Aug):** README, Solution Brief Overview, deck, screenshots
- **Day 9 (22 Aug):** Record demo video, rehearse
- **Submit by 23 Aug, 11:59 PM IST**

---

## 9. Open Decisions

- [ ] Solo or team?
- [ ] Confirm category choice: Lighting (recommended) vs. power tool
      accessories vs. abrasives
- [ ] Curated source set vs. live search API for the MVP demo
- [ ] Grok API key — confirm access and budget
- [ ] Who hand-researches the 10-row eval set (a human, following the
      manufacturer-only sourcing rule)
- [ ] Where to host the working live link (not localhost)
- [ ] Confirm actual deadline on the dashboard roadmap (email says 23 Aug
      11:59 PM IST; reconcile against any earlier Sep 4 reference)
- [ ] Optional: email support+unihack@hack2skill.com to ask whether the
      rule-book/master-data files (guidelines doc, UOM master,
      manufacturer/brand list, LOV) are available to participants —
      low priority, not blocking
