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


def find_applicable_standards(traits: set[str], directives: list[str]) -> list[dict]:
    results = []
    standards = load_standards()

    for standard in standards:
        standard_directives = standard.get("directives", [])

        if directives and not any(d in directives for d in standard_directives):
            continue

        if standard_applies(standard, traits):
            results.append(standard)

    return results