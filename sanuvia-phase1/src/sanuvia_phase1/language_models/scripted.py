"""ScriptedLanguageModel — a deterministic TEST DOUBLE.

It is **not** a foundation model and makes **no** empirical claim about real LLMs.
It returns pre-authored JSON responses in order (one per ``complete`` call), so
the whole Phase 1 demonstrator is byte-identically reproducible in CI without any
network or vendor dependency. The authored responses are stylized stand-ins for
the *documented baseline archetypes* (Prototype Brief, Conditions 1 & 2); real
baseline behaviour is obtained only via the opt-in :class:`ExternalLanguageModel`.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..ports import LmRequest, LmResponse


class ScriptedLanguageModel:
    """Returns the pre-authored responses in call order. Implements ``LanguageModel``.

    Requests are ignored (the response is fixed per call index) — this is what
    makes it deterministic. Extra calls beyond the script return an empty object
    ``"{}"`` so the plumbing degrades safely rather than raising.
    """

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses: tuple[str, ...] = tuple(responses)
        self._index = 0

    def complete(self, request: LmRequest) -> LmResponse:  # noqa: ARG002
        if self._index < len(self._responses):
            text = self._responses[self._index]
        else:
            text = "{}"
        self._index += 1
        return LmResponse(json_text=text)
