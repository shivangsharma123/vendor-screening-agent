"""Pydantic request/response schemas for the API."""
from pydantic import BaseModel


class VendorSearch(BaseModel):
    """Input for a screening request. The dashboard sends the first three; API
    callers may also supply strong identifiers for a more confident check."""
    vendor_name: str
    country: str = ""
    website: str = ""
    tax_id: str = ""     # Tax ID / VAT / GST - top-tier exact-match key
    lei: str = ""
    isin: str = ""
    ticker: str = ""


class VendorDecision(BaseModel):
    """What the UI posts when a user clicks Reuse / Send to review / Create new.
    The human stays in control - the agent only recommends."""
    query_vendor_name: str
    query_country: str = ""
    query_website: str = ""
    candidate_vendor_id: str = ""
    candidate_vendor_name: str = ""
    match_percent: float = 0.0
    decision: str  # 'reuse' | 'review' | 'create'
