#!/usr/bin/env python3
"""Fetch and pretty-print WLED JSON API endpoints.

Usage:
    export WLED_BASE_URL=http://wled.local
    python explore_wled.py
    python explore_wled.py --base-url http://192.168.1.50 --endpoint state
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import WLEDApiError, WLEDClient

ENDPOINTS = {
    "full": ("/json", "get_json"),
    "state": ("/json/state", "get_state"),
    "info": ("/json/info", "get_info"),
    "effects": ("/json/eff", "get_effects"),
    "palettes": ("/json/pal", "get_palettes"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explore WLED JSON API endpoints")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("WLED_BASE_URL"),
        help="WLED base URL, e.g. http://wled.local or http://192.168.1.50 (default: WLED_BASE_URL)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--endpoint",
        choices=["all", *ENDPOINTS.keys()],
        default="all",
        help="Endpoint to fetch; default fetches all key endpoints",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.base_url:
        print("error: provide --base-url or set WLED_BASE_URL", file=sys.stderr)
        return 2

    client = WLEDClient(args.base_url, timeout=args.timeout)
    names = list(ENDPOINTS) if args.endpoint == "all" else [args.endpoint]

    for name in names:
        path, method_name = ENDPOINTS[name]
        print(f"\n=== {name}: {path} ===")
        try:
            data = getattr(client, method_name)()
        except WLEDApiError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            continue
        print(json.dumps(data, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
