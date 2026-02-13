"""CLI entrypoint for OPTIMADE harvesting."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import requests

from .registry import fetch_registry_links
from .harvester import OptimadeHarvester


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OPTIMADE full-corpus harvester")
    parser.add_argument("--registry-url", default=None, help="OPTIMADE registry base URL")
    parser.add_argument("--output-dir", default="optimade_harvest", help="Output directory")
    parser.add_argument("--page-limit", type=int, default=1000, help="Page size per request")
    parser.add_argument("--shard-size", type=int, default=5000, help="Structures per shard archive")
    parser.add_argument("--resume", dest="resume", action="store_true", help="Resume from state if available")
    parser.add_argument("--no-resume", dest="resume", action="store_false", help="Disable resume")
    parser.set_defaults(resume=True)
    parser.add_argument("--include-provider", action="append", default=[], help="Provider IDs to include")
    parser.add_argument("--exclude-provider", action="append", default=[], help="Provider IDs to exclude")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP request timeout (seconds)")
    parser.add_argument("--rate-limit", type=float, default=1.0, help="Requests per second per host")
    parser.add_argument("--max-providers", type=int, default=None, help="Limit providers (dev/testing)")
    parser.add_argument("--dry-run", action="store_true", help="List providers and exit")
    return parser.parse_args(argv)


def _print_provider_summary(providers: List[dict], page_limit: int, timeout: int) -> None:
    print(f"Providers discovered: {len(providers)}")
    for provider in providers:
        provider_id = provider.get("id")
        base_url = provider.get("base_url")
        name = provider.get("name", "")
        count = None
        if base_url:
            try:
                url = _structures_url(base_url, page_limit)
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                payload = response.json()
                meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
                if isinstance(meta, dict):
                    count = meta.get("data_available")
            except Exception:
                count = None
        count_str = str(count) if isinstance(count, int) else "unknown"
        print(f"- {provider_id}: {name} ({base_url}) data_available={count_str}")


def _structures_url(base_url: str, page_limit: int) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        structures_url = f"{base}/structures"
    else:
        structures_url = f"{base}/v1/structures"
    return f"{structures_url}?page_limit={page_limit}"


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    try:
        import config  # type: ignore
        default_registry = getattr(config, "OPTIMADE_REGISTRY_URL", None)
    except ImportError:
        default_registry = None

    registry_url = args.registry_url or default_registry
    if not registry_url:
        print("Error: registry URL not provided and OPTIMADE_REGISTRY_URL not set.")
        return 1

    providers = fetch_registry_links(
        registry_url,
        cache_path=None,
        request_timeout=args.timeout,
        include=args.include_provider,
        exclude=args.exclude_provider,
        max_providers=args.max_providers,
    )

    if args.dry_run:
        _print_provider_summary(providers, args.page_limit, args.timeout)
        return 0

    harvester = OptimadeHarvester(
        providers,
        Path(args.output_dir),
        page_limit=args.page_limit,
        shard_size=args.shard_size,
        resume=args.resume,
        request_timeout=args.timeout,
        rate_limit_per_host=args.rate_limit,
    )

    def status(msg: str) -> None:
        print(msg)

    try:
        harvester.harvest(status_callback=status)
    except KeyboardInterrupt:
        print("Harvest interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
