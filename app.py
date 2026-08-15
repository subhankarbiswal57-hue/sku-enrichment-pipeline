"""
Streamlit demo UI — SKU Enrichment Pipeline.

Shows, for each SKU in the input slice: the raw input row, the retrieved
manufacturer source (if any), the enriched attributes with per-field
state/confidence, the generated descriptions, and a review queue for
low-confidence fields. Confidence/review status is shown here in the UI
only — it is NOT written as an extra column in the real 252-column
output format.

Run with: streamlit run app.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pandas as pd
import streamlit as st

from classify import classify
from describe import build_all
from enrich import enrich
from ingest import load_and_clean

st.set_page_config(page_title="SKU Enrichment Pipeline", layout="wide")

st.title("SKU Enrichment Pipeline")
st.caption(
    "UniHack 2026 — given minimal product identifiers, retrieves manufacturer "
    "source pages and extracts structured attributes with evidence. "
    "Category: Lighting > LED Bulbs (Phillips Lighting slice of the real 1000-row sample)."
)

DATA_PATH = os.path.join(os.path.dirname(__file__), "sample_data", "input_slice.csv")


@st.cache_data
def get_rows():
    return load_and_clean(DATA_PATH)


rows = get_rows()
part_options = {f"{r.mfg_part_num} — {r.part_desc}": r for r in rows}

selected_label = st.selectbox("Choose a SKU from the real sample data", list(part_options.keys()))
raw_row = part_options[selected_label]

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Raw Input")
    st.json({
        "Mfg_Part_Num": raw_row.mfg_part_num,
        "Part_Desc": raw_row.part_desc,
        "E1_Brand": raw_row.e1_brand or "(placeholder — filtered)",
        "Unilog_Brand": raw_row.unilog_brand or "(placeholder — filtered)",
        "Part_Manuf": f"{raw_row.manufacturer_name} ({raw_row.manufacturer_code})",
    })

    st.subheader("2. Classification")
    c = classify(raw_row)
    if c.state == "FOUND":
        st.success(f"Classpath: {c.classpath}")
    else:
        st.warning("Classpath: UNKNOWN — no clear signal in description")

with col2:
    st.subheader("3. Retrieved Source")
    enriched = enrich(raw_row)
    if enriched.source_url:
        st.success(f"Manufacturer source found:\n\n{enriched.source_url}")
    else:
        st.warning("No source found in curated set for this SKU — attributes beyond Part_Desc parsing will be UNKNOWN, not guessed.")

    st.subheader("4. Extracted Attributes")
    rows_display = []
    for a in enriched.attributes:
        rows_display.append({
            "Attribute": a.label,
            "Value": f"{a.value} {a.uom or ''}".strip() if a.value else "—",
            "State": a.state,
            "Confidence": a.confidence,
        })
    df = pd.DataFrame(rows_display)

    def highlight_state(row):
        if row["State"] == "UNKNOWN":
            return ["background-color: #fff3cd"] * len(row)
        if row["Confidence"] == "Low":
            return ["background-color: #ffe0e0"] * len(row)
        return [""] * len(row)

    st.dataframe(df.style.apply(highlight_state, axis=1), use_container_width=True, hide_index=True)

st.subheader("5. Generated Descriptions")
descs = build_all(enriched, raw_row.manufacturer_name)
for label, text in descs.items():
    st.text(f"{label} ({len(text)} chars): {text}")

st.subheader("6. Review Queue")
review_items = [a for a in enriched.attributes if a.confidence in ("Medium", "Low") and a.state == "FOUND"]
unknowns = [a for a in enriched.attributes if a.state == "UNKNOWN"]

if review_items:
    st.info(f"{len(review_items)} field(s) from the manufacturer source — worth a quick human check before publishing:")
    for a in review_items:
        st.write(f"⚠️ **{a.label}**: {a.value} {a.uom or ''} — sourced from manufacturer page, not the raw description")
else:
    st.write("No fields need review for this SKU.")

if unknowns:
    with st.expander(f"{len(unknowns)} field(s) left UNKNOWN (not guessed)"):
        for a in unknowns:
            st.write(f"- {a.label}: no supporting source ({a.evidence_note})")

st.divider()
st.caption(
    "Evidence per field: deterministic attributes (Wattage, Color Temperature, Pack Quantity, "
    "Base Type) are parsed directly from Part_Desc — high confidence. Attributes from the "
    "manufacturer page (Lumens, Rated Life, Dimmable) are medium confidence since they depend "
    "on retrieval + extraction, not just the raw description."
)
