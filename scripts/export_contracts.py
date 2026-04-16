#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI schema for frontend contract use.

Usage:
    python scripts/export_contracts.py [--out-dir contracts_export]

Output:
    <out-dir>/openapi.json

Run this after any change to request/response models or route definitions
to keep the frontend contract snapshot up to date.
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path regardless of cwd
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export RegCheck OpenAPI schema")
    parser.add_argument(
        "--out-dir",
        default="contracts_export",
        help="Output directory (default: contracts_export)",
    )
    args = parser.parse_args()

    out_dir = project_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Import here so the path patch above is in place first.
    # The lifespan (knowledge-base warmup) does NOT run on plain import,
    # so this is safe to call without a running server.
    from app.main import app  # noqa: PLC0415

    schema = app.openapi()

    out_path = out_dir / "openapi.json"
    out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    paths = list(schema.get("paths", {}).keys())
    component_count = len(schema.get("components", {}).get("schemas", {}))
    print(f"openapi.json written to {out_path}")
    print(f"  OpenAPI version : {schema.get('openapi', '?')}")
    print(f"  API title       : {schema.get('info', {}).get('title', '?')}")
    print(f"  API version     : {schema.get('info', {}).get('version', '?')}")
    print(f"  Paths           : {paths}")
    print(f"  Schema components: {component_count}")


if __name__ == "__main__":
    main()
