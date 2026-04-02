from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import zipfile


EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
}
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
}
EXCLUDED_SUFFIXES = {
    ".egg-info",
    ".pyc",
    ".pyo",
    ".zip",
}


def _is_excluded(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
        return True
    if path.name in EXCLUDED_FILE_NAMES:
        return True
    if any(path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return True
    return False


def build_source_archive(output_path: Path | None = None) -> Path:
    root = Path(__file__).resolve().parent.parent
    dist_dir = root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = dist_dir / f"regcheck-source-{timestamp}.zip"
    else:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if _is_excluded(path, root):
                continue
            archive.write(path, arcname=path.relative_to(root))

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a clean source archive for handoff.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output archive path. Defaults to dist/regcheck-source-<timestamp>.zip.",
    )
    args = parser.parse_args()

    archive_path = build_source_archive(args.output)
    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
