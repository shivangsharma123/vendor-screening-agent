"""
Web-search fallback (DuckDuckGo via the `ddgs` package).

This is deliberately a LAST resort: it runs only when neither the vendor master
nor GLEIF produced a confident answer. Results are cached so the same query is
never fetched twice in a session.
"""
import time
from typing import Any, Dict

from .config import WEB_CACHE_TTL
from .scoring import name_match_score

_CACHE: Dict[str, Dict[str, Any]] = {}


def cached_web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    now = time.time()
    hit = _CACHE.get(query)
    if hit and (now - hit["ts"]) < WEB_CACHE_TTL:
        return {**hit["data"], "from_cache": True}
    try:
        from ddgs import DDGS
        raw = list(DDGS().text(query, max_results=max_results))
        data = {
            "ok": True,
            "results": [
                {"title": r.get("title", ""), "url": r.get("href", ""),
                 "snippet": r.get("body", "")}
                for r in raw
            ],
        }
    except Exception as exc:  # ddgs raises various network/parse errors
        data = {"ok": False, "error": str(exc), "results": []}
    _CACHE[query] = {"ts": now, "data": data}
    return {**data, "from_cache": False}


def web_verify(vendor_name: str, country: str) -> Dict[str, Any]:
    query = f'"{vendor_name}" {country} company official website'.strip()
    result = cached_web_search(query)
    result["query"] = query
    return result


def external_evidence_score(web_result: Dict[str, Any], candidate_name: str):
    """How strongly the web results corroborate the candidate's name (0-100)."""
    if not web_result or not web_result.get("results"):
        return None
    best = 0.0
    for r in web_result["results"]:
        text = f"{r.get('title', '')} {r.get('snippet', '')}"
        best = max(best, name_match_score(candidate_name, text))
    return round(best * 100, 1)
