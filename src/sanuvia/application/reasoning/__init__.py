"""The reasoning engine — Model Revision (the centerpiece) and the Core Loop.

This is the *genuine* reasoning: how the persistent model revises in response to
appraised evidence. It orchestrates the ports; it never talks to a database, a
web framework, or a foundation model directly. Language understanding
(appraisal), commit governance, and cognitive-state inference are injected ports.
"""

from __future__ import annotations

from .config import ReasoningConfig
from .core_loop import CoreLoop, InteractionResult
from .model_revision import ModelRevisionEngine

__all__ = [
    "ReasoningConfig",
    "ModelRevisionEngine",
    "CoreLoop",
    "InteractionResult",
]
