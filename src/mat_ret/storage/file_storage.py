"""File-based storage backend (default) — wraps existing JSON + CIF save logic."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import StorageBackend

logger = logging.getLogger(__name__)


def _serialize_value(value: Any) -> Any:
    """Make a value JSON-serializable."""
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "__dict__") and not isinstance(value, (int, float, str, bool, list, dict, type(None))):
        return str(value)
    return value


class FileStorage(StorageBackend):
    """Stores materials as individual JSON files alongside their CIF files.

    This is the **default** backend that mirrors the original mat_ret
    behaviour.  An ``_index.json`` manifest in the output directory tracks
    all records for querying.
    """

    def __init__(self, output_directory: Optional[Path] = None):
        self.output_dir = Path(output_directory) if output_directory else (Path.cwd() / "downloaded_materials")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.output_dir / "_storage_index.json"
        self._index: Dict[str, Dict[str, Any]] = self._load_index()

    # -- index helpers ---------------------------------------------------------

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        if self._index_path.exists():
            try:
                with open(self._index_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt storage index — starting fresh")
        return {}

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as fh:
            json.dump(self._index, fh, indent=2, default=str)

    # -- StorageBackend implementation -----------------------------------------

    def save_material(self, material: Dict[str, Any], *, search_query: Optional[str] = None) -> str:
        record_id = str(uuid.uuid4())
        cleaned: Dict[str, Any] = {}
        for k, v in material.items():
            if k == "structure":
                continue  # CIF path stored separately
            cleaned[k] = _serialize_value(v)
        cleaned["_record_id"] = record_id
        if search_query:
            cleaned["_search_query"] = search_query

        # Write individual JSON
        json_path = self.output_dir / f"{record_id}.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(cleaned, fh, indent=2, default=str)

        # Update index (lightweight summary)
        self._index[record_id] = {
            "formula": cleaned.get("formula", ""),
            "material_id": cleaned.get("material_id", ""),
            "source_database": cleaned.get("source_database", ""),
            "cif_path": cleaned.get("cif_path", ""),
            "space_group_number": cleaned.get("space_group_number"),
            "crystal_system": cleaned.get("crystal_system", ""),
            "band_gap": cleaned.get("band_gap"),
            "elements": cleaned.get("elements", []),
            "search_query": search_query or "",
            "json_path": str(json_path),
        }
        self._save_index()
        return record_id

    def get_material(self, record_id: str) -> Optional[Dict[str, Any]]:
        entry = self._index.get(record_id)
        if entry is None:
            return None
        json_path = Path(entry.get("json_path", ""))
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        return dict(entry, _record_id=record_id)

    def query_materials(
        self,
        *,
        formula: Optional[str] = None,
        source_database: Optional[str] = None,
        elements: Optional[List[str]] = None,
        space_group_number: Optional[int] = None,
        crystal_system: Optional[str] = None,
        band_gap_min: Optional[float] = None,
        band_gap_max: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        for rid, entry in self._index.items():
            if formula and entry.get("formula", "").lower() != formula.lower():
                continue
            if source_database and entry.get("source_database", "").lower() != source_database.lower():
                continue
            if elements:
                mat_elems = {e.lower() for e in (entry.get("elements") or [])}
                if not all(e.lower() in mat_elems for e in elements):
                    continue
            if space_group_number is not None and entry.get("space_group_number") != space_group_number:
                continue
            if crystal_system and (entry.get("crystal_system") or "").lower() != crystal_system.lower():
                continue
            bg = entry.get("band_gap")
            if band_gap_min is not None and (bg is None or bg < band_gap_min):
                continue
            if band_gap_max is not None and (bg is None or bg > band_gap_max):
                continue
            matches.append(dict(entry, _record_id=rid))
        return matches[offset: offset + limit]

    def list_materials(self, *, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        items = list(self._index.items())
        sliced = items[offset: offset + limit]
        return [dict(v, _record_id=k) for k, v in sliced]

    def delete_material(self, record_id: str) -> bool:
        entry = self._index.pop(record_id, None)
        if entry is None:
            return False
        json_path = Path(entry.get("json_path", ""))
        if json_path.exists():
            json_path.unlink(missing_ok=True)
        self._save_index()
        return True

    def count_materials(self, *, source_database: Optional[str] = None) -> int:
        if source_database is None:
            return len(self._index)
        return sum(
            1 for e in self._index.values()
            if (e.get("source_database") or "").lower() == source_database.lower()
        )

    def search_by_formula(self, formula: str) -> List[Dict[str, Any]]:
        return self.query_materials(formula=formula)

    def search_by_elements(self, elements: List[str]) -> List[Dict[str, Any]]:
        return self.query_materials(elements=elements)

    def get_cif_path(self, record_id: str) -> Optional[str]:
        entry = self._index.get(record_id)
        if entry is None:
            return None
        return entry.get("cif_path") or None
