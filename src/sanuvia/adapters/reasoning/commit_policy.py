"""Phase-0 commit-policy scaffold.

============================ TEMPORARY SCAFFOLD =============================
This is NOT the specification's revision governance, and it is not a product
algorithm. The frozen specification *intentionally leaves the ``proposed ->
committed`` transition unspecified* (FR-MR-003): what decides or validates the
transition "is not resolved by PRS text." This class exists only so the exit
test can exercise revision while that governance is undefined.

It commits every proposed event. That is an explicit, injected, clearly-named
placeholder in the adapter layer — never a governance rule hidden inside the
engine. When the transition governance is specified, replace this adapter; the
reasoning engine, which only *asks* the ``RevisionCommitPolicy`` port, does not
change.
=============================================================================
"""

from __future__ import annotations

from sanuvia.domain import RevisionEvent


class PlaceholderCommitAllPolicy:
    """Commits every proposed RevisionEvent. Implements ``RevisionCommitPolicy``.

    Temporary scaffold for an intentionally-unspecified specification area
    (FR-MR-003). Deliberately trivial and honest: it does not pretend to reason
    about *whether* a revision should commit.
    """

    def should_commit(self, event: RevisionEvent) -> bool:  # noqa: ARG002
        return True
