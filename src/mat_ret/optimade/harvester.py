"""OPTIMADE harvesting implementation."""

from __future__ import annotations

import io
import json
import logging
import os
import re
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

import requests
from urllib3.util.retry import Retry

try:
    import zstandard as zstd
except ImportError as exc:  # pragma: no cover - handled at runtime
    zstd = None

try:
    from optimade.adapters.structures import Structure as OptimadeStructure
    from optimade.adapters.exceptions import ConversionError as OptimadeConversionError
except ImportError:
    OptimadeStructure = None
    OptimadeConversionError = Exception

from pymatgen.io.cif import CifWriter
from pymatgen.core.structure import Structure as PymatgenStructure

logger = logging.getLogger(__name__)


@dataclass
class HarvestProgress:
    provider_id: str
    harvested: int
    shard_index: int
    message: str


class TarZstdShardWriter:
    """Stream a tar.zst shard to disk."""

    def __init__(self, target_path: Path, compression_level: int = 3):
        if zstd is None:
            raise RuntimeError("zstandard is required to write .tar.zst archives")

        self.target_path = target_path
        self.temp_path = target_path.with_suffix(target_path.suffix + ".part")
        self.temp_path.parent.mkdir(parents=True, exist_ok=True)
        self._closed = False

        self._file = self.temp_path.open("wb")
        try:
            self._compressor = zstd.ZstdCompressor(level=compression_level)
            self._stream = self._compressor.stream_writer(self._file)
            self._tar = tarfile.open(fileobj=self._stream, mode="w|")
        except Exception:
            self._file.close()
            raise

    def add_bytes(self, arcname: str, payload: bytes) -> None:
        info = tarfile.TarInfo(name=arcname)
        info.size = len(payload)
        info.mtime = int(time.time())
        self._tar.addfile(info, io.BytesIO(payload))

    def close(self) -> None:
        if self._closed:
            return
        self._tar.close()
        self._stream.close()
        self._file.close()
        os.replace(self.temp_path, self.target_path)
        self._closed = True

    def abort(self) -> None:
        if self._closed:
            return
        try:
            self._tar.close()
        except Exception:
            pass
        try:
            self._stream.close()
        except Exception:
            pass
        try:
            self._file.close()
        except Exception:
            pass
        try:
            if self.temp_path.exists():
                self.temp_path.unlink()
        except OSError:
            pass
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed


class OptimadeHarvester:
    """Harvest structures from OPTIMADE providers."""

    def __init__(
        self,
        providers: List[Dict[str, str]],
        output_directory: Path,
        *,
        page_limit: int = 1000,
        shard_size: int = 5000,
        resume: bool = True,
        request_timeout: int = 30,
        rate_limit_per_host: float = 1.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.providers = providers
        self.output_directory = Path(output_directory).expanduser()
        self.page_limit = max(1, page_limit)
        self.shard_size = max(1, shard_size)
        self.resume = resume
        self.request_timeout = max(1, request_timeout)
        self.rate_limit_per_host = max(0.0, rate_limit_per_host)
        self._last_request_time: Dict[str, float] = {}

        if session is None:
            session = requests.Session()
            retry = Retry(
                total=5,
                backoff_factor=1,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",),
                respect_retry_after_header=True,
            )
            adapter = requests.adapters.HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            self._owns_session = True
        else:
            self._owns_session = False
        self.session = session

    def close(self) -> None:
        """Close the underlying HTTP session if we own it."""
        if self._owns_session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def harvest(
        self,
        *,
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[HarvestProgress], None]] = None,
    ) -> None:
        for provider in self.providers:
            self._harvest_provider(provider, status_callback, progress_callback)

    def _harvest_provider(
        self,
        provider: Dict[str, str],
        status_callback: Optional[Callable[[str], None]],
        progress_callback: Optional[Callable[[HarvestProgress], None]],
    ) -> None:
        provider_id = provider.get("id") or "unknown"
        base_url = provider.get("base_url")
        if not base_url:
            if status_callback:
                status_callback(f"Skipping {provider_id}: missing base_url")
            return

        provider_dir = self.output_directory / "optimade" / provider_id
        shards_dir = provider_dir / "shards"
        state_path = provider_dir / "state.json"
        provider_dir.mkdir(parents=True, exist_ok=True)
        shards_dir.mkdir(parents=True, exist_ok=True)

        state = self._load_state(state_path)
        if state.get("complete"):
            if status_callback:
                status_callback(f"Provider {provider_id} already complete. Skipping.")
            return

        next_url = state.get("next_url")
        if not next_url:
            next_url = self._build_structures_url(base_url, self.page_limit, 0)

        shard_index = int(state.get("shard_index", 1))
        total_harvested = int(state.get("total_harvested", 0))

        # Clean up any partial shards from previous runs.
        self._cleanup_partial_shards(shards_dir, provider_id)

        current_shard_count = 0
        shard_writer = self._open_shard_writer(shards_dir, provider_id, shard_index)

        try:
            while next_url:
                if status_callback:
                    status_callback(f"Harvesting {provider_id}: fetching {next_url}")

                payload = self._fetch_json(next_url)
                data = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(data, list):
                    if status_callback:
                        status_callback(f"Provider {provider_id}: invalid data payload")
                    shard_writer.abort()
                    return

                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    entry_id = entry.get("id") or f"record_{total_harvested + current_shard_count + 1}"
                    safe_id = _safe_identifier(entry_id)

                    metadata = self._build_metadata(provider, entry)
                    metadata_bytes = json.dumps(metadata, indent=2, default=str).encode("utf-8")
                    metadata_path = f"metadata/{provider_id}/{safe_id}.json"

                    cif_bytes = self._structure_to_cif_bytes(provider_id, entry)
                    cif_path = f"cif/{provider_id}/{safe_id}.cif"

                    shard_writer.add_bytes(metadata_path, metadata_bytes)
                    shard_writer.add_bytes(cif_path, cif_bytes)
                    current_shard_count += 1

                next_url = self._next_page_url(next_url, payload, self.page_limit)

                if current_shard_count >= self.shard_size or not next_url:
                    if current_shard_count == 0:
                        shard_writer.abort()
                        if not next_url:
                            state = {
                                "provider_id": provider_id,
                                "provider_base_url": base_url,
                                "next_url": None,
                                "shard_index": shard_index,
                                "total_harvested": total_harvested,
                                "complete": True,
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }
                            self._write_state(state_path, state)
                    else:
                        shard_writer.close()
                        total_harvested += current_shard_count
                        shard_index += 1

                        state = {
                            "provider_id": provider_id,
                            "provider_base_url": base_url,
                            "next_url": next_url,
                            "shard_index": shard_index,
                            "total_harvested": total_harvested,
                            "complete": next_url is None,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                        self._write_state(state_path, state)

                        if progress_callback:
                            progress_callback(
                                HarvestProgress(
                                    provider_id=provider_id,
                                    harvested=total_harvested,
                                    shard_index=shard_index - 1,
                                    message="Shard complete",
                                )
                            )

                    if not next_url:
                        if status_callback:
                            status_callback(f"Provider {provider_id} complete. Total {total_harvested}")
                        break

                    current_shard_count = 0
                    shard_writer = self._open_shard_writer(shards_dir, provider_id, shard_index)
        finally:
            if shard_writer and not shard_writer.closed:
                shard_writer.abort()

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        self._respect_rate_limit(url)
        response = self.session.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        return response.json()

    def _respect_rate_limit(self, url: str) -> None:
        if self.rate_limit_per_host <= 0:
            return
        host = urlparse(url).netloc
        if not host:
            return
        min_interval = 1.0 / self.rate_limit_per_host
        last_time = self._last_request_time.get(host)
        if last_time is not None:
            elapsed = time.time() - last_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        self._last_request_time[host] = time.time()

    def _build_structures_url(self, base_url: str, page_limit: int, page_offset: int) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/v1"):
            structures_url = f"{base}/structures"
        else:
            structures_url = f"{base}/v1/structures"
        params = {
            "page_limit": str(page_limit),
            "page_offset": str(page_offset),
        }
        return f"{structures_url}?{urlencode(params)}"

    def _next_page_url(self, current_url: str, payload: Dict[str, Any], page_limit: int) -> Optional[str]:
        links = payload.get("links", {}) if isinstance(payload, dict) else {}
        next_link = None
        if isinstance(links, dict):
            next_link = links.get("next")

        if isinstance(next_link, dict):
            href = next_link.get("href")
            if isinstance(href, str) and href:
                return href
        elif isinstance(next_link, str) and next_link:
            return next_link

        # Fallback to page_offset increment when links.next is missing
        meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
        data_returned = meta.get("data_returned") if isinstance(meta, dict) else None
        if not isinstance(data_returned, int) or data_returned <= 0:
            return None

        if data_returned < page_limit:
            return None

        parsed = urlparse(current_url)
        query = parse_qs(parsed.query)
        current_offset = 0
        try:
            if "page_offset" in query:
                current_offset = int(query["page_offset"][0])
        except (ValueError, TypeError, IndexError):
            current_offset = 0

        query["page_offset"] = [str(current_offset + data_returned)]
        new_query = urlencode(query, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    def _open_shard_writer(self, shards_dir: Path, provider_id: str, shard_index: int) -> TarZstdShardWriter:
        shard_name = f"{provider_id}_shard_{shard_index:06d}.tar.zst"
        shard_path = shards_dir / shard_name
        return TarZstdShardWriter(shard_path)

    def _cleanup_partial_shards(self, shards_dir: Path, provider_id: str) -> None:
        pattern = f"{provider_id}_shard_*.tar.zst.part"
        for candidate in shards_dir.glob(pattern):
            try:
                candidate.unlink()
            except OSError:
                pass

    def _build_metadata(self, provider: Dict[str, str], entry: Dict[str, Any]) -> Dict[str, Any]:
        attributes = entry.get("attributes", {}) if isinstance(entry.get("attributes"), dict) else {}
        standard = {
            "material_id": entry.get("id"),
            "formula": attributes.get("chemical_formula_reduced") or attributes.get("chemical_formula_descriptive"),
            "last_modified": attributes.get("last_modified"),
            "source_database": provider.get("id"),
        }
        return {
            "provider_id": provider.get("id"),
            "provider_name": provider.get("name"),
            "provider_base_url": provider.get("base_url"),
            "harvested_at": datetime.now(timezone.utc).isoformat(),
            "standard": standard,
            "optimade": entry,
        }

    def _structure_to_cif_bytes(self, provider_id: str, entry: Dict[str, Any]) -> bytes:
        if OptimadeStructure is None:
            return self._placeholder_cif(provider_id, entry, "optimade.adapters not available")

        try:
            structure = OptimadeStructure(entry).convert("pymatgen")
        except OptimadeConversionError as exc:
            return self._placeholder_cif(provider_id, entry, f"conversion failed: {exc}")
        except Exception as exc:
            return self._placeholder_cif(provider_id, entry, f"conversion error: {exc}")

        if not isinstance(structure, PymatgenStructure):
            return self._placeholder_cif(provider_id, entry, "conversion returned invalid structure")

        try:
            cif_writer = CifWriter(structure)
            return str(cif_writer).encode("utf-8")
        except Exception as exc:
            return self._placeholder_cif(provider_id, entry, f"cif write failed: {exc}")

    def _placeholder_cif(self, provider_id: str, entry: Dict[str, Any], reason: str) -> bytes:
        attributes = entry.get("attributes", {}) if isinstance(entry.get("attributes"), dict) else {}
        lines = [
            "# OPTIMADE CIF placeholder",
            f"# Provider: {provider_id}",
            f"# Structure ID: {entry.get('id', 'unknown')}",
            f"# Formula: {attributes.get('chemical_formula_reduced', 'unknown')}",
            f"# Reason: {reason}",
        ]
        return ("\n".join(lines) + "\n").encode("utf-8")

    def _load_state(self, state_path: Path) -> Dict[str, Any]:
        if not self.resume or not state_path.exists():
            return {}
        try:
            with state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _write_state(self, state_path: Path, state: Dict[str, Any]) -> None:
        try:
            with state_path.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
        except OSError:
            return


def _safe_identifier(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value or "unknown"
