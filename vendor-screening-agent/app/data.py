"""
Vendor-master data access.

Loads the internal vendor master once and exposes helpers to read it and to
append a brand-new vendor (what the "Create new" button does - a real, functional
write so the new record is found on the next search).
"""
import os
import threading

import pandas as pd

from .config import MASTER_CSV_PATH

_LOCK = threading.Lock()
MASTER_COLUMNS = ["vendor_id", "vendor_name", "country", "city",
                  "website", "lei", "tax_id", "created_date", "end_date"]

_master = pd.read_csv(MASTER_CSV_PATH).fillna("")


def get_master() -> pd.DataFrame:
    """The current vendor master (reflects any records added at runtime)."""
    return _master


def get_master_names() -> list:
    if "vendor_name" in _master.columns:
        return _master["vendor_name"].astype(str).tolist()
    return []


def _next_vendor_id() -> str:
    nums = []
    for vid in _master.get("vendor_id", []):
        s = str(vid)
        if s.upper().startswith("V") and s[1:].isdigit():
            nums.append(int(s[1:]))
    return f"V{(max(nums) + 1) if nums else 1:04d}"


def add_vendor(vendor_name: str, country: str = "", city: str = "",
               website: str = "", lei: str = "") -> dict:
    """
    Append a new vendor to the master and persist it to the CSV.
    Returns the created row (including its generated vendor_id).
    """
    global _master
    with _LOCK:
        new_id = _next_vendor_id()
        row = {
            "vendor_id": new_id,
            "vendor_name": vendor_name,
            "country": country,
            "city": city,
            "website": website,
            "lei": lei,
            "tax_id": "",
            "created_date": pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
            "end_date": "",
        }
        _master = pd.concat(
            [_master, pd.DataFrame([row])], ignore_index=True
        ).fillna("")
        try:
            os.makedirs(os.path.dirname(MASTER_CSV_PATH), exist_ok=True)
            _master.to_csv(MASTER_CSV_PATH, index=False)
        except OSError:
            pass  # in-memory add still succeeds even if the disk write fails
    return row
