"""scripts/shadow_compare.py — offline shadow-diff benchmark helper.

Usage (from the repo root):

    python -m scripts.shadow_compare "smart speaker with wifi and bluetooth"
    python -m scripts.shadow_compare --file descriptions.txt

Shadow comparison was removed from the inline ``/analyze`` request path to
eliminate the per-request cost of running the legacy v1 engine.  Use this
script for regression checks, benchmarks, and audit reviews instead.

Exit codes:
  0 — diffs produced (or empty diff = engines agree)
  1 — exception during comparison
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any


def _build_diff(v1_result: Any, v2_result: Any) -> list[dict[str, object]]:
    """Return a list of diff items comparing v1 and v2 analysis results."""
    v1_traits = set(v1_result.confirmed_traits)
    v2_traits = set(v2_result.confirmed_traits)
    v1_standards = {item.code for item in v1_result.standards}
    v2_standards = {item.code for item in v2_result.standards}
    trait_evidence = {item.trait for item in v2_result.trait_evidence if item.confirmed}
    audited_codes = {item.code for item in v2_result.standard_match_audit.selected}
    audited_codes.update(item.code for item in v2_result.standard_match_audit.review)

    diff: list[dict[str, object]] = []
    for trait in sorted(v2_traits - v1_traits):
        diff.append({"kind": "trait", "key": trait, "direction": "v2_only", "has_evidence": trait in trait_evidence})
    for trait in sorted(v1_traits - v2_traits):
        diff.append({"kind": "trait", "key": trait, "direction": "v1_only", "has_evidence": False})
    for code in sorted(v2_standards - v1_standards):
        diff.append({"kind": "standard", "key": code, "direction": "v2_only", "has_evidence": code in audited_codes})
    for code in sorted(v1_standards - v2_standards):
        diff.append({"kind": "standard", "key": code, "direction": "v1_only", "has_evidence": False})
    return diff


def compare(description: str, category: str = "", directives: list[str] | None = None) -> list[dict[str, object]]:
    """Run both engines against *description* and return a diff payload.

    Suitable for use in benchmark scripts and CI regression checks.
    """
    from app.services.rules.legacy import analyze_v1
    from rules import analyze

    v1 = analyze_v1(description=description, category=category, directives=directives)
    v2 = analyze(description=description, category=category, directives=directives)
    return _build_diff(v1, v2)


def _run_one(description: str) -> int:
    try:
        diff = compare(description)
        print(json.dumps({"description": description, "diff_count": len(diff), "diff": diff}, indent=2))
        return 0
    except Exception:
        traceback.print_exc()
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow-compare v1 and v2 analysis engines.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("description", nargs="?", help="Single product description to compare.")
    group.add_argument("--file", help="File with one description per line.")
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            descriptions = [line.strip() for line in fh if line.strip()]
        exit_code = 0
        for desc in descriptions:
            exit_code = max(exit_code, _run_one(desc))
        return exit_code

    return _run_one(args.description)


if __name__ == "__main__":
    sys.exit(main())
