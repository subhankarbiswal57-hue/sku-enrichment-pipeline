"""
Shared pytest fixtures for the SKU Enrichment Pipeline test suite.
"""
import os
import sys

# Never call live API in tests
os.environ.pop("XAI_API_KEY", None)
os.environ.pop("OPENROUTER_API_KEY", None)

import pytest

# Add src to path so all pipeline modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import CleanRow, Attribute, Classification, EnrichedRow, ATTRIBUTE_LABELS


@pytest.fixture
def sample_row_565374():
    """Real Philips 75W A19 row from the input slice."""
    return CleanRow(
        mfg_part_num="565374",
        part_desc="565374 75W Led A19 Med 27k 4pk",
        e1_brand=None,
        unilog_brand=None,
        dib_brand=None,
        manufacturer_name="Phillips Lighting",
        manufacturer_code="5831",
    )


@pytest.fixture
def sample_row_586875():
    """Real Philips 60W Multi CCT row from the input slice."""
    return CleanRow(
        mfg_part_num="586875",
        part_desc="586875 60W Led Multi CCT 4pk",
        e1_brand=None,
        unilog_brand=None,
        dib_brand=None,
        manufacturer_name="Phillips Lighting",
        manufacturer_code="5831",
    )


@pytest.fixture
def sample_row_no_source():
    """A row with no curated source page — tests fallback/blank paths."""
    return CleanRow(
        mfg_part_num="999999",
        part_desc="999999 40W Led A19 Med 27k 2pk",
        e1_brand=None,
        unilog_brand=None,
        dib_brand=None,
        manufacturer_name="Phillips Lighting",
        manufacturer_code="5831",
    )
