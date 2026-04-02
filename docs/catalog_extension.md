# Catalog Extension Guide

RuleGrid's product coverage now depends on four catalog layers working together:

- `data/traits.yaml`
  Defines reusable capability, environment, power, privacy, safety, and boundary traits.
- `data/product_genres.yaml`
  Defines stable grouping hints that multiple products can share.
- `data/products.yaml`
  Defines the reviewable product-family and subtype catalog that drives matching and routing.
- `data/classifier_signals.yaml`
  Defines auditable text signals, negations, suppression mappings, and cue groups.

## Add a Product Family

1. Add a product row in `data/products.yaml`.
2. Keep `product_family` and `product_subfamily` explicit and human-readable.
3. Add realistic aliases:
   Use a small set of strong aliases, then weaker marketplace/shorthand variants.
4. Add `preferred_clues` and `exclude_clues` when nearby products are easy to confuse.
5. Add `genres`, `route_family`, `primary_standard_code`, and any supporting standards.
6. Add the minimum trait structure needed for routing:
   Prefer `implied_traits` plus `family_traits` / `subtype_traits` over giant alias lists.
7. Add or update a calibration fixture in `tests/calibration_fixtures.py`.

## Add a Trait Safely

1. Add the trait to `data/traits.yaml` with a clear label and description.
2. Prefer stable, reusable semantics:
   Example: `charger_role` is better than a product-specific trait like `usb_wall_charger_capability`.
3. If the trait is mainly classifier-facing, add signal patterns in `data/classifier_signals.yaml`.
4. If the trait affects route selection or context tags, add a targeted mapping in:
   `app/services/classifier/traits.py` or `app/services/rules/routing_context_helpers.py`.
5. Run the catalog audit and warmup validation after the edit.

## Add Classifier Signals

1. Put explicit phrases in `trait_detection` under the most specific group.
2. Add negation phrases in `negations` when the text can explicitly disable the trait.
3. Add `suppression_mappings` when a negation should also remove related derived traits.
4. Keep patterns explainable:
   Prefer a few precise phrases over broad catch-all regexes.
5. Every signal name must be a real trait id:
   the knowledge-base warmup now validates this automatically.

## How Genres, Products, and Traits Interact

- Traits describe what the product is or does.
- Genres provide reusable grouping and routing hints shared by many products.
- Products provide the concrete family/subtype match and the primary safety route.
- Signals provide text evidence that can confirm, suppress, or refine product-implied traits.

In practice:

- Add a new genre only when several products genuinely share a stable grouping.
- Add a new product when family/subtype routing or standards behavior needs to differ.
- Add a new trait when multiple products or routes need the same concept.

## Validate After Edits

Run these from the repo root:

```powershell
.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate
.\venv\Scripts\python.exe -m pytest
```

For a fuller local audit:

```powershell
.\venv\Scripts\python.exe .\scripts\catalog_audit.py all
```

The audit reports:

- unknown or malformed catalog references via the real validator path
- unused traits
- products with thin alias coverage
- aliases shared across many products
- products missing genre / route / trait structure
