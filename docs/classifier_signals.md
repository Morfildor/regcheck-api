# Classifier Signal Config

Classifier text signals now live in `data/classifier_signals.yaml`.

What moved there:

- `trait_detection`: grouped regex packs for explicit trait detection
- `negations`: grouped regex packs for explicit negation handling
- `suppression_mappings`: trait groups removed when a negation is present
- `wireless_mentions`: phrases that allow product-implied radio traits to survive suppression
- `cue_groups`: reusable text cues for baseline inference and context scoring

How it is loaded:

- `app/services/classifier/signal_config.py` reads and compiles the YAML once
- the compiled snapshot is attached to the knowledge-base warmup snapshot
- classifier code reads the cached compiled forms via `get_classifier_signal_snapshot()`

How to extend it safely:

1. Add new phrases under the most specific existing group in `data/classifier_signals.yaml`.
2. If a new negation should suppress related traits, add the suppression set under `suppression_mappings`.
3. Keep new patterns normalized to the classifier text format used by `normalize()`.
4. Prefer adding explicit signal phrases over changing precedence logic in `traits.py`.
5. Add or update a focused classifier regression in `tests/test_classifier_hardening.py`.
6. Every signal name must already exist as a trait id in `data/traits.yaml`.

Validation:

- knowledge-base warmup now validates classifier signal trait ids, suppression mappings, and regex compilation
- `.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate` runs the same validation path locally
