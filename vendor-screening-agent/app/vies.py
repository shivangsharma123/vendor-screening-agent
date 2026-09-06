"""
EU VIES VAT validation client (free, official, no API key).

VIES is the European Commission's VAT Information Exchange System. It confirms
whether a VAT number is real and active across all 27 EU member states - a
second official open-data legitimacy source alongside GLEIF.

Note: only EU VAT numbers are covered (not India/US/UK-GB). Some countries
(e.g. DE, ES) return only valid/invalid without the company name for privacy.
"""
import re
import time
from typing import Any, Dict, Optional

import requests

_CACHE: Dict[str, Any] = {}
_TTL = 3600
_BASE = "https://ec.europa.eu/taxation_customs/vies/rest-api/ms"
EU_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
    "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
    "SE", "SI", "SK", "XI",   # XI = Northern Ireland
}


def check_vat(vat: str) -> Optional[Dict[str, Any]]:
    """
    Validate an EU VAT number via VIES.
    Returns None if the input is empty or not an EU VAT (so non-EU tax IDs are
    simply skipped). Otherwise a dict: {checked, valid, name, address, country,
    vat, source}.
    """
    if not vat:
        return None
    cleaned = re.sub(r"[\s.\-]", "", str(vat)).upper()
    m = re.match(r"^([A-Z]{2})([A-Z0-9]+)$", cleaned)
    if not m:
        return None
    cc, num = m.group(1), m.group(2)
    if cc not in EU_COUNTRIES:
        return None  # VIES only covers the EU

    key = cc + num
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < _TTL:
        return hit[1]

    result: Dict[str, Any]
    try:
        r = requests.get(f"{_BASE}/{cc}/vat/{num}", timeout=8,
                         headers={"Accept": "application/json"})
        if r.status_code == 200:
            d = r.json()
            result = {
                "checked": True,
                "valid": bool(d.get("isValid")),
                "name": (d.get("name") or "").strip().replace("---", ""),
                "address": (d.get("address") or "").strip().replace("---", ""),
                "country": cc,
                "vat": key,
                "source": "EU VIES",
            }
        else:
            result = {"checked": True, "valid": None, "vat": key,
                      "source": "EU VIES", "error": f"HTTP {r.status_code}"}
    except requests.RequestException:
        result = {"checked": True, "valid": None, "vat": key,
                  "source": "EU VIES", "error": "VIES unavailable"}

    _CACHE[key] = (time.time(), result)
    return result
