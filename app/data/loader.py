"""Loader for deterministic factual evidence base."""
import json
from pathlib import Path
from typing import List, Optional, Dict
from app.models import EvidenceItem

_EVIDENCE_FILE = Path(__file__).parent / "evidence.json"
_CACHE: Optional[Dict[str, EvidenceItem]] = None


def _load_cache() -> Dict[str, EvidenceItem]:
    global _CACHE
    if _CACHE is None:
        if not _EVIDENCE_FILE.exists():
            raise FileNotFoundError(f"Evidence dataset missing at {_EVIDENCE_FILE}")
        with open(_EVIDENCE_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        _CACHE = {
            item["source_id"]: EvidenceItem(
                source_id=item["source_id"],
                title=item["title"],
                content=item["content"]
            )
            for item in raw_data
        }
    return _CACHE


def get_all_evidence() -> List[EvidenceItem]:
    """Return all available evidence records."""
    cache = _load_cache()
    return list(cache.values())


def get_evidence_by_id(source_id: str) -> Optional[EvidenceItem]:
    """Retrieve a single evidence item by source ID."""
    cache = _load_cache()
    return cache.get(source_id)


def get_evidence_by_ids(source_ids: List[str]) -> List[EvidenceItem]:
    """Retrieve a subset of evidence items by source IDs in the order requested."""
    cache = _load_cache()
    results = []
    for sid in source_ids:
        if sid in cache:
            results.append(cache[sid])
        else:
            raise KeyError(f"Evidence source_id '{sid}' not found in trusted knowledge base.")
    return results


def reload_cache() -> None:
    """Force reload evidence from disk (used primarily in tests)."""
    global _CACHE
    _CACHE = None
    _load_cache()
