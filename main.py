from __future__ import annotations

from app import main as _main
from app.services.knowledge_base import reset_cache

app = _main.app
logger = _main.logger
warmup_knowledge_base = _main.warmup_knowledge_base
analyze = _main.analyze

_require_admin_reload_token = _main._require_admin_reload_token
admin_reload = _main.admin_reload
get_runtime_state = _main.get_runtime_state
health = _main.health
health_live = _main.health_live
health_ready = _main.health_ready
metadata_options = _main.metadata_options
metadata_standards = _main.metadata_standards
root = _main.root
run_analysis = _main.run_analysis

__all__ = [
    "_require_admin_reload_token",
    "admin_reload",
    "analyze",
    "app",
    "get_runtime_state",
    "health",
    "health_live",
    "health_ready",
    "logger",
    "metadata_options",
    "metadata_standards",
    "reset_cache",
    "root",
    "run_analysis",
    "warmup_knowledge_base",
]
