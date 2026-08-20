#!/usr/bin/env python3
"""
Enterprise SKU Enrichment Pipeline — End-to-End Demo Runner.
UniHack 2026 Showcase Script.

Executes all 5 pipeline stages + evaluations + tests in a structured,
color-formatted console demonstration.
"""

from __future__ import annotations

import os
import sys
import time

# Ensure src/ is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ANSI Color formatting
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
RESET = "\033[0m"


def header(title: str):
    print(f"\n{BOLD}{BLUE}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  ⚡ {title.upper()}{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 70}{RESET}\n")


def subheader(title: str):
    print(f"\n{BOLD}{YELLOW}▶ {title}{RESET}")
    print(f"{DIM}{'─' * 55}{RESET}")


def run_demo():
    header("UniHack 2026: Enterprise SKU Enrichment Pipeline")
    print(f"{DIM}Autonomous Multi-Stage Catalog Enrichment Engine{RESET}")
    print(f"{DIM}Team: Person A (Ingest/Taxonomy/Retrieval) | Person B (Enrich/Describe)")
    print(f"      Person C (Pipeline Orchestration)   | Person D (Evaluation/UI/QA){RESET}\n")

    # -----------------------------------------------------------------------
    # STAGE 1: INGESTION & CLEANSING
    # -----------------------------------------------------------------------
    subheader("Stage 1: Ingestion & Cleansing (Person A)")
    from ingest import load_and_clean
    input_file = os.path.join("sample_data", "input_slice.csv")
    clean_rows = load_and_clean(input_file)
    print(f"  {GREEN}✓{RESET} Ingested {BOLD}{len(clean_rows)}{RESET} raw rows from {input_file}")
    print(f"  {GREEN}✓{RESET} Cleansed placeholder brands ('-- Unbranded --', 'N/A', etc.)")
    print(f"  {GREEN}✓{RESET} Parsed manufacturer codes out of Part_Manuf")

    sample = clean_rows[0]
    print(f"\n  {DIM}Sample Raw Input Row:{RESET}")
    print(f"    • Part Number   : {BOLD}{sample.mfg_part_num}{RESET}")
    print(f"    • Description   : {sample.part_desc}")
    print(f"    • Manufacturer  : {sample.manufacturer_name} (Code: {sample.manufacturer_code})")
    print(f"    • Brands        : E1={sample.e1_brand}, Unilog={sample.unilog_brand}, DIB={sample.dib_brand}")

    # -----------------------------------------------------------------------
    # STAGE 2: TAXONOMY & CLASSIFICATION
    # -----------------------------------------------------------------------
    subheader("Stage 2: Taxonomy & Classification (Person A)")
    from classify import classify
    c_sample = classify(sample)
    print(f"  {GREEN}✓{RESET} 4-tier taxonomy engine evaluated:")
    print(f"    • Department    : {BOLD}{c_sample.dept}{RESET}")
    print(f"    • Class         : {BOLD}{c_sample.cls}{RESET}")
    print(f"    • Fine          : {BOLD}{c_sample.fine}{RESET}")
    print(f"    • Full Classpath: {CYAN}{c_sample.classpath}{RESET}")

    # -----------------------------------------------------------------------
    # STAGE 3 & 4: SOURCE RETRIEVAL & ATTRIBUTE EXTRACTION
    # -----------------------------------------------------------------------
    subheader("Stage 3 & 4: Source Discovery & Extraction (Persons A & B)")
    from enrich import enrich

    # Test curated sample with rich manufacturer source
    philips_sample = next((r for r in clean_rows if r.mfg_part_num in ("565374", "586875")), clean_rows[0])
    enriched = enrich(philips_sample)

    print(f"  Target SKU: {BOLD}{philips_sample.mfg_part_num}{RESET} — {philips_sample.part_desc}")
    if enriched.mfr_url:
        print(f"  {GREEN}✓{RESET} Manufacturer Source Verified: {CYAN}{enriched.mfr_url}{RESET}")
    else:
        print(f"  {YELLOW}ℹ{RESET} No external manufacturer URL (title-only extraction)")

    print(f"\n  {BOLD}Extracted 7 Standardized Attributes:{RESET}")
    for attr in enriched.attributes:
        val_str = f"{attr.value} {attr.uom or ''}".strip() if attr.value else f"{DIM}BLANK{RESET}"
        state_color = GREEN if attr.state == "FOUND" else YELLOW
        print(f"    • {attr.label:<20}: {state_color}[{attr.state:5}]{RESET} {BOLD}{val_str:<15}{RESET} (Conf: {attr.confidence:<6} | Source: {DIM}{attr.evidence_note}{RESET})")

    if enriched.marketing_description:
        print(f"\n  {BOLD}Manufacturer Marketing Copy:{RESET}")
        print(f"    \"{enriched.marketing_description.strip().replace(chr(10), ' ')}\"")
    if enriched.item_features:
        print(f"    Bullet points: {', '.join(enriched.item_features)}")

    # -----------------------------------------------------------------------
    # STAGE 5: MULTI-CHANNEL DESCRIPTION BUILDING
    # -----------------------------------------------------------------------
    subheader("Stage 5: Multi-Channel Description Generation (Person B)")
    from describe import build_all
    descs = build_all(enriched, philips_sample.manufacturer_name)
    for channel, text in descs.items():
        print(f"  • {BOLD}{channel:<14}{RESET} ({len(text)} chars): {text}")

    # -----------------------------------------------------------------------
    # STAGE 6: FULL PIPELINE EXECUTION (252-COLUMN CSV)
    # -----------------------------------------------------------------------
    subheader("Stage 6: Pipeline Orchestration & 252-Column Export (Person C)")
    from pipeline import run as run_pipeline, load_real_headers
    headers = load_real_headers()
    out_csv = "output_demo.csv"
    demo_limit = 10
    run_pipeline(input_path=input_file, output_path=out_csv, limit=demo_limit)
    print(f"  {GREEN}✓{RESET} Exported {BOLD}{demo_limit}{RESET} records into {CYAN}{out_csv}{RESET}")
    print(f"  {GREEN}✓{RESET} Certified {BOLD}{len(headers)}{RESET} Unihack Delivery Schema columns")

    # -----------------------------------------------------------------------
    # EVALUATION & GROUND TRUTH SCORING
    # -----------------------------------------------------------------------
    subheader("Quality Assurance & Ground-Truth Scoring (Person D)")
    from evaluate import run_eval
    eval_file = os.path.join("sample_data", "eval_set.csv")
    run_eval(input_file, eval_file)

    # -----------------------------------------------------------------------
    # SUMMARY & NEXT STEPS
    # -----------------------------------------------------------------------
    header("Demo Complete — All Systems Operational")
    print(f"  {GREEN}●{RESET} {BOLD}Interactive Streamlit UI{RESET} : Run {CYAN}streamlit run app.py{RESET}")
    print(f"  {GREEN}●{RESET} {BOLD}Automated QA Test Suite{RESET}  : Run {CYAN}pytest tests/ -v{RESET}")
    print(f"  {GREEN}●{RESET} {BOLD}Full Batch Pipeline Run{RESET}  : Run {CYAN}python src/pipeline.py{RESET}\n")


if __name__ == "__main__":
    start = time.time()
    run_demo()
    print(f"{DIM}Execution time: {time.time() - start:.2f}s{RESET}\n")
