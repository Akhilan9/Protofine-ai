"""Data access package for trusted evidence."""
from app.data.loader import get_all_evidence, get_evidence_by_ids, get_evidence_by_id

__all__ = ["get_all_evidence", "get_evidence_by_ids", "get_evidence_by_id"]
