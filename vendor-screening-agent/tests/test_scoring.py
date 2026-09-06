"""
Offline unit tests for the scoring engine (no network needed).

Run from the project root:  python3 -m pytest -q
These lock in the two things judges will probe: real duplicates stay high, and
name-only false positives (Capital Infosys, etc.) are damped.
"""
from app.scoring import composite_name_score
from app.text_utils import country_sim, containment_penalty


def ns(a, b):
    return composite_name_score(a, b)["score"]


# --- true duplicates must stay HIGH (>= 0.90) ---
def test_legal_suffix():
    assert ns("Alpha Consulting", "Alpha Consulting Ltd.") >= 0.90

def test_word_order():
    assert ns("ABC Pharma Services", "Services ABC Pharma") >= 0.90

def test_abbreviation():
    assert ns("IBM", "International Business Machines") >= 0.99  # acronym expansion

def test_spacing_punctuation():
    assert ns("Blue-Tech R&D", "Bluetech R and D") >= 0.85

def test_brand_vs_legal():
    assert ns("Cognizant", "Cognizant Technology Solutions") >= 0.90


# --- name-only false positives must be damped (< 0.65) ---
def test_capital_infosys_damped():
    assert ns("Infosys", "Capital Infosys") < 0.65

def test_ravi_infosys_damped():
    assert ns("Infosys", "Ravi Infosys") < 0.65

def test_real_infosys_kept():
    assert ns("Infosys", "Infosys Limited") >= 0.95


# --- containment penalty behaviour ---
def test_penalty_same_head_no_penalty():
    assert containment_penalty("Cognizant", "Cognizant Technology Solutions") == 1.0

def test_penalty_different_leading_qualifier():
    assert containment_penalty("Infosys", "Capital Infosys") < 1.0


# --- country normalisation ---
def test_country_iso_equivalence():
    assert country_sim("India", "IN") == 1.0
    assert country_sim("USA", "US") == 1.0

def test_country_mismatch():
    assert country_sim("India", "Germany") < 0.5
