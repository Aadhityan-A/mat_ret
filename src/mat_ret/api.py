"""User-facing helper functions for fetching materials data."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .databases import (
    AFLOWClient,
    AlexandriaClient,
    JARVISClient,
    MPDSClient,
    MaterialsCloudClient,
    MaterialsDatabaseRetriever,
    MaterialsProjectClient,
    OQMDClient,
)


def _sanitize_output_directory(output_directory: Optional[Path]) -> Optional[Path]:
    return Path(output_directory).expanduser() if output_directory else None


def fetch_materials_project(
    formula: str,
    *,
    api_key: str,
    limit: int = 10,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the Materials Project database."""
    if not api_key:
        raise ValueError("Materials Project API key is required")

    client = MaterialsProjectClient(api_key, output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit)


def fetch_jarvis(
    formula: str,
    *,
    limit: int = 10,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the JARVIS database."""
    client = JARVISClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit)


def fetch_aflow(
    formula: str,
    *,
    limit: int = 10,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the AFLOW database."""
    client = AFLOWClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit)


def fetch_alexandria(
    formula: str,
    *,
    limit: int = 10,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the Alexandria database."""
    client = AlexandriaClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit)


def fetch_materials_cloud(
    formula: str,
    *,
    limit: int = 10,
    output_directory: Optional[Path] = None,
    mp_api_key: Optional[str] = None,
) -> List[Dict]:
    """Retrieve structures from the Materials Cloud archive."""
    client = MaterialsCloudClient(
        output_directory=_sanitize_output_directory(output_directory),
        mp_api_key=mp_api_key,
    )
    return client.get_structures(formula, limit=limit)


def fetch_oqmd(
    formula: str,
    *,
    limit: int = 10,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the OQMD database."""
    client = OQMDClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit)


def fetch_mpds(
    formula: str,
    *,
    api_key: str,
    limit: int = 10,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the MPDS database."""
    # MPDS API key is optional; use empty string if not provided
    api_key = api_key or ""
    client = MPDSClient(api_key, output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit)


def fetch_all_databases(
    formula: str,
    *,
    limit_per_database: int = 3,
    mp_api_key: Optional[str] = None,
    mpds_api_key: Optional[str] = None,
    output_directory: Optional[Path] = None,
) -> Dict[str, List[Dict]]:
    """Retrieve structures from every available database client."""
    retriever = MaterialsDatabaseRetriever(
        mp_api_key=mp_api_key,
        mpds_api_key=mpds_api_key,
        output_directory=_sanitize_output_directory(output_directory),
    )
    return retriever.retrieve_materials(formula, limit_per_db=limit_per_database)
