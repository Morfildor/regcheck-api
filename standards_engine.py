from __future__ import annotations

import sys

from app.services.standards_engine import service as _module

_module.__dict__["__file__"] = __file__
sys.modules[__name__] = _module
