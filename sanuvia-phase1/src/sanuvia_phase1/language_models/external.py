"""ExternalLanguageModel — the real foundation-model adapter seam (opt-in).

This is the boundary at which a *real* foundation model is plugged in for
evaluation. It is deliberately **vendor-neutral**: it wraps a caller-injected
``client`` callable that takes an ``LmRequest`` and returns the model's raw JSON
reply. No provider SDK is imported, no model is chosen, and nothing here runs in
the default test/CI path.

Governance (unresolved — requires Felix/both developers): which provider/model,
access method, temperature/seed, and the exact prompt contract are **not**
selected here. Wiring a client is an explicit, opt-in decision.
"""

from __future__ import annotations

from collections.abc import Callable

from ..ports import LanguageModel, LmRequest, LmResponse

LmClient = Callable[[LmRequest], str]


class ExternalLanguageModel:
    """Adapts a caller-supplied client into the ``LanguageModel`` port.

    ``client`` must send the request to a real model and return its raw reply,
    which is expected to be a single JSON object conforming to the Phase 1
    response contract. Real runs are **not** guaranteed deterministic.
    """

    def __init__(self, client: LmClient) -> None:
        self._client = client

    def complete(self, request: LmRequest) -> LmResponse:
        return LmResponse(json_text=self._client(request))


def language_model_from_env() -> LanguageModel:
    """Placeholder factory — intentionally refuses to auto-select a provider.

    A real provider/model must never be chosen silently (§8). Until governance is
    resolved, this raises so nothing accidentally reaches a network/vendor.
    """
    raise RuntimeError(
        "No foundation-model provider is configured. Real FM evaluation is opt-in: "
        "construct ExternalLanguageModel(client=...) explicitly with an approved "
        "provider/model and prompt contract (see docs — governance is unresolved)."
    )
