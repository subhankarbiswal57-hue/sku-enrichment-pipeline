"""
Property-based tests for SKU Enrichment Pipeline data contracts.

Uses Hypothesis to fuzz-test model invariants and pipeline stage contracts.
CRITICAL: First two lines suppress live API keys — never call live APIs in tests.
"""
import os; os.environ.pop("XAI_API_KEY", None)  # never call live API in tests
os.environ.pop("OPENROUTER_API_KEY", None)

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from models import (
    CleanRow,
    Attribute,
    Classification,
    EnrichedRow,
    ATTRIBUTE_LABELS,
    make_found_attr,
    make_blank_attr,
)


# ---------------------------------------------------------------------------
# Strategies for generating test data
# ---------------------------------------------------------------------------

alphanumeric = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 -",
    min_size=1,
    max_size=60,
)

non_empty_str = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())

confidence_st = st.sampled_from(["High", "Medium", "Low"])
label_st = st.sampled_from(ATTRIBUTE_LABELS)
uom_st = st.sampled_from(["W", "K", "lm", "h", None])


# ---------------------------------------------------------------------------
# Test 1: Attribute state derivation invariant
# ---------------------------------------------------------------------------

class TestAttributeInvariants:
    """Attribute.state is FOUND iff value is not None, BLANK otherwise."""

    def test_found_state(self):
        a = make_found_attr("Wattage", "75", "W", "High", "Part_Desc")
        assert a.state == "FOUND"
        assert a.value is not None

    def test_blank_state(self):
        a = make_blank_attr("Wattage", "not in Part_Desc")
        assert a.state == "BLANK"
        assert a.value is None
        assert a.confidence == "Low"

    def test_blank_must_be_low_confidence(self):
        """BLANK state (value=None) MUST have Low confidence — never High or Medium."""
        with pytest.raises(ValueError, match="BLANK state"):
            Attribute(label="Test", value=None, uom=None, confidence="High", evidence_note="test")

        with pytest.raises(ValueError, match="BLANK state"):
            Attribute(label="Test", value=None, uom=None, confidence="Medium", evidence_note="test")

    @given(
        label=label_st,
        value=non_empty_str,
        uom=uom_st,
        confidence=st.sampled_from(["High", "Medium"]),
    )
    @settings(max_examples=50)
    def test_found_attr_always_found_state(self, label, value, uom, confidence):
        a = make_found_attr(label, value.strip(), uom, confidence, "test")
        assert a.state == "FOUND"

    @given(label=label_st)
    @settings(max_examples=20)
    def test_blank_attr_always_blank_state(self, label):
        a = make_blank_attr(label)
        assert a.state == "BLANK"
        assert a.confidence == "Low"

    def test_make_found_rejects_empty_value(self):
        with pytest.raises(ValueError):
            make_found_attr("Wattage", "", "W", "High", "Part_Desc")


# ---------------------------------------------------------------------------
# Test 2: Classification contract
# ---------------------------------------------------------------------------

class TestClassificationContract:
    def test_found_classification_has_all_fields(self):
        c = Classification(
            dept="Lighting & Ceiling Fans",
            cls="Light Bulbs",
            fine="LED Bulbs",
            classpath="Lighting & Ceiling Fans>Light Bulbs>LED Bulbs",
            found=True,
        )
        assert c.found is True
        assert c.dept != ""
        assert c.cls != ""
        assert c.fine != ""
        assert ">" in c.classpath

    def test_not_found_classification_has_empty_fields(self):
        c = Classification(dept="", cls="", fine="", classpath="", found=False)
        assert c.found is False
        assert c.dept == ""
        assert c.classpath == ""


# ---------------------------------------------------------------------------
# Test 3: EnrichedRow always has exactly 7 attributes
# ---------------------------------------------------------------------------

class TestEnrichedRowContract:
    def test_seven_attributes_in_fixed_order(self, sample_row_565374):
        from enrich import enrich
        result = enrich(sample_row_565374)
        assert len(result.attributes) == 7
        for attr, expected_label in zip(result.attributes, ATTRIBUTE_LABELS):
            assert attr.label == expected_label

    def test_enriched_row_no_source(self, sample_row_no_source):
        from enrich import enrich
        result = enrich(sample_row_no_source)
        assert len(result.attributes) == 7
        assert result.mfr_url is None

    def test_all_states_are_found_or_blank(self, sample_row_565374):
        from enrich import enrich
        result = enrich(sample_row_565374)
        for a in result.attributes:
            assert a.state in ("FOUND", "BLANK")


# ---------------------------------------------------------------------------
# Test 4: Description generation contracts
# ---------------------------------------------------------------------------

class TestDescriptionContracts:
    def test_build_all_returns_five_keys(self, sample_row_565374):
        from enrich import enrich
        from describe import build_all
        enriched = enrich(sample_row_565374)
        descs = build_all(enriched, sample_row_565374.manufacturer_name)
        expected_keys = {"INVOICE_DESC", "MOBILE_DESC", "SHORT_DESC", "LONG_DESC1", "RETAIL_DESC"}
        assert set(descs.keys()) == expected_keys

    def test_all_descriptions_are_strings(self, sample_row_565374):
        from enrich import enrich
        from describe import build_all
        enriched = enrich(sample_row_565374)
        descs = build_all(enriched, sample_row_565374.manufacturer_name)
        for key, val in descs.items():
            assert isinstance(val, str), f"{key} is not str: {type(val)}"

    def test_invoice_desc_is_upper_and_short(self, sample_row_565374):
        from enrich import enrich
        from describe import build_all
        enriched = enrich(sample_row_565374)
        descs = build_all(enriched, sample_row_565374.manufacturer_name)
        inv = descs["INVOICE_DESC"]
        assert inv == inv.upper(), f"INVOICE_DESC not ALL CAPS: {inv!r}"
        assert len(inv) <= 40, f"INVOICE_DESC exceeds 40 chars ({len(inv)}): {inv!r}"


# ---------------------------------------------------------------------------
# Test 5: Classify module
# ---------------------------------------------------------------------------

class TestClassifyModule:
    def test_led_bulb_classified(self, sample_row_565374):
        from classify import classify
        c = classify(sample_row_565374)
        assert c.found is True
        assert "LED" in c.fine

    def test_unknown_product(self):
        row = CleanRow("000000", "XYZ Mystery Widget", None, None, None, "Unknown", None)
        from classify import classify
        c = classify(row)
        # Either found or not — but should never crash
        assert isinstance(c.found, bool)


# ---------------------------------------------------------------------------
# Test 6: Normalize module
# ---------------------------------------------------------------------------

class TestNormalizeModule:
    def test_parse_wattage(self):
        from normalize import parse_wattage
        assert parse_wattage("565374 75W Led A19 Med 27k 4pk") == "75 W"

    def test_parse_cct(self):
        from normalize import parse_cct
        assert parse_cct("565374 75W Led A19 Med 27k 4pk") == "2700 K"

    def test_parse_pack_qty(self):
        from normalize import parse_pack_qty
        assert parse_pack_qty("565374 75W Led A19 Med 27k 4pk") == "4"

    def test_parse_base_type(self):
        from normalize import parse_base_type
        assert parse_base_type("565374 75W Led A19 Med 27k 4pk") == "E26"

    def test_parse_wattage_missing(self):
        from normalize import parse_wattage
        assert parse_wattage("some description without wattage") is None


# ---------------------------------------------------------------------------
# Test 7: Ingest module
# ---------------------------------------------------------------------------

class TestIngestModule:
    def test_load_and_clean_returns_clean_rows(self):
        from ingest import load_and_clean
        rows = load_and_clean("sample_data/input_slice.csv")
        assert len(rows) > 0
        for r in rows:
            assert isinstance(r, CleanRow)
            assert r.mfg_part_num  # non-empty
            assert r.part_desc     # non-empty


# ---------------------------------------------------------------------------
# Test 8: Pipeline output row contract
# ---------------------------------------------------------------------------

class TestPipelineOutput:
    def test_output_row_has_252_columns(self, sample_row_565374):
        from pipeline import build_output_row, load_real_headers
        headers = load_real_headers()
        assert len(headers) == 252
        out = build_output_row(sample_row_565374, headers)
        assert len(out) == 252

    def test_all_output_values_are_strings(self, sample_row_565374):
        from pipeline import build_output_row, load_real_headers
        headers = load_real_headers()
        out = build_output_row(sample_row_565374, headers)
        for col, val in out.items():
            assert isinstance(val, str), f"Column {col!r} has non-string value: {type(val)}"

    def test_no_none_values_in_output(self, sample_row_565374):
        from pipeline import build_output_row, load_real_headers
        headers = load_real_headers()
        out = build_output_row(sample_row_565374, headers)
        for col, val in out.items():
            assert val is not None, f"Column {col!r} has None value"


# ---------------------------------------------------------------------------
# Test 9: Evaluation set validity
# ---------------------------------------------------------------------------

class TestEvalSet:
    def test_eval_set_loads(self):
        from evaluate import load_eval_set
        expected = load_eval_set("sample_data/eval_set.csv")
        assert len(expected) > 0

    def test_eval_set_attributes_are_valid_labels(self):
        from evaluate import load_eval_set
        expected = load_eval_set("sample_data/eval_set.csv")
        for part_num, attrs in expected.items():
            for label in attrs:
                assert label in ATTRIBUTE_LABELS, f"Unknown label {label!r} for {part_num}"


# ---------------------------------------------------------------------------
# Test 10: Dedup module
# ---------------------------------------------------------------------------

class TestDedupModule:
    def test_no_self_duplicates(self, sample_row_565374):
        from dedup import find_duplicates
        matches = find_duplicates([sample_row_565374])
        assert len(matches) == 0

    def test_identical_part_num_detected(self):
        from dedup import find_duplicates
        r1 = CleanRow("565374", "75W Led A19 Med 27k 4pk", None, None, None, "Phillips", "5831")
        r2 = CleanRow("565374", "75W LED A19 Medium 2700K 4-Pack", None, None, None, "Phillips", "5831")
        matches = find_duplicates([r1, r2])
        assert len(matches) >= 1
