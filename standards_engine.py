from knowledge_base import load_standards


def standard_applies(standard: dict, traits: set[str]) -> bool:
    applies_if_all = standard.get("applies_if_all", [])
    applies_if_any = standard.get("applies_if_any", [])
    exclude_if = standard.get("exclude_if", [])

    if any(t in traits for t in exclude_if):
        return False

    if not all(t in traits for t in applies_if_all):
        return False

    if applies_if_any and not any(t in traits for t in applies_if_any):
        return False

    return True


def build_reason(standard: dict, traits: set[str]) -> str:
    all_hits = [t for t in standard.get("applies_if_all", []) if t in traits]
    any_hits = [t for t in standard.get("applies_if_any", []) if t in traits]

    parts = []
    if all_hits:
        parts.append("required traits matched: " + ", ".join(all_hits))
    if any_hits:
        parts.append("additional traits matched: " + ", ".join(any_hits))

    notes = standard.get("notes")
    if notes:
        parts.append(notes)

    return ". ".join(parts) if parts else (notes or "")


def find_applicable_standards(traits: set[str], directives: list[str]) -> list[dict]:
    standards = load_standards()
    results = []

    for standard in standards:
        standard_directives = standard.get("directives", [])

        if directives and not any(d in directives for d in standard_directives):
            continue

        if standard_applies(standard, traits):
            enriched = dict(standard)
            enriched["reason"] = build_reason(standard, traits)
            results.append(enriched)

    results.sort(key=lambda x: (x.get("category", ""), x.get("code", "")))
    return results