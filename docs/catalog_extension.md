# Catalog Extension Guide

RuleGrid now loads modular catalogs for products, traits, standards, and classifier signals. The public API is unchanged, but catalog maintenance should happen in the fragment directories instead of growing the root YAML files.

## Catalog Layout

- `data/products.yaml`
- `data/traits.yaml`
- `data/standards.yaml`
- `data/classifier_signals.yaml`

Those root files are lightweight anchors. Runtime loading merges them with fragment directories when they exist:

- `data/products/*.yaml`
- `data/traits/*.yaml`
- `data/standards/*.yaml`
- `data/classifier_signals/*.yaml`

`product_genres.yaml` remains a single catalog unless a future split is needed.

## Deterministic Merge Rules

Catalog loading is intentionally simple and deterministic:

1. Load the root file first, if it exists.
2. Load fragment files from the matching directory in lexicographic relative-path order.
3. Merge mappings recursively.
4. Concatenate lists in file order.
5. Let later scalar values override earlier scalar values.

This means fragment ordering is explicit and stable. If you need one fragment to extend another, name the files accordingly and keep ids stable.

## Add a Product Family

1. Pick the right fragment file under `data/products/`.
2. Add a new product row with a stable `id`.
3. Keep `product_family` and `product_subfamily` explicit and human-readable.
4. Add a small set of realistic aliases first, then only the shorthand variants that materially help recall.
5. Prefer `required_clues`, `preferred_clues`, and `exclude_clues` over keyword stuffing.
6. Set `genres`, `route_family`, `primary_standard_code`, and any `supporting_standard_codes`.
7. Add the minimum useful trait structure through `implied_traits`, `family_traits`, and `subtype_traits`.
8. Add or update regression coverage in `tests/calibration_fixtures.py`, `tests/test_matching_regressions.py`, or snapshots when the contract should stay stable.

## Add Traits and Signals Safely

Add traits in `data/traits/`:

1. Use a clear, reusable semantic id.
2. Keep names coherent across routing and classification.
3. Prefer broad concepts such as `wired_networking`, `metering`, or `uv_irradiation_boundary` over product-specific one-offs.
4. Add `normalized_to` aliases when older wording still needs to resolve cleanly.

Add classifier signals in `data/classifier_signals/`:

1. Put explicit phrases under `trait_detection`.
2. Add negations under `negations` when the text can explicitly switch a trait off.
3. Add `suppression_mappings` when a negation should remove related derived traits too.
4. Keep patterns explainable and narrow.
5. Every signal key must map to a real trait id; warmup validation enforces this.

## Boundary and Broad-Review Products

When a product should not overcommit to a precise subtype or route, use the explicit boundary fields on the product row:

- `max_match_stage: family`
- `route_confidence_cap: low|medium|high`
- `family_level_reason: ...`
- `boundary_tags: [...]`

Use those for products such as:

- medical-adjacent or therapy-adjacent devices
- UV / irradiation products
- energy storage, inverter, and installation-boundary products
- machinery-like products that should remain family-level until scope is clarified

The goal is to surface a usable result with review questions and audit reasons instead of a false-precision subtype match.

## Routing and Trait Hygiene

Use traits for durable behavior, not just matching convenience:

- Traits should help both classification and routing.
- Product rows should not rely on giant alias lists to do routing work.
- If a new trait changes routing context or risk questions, update the focused helper in the classifier or rules layer instead of adding ad-hoc special cases.

## Validate and Audit

Run these from the repo root:

```powershell
.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate
.\venv\Scripts\python.exe .\scripts\catalog_audit.py report --minimum-aliases 4 --broad-alias-threshold 3
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\ruff.exe check .
.\venv\Scripts\mypy.exe .
```

Or use the full local quality gate:

```powershell
.\scripts\quality.ps1
```

`catalog_audit.py` now supports modular catalogs and reports:

- catalog source file counts
- alias collision severity
- route-family coverage
- traits-per-product distribution
- products lacking decisive clues
- products likely to overmatch
- boundary product rows
- optional diff summaries with `--compare-dir`

## Add Regression Coverage

For new coverage, prefer a mix of:

- `tests/calibration_fixtures.py` for route and directive expectations
- `tests/test_classifier_hardening.py` for trait and negation behavior
- `tests/test_matching_regressions.py` for boundary-review and routing regressions
- `tests/snapshots/*.json` when the API payload shape and high-signal fields should remain stable over time

When adding boundary products, include at least:

- expected family vs. subtype behavior
- expected route confidence
- review items or boundary questions
- local-only / wired-only / no-cloud phrasing when relevant

## Safe Extension Checklist

- Keep ids stable.
- Keep fragment ownership obvious.
- Prefer decisive clues over broad aliases.
- Add boundary metadata when the route is intentionally conservative.
- Run `catalog_audit.py validate` before shipping.
- Add regression coverage in the same change as the catalog edit.
