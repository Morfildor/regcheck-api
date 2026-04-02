# Backend Calibration Notes

Calibration and hardening now live in a small set of explicit backend touchpoints:

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

When adding a new product family or legislation route later, prefer updating the family calibration in `routing.py` first, then add any supporting trait or standard gating changes in the files above instead of scattering logic across unrelated modules.

Local validation workflow:

```powershell
.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate
.\venv\Scripts\python.exe -m pytest tests/test_classifier_hardening.py tests/test_calibration_fixtures.py
```
