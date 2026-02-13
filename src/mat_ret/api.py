"""User-facing helper functions for fetching materials data."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

from .databases import (
    AFLOWClient,
    AlexandriaClient,
    JARVISClient,
    MPDSClient,
    MaterialsCloudClient,
    MaterialsDatabaseRetriever,
    MaterialsProjectClient,
    OQMDClient,
    OptimadeSearchClient,
)
from .optimade.harvester import OptimadeHarvester
from .optimade.registry import fetch_registry_links
from .xrd import (
    XRDConfig,
    XRDResult,
    generate_xrd_from_cif,
    generate_xrd_from_structure,
    list_supported_radiations,
)


def _sanitize_output_directory(output_directory: Optional[Path]) -> Optional[Path]:
    return Path(output_directory).expanduser() if output_directory else None


def fetch_materials_project(
    formula: str,
    *,
    api_key: str,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the Materials Project database."""
    if not api_key:
        raise ValueError("Materials Project API key is required")

    client = MaterialsProjectClient(api_key, output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements)


def fetch_jarvis(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the JARVIS database."""
    client = JARVISClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements)


def fetch_aflow(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the AFLOW database."""
    client = AFLOWClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements)


def fetch_alexandria(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the Alexandria database."""
    client = AlexandriaClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements)


def fetch_materials_cloud(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    mp_api_key: Optional[str] = None,
) -> List[Dict]:
    """Retrieve structures from the Materials Cloud archive."""
    client = MaterialsCloudClient(
        output_directory=_sanitize_output_directory(output_directory),
        mp_api_key=mp_api_key,
    )
    return client.get_structures(formula, limit=limit, elements=elements)


def fetch_oqmd(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the OQMD database."""
    client = OQMDClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements)


def fetch_mpds(
    formula: str,
    *,
    api_key: str,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
) -> List[Dict]:
    """Retrieve structures from the MPDS database."""
    # MPDS API key is optional; use empty string if not provided
    api_key = api_key or ""
    client = MPDSClient(api_key, output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements)


def fetch_optimade(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    registry_url: Optional[str] = None,
    providers: Optional[List[Dict[str, str]]] = None,
) -> List[Dict]:
    """Retrieve structures from OPTIMADE providers."""
    client = OptimadeSearchClient(
        output_directory=_sanitize_output_directory(output_directory),
        registry_url=registry_url,
        providers=providers,
    )
    return client.get_structures(formula, limit=limit, elements=elements)


def list_optimade_providers(
    registry_url: Optional[str] = None,
    cache_path: Optional[Path] = None,
) -> List[Dict]:
    """List OPTIMADE providers from the registry."""
    if registry_url is None:
        try:
            import config  # type: ignore

            registry_url = getattr(config, "OPTIMADE_REGISTRY_URL", None)
        except ImportError:
            registry_url = None
    if not registry_url:
        raise ValueError("OPTIMADE registry URL is required")

    return fetch_registry_links(
        registry_url,
        cache_path=cache_path,
    )


def harvest_optimade(
    output_directory: Path,
    *,
    registry_url: Optional[str] = None,
    include_providers: Optional[List[str]] = None,
    exclude_providers: Optional[List[str]] = None,
    page_limit: int = 1000,
    shard_size: int = 5000,
    resume: bool = True,
    request_timeout: int = 30,
    rate_limit_per_host: float = 1.0,
) -> None:
    """Harvest all OPTIMADE providers into CIF + metadata shards."""
    if registry_url is None:
        try:
            import config  # type: ignore

            registry_url = getattr(config, "OPTIMADE_REGISTRY_URL", None)
        except ImportError:
            registry_url = None
    if not registry_url:
        raise ValueError("OPTIMADE registry URL is required")

    providers = fetch_registry_links(
        registry_url,
        include=include_providers,
        exclude=exclude_providers,
        request_timeout=request_timeout,
    )

    harvester = OptimadeHarvester(
        providers,
        Path(output_directory),
        page_limit=page_limit,
        shard_size=shard_size,
        resume=resume,
        request_timeout=request_timeout,
        rate_limit_per_host=rate_limit_per_host,
    )
    harvester.harvest()


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


def generate_xrd_pattern_from_structure(
    structure,
    *,
    config: Optional[XRDConfig] = None,
) -> XRDResult:
    """Generate an XRD pattern from a pymatgen Structure."""
    return generate_xrd_from_structure(structure, config=config)


def generate_xrd_pattern_from_cif(
    cif_path: Union[Path, str],
    *,
    config: Optional[XRDConfig] = None,
) -> XRDResult:
    """Generate an XRD pattern from a CIF file path."""
    return generate_xrd_from_cif(cif_path, config=config)


def list_xrd_radiations() -> List[str]:
    """List supported XRD radiation presets."""
    return list_supported_radiations()
