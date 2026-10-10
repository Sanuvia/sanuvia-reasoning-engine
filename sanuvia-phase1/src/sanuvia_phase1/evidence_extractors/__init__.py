"""Evidence-extractor implementations behind the ``EvidenceExtractor`` port.

* :class:`ScriptedEvidenceExtractor` — deterministic TEST DOUBLE (default CI path).
* :class:`ExternalEvidenceExtractor` — real, provider-neutral, injected-client seam.
"""

from __future__ import annotations

from .external import (
    ExtractionClient,
    ExtractionRequest,
    ExternalEvidenceExtractor,
    evidence_extractor_from_env,
)
from .scripted import ScriptedEvidenceExtractor

__all__ = [
    "ScriptedEvidenceExtractor",
    "ExternalEvidenceExtractor",
    "ExtractionClient",
    "ExtractionRequest",
    "evidence_extractor_from_env",
]
