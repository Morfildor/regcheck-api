# Backend Calibration Notes

Calibration and hardening now live in a small set of explicit backend touchpoints:

- `data/taxonomy/*.yaml`
  Governs product families, subfamilies, route anchors, and structured boundary decisions.
- `app/services/classifier/traits.py`
  Keeps explicit-vs-inferred trait extraction disciplined, handles negations, and suppresses weak ambiguous product guesses before they leak into routing.
- `app/services/rules/routing.py`
  Owns family-aware route calibration, route separation, primary route selection, and scope-specific fallback behavior.
- `app/services/rules/facts.py`
  Generates materially useful follow-up questions and missing-fact prompts while avoiding filler for passive or weakly described products.
- `app/services/standards_engine/gating.py`
  Filters and rejects standards that conflict with the calibrated route family or scope so outputs stay coherent.
- `app/services/rules/service.py`
  Builds the decision trace and threads calibrated routing and standards selections into the final analysis.
- `app/services/rules/result_builder.py`
  Stabilizes output ordering so primary safety and route-critical standards surface first in a predictable way.
- `tests/calibration_fixtures.py`
  Holds representative regression cases that pin product-family selection, route selection, and obvious false-positive exclusions across household, AV/ICT, charger, security, wellness, and EV scenarios.

Product matching touchpoints:

- `app/services/classifier/head_resolution.py`
  Owns head resolution v2. It prefers concise governed product heads, supports compound heads such as `garage door controller` and `document camera visualizer`, and records competing-head reasons when precision should stay conservative.
- `app/services/classifier/relation_parsing.py`
  Parses `controller for`, `receiver for`, `backup for`, `built into`, and related patterns into auditable role slots before reranking.
- `app/services/classifier/confusable_domains.py`
  Applies explicit domain-role disambiguation matrices for the main collision zones such as security vs projector, networking vs security, and UPS vs charger families.
- `app/services/classifier/matching.py`
  Shortlists, reranks, applies the domain-role matrices, and decides when to stop at family level instead of overcommitting to a subtype.
- `app/services/classifier/matching_runtime.py`
  Supplies compiled matcher metadata such as known head phrases, role-aware shortlist traits, and governed product snapshots.

Head resolution v2 rules:

- Prefer the shortest decisive governed head term, but keep the full phrase and tie-break reasons in audit output.
- Treat protocol and packaging words such as `wifi`, `zigbee`, `portable`, `desktop`, and `rechargeable` as modifiers unless they are part of a governed compound head.
- If two head candidates stay close, bias toward a family-level stop rather than a brittle subtype guess.
- When a relation split hides a stronger full-phrase head, let the full-phrase head win and record that override in parse notes.

Domain-role disambiguation rules:

- Use explicit positive and negative guards instead of burying cross-domain calibration in opaque weights.
- Prefer route-anchor compatibility, target-device cues, and confusable-family penalties over global threshold changes.
- Keep reasons stable and short so audit consumers can compare runs cleanly.

Audit expectations:

- Top subtype candidates should expose stable product ids, family, subtype, score, shortlist reason, rerank reason, and final stop reason.
- Role-parse audit should include the resolved primary head, head term, quality, competing heads, and relation-role slots.
- Confusable-domain and domain-role adjustments should surface as concise reasons, not raw score dumps.

When adding a new product family or legislation route later, prefer updating the family calibration in `routing.py` first, then add any supporting trait or standard gating changes in the files above instead of scattering logic across unrelated modules.

Local validation workflow:

```powershell
.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate
.\venv\Scripts\python.exe -m pytest tests/test_classifier_hardening.py tests/test_calibration_fixtures.py
.\venv\Scripts\python.exe .\scripts\eval_matching.py --mode adversarial
.\venv\Scripts\python.exe .\scripts\eval_matching.py --mode paraphrase,organic --json-out .\tmp\matching_eval.json
```

Evaluation output notes:

- `mode_summaries` separates curated, adversarial, paraphrase, and organic fixtures.
- `domain_confusion_summaries` highlights family leaks across domains.
- `head_resolution_disagreements` points to low-quality or conflicted heads that still need calibration.
- `unresolved_valid_products` captures products that landed on the right family but still stopped short of the expected subtype.
- `failures_by_reason` groups JSON output by actionable reasons such as `domain_confusion`, `overcommitted_subtype`, or `unresolved_valid_product`.
