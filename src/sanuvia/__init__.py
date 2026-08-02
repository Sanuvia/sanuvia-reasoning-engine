"""Sanuvia — Persistent Reasoning Core (Phase 0).

The thesis this package exists to prove (see "Why Isn't Sanuvia Just an LLM
Wrapper?"): the foundation model does not own the persistent reasoning state —
Sanuvia does. This package is the state that reasons *across* inferences:
evidence, models, hypotheses, uncertainty, and revision history that are
versioned, typed, and traceable.

Architecture (clean / hexagonal — deployment-agnostic):

    sanuvia.domain        Pure reasoning objects and invariants. No framework,
                          no cloud SDK, no foundation model, no I/O. The data
                          model here is the single source of truth regardless
                          of where the system is deployed.

    sanuvia.application   Use cases (Core Loop, capabilities) expressed only
                          against ports (interfaces). Knows *what* must happen,
                          never *where* state lives. [added incrementally]

    sanuvia.adapters      Concrete implementations of the ports: persistence,
                          API, foundation-model access. Cloud-specific code, if
                          any, lives here only. [added incrementally]

Scope is strictly Phase 0 (Persistent Reasoning Core). No UI, no mediation, no
Safety Gateways, no Content Layer enforcement — those begin at Phase 2. Unresolved
transition functions (revision escalation, recognition-condition computation,
inquiry reopening thresholds) are represented as data / interfaces only and are
never hard-coded to fake a result.

Source of truth: Sanuvia Implementation Programme v1.3; Phase 1 Prototype Brief;
System Ownership & Runtime Architecture artefacts (FR-* requirements).
"""
