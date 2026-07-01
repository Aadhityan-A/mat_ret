"""SQLite storage backend — zero-dependency, serverless."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import StorageBackend

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS materials (
    record_id       TEXT PRIMARY KEY,
    material_id     TEXT,
    formula         TEXT,
    source_database TEXT,
    cif_path        TEXT,
    space_group     TEXT,
    space_group_number INTEGER,
    crystal_system  TEXT,
    band_gap        REAL,
    formation_energy REAL,
    formation_energy_per_atom REAL,
    energy_per_atom REAL,
    energy_above_hull REAL,
    density         REAL,
    volume          REAL,
    bulk_modulus    REAL,
    shear_modulus   REAL,
    magnetic_moment REAL,
    is_metallic     INTEGER,
    elements        TEXT,       -- JSON array
    search_query    TEXT,
    raw_data        TEXT,       -- full JSON blob
    created_at      TEXT
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_formula ON materials(formula);",
    "CREATE INDEX IF NOT EXISTS idx_source_database ON materials(source_database);",
    "CREATE INDEX IF NOT EXISTS idx_space_group_number ON materials(space_group_number);",
    "CREATE INDEX IF NOT EXISTS idx_crystal_system ON materials(crystal_system);",
    "CREATE INDEX IF NOT EXISTS idx_band_gap ON materials(band_gap);",
    "CREATE INDEX IF NOT EXISTS idx_created_at ON materials(created_at);",
]

_META_TABLE = """
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "__dict__") and not isinstance(value, (int, float, str, bool, list, dict, type(None))):
        return str(value)
    return value


class SQLiteStorage(StorageBackend):
    """SQLite-backed storage for materials data.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Defaults to
        ``downloaded_materials/mat_ret.db`` in the current directory.
        Use ``":memory:"`` for an in-memory database (useful for testing).
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path.cwd() / "downloaded_materials"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "mat_ret.db")
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._ensure_schema()

    # -- schema ----------------------------------------------------------------

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(_META_TABLE)
        cur.executescript(_CREATE_TABLE)
        for idx in _CREATE_INDEXES:
            cur.execute(idx)
        cur.execute(
            "INSERT OR IGNORE INTO _meta (key, value) VALUES (?, ?)",
            ("schema_version", str(_SCHEMA_VERSION)),
        )
        self._conn.commit()

    # -- StorageBackend implementation -----------------------------------------

    def save_material(self, material: Dict[str, Any], *, search_query: Optional[str] = None) -> str:
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Serialize full data for raw_data column
        raw: Dict[str, Any] = {}
        for k, v in material.items():
            if k == "structure":
                continue
            raw[k] = _serialize_value(v)

        elements = material.get("elements", [])
        if isinstance(elements, (list, tuple)):
            elements_json = json.dumps(list(elements))
        else:
            elements_json = json.dumps([])

        is_metallic = material.get("is_metallic")
        if isinstance(is_metallic, bool):
            is_metallic = int(is_metallic)

        self._conn.execute(
            """INSERT INTO materials (
                record_id, material_id, formula, source_database, cif_path,
                space_group, space_group_number, crystal_system,
                band_gap, formation_energy, formation_energy_per_atom,
                energy_per_atom, energy_above_hull, density, volume,
                bulk_modulus, shear_modulus, magnetic_moment, is_metallic,
                elements, search_query, raw_data, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record_id,
                str(material.get("material_id", "")),
                material.get("formula", ""),
                material.get("source_database", ""),
                material.get("cif_path", ""),
                material.get("space_group", ""),
                _to_int(material.get("space_group_number")),
                material.get("crystal_system", ""),
                _to_float(material.get("band_gap")),
                _to_float(material.get("formation_energy")),
                _to_float(material.get("formation_energy_per_atom")),
                _to_float(material.get("energy_per_atom")),
                _to_float(material.get("energy_above_hull")),
                _to_float(material.get("density")),
                _to_float(material.get("volume")),
                _to_float(material.get("bulk_modulus")),
                _to_float(material.get("shear_modulus")),
                _to_float(material.get("magnetic_moment")),
                _to_int(is_metallic),
                elements_json,
                search_query or "",
                json.dumps(raw, default=str),
                now,
            ),
        )
        self._conn.commit()
        return record_id

    def get_material(self, record_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute("SELECT * FROM materials WHERE record_id = ?", (record_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

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
        filters: Optional[Any] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []

        if formula is not None:
            clauses.append("LOWER(formula) = LOWER(?)")
            params.append(formula)
        if source_database is not None:
            clauses.append("LOWER(source_database) = LOWER(?)")
            params.append(source_database)
        if space_group_number is not None:
            clauses.append("space_group_number = ?")
            params.append(space_group_number)
        if crystal_system is not None:
            clauses.append("LOWER(crystal_system) = LOWER(?)")
            params.append(crystal_system)
        if band_gap_min is not None:
            clauses.append("band_gap >= ?")
            params.append(band_gap_min)
        if band_gap_max is not None:
            clauses.append("band_gap <= ?")
            params.append(band_gap_max)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        # When element membership or a SearchFilters object must be applied in
        # Python, we cannot push LIMIT/OFFSET into SQL (it would truncate before
        # the post-filter runs).  Fetch the candidate set, post-filter, then page.
        needs_post = bool(elements) or (filters is not None and filters.has_any_filter())

        if not needs_post:
            sql = f"SELECT * FROM materials{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
            cur = self._conn.execute(sql, [*params, limit, offset])
            return [self._row_to_dict(r) for r in cur.fetchall()]

        sql = f"SELECT * FROM materials{where} ORDER BY created_at DESC"
        cur = self._conn.execute(sql, params)
        results = [self._hoist_computed(self._row_to_dict(r)) for r in cur.fetchall()]

        if elements:
            needed = {e.lower() for e in elements}
            results = [
                r for r in results
                if needed.issubset({str(e).lower() for e in (r.get("elements") or [])})
            ]
        if filters is not None and filters.has_any_filter():
            from ..search import apply_post_filters
            from ..property_mapping import STANDARD_PROPERTIES
            results = apply_post_filters(results, filters, STANDARD_PROPERTIES)

        return results[offset: offset + limit]

    def list_materials(self, *, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM materials ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def delete_material(self, record_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM materials WHERE record_id = ?", (record_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def count_materials(self, *, source_database: Optional[str] = None) -> int:
        if source_database is None:
            cur = self._conn.execute("SELECT COUNT(*) FROM materials")
        else:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM materials WHERE LOWER(source_database) = LOWER(?)",
                (source_database,),
            )
        return cur.fetchone()[0]

    def search_by_formula(self, formula: str) -> List[Dict[str, Any]]:
        return self.query_materials(formula=formula)

    def search_by_elements(self, elements: List[str]) -> List[Dict[str, Any]]:
        return self.query_materials(elements=elements)

    def get_cif_path(self, record_id: str) -> Optional[str]:
        cur = self._conn.execute("SELECT cif_path FROM materials WHERE record_id = ?", (record_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return row["cif_path"] or None

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _hoist_computed(mat: Dict[str, Any]) -> Dict[str, Any]:
        """Lift computed keys (num_sites/num_elements/elements) out of raw_data.

        These are not promoted to dedicated columns, so ``apply_post_filters``
        needs them surfaced at the top level to filter on.
        """
        raw = mat.get("raw_data")
        if isinstance(raw, dict):
            for key in ("num_sites", "num_elements", "elements"):
                if mat.get(key) in (None, "", []) and raw.get(key) is not None:
                    mat[key] = raw[key]
        return mat

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        # Deserialize elements JSON
        if "elements" in d and isinstance(d["elements"], str):
            try:
                d["elements"] = json.loads(d["elements"])
            except (json.JSONDecodeError, TypeError):
                d["elements"] = []
        # Deserialize raw_data
        if "raw_data" in d and isinstance(d["raw_data"], str):
            try:
                d["raw_data"] = json.loads(d["raw_data"])
            except (json.JSONDecodeError, TypeError):
                pass
        # Convert is_metallic back to bool
        if d.get("is_metallic") is not None:
            d["is_metallic"] = bool(d["is_metallic"])
        return d
