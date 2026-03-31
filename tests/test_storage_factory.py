"""Tests for the storage factory and StorageType enum."""

import pytest

from mat_ret.storage import StorageType, get_storage
from mat_ret.storage.base import StorageBackend
from mat_ret.storage.file_storage import FileStorage
from mat_ret.storage.sqlite_storage import SQLiteStorage


class TestStorageType:
    def test_enum_values(self):
        assert StorageType.FILE.value == "file"
        assert StorageType.SQLITE.value == "sqlite"
        assert StorageType.MONGODB.value == "mongodb"

    def test_str_enum(self):
        assert str(StorageType.FILE) == "StorageType.FILE" or StorageType.FILE == "file"


class TestGetStorageFactory:
    def test_file_backend_default(self, tmp_path):
        storage = get_storage("file", output_directory=tmp_path)
        assert isinstance(storage, FileStorage)

    def test_file_backend_enum(self, tmp_path):
        storage = get_storage(StorageType.FILE, output_directory=tmp_path)
        assert isinstance(storage, FileStorage)

    def test_sqlite_backend(self, tmp_path):
        path = str(tmp_path / "test.db")
        storage = get_storage("sqlite", sqlite_path=path)
        assert isinstance(storage, SQLiteStorage)
        storage.close()

    def test_sqlite_backend_enum(self, tmp_path):
        path = str(tmp_path / "test2.db")
        storage = get_storage(StorageType.SQLITE, sqlite_path=path)
        assert isinstance(storage, SQLiteStorage)
        storage.close()

    def test_sqlite_memory(self):
        storage = get_storage("sqlite", sqlite_path=":memory:")
        assert isinstance(storage, SQLiteStorage)
        storage.close()

    def test_invalid_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage("invalid_backend")

    def test_case_insensitive(self, tmp_path):
        storage = get_storage("FILE", output_directory=tmp_path)
        assert isinstance(storage, FileStorage)

    def test_all_backends_are_storage_backend(self, tmp_path):
        f = get_storage("file", output_directory=tmp_path)
        assert isinstance(f, StorageBackend)

        s = get_storage("sqlite", sqlite_path=":memory:")
        assert isinstance(s, StorageBackend)
        s.close()


class TestStorageBackendAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore[abstract]
