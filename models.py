from __future__ import annotations

import sys

from app.domain import models as _module

_module.__dict__["__file__"] = __file__
sys.modules[__name__] = _module
