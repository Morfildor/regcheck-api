from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in constrained environments
    load_dotenv = None


def init_env() -> None:
    if load_dotenv is None:
        return

    # Keep deployed env vars authoritative while allowing local .env defaults.
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
