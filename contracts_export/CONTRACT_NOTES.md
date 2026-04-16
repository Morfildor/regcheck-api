# RegCheck API — Contract Notes

This folder is the canonical API contract snapshot for the frontend project.
Update it by running `python scripts/export_contracts.py` after any backend model or route change.

---

## Endpoint

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/analyze` |
| Request body | `application/json` — see `ProductInput` schema in `openapi.json` |
| Response body | `application/json` — see `AnalysisResult` schema in `openapi.json` |
| Auth | None (CORS controlled) |

### Other endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | API status and version |
| `GET` | `/health` | Readiness check (503 when warming up) |
| `GET` | `/health/live` | Liveness check |
| `GET` | `/health/ready` | Readiness with detail |
| `GET` | `/metadata/options` | Available traits, genres, products, legislations |
| `GET` | `/metadata/standards` | Full standards catalog |

---

## Source backend

| Property | Value |
|---|---|
| Project | `rulegrid-backend` |
| App version | `6.1.0` (from `pyproject.toml`) |
| API version | `1.0` (hardcoded in every response as `api_version`) |
| Engine version | `2.0` (hardcoded as `engine_version`) |
| Git commit | `addecad` — "Promote v3 matching, routing, and standards ownership" |
| Export date | 2026-04-15 |

---

## Fixture files

| File | Product | Key directives | Risk |
|---|---|---|---|
| `analysis_mains_appliance.json` | 230 V electric kettle, household, no wireless | LVD · EMC · RoHS | LOW |
| `analysis_radio_product.json` | Dual-band WiFi mesh router + Bluetooth | RED · RoHS · Ecodesign | MEDIUM |
| `analysis_complex_iot_appliance.json` | Smart washing machine, WiFi/BT, cloud, OTA | RED · RED\_CYBER · RoHS · ECO · GDPR · CRA (future) | HIGH |

Each fixture file contains a `_fixture_meta` key (non-schema) with the test description and the
`ProductInput` that would produce a similar response. This key is **not** part of the API schema.

---

## Semantic notes for the frontend

### Response structure

- **`ce_legislations`** — directives that require CE marking (LVD, EMC, RED, RoHS). Render prominently.
- **`non_ce_obligations`** — regulatory obligations without CE marking (REACH, WEEE, GPSR, GDPR, Ecodesign).
- **`future_regimes`** — obligations not yet in force (CRA). Render in a "watch list" or "future" section.
- **`standards`** — the selected compliance standards; always present.
- **`review_items`** — standards flagged for human review (confidence low, facts missing). Render distinctly from selected standards.
- **`missing_information_items`** — structured list of missing facts with `importance: "high" | "medium" | "low"`. Surface `high`-importance items prominently.

### Risk levels

`overall_risk`, `current_compliance_risk`, `future_watchlist_risk` each use the enum `"LOW" | "MEDIUM" | "HIGH" | "CRITICAL"`.
The `risk_summary` object repeats this in structured form with reasons.

### Confidence

`product_match_confidence` and `route_confidence` use `"low" | "medium" | "high"`.
`classification_is_ambiguous: true` means the engine could not commit to a single product — surface
this to users as a warning that results may be less precise.

### RED absorbs LVD and EMC

When `directives` contains `"RED"`, LVD and EMC are not listed as separate CE directives.
A single Declaration of Conformity covering RED + RoHS is correct. Do not show LVD and EMC
as separate obligations in this case.

### Directive keys vs codes

The `directive_key` field on `LegislationItem` (e.g. `"RED"`, `"LVD"`) is used for grouping and
display. The `code` field (e.g. `"RED"`, `"LVD"`, `"ECO"`, `"GDPR"`) is the human-readable label.
They often match but may differ for sub-regulations (e.g. `code: "RED_CYBER"`,
`directive_key: "RED_CYBER"`).

### Standards sections

`standard_sections` groups standards by their triggering directive. The `items` list inside each
section is of type `StandardSectionItem`, which extends `StandardItem` with three extra fields:
`triggered_by_directive`, `triggered_by_label`, `triggered_by_title`.
Note: in some responses `items` may be empty even when `count > 0` (lazy population).
Use the top-level `standards` list as the authoritative source for all selected standards.

### Versioning

Every response includes:
```json
{
  "api_version": "1.0",
  "engine_version": "2.0",
  "catalog_version": "2025-Q1"
}
```
`catalog_version` reflects the knowledge base loaded at startup; it may be `null` if the server
is in degraded mode.

### Degraded mode

When `degraded_mode: true`, the analysis completed but one or more internal stages failed.
`degraded_reasons` lists what was skipped. The response is still structurally valid but may be
missing some obligations or standards. Surface a warning banner to the user.

### `_fixture_meta` key

The fixture JSON files contain a top-level `_fixture_meta` key that does not exist in real API
responses. Strip or ignore it when using fixtures as mock responses.

---

## How to re-export after schema changes

```bash
# From the backend repo root:
python scripts/export_contracts.py
```

This regenerates `contracts_export/openapi.json` without starting a server.
The fixture files are hand-authored — update them manually when new fields are added or when
representative product examples change.

Recommended workflow:
1. Make backend model changes.
2. Run `python scripts/export_contracts.py`.
3. Diff `contracts_export/openapi.json` against the previous version.
4. Update fixture files for any new or changed fields.
5. Commit `contracts_export/` changes alongside the backend model changes.
