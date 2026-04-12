# Classifier Signal Config

Classifier text signals now live in `data/classifier_signals.yaml` and focused fragment packs under `data/classifier_signals/*.yaml`.

What moved there:

- `trait_detection`: grouped regex packs for explicit trait detection
- `negations`: grouped regex packs for explicit negation handling
- `suppression_mappings`: trait groups removed when a negation is present
- `wireless_mentions`: phrases that allow product-implied radio traits to survive suppression
- `cue_groups`: reusable text cues for baseline inference and context scoring
- `relation_cues`: governed controller, module, receiver, gateway, panel, backup, and host-device relation patterns
- `domain_roles_wave4.yaml`: explicit role and confusable-domain cue packs used by head resolution v2 and domain-role disambiguation
- `domain_roles_wave6.yaml`: targeted building-access, EV companion, lighting/grow-light, display-PC hybrid, countertop-induction, and wellness-heating packs used by the wave-six disambiguation rules

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

Role-cue conventions:

- Prefer grouped cue packs such as `controller_for`, `receiver_for`, `backup_for`, `panel_for`, or `visualizer_for` over one-off regexes in matcher code.
- Keep role packs explicit and domain-shaped. A good pack names the role and the decisive context: `garage_control_context`, `document_camera_context`, `smoke_co_alarm_context`.
- Use cue packs to reinforce governed heads and confusable-family guards. Do not use them as a substitute for product-specific aliases when the product name itself is decisive.
- When a phrase is broad and reusable, put it in `cue_groups`. When it expresses relationship structure, keep it in `relation_cues`.
- Prefer negative guards and contrastive cues over expanding broad aliases like `controller`, `module`, or `gateway` across many products.
- For companion-device domains, pair the role cue with a contrastive guard in the same pack so `bridge`, `gateway`, `module`, `meter`, `panel`, or `controller` wording does not collapse into the supported main device.
- For hybrid domains, keep the cue pack outcome explicit: either a clear governed hybrid subtype/family or a family-level boundary with an auditable stop reason.
- Multi-word heads such as `lock bridge`, `load balancing meter`, `kiosk display`, `grow light strip`, and `heated shoulder wrap` should be reinforced with both a head cue and a confusable-domain guard instead of a single broad alias.

Avoiding generic-alias regressions:

1. First try a targeted cue pack or preferred clue before adding a new alias.
2. Only add a generic-looking alias when the surrounding product already has strong family keywords, required traits, or explicit negative clues.
3. If a new cue or alias is meant to separate two domains, add both the positive clue and the negative/confusable guard in the same change.
4. Add at least one adversarial or paraphrase fixture in `tests/matching_quality_fixtures/*_wave4.py` for the exact wording that motivated the change.
5. For wave-six domain fixes, prefer adding the exact prompt family to the relevant `*_wave6.py` fixture file and let `scripts/eval_matching.py` generate the mutation variants on top.

Validation:

- knowledge-base warmup now validates classifier signal trait ids, suppression mappings, and regex compilation
- `.\venv\Scripts\python.exe .\scripts\catalog_audit.py validate` runs the same validation path locally
