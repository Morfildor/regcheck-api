from __future__ import annotations

import sys

from app.core import runtime_state as _module

_module.__dict__["__file__"] = __file__
sys.modules[__name__] = _module
