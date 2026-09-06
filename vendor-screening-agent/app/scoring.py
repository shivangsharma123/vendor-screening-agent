"""
The scoring engine.

- composite_name_score: three fuzzy algorithms + acronym expansion + the
  containment penalty, blended into one explainable name score.
- internal_matches: screens a proposed vendor against the internal master using
  transparent weighted evidence, with a small ML classifier as a secondary check.

The scoring is deliberately transparent: every number shown in the UI comes from
these functions, so a reviewer can trace exactly why a match scored what it did.
"""
import re
from typing import Any, Dict

import numpy as np
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import data
from .config import (
    COLS, WEIGHTS, POS_RANGES, NEG_RANGES, BINARY_COLS, POS_P, NEG_P,
    MIN_REPORT_THRESHOLD, INTERNAL_NAME_MIN, confidence_level, decision_label,
)
from .text_utils import (
    gv, norm, name_core, name_tokens, country_sim,
    acronym_similarity, containment_penalty,
)


# --------------------------------------------------------------------------- #
# 1. Composite name score (three algorithms + acronym + containment penalty)
# --------------------------------------------------------------------------- #
def _lev_ratio(a, b) -> float:
    return fuzz.token_set_ratio(str(a), str(b)) / 100 if a and b else 0.0


def _jaro_winkler(a, b) -> float:
    return JaroWinkler.normalized_similarity(str(a), str(b)) if a and b else 0.0


def _tfidf_cosine(a, b) -> float:
    a, b = str(a).strip(), str(b).strip()
    if not a or not b:
        return 0.0
    try:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        matrix = vec.fit_transform([a, b])
        return float(cosine_similarity(matrix[0], matrix[1])[0][0])
    except ValueError:
        return 0.0


def composite_name_score(a, b) -> Dict[str, Any]:
    """
    Best of three fuzzy algorithms on the cleaned names, with two overrides:
      * a clean acronym<->expansion match (IBM = International Business Machines)
        is decisive and returns 1.0 immediately;
      * otherwise the best score is damped by containment_penalty so a different
        leading qualifier (Capital Infosys) can't ride on a shared token.
    """
    ca, cb = name_core(a), name_core(b)
    scores = {
        "levenshtein": round(_lev_ratio(ca, cb), 3),
        "jaro_winkler": round(_jaro_winkler(ca, cb), 3),
        "tfidf_cosine": round(_tfidf_cosine(ca, cb), 3),
    }
    if acronym_similarity(a, b) >= 1.0:
        return {"score": 1.0, "method": "acronym_expansion", "breakdown": scores}

    best_method = max(scores, key=scores.get)
    best_score = scores[best_method]
    penalty = containment_penalty(a, b)
    adj = round(best_score * penalty, 3)
    method = best_method if penalty >= 1.0 else best_method + "+containment_damp"
    return {"score": adj, "method": method, "breakdown": scores}


def name_match_score(a, b) -> float:
    return composite_name_score(a, b)["score"]


# --------------------------------------------------------------------------- #
# 2. Feature extraction + the secondary ML classifier
# --------------------------------------------------------------------------- #
def _norm_id(x) -> str:
    return re.sub(r"[\s.\-]", "", str(x or "")).upper()


def feats(v, r) -> Dict[str, Any]:
    vco, rco = gv(v, "country"), gv(r, "country")
    ns = composite_name_score(gv(v, "vendor_name"), gv(r, "vendor_name"))
    return {
        "name_similarity": ns["score"],
        "name_method": ns["method"],
        "name_breakdown": ns["breakdown"],
        "country_similarity": country_sim(vco, rco),
        "country_match": int(country_sim(vco, rco) >= .9),
        "city_similarity": _lev_ratio(gv(v, "city"), gv(r, "city")),
        "website_similarity": _lev_ratio(gv(v, "website"), gv(r, "website")),
        "lei_match": int(bool(gv(v, "lei")) and
                         _norm_id(gv(v, "lei")) == _norm_id(gv(r, "lei"))),
        "tax_match": int(bool(gv(v, "tax_id")) and
                         _norm_id(gv(v, "tax_id")) == _norm_id(gv(r, "tax_id"))),
    }


def _train_model():
    """
    HONEST NOTE: this classifier is trained on SYNTHETIC data drawn from the
    ranges above - it is a demonstration of the ML path and a secondary
    cross-check (25% weight), NOT the primary scorer. The transparent weighted
    evidence is the real, explainable engine.
    """
    rng = np.random.default_rng(42)
    X, y = [], []
    for label in (1, 0):
        ranges = POS_RANGES if label else NEG_RANGES
        probs = POS_P if label else NEG_P
        for _ in range(900):
            row = []
            for c in COLS:
                if c in BINARY_COLS:
                    p = probs[c]
                    row.append(rng.choice([0, 1], p=[1 - p, p]))
                else:
                    lo, hi = ranges[c]
                    row.append(rng.uniform(lo, hi))
            X.append(row)
            y.append(label)
    model = RandomForestClassifier(n_estimators=250, max_depth=10,
                                   class_weight="balanced", random_state=42)
    model.fit(X, y)
    return model


_MODEL = _train_model()


# --------------------------------------------------------------------------- #
# 3. Human-readable evidence builders
# --------------------------------------------------------------------------- #
def matched_fields_internal(v, r, f):
    fields = []
    if f["tax_match"]:
        fields.append({"field": "tax_id", "score": 100.0, "note": "Exact Tax ID / VAT match"})
    if f["lei_match"]:
        fields.append({"field": "lei", "score": 100.0, "note": "Exact LEI code match"})
    if f["name_similarity"] >= .55:
        fields.append({"field": "legal_name", "score": round(f["name_similarity"] * 100, 1),
                       "note": f"Matched via {f['name_method']}"})
    if f["country_match"]:
        fields.append({"field": "country", "score": round(f["country_similarity"] * 100, 1),
                       "note": f"Country matches ({gv(r, 'country')})"})
    if f["city_similarity"] >= .7:
        fields.append({"field": "city", "score": round(f["city_similarity"] * 100, 1),
                       "note": "City matches"})
    if f["website_similarity"] >= .7:
        fields.append({"field": "website", "score": round(f["website_similarity"] * 100, 1),
                       "note": "Website matches"})
    return fields


def diff_breakdown(v, r, f):
    similar, add_on = [], []
    if f["tax_match"]:
        similar.append("Tax ID / VAT number matches exactly")
    if f["name_method"] == "acronym_expansion":
        similar.append("Short form and full name of the same company")
    elif f["name_similarity"] >= .55:
        similar.append(f"Company name is a {f['name_similarity']:.0%} match")
    if f["country_match"]:
        similar.append(f"Same country ({gv(r, 'country')})")
    elif f["country_similarity"] > 0:
        similar.append(f"Similar location ({f['country_similarity']:.0%})")
    if f["city_similarity"] >= .7:
        similar.append(f"Same city ({gv(r, 'city')})")
    if f["website_similarity"] >= .7:
        similar.append("Same website")
    vt, rt = name_tokens(gv(v, "vendor_name")), name_tokens(gv(r, "vendor_name"))
    extra_in_v, extra_in_r = vt - rt, rt - vt
    if extra_in_v:
        add_on.append("New name adds: " + ", ".join(sorted(extra_in_v)))
    if extra_in_r:
        add_on.append("Existing record has extra term(s): " + ", ".join(sorted(extra_in_r)))
    if gv(v, "website") and not gv(r, "website"):
        add_on.append(f"Website provided ({gv(v, 'website')}) - not on existing record")
    return {"similar": similar, "add_on": add_on}


def evidence_internal(v, r, f):
    """The 5 named evidence categories the UI draws as bars (deck slide 12).
    A category with no check is None -> shown as 'Not checked', never invented."""
    return {
        "name_similarity": round(f["name_similarity"] * 100, 1),
        "website_domain": round(f["website_similarity"] * 100, 1) if gv(v, "website") else None,
        "country_address": round(f["country_similarity"] * 100, 1) if (gv(v, "country") or gv(r, "country")) else None,
        "registry_identifier": 100.0 if (f["lei_match"] or f["tax_match"])
            else (0.0 if (gv(v, "lei") or gv(v, "tax_id")) else None),
        "external_evidence": None,
    }


# --------------------------------------------------------------------------- #
# 4. Internal vendor-master screening
# --------------------------------------------------------------------------- #
def internal_matches(vendor_name, country, website, lei="", tax_id=""):
    v = {"vendor_name": vendor_name, "country": country, "website": website,
         "lei": lei, "tax_id": tax_id}
    out = []
    for _, r in data.get_master().iterrows():
        f = feats(v, r)
        # Surface genuinely name-similar records, OR any exact identifier match
        # (Tax ID / LEI). A matching Tax ID must surface even when the NAME is
        # different - that is the strongest duplicate signal in real MDM.
        if f["name_similarity"] < INTERNAL_NAME_MIN and not f["lei_match"] and not f["tax_match"]:
            continue

        # Transparent weighted evidence over the signals we ACTUALLY have. Fields
        # the user did not provide (city/website) are excluded and the weights
        # renormalised, so an absent field can't drag a real match down.
        provided = {
            "name_similarity": True,
            "country_similarity": bool(gv(v, "country")),
            "country_match": bool(gv(v, "country")),
            "city_similarity": bool(gv(v, "city")),
            "website_similarity": bool(gv(v, "website")),
        }
        active = [c for c in COLS if provided.get(c)]
        wsum = sum(WEIGHTS[c] for c in active) or 1.0
        h = 100 * sum(WEIGHTS[c] * f[c] for c in active) / wsum

        # Secondary ML cross-check (minority weight); heuristic is primary.
        x = np.array([[f[c] for c in COLS]])
        ml = float(_MODEL.predict_proba(x)[0][1]) * 100
        p = .75 * h + .25 * ml
        if f["lei_match"] or f["tax_match"]:
            p = 100.0  # exact Tax ID / LEI match = certain duplicate

        # Corroboration gate: a name match alone can never be a confident
        # duplicate - it needs a non-name signal (same country/city, or exact ID).
        corroborated = bool(f["country_match"] or f["city_similarity"] >= .7
                            or f["lei_match"] or f["tax_match"])
        if not corroborated:
            p = min(p, 84.0)
        if p < MIN_REPORT_THRESHOLD:
            continue

        bd = diff_breakdown(v, r, f)
        details = []
        if gv(r, "vendor_id"):
            details.append({"label": "Vendor ID", "value": str(gv(r, "vendor_id"))})
        if gv(r, "tax_id"):
            details.append({"label": "Tax ID / VAT", "value": str(gv(r, "tax_id"))})
        if gv(r, "created_date"):
            details.append({"label": "Added on", "value": str(gv(r, "created_date"))})
        if gv(r, "end_date"):
            details.append({"label": "Contract end", "value": str(gv(r, "end_date"))})
        out.append({
            "source": ["Vendor master (internal)"],
            "vendor_id": str(gv(r, "vendor_id", "")),
            "vendor_name": gv(r, "vendor_name"),
            "country": gv(r, "country"), "city": gv(r, "city"),
            "match_percent": round(p, 1),
            "confidence": confidence_level(p),
            "decision_label": decision_label(p),
            "matched_fields": matched_fields_internal(v, r, f),
            "similar": bd["similar"], "add_on": bd["add_on"], "details": details,
            "evidence": evidence_internal(v, r, f),
        })
    out.sort(key=lambda z: z["match_percent"], reverse=True)
    return out[:5]
