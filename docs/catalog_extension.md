# Catalog Extension Guide

RuleGrid now operates on a normalized modular catalog. The public API is unchanged, but product maintenance should happen through the fragment catalogs and should follow the route-anchor and family-governance rules below.

## Catalog Layout

Runtime loading merges the root anchors with fragment directories:

- `data/products.yaml` + `data/products/*.yaml`
- `data/traits.yaml` + `data/traits/*.yaml`
- `data/standards.yaml` + `data/standards/*.yaml`
- `data/classifier_signals.yaml` + `data/classifier_signals/*.yaml`
- `data/product_genres.yaml`

The root files remain lightweight anchors. Most maintenance work should happen in the fragment directories.

## Deterministic Merge Rules

Catalog loading is intentionally simple and stable:

1. Load the root file first, if it exists.
2. Load fragment files from the matching directory in lexicographic relative-path order.
3. Merge mappings recursively.
4. Concatenate lists in file order.
5. Let later scalar values override earlier scalar values.

This means fragment order is part of the contract. Keep product ids stable and avoid depending on accidental file ordering.

## Required Product Structure

Every in-scope product row should carry reviewable structure. For the normalized catalog, the expected product fields are:

- `id`: Stable product id. Never recycle ids for a different meaning.
- `label`: Human-readable display label.
- `genres`: Required for normal routing and auditability. Use one or more real catalog genres.
- `product_family`: Required. Use a stable, human-readable family shared by similar products.
- `product_subfamily`: Required for normal products. Usually the stable product leaf and often the same as the product id.
- `route_anchor`: Required for routable products. Choose from the governed route-anchor set below.
- `route_family`: Required for routable products. It should be the route family implied by the chosen `route_anchor`.
- `primary_standard_code`: Required when the product is confidently anchored to a concrete product-safety route. Omit it for boundary anchors and broad-review products.
- `supporting_standard_codes`: Optional supporting route standards.
- trait fields such as `implied_traits`, `default_traits`, `family_traits`, and `subtype_traits`: Use these to support explainable classification, routing, and missing-fact questions.

Do not leave structure blank. If a product should stay broad, encode that explicitly with family-level handling or a boundary route instead of falling back to `unknown`, `unanchored`, or empty fields.

## Family And Subfamily Rules

Use `product_family` for a stable explainable cluster:

- Good: `portable_power_charger`, `life_safety_alarm`, `energy_power_system`
- Avoid: `unknown`, opaque internal abbreviations, or one-off ids used as families

Use `product_subfamily` for the leaf product identity:

- Usually the same as the product id
- Keep it stable across refactors and re-sharding
- Do not overuse subtype precision when the product should remain family-level only in runtime behavior

When adding or renaming a family:

- prefer human-readable wording
- keep the family usable in classifier explanations
- keep the family useful for route governance
- avoid near-duplicates with overlapping scope

## Route-Anchor Governance

`route_anchor` is the small governed vocabulary that ties product structure to routing behavior. Choose the smallest anchor that predictably represents the product family.

Current route-anchor set:

- `household_core`
- `household_connected`
- `hvac_control`
- `lighting_core`
- `lighting_connected`
- `avict_core`
- `avict_connected`
- `avict_wearable`
- `building_access`
- `life_safety_alarm`
- `ev_charging`
- `ev_connector_accessory`
- `machinery_tool`
- `toy`
- `power_system_boundary`
- `medical_wellness_boundary`
- `micromobility_boundary`
- `drone_uas_boundary`
- `specialty_electrical_boundary`

Use them consistently:

- household appliances: `household_core` or `household_connected`
- AV/ICT devices and chargers: `avict_core` or `avict_connected`
- wearable AV/ICT and body-worn consumer electronics: `avict_wearable`
- connected lighting: `lighting_connected`
- non-connected lighting and optical products: `lighting_core`
- building access, smart locks, shutters, gates: `building_access`
- smoke and CO alarms: `life_safety_alarm`
- EV charge equipment: `ev_charging`
- EV connector and cable accessories: `ev_connector_accessory`
- power tools, bench tools, garden powered equipment: `machinery_tool`
- energy systems, inverters, storage, metering gateways near installation scope: `power_system_boundary`
- wellness and therapy-adjacent devices near medical scope: `medical_wellness_boundary`
- agricultural and specialty electrical products: `specialty_electrical_boundary`

Avoid one-off anchors. If a product cannot fit the current set cleanly, first check whether it should stay family-level only or boundary-reviewed before adding a new anchor.

## Family-Level Only And Boundary Review

Use explicit family-level handling when a product should not overcommit to subtype or route precision.

Use these fields together:

- `max_match_stage: family`
- `route_confidence_cap: low` or `medium`
- `family_level_reason: ...`
- `boundary_tags: [...]`

Use family-level only handling for products such as:

- wellness vs medical-boundary devices
- UV / irradiation products
- energy system / inverter / storage products
- industrial or fixed-installation boundary products
- machinery/system boundary products
- specialty agricultural electrical products

Use a boundary anchor when the primary route itself should remain broad:

- `power_system_boundary`
- `medical_wellness_boundary`
- `specialty_electrical_boundary`
- `micromobility_boundary`
- `drone_uas_boundary`

Use a normal route anchor plus family-level handling when the main route family is still valid but subtype precision should remain conservative:

- UV nail lamps can stay on the lighting route with family-level handling
- water dispensers can stay on the household route with family-level handling
- bench saws can stay on the machinery/tool route with family-level handling

Do not silently force a consumer-product route on system-level or boundary products just to populate the fields.

## Traits And Signals

Traits should be durable routing and explainability inputs, not speculative metadata.

When adding traits:

- prefer reusable semantic traits over product-specific one-offs
- keep names coherent across product rows, classifier signals, and routing
- remove or merge traits that never influence matching, routing, or review behavior
- add `normalized_to` aliases when older wording still needs to resolve cleanly

Classifier signal rules:

- every signal key must map to a real trait id
- keep detection patterns narrow and explainable
- add negations when text can explicitly disable the trait
- add suppression mappings only when the negation should also remove derived traits

## Modular Product File Conventions

Use product fragments as semantic domain shards, not as arbitrary wave dumps.

Preferred organization:

- household, kitchen, climate, and water appliances together
- lighting and optical products together
- AV/ICT and networking products together
- EV charging and mobility products together
- security, alarms, and building-access products together
- wellness and medical-boundary products together
- energy-system boundary products together
- specialty and agricultural boundary products together

When moving products between files:

- preserve the stable product id
- move the whole product block without semantic changes unless the move is part of a planned normalization pass
- keep file names intuitive for future contributors
- avoid creating tiny fragments unless the boundary is genuinely useful

## Validation And Audit

Run these commands from the repo root:

```powershell
.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate
.\venv\Scripts\python.exe .\scripts\catalog_audit.py summary
.\venv\Scripts\python.exe .\scripts\catalog_audit.py summary --json
.\venv\Scripts\python.exe .\scripts\catalog_audit.py report --strict-structure
.\venv\Scripts\python.exe .\scripts\catalog_audit.py report --by-file
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\ruff.exe check .
.\venv\Scripts\mypy.exe .
```

Or use the local quality gate:

```powershell
.\scripts\quality.ps1
```

`catalog_audit.py` supports:

- `validate`: lightweight schema and linkage validation
- `summary`: normalized structural summary and route-family overview
- `summary --json`: machine-readable summary for CI or reporting
- `report --strict-structure`: fail when normalized products still miss required structure
- `report --by-file`: hotspot counts for raw unknown-family and unanchored-route concentration by file

The report now highlights:

- missing structure counts by field
- raw versus normalized unknown-family and unanchored-route counts
- unused traits with source context
- weak route governance
- boundary-heavy products
- file-level hotspots for structural cleanup

## Regression Coverage Expectations

Catalog changes should ship with focused regression coverage in the same change.

Prefer a mix of:

- route and directive regressions in `tests/test_route_normalization.py`
- classifier regressions in `tests/test_classifier_hardening.py`
- matching regressions in `tests/test_matching_regressions.py`
- payload stability snapshots in `tests/snapshots/*.json`

For new boundary products, include assertions for:

- family and subfamily placement
- route anchor and route family
- family-level-only behavior
- route confidence
- expected review items or missing-fact prompts

## Safe Extension Checklist

- Keep ids stable.
- Fill `genres`, `product_family`, `product_subfamily`, `route_anchor`, and `route_family`.
- Use the governed route-anchor set.
- Prefer explicit family-level handling over empty structure.
- Keep modular file ownership obvious.
- Remove or merge unused traits instead of accumulating dead taxonomy.
- Run `catalog_audit.py validate` and `catalog_audit.py report --strict-structure`.
- Add regression coverage in the same change.
