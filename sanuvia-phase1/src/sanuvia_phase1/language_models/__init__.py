"""Language-model implementations behind the Phase 1 ``LanguageModel`` port.

* :class:`ScriptedLanguageModel` — deterministic TEST DOUBLE (default CI path).
* :class:`ExternalLanguageModel` — real adapter seam (opt-in; no vendor bundled).
"""

from __future__ import annotations

from .external import ExternalLanguageModel
from .scripted import ScriptedLanguageModel

__all__ = ["ScriptedLanguageModel", "ExternalLanguageModel"]
