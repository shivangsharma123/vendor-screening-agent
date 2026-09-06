"""
Screening orchestration.

external_matches: screens against the GLEIF registry (name search, ISIN/LEI
lookup, former names, and concurrent parent-hierarchy checks).
screen_vendor: runs the internal + external checks, adds a web fallback only when
nothing confident was found, and returns the full response the UI renders.
"""
from typing import Any, Dict, List

from . import gleif
from .config import (
    MEDIUM_THRESHOLD, HIGH_THRESHOLD, MIN_REPORT_THRESHOLD,
    confidence_level, decision_label,
)
from .data import get_master_names
from .scoring import composite_name_score, name_match_score, internal_matches
from .text_utils import country_sim
from .vies import check_vat
from .web_search import web_verify, external_evidence_score


def external_matches(vendor_name, country, master_names, lei="", isin="", max_hits=3):
    hits: List[dict] = []
    seen: set = set()

    if lei:
        rec = gleif.by_lei(lei)
        if rec:
            hits.append(rec)
            seen.add(rec["lei"])
    if isin:
        for rec in gleif.search_by_isin(isin):
            if rec["lei"] not in seen:
                hits.append(rec)
                seen.add(rec["lei"])
    for rec in gleif.search_by_name(vendor_name, country, limit=5):
        if rec["lei"] not in seen:
            hits.append(rec)
            seen.add(rec["lei"])

    # Fetch every parent (direct + ultimate) for all hits concurrently.
    parent_map = gleif.prefetch_parents(hits)

    results = []
    for h in hits:
        # Compare against the legal name AND any trading/former names (catches
        # rebrands, e.g. Cognizant vs Cognizant Technology Solutions).
        candidate_names = [h["legal_name"]] + h.get("other_names", [])
        best = max(
            (composite_name_score(vendor_name, cn) for cn in candidate_names if cn),
            key=lambda d: d["score"],
            default={"score": 0.0, "method": "none", "breakdown": {}},
        )
        name_score = best["score"]
        exact_id = (bool(lei and h["lei"].upper() == lei.strip().upper())
                    or bool(isin and h["lei"] in seen))
        if name_score < .45 and not exact_id:
            continue

        country_score = country_sim(country, h["country"])
        overall = 100.0 if (lei and h["lei"].upper() == lei.strip().upper()) else \
            round(100 * (0.75 * name_score + 0.25 * country_score), 1)

        matched_fields, similar, add_on = [], [], []
        if lei and h["lei"].upper() == lei.strip().upper():
            matched_fields.append({"field": "lei", "score": 100.0, "note": "Exact LEI code match"})
            similar.append("Official registry ID matches exactly")
        if name_score >= .55:
            matched_fields.append({"field": "legal_name", "score": round(name_score * 100, 1),
                                   "note": f"Matched via {best['method']}"})
            similar.append(f"Company name is a {name_score:.0%} match")
        if country_score >= .85:
            matched_fields.append({"field": "country", "score": round(country_score * 100, 1),
                                   "note": f"Registered country matches ({h['country']})"})
            similar.append(f"Same country ({h['country']})")
        if h["status"]:
            add_on.append(f"{h['status'].title()} company in the public registry")
        if h.get("registration_status"):
            add_on.append(f"Registry record: {h['registration_status'].title()}")
        if h.get("other_names"):
            add_on.append("Also known as: " + ", ".join(h["other_names"][:3]))

        # Corporate-family check (parents were prefetched concurrently above).
        for kind in ("direct", "ultimate"):
            par = parent_map.get((h["lei"], kind))
            if not par or not par["legal_name"]:
                continue
            for mn in master_names:
                if name_match_score(par["legal_name"], mn) >= .80:
                    similar.append(
                        f"Same corporate group as your vendor '{mn}' "
                        f"({kind} parent: {par['legal_name']})"
                    )
                    matched_fields.append({"field": "corporate_hierarchy", "score": 90.0,
                                           "note": f"{kind} parent matches existing vendor '{mn}'"})
                    overall = max(overall, 90.0)
                    break

        # Registry evidence: an ACTIVE entity with an ISSUED LEI is strong.
        if lei and h["lei"].upper() == lei.strip().upper():
            registry_score = 100.0
        elif h.get("status") == "ACTIVE" and h.get("registration_status") == "ISSUED":
            registry_score = 90.0
        elif h.get("status") or h.get("registration_status"):
            registry_score = 50.0
        else:
            registry_score = None

        # Corroboration gate: for an EXTERNAL hit, a matching country is NOT
        # enough (two different real firms can share a name in one country, e.g.
        # "Cognizant Chemical" vs "Cognizant"). Promotion to "likely duplicate"
        # needs identity-level evidence: exact LEI/ISIN, or a corporate-parent
        # link to an existing vendor. Otherwise cap at "human review".
        corroborated = exact_id or any(
            mf["field"] in ("lei", "corporate_hierarchy") for mf in matched_fields
        )
        if not corroborated:
            overall = min(overall, 84.0)

        # Extra company details pulled from the public registry (more context).
        details = []
        if h.get("registration_number"):
            details.append({"label": "Official registry no.", "value": h["registration_number"]})
        if h.get("registered_since"):
            details.append({"label": "Registered since", "value": h["registered_since"]})
        if h.get("last_verified"):
            details.append({"label": "Registry verified", "value": h["last_verified"]})
        if h.get("next_renewal"):
            details.append({"label": "LEI valid until", "value": h["next_renewal"]})
        if h.get("address_full"):
            details.append({"label": "Address", "value": h["address_full"]})

        final_pct = min(overall, 100.0)
        results.append({
            "source": ["GLEIF LEI Registry"],
            "vendor_id": h["lei"],
            "vendor_name": h["legal_name"],
            "country": h["country"], "city": h["city"],
            "match_percent": final_pct,
            "confidence": confidence_level(final_pct),
            "decision_label": decision_label(final_pct),
            "matched_fields": matched_fields,
            "similar": similar, "add_on": add_on, "details": details,
            "evidence": {
                "name_similarity": round(name_score * 100, 1),
                "website_domain": None,        # GLEIF exposes no website
                "country_address": round(country_score * 100, 1) if country else None,
                "registry_identifier": registry_score,
                "external_evidence": None,
            },
        })
    results.sort(key=lambda x: x["match_percent"], reverse=True)
    return results[:max_hits]


def screen_vendor(v) -> Dict[str, Any]:
    """Run internal + GLEIF checks, add a web fallback only when nothing
    confident was found, and assemble the response the dashboard renders."""
    master_names = get_master_names()
    internal = internal_matches(v.vendor_name, v.country, v.website, v.lei, v.tax_id)
    try:
        external = external_matches(v.vendor_name, v.country, master_names, v.lei, v.isin)
    except Exception:
        external = []  # a GLEIF hiccup must never take the whole screen down

    combined = sorted(internal + external, key=lambda c: c["match_percent"], reverse=True)

    # Web fallback fires only when there is NO confident evidence yet - either
    # nothing found, or the best match is below the "human review" band. This
    # keeps the common path fast while still giving evidence for unknown names.
    best = combined[0]["match_percent"] if combined else 0.0
    web_result = None
    if not combined or best < MEDIUM_THRESHOLD:
        try:
            web_result = web_verify(v.vendor_name, v.country)
        except Exception as exc:
            web_result = {"ok": False, "error": str(exc), "results": []}

    if combined and web_result is not None:
        combined[0]["evidence"]["external_evidence"] = external_evidence_score(
            web_result, combined[0]["vendor_name"]
        )

    # Live legitimacy check against the free official EU VIES service (EU VAT only).
    vat_check = check_vat(v.tax_id) if getattr(v, "tax_id", "") else None

    return {
        "query": {"vendor_name": v.vendor_name, "country": v.country, "website": v.website,
                  "tax_id": v.tax_id, "lei": v.lei, "isin": v.isin, "ticker": v.ticker},
        "result_count": len(combined),
        "candidates": combined[:8],
        "no_match_above_threshold": len(combined) == 0,
        "vat_check": vat_check,
        "web_search_fallback": web_result,
        "thresholds": {"high": HIGH_THRESHOLD, "medium": MEDIUM_THRESHOLD,
                       "minimum_reported": MIN_REPORT_THRESHOLD},
    }
