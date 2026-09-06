"""
HTTP endpoints.

  GET  /              -> the dashboard (static HTML shell)
  GET  /health        -> liveness probe
  POST /screen        -> screen a proposed vendor
  POST /decision      -> record Reuse / Send to review / Create new (functional)
  GET  /decisions     -> read the decision audit log
"""
import csv
import os

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import FileResponse

from .. import data
from ..config import DECISIONS_LOG_PATH, DECISION_LABELS
from ..models import VendorSearch, VendorDecision
from ..screening import screen_vendor

router = APIRouter()

_INDEX_HTML = os.path.join("templates", "index.html")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/screen")
def screen(v: VendorSearch):
    return screen_vendor(v)


@router.post("/decision")
def record_decision(d: VendorDecision):
    """
    Persist the human's choice to a CSV audit log. This is the real backend
    action behind the three buttons - the human decides, the system records.

    'create' additionally writes a brand-new vendor into the master, so the
    website is genuinely functional: the new record is found on the next search.
    """
    if d.decision not in DECISION_LABELS:
        return {"ok": False,
                "error": f"Unknown decision '{d.decision}'. Expected one of: {list(DECISION_LABELS)}"}

    created_vendor = None
    if d.decision == "create":
        created_vendor = data.add_vendor(
            vendor_name=d.query_vendor_name,
            country=d.query_country,
            website=d.query_website,
        )

    row = {
        "timestamp": pd.Timestamp.utcnow().isoformat(),
        "query_vendor_name": d.query_vendor_name,
        "query_country": d.query_country,
        "query_website": d.query_website,
        "candidate_vendor_id": (created_vendor["vendor_id"] if created_vendor
                                else d.candidate_vendor_id),
        "candidate_vendor_name": (created_vendor["vendor_name"] if created_vendor
                                  else d.candidate_vendor_name),
        "match_percent": d.match_percent,
        "decision": d.decision,
        "decision_label": DECISION_LABELS[d.decision],
    }
    try:
        os.makedirs(os.path.dirname(DECISIONS_LOG_PATH), exist_ok=True)
        file_exists = os.path.isfile(DECISIONS_LOG_PATH)
        with open(DECISIONS_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "recorded": row, "created_vendor": created_vendor}


@router.get("/decisions")
def list_decisions(limit: int = 50):
    if not os.path.isfile(DECISIONS_LOG_PATH):
        return {"count": 0, "decisions": []}
    df = pd.read_csv(DECISIONS_LOG_PATH).fillna("")
    rows = df.tail(limit).to_dict(orient="records")
    return {"count": len(df), "decisions": list(reversed(rows))}


@router.get("/")
def dashboard():
    return FileResponse(_INDEX_HTML)
