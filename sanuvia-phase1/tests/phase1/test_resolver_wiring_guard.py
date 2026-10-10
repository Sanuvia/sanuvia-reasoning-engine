"""The real External path must receive NO scripted identity resolver (G-1).

``ScriptedIdentityResolver`` returns fixture-authored identity decisions. It is
a test double. If it ever reached a real-model configuration it would be
deciding identity for a real run from authored fixture data, which is both
wrong and invisible.

The guard is structural -- the resolver is bound to the same branch of
``SanuviaPersistentCondition.start`` that selects the scripted appraiser -- but
structure that nothing asserts can be refactored away silently. These tests
assert both branches, and that they are not cross-wired.
"""

from __future__ import annotations

from typing import Any

import json

from fixtures.longitudinal.case_001 import CASE_001

from sanuvia.adapters.reasoning.scripted_appraiser import ScriptedAppraiser
from sanuvia.adapters.reasoning.scripted_identity_resolver import (
    ScriptedIdentityResolver,
)
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.evidence_appraisers.external import ExternalEvidenceAppraiser


def _deps_of(condition: SanuviaPersistentCondition) -> Any:
    """The dependencies the condition actually built."""
    assert condition._service is not None  # start() ran
    return condition._service._deps


def _fake_external() -> ExternalEvidenceAppraiser:
    """An External appraiser over a fake client. Nothing reaches a network."""
    return ExternalEvidenceAppraiser(
        client=lambda _prompt: json.dumps(
            {"supports": [], "contradicts": [], "proposals": []}
        )
    )


def test_external_branch_receives_no_identity_resolver() -> None:
    """The defining assertion: a real appraiser gets no fixture resolver."""
    condition = SanuviaPersistentCondition(CASE_001, appraiser=_fake_external())
    condition.start()

    deps = _deps_of(condition)
    assert deps.identity_resolver is None
    assert not isinstance(deps.identity_resolver, ScriptedIdentityResolver)


def test_external_branch_keeps_the_injected_real_appraiser() -> None:
    """Guarding identity must not have swapped the appraiser back to scripted."""
    appraiser = _fake_external()
    condition = SanuviaPersistentCondition(CASE_001, appraiser=appraiser)
    condition.start()

    deps = _deps_of(condition)
    assert deps.appraiser is appraiser
    assert not isinstance(deps.appraiser, ScriptedAppraiser)


def test_scripted_branch_receives_the_fixture_authored_resolver() -> None:
    """The converse: without an injected appraiser, the double IS wired."""
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()

    deps = _deps_of(condition)
    assert isinstance(deps.identity_resolver, ScriptedIdentityResolver)
    assert isinstance(deps.appraiser, ScriptedAppraiser)


def test_the_two_branches_are_not_cross_wired() -> None:
    """Resolver and appraiser must move together, never independently.

    A scripted appraiser with no resolver cannot express its authored
    plurality; a real appraiser with a resolver would decide a real run's
    identity from fixture data. Asserting the pairing catches either.
    """
    scripted = SanuviaPersistentCondition(CASE_001)
    scripted.start()
    external = SanuviaPersistentCondition(CASE_001, appraiser=_fake_external())
    external.start()

    scripted_deps, external_deps = _deps_of(scripted), _deps_of(external)

    scripted_pair = (
        isinstance(scripted_deps.appraiser, ScriptedAppraiser),
        scripted_deps.identity_resolver is not None,
    )
    external_pair = (
        isinstance(external_deps.appraiser, ScriptedAppraiser),
        external_deps.identity_resolver is not None,
    )
    assert scripted_pair == (True, True)
    assert external_pair == (False, False)


def test_the_real_run_pipeline_injects_a_real_appraiser() -> None:
    """The REAL path reaches the External branch, so it gets no resolver.

    Read structurally rather than by executing a run: the pipeline passes an
    injected appraiser, which is the condition the guard keys on.
    """
    import inspect

    from sanuvia_phase1 import pipeline

    source = inspect.getsource(pipeline)
    assert "SanuviaPersistentCondition" in source
    assert "appraiser=" in source
    # And the fixture double is not reachable from the real-run module.
    assert "ScriptedIdentityResolver" not in source
    assert "resolver_for_script" not in source


def test_default_wiring_injects_no_resolver() -> None:
    """build_in_memory_dependencies must not default one in."""
    from sanuvia.adapters.wiring import build_in_memory_dependencies

    deps = build_in_memory_dependencies(appraiser=ScriptedAppraiser({}))
    assert deps.identity_resolver is None
