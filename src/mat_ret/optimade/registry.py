"""OPTIMADE provider registry utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


def _ensure_links_url(registry_url: str) -> str:
    base = registry_url.rstrip("/")
    if base.endswith("/v1/links"):
        return base
    if base.endswith("/v1"):
        return f"{base}/links"
    return f"{base}/v1/links"


def _load_cache(cache_path: Path) -> Optional[List[Dict[str, str]]]:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, list):
        return None
    return [item for item in payload if isinstance(item, dict)]


def _save_cache(cache_path: Path, providers: List[Dict[str, str]]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(providers, handle, indent=2)
    except OSError:
        return


def _normalize_provider_id(raw_id: Optional[str], base_url: Optional[str]) -> Optional[str]:
    if raw_id:
        return raw_id.strip()
    if not base_url:
        return None
    parsed = urlparse(base_url)
    if parsed.netloc:
        return parsed.netloc.replace(":", "_")
    return None


def _filter_providers(
    providers: List[Dict[str, str]],
    include: Optional[List[str]],
    exclude: Optional[List[str]],
    max_providers: Optional[int],
) -> List[Dict[str, str]]:
    filtered = providers

    if include:
        include_set = {item.strip() for item in include if item.strip()}
        if include_set:
            filtered = [p for p in filtered if p.get("id") in include_set]

    if exclude:
        exclude_set = {item.strip() for item in exclude if item.strip()}
        if exclude_set:
            filtered = [p for p in filtered if p.get("id") not in exclude_set]

    if max_providers is not None:
        filtered = filtered[: max(0, max_providers)]

    return filtered


def _extract_providers(payload: Dict[str, Any]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    providers: List[Dict[str, str]] = []
    externals: List[Dict[str, str]] = []

    data = payload.get("data", []) if isinstance(payload, dict) else []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        attributes = entry.get("attributes", {}) if isinstance(entry.get("attributes"), dict) else {}
        link_type = attributes.get("link_type")
        base_url = attributes.get("base_url")
        if not base_url:
            continue

        provider_id = _normalize_provider_id(entry.get("id"), base_url)
        if not provider_id:
            continue

        record = {
            "id": provider_id,
            "base_url": base_url.rstrip("/"),
            "name": attributes.get("name", "") or provider_id,
        }

        if link_type == "child":
            providers.append(record)
        elif link_type in {"external", "root"}:
            externals.append(record)

    return providers, externals


def _fetch_index_children(index_url: str, request_timeout: int) -> List[Dict[str, str]]:
    links_url = _ensure_links_url(index_url)
    response = requests.get(links_url, timeout=request_timeout)
    response.raise_for_status()
    payload = response.json()
    providers, _ = _extract_providers(payload)
    return providers


def _dedupe_providers(providers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen_ids = set()
    seen_urls = set()
    deduped: List[Dict[str, str]] = []
    for provider in providers:
        provider_id = provider.get("id")
        base_url = provider.get("base_url")
        if provider_id and provider_id in seen_ids:
            continue
        if base_url and base_url in seen_urls:
            continue
        if provider_id:
            seen_ids.add(provider_id)
        if base_url:
            seen_urls.add(base_url)
        deduped.append(provider)
    return deduped


def fetch_registry_links(
    registry_url: str,
    *,
    cache_path: Optional[Path] = None,
    request_timeout: int = 30,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    max_providers: Optional[int] = None,
) -> List[Dict[str, str]]:
    """Fetch provider list from the OPTIMADE registry.

    Returns a list of dictionaries with keys: id, base_url, name.
    """
    cache_path = cache_path.expanduser() if cache_path else None

    links_url = _ensure_links_url(registry_url)

    try:
        response = requests.get(links_url, timeout=request_timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        if cache_path:
            cached = _load_cache(cache_path)
            if cached is not None:
                return _filter_providers(cached, include, exclude, max_providers)
        raise RuntimeError(f"Failed to retrieve OPTIMADE registry: {exc}") from exc

    providers, externals = _extract_providers(payload)

    for external in externals:
        base_url = external.get("base_url")
        if not base_url:
            continue
        try:
            child_providers = _fetch_index_children(base_url, request_timeout)
        except Exception:
            child_providers = []

        if child_providers:
            providers.extend(child_providers)
        else:
            providers.append(external)

    providers = _dedupe_providers(providers)

    if cache_path:
        _save_cache(cache_path, providers)

    return _filter_providers(providers, include, exclude, max_providers)
