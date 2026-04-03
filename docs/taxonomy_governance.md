# Taxonomy Governance

RuleGrid now treats product taxonomy and route anchoring as governed catalog inputs rather than hidden normalization outcomes.

## Source Of Truth

The authoritative taxonomy lives in `data/taxonomy/`:

- `families.yaml`: allowed `product_family` values, default genres, allowed route anchors, optional required traits, and boundary tendencies
- `subfamilies.yaml`: allowed `product_subfamily` values and the family each one belongs to
- `route_anchors.yaml`: finite route-anchor vocabulary, route-family mapping, scoring signals, and family-level handling defaults
- `boundaries.yaml`: structured boundary decision rules, preferred route anchors, confidence caps, and missing differentiators

These files are intentionally specific. They are not a generic rules engine.

## How To Extend Taxonomy

When adding a new product family:

1. Add the family to `data/taxonomy/families.yaml`.
2. Add each supported leaf product to `data/taxonomy/subfamilies.yaml`.
3. Choose from the existing governed `route_anchor` values whenever possible.
4. Add or update a boundary rule only if the family really needs boundary-specific handling.
5. Backfill explicit `product_family`, `product_subfamily`, and `route_anchor` in the product fragment rows when confidence is strong.

Family names should stay human-readable and stable enough for classifier explanations, audit reporting, and catalog maintenance.

## Choosing Family, Subfamily, And Route Anchor

Use `product_family` for the explainable cluster shared by multiple similar products.

Use `product_subfamily` for the stable product leaf. In most cases this matches the product id.

Use `route_anchor` for the smallest governed routing bucket that consistently represents the family:

- `household_core` / `household_connected` for household appliances
- `lighting_core` / `lighting_connected` for lighting and optical lighting routes
- `avict_core` / `avict_connected` / `avict_wearable` for AV/ICT
- `building_access` for locks, gates, shutters, and access drives
- `life_safety_alarm` for smoke and CO alarms
- `ev_charging` / `ev_connector_accessory` for EV charging
- boundary anchors such as `power_system_boundary`, `medical_wellness_boundary`, `drone_uas_boundary`, and `specialty_electrical_boundary` for deliberately conservative routing

If the product does not justify precise route commitment, prefer family-level handling instead of leaving structure blank.

## Boundary Review Handling

Use explicit boundary-review handling when the product sits near a controlled scope boundary:

- medical / wellness
- UV / irradiation
- body treatment / therapy
- power system / inverter / storage
- industrial installation
- machinery or stationary-system scope
- specialty agricultural electrical use
- office monitor / all-in-one / kiosk ambiguity
- water dispensing / hygiene

The structured boundary layer can supply:

- `boundary_class`
- `max_match_stage`
- `route_confidence_cap`
- `family_level_reason`
- `boundary_missing_differentiators`

This keeps conservative behavior visible and explainable.

## Inference Debt

Normalization still supports a temporary compatibility path, but it now reports when it had to compensate for incomplete structure.

Current inference-debt signals include:

- `family_inferred`
- `subfamily_inferred`
- `route_anchor_inferred`
- `route_family_inferred`
- `compatibility_fallback`
- `route_anchor_low_confidence`
- `family_level_only`
- `route_reason_weak`

Legacy fallback from missing family/subfamily to product id is no longer the normal steady state. It only occurs through the explicit compatibility path and is surfaced through audit metadata.

## Audit Commands

Run lightweight governance audits from the repo root:

```powershell
.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate
.\venv\Scripts\python.exe .\scripts\catalog_audit.py taxonomy --by-file
.\venv\Scripts\python.exe .\scripts\catalog_audit.py route-governance --by-family
.\venv\Scripts\python.exe .\scripts\catalog_audit.py inference-debt --by-file
.\venv\Scripts\python.exe .\scripts\catalog_audit.py summary --json
```

Use these reports to find:

- undeclared family or subfamily structure
- undeclared route anchors
- compatibility fallback usage
- singleton families and subfamilies
- weak family support
- file-level family outliers
- weak or ambiguous route-anchor reasons

## Migration Guidance

When moving a product away from normalization fallback:

1. Add or confirm the taxonomy family and subfamily.
2. Backfill explicit `product_family` and `product_subfamily` in the raw product row.
3. Backfill `route_anchor` when the route is strong enough.
4. Use family-level handling or a boundary anchor for true boundary products.
5. Re-run the audit commands and regression tests.

The goal is for the raw catalog to carry the real structure directly, with normalization acting only as a thin compatibility and reporting layer.
