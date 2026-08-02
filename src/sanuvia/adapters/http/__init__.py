"""HTTP adapter — the engineering review harness.

A thin layer that sits *above* the existing Application API. It contains no
reasoning: controllers only call ``ReasoningService`` / ``WorldModelView`` and
execute the existing artifact modules (reasoning_trace, reasoning_graph,
exit_test). The browser talks only to this HTTP layer; this HTTP layer talks only
to the Application API and reads persisted artifacts through the existing ports.

    Browser → HTTP adapter → Application API → Reasoning Engine → Persistence

This is a diagnostic tool for remotely inspecting and validating the Persistent
Reasoning Core. It is deliberately NOT the Phase 1 conversation experience.
"""
