"""Abstract base class for storage backends."""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class StorageBackend(abc.ABC):
    """Interface that every storage backend must implement."""

    @abc.abstractmethod
    def save_material(self, material: Dict[str, Any], *, search_query: Optional[str] = None) -> str:
        """Persist one material record.

        Parameters
        ----------
        material:
            Dictionary of standard property keys plus optional ``cif_path``
            and ``source_database`` values.
        search_query:
            The search query that produced this material (for provenance).

        Returns
        -------
        str
            A unique identifier for the stored record.
        """

    @abc.abstractmethod
    def get_material(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single material by its stored record ID."""

    @abc.abstractmethod
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
        """Query stored materials with optional filters.

        Returns a list of material dictionaries.
        """

    @abc.abstractmethod
    def list_materials(self, *, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Return all stored materials with pagination."""

    @abc.abstractmethod
    def delete_material(self, record_id: str) -> bool:
        """Delete a stored material.  Returns True if deleted."""

    @abc.abstractmethod
    def count_materials(self, *, source_database: Optional[str] = None) -> int:
        """Count stored materials, optionally filtered by source database."""

    @abc.abstractmethod
    def search_by_formula(self, formula: str) -> List[Dict[str, Any]]:
        """Return materials whose formula matches *formula*."""

    @abc.abstractmethod
    def search_by_elements(self, elements: List[str]) -> List[Dict[str, Any]]:
        """Return materials containing **all** supplied elements."""

    @abc.abstractmethod
    def get_cif_path(self, record_id: str) -> Optional[str]:
        """Return the CIF file path for a stored material."""

    def close(self) -> None:
        """Release any resources (connections, file handles)."""

    # Convenience ----------------------------------------------------------------

    def save_many(self, materials: List[Dict[str, Any]], *, search_query: Optional[str] = None) -> List[str]:
        """Persist multiple materials. Returns list of record IDs."""
        return [self.save_material(m, search_query=search_query) for m in materials]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
