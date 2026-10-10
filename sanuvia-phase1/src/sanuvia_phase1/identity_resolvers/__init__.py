"""Identity-resolver adapters (R1). Opt-in; nothing runs by default."""

from .external import (
    RESOLVER_ID,
    ExternalIdentityResolver,
    IdentityResolutionPrompt,
)

__all__ = [
    "RESOLVER_ID",
    "ExternalIdentityResolver",
    "IdentityResolutionPrompt",
]
