from __future__ import annotations

import json

from app.services.rules.legacy import analyze_v1
from rules import analyze
from tests.benchmark_cases import ADVERSARIAL_CASES, BLIND_HOLDOUT_CASES, CURATED_MATCH_CASES


def _diff_payload(description: str) -> dict[str, object]:
    before = analyze_v1(description=description)
    after = analyze(description)
    return {
        "description": description,
        "product": {"before": before.product_type, "after": after.product_type},
        "directives": {"before": before.directives, "after": after.directives},
        "standards": {"before": [item.code for item in before.standards], "after": [item.code for item in after.standards]},
    }


def main() -> int:
    cases = CURATED_MATCH_CASES + BLIND_HOLDOUT_CASES + ADVERSARIAL_CASES
    print(json.dumps([_diff_payload(case.description) for case in cases], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
