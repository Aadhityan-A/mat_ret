"""MongoDB storage backend — requires ``pymongo`` (optional dependency)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import StorageBackend

logger = logging.getLogger(__name__)

try:
    import pymongo  # type: ignore[import-untyped]
    from pymongo import MongoClient  # type: ignore[import-untyped]
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False
    pymongo = None  # type: ignore[assignment]
    MongoClient = None  # type: ignore[assignment,misc]


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "__dict__") and not isinstance(value, (int, float, str, bool, list, dict, type(None))):
        return str(value)
    return value


class MongoDBStorage(StorageBackend):
    """MongoDB-backed storage for materials data.

    Parameters
    ----------
    uri:
        MongoDB connection string.  Defaults to ``mongodb://localhost:27017``.
    db_name:
        Database name.  Defaults to ``mat_ret``.
    collection_name:
        Collection name.  Defaults to ``materials``.
    """

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        db_name: str = "mat_ret",
        collection_name: str = "materials",
    ):
        if not HAS_PYMONGO:
            raise ImportError(
                "pymongo is required for MongoDB storage. "
                "Install it with: pip install pymongo>=4.0"
            )
        self._uri = uri
        self._client: Any = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._db = self._client[db_name]
        self._collection = self._db[collection_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._collection.create_index("formula")
        self._collection.create_index("source_database")
        self._collection.create_index("space_group_number")
        self._collection.create_index("crystal_system")
        self._collection.create_index("band_gap")
        self._collection.create_index("elements")
        self._collection.create_index("created_at")

    # -- StorageBackend implementation -----------------------------------------

    def save_material(self, material: Dict[str, Any], *, search_query: Optional[str] = None) -> str:
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc: Dict[str, Any] = {"_id": record_id, "created_at": now}
        if search_query:
            doc["search_query"] = search_query

        for k, v in material.items():
            if k == "structure":
                continue
            doc[k] = _serialize_value(v)

        # Ensure elements is a list
        if "elements" in doc and not isinstance(doc["elements"], list):
            doc["elements"] = []

        self._collection.insert_one(doc)
        return record_id

    def get_material(self, record_id: str) -> Optional[Dict[str, Any]]:
        doc = self._collection.find_one({"_id": record_id})
        if doc is None:
            return None
        return self._doc_to_dict(doc)

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
        query: Dict[str, Any] = {}

        if formula is not None:
            query["formula"] = {"$regex": f"^{formula}$", "$options": "i"}
        if source_database is not None:
            query["source_database"] = {"$regex": f"^{source_database}$", "$options": "i"}
        if space_group_number is not None:
            query["space_group_number"] = space_group_number
        if crystal_system is not None:
            query["crystal_system"] = {"$regex": f"^{crystal_system}$", "$options": "i"}
        if band_gap_min is not None or band_gap_max is not None:
            bg_filter: Dict[str, float] = {}
            if band_gap_min is not None:
                bg_filter["$gte"] = band_gap_min
            if band_gap_max is not None:
                bg_filter["$lte"] = band_gap_max
            query["band_gap"] = bg_filter
        if elements:
            query["elements"] = {"$all": [e for e in elements]}

        cursor = (
            self._collection.find(query)
            .sort("created_at", pymongo.DESCENDING)
            .skip(offset)
            .limit(limit)
        )
        return [self._doc_to_dict(doc) for doc in cursor]

    def list_materials(self, *, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        cursor = (
            self._collection.find()
            .sort("created_at", pymongo.DESCENDING)
            .skip(offset)
            .limit(limit)
        )
        return [self._doc_to_dict(doc) for doc in cursor]

    def delete_material(self, record_id: str) -> bool:
        result = self._collection.delete_one({"_id": record_id})
        return result.deleted_count > 0

    def count_materials(self, *, source_database: Optional[str] = None) -> int:
        if source_database is None:
            return self._collection.count_documents({})
        return self._collection.count_documents(
            {"source_database": {"$regex": f"^{source_database}$", "$options": "i"}}
        )

    def search_by_formula(self, formula: str) -> List[Dict[str, Any]]:
        return self.query_materials(formula=formula)

    def search_by_elements(self, elements: List[str]) -> List[Dict[str, Any]]:
        return self.query_materials(elements=elements)

    def get_cif_path(self, record_id: str) -> Optional[str]:
        doc = self._collection.find_one({"_id": record_id}, {"cif_path": 1})
        if doc is None:
            return None
        return doc.get("cif_path") or None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def ping(self) -> bool:
        """Test the MongoDB connection.  Returns True if reachable."""
        try:
            self._client.admin.command("ping")
            return True
        except Exception:
            return False

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _doc_to_dict(doc: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(doc)
        # Rename _id → record_id for consistency
        if "_id" in d:
            d["record_id"] = d.pop("_id")
        return d
