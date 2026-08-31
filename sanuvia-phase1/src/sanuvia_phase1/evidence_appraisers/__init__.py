"""Evidence-appraiser adapters behind the FROZEN Phase 0 ``EvidenceAppraiser`` port.

Golden mode uses Phase 0's own ``ScriptedAppraiser`` (deterministic). Real mode
uses :class:`ExternalEvidenceAppraiser` — a provider-neutral, injected-client
adapter. The appraiser only PROPOSES candidate hypotheses and support/contradiction
per the documented boundary (Programme v1.4 Part 2: "FM generates candidate
inferences; Sanuvia manages hypotheses and revises models"); the frozen engine
remains the authority for model revision and persistence.
"""

from __future__ import annotations

from .external import (
    AppraisalClient,
    AppraisalRequest,
    ExternalEvidenceAppraiser,
    evidence_appraiser_from_env,
)

__all__ = [
    "ExternalEvidenceAppraiser",
    "AppraisalClient",
    "AppraisalRequest",
    "evidence_appraiser_from_env",
]
