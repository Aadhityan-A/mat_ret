#!/usr/bin/env python3
"""Demonstrate fetching materials data from every supported database."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

from mat_ret import (
    fetch_aflow,
    fetch_alexandria,
    fetch_all_databases,
    fetch_jarvis,
    fetch_materials_cloud,
    fetch_materials_project,
    fetch_mpds,
    fetch_oqmd,
)

MATERIAL = "MgO"
LIMIT_PER_DATABASE = 1
OUTPUT_DIRECTORY = Path.cwd() / "example_downloads"


def _summarize_result(entry: Dict) -> Dict:
    """Strip out heavy fields and return a small metadata snapshot."""
    snapshot = {}
    for key in ("material_id", "formula", "band_gap", "formation_energy_per_atom", "density", "space_group", "functional", "source_database"):
        if key in entry and entry[key] is not None:
            snapshot[key] = entry[key]
    snapshot.setdefault("keys", sorted(k for k in entry.keys() if k != "structure"))
    return snapshot


def _safe_fetch(
    label: str,
    fetcher: Callable[..., List[Dict]],
    *,
    requires_key: Optional[str] = None,
    **kwargs,
) -> None:
    """Call a fetch helper and print diagnostic output."""
    print(f"\n=== {label} ===")

    if requires_key and not kwargs.get(requires_key):
        print(f"Skipping: missing required credential '{requires_key}'.")
        return

    try:
        results = fetcher(MATERIAL, limit=LIMIT_PER_DATABASE, output_directory=OUTPUT_DIRECTORY, **kwargs)
    except Exception as exc:  # pragma: no cover - demo script should be resilient
        print(f"Failed with error: {exc}")
        return

    if not results:
        print("No structures returned.")
        return

    print(f"Retrieved {len(results)} structure(s).")
    for idx, entry in enumerate(results, start=1):
        summary = _summarize_result(entry)
        print(f"- Result {idx}: {json.dumps(summary, indent=2, default=str)}")


def main() -> None:
    """Run standalone examples for each database helper."""
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # Load API keys, falling back to config defaults if environment variables are not set
    try:
        import config
        mp_api_key = os.getenv("MP_API_KEY") or config.MP_API_KEY
        mpds_api_key = os.getenv("MPDS_API_KEY") or config.MPDS_API_KEY
    except ImportError:
        mp_api_key = os.getenv("MP_API_KEY")
        mpds_api_key = os.getenv("MPDS_API_KEY")

    _safe_fetch(
        "Materials Project",
        fetch_materials_project,
        requires_key="api_key",
        api_key=mp_api_key,
    )
    _safe_fetch("JARVIS", fetch_jarvis)
    _safe_fetch("AFLOW", fetch_aflow)
    _safe_fetch("Alexandria", fetch_alexandria)
    _safe_fetch("Materials Cloud", fetch_materials_cloud, mp_api_key=mp_api_key)
    _safe_fetch("OQMD", fetch_oqmd)
    # MPDS (Materials Platform for Data Science) fetch (API key optional)
    _safe_fetch(
        "MPDS",
        fetch_mpds,
        api_key=mpds_api_key,
    )

    print("\n=== Aggregated retrieval ===")
    try:
        combined = fetch_all_databases(
            MATERIAL,
            limit_per_database=LIMIT_PER_DATABASE,
            mp_api_key=mp_api_key,
            mpds_api_key=mpds_api_key,
            output_directory=OUTPUT_DIRECTORY,
        )
    except Exception as exc:  # pragma: no cover
        print(f"Combined retrieval failed: {exc}")
    else:
        for db_name, results in combined.items():
            print(f"{db_name}: {len(results)} result(s)")
if __name__ == "__main__":
    main()
