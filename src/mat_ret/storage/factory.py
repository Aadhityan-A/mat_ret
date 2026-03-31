"""Factory for creating storage backend instances."""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Any, Optional

from .base import StorageBackend


class StorageType(str, enum.Enum):
    """Supported storage backend types."""

    FILE = "file"
    SQLITE = "sqlite"
    MONGODB = "mongodb"


def get_storage(
    backend: str | StorageType = StorageType.FILE,
    *,
    output_directory: Optional[Path] = None,
    sqlite_path: Optional[str] = None,
    mongodb_uri: Optional[str] = None,
    mongodb_db_name: Optional[str] = None,
    **kwargs: Any,
) -> StorageBackend:
    """Create and return a storage backend instance.

    Parameters
    ----------
    backend:
        One of ``"file"``, ``"sqlite"``, or ``"mongodb"``.
    output_directory:
        Directory for file-based storage.
    sqlite_path:
        Path for SQLite database file.
    mongodb_uri:
        MongoDB connection URI.
    mongodb_db_name:
        MongoDB database name.

    Returns
    -------
    StorageBackend
        Configured storage instance.

    Raises
    ------
    ValueError
        If *backend* is not a recognised storage type.
    """
    if isinstance(backend, str):
        try:
            backend = StorageType(backend.lower())
        except ValueError:
            raise ValueError(
                f"Unknown storage backend {backend!r}. "
                f"Choose from: {', '.join(t.value for t in StorageType)}"
            )

    if backend == StorageType.FILE:
        from .file_storage import FileStorage
        return FileStorage(output_directory=output_directory)

    if backend == StorageType.SQLITE:
        from .sqlite_storage import SQLiteStorage
        return SQLiteStorage(db_path=sqlite_path)

    if backend == StorageType.MONGODB:
        from .mongo_storage import MongoDBStorage
        kw: dict[str, Any] = {}
        if mongodb_uri:
            kw["uri"] = mongodb_uri
        if mongodb_db_name:
            kw["db_name"] = mongodb_db_name
        return MongoDBStorage(**kw)

    raise ValueError(f"Unhandled storage type: {backend}")  # pragma: no cover
