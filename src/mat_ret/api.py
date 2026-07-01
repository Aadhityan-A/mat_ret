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
from .search import SearchFilters
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
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from the Materials Project database."""
    if not api_key:
        raise ValueError("Materials Project API key is required")

    client = MaterialsProjectClient(api_key, output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def fetch_jarvis(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from the JARVIS database."""
    client = JARVISClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def fetch_aflow(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from the AFLOW database."""
    client = AFLOWClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def fetch_alexandria(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from the Alexandria database."""
    client = AlexandriaClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def fetch_materials_cloud(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    mp_api_key: Optional[str] = None,
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from the Materials Cloud archive."""
    client = MaterialsCloudClient(
        output_directory=_sanitize_output_directory(output_directory),
        mp_api_key=mp_api_key,
    )
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def fetch_oqmd(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from the OQMD database."""
    client = OQMDClient(output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def fetch_mpds(
    formula: str,
    *,
    api_key: str,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from the MPDS database."""
    # MPDS API key is optional; use empty string if not provided
    api_key = api_key or ""
    client = MPDSClient(api_key, output_directory=_sanitize_output_directory(output_directory))
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def fetch_optimade(
    formula: str,
    *,
    limit: int = 10,
    elements: Optional[List[str]] = None,
    output_directory: Optional[Path] = None,
    registry_url: Optional[str] = None,
    providers: Optional[List[Dict[str, str]]] = None,
    filters: Optional[SearchFilters] = None,
) -> List[Dict]:
    """Retrieve structures from OPTIMADE providers."""
    client = OptimadeSearchClient(
        output_directory=_sanitize_output_directory(output_directory),
        registry_url=registry_url,
        providers=providers,
    )
    return client.get_structures(formula, limit=limit, elements=elements, filters=filters)


def list_optimade_providers(
    registry_url: Optional[str] = None,
    cache_path: Optional[Path] = None,
) -> List[Dict]:
    """List OPTIMADE providers from the registry."""
    if registry_url is None:
        from ._config_loader import get_config_value
        registry_url = get_config_value("OPTIMADE_REGISTRY_URL")
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
        from ._config_loader import get_config_value
        registry_url = get_config_value("OPTIMADE_REGISTRY_URL")
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
    formula: Optional[str] = None,
    *,
    elements: Optional[List[str]] = None,
    databases: Optional[List[str]] = None,
    filters: Optional[SearchFilters] = None,
    limit_per_database: int = 3,
    retrieve_all: bool = False,
    hard_limit_per_database: int = 2000,
    parallel: bool = False,
    save_cif: bool = True,
    merge_duplicates: bool = False,
    mp_api_key: Optional[str] = None,
    mpds_api_key: Optional[str] = None,
    output_directory: Optional[Path] = None,
    storage=None,
) -> Union[Dict[str, List[Dict]], Dict]:
    """Retrieve structures from every available database client.

    Parameters
    ----------
    formula:
        Composition formula (e.g. ``"Fe2O3"``).  Optional when *elements* is given.
    elements:
        Element-set (chemsys) search returning materials that contain **all** of
        these elements.
    databases:
        Restrict retrieval to a subset of supported databases (see
        :data:`mat_ret.databases.SUPPORTED_DATABASES`).
    filters:
        A :class:`~mat_ret.search.SearchFilters` applied across all databases.
    retrieve_all:
        Query each database up to *hard_limit_per_database* (a safety cap) rather
        than *limit_per_database*.
    parallel:
        Query databases concurrently.
    save_cif:
        Write CIF + metadata files per result (default ``True``).
    merge_duplicates:
        When ``True`` return a unified envelope ``{"materials", "by_database",
        "metadata"}`` with cross-database de-duplication, instead of the default
        ``{db_name: [materials]}`` mapping.
    storage:
        Optional :class:`~mat_ret.storage.base.StorageBackend` instance.
        When provided, every retrieved material is also persisted into the
        chosen storage backend.
    """
    retriever = MaterialsDatabaseRetriever(
        mp_api_key=mp_api_key,
        mpds_api_key=mpds_api_key,
        output_directory=_sanitize_output_directory(output_directory),
        storage=storage,
        databases=databases,
    )
    call_kwargs = dict(
        elements=elements,
        filters=filters,
        databases=databases,
        retrieve_all=retrieve_all,
        hard_limit_per_db=hard_limit_per_database,
        parallel=parallel,
        save_cif=save_cif,
    )
    if merge_duplicates:
        return retriever.retrieve_unified(formula, limit_per_database, **call_kwargs)
    return retriever.retrieve_materials(formula, limit_per_database, **call_kwargs)


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
